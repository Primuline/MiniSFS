"""HUD 与 UI 系统：信息面板、时间控制、工具栏、选中信息。

所有 UI 元素绘制在渲染器之上，使用 Pygame 的 Surface 和 Font 实现。
"""

import math
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
    WINDOW_HEIGHT,
    WINDOW_WIDTH,
)
from src.core.types import (
    BODY_TYPE,
    CHARGE,
    IS_ACTIVE,
    MASS,
    RADIUS,
    VX,
    VY,
    X,
    Y,
)

# ============================================================================
# 面板配置
# ============================================================================

PANEL_BG = (20, 20, 40, 200)
PANEL_BORDER = (60, 60, 100)
TEXT_COLOR = (200, 200, 220)
TEXT_HIGHLIGHT = (255, 255, 255)
LABEL_COLOR = (150, 150, 180)
BTN_NORMAL = (50, 50, 80)
BTN_HOVER = (70, 70, 110)
BTN_ACTIVE = (100, 120, 200)
BTN_DISABLED = (30, 30, 50)

INFO_PANEL_WIDTH = 220
TOOLBAR_WIDTH = 44
CONTROL_BAR_HEIGHT = 36


class Button:
    """简单的 UI 按钮。"""

    def __init__(
        self,
        x: int,
        y: int,
        width: int,
        height: int,
        text: str,
        action: str = "",
        color: Tuple[int, int, int] = BTN_NORMAL,
        hover_color: Tuple[int, int, int] = BTN_HOVER,
        font_size: int = 16,
    ) -> None:
        """初始化按钮。

        Args:
            x, y: 左上角坐标
            width, height: 尺寸
            text: 按钮文字
            action: 按钮触发的动作标识
            color: 正常颜色
            hover_color: 悬停颜色
            font_size: 字体大小
        """
        self.rect = pygame.Rect(x, y, width, height)
        self.text = text
        self.action = action
        self.color = color
        self.hover_color = hover_color
        self.font = pygame.font.Font(None, font_size)
        self.hovered = False
        self.active = False
        self.disabled = False
        self.visible = True

    def draw(self, surface: pygame.Surface) -> None:
        """绘制按钮。

        Args:
            surface: 目标 Surface
        """
        if not self.visible:
            return

        color = self.color
        if self.disabled:
            color = BTN_DISABLED
        elif self.active:
            color = BTN_ACTIVE
        elif self.hovered:
            color = self.hover_color

        # 背景
        pygame.draw.rect(surface, color, self.rect, border_radius=4)
        pygame.draw.rect(surface, PANEL_BORDER, self.rect, 1, border_radius=4)

        # 文字
        text_color = TEXT_HIGHLIGHT if (self.active or self.hovered) else TEXT_COLOR
        if self.disabled:
            text_color = (80, 80, 80)
        text_surf = self.font.render(self.text, True, text_color)
        tr = text_surf.get_rect(center=self.rect.center)
        surface.blit(text_surf, tr)

    def handle_event(self, event: pygame.event.Event) -> Optional[str]:
        """处理事件，返回点击动作。

        Args:
            event: Pygame 事件

        Returns:
            点击时返回 action 字符串，否则返回 None
        """
        if not self.visible or self.disabled:
            return None

        if event.type == pygame.MOUSEMOTION:
            self.hovered = self.rect.collidepoint(event.pos)
            return None

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect.collidepoint(event.pos):
                return self.action

        return None

    def set_pos(self, x: int, y: int) -> None:
        """设置按钮位置。

        Args:
            x, y: 新的左上角坐标
        """
        self.rect.x = x
        self.rect.y = y


class HUDManager:
    """HUD 管理器，管理所有 UI 元素。

    维护信息面板、时间控制、工具栏等 UI 组件的状态和绘制。
    """

    def __init__(self) -> None:
        """初始化 HUD 管理器。"""
        self.width: int = WINDOW_WIDTH
        self.height: int = WINDOW_HEIGHT

        # 字体
        self._font_title = pygame.font.Font(None, 20)
        self._font_label = pygame.font.Font(None, 16)
        self._font_value = pygame.font.Font(None, 16)
        self._font_small = pygame.font.Font(None, 14)

        # ============ 工具栏 ============
        tool_y = 100
        tool_spacing = 46
        self.tool_buttons: List[Button] = []
        tools = [
            ("S", "TOOL_STAR", "Star"),
            ("P", "TOOL_PLANET", "Planet"),
            ("D", "TOOL_PROBE", "Probe"),
            ("+/-", "TOOL_CHARGED", "Charged"),
        ]
        for i, (label, action, _) in enumerate(tools):
            btn = Button(
                5, tool_y + i * tool_spacing,
                34, 34, label, action,
                font_size=14,
            )
            self.tool_buttons.append(btn)

        self.active_tool: Optional[str] = None

        # ============ 时间控制 ============
        ctrl_y = self.height - CONTROL_BAR_HEIGHT - 5
        ctrl_x = self.width // 2 - 80
        self.time_buttons: List[Button] = []
        time_actions = [
            ("|<", "REWIND"),
            (">", "PLAY_PAUSE"),
            (">>", "FAST_2X"),
            (">>>", "FAST_4X"),
        ]
        for i, (label, action) in enumerate(time_actions):
            btn = Button(
                ctrl_x + i * 45, ctrl_y,
                40, CONTROL_BAR_HEIGHT - 4,
                label, action,
                font_size=14,
            )
            self.time_buttons.append(btn)

        # 时间速度标签
        self.time_speed: float = 1.0
        self.is_paused: bool = False

        # ============ 信息面板 ============
        self.info_panel_visible: bool = False
        self._info_body_data: Optional[Dict[str, float]] = None
        self._info_body_type: int = -1

        # 选中天体信息
        self.selected_body_info: Optional[str] = None

    # ------------------------------------------------------------------
    # 更新方法
    # ------------------------------------------------------------------

    def set_selected_body(
        self, body_data: Optional[np.ndarray], body_id: int
    ) -> None:
        """更新选中天体的信息。

        Args:
            body_data: 天体的状态行 (shape (NUM_FIELDS,))
            body_id: 天体的 ID
        """
        if body_data is None:
            self.info_panel_visible = False
            self._info_body_data = None
            self.selected_body_info = None
            return

        self.info_panel_visible = True
        self._info_body_data = {
            "id": float(body_id),
            "x": float(body_data[X]),
            "y": float(body_data[Y]),
            "vx": float(body_data[VX]),
            "vy": float(body_data[VY]),
            "mass": float(body_data[MASS]),
            "radius": float(body_data[RADIUS]),
            "body_type": float(body_data[BODY_TYPE]),
            "charge": float(body_data[CHARGE]),
            "static": float(body_data[8]),  # IS_STATIC
        }
        self._info_body_type = int(body_data[BODY_TYPE])

        # 生成简要描述
        type_names = {0: "Star", 1: "Planet", 2: "Probe", 3: "Charged"}
        type_name = type_names.get(self._info_body_type, "Unknown")
        speed = math.sqrt(
            float(body_data[VX]) ** 2 + float(body_data[VY]) ** 2
        )
        self.selected_body_info = (
            f"{type_name} #{body_id}  "
            f"速度: {speed:.2e} m/s"
        )

    def get_tool_display_name(self, tool: str) -> str:
        """获取工具对应的天体类型名称。

        Args:
            tool: 工具标识

        Returns:
            显示名称
        """
        names = {
            "TOOL_STAR": "Star",
            "TOOL_PLANET": "Planet",
            "TOOL_PROBE": "Probe",
            "TOOL_CHARGED": "Charged",
        }
        return names.get(tool, tool)

    def get_tool_body_type(self, tool: str) -> int:
        """获取工具对应的天体类型值。

        Args:
            tool: 工具标识

        Returns:
            BODY_TYPE_* 常量
        """
        mapping = {
            "TOOL_STAR": BODY_TYPE_STAR,
            "TOOL_PLANET": BODY_TYPE_PLANET,
            "TOOL_PROBE": BODY_TYPE_PROBE,
            "TOOL_CHARGED": BODY_TYPE_CHARGED,
        }
        return mapping.get(tool, BODY_TYPE_PLANET)

    def get_default_body_params(self, tool: str) -> Tuple[float, float, float, float]:
        """获取工具的默认天体参数。

        Args:
            tool: 工具标识

        Returns:
            (mass, radius, charge, body_type) 元组
        """
        mapping = {
            "TOOL_STAR": (DEFAULT_MASS_STAR, DEFAULT_RADIUS_STAR, 0.0, float(BODY_TYPE_STAR)),
            "TOOL_PLANET": (DEFAULT_MASS_PLANET, DEFAULT_RADIUS_PLANET, 0.0, float(BODY_TYPE_PLANET)),
            "TOOL_PROBE": (DEFAULT_MASS_PROBE, DEFAULT_RADIUS_PROBE, 0.0, float(BODY_TYPE_PROBE)),
            "TOOL_CHARGED": (DEFAULT_MASS_CHARGED, DEFAULT_RADIUS_CHARGED, DEFAULT_CHARGE_CHARGED, float(BODY_TYPE_CHARGED)),
        }
        return mapping.get(tool, (DEFAULT_MASS_PLANET, DEFAULT_RADIUS_PLANET, 0.0, float(BODY_TYPE_PLANET)))

    # ------------------------------------------------------------------
    # 事件处理
    # ------------------------------------------------------------------

    def handle_event(self, event: pygame.event.Event) -> Optional[str]:
        """处理 HUD 事件。

        Args:
            event: Pygame 事件

        Returns:
            动作字符串（如 "TOOL_STAR", "PLAY_PAUSE"）
        """
        # 工具栏事件
        for btn in self.tool_buttons:
            action = btn.handle_event(event)
            if action:
                return action

        # 时间控制事件
        for btn in self.time_buttons:
            action = btn.handle_event(event)
            if action:
                return action

        return None

    def set_tool_active(self, tool: Optional[str]) -> None:
        """设置当前激活的工具。

        Args:
            tool: 工具标识
        """
        self.active_tool = tool
        for btn in self.tool_buttons:
            btn.active = (btn.action == tool)

    def set_play_pause_state(self, is_paused: bool) -> None:
        """设置播放/暂停状态。

        Args:
            is_paused: 是否暂停
        """
        self.is_paused = is_paused
        if len(self.time_buttons) >= 2:
            self.time_buttons[1].text = ">" if is_paused else "||"

    def set_time_speed(self, speed: float) -> None:
        """设置时间速度。

        Args:
            speed: 时间速度倍率
        """
        self.time_speed = speed
        for i, btn in enumerate(self.time_buttons):
            if i >= 2:  # 快进按钮
                btn.active = False
        if speed >= 4.0:
            self.time_buttons[3].active = True
        elif speed >= 2.0:
            self.time_buttons[2].active = True

    # ------------------------------------------------------------------
    # 绘制
    # ------------------------------------------------------------------

    def draw(self, surface: pygame.Surface) -> None:
        """绘制所有 HUD 元素。

        Args:
            surface: 目标 Surface
        """
        self._draw_info_panel(surface)
        self._draw_toolbar(surface)
        self._draw_time_controls(surface)
        self._draw_active_tool_indicator(surface)
        self._draw_selected_info_bar(surface)

    def _draw_info_panel(self, surface: pygame.Surface) -> None:
        """绘制信息面板。

        Args:
            surface: 目标 Surface
        """
        if not self.info_panel_visible or self._info_body_data is None:
            return

        panel_x = self.width - INFO_PANEL_WIDTH - 10
        panel_y = 10
        panel_w = INFO_PANEL_WIDTH
        panel_h = 200

        # 背景
        panel_surf = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
        panel_surf.fill(PANEL_BG)
        surface.blit(panel_surf, (panel_x, panel_y))
        pygame.draw.rect(
            surface, PANEL_BORDER,
            (panel_x, panel_y, panel_w, panel_h), 1, border_radius=4,
        )

        # 标题
        type_names = {0: "Star", 1: "Planet", 2: "Probe", 3: "Charged"}
        type_name = type_names.get(self._info_body_type, "Unknown")
        title = f"{type_name} #{int(self._info_body_data['id'])}"
        title_surf = self._font_title.render(title, True, TEXT_HIGHLIGHT)
        surface.blit(title_surf, (panel_x + 10, panel_y + 8))

        # 信息行
        data = self._info_body_data
        lines = [
            ("Pos", f"({data['x']:.2e}, {data['y']:.2e})"),
            ("Vel", f"({data['vx']:.2e}, {data['vy']:.2e}) m/s"),
            ("Mass", f"{data['mass']:.3e} kg"),
            ("Radius", f"{data['radius']:.2e} m"),
        ]
        if self._info_body_type == BODY_TYPE_CHARGED:
            lines.append(("Charge", f"{data['charge']:.2e} C"))

        speed = math.sqrt(data['vx']**2 + data['vy']**2)
        lines.append(("Speed", f"{speed:.2e} m/s"))

        if data.get('static', 0) == 1.0:
            lines.append(("Fixed", "Static"))

        for i, (label, value) in enumerate(lines):
            y = panel_y + 32 + i * 20
            label_surf = self._font_label.render(label + ":", True, LABEL_COLOR)
            surface.blit(label_surf, (panel_x + 10, y))
            value_surf = self._font_value.render(value, True, TEXT_COLOR)
            surface.blit(value_surf, (panel_x + 80, y))

    def _draw_toolbar(self, surface: pygame.Surface) -> None:
        """绘制工具栏。

        Args:
            surface: 目标 Surface
        """
        # 工具栏背景
        tool_bg = pygame.Surface((TOOLBAR_WIDTH, self.height), pygame.SRCALPHA)
        tool_bg.fill((15, 15, 35, 180))
        surface.blit(tool_bg, (0, 0))

        # 工具标题
        title_surf = self._font_title.render("Tools", True, LABEL_COLOR)
        surface.blit(title_surf, (6, 70))

        # 工具按钮
        for btn in self.tool_buttons:
            btn.draw(surface)

        # 当前工具提示
        if self.active_tool:
            hint = self.get_tool_display_name(self.active_tool)
            hint_surf = self._font_small.render(hint, True, TEXT_HIGHLIGHT)
            surface.blit(hint_surf, (5, 55))

    def _draw_time_controls(self, surface: pygame.Surface) -> None:
        """绘制时间控制按钮。

        Args:
            surface: 目标 Surface
        """
        bar_y = self.height - CONTROL_BAR_HEIGHT - 5
        bar_w = 200
        bar_x = self.width // 2 - bar_w // 2

        # 背景
        bar_bg = pygame.Surface((bar_w, CONTROL_BAR_HEIGHT), pygame.SRCALPHA)
        bar_bg.fill((15, 15, 35, 200))
        surface.blit(bar_bg, (bar_x, bar_y))
        pygame.draw.rect(
            surface, PANEL_BORDER,
            (bar_x, bar_y, bar_w, CONTROL_BAR_HEIGHT), 1, border_radius=4,
        )

        # 按钮
        for btn in self.time_buttons:
            btn.draw(surface)

        # 速度指示
        speed_text = f"{self.time_speed:.0f}x"
        if self.is_paused:
            speed_text = "PAUSED"
        speed_surf = self._font_small.render(speed_text, True, TEXT_COLOR)
        sr = speed_surf.get_rect(
            midtop=(self.width // 2, bar_y - 16)
        )
        surface.blit(speed_surf, sr)

    def _draw_active_tool_indicator(self, surface: pygame.Surface) -> None:
        """绘制当前激活工具的提示指示。

        Args:
            surface: 目标 Surface
        """
        if self.active_tool:
            tool_name = self.get_tool_display_name(self.active_tool)
            text = f"Active: {tool_name}  (right-click to cancel)"
            text_surf = self._font_small.render(text, True, (180, 180, 200))
            surface.blit(text_surf, (50, 5))

    def _draw_selected_info_bar(self, surface: pygame.Surface) -> None:
        """绘制选中天体信息条（顶部居中）。

        Args:
            surface: 目标 Surface
        """
        if self.selected_body_info:
            text_surf = self._font_label.render(
                self.selected_body_info, True, TEXT_HIGHLIGHT
            )
            tr = text_surf.get_rect(midtop=(self.width // 2, 5))
            # 背景
            bg = pygame.Surface((tr.width + 16, tr.height + 6), pygame.SRCALPHA)
            bg.fill((0, 0, 0, 160))
            surface.blit(bg, (tr.x - 8, tr.y - 3))
            surface.blit(text_surf, tr)
