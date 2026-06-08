"""MiniSFS 主入口：可视化演示。

初始化所有模块，实现主循环：
    输入 -> 物理更新 -> 碰撞检测 -> 尾迹记录 -> 渲染

使用固定时间步长保证物理稳定性，渲染帧率独立于物理帧率。
默认场景：恒星 + 行星绕质心运动 + 可发射探测器。
"""

import math
import sys
from typing import Dict, List, Optional, Tuple

import numpy as np
import pygame

from src.config import (
    BODY_TYPE_CHARGED,
    BODY_TYPE_PLANET,
    BODY_TYPE_PROBE,
    BODY_TYPE_STAR,
    DEFAULT_CHARGE_CHARGED,
    DEFAULT_MASS_CHARGED,
    DEFAULT_MASS_PLANET,
    DEFAULT_MASS_PROBE,
    DEFAULT_MASS_STAR,
    DEFAULT_RADIUS_CHARGED,
    DEFAULT_RADIUS_PLANET,
    DEFAULT_RADIUS_PROBE,
    DEFAULT_RADIUS_STAR,
    GAME_STATE_PAUSED,
    GAME_STATE_PLAYING,
    SUBSTEPS,
    TARGET_FPS,
    TIME_STEP,
    WINDOW_HEIGHT,
    WINDOW_WIDTH,
    WORLD_SCALE,
)
from src.core.types import (
    BODY_TYPE,
    CHARGE,
    IS_ACTIVE,
    IS_STATIC,
    MASS,
    RADIUS,
    VX,
    VY,
    X,
    Y,
    make_body,
)
from src.input.handler import InputHandler
from src.physics.engine import PhysicsEngine
from src.quadtree.trail import TrailBuffer
from src.rendering.camera import Camera
from src.rendering.effects import ParticleSystem
from src.rendering.hud import HUDManager
from src.rendering.renderer import Renderer

# ============================================================================
# 默认场景创建
# ============================================================================


def create_default_scene() -> np.ndarray:
    """创建默认演示场景。

    包含：
        - 1 颗大质量静态恒星（中心）
        - 1 颗行星绕恒星轨道运动
        - 1 颗更小的卫星绕行星轨道运动
        - 1 个初始静止的探测器（便于玩家操作）

    天体参数经过调整，在 WORLD_SCALE = 1e9 m/px 下肉眼可见。

    Returns:
        shape (N, NUM_FIELDS) 的天体状态数组
    """
    scale = WORLD_SCALE  # 1e9 m/px

    bodies_list = []

    # 1. 中心恒星（静态）
    star = make_body(
        x=0.0, y=0.0,
        vx=0.0, vy=0.0,
        mass=DEFAULT_MASS_STAR,  # 1e30
        radius=scale * DEFAULT_RADIUS_STAR,  # 20 * 1e9 = 2e10 m
        body_type=BODY_TYPE_STAR,
        is_static=True,
    )
    bodies_list.append(star)

    # 2. 行星（绕恒星公转）
    # 轨道参数：约 150px 半径
    orbit_radius = 150.0 * scale  # 1.5e11 m
    planet_mass = DEFAULT_MASS_PLANET  # 5e28
    # 圆周运动速度 v = sqrt(G * M / r)
    orbital_speed = math.sqrt(
        DEFAULT_MASS_STAR * 6.67430e-11 / orbit_radius
    )

    planet = make_body(
        x=orbit_radius, y=0.0,
        vx=0.0, vy=orbital_speed,
        mass=planet_mass,
        radius=scale * DEFAULT_RADIUS_PLANET,  # 8 * 1e9 = 8e9 m
        body_type=BODY_TYPE_PLANET,
    )
    bodies_list.append(planet)

    # 3. 卫星（绕行星公转）
    moon_orbit = 40.0 * scale  # 4e10 m
    moon_mass = 1.0e27

    # 卫星相对于行星的速度
    moon_orbital_speed = math.sqrt(
        planet_mass * 6.67430e-11 / moon_orbit
    )
    # 卫星相对于恒星的位置和速度 = 行星的位置和速度 + 卫星的相对位置和速度
    moon = make_body(
        x=orbit_radius + moon_orbit, y=0.0,
        vx=0.0, vy=orbital_speed + moon_orbital_speed,
        mass=moon_mass,
        radius=scale * 5.0,  # 5px
        body_type=BODY_TYPE_PLANET,
    )
    bodies_list.append(moon)

    # 4. 探测器（初始位于行星附近）
    probe_offset = 60.0 * scale
    probe = make_body(
        x=orbit_radius - probe_offset, y=0.0,
        vx=0.0, vy=orbital_speed,
        mass=DEFAULT_MASS_PROBE,
        radius=scale * DEFAULT_RADIUS_PROBE,
        body_type=BODY_TYPE_PROBE,
    )
    bodies_list.append(probe)

    # 合并所有天体
    return np.vstack(bodies_list)


def create_collision_scene() -> np.ndarray:
    """创建可选的碰撞演示场景（2组天体对撞）。

    Returns:
        shape (N, NUM_FIELDS) 的天体状态数组
    """
    scale = WORLD_SCALE

    bodies_list = []

    # 左侧恒星
    star1 = make_body(
        x=-100.0 * scale, y=0.0,
        vx=2e3, vy=0.0,
        mass=1.0e29,
        radius=scale * 12.0,
        body_type=BODY_TYPE_STAR,
    )
    bodies_list.append(star1)

    # 右侧恒星
    star2 = make_body(
        x=100.0 * scale, y=0.0,
        vx=-2e3, vy=0.0,
        mass=1.0e29,
        radius=scale * 12.0,
        body_type=BODY_TYPE_STAR,
    )
    bodies_list.append(star2)

    return np.vstack(bodies_list)


# ============================================================================
# 工具函数
# ============================================================================


def add_body_to_array(
    bodies: np.ndarray,
    body_data: np.ndarray,
) -> np.ndarray:
    """向天体数组添加一个新天体。

    Args:
        bodies: 现有天体数组
        body_data: shape (1, NUM_FIELDS) 的新天体数据

    Returns:
        合并后的天体数组
    """
    return np.vstack([bodies, body_data])


def remove_body_from_array(
    bodies: np.ndarray, body_id: int
) -> np.ndarray:
    """从天体数组中移除指定天体。

    Args:
        bodies: 现有天体数组
        body_id: 要移除的天体行索引

    Returns:
        移除后的天体数组
    """
    if body_id < 0 or body_id >= bodies.shape[0]:
        return bodies

    # 标记为不活跃（保持数组索引稳定）
    bodies[body_id, IS_ACTIVE] = 0.0
    # 重新筛选活跃天体
    active = bodies[bodies[:, IS_ACTIVE] == 1.0]
    return active


# ============================================================================
# 主函数
# ============================================================================


def main() -> None:
    """MiniSFS 主入口。

    初始化所有模块，运行主循环。"""
    pygame.init()
    pygame.display.set_caption("MiniSFS")

    # 创建模块实例
    renderer = Renderer(WINDOW_WIDTH, WINDOW_HEIGHT)
    camera = Camera(WINDOW_WIDTH, WINDOW_HEIGHT, WORLD_SCALE)
    physics_engine = PhysicsEngine(
        substeps=SUBSTEPS,
        use_quadtree=False,
    )
    trail_buffer = TrailBuffer()
    input_handler = InputHandler()
    hud = HUDManager()
    particle_system = ParticleSystem()

    # 场景
    bodies = create_default_scene()

    # 游戏状态
    game_state: str = GAME_STATE_PLAYING
    clock = pygame.time.Clock()
    running = True

    # 物理时间步
    physics_dt = TIME_STEP  # 固定 1/60 秒
    accumulator = 0.0
    # 基准时间速度：世界尺度 1e9 m/px，需要 ~3e6 倍加速轨道才肉眼可见
    BASE_TIME_SPEED = 3_000_000.0
    time_speed = BASE_TIME_SPEED
    time_multiplier = 1.0  # 相对于基准速度的倍率（1x, 2x, 4x）
    is_paused = False

    # 工具状态
    active_tool: Optional[str] = None

    # 瞄准状态
    is_aiming = False
    aim_start_screen: Tuple[int, int] = (0, 0)
    aim_start_world: Tuple[float, float] = (0.0, 0.0)
    aim_current_world: Tuple[float, float] = (0.0, 0.0)

    # 显示尾迹
    show_trails = True

    # 抓取拖拽状态
    is_grabbing = False
    grabbed_body_id: Optional[int] = None

    # 当前选中天体
    selected_body_id: Optional[int] = None

    # 预测轨迹缓存
    predicted_trajectory: Optional[np.ndarray] = None
    _prediction_frame_counter: int = 0  # 仅每 N 帧重新计算预测轨迹
    _last_predicted_body_id: Optional[int] = None  # 跟踪上次选中的探测器 ID

    # ==================================================================
    # 主循环
    # ==================================================================

    while running:
        frame_dt = min(clock.tick(TARGET_FPS) / 1000.0, 0.05)  # 最大 50ms

        # ================================================================
        # 1. 输入处理
        # ================================================================

        commands: List[str] = []

        for event in pygame.event.get():
            # HUD 优先处理事件
            hud_cmd = hud.handle_event(event)
            if hud_cmd is not None:
                commands.append(hud_cmd)
                # 工具栏的点击不传给 InputHandler
                if hud_cmd.startswith("TOOL_"):
                    continue
                # 时间控制的事件也跳过 InputHandler
                if hud_cmd in ("PLAY_PAUSE", "FAST_2X", "FAST_4X", "REWIND"):
                    continue

            # InputHandler 处理（传入 bodies 和 camera 用于抓取检测）
            inp_cmd = input_handler.handle_event(event, bodies, camera)
            if inp_cmd is not None:
                commands.append(inp_cmd)

        # 键盘持续按下的方向键
        keys = pygame.key.get_pressed()
        if keys[pygame.K_LEFT]:
            commands.append("PAN_LEFT")
        if keys[pygame.K_RIGHT]:
            commands.append("PAN_RIGHT")
        if keys[pygame.K_UP]:
            commands.append("PAN_UP")
        if keys[pygame.K_DOWN]:
            commands.append("PAN_DOWN")

        # ================================================================
        # 2. 命令处理
        # ================================================================

        for cmd in commands:
            if cmd == "QUIT":
                running = False

            # --- 相机控制 ---
            elif cmd == "RESET_CAMERA":
                camera.reset()
                selected_body_id = None

            elif cmd.startswith("PAN:"):
                parts = cmd.split(":")
                if len(parts) >= 2:
                    coords = parts[1].split(",")
                    if len(coords) == 2:
                        dx = float(coords[0])
                        dy = float(coords[1])
                        # 死区阈值：抖动 < 3px 忽略
                        if abs(dx) + abs(dy) > 3:
                            camera.pan(-dx, -dy)

            elif cmd == "PAN_LEFT":
                camera.pan(-500.0 * frame_dt, 0)
            elif cmd == "PAN_RIGHT":
                camera.pan(500.0 * frame_dt, 0)
            elif cmd == "PAN_UP":
                camera.pan(0, -500.0 * frame_dt)
            elif cmd == "PAN_DOWN":
                camera.pan(0, 500.0 * frame_dt)

            elif cmd.startswith("ZOOM_IN"):
                parts = cmd.split(":")
                sx_str = parts[1].split(",")
                sx, sy = int(sx_str[0]), int(sx_str[1])
                camera.zoom_at(1.1, sx, sy)

            elif cmd.startswith("ZOOM_OUT"):
                parts = cmd.split(":")
                sx_str = parts[1].split(",")
                sx, sy = int(sx_str[0]), int(sx_str[1])
                camera.zoom_at(1.0 / 1.1, sx, sy)

            # --- 时间控制 ---
            elif cmd == "TOGGLE_PAUSE":
                is_paused = not is_paused
                hud.set_play_pause_state(is_paused)

            elif cmd == "PLAY_PAUSE":
                is_paused = not is_paused
                hud.set_play_pause_state(is_paused)

            elif cmd == "FAST_2X":
                # 切换 1x ↔ 2x（相对于基础速度）
                time_multiplier = 2.0 if time_multiplier == 1.0 else 1.0
                time_speed = BASE_TIME_SPEED * time_multiplier
                hud.set_time_speed(time_multiplier)

            elif cmd == "FAST_4X":
                # 切换 1x ↔ 4x（相对于基础速度）
                time_multiplier = 4.0 if time_multiplier == 1.0 else 1.0
                time_speed = BASE_TIME_SPEED * time_multiplier
                hud.set_time_speed(time_multiplier)

            elif cmd == "REWIND":
                # REWIND 重置为 1x
                time_multiplier = 1.0
                time_speed = BASE_TIME_SPEED
                hud.set_time_speed(1.0)

            # --- 工具选择 ---
            elif cmd.startswith("TOOL_"):
                if active_tool == cmd:
                    active_tool = None  # 取消选择
                else:
                    active_tool = cmd
                hud.set_tool_active(active_tool)

            # --- 自定义粒子参数调节 ---
            elif cmd.startswith("CUSTOM_"):
                hud.handle_custom_param(cmd)

            # --- 鼠标点击 ---
            elif cmd.startswith("CLICK:"):
                parts = cmd.split(":")
                sx_str = parts[1].split(",")
                sx, sy = int(sx_str[0]), int(sx_str[1])

                # 检查是否在 UI 区域
                if sx < 50 or sy > WINDOW_HEIGHT - 50:  # 工具栏或控制栏区域
                    continue

                if active_tool:
                    # 使用工具放置天体
                    world_x, world_y = camera.screen_to_world(sx, sy)
                    mass, radius, charge, body_type = hud.get_default_body_params(active_tool)

                    new_body = make_body(
                        x=world_x, y=world_y,
                        vx=0.0, vy=0.0,
                        mass=mass,
                        radius=radius * WORLD_SCALE,  # 将像素半径转为世界单位
                        charge=charge,
                        body_type=int(body_type),
                    )
                    bodies = add_body_to_array(bodies, new_body)

                    # 自定义粒子：使用面板配置的速度（方向向上）
                    if active_tool == "TOOL_CUSTOM":
                        bodies[-1, VY] = -hud.custom_speed  # 向上发射

                    # 如果放置的是探测器，选择它并允许瞄准
                    if int(body_type) == BODY_TYPE_PROBE:
                        selected_body_id = bodies.shape[0] - 1
                        renderer.selected_body_id = selected_body_id
                        hud.set_selected_body(bodies[selected_body_id], selected_body_id)

                    # 放置后保持工具激活（可连续放置）
                else:
                    # 选择天体
                    found_id = input_handler.find_body_at_screen_pos(sx, sy, bodies, camera)
                    if found_id is not None:
                        selected_body_id = found_id
                        renderer.selected_body_id = found_id
                        hud.set_selected_body(bodies[found_id], found_id)
                    else:
                        # 取消选择
                        selected_body_id = None
                        renderer.selected_body_id = None
                        hud.set_selected_body(None, -1)

            # --- 左键抓取拖拽 ---
            elif cmd.startswith("GRAB_START:"):
                parts = cmd.split(":")
                sx_str = parts[1].split(",")
                body_id = int(sx_str[0])
                sx, sy = int(sx_str[1]), int(sx_str[2])

                if active_tool:
                    # 有工具激活时不进入抓取模式，重置 handler 状态
                    input_handler.reset_grab()
                    # 当作工具放置处理（与 CLICK 相同逻辑）
                    if sx < 50 or sy > WINDOW_HEIGHT - 50:
                        continue
                    world_x, world_y = camera.screen_to_world(sx, sy)
                    mass, radius, charge, body_type = hud.get_default_body_params(active_tool)
                    new_body = make_body(
                        x=world_x, y=world_y,
                        vx=0.0, vy=0.0,
                        mass=mass,
                        radius=radius * WORLD_SCALE,
                        charge=charge,
                        body_type=int(body_type),
                    )
                    bodies = add_body_to_array(bodies, new_body)
                    if int(body_type) == BODY_TYPE_PROBE:
                        selected_body_id = bodies.shape[0] - 1
                        renderer.selected_body_id = selected_body_id
                        hud.set_selected_body(bodies[selected_body_id], selected_body_id)
                else:
                    # 进入抓取模式
                    is_grabbing = True
                    grabbed_body_id = body_id
                    is_paused = True
                    hud.set_play_pause_state(True)
                    # 选中被抓取的天体
                    selected_body_id = body_id
                    renderer.selected_body_id = body_id
                    hud.set_selected_body(bodies[body_id], body_id)

            elif cmd.startswith("GRAB_DRAG:"):
                parts = cmd.split(":")
                coords = parts[1].split(",")
                sx, sy = int(coords[1]), int(coords[2])
                if grabbed_body_id is not None and grabbed_body_id < bodies.shape[0]:
                    wx, wy = camera.screen_to_world(sx, sy)
                    bodies[grabbed_body_id, X] = wx
                    bodies[grabbed_body_id, Y] = wy

            elif cmd == "GRAB_END":
                if grabbed_body_id is not None:
                    trail_buffer.clear(grabbed_body_id)  # 清除拖拽产生的跳跃尾迹
                    bodies[grabbed_body_id, VX] = 0.0
                    bodies[grabbed_body_id, VY] = 0.0
                is_grabbing = False
                grabbed_body_id = None
                is_paused = False
                hud.set_play_pause_state(False)

            # --- 右键 ---
            elif cmd.startswith("RIGHT_CLICK:"):
                parts = cmd.split(":")
                sx_str = parts[1].split(",")
                sx, sy = int(sx_str[0]), int(sx_str[1])

                # 如果工具激活，取消工具
                if active_tool:
                    active_tool = None
                    hud.set_tool_active(None)
                    continue

                # 检查是否在现有探测器上点击
                found_id = input_handler.find_body_at_screen_pos(sx, sy, bodies, camera)
                if found_id is not None and int(bodies[found_id, BODY_TYPE]) == BODY_TYPE_PROBE:
                    # 开始瞄准
                    is_aiming = True
                    input_handler.start_aiming()
                    aim_start_screen = (sx, sy)
                    world_x, world_y = camera.screen_to_world(sx, sy)
                    aim_start_world = (world_x, world_y)
                    selected_body_id = found_id
                    renderer.selected_body_id = found_id
                    hud.set_selected_body(bodies[found_id], found_id)
                else:
                    # 取消选择
                    selected_body_id = None
                    renderer.selected_body_id = None
                    hud.set_selected_body(None, -1)
                    active_tool = None
                    hud.set_tool_active(None)

            # --- 双击：跟随天体 ---
            elif cmd.startswith("DOUBLE_CLICK:"):
                parts = cmd.split(":")
                sx_str = parts[1].split(",")
                sx, sy = int(sx_str[0]), int(sx_str[1])
                found_id = input_handler.find_body_at_screen_pos(sx, sy, bodies, camera)
                if found_id is not None:
                    wx = float(bodies[found_id, X])
                    wy = float(bodies[found_id, Y])
                    camera.follow(wx, wy)

            # --- 发射探测器 ---
            elif cmd.startswith("LAUNCH_PROBE:"):
                parts = cmd.split(":")
                if len(parts) >= 2:
                    coords = parts[1].split(",")
                    if len(coords) == 4:
                        start_x = float(coords[0])
                        start_y = float(coords[1])
                        dx = float(coords[2])
                        dy = float(coords[3])

                    # 转换为世界坐标速度
                    # 拖拽方向的反向为发射方向，力度与拖拽距离成正比
                    world_dx = dx * WORLD_SCALE / camera.zoom
                    world_dy = dy * WORLD_SCALE / camera.zoom
                    launch_speed = min(
                        math.sqrt(world_dx**2 + world_dy**2),
                        1.0e6,  # 最大速度限制
                    )

                    if launch_speed > 100.0 and selected_body_id is not None:
                        idx = selected_body_id
                        if idx < bodies.shape[0]:
                            # 方向：鼠标拖拽方向的反向
                            angle = math.atan2(-world_dy, -world_dx)
                            bodies[idx, VX] = math.cos(angle) * launch_speed
                            bodies[idx, VY] = math.sin(angle) * launch_speed

                            # 尾焰粒子
                            sx_world = float(bodies[idx, X])
                            sy_world = float(bodies[idx, Y])
                            psx, psy = camera.world_to_screen(sx_world, sy_world)
                            particle_system.emit_probe_exhaust(psx, psy, angle)

                    is_aiming = False

            elif cmd == "DELETE_SELECTED":
                if selected_body_id is not None:
                    trail_buffer.clear(selected_body_id)
                    bodies = remove_body_from_array(bodies, selected_body_id)
                    selected_body_id = None
                    renderer.selected_body_id = None
                    hud.set_selected_body(None, -1)

            elif cmd == "MENU":
                running = False

        # ================================================================
        # 3. 物理更新（固定时间步）
        # ================================================================

        if not is_paused and not is_grabbing:
            if time_speed > 100:
                # 高倍速：直接放大 dt（避免数百万小步积累）
                # 物理引擎内部用 SUBSTEPS=4 拆分，RK4 能保证稳定
                big_dt = physics_dt * time_speed
                bodies = physics_engine.update(bodies, big_dt)
            else:
                accumulator += frame_dt * time_speed
                max_accumulate = physics_dt * 10
                if accumulator > max_accumulate:
                    accumulator = max_accumulate
                while accumulator >= physics_dt:
                    bodies = physics_engine.update(bodies, physics_dt)
                    accumulator -= physics_dt
        else:
            # 暂停时重置累积器
            accumulator = 0.0

        # ================================================================
        # 4. 尾迹记录
        # ================================================================

        if is_grabbing and grabbed_body_id is not None:
            trail_buffer.push_all(bodies, exclude={grabbed_body_id})
        else:
            trail_buffer.push_all(bodies)

        # ================================================================
        # 5. 更新尾迹后的数据
        # ================================================================

        # 获取尾迹数据
        trails: Dict[int, List[Tuple[float, float]]] = {}
        if show_trails:
            trails = trail_buffer.get_all_trails()

        # 跟随选中天体
        if selected_body_id is not None and not is_aiming:
            if selected_body_id < bodies.shape[0] and bodies[selected_body_id, IS_ACTIVE] == 1.0:
                # 仅当按下 F 键时跟随，否则不自动跟随
                # 或者在双击后自动跟随（已在 DOUBLE_CLICK 中处理）
                pass
            else:
                # 选中的天体已消失
                selected_body_id = None
                renderer.selected_body_id = None
                hud.set_selected_body(None, -1)

        # 预测轨迹（选中探测器时，每 3 帧重新计算并缓存；抓取时跳过）
        _prediction_frame_counter += 1
        should_recalc = (
            selected_body_id is not None
            and selected_body_id < bodies.shape[0]
            and int(bodies[selected_body_id, BODY_TYPE]) == BODY_TYPE_PROBE
            and not is_grabbing
        )
        # 切换选中天体时立即重新计算
        if should_recalc and selected_body_id != _last_predicted_body_id:
            _prediction_frame_counter = 0
            _last_predicted_body_id = selected_body_id
        if not should_recalc:
            _last_predicted_body_id = None

        if should_recalc and _prediction_frame_counter % 6 == 1:
            probe_data = bodies[selected_body_id:selected_body_id + 1].copy()
            other_bodies = np.delete(bodies, selected_body_id, axis=0)
            if other_bodies.shape[0] > 0:
                # 使用与模拟相同的 dt，预测约 1 秒视觉时间
                if time_speed > 100:
                    pred_dt = physics_dt * time_speed  # 和模拟一样的 dt
                    # 1 秒的视觉步数 = 60fps / multiplier
                    pred_steps = int(TARGET_FPS / max(1, time_multiplier))
                    pred_steps = max(3, min(pred_steps, 60))
                else:
                    pred_dt = physics_dt
                    pred_steps = 60
                pred = physics_engine.predict_trajectory(
                    probe_data, other_bodies, steps=pred_steps, dt=pred_dt
                )
                if pred.shape[0] > 0:
                    predicted_trajectory = pred
                else:
                    predicted_trajectory = None
            else:
                predicted_trajectory = None
        elif not should_recalc:
            predicted_trajectory = None

        # 更新粒子系统
        particle_system.update(frame_dt)

        # ================================================================
        # 6. 渲染
        # ================================================================

        # 更新瞄准线
        if is_aiming and selected_body_id is not None:
            world_x, world_y = camera.screen_to_world(
                input_handler.mouse_screen_x,
                input_handler.mouse_screen_y,
            )
            aim_current_world = (world_x, world_y)

        # 渲染
        renderer.render(bodies, trails, camera)

        # 绘制瞄准线
        if is_aiming:
            start_screen = camera.world_to_screen(
                aim_start_world[0], aim_start_world[1]
            )
            end_screen = (
                input_handler.mouse_screen_x,
                input_handler.mouse_screen_y,
            )
            ddx = end_screen[0] - start_screen[0]
            ddy = end_screen[1] - start_screen[1]
            dist = math.sqrt(ddx*ddx + ddy*ddy)
            if dist > 5:
                # 从探测器指向鼠标的线（蓝色瞄准线）
                pygame.draw.line(
                    renderer.screen,
                    (100, 200, 255, 160),
                    start_screen, end_screen, 2,
                )
                # 发射方向指示（反方向，橙色）
                launch_end = (
                    start_screen[0] - int(ddx * 1.5),
                    start_screen[1] - int(ddy * 1.5),
                )
                pygame.draw.line(
                    renderer.screen,
                    (255, 180, 50, 200),
                    start_screen, launch_end, 3,
                )

        # 绘制预测轨迹
        if predicted_trajectory is not None and predicted_trajectory.shape[0] > 1:
            renderer.render_predicted_trajectory(predicted_trajectory, camera)

        # 绘制粒子
        particle_system.render(renderer.screen)

        # 绘制 HUD
        hud.draw(renderer.screen)
        renderer.render_hud(game_state)

        # 更新窗口标题
        actual_fps = clock.get_fps()
        paused_indicator = " PAUSED" if is_paused else ""
        grabbing_indicator = " GRABBING" if is_grabbing else ""
        speed_indicator = f" {time_multiplier:.0f}x" if time_multiplier > 1 else ""
        pygame.display.set_caption(
            f"MiniSFS{grabbing_indicator}{paused_indicator}{speed_indicator}"
            f" - 天体: {bodies.shape[0]}"
            f" - zoom: {camera.zoom:.1f}"
            f" - {actual_fps:.0f} FPS"
        )

        # 刷新显示
        pygame.display.flip()

    # ================================================================
    # 退出
    # ================================================================
    pygame.quit()
    sys.exit(0)


if __name__ == "__main__":
    main()
