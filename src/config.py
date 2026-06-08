"""MiniSFS 游戏全局配置与常量。

此文件存放所有可调的游戏常量。各模块通过 ``from src.config import ...`` 导入使用。
常量分为物理、渲染、四叉树、游戏、输入等类别，按字母顺序组织在每个类别中。
"""

# ============================================================================
# 物理常量 (Physics)
# ============================================================================

# 万有引力常数 (N m^2 / kg^2)
GRAVITATIONAL_CONSTANT: float = 6.67430e-11

# 库仑常数 (N m^2 / C^2)
COULOMB_CONSTANT: float = 8.987551787e9

# 默认物理更新时间步 (秒)
TIME_STEP: float = 1.0 / 60.0

# 最大物理更新时间步，防止大 dt 导致物体穿越 (秒)
TIME_STEP_MAX: float = 1.0 / 30.0

# 软化参数 (m) — 防止距离过近时引力发散
SOFTENING: float = 1.0

# 物理子步数 — 每帧将 dt 拆分为子步以提高稳定性
SUBSTEPS: int = 4

# 最小允许质量 (kg) — 低于此值会被移除
MIN_MASS: float = 1.0

# ============================================================================
# 渲染常量 (Rendering)
# ============================================================================

# 窗口尺寸 (像素)
WINDOW_WIDTH: int = 1280
WINDOW_HEIGHT: int = 720

# 目标帧率 (FPS)
TARGET_FPS: int = 60

# 背景颜色 (RGB)
BACKGROUND_COLOR: tuple[int, int, int] = (10, 10, 30)

# 世界单位/像素比 (m per pixel) — 取决于模拟规模
WORLD_SCALE: float = 1e9  # 1 像素 = 1e9 米

# ============================================================================
# 四叉树常量 (Quadtree)
# ============================================================================

# Barnes-Hut 近似阈值 θ (s / d < theta 时使用质心近似)
BARNES_HUT_THETA: float = 0.5

# 四叉树每个节点最大容量 (超过则分裂)
QUADTREE_CAPACITY: int = 4

# 是否强制使用四叉树 (否则在 N < 50 时退化为 O(n^2))
QUADTREE_FORCE_ENABLED: bool = False

# ============================================================================
# 尾迹 / 轨迹常量 (Trail)
# ============================================================================

# 每个天体最大轨迹点数 (帧)
MAX_TRAIL_LENGTH: int = 300

# 尾迹颜色 — 速度从慢到快的渐变 (RGB)
TRAIL_COLOR_SLOW: tuple[int, int, int] = (50, 150, 255)    # 冷色
TRAIL_COLOR_FAST: tuple[int, int, int] = (255, 150, 50)    # 暖色

# 尾迹透明度 (0-255)
TRAIL_ALPHA_NEW: int = 200
TRAIL_ALPHA_OLD: int = 30

# ============================================================================
# 天体类型常量 (Body Types)
# ============================================================================

# 天体类型枚举值 (存于 BodyState 数组的第 BODY_TYPE 列)
BODY_TYPE_STAR: int = 0      # 恒星 — 大质量发光
BODY_TYPE_PLANET: int = 1    # 行星 — 普通天体
BODY_TYPE_PROBE: int = 2     # 探测器 — 玩家可控
BODY_TYPE_CHARGED: int = 3   # 带电粒子 — 受库仑力影响

# 不同类型天体的默认半径 (像素)
DEFAULT_RADIUS_STAR: float = 20.0
DEFAULT_RADIUS_PLANET: float = 8.0
DEFAULT_RADIUS_PROBE: float = 3.0
DEFAULT_RADIUS_CHARGED: float = 6.0

# 不同类型天体的默认质量 (kg)
DEFAULT_MASS_STAR: float = 1.0e30
DEFAULT_MASS_PLANET: float = 5.0e28
DEFAULT_MASS_PROBE: float = 1.0e3
DEFAULT_MASS_CHARGED: float = 1.0e10

# 不同类型天体的默认电荷 (C)
DEFAULT_CHARGE_CHARGED: float = 1.0e6

# ============================================================================
# 自定义粒子常量 (Custom Particle)
# ============================================================================

# 自定义粒子的默认质量 (kg)
CUSTOM_MASS_DEFAULT: float = 1.0e25
# 自定义粒子的默认电荷 (C)
CUSTOM_CHARGE_DEFAULT: float = 0.0
# 自定义粒子的默认速度 (m/s)
CUSTOM_SPEED_DEFAULT: float = 1.0e4
# 自定义粒子的质量调整步进 (倍数)
CUSTOM_MASS_STEP: float = 10.0
# 自定义粒子的电荷步进 (C)
CUSTOM_CHARGE_STEP: float = 1.0e5
# 自定义粒子的速度步进 (倍数)
CUSTOM_SPEED_STEP: float = 2.0
# 自定义粒子半径公式系数: radius = CUSTOM_RADIUS_FACTOR * sqrt(mass / 1e25) (像素)
CUSTOM_RADIUS_FACTOR: float = 6.0
# 自定义粒子质量范围
CUSTOM_MASS_MIN: float = 1.0e3
CUSTOM_MASS_MAX: float = 1.0e30

# ============================================================================
# 游戏常量 (Game)
# ============================================================================

# 游戏状态枚举值
GAME_STATE_MENU: str = "MENU"
GAME_STATE_PLAYING: str = "PLAYING"
GAME_STATE_PAUSED: str = "PAUSED"
GAME_STATE_WIN: str = "WIN"
GAME_STATE_LOSE: str = "LOSE"

# 关卡文件扩展名
LEVEL_FILE_EXTENSION: str = ".json"

# 关卡目录路径 (相对于项目根目录)
LEVEL_DIR: str = "assets/levels"

# 目标区域判定半径 (像素)
TARGET_ZONE_RADIUS: float = 15.0

# 探测器燃料上限 (秒)
PROBE_FUEL_MAX: float = 10.0

# 评分权重
SCORE_WEIGHT_TIME: float = 0.3
SCORE_WEIGHT_FUEL: float = 0.3
SCORE_WEIGHT_BODIES: float = 0.4

# ============================================================================
# 输入常量 (Input)
# ============================================================================

# 相机移动速度 (像素/秒)
CAMERA_PAN_SPEED: float = 500.0

# 相机缩放速度 (每滚轮步)
CAMERA_ZOOM_SPEED: float = 0.1

# 相机最小/最大缩放倍数
CAMERA_ZOOM_MIN: float = 0.1
CAMERA_ZOOM_MAX: float = 10.0

# 鼠标拖拽选择半径 (像素)
CLICK_SELECTION_RADIUS: float = 10.0
