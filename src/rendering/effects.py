"""特效模块：尾迹绘制、预测轨道、碰撞粒子特效、星云背景。

提供独立的绘制函数，供 Renderer 调用。
所有函数不修改物理状态，仅读取数据绘制到 Pygame Surface。
"""

import math
import random
from typing import Dict, List, Optional, Tuple, Union

import numpy as np
import pygame

from src.config import (
    BACKGROUND_COLOR,
    TRAIL_ALPHA_NEW,
    TRAIL_ALPHA_OLD,
    TRAIL_COLOR_FAST,
    TRAIL_COLOR_SLOW,
    WINDOW_HEIGHT,
    WINDOW_WIDTH,
)
from src.core.types import VX, VY, X, Y

# ============================================================================
# 星云背景
# ============================================================================


class StarField:
    """星云背景：随机分布的星星，缓慢飘动。

    星星分为两层：
        - 远景层：小、暗、慢速飘动
        - 近景层：大、亮、快速飘动
    """

    def __init__(
        self,
        num_stars_far: int = 200,
        num_stars_near: int = 100,
        width: int = WINDOW_WIDTH,
        height: int = WINDOW_HEIGHT,
    ) -> None:
        """初始化星场。

        Args:
            num_stars_far: 远景星星数量
            num_stars_near: 近景星星数量
            width: 视野宽度（像素）
            height: 视野高度（像素）
        """
        self.width: int = width
        self.height: int = height

        # 远景层
        self.far_stars: List[dict] = []
        for _ in range(num_stars_far):
            self.far_stars.append({
                "x": random.uniform(0, width),
                "y": random.uniform(0, height),
                "radius": random.uniform(0.3, 0.8),
                "brightness": random.uniform(30, 100),
                "drift_x": random.uniform(-0.02, 0.02),
                "drift_y": random.uniform(-0.02, 0.02),
            })

        # 近景层
        self.near_stars: List[dict] = []
        for _ in range(num_stars_near):
            self.near_stars.append({
                "x": random.uniform(0, width),
                "y": random.uniform(0, height),
                "radius": random.uniform(0.8, 2.0),
                "brightness": random.uniform(100, 200),
                "twinkle_speed": random.uniform(0.5, 2.0),
                "twinkle_offset": random.uniform(0, 2 * math.pi),
                "drift_x": random.uniform(-0.05, 0.05),
                "drift_y": random.uniform(-0.05, 0.05),
            })

        # 用于 twinkle 动画的累计时间
        self._time: float = 0.0

        # 背景表面缓存
        self._surface: Optional[pygame.Surface] = None

    def update(self, dt: float) -> None:
        """更新星星位置（飘动）。

        Args:
            dt: 时间增量（秒）
        """
        self._time += dt

        for star in self.far_stars:
            star["x"] += star["drift_x"] * dt * 60
            star["y"] += star["drift_y"] * dt * 60
            # 循环
            if star["x"] < 0:
                star["x"] += self.width
            if star["x"] > self.width:
                star["x"] -= self.width
            if star["y"] < 0:
                star["y"] += self.height
            if star["y"] > self.height:
                star["y"] -= self.height

        for star in self.near_stars:
            star["x"] += star["drift_x"] * dt * 60
            star["y"] += star["drift_y"] * dt * 60
            if star["x"] < 0:
                star["x"] += self.width
            if star["x"] > self.width:
                star["x"] -= self.width
            if star["y"] < 0:
                star["y"] += self.height
            if star["y"] > self.height:
                star["y"] -= self.height

    def render(self, surface: pygame.Surface) -> None:
        """渲染背景星场。

        Args:
            surface: 目标 Pygame Surface
        """
        # 远景层
        for star in self.far_stars:
            b = int(star["brightness"])
            color = (b, b, b + 10)
            pygame.draw.circle(
                surface, color,
                (int(star["x"]), int(star["y"])),
                star["radius"],
            )

        # 近景层（闪烁）
        for star in self.near_stars:
            twinkle = 0.5 + 0.5 * math.sin(
                self._time * star["twinkle_speed"] + star["twinkle_offset"]
            )
            b = int(star["brightness"] * twinkle)
            b = max(0, min(255, b))
            color = (b, b, int(b * 1.2))
            pygame.draw.circle(
                surface, color,
                (int(star["x"]), int(star["y"])),
                star["radius"],
            )


# ============================================================================
# 尾迹绘制
# ============================================================================


def draw_trails(
    surface: pygame.Surface,
    trails: Dict[int, List[Tuple[float, float]]],
    body_speeds: Dict[int, float],
    camera: "ICamera",  # type: ignore
    fade_factors: Optional[Dict[int, float]] = None,
) -> None:
    """绘制所有天体的尾迹。

    每条尾迹使用线段绘制，颜色从旧到新渐变（透明度 + 色调）。
    速度快的天体尾迹偏暖色，速度慢的偏冷色。
    支持淡出系数：已消失天体的尾迹透明度乘上 fade_factor 逐渐消失。

    Args:
        surface: 目标 Pygame Surface
        trails: 尾迹数据 {body_id: [(x1,y1), (x2,y2), ...]}（从旧到新）
        body_speeds: 天体当前速度 {body_id: speed_magnitude}
        camera: 相机对象
        fade_factors: 淡出系数 {body_id: fade_factor (0~1)}，默认 None（全部 1.0）
    """
    # 获取速度范围用于颜色归一化
    if body_speeds:
        max_speed = max(body_speeds.values()) if body_speeds else 1.0
    else:
        max_speed = 1.0
    max_speed = max(max_speed, 1.0)  # 避免除零

    for body_id, trail_points in trails.items():
        if len(trail_points) < 2:
            continue

        speed = body_speeds.get(body_id, 0.0)
        speed_ratio = min(speed / max_speed, 1.0)

        # 根据速度确定基础色调
        r_slow, g_slow, b_slow = TRAIL_COLOR_SLOW
        r_fast, g_fast, b_fast = TRAIL_COLOR_FAST
        base_r = int(r_slow + (r_fast - r_slow) * speed_ratio)
        base_g = int(g_slow + (g_fast - g_slow) * speed_ratio)
        base_b = int(b_slow + (b_fast - b_slow) * speed_ratio)

        # 获取该天体的淡出系数
        body_fade = 1.0
        if fade_factors is not None and body_id in fade_factors:
            body_fade = fade_factors[body_id]

        n_points = len(trail_points)

        # 从旧到新逐段绘制
        for i in range(n_points - 1):
            x1, y1 = trail_points[i]
            x2, y2 = trail_points[i + 1]

            # 转换到屏幕坐标
            sx1, sy1 = camera.world_to_screen(x1, y1)
            sx2, sy2 = camera.world_to_screen(x2, y2)

            # 计算该段的透明度（从旧到新渐变，再乘淡出系数）
            t = i / (n_points - 1)  # 0 = 最旧, 1 = 最新
            alpha = int((TRAIL_ALPHA_OLD + (TRAIL_ALPHA_NEW - TRAIL_ALPHA_OLD) * t) * body_fade)
            alpha = max(0, min(255, alpha))

            # 宽度渐变（旧段细，新段粗）
            width = max(1.0, t * 2.5)

            # 颜色随渐变微调
            r = int(base_r * (0.5 + 0.5 * t))
            g = int(base_g * (0.5 + 0.5 * t))
            b = int(base_b * (0.5 + 0.5 * t))

            color = (r, g, b, alpha)
            _draw_alpha_line(surface, color, (sx1, sy1), (sx2, sy2), width)


def _draw_alpha_line(
    surface: pygame.Surface,
    color: Tuple[int, int, int, int],
    start: Tuple[int, int],
    end: Tuple[int, int],
    width: float = 1.0,
) -> None:
    """绘制带透明度的线段。

    Pygame 的 draw.line 不支持每条线独立 alpha，使用临时 surface 实现。

    Args:
        surface: 目标 Surface
        color: (R, G, B, A) 颜色
        start: 起点 (x, y)
        end: 终点 (x, y)
        width: 线宽
    """
    r, g, b, a = color
    if a <= 0:
        return

    # 创建临时 surface 用于 alpha 绘制
    line_surf = pygame.Surface((abs(end[0] - start[0]) + 3, abs(end[1] - start[1]) + 3), pygame.SRCALPHA)
    line_surf.fill((0, 0, 0, 0))

    # 在临时 surface 上绘制（相对坐标）
    ox, oy = min(start[0], end[0]) - 1, min(start[1], end[1]) - 1
    local_start = (start[0] - ox, start[1] - oy)
    local_end = (end[0] - ox, end[1] - oy)

    pygame.draw.line(line_surf, (r, g, b, a), local_start, local_end, max(1, int(width)))
    surface.blit(line_surf, (ox, oy))


# ============================================================================
# 预测轨道绘制
# ============================================================================


def draw_predicted_trajectory(
    surface: pygame.Surface,
    trajectory: np.ndarray,
    camera: "ICamera",  # type: ignore
) -> None:
    """绘制预测轨道（虚线/半透明）。

    Args:
        surface: 目标 Pygame Surface
        trajectory: shape (M, 2) 的预测轨迹坐标数组
        camera: 相机对象
    """
    if trajectory.shape[0] < 2:
        return

    points_screen: List[Tuple[int, int]] = []
    for i in range(trajectory.shape[0]):
        sx, sy = camera.world_to_screen(
            float(trajectory[i, 0]), float(trajectory[i, 1])
        )
        points_screen.append((sx, sy))

    # 虚线段：绘制时每隔一段画一个线段
    dash_length = 6
    gap_length = 4
    total_segments = len(points_screen) - 1

    for i in range(total_segments):
        # 奇偶段交替显示/隐藏
        if (i // 3) % 2 == 0:
            alpha = 120 - int(80 * (i / total_segments))
            alpha = max(30, alpha)
            color = (100, 200, 255, alpha)
            _draw_alpha_line(
                surface, color,
                points_screen[i], points_screen[i + 1],
                1.5,
            )

    # 终点标记（小圆圈）
    if len(points_screen) > 0:
        last = points_screen[-1]
        pygame.draw.circle(surface, (100, 200, 255, 100), last, 3, 1)


# ============================================================================
# 碰撞粒子特效
# ============================================================================


class Particle:
    """单个粒子，用于碰撞特效、发射特效等。"""

    def __init__(
        self,
        x: float,
        y: float,
        vx: float,
        vy: float,
        color: Tuple[int, int, int],
        lifetime: float = 1.0,
        radius: float = 2.0,
    ) -> None:
        """初始化粒子。

        Args:
            x, y: 初始位置（像素）
            vx, vy: 初始速度（像素/秒）
            color: RGB 颜色
            lifetime: 存活时间（秒）
            radius: 粒子半径（像素）
        """
        self.x: float = x
        self.y: float = y
        self.vx: float = vx
        self.vy: float = vy
        self.color: Tuple[int, int, int] = color
        self.lifetime: float = lifetime
        self.max_lifetime: float = lifetime
        self.radius: float = radius
        self.alive: bool = True

    def update(self, dt: float) -> None:
        """更新粒子状态。

        Args:
            dt: 时间增量（秒）
        """
        self.lifetime -= dt
        if self.lifetime <= 0:
            self.alive = False
            return

        # 简单运动（无重力）
        self.x += self.vx * dt
        self.y += self.vy * dt

        # 阻力减速
        self.vx *= 0.98
        self.vy *= 0.98

    def render(self, surface: pygame.Surface) -> None:
        """渲染粒子。

        Args:
            surface: 目标 Surface
        """
        if not self.alive:
            return

        alpha = int(255 * (self.lifetime / self.max_lifetime))
        alpha = max(0, min(255, alpha))
        r, g, b = self.color
        # 变暗
        fade = self.lifetime / self.max_lifetime
        cr = int(r * fade)
        cg = int(g * fade)
        cb = int(b * fade)

        # 使用临时 surface 支持透明度
        size = int(self.radius * 2) + 2
        particle_surf = pygame.Surface((size, size), pygame.SRCALPHA)
        particle_surf.fill((0, 0, 0, 0))
        pygame.draw.circle(
            particle_surf, (cr, cg, cb, alpha),
            (size // 2, size // 2), self.radius,
        )
        surface.blit(particle_surf, (self.x - size // 2, self.y - size // 2))


class ParticleSystem:
    """粒子系统管理器，管理一组粒子的生命周期。"""

    def __init__(self) -> None:
        """初始化粒子系统。"""
        self.particles: List[Particle] = []
        self._next_id: int = 0

    def emit_explosion(
        self,
        x: float,
        y: float,
        color: Tuple[int, int, int],
        count: int = 20,
        speed: float = 200.0,
    ) -> None:
        """在指定位置发射爆炸粒子。

        Args:
            x, y: 爆炸中心（像素）
            color: 主颜色
            count: 粒子数量
            speed: 粒子初始速度（像素/秒）
        """
        for _ in range(count):
            angle = random.uniform(0, 2 * math.pi)
            spd = random.uniform(speed * 0.3, speed)
            lifetime = random.uniform(0.3, 1.0)
            radius = random.uniform(1.0, 3.0)
            # 颜色微调
            r_offset = random.randint(-30, 30)
            g_offset = random.randint(-30, 30)
            b_offset = random.randint(-30, 30)
            particle_color = (
                max(0, min(255, color[0] + r_offset)),
                max(0, min(255, color[1] + g_offset)),
                max(0, min(255, color[2] + b_offset)),
            )
            self.particles.append(Particle(
                x=x, y=y,
                vx=math.cos(angle) * spd,
                vy=math.sin(angle) * spd,
                color=particle_color,
                lifetime=lifetime,
                radius=radius,
            ))

    def emit_probe_exhaust(
        self,
        x: float,
        y: float,
        angle: float,
        count: int = 3,
    ) -> None:
        """在探测器尾部发射尾焰粒子。

        Args:
            x, y: 发射位置（像素）
            angle: 发射方向（弧度），尾部方向相反
            count: 每帧粒子数量
        """
        for _ in range(count):
            # 尾部方向
            spread = random.uniform(-0.3, 0.3)
            dir_angle = angle + math.pi + spread
            spd = random.uniform(50, 150)
            lifetime = random.uniform(0.1, 0.4)
            radius = random.uniform(1.0, 2.5)
            # 橙色火焰
            r = random.randint(200, 255)
            g = random.randint(100, 200)
            b = random.randint(0, 50)
            self.particles.append(Particle(
                x=x, y=y,
                vx=math.cos(dir_angle) * spd,
                vy=math.sin(dir_angle) * spd,
                color=(r, g, b),
                lifetime=lifetime,
                radius=radius,
            ))

    def update(self, dt: float) -> None:
        """更新所有粒子。

        Args:
            dt: 时间增量（秒）
        """
        for p in self.particles:
            p.update(dt)
        # 移除死亡粒子
        self.particles = [p for p in self.particles if p.alive]

    def render(self, surface: pygame.Surface) -> None:
        """渲染所有粒子。

        Args:
            surface: 目标 Surface
        """
        for p in self.particles:
            p.render(surface)

    def clear(self) -> None:
        """清除所有粒子。"""
        self.particles.clear()


# ============================================================================
# 目标区域脉冲动画
# ============================================================================


def draw_target_zone(
    surface: pygame.Surface,
    world_x: float,
    world_y: float,
    radius: float,
    camera: "ICamera",  # type: ignore
    time: float = 0.0,
) -> None:
    """渲染目标区域（脉冲动画）。

    绘制一个不断脉动的光环，表示探测器需要到达的目标区域。

    Args:
        surface: 目标 Surface
        world_x, world_y: 目标中心世界坐标
        radius: 目标区域半径（世界单位）
        camera: 相机对象
        time: 累计时间（秒），用于脉冲动画
    """
    sx, sy = camera.world_to_screen(world_x, world_y)
    screen_radius = camera.world_distance_to_screen(radius)

    # 三个脉冲环
    for i in range(3):
        phase = time * 1.5 + i * 2.094  # 2pi/3 相位差
        pulse = 0.3 + 0.3 * math.sin(phase)
        r = screen_radius * (1.0 + pulse * 0.5)
        alpha = int(80 + 60 * (0.5 + 0.5 * math.sin(phase)))
        alpha = max(20, min(200, alpha))

        # 颜色：绿色脉冲
        color = (0, 200 + int(55 * (0.5 + 0.5 * math.sin(phase))), 100, alpha)

        # 绘制圆环（使用临时 surface）
        ring_size = int(r * 2) + 10
        ring_surf = pygame.Surface((ring_size, ring_size), pygame.SRCALPHA)
        ring_surf.fill((0, 0, 0, 0))
        pygame.draw.circle(
            ring_surf, color,
            (ring_size // 2, ring_size // 2),
            r, max(1, int(2 + pulse * 2)),
        )
        surface.blit(ring_surf, (sx - ring_size // 2, sy - ring_size // 2))
