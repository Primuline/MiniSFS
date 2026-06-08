# 自定义粒子参数输入 — 科学计数法输入弹窗

## 概述

将当前的自定义粒子参数弹窗从 `+/-` 按钮调节改为**手动输入科学计数法数值**。
质量、电荷、速率三个参数各有两个输入框：系数（float）和指数（int）。

## 弹窗布局

弹窗居中显示，半透明背景遮罩覆盖全屏。

```
┌─────────────────────────────────────────┐
│         Custom Particle Config          │
│                                         │
│  Mass   [____]  *10^ [____] kg         │
│  Charge [____]  *10^ [____] C          │
│  Speed  [____]  *10^ [____] km/s       │
│  Radius: 6 px  (auto from mass)        │
│                                         │
│           [  OK  ]  [ Cancel ]          │
└─────────────────────────────────────────┘
```

## 交互方式

### 输入框切换
- 点击某个输入框使其获得焦点（显示光标闪烁）
- 同一时间只有一个输入框处于激活状态
- 6 个输入框可任意点击切换

### 键盘输入
- 系数输入框：支持 `0-9`、`.`（小数点）、`-`（负号）
- 指数输入框：支持 `0-9`、`-`（负号）
- `Backspace` — 删除最后一个字符
- `Enter` — 确认输入（相当于点 OK）

### 显示
- 激活的输入框显示**白色边框** + 闪烁光标（`|` 每 0.5 秒闪烁）
- 非激活输入框显示灰色边框
- 空输入框显示占位文字（如 "1.0"、"25"）

### 按钮
- 点击 `OK` → 读取所有输入框的值，计算最终参数：
  - `mass = coefficient × 10^exponent` (kg)
  - `charge = coefficient × 10^exponent` (C)
  - `speed = coefficient × 10^exponent` (m/s)
  - 注意：速度单位是 **km/s**，需转换为 m/s（×1000）
- 点击 `Cancel` / `Esc` → 关闭弹窗，取消整个放置操作

## 数据校验

- 系数不能为空，默认为 `1.0`
- 指数不能为空，默认为 `0`
- 解析失败（如空字符串或无效字符）时，使用默认值
- 不显示校验错误提示，静默使用默认值

## 技术实现

### 实现文件

在 `src/rendering/input_dialog.py` 中实现 `ScientificInputDialog` 类：

```python
class ScientificInputDialog:
    """科学计数法输入弹窗。"""
    
    def __init__(self):
        # 6 个输入框: mass_coeff, mass_exp, charge_coeff, charge_exp, speed_coeff, speed_exp
        # 每个输入框: rect, text, active, placeholder
        self.fields = [...]
        self.active_field_index = -1  # -1 = 无激活
        self.visible = False
        self.cursor_visible = True
        self.cursor_timer = 0.0
    
    def handle_event(self, event) -> Optional[dict]:
        """返回 {"mass": float, "charge": float, "speed": float} 或 "CANCEL" 或 None"""
    
    def draw(self, surface):
        """绘制弹窗"""
```

### 集成到现有系统

1. `src/rendering/hud.py` 的 `HUDManager` 中移除 `custom_dialog_buttons` 和 `create_dialog_buttons`/`destroy_dialog_buttons`
2. 改为引用 `ScientificInputDialog` 实例
3. `handle_event` 中优先将事件传给 `ScientificInputDialog`
4. `draw` 中调用 `ScientificInputDialog.draw()`

## 文件修改清单

| 文件 | 改动 |
|------|------|
| `src/rendering/input_dialog.py` | **新建** — `ScientificInputDialog` 类 |
| `src/rendering/hud.py` | 移除 `custom_dialog_buttons`，替换为 `ScientificInputDialog` |
| `src/main.py` | 移除 `CUSTOM_DIALOG_MASS_UP/DOWN` 等命令处理，改为读取 `ScientificInputDialog` 的返回结果 |

## 验收标准

1. 选择 C 工具 → 显示科学计数法输入弹窗
2. 点击输入框 → 显示白色边框 + 光标闪烁
3. 键盘输入数字和小数点 → 内容更新
4. OK 后正确计算实际数值
5. Cancel/Esc 关闭弹窗
6. 所有已有测试通过
