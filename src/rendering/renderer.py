"""渲染管线：将物理状态绘制到 Pygame 窗口。

实现 ``IRenderer`` 接口（定义在 ``src.core.interfaces``）。
渲染器**不修改**物理状态，仅读取 BodyState 数组和 TrailBuffer。
"""

import math
from typing import Dict, List, Optional, Tuple
import numpy as np

import numpy as np
import pygame

from src.config import (
    BACKGROUND_COLOR,
    BODY_TYPE_CHARGED,
    BODY_TYPE_PLANET,
    BODY_TYPE_PROBE,
    BODY_TYPE_STAR,
    DEFAULT_RADIUS_CHARGED,
    DEFAULT_RADIUS_PLANET,
    DEFAULT_RADIUS_PROBE,
    DEFAULT_RADIUS_STAR,
    WINDOW_HEIGHT,
    WINDOW_WIDTH,
)
from src.core.interfaces import ICamera, IRenderer
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
)
from src.rendering.effects import (
    StarField,
    draw_placement_trajectory,
    draw_predicted_trajectory,
    draw_trails,
    draw_target_zone,
)


class Renderer(IRenderer):
    """Pygame 渲染器。

    负责将天体状态数组绘制到窗口。
    每帧调用 render() 进行完整绘制。

    Attributes:
        width: 窗口宽度（像素）
        height: 窗口高度（像素）
        star_field: 星云背景
    """

    def __init__(
        self,
        width: int = WINDOW_WIDTH,
        height: int = WINDOW_HEIGHT,
    ) -> None:
        """初始化渲染器。

        Args:
            width: 窗口宽度（像素）
            height: 窗口高度（像素）
        """
        self.width: int = width
        self.height: int = height

        # 创建主窗口
        self.screen: pygame.Surface = pygame.display.set_mode(
            (width, height), pygame.HWSURFACE | pygame.DOUBLEBUF
        )
        pygame.display.set_caption("MiniSFS")

        # 星云背景
        self.star_field: StarField = StarField(
            num_stars_far=200,
            num_stars_near=100,
            width=width,
            height=height,
        )

        # 缓存 surface 用于星空背景
        self._background_surface: Optional[pygame.Surface] = None
        self._background_dirty: bool = True

        # 选中天体 ID
        self.selected_body_id: Optional[int] = None

        # 框选状态
        self.box_select_start: Optional[Tuple[int, int]] = None
        self.box_select_end: Optional[Tuple[int, int]] = None
        self.selected_body_ids: set = set()

        # 累计时间
        self._time: float = 0.0

        # 发光效果缓存
        self._glow_cache: Dict[float, pygame.Surface] = {}

        # 字体
        self._font_small: pygame.font.Font = pygame.font.Font(None, 18)
        self._font_medium: pygame.font.Font = pygame.font.Font(None, 24)
        self._font_large: pygame.font.Font = pygame.font.Font(None, 36)

    # ------------------------------------------------------------------
    # IRenderer 接口方法
    # ------------------------------------------------------------------

    def render(
        self,
        bodies: np.ndarray,
        trails: Dict[int, List[Tuple[float, float]]],
        camera: ICamera,
        fade_factors: Optional[Dict[int, float]] = None,
    ) -> None:
        """渲染一帧画面。

        绘制顺序：背景 -> 尾迹 -> 天体 -> 选中高亮 -> HUD

        Args:
            bodies: shape (N, NUM_FIELDS) 的天体状态数组
            trails: 尾迹数据 {body_id: [(x1,y1), ...]}
            camera: 相机对象
            fade_factors: 尾迹淡出系数 {body_id: fade_factor (0~1)}，可选
        """
        self._time += 1.0 / 60.0  # 近似帧时间

        # 更新背景
        self.star_field.update(1.0 / 60.0)

        # 清屏
        self.screen.fill(BACKGROUND_COLOR)

        # 渲染背景
        self.render_background()

        # 计算每个天体的速度（用于尾迹颜色）
        body_speeds: Dict[int, float] = {}
        for i in range(bodies.shape[0]):
            vx = float(bodies[i, VX])
            vy = float(bodies[i, VY])
            body_speeds[i] = math.sqrt(vx * vx + vy * vy)

        # 绘制尾迹（在星体下方）
        draw_trails(self.screen, trails, body_speeds, camera, fade_factors)

        # 绘制天体
        self._draw_bodies(bodies, camera)

        # 选中天体高亮（单天体 + 多选）
        if self.selected_body_id is not None or len(self.selected_body_ids) > 0:
            self._draw_selection_highlight(bodies, camera)

    def render_background(self) -> None:
        """渲染静态背景（星云、网格等）。"""
        self.star_field.render(self.screen)

    def render_hud(
        self,
        game_state: str,
        score: Optional[Dict[str, float]] = None,
    ) -> None:
        """渲染 HUD 信息。

        Args:
            game_state: 当前游戏状态
            score: 评分数据（可选）
        """
        # 帧率显示在窗口标题，不在这里绘制
        if game_state == "PAUSED":
            pause_text = self._font_large.render("PAUSED", True, (255, 255, 100))
            text_rect = pause_text.get_rect(center=(self.width // 2, 50))
            # 半透明背景
            bg_surf = pygame.Surface((text_rect.width + 20, text_rect.height + 10), pygame.SRCALPHA)
            bg_surf.fill((0, 0, 0, 128))
            self.screen.blit(bg_surf, (text_rect.x - 10, text_rect.y - 5))
            self.screen.blit(pause_text, text_rect)

        # 底部状态栏
        state_colors = {
            "PLAYING": (100, 220, 100),
            "PAUSED": (255, 255, 100),
            "WIN": (100, 255, 200),
            "LOSE": (255, 100, 100),
            "MENU": (200, 200, 200),
        }
        color = state_colors.get(game_state, (200, 200, 200))
        state_text = self._font_small.render(f"State: {game_state}", True, color)
        self.screen.blit(state_text, (10, self.height - 25))

        # 快捷键提示
        hint = "Space:Pause  R:Reset  Esc:Menu"
        hint_text = self._font_small.render(hint, True, (150, 150, 150))
        hr = hint_text.get_rect(right=self.width - 10, bottom=self.height - 5)
        self.screen.blit(hint_text, hr)

    def render_predicted_trajectory(
        self, trajectory: np.ndarray, camera: ICamera
    ) -> None:
        """渲染预测轨迹（虚线/半透明）。

        Args:
            trajectory: shape (M, 2) 的预测轨迹坐标
            camera: 相机对象
        """
        draw_predicted_trajectory(self.screen, trajectory, camera)

    def render_placement_trajectory(
        self,
        result: Dict[str, object],
        camera: ICamera,
    ) -> None:
        """渲染放置速度设定时的轨迹预览。

        Args:
            result: predict_single_star_trajectory 返回的字典
            camera: 相机对象
        """
        draw_placement_trajectory(self.screen, result, camera)

    def render_target_zone(
        self, x: float, y: float, radius: float, camera: ICamera
    ) -> None:
        """渲染目标区域（脉冲动画）。

        Args:
            x, y: 目标中心世界坐标
            radius: 目标区域半径（米）
            camera: 相机对象
        """
        draw_target_zone(self.screen, x, y, radius, camera, self._time)

    # ------------------------------------------------------------------
    # 内部绘制方法
    # ------------------------------------------------------------------

    def _draw_bodies(self, bodies: np.ndarray, camera: ICamera) -> None:
        """绘制所有活跃天体。

        Args:
            bodies: 天体状态数组
            camera: 相机对象
        """
        for i in range(bodies.shape[0]):
            if bodies[i, IS_ACTIVE] == 0.0:
                continue

            body_type = int(bodies[i, BODY_TYPE])
            wx = float(bodies[i, X])
            wy = float(bodies[i, Y])
            if np.isnan(wx) or np.isnan(wy):
                continue  # 跳过位置无效的天体
            radius = float(bodies[i, RADIUS])
            mass = float(bodies[i, MASS])
            vx = float(bodies[i, VX])
            vy = float(bodies[i, VY])
            charge = float(bodies[i, CHARGE])
            is_static = bodies[i, IS_STATIC] == 1.0

            sx, sy = camera.world_to_screen(wx, wy)
            screen_radius = max(1.0, camera.world_distance_to_screen(radius))

            if body_type == BODY_TYPE_STAR:
                self._draw_star(sx, sy, screen_radius, mass)
            elif body_type == BODY_TYPE_PLANET:
                self._draw_planet(sx, sy, screen_radius, mass, is_static)
            elif body_type == BODY_TYPE_PROBE:
                self._draw_probe(sx, sy, screen_radius, vx, vy)
            elif body_type == BODY_TYPE_CHARGED:
                self._draw_charged(sx, sy, screen_radius, charge)

    def _draw_star(self, sx: int, sy: int, radius: float, mass: float) -> None:
        """绘制恒星：径向渐变发光效果。

        Args:
            sx, sy: 屏幕中心坐标
            radius: 屏幕半径（像素）
            mass: 质量（用于颜色）
        """
        # 亮度随质量变化
        intensity = min(1.0, mass / 1e31)
        r = min(255, int(200 + 55 * intensity))
        g = min(255, int(150 + 50 * intensity))
        b = min(220, int(100 + 40 * intensity))

        # 外发光层（大半径半透明，最大 200px 防止 OOM）
        glow_radius = min(radius * 3.0, 200.0)
        glow_surf = self._get_glow_surface(glow_radius, (r, g, b, 40))
        self.screen.blit(glow_surf, (sx - glow_radius, sy - glow_radius))

        # 中发光层（最大 150px）
        mid_radius = min(radius * 2.0, 150.0)
        mid_surf = self._get_glow_surface(mid_radius, (r, g, b, 80))
        self.screen.blit(mid_surf, (sx - mid_radius, sy - mid_radius))

        # 核心（最亮）
        core_radius = radius
        pygame.draw.circle(self.screen, (r, g, b), (sx, sy), int(core_radius))
        pygame.draw.circle(self.screen, (255, 255, 255), (sx, sy), max(1, int(core_radius * 0.4)))

    def _draw_planet(self, sx: int, sy: int, radius: float, mass: float, is_static: bool) -> None:
        """绘制行星：纯色圆 + 阴影。

        Args:
            sx, sy: 屏幕中心坐标
            radius: 屏幕半径（像素）
            mass: 质量（用于颜色）
            is_static: 是否静态天体
        """
        # 质量决定颜色
        intensity = min(1.0, mass / 1e29)
        base_color = (
            int(100 + 100 * intensity),
            int(80 + 120 * intensity),
            int(180 + 50 * intensity),
        )

        if is_static:
            # 静态天体更暗
            base_color = tuple(c // 2 for c in base_color)

        # 主体
        pygame.draw.circle(self.screen, base_color, (sx, sy), int(radius))

        # 阴影（右下角半圆）
        shadow_radius = int(radius)
        if shadow_radius > 2:
            shadow_surf = pygame.Surface((shadow_radius * 2, shadow_radius * 2), pygame.SRCALPHA)
            shadow_surf.fill((0, 0, 0, 0))
            pygame.draw.circle(
                shadow_surf, (0, 0, 0, 60),
                (shadow_radius, shadow_radius), shadow_radius,
            )
            # 只保留右下部分
            clip_surf = pygame.Surface((shadow_radius, shadow_radius), pygame.SRCALPHA)
            clip_surf.fill((0, 0, 0, 0))
            clip_surf.blit(shadow_surf, (0, 0), (shadow_radius, shadow_radius, shadow_radius, shadow_radius))
            self.screen.blit(clip_surf, (sx, sy))

        # 高光（左上角小亮圆）
        if radius > 4:
            highlight_radius = max(1, int(radius * 0.3))
            pygame.draw.circle(
                self.screen, (255, 255, 255, 60),
                (sx - int(radius * 0.25), sy - int(radius * 0.25)),
                highlight_radius,
            )

    def _draw_probe(self, sx: int, sy: int, radius: float, vx: float, vy: float) -> None:
        """绘制探测器：小圆 + 速度方向指示。

        Args:
            sx, sy: 屏幕中心坐标
            radius: 屏幕半径（像素）
            vx, vy: 速度分量
        """
        # 主体
        probe_color = (200, 220, 255)
        pygame.draw.circle(self.screen, probe_color, (sx, sy), max(1, int(radius)))

        # 速度方向指示线
        speed = math.sqrt(vx * vx + vy * vy)
        if speed > 0.1:
            dir_len = radius * 2.5
            dx = vx / speed * dir_len
            dy = vy / speed * dir_len
            end_x = int(sx + dx)
            end_y = int(sy + dy)
            pygame.draw.line(self.screen, (100, 200, 255), (sx, sy), (end_x, end_y), 1)

    def _draw_charged(self, sx: int, sy: int, radius: float, charge: float) -> None:
        """绘制带电粒子：带 +/- 标识。

        Args:
            sx, sy: 屏幕中心坐标
            radius: 屏幕半径（像素）
            charge: 电荷量
        """
        # 颜色：正电荷红色，负电荷蓝色
        if charge > 0:
            color = (255, 80, 80)
            sign = "+"
        else:
            color = (80, 130, 255)
            sign = "-"

        pygame.draw.circle(self.screen, color, (sx, sy), max(1, int(radius)))
        pygame.draw.circle(self.screen, (255, 255, 255), (sx, sy), max(1, int(radius)), 1)

        # 标识字符
        sign_text = self._font_small.render(sign, True, (255, 255, 255))
        tr = sign_text.get_rect(center=(sx, sy))
        self.screen.blit(sign_text, tr)

    def _draw_selection_highlight(self, bodies: np.ndarray, camera: ICamera) -> None:
        """绘制选中天体的高亮圈。

        同时绘制单天体选择（selected_body_id）和多选（selected_body_ids）的高亮。

        Args:
            bodies: 天体状态数组
            camera: 相机对象
        """
        # 收集需要高亮的天体 ID
        highlight_ids: set = set()
        if self.selected_body_id is not None:
            highlight_ids.add(self.selected_body_id)
        highlight_ids.update(self.selected_body_ids)

        for idx in list(highlight_ids):
            if idx >= bodies.shape[0] or bodies[idx, IS_ACTIVE] == 0.0:
                if idx == self.selected_body_id:
                    self.selected_body_id = None
                continue

            wx = float(bodies[idx, X])
            wy = float(bodies[idx, Y])
            radius = float(bodies[idx, RADIUS])
            sx, sy = camera.world_to_screen(wx, wy)
            screen_radius = camera.world_distance_to_screen(radius)

            # 脉动高亮
            pulse = 0.8 + 0.2 * math.sin(self._time * 4)
            highlight_r = screen_radius * 1.5 * pulse
            alpha = int(100 + 80 * (0.5 + 0.5 * math.sin(self._time * 4)))

            # 使用临时 surface 支持透明度
            size = int(highlight_r * 2) + 10
            hl_surf = pygame.Surface((size, size), pygame.SRCALPHA)
            hl_surf.fill((0, 0, 0, 0))
            pygame.draw.circle(
                hl_surf, (0, 200, 255, alpha),
                (size // 2, size // 2),
                highlight_r, 2,
            )
            self.screen.blit(hl_surf, (sx - size // 2, sy - size // 2))

    def _get_glow_surface(self, radius: float, color: Tuple[int, int, int, int]) -> pygame.Surface:
        """获取发光 surface（带缓存）。

        使用缓存的径向渐变圆，避免每帧重复创建。

        Args:
            radius: 发光半径（像素）
            color: RGBA 颜色

        Returns:
            半透明发光 Surface
        """
        # 使用半径作为缓存键（取整到 1px 精度）
        cache_key = round(radius, 0)
        if cache_key not in self._glow_cache:
            safe_radius = min(radius, 200.0)  # 安全上限
            size = int(safe_radius * 2)
            surf = pygame.Surface((size, size), pygame.SRCALPHA)
            surf.fill((0, 0, 0, 0))

            r, g, b, a = color
            cx, cy = size // 2, size // 2

            # 绘制多层半透明圆实现渐变
            layers = 8
            for i in range(layers):
                t = i / layers
                layer_r = radius * (1.0 - t)
                layer_a = int(a * (1.0 - t * 0.8))
                if layer_a <= 0:
                    continue
                pygame.draw.circle(
                    surf, (r, g, b, layer_a),
                    (cx, cy), int(layer_r),
                )

            self._glow_cache[cache_key] = surf

        return self._glow_cache[cache_key]

    # ------------------------------------------------------------------
    # 框选框绘制
    # ------------------------------------------------------------------

    def draw_box_selection(self) -> None:
        """绘制蓝色半透明框选框。

        使用 box_select_start 和 box_select_end 确定选框范围。
        两个坐标的 min/max 确保选框能朝任意方向拖拽。
        只有选框尺寸 > 10px 时才绘制。
        """
        start = self.box_select_start
        end = self.box_select_end
        if start is None or end is None:
            return

        x1, y1 = min(start[0], end[0]), min(start[1], end[1])
        x2, y2 = max(start[0], end[0]), max(start[1], end[1])

        # 小于 10px 的选框不绘制（避免微小点击产生的闪烁）
        if (x2 - x1) < 10 and (y2 - y1) < 10:
            return

        # 半透明填充
        s = pygame.Surface((x2 - x1, y2 - y1), pygame.SRCALPHA)
        s.fill((0, 100, 255, 60))
        self.screen.blit(s, (x1, y1))

        # 边框
        pygame.draw.rect(
            self.screen, (0, 150, 255),
            (x1, y1, x2 - x1, y2 - y1), 1,
        )

    # ------------------------------------------------------------------
    # 自定义粒子放置预览方法
    # ------------------------------------------------------------------

    def draw_placement_preview(
        self, world_x: float, world_y: float,
        radius_world: float, camera: ICamera,
        surface: pygame.Surface,
    ) -> None:
        """绘制虚线放置预览圆 + 十字准星。

        Args:
            world_x: 预览中心世界 x 坐标 (m)
            world_y: 预览中心世界 y 坐标 (m)
            radius_world: 预览半径世界坐标 (m)
            camera: 相机对象
            surface: 目标绘制 Surface
        """
        sx, sy = camera.world_to_screen(world_x, world_y)
        screen_radius = max(2.0, camera.world_distance_to_screen(radius_world))
        int_sr = int(screen_radius)
        isx, isy = int(sx), int(sy)

        color = (200, 200, 255)

        # 虚线圆：32 段，每隔一段绘制
        num_segments = 32
        for i in range(0, num_segments, 2):
            angle1 = 2.0 * math.pi * i / num_segments
            angle2 = 2.0 * math.pi * (i + 1) / num_segments
            x1 = isx + int_sr * math.cos(angle1)
            y1 = isy + int_sr * math.sin(angle1)
            x2 = isx + int_sr * math.cos(angle2)
            y2 = isy + int_sr * math.sin(angle2)
            pygame.draw.line(surface, color, (x1, y1), (x2, y2), 2)

        # 十字准星
        cross_len = max(5, int_sr // 3)
        pygame.draw.line(surface, color, (isx - cross_len, isy), (isx + cross_len, isy), 1)
        pygame.draw.line(surface, color, (isx, isy - cross_len), (isx, isy + cross_len), 1)

        # 中心点
        pygame.draw.circle(surface, color, (isx, isy), 2)

    def draw_velocity_arrow(
        self, start_world: Tuple[float, float],
        end_screen: Tuple[int, int],
        max_length: float,
        camera: ICamera,
        surface: pygame.Surface,
    ) -> None:
        """绘制速度方向箭头（橙色）。

        箭头的方向从 start_world 指向鼠标屏幕位置，长度限制为 max_length 像素。
        超过最大长度时截断但方向不变。

        Args:
            start_world: 箭头起点的世界坐标 (x, y)
            end_screen: 箭头终点的屏幕坐标 (sx, sy)
            max_length: 箭头最大长度（像素）
            camera: 相机对象
            surface: 目标绘制 Surface
        """
        sx0, sy0 = camera.world_to_screen(start_world[0], start_world[1])
        ex, ey = end_screen

        dx = ex - sx0
        dy = ey - sy0
        dist = math.sqrt(dx * dx + dy * dy)

        if dist < 1.0:
            return

        # 截断超过最大长度的箭头
        if dist > max_length:
            dx = dx / dist * max_length
            dy = dy / dist * max_length
            ex = int(sx0 + dx)
            ey = int(sy0 + dy)

        isx0, isy0 = int(sx0), int(sy0)
        iex, iey = int(ex), int(ey)

        # 主线条（橙色，宽度 3）
        arrow_color = (255, 180, 50)
        pygame.draw.line(surface, arrow_color, (isx0, isy0), (iex, iey), 3)

        # 箭头三角形
        arrow_size = 12
        angle = math.atan2(dy, dx)  # 从起点到终点的方向
        wing_angle = math.atan2(1.0, 1.0)  # 约 45 度（实际是 math.pi/4）
        wing_offset = math.pi * 5.0 / 6.0  # 150 度，箭头翼向后张开

        wing1_x = iex + arrow_size * math.cos(angle + wing_offset)
        wing1_y = iey + arrow_size * math.sin(angle + wing_offset)
        wing2_x = iex + arrow_size * math.cos(angle - wing_offset)
        wing2_y = iey + arrow_size * math.sin(angle - wing_offset)

        pygame.draw.polygon(surface, arrow_color, [
            (iex, iey), (int(wing1_x), int(wing1_y)), (int(wing2_x), int(wing2_y))
        ])

    def set_title_fps(self, fps: float) -> None:
        """在窗口标题显示帧率。

        Args:
            fps: 当前帧率
        """
        pygame.display.set_caption(f"MiniSFS - {fps:.0f} FPS")
