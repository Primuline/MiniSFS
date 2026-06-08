"""MiniSFS 集成测试套件。

测试各模块之间的配合与数据流，覆盖物理引擎、相机、输入处理器、
尾迹缓冲区等核心模块的跨模块交互。

所有涉及 Pygame 窗口的测试使用 dummy video driver 模式。
"""

import math
import os

import numpy as np
import pytest

from src.config import (
    CLICK_SELECTION_RADIUS,
    COULOMB_CONSTANT,
    GRAVITATIONAL_CONSTANT,
    SOFTENING,
    WORLD_SCALE,
)
from src.core.types import (
    BODY_TYPE_PLANET,
    BODY_TYPE_STAR,
    IS_ACTIVE,
    IS_STATIC,
    MASS,
    VX,
    VY,
    X,
    Y,
    make_body,
)
from src.input.handler import InputHandler
from src.main import create_default_scene
from src.physics.engine import PhysicsEngine
from src.quadtree.trail import TrailBuffer
from src.rendering.camera import Camera


# ============================================================================
# fixture: Pygame dummy 模式
# ============================================================================


@pytest.fixture(scope="module")
def pygame_dummy() -> None:
    """使用 dummy video driver 初始化 Pygame，避免打开真实窗口。"""
    os.environ["SDL_VIDEODRIVER"] = "dummy"
    import pygame
    pygame.init()
    pygame.display.set_mode((1, 1))
    yield
    pygame.quit()


# ============================================================================
# 辅助函数
# ============================================================================


def _create_two_body_circular(
    m_center: float = 1.0e30,
    m_orbiter: float = 5.0e28,
    orbit_radius: float = 1.5e11,
    center_static: bool = True,
) -> np.ndarray:
    """创建 1 个中心天体 + 1 个绕行天体的两体系统。

    Args:
        m_center: 中心天体质量 (kg)
        m_orbiter: 绕行天体质量 (kg)
        orbit_radius: 轨道半径 (m)
        center_static: 中心天体是否静态

    Returns:
        shape (2, NUM_FIELDS) 的天体状态数组
    """
    orbital_speed = math.sqrt(
        GRAVITATIONAL_CONSTANT * m_center / orbit_radius
    )
    b1 = make_body(
        x=0.0, y=0.0,
        vx=0.0, vy=0.0,
        mass=m_center,
        radius=1.0e6,
        body_type=BODY_TYPE_STAR,
        is_static=center_static,
    )
    b2 = make_body(
        x=orbit_radius, y=0.0,
        vx=0.0, vy=orbital_speed,
        mass=m_orbiter,
        radius=1.0e6,
        body_type=BODY_TYPE_PLANET,
    )
    return np.vstack([b1, b2])


# ============================================================================
# 测试类
# ============================================================================


class TestPhysicsIntegration:
    """物理引擎集成测试。"""

    def test_physics_bodies_move(self) -> None:
        """验证物理更新后非静态天体会移动，静态恒星不动。"""
        engine = PhysicsEngine(softening=SOFTENING)
        bodies = create_default_scene()
        dt = 1.0 / 60.0

        # 记录更新前各天体位置
        positions_before = bodies[:, [X, Y]].copy()

        # 执行一次物理更新
        bodies = engine.update(bodies, dt)

        # 遍历所有天体检查移动情况
        for i in range(bodies.shape[0]):
            is_static = bool(bodies[i, IS_STATIC])
            is_active = bool(bodies[i, IS_ACTIVE])

            if not is_active:
                continue

            dx = float(bodies[i, X] - positions_before[i, 0])
            dy = float(bodies[i, Y] - positions_before[i, 1])
            moved = math.sqrt(dx**2 + dy**2) > 0.0

            if is_static:
                assert not moved, f"天体 {i}（静态）不应该移动"
            else:
                assert moved, f"天体 {i}（非静态）应该移动"

    def test_energy_conservation(self) -> None:
        """两体圆周运动 100 步后能量波动 < 0.1%。"""
        engine = PhysicsEngine(g=GRAVITATIONAL_CONSTANT, softening=SOFTENING)
        # 使用一个静态超大中心天体
        m_center = 1.0e30
        m_orbiter = 5.0e28
        orbit_r = 1.5e11

        bodies = _create_two_body_circular(
            m_center=m_center,
            m_orbiter=m_orbiter,
            orbit_radius=orbit_r,
            center_static=True,
        )

        dt = 1.0 / 60.0
        n_steps = 100

        e0 = engine.get_total_energy(bodies)
        energies = [e0]

        for _ in range(n_steps):
            bodies = engine.update(bodies, dt)
            energies.append(engine.get_total_energy(bodies))

        e_max = max(energies)
        e_min = min(energies)
        e_range = (e_max - e_min) / abs(e0) * 100  # 百分比

        assert e_range < 0.1, (
            f"能量波动 {e_range:.4f}% 超过 0.1%"
        )

    def test_gravitational_force_symmetric(self) -> None:
        """验证引力 F12 = -F21。"""
        m1 = 1.0e30
        m2 = 5.0e28
        dist = 1.5e11

        b1 = make_body(x=0.0, y=0.0, mass=m1)
        b2 = make_body(x=dist, y=0.0, mass=m2)
        bodies = np.vstack([b1, b2])

        engine = PhysicsEngine(g=GRAVITATIONAL_CONSTANT, softening=SOFTENING)
        forces = engine.compute_forces(bodies)

        # 验证大小相等
        f1_mag = float(np.linalg.norm(forces[0]))
        f2_mag = float(np.linalg.norm(forces[1]))
        assert f1_mag == pytest.approx(f2_mag, rel=1e-10), "引力大小不相等"

        # 验证方向相反
        assert forces[0, 0] == pytest.approx(-forces[1, 0], rel=1e-10), "F_x 不对称"
        assert forces[0, 1] == pytest.approx(-forces[1, 1], rel=1e-10), "F_y 不对称"

        # 验证大小符合牛顿公式
        expected = GRAVITATIONAL_CONSTANT * m1 * m2 / (dist**2)
        assert f1_mag == pytest.approx(expected, rel=1e-10), "引力大小不符合牛顿公式"

    def test_get_body_count_and_state(self) -> None:
        """验证 get_body_count 和 get_body_state 返回正确数据。"""
        engine = PhysicsEngine()
        bodies = create_default_scene()

        count = engine.get_body_count(bodies)
        assert count == 4, f"应有 4 个活跃天体，实际 {count}"

        # 检查第 0 个天体（恒星）
        state = engine.get_body_state(bodies, 0)
        assert state["is_static"] is True
        assert state["mass"] == pytest.approx(1.0e30, rel=1e-10)
        assert state["x"] == 0.0
        assert state["y"] == 0.0

        # 检查第 1 个天体（行星）
        state = engine.get_body_state(bodies, 1)
        assert state["is_static"] is False
        assert state["mass"] == pytest.approx(5.0e28, rel=1e-10)
        assert state["vx"] == 0.0
        assert float(state["vy"]) > 0  # 有切向速度

    def test_get_total_momentum(self) -> None:
        """验证动量查询 API 返回合理值。"""
        engine = PhysicsEngine()
        bodies = create_default_scene()

        px, py = engine.get_total_momentum(bodies)

        # 默认场景总动量应接近零（对称运动）
        total_mass = float(np.sum(bodies[:, MASS]))
        # px 和 py 应为合理的有限值
        assert math.isfinite(px)
        assert math.isfinite(py)
        # 总动量不应为 NaN
        assert not math.isnan(px)
        assert not math.isnan(py)

        # 两体圆周运动动量应该守恒
        binary = _create_two_body_circular(center_static=False)
        px0, py0 = engine.get_total_momentum(binary)
        engine.update(binary, 1.0)
        px1, py1 = engine.get_total_momentum(binary)
        assert px0 == pytest.approx(px1, abs=1.0)
        assert py0 == pytest.approx(py1, abs=1.0)


class TestCameraIntegration:
    """相机集成测试。"""

    def test_camera_pan_zoom(self) -> None:
        """验证相机平移和缩放使 center 和 zoom 变化。"""
        camera = Camera(width=1280, height=720, world_scale=WORLD_SCALE)

        # 初始状态
        assert camera.center_x == 0.0
        assert camera.center_y == 0.0
        assert camera.zoom == 1.0

        # 平移 100, 50 像素
        camera.pan(100.0, 50.0)
        assert camera.center_x != 0.0, "平移后 center_x 应变化"
        assert camera.center_y != 0.0, "平移后 center_y 应变化"

        # 验证方向：正 dx 使世界坐标向右移
        assert camera.center_x > 0.0
        assert camera.center_y > 0.0

        # 缩放
        camera.zoom_at(2.0, 640, 360)
        assert camera.zoom != 1.0, "缩放后 zoom 应变化"
        assert camera.zoom > 1.0, "放大后 zoom 应 > 1"

        # 多次缩放到最大
        camera.zoom_at(10.0, 640, 360)
        assert camera.zoom <= 10.0, "zoom 不应超过最大值"

    def test_camera_get_state(self) -> None:
        """验证 get_state 返回正确的相机状态字典。"""
        camera = Camera(width=1280, height=720, world_scale=WORLD_SCALE)
        camera.pan(200.0, -100.0)
        camera.zoom_at(1.5, 640, 360)

        state = camera.get_state()
        assert "center_x" in state
        assert "center_y" in state
        assert "zoom" in state
        assert state["center_x"] == camera.center_x
        assert state["center_y"] == camera.center_y
        assert state["zoom"] == camera.zoom

    def test_camera_world_screen_transform(self) -> None:
        """验证世界坐标和屏幕坐标的变换一致性。"""
        camera = Camera(width=1280, height=720, world_scale=WORLD_SCALE)

        # 屏幕中心应映射到世界原点 (center_x=0, center_y=0, zoom=1)
        wx, wy = camera.screen_to_world(640, 360)
        assert wx == pytest.approx(0.0, abs=1e-6)
        assert wy == pytest.approx(0.0, abs=1e-6)

        # 世界原点应映射到屏幕中心
        sx, sy = camera.world_to_screen(0.0, 0.0)
        assert sx == 640
        assert sy == 360

        # 平移后重新验证
        camera.pan(100.0, 50.0)
        wx2, wy2 = camera.screen_to_world(640, 360)
        assert wx2 != 0.0

        # round-trip 验证
        sx2, sy2 = camera.world_to_screen(wx2, wy2)
        assert sx2 == 640
        assert sy2 == 360


class TestInputIntegration:
    """输入处理器集成测试。"""

    def test_mouse_click_selects_body(self, pygame_dummy) -> None:
        """模拟鼠标点击天体所在位置应返回该天体 ID。"""
        import pygame

        camera = Camera(width=1280, height=720, world_scale=WORLD_SCALE)
        handler = InputHandler()
        bodies = create_default_scene()

        # 获取第 1 个天体（行星）的屏幕位置
        planet_id = 1
        world_x = float(bodies[planet_id, X])
        world_y = float(bodies[planet_id, Y])
        screen_x, screen_y = camera.world_to_screen(world_x, world_y)

        # 模拟点击
        cmd = handler.inject_mouse_click(screen_x, screen_y, button=1)
        assert cmd.startswith("CLICK:"), f"应生成 CLICK 命令，实际: {cmd}"

        # 验证 find_body_at_screen_pos 能找到该天体
        found_id = handler.find_body_at_screen_pos(
            screen_x, screen_y, bodies, camera
        )
        assert found_id is not None, "应找到天体"
        assert found_id == planet_id, f"应找到行星 ID={planet_id}，实际 {found_id}"

    def test_mouse_drag_pan_camera(self, pygame_dummy) -> None:
        """模拟中键拖拽应使相机中心变化。"""
        import pygame

        camera = Camera(width=1280, height=720, world_scale=WORLD_SCALE)
        handler = InputHandler()

        # 记录初始中心
        initial_center_x = camera.center_x
        initial_center_y = camera.center_y

        # 模拟中键拖拽 100 像素
        cmds = handler.inject_mouse_drag(400, 300, 500, 350, button=2)

        # 应产生中键平移命令 "PAN:dx,dy"
        pan_cmd = None
        for cmd in cmds:
            if cmd.startswith("PAN:"):
                pan_cmd = cmd
                break

        assert pan_cmd is not None, f"应生成 PAN 命令，实际命令: {cmds}"

        # 处理平移命令
        handler.handle_camera_commands(cmds, camera, 1.0)

        # 验证相机中心发生了变化
        assert camera.center_x != initial_center_x, "拖拽后 center_x 应变化"
        assert camera.center_y != initial_center_y, "拖拽后 center_y 应变化"

    def test_keyboard_shortcuts(self, pygame_dummy) -> None:
        """模拟键盘快捷键应返回正确的命令。"""
        import pygame

        handler = InputHandler()

        # 空格 -> TOGGLE_PAUSE
        cmd = handler.inject_key_press("K_SPACE")
        assert cmd == "TOGGLE_PAUSE", f"K_SPACE 应为 TOGGLE_PAUSE，实际: {cmd}"

        # R -> RESET_CAMERA
        cmd = handler.inject_key_press("K_r")
        assert cmd == "RESET_CAMERA", f"K_r 应为 RESET_CAMERA，实际: {cmd}"

        # ESCAPE -> MENU
        cmd = handler.inject_key_press("K_ESCAPE")
        assert cmd == "MENU", f"K_ESCAPE 应为 MENU，实际: {cmd}"

        # F -> FAST_2X
        cmd = handler.inject_key_press("K_f")
        assert cmd == "FAST_2X", f"K_f 应为 FAST_2X，实际: {cmd}"

        # G -> FAST_4X
        cmd = handler.inject_key_press("K_g")
        assert cmd == "FAST_4X", f"K_g 应为 FAST_4X，实际: {cmd}"

        # DELETE -> DELETE_SELECTED
        cmd = handler.inject_key_press("K_DELETE")
        assert cmd == "DELETE_SELECTED", f"K_DELETE 应为 DELETE_SELECTED，实际: {cmd}"

        # T -> TOGGLE_TRAILS
        cmd = handler.inject_key_press("K_t")
        assert cmd == "TOGGLE_TRAILS", f"K_t 应为 TOGGLE_TRAILS，实际: {cmd}"

        # H -> None（未绑定）
        cmd = handler.inject_key_press("K_h")
        assert cmd == "", f"K_h 应为空字符串，实际: {cmd}"

    def test_get_mouse_pos(self, pygame_dummy) -> None:
        """验证 get_mouse_pos 和 inject 的鼠标位置一致。"""
        import pygame

        handler = InputHandler()

        x, y = handler.get_mouse_pos()
        assert x == 0
        assert y == 0

        # 模拟点击更新鼠标位置
        handler.inject_mouse_click(500, 300)
        x, y = handler.get_mouse_pos()
        assert x == 500
        assert y == 300


class TestTrailBufferIntegration:
    """尾迹缓冲区集成测试。"""

    def test_trail_buffer_records_positions(self) -> None:
        """验证 TrailBuffer 正确记录位置、长度和回退。"""
        buffer = TrailBuffer(maxlen=10)

        # 初始状态：无尾迹
        trail = buffer.get_trail(0)
        assert trail == [], "初始尾迹应为空"

        # 模拟 5 帧数据
        for frame in range(5):
            buffer.push_frame(0, float(frame * 10.0), float(frame * 5.0))

        # 验证长度
        trail = buffer.get_trail(0)
        assert len(trail) == 5, f"尾迹长度应为 5，实际 {len(trail)}"

        # 验证坐标正确性
        assert trail[3] == (30.0, 15.0), f"第 4 帧坐标错误: {trail[3]}"

        # 验证 rewind
        # rewind(0, frames=2): 从最新的往后退 2 帧
        # 最新(索引4) = (40, 20), 后退2帧 = (20, 10)
        pos = buffer.rewind(0, frames=2)
        assert pos is not None, "rewind 应返回有效坐标"
        assert pos[0] == pytest.approx(20.0)
        assert pos[1] == pytest.approx(10.0)

        # 历史不足时应返回 None
        pos = buffer.rewind(0, frames=10)
        assert pos is None, "历史不足时应返回 None"

        # 最新帧 rewind(0) = 最后一个
        pos = buffer.rewind(0, frames=0)
        assert pos is not None
        assert pos == (40.0, 20.0)

    def test_trail_buffer_clear(self) -> None:
        """验证清除尾迹操作。"""
        buffer = TrailBuffer(maxlen=10)
        buffer.push_frame(0, 1.0, 2.0)
        buffer.push_frame(1, 3.0, 4.0)

        assert len(buffer) == 2

        # 清除单个
        buffer.clear(0)
        assert buffer.get_trail(0) == []
        assert len(buffer) == 1

        # 清除全部
        buffer.clear_all()
        assert len(buffer) == 0

    def test_trail_buffer_maxlen(self) -> None:
        """验证尾迹最大长度限制。"""
        buffer = TrailBuffer(maxlen=5)
        for frame in range(10):
            buffer.push_frame(0, float(frame), float(frame))

        trail = buffer.get_trail(0)
        assert len(trail) == 5, f"尾迹长度应为 5（maxlen），实际 {len(trail)}"
        # 应保留最后 5 帧: 5, 6, 7, 8, 9
        assert trail[0] == (5.0, 5.0), f"第一帧应为 (5,5)，实际 {trail[0]}"
        assert trail[-1] == (9.0, 9.0), f"最后一帧应为 (9,9)，实际 {trail[-1]}"

    def test_trail_push_all(self) -> None:
        """验证 push_all 为所有活跃天体同时记录尾迹。"""
        buffer = TrailBuffer(maxlen=10)
        bodies = create_default_scene()

        # push_all 一次
        buffer.push_all(bodies)

        # 验证每个活跃天体都有尾迹
        for i in range(bodies.shape[0]):
            trail = buffer.get_trail(i)
            assert len(trail) == 1, f"天体 {i} 应有 1 帧尾迹"
            assert trail[0][0] == pytest.approx(float(bodies[i, X]))
            assert trail[0][1] == pytest.approx(float(bodies[i, Y]))

        # 再 push_all 一次
        buffer.push_all(bodies)
        for i in range(bodies.shape[0]):
            trail = buffer.get_trail(i)
            assert len(trail) == 2, f"天体 {i} 应有 2 帧尾迹"
