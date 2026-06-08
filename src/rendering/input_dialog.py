"""科学计数法输入弹窗模块。

提供 ScientificInputDialog 类，用于自定义粒子参数的
科学计数法手动输入（质量、电荷、速度各含系数和指数）。

提供 EditBodyDialog 类，用于编辑已存在天体的
质量与电荷参数（无速度输入）。
"""

import math
from typing import Dict, List, Optional, Tuple, Union

import pygame

from src.config import WINDOW_HEIGHT, WINDOW_WIDTH

# ============================================================================
# 颜色常量
# ============================================================================

DIALOG_BG = (20, 20, 40, 220)
DIALOG_BORDER = (60, 60, 100)
TEXT_COLOR = (200, 200, 220)
TEXT_HIGHLIGHT = (255, 255, 255)
LABEL_COLOR = (150, 150, 180)
PLACEHOLDER_COLOR = (100, 100, 120)
FIELD_INACTIVE = (50, 50, 80)
FIELD_ACTIVE = (60, 60, 100)
FIELD_BORDER_INACTIVE = (80, 80, 110)
FIELD_BORDER_ACTIVE = (200, 200, 255)
CURSOR_COLOR = (200, 200, 255)
BTN_OK_COLOR = (40, 80, 40)
BTN_OK_HOVER = (60, 140, 60)
BTN_CANCEL_COLOR = (80, 40, 40)
BTN_CANCEL_HOVER = (140, 60, 60)
BTN_TEXT_COLOR = (220, 220, 220)
HINT_COLOR = (120, 120, 140)

# ============================================================================
# 输入框定义辅助
# ============================================================================

# 每个输入框: (标签, 占位符, 允许小数点, 允许负号)
# 索引: 0=mass_coeff, 1=mass_exp, 2=charge_coeff, 3=charge_exp,
#       4=radius_coeff, 5=radius_exp
FIELD_DEFS: List[Tuple[str, str, bool, bool]] = [
    ("Mass coeff",    "1.0", True,  True),
    ("Mass exp",      "26",  False, True),
    ("Charge coeff",  "0.0", True,  True),
    ("Charge exp",    "0",   False, True),
    ("Radius coeff",  "6.4", True,  False),
    ("Radius exp",    "3",   False, False),
]

# 行标签
ROW_LABELS: List[str] = ["Mass", "Charge", "Radius"]
ROW_UNITS: List[str] = ["kg", "C", "km"]

# 编辑弹窗字段定义（2 行：Mass, Charge，无 Speed）
EDIT_FIELD_DEFS: List[Tuple[str, str, bool, bool]] = [
    ("Mass coeff",  "1.0", True,  True),
    ("Mass exp",    "0",   False, True),
    ("Charge coeff","0.0", True,  True),
    ("Charge exp",  "0",   False, True),
    ("Radius coeff","6.4", True,  False),
    ("Radius exp",  "3",   False, False),
]

EDIT_ROW_LABELS: List[str] = ["Mass", "Charge", "Radius"]
EDIT_ROW_UNITS: List[str] = ["kg", "C", "km"]


# ============================================================================
# 工具函数
# ============================================================================


def _float_to_components(value: float) -> Tuple[str, str]:
    """将浮点数拆分为系数和指数文本。

    Args:
        value: 浮点数

    Returns:
        (系数文本, 指数文本) 元组
    """
    if value == 0.0:
        return ("0", "0")
    exp = int(math.floor(math.log10(abs(value))))
    coeff = value / (10 ** exp)
    coeff = round(coeff, 6)
    coeff_str = str(coeff)
    return (coeff_str, str(exp))


# ============================================================================
# 编辑弹窗 — EditBodyDialog
# ============================================================================


class EditBodyDialog:
    """编辑天体参数弹窗。

    3 行（Mass, Charge, Radius），前两行每行系数+指数两个输入框，
    最后一行（Radius）只有一个系数输入框，共 5 个输入框。
    支持键盘输入（数字、小数点、负号、Backspace、Enter）。
    激活的输入框显示白色边框 + 闪烁光标。
    提供 OK / Cancel 按钮。

    handle_event 返回:
        - {"mass": float, "charge": float, "radius": float}  — 确认
        - "CANCEL"                                             — 取消
        - None                                                 — 事件已消费，无动作
    """

    # 布局常量
    PANEL_WIDTH: int = 340
    PANEL_HEIGHT: int = 235
    FIELD_HEIGHT: int = 24
    COEFF_WIDTH: int = 80
    EXP_WIDTH: int = 45
    BUTTON_WIDTH: int = 72
    BUTTON_HEIGHT: int = 28
    ROW_SPACING: int = 35
    ROW_START_OFFSET: int = -30
    BLINK_INTERVAL_MS: int = 500

    def __init__(self) -> None:
        """初始化编辑弹窗。"""
        self.visible: bool = False
        self.active_field_index: int = -1  # -1 = 无激活
        self.cursor_visible: bool = True

        # 5 个输入字段数据
        self.fields: List[Dict] = []
        for idx, (_, placeholder, allow_decimal, allow_negative) in enumerate(EDIT_FIELD_DEFS):
            coeff_field = idx in (0, 2, 4)
            width = self.COEFF_WIDTH if coeff_field else self.EXP_WIDTH
            self.fields.append({
                "rect": pygame.Rect(0, 0, width, self.FIELD_HEIGHT),
                "text": placeholder,
                "placeholder": placeholder,
                "allow_decimal": allow_decimal,
                "allow_negative": allow_negative,
            })

        # OK / Cancel 按钮 rect
        self.ok_rect: pygame.Rect = pygame.Rect(0, 0, self.BUTTON_WIDTH, self.BUTTON_HEIGHT)
        self.cancel_rect: pygame.Rect = pygame.Rect(0, 0, self.BUTTON_WIDTH, self.BUTTON_HEIGHT)

        # 按钮悬停状态
        self.ok_hovered: bool = False
        self.cancel_hovered: bool = False

        # 字体
        self._font_title: pygame.font.Font = pygame.font.Font(None, 20)
        self._font_field: pygame.font.Font = pygame.font.Font(None, 18)
        self._font_label: pygame.font.Font = pygame.font.Font(None, 16)
        self._font_small: pygame.font.Font = pygame.font.Font(None, 14)

        # 计算布局
        self._compute_layout()

    # ------------------------------------------------------------------
    # 布局计算
    # ------------------------------------------------------------------

    def _compute_layout(self) -> None:
        """计算所有输入框和按钮的位置。"""
        cx = WINDOW_WIDTH // 2

        # 中心垂直偏移
        cy = WINDOW_HEIGHT // 2
        row_start_y = cy + self.ROW_START_OFFSET

        # 每行左侧：系数框位置
        coeff_x = cx - 55
        # 每行指数框位置
        exp_x = cx + 60

        for row in range(3):
            coeff_idx = row * 2
            exp_idx = row * 2 + 1
            row_y = row_start_y + row * self.ROW_SPACING

            # 系数框
            cf = self.fields[coeff_idx]
            cf["rect"].x = coeff_x
            cf["rect"].y = row_y
            cf["rect"].centery = row_y + self.FIELD_HEIGHT // 2

            # 指数框
            ef = self.fields[exp_idx]
            ef["rect"].x = exp_x
            ef["rect"].y = row_y
            ef["rect"].centery = row_y + self.FIELD_HEIGHT // 2

        # OK / Cancel 按钮位置
        btn_y = row_start_y + 3 * self.ROW_SPACING + 5
        self.ok_rect.x = cx - 80
        self.ok_rect.y = btn_y
        self.cancel_rect.x = cx + 8
        self.cancel_rect.y = btn_y

    # ------------------------------------------------------------------
    # 预填值
    # ------------------------------------------------------------------

    def prefill(self, mass: float, charge: float, radius_meters: float = 7.0e8) -> None:
        """预填质量和电荷的当前值，以及半径（m → km）。

        Args:
            mass: 当前质量 (kg)
            charge: 当前电荷 (C)
            radius_meters: 当前半径 (m)，内部转为 km
        """
        mass_coeff, mass_exp = _float_to_components(mass)
        charge_coeff, charge_exp = _float_to_components(charge)

        self.fields[0]["text"] = mass_coeff
        self.fields[1]["text"] = mass_exp
        self.fields[2]["text"] = charge_coeff
        self.fields[3]["text"] = charge_exp
        # 半径：m → km 后拆分
        radius_km = radius_meters / 1000.0
        r_coeff, r_exp = _float_to_components(radius_km)
        self.fields[4]["text"] = r_coeff
        self.fields[5]["text"] = r_exp

    # ------------------------------------------------------------------
    # 字段值读取
    # ------------------------------------------------------------------

    def _get_field_value(
        self, coeff_idx: int, exp_idx: int
    ) -> float:
        """读取系数和指数并计算数值。

        Args:
            coeff_idx: 系数输入框索引
            exp_idx: 指数输入框索引

        Returns:
            计算后的数值
        """
        coeff_text = self.fields[coeff_idx]["text"]
        exp_text = self.fields[exp_idx]["text"]

        try:
            coeff = float(coeff_text) if coeff_text else 1.0
        except ValueError:
            coeff = 1.0

        try:
            exp = int(exp_text) if exp_text else 0
        except ValueError:
            exp = 0

        return coeff * (10 ** exp)

    def get_results(self) -> Dict[str, float]:
        """读取所有输入框并计算最终参数。

        Returns:
            {"mass": float (kg), "charge": float (C), "radius": float (m)}

        注意：半径从 km 转为 m（×1000）。
        解析失败时静默使用默认值（系数 1.0，指数 0）。
        """
        mass = self._get_field_value(0, 1)
        charge = self._get_field_value(2, 3)
        radius = self._get_field_value(4, 5) * 1000.0  # km -> m
        radius = max(1.0, min(radius, 1.0e12))
        return {"mass": mass, "charge": charge, "radius": radius}

    # ------------------------------------------------------------------
    # 输入校验
    # ------------------------------------------------------------------

    def _is_valid_input(self, char: str, field_idx: int) -> bool:
        """检查输入的字符是否合法。

        Args:
            char: 输入的字符
            field_idx: 输入框索引

        Returns:
            是否合法
        """
        field = self.fields[field_idx]
        allow_decimal = field["allow_decimal"]
        allow_negative = field["allow_negative"]

        if char in "0123456789":
            return True
        if char == "." and allow_decimal:
            return "." not in field["text"]
        if char == "-" and allow_negative:
            return field["text"] == ""
        return False

    # ------------------------------------------------------------------
    # 事件处理
    # ------------------------------------------------------------------

    def handle_event(
        self, event: pygame.event.Event
    ) -> Optional[Union[str, Dict[str, float]]]:
        """处理事件。

        Args:
            event: Pygame 事件

        Returns:
            - {"mass": float, "charge": float} — 确认
            - "CANCEL" — 取消
            - None — 事件已消费，无动作
        """
        if not self.visible:
            return None

        # 鼠标移动：更新按钮悬停状态
        if event.type == pygame.MOUSEMOTION:
            self.ok_hovered = self.ok_rect.collidepoint(event.pos)
            self.cancel_hovered = self.cancel_rect.collidepoint(event.pos)
            return None

        # 鼠标点击
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            # 检查输入框点击
            for i, field in enumerate(self.fields):
                if field["rect"].collidepoint(event.pos):
                    self.active_field_index = i
                    self.cursor_visible = True
                    return None

            # 检查 OK 按钮
            if self.ok_rect.collidepoint(event.pos):
                return self.get_results()

            # 检查 Cancel 按钮
            if self.cancel_rect.collidepoint(event.pos):
                return "CANCEL"

            # 点击弹窗外区域忽略
            return None

        # 键盘输入
        if event.type == pygame.KEYDOWN:
            # Esc = Cancel
            if event.key == pygame.K_ESCAPE:
                return "CANCEL"

            # Enter = OK
            if event.key == pygame.K_RETURN:
                return self.get_results()

            if self.active_field_index < 0:
                return None

            field = self.fields[self.active_field_index]

            # Backspace
            if event.key == pygame.K_BACKSPACE:
                field["text"] = field["text"][:-1]
                return None

            # 获取按键字符
            if event.key == pygame.K_KP_MINUS:
                char = "-"
            elif event.key == pygame.K_KP_PERIOD:
                char = "."
            else:
                try:
                    char = event.unicode
                except Exception:
                    return None

            # 检查合法性并附加
            if char and self._is_valid_input(char, self.active_field_index):
                field["text"] += char

            return None

        return None

    # ------------------------------------------------------------------
    # 绘制
    # ------------------------------------------------------------------

    def draw(self, surface: pygame.Surface) -> None:
        """绘制弹窗。

        Args:
            surface: 目标 Surface
        """
        if not self.visible:
            return

        cx = WINDOW_WIDTH // 2
        cy = WINDOW_HEIGHT // 2
        pw = self.PANEL_WIDTH
        ph = self.PANEL_HEIGHT
        px = cx - pw // 2
        py = cy - ph // 2

        # 半透明背景遮罩
        mask = pygame.Surface((WINDOW_WIDTH, WINDOW_HEIGHT), pygame.SRCALPHA)
        mask.fill((0, 0, 0, 120))
        surface.blit(mask, (0, 0))

        # 面板背景
        panel_surf = pygame.Surface((pw, ph), pygame.SRCALPHA)
        panel_surf.fill(DIALOG_BG)
        surface.blit(panel_surf, (px, py))
        pygame.draw.rect(surface, DIALOG_BORDER, (px, py, pw, ph), 2, border_radius=8)

        # 标题
        title = "Edit Body Parameters"
        title_surf = self._font_title.render(title, True, TEXT_HIGHLIGHT)
        tr = title_surf.get_rect(center=(cx, py + 18))
        surface.blit(title_surf, tr)

        # 光标闪烁
        now = pygame.time.get_ticks()
        self.cursor_visible = (now // self.BLINK_INTERVAL_MS) % 2 == 0

        row_start_y = cy + self.ROW_START_OFFSET
        label_x = px + 15

        for row in range(3):
            row_y = row_start_y + row * self.ROW_SPACING
            coeff_idx = row * 2
            exp_idx = row * 2 + 1

            # 行标签
            lbl_surf = self._font_label.render(EDIT_ROW_LABELS[row], True, LABEL_COLOR)
            surface.blit(lbl_surf, (label_x, row_y + 3))

            # 每行：系数 + *10^ + 指数 + 单位
            self._draw_field(surface, self.fields[coeff_idx], coeff_idx == self.active_field_index, row_y)

            # *10^ 标签
            power_surf = self._font_small.render("*10^", True, LABEL_COLOR)
            power_rect = power_surf.get_rect(
                midleft=(self.fields[coeff_idx]["rect"].right + 4, row_y + self.FIELD_HEIGHT // 2)
            )
            surface.blit(power_surf, power_rect)

            # 指数输入框
            self._draw_field(surface, self.fields[exp_idx], exp_idx == self.active_field_index, row_y)

            # 单位
            unit_surf = self._font_small.render(EDIT_ROW_UNITS[row], True, LABEL_COLOR)
            unit_rect = unit_surf.get_rect(
                midleft=(self.fields[exp_idx]["rect"].right + 4, row_y + self.FIELD_HEIGHT // 2)
            )
            surface.blit(unit_surf, unit_rect)

        # OK / Cancel 按钮
        self._draw_button(
            surface, self.ok_rect, "OK",
            BTN_OK_HOVER if self.ok_hovered else BTN_OK_COLOR,
        )
        self._draw_button(
            surface, self.cancel_rect, "Cancel",
            BTN_CANCEL_HOVER if self.cancel_hovered else BTN_CANCEL_COLOR,
        )

        # 底部提示
        hint = "Esc to cancel  |  Enter to confirm"
        hint_surf = self._font_small.render(hint, True, HINT_COLOR)
        hr = hint_surf.get_rect(center=(cx, py + ph - 10))
        surface.blit(hint_surf, hr)

    def _draw_field(
        self,
        surface: pygame.Surface,
        field: Dict,
        is_active: bool,
        row_y: int,
    ) -> None:
        """绘制单个输入框。

        Args:
            surface: 目标 Surface
            field: 输入框数据字典
            is_active: 是否激活
            row_y: 行垂直位置（用于光标定位）
        """
        rect = field["rect"]

        # 背景
        bg_color = FIELD_ACTIVE if is_active else FIELD_INACTIVE
        pygame.draw.rect(surface, bg_color, rect, border_radius=3)

        # 边框
        border_color = FIELD_BORDER_ACTIVE if is_active else FIELD_BORDER_INACTIVE
        pygame.draw.rect(surface, border_color, rect, 1, border_radius=3)

        # 文字或占位符
        if field["text"]:
            text_surf = self._font_field.render(field["text"], True, TEXT_HIGHLIGHT)
        else:
            text_surf = self._font_field.render(field["placeholder"], True, PLACEHOLDER_COLOR)

        text_rect = text_surf.get_rect(midleft=(rect.x + 4, rect.centery))
        surface.blit(text_surf, text_rect)

        # 光标闪烁（仅激活状态）
        if is_active and self.cursor_visible:
            cursor_x = text_rect.right + 1
            cursor_y1 = rect.y + 3
            cursor_y2 = rect.bottom - 3
            pygame.draw.line(surface, CURSOR_COLOR, (cursor_x, cursor_y1), (cursor_x, cursor_y2), 2)

    def _draw_button(
        self,
        surface: pygame.Surface,
        rect: pygame.Rect,
        text: str,
        color: Tuple[int, int, int],
    ) -> None:
        """绘制一个按钮。

        Args:
            surface: 目标 Surface
            rect: 按钮位置矩形
            text: 按钮文字
            color: 按钮颜色
        """
        # 背景
        pygame.draw.rect(surface, color, rect, border_radius=4)
        pygame.draw.rect(surface, DIALOG_BORDER, rect, 1, border_radius=4)

        # 文字
        text_surf = self._font_field.render(text, True, BTN_TEXT_COLOR)
        tr = text_surf.get_rect(center=rect.center)
        surface.blit(text_surf, tr)


# ============================================================================
# 自定义粒子输入弹窗 — ScientificInputDialog（保留原实现）
# ============================================================================


class ScientificInputDialog:
    """科学计数法输入弹窗。

    6 个输入框：质量系数/指数、电荷系数/指数、半径系数/指数。
    支持键盘输入（数字、小数点、负号、Backspace、Enter）。
    激活的输入框显示白色边框 + 闪烁光标。
    提供 OK / Cancel 按钮。

    handle_event 返回:
        - {"mass": float, "charge": float, "radius": float}  — 确认
        - "CANCEL"                                                            — 取消
        - None                                                                — 事件已消费，无动作
    """

    # 布局常量
    PANEL_WIDTH: int = 340
    PANEL_HEIGHT: int = 275
    FIELD_HEIGHT: int = 24
    COEFF_WIDTH: int = 80
    EXP_WIDTH: int = 45
    BUTTON_WIDTH: int = 72
    BUTTON_HEIGHT: int = 28
    ROW_SPACING: int = 35
    ROW_START_OFFSET: int = -70
    BUTTON_Y_OFFSET: int = 115
    BLINK_INTERVAL_MS: int = 500

    def __init__(self) -> None:
        """初始化科学计数法输入弹窗。"""
        self.visible: bool = False
        self.active_field_index: int = -1  # -1 = 无激活
        self.cursor_visible: bool = True

        # 6 个输入字段数据
        self.fields: List[Dict] = []
        for idx, (_, placeholder, allow_decimal, allow_negative) in enumerate(FIELD_DEFS):
            coeff_field = idx in (0, 2, 4)
            width = self.COEFF_WIDTH if coeff_field else self.EXP_WIDTH
            self.fields.append({
                "rect": pygame.Rect(0, 0, width, self.FIELD_HEIGHT),
                "text": placeholder,
                "placeholder": placeholder,
                "allow_decimal": allow_decimal,
                "allow_negative": allow_negative,
            })

        # OK / Cancel 按钮 rect
        self.ok_rect: pygame.Rect = pygame.Rect(0, 0, self.BUTTON_WIDTH, self.BUTTON_HEIGHT)
        self.cancel_rect: pygame.Rect = pygame.Rect(0, 0, self.BUTTON_WIDTH, self.BUTTON_HEIGHT)

        # 按钮悬停状态
        self.ok_hovered: bool = False
        self.cancel_hovered: bool = False

        # 字体
        self._font_title: pygame.font.Font = pygame.font.Font(None, 20)
        self._font_field: pygame.font.Font = pygame.font.Font(None, 18)
        self._font_label: pygame.font.Font = pygame.font.Font(None, 16)
        self._font_small: pygame.font.Font = pygame.font.Font(None, 14)

        # 计算布局
        self._compute_layout()

    # ------------------------------------------------------------------
    # 布局计算
    # ------------------------------------------------------------------

    def _compute_layout(self) -> None:
        """计算所有输入框和按钮的位置。"""
        cx = WINDOW_WIDTH // 2

        # 中心垂直偏移
        cy = WINDOW_HEIGHT // 2
        row_start_y = cy + self.ROW_START_OFFSET

        # 每行左侧：系数框位置
        coeff_x = cx - 55
        # 每行指数框位置
        exp_x = cx + 60

        for row in range(3):
            coeff_idx = row * 2
            exp_idx = row * 2 + 1
            row_y = row_start_y + row * self.ROW_SPACING

            # 系数框
            cf = self.fields[coeff_idx]
            cf["rect"].x = coeff_x
            cf["rect"].y = row_y
            # 使系数框居中于标签右侧
            cf["rect"].centery = row_y + self.FIELD_HEIGHT // 2

            # 指数框
            ef = self.fields[exp_idx]
            ef["rect"].x = exp_x
            ef["rect"].y = row_y
            ef["rect"].centery = row_y + self.FIELD_HEIGHT // 2

        # OK / Cancel 按钮位置
        btn_y = row_start_y + 3 * self.ROW_SPACING + 10
        self.ok_rect.x = cx - 80
        self.ok_rect.y = btn_y
        self.cancel_rect.x = cx + 8
        self.cancel_rect.y = btn_y

    # ------------------------------------------------------------------
    # 字段值读取
    # ------------------------------------------------------------------

    def _get_field_value(
        self, coeff_idx: int, exp_idx: int
    ) -> float:
        """读取系数和指数并计算数值。

        Args:
            coeff_idx: 系数输入框索引
            exp_idx: 指数输入框索引

        Returns:
            计算后的数值
        """
        coeff_text = self.fields[coeff_idx]["text"]
        exp_text = self.fields[exp_idx]["text"]

        try:
            coeff = float(coeff_text) if coeff_text else 1.0
        except ValueError:
            coeff = 1.0

        try:
            exp = int(exp_text) if exp_text else 0
        except ValueError:
            exp = 0

        return coeff * (10 ** exp)

    # ------------------------------------------------------------------
    # 预填值
    # ------------------------------------------------------------------

    def prefill(self, mass: float) -> None:
        """预填 radius 的默认值。

        Args:
            mass: 当前质量 (kg)，未使用（保留参数兼容）
        """
        # 重设所有字段为 placeholder
        for i, field in enumerate(self.fields):
            field["text"] = field["placeholder"]

        # 使用固定默认半径（米）转为 km 填入弹窗
        from src.config import CUSTOM_RADIUS_DEFAULT
        radius_km = CUSTOM_RADIUS_DEFAULT / 1000.0
        r_coeff, r_exp = _float_to_components(radius_km)
        self.fields[4]["text"] = r_coeff
        self.fields[5]["text"] = r_exp

    # ------------------------------------------------------------------
    # 字段值读取
    # ------------------------------------------------------------------

    def get_results(self) -> Dict[str, float]:
        """读取所有输入框并计算最终参数。

        Returns:
            {"mass": float (kg), "charge": float (C), "radius": float (m)}

        注意：半径从 km 转为 m（×1000）。
        解析失败时静默使用默认值（系数 1.0，指数 0）。
        """
        mass = self._get_field_value(0, 1)
        charge = self._get_field_value(2, 3)
        radius = self._get_field_value(4, 5) * 1000.0  # km -> m
        return {"mass": mass, "charge": charge, "radius": radius}

    # ------------------------------------------------------------------
    # 输入校验
    # ------------------------------------------------------------------

    def _is_valid_input(self, char: str, field_idx: int) -> bool:
        """检查输入的字符是否合法。

        Args:
            char: 输入的字符
            field_idx: 输入框索引

        Returns:
            是否合法
        """
        field = self.fields[field_idx]
        allow_decimal = field["allow_decimal"]
        allow_negative = field["allow_negative"]

        if char in "0123456789":
            return True
        if char == "." and allow_decimal:
            # 检查是否已有小数点
            return "." not in field["text"]
        if char == "-" and allow_negative:
            # 负号只能在开头
            return field["text"] == ""
        return False

    # ------------------------------------------------------------------
    # 事件处理
    # ------------------------------------------------------------------

    def handle_event(
        self, event: pygame.event.Event
    ) -> Optional[Union[str, Dict[str, float]]]:
        """处理事件。

        Args:
            event: Pygame 事件

        Returns:
            - {"mass": float, "charge": float, "radius": float} — 确认
            - "CANCEL" — 取消
            - None — 事件已消费，无动作
        """
        if not self.visible:
            return None

        # 鼠标移动：更新按钮悬停状态
        if event.type == pygame.MOUSEMOTION:
            self.ok_hovered = self.ok_rect.collidepoint(event.pos)
            self.cancel_hovered = self.cancel_rect.collidepoint(event.pos)
            return None

        # 鼠标点击
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            # 检查输入框点击
            for i, field in enumerate(self.fields):
                if field["rect"].collidepoint(event.pos):
                    self.active_field_index = i
                    self.cursor_visible = True
                    return None

            # 检查 OK 按钮
            if self.ok_rect.collidepoint(event.pos):
                return self.get_results()

            # 检查 Cancel 按钮
            if self.cancel_rect.collidepoint(event.pos):
                return "CANCEL"

            # 点击弹窗外区域忽略
            return None

        # 键盘输入
        if event.type == pygame.KEYDOWN:
            # Esc = Cancel
            if event.key == pygame.K_ESCAPE:
                return "CANCEL"

            # Enter = OK
            if event.key == pygame.K_RETURN:
                return self.get_results()

            if self.active_field_index < 0:
                return None

            field = self.fields[self.active_field_index]

            # Backspace
            if event.key == pygame.K_BACKSPACE:
                field["text"] = field["text"][:-1]
                return None

            # 获取按键字符
            if event.key == pygame.K_KP_MINUS:
                char = "-"
            elif event.key == pygame.K_KP_PERIOD:
                char = "."
            else:
                try:
                    char = event.unicode
                except Exception:
                    return None

            # 检查合法性并附加
            if char and self._is_valid_input(char, self.active_field_index):
                field["text"] += char

            return None

        return None

    # ------------------------------------------------------------------
    # 绘制
    # ------------------------------------------------------------------

    def draw(self, surface: pygame.Surface) -> None:
        """绘制弹窗。

        Args:
            surface: 目标 Surface
        """
        if not self.visible:
            return

        cx = WINDOW_WIDTH // 2
        cy = WINDOW_HEIGHT // 2
        pw = self.PANEL_WIDTH
        ph = self.PANEL_HEIGHT
        px = cx - pw // 2
        py = cy - ph // 2

        # 半透明背景遮罩
        mask = pygame.Surface((WINDOW_WIDTH, WINDOW_HEIGHT), pygame.SRCALPHA)
        mask.fill((0, 0, 0, 120))
        surface.blit(mask, (0, 0))

        # 面板背景
        panel_surf = pygame.Surface((pw, ph), pygame.SRCALPHA)
        panel_surf.fill(DIALOG_BG)
        surface.blit(panel_surf, (px, py))
        pygame.draw.rect(surface, DIALOG_BORDER, (px, py, pw, ph), 2, border_radius=8)

        # 标题
        title = "Custom Particle Config"
        title_surf = self._font_title.render(title, True, TEXT_HIGHLIGHT)
        tr = title_surf.get_rect(center=(cx, py + 18))
        surface.blit(title_surf, tr)

        # 光标闪烁
        now = pygame.time.get_ticks()
        self.cursor_visible = (now // self.BLINK_INTERVAL_MS) % 2 == 0

        row_start_y = cy + self.ROW_START_OFFSET
        label_x = px + 15

        for row in range(3):
            row_y = row_start_y + row * self.ROW_SPACING
            coeff_idx = row * 2
            exp_idx = row * 2 + 1

            # 行标签
            lbl_surf = self._font_label.render(ROW_LABELS[row], True, LABEL_COLOR)
            surface.blit(lbl_surf, (label_x, row_y + 3))

            # 每行：系数 + *10^ + 指数 + 单位
            self._draw_field(surface, self.fields[coeff_idx], coeff_idx == self.active_field_index, row_y)

            # *10^ 标签
            power_surf = self._font_small.render("*10^", True, LABEL_COLOR)
            power_rect = power_surf.get_rect(
                midleft=(self.fields[coeff_idx]["rect"].right + 4, row_y + self.FIELD_HEIGHT // 2)
            )
            surface.blit(power_surf, power_rect)

            # 指数输入框
            self._draw_field(surface, self.fields[exp_idx], exp_idx == self.active_field_index, row_y)

            # 单位（在指数框右侧）
            unit_surf = self._font_small.render(ROW_UNITS[row], True, LABEL_COLOR)
            unit_rect = unit_surf.get_rect(
                midleft=(self.fields[exp_idx]["rect"].right + 4, row_y + self.FIELD_HEIGHT // 2)
            )
            surface.blit(unit_surf, unit_rect)

        # OK / Cancel 按钮
        self._draw_button(
            surface, self.ok_rect, "OK",
            BTN_OK_HOVER if self.ok_hovered else BTN_OK_COLOR,
        )
        self._draw_button(
            surface, self.cancel_rect, "Cancel",
            BTN_CANCEL_HOVER if self.cancel_hovered else BTN_CANCEL_COLOR,
        )

        # 底部提示
        hint = "Esc to cancel  |  Enter to confirm"
        hint_surf = self._font_small.render(hint, True, HINT_COLOR)
        hr = hint_surf.get_rect(center=(cx, py + ph - 10))
        surface.blit(hint_surf, hr)

    def _draw_field(
        self,
        surface: pygame.Surface,
        field: Dict,
        is_active: bool,
        row_y: int,
    ) -> None:
        """绘制单个输入框。

        Args:
            surface: 目标 Surface
            field: 输入框数据字典
            is_active: 是否激活
            row_y: 行垂直位置（用于光标定位）
        """
        rect = field["rect"]

        # 背景
        bg_color = FIELD_ACTIVE if is_active else FIELD_INACTIVE
        pygame.draw.rect(surface, bg_color, rect, border_radius=3)

        # 边框
        border_color = FIELD_BORDER_ACTIVE if is_active else FIELD_BORDER_INACTIVE
        pygame.draw.rect(surface, border_color, rect, 1, border_radius=3)

        # 文字或占位符
        if field["text"]:
            text_surf = self._font_field.render(field["text"], True, TEXT_HIGHLIGHT)
        else:
            text_surf = self._font_field.render(field["placeholder"], True, PLACEHOLDER_COLOR)

        text_rect = text_surf.get_rect(midleft=(rect.x + 4, rect.centery))
        surface.blit(text_surf, text_rect)

        # 光标闪烁（仅激活状态）
        if is_active and self.cursor_visible:
            cursor_x = text_rect.right + 1
            cursor_y1 = rect.y + 3
            cursor_y2 = rect.bottom - 3
            pygame.draw.line(surface, CURSOR_COLOR, (cursor_x, cursor_y1), (cursor_x, cursor_y2), 2)

    def _draw_button(
        self,
        surface: pygame.Surface,
        rect: pygame.Rect,
        text: str,
        color: Tuple[int, int, int],
    ) -> None:
        """绘制一个按钮。

        Args:
            surface: 目标 Surface
            rect: 按钮位置矩形
            text: 按钮文字
            color: 按钮颜色
        """
        # 背景
        pygame.draw.rect(surface, color, rect, border_radius=4)
        pygame.draw.rect(surface, DIALOG_BORDER, rect, 1, border_radius=4)

        # 文字
        text_surf = self._font_field.render(text, True, BTN_TEXT_COLOR)
        tr = text_surf.get_rect(center=rect.center)
        surface.blit(text_surf, tr)
