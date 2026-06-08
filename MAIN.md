# MiniSFS 架构总览

MiniSFS (Mini Space Flight Simulator) 是一款 2D 关卡/沙盒物理模拟游戏，类似《宇宙沙盒 (Universe Sandbox)》的 2D 版本 + 引力弹弓解谜。

---

## 1. 目录结构

```
MiniSFS/
├── assets/                      # 资源文件
│   ├── levels/                  # 关卡 JSON 文件
│   ├── textures/                # 纹理资源
│   └── fonts/                   # 字体资源
├── docs/                        # 文档
├── src/                         # 源代码
│   ├── __init__.py
│   ├── main.py                  # 入口点 (Phase 3 创建)
│   ├── config.py                # 游戏全局常量
│   ├── core/                    # 核心数据类型与接口
│   │   ├── __init__.py
│   │   ├── types.py             # BodyState 数组列索引、类型别名、工厂函数
│   │   └── interfaces.py        # 7 个抽象接口定义
│   ├── physics/                 # 物理引擎
│   │   ├── __init__.py
│   │   ├── engine.py            # PhysicsEngine: update, predict_trajectory
│   │   ├── forces.py            # 引力/库仑力计算
│   │   ├── integrators.py       # 数值积分器 (Euler, RK4, Velocity Verlet)
│   │   └── collision.py         # 碰撞检测与响应
│   ├── quadtree/                # 四叉树与空间数据结构
│   │   ├── __init__.py
│   │   ├── quadtree.py          # Quadtree 实现
│   │   ├── barnes_hut.py        # Barnes-Hut 近似加速
│   │   └── trail.py             # TrailBuffer (deque 尾迹)
│   ├── rendering/               # 渲染与 UI
│   │   ├── __init__.py
│   │   ├── renderer.py          # Renderer: 天体绘制、背景、特效
│   │   ├── camera.py            # Camera: 视口变换
│   │   ├── hud.py               # HUD: 信息面板、控制按钮
│   │   └── effects.py           # 粒子特效、尾迹绘制
│   ├── game/                    # 游戏逻辑
│   │   ├── __init__.py
│   │   ├── manager.py           # GameManager: FSM、关卡切换
│   │   ├── level.py             # 关卡加载/保存 (JSON)
│   │   └── scoring.py           # 评分系统
│   └── input/                   # 输入处理
│       └── __init__.py
│       └── handler.py           # InputHandler: Pygame 事件→命令
├── tests/                       # 测试
│   ├── __init__.py
│   ├── fixtures/                # 测试数据 (JSON 关卡等)
│   ├── test_physics.py
│   ├── test_quadtree.py
│   ├── test_collision.py
│   └── test_game.py
├── MAIN.md                      # 本文档
├── pytest.ini
├── requirements.txt
└── README.md
```

## 2. 模块职责

| 模块 | 职责 | 依赖 | 不依赖 |
|------|------|------|--------|
| `src.core` | 类型定义、接口规范、列索引常量 | NumPy | Pygame |
| `src.physics` | 多体引力/库仑力计算、数值积分、碰撞响应 | NumPy, core | Pygame |
| `src.quadtree` | 四叉树空间划分、Barnes-Hut 近似、尾迹缓冲区 | NumPy, core | Pygame |
| `src.rendering` | Pygame 绘制、相机变换、HUD、特效 | Pygame, NumPy, core | physics 实现 |
| `src.game` | 游戏状态机、关卡加载、评分 | core | Pygame (尽量) |
| `src.input` | 事件处理、输入→命令转换 | Pygame, core | physics/rendering |
| `src.config` | 全局常量 | 无 | 无 |

**依赖方向**: `config` < `core` < `physics` + `quadtree` < `rendering` + `game` + `input`

## 3. 核心数据模型: BodyState 数组

所有模块通过扁平的 NumPy 数组 (BodyState) 交换天体数据。数组格式:

```python
# shape: (N, NUM_FIELDS=10), dtype: np.float64
bodies = np.array([
    [x, y, vx, vy, mass, charge, radius, body_type, is_static, is_active],
    ...
])
```

### 列索引 (BodyField)

| 索引 | 常量名 | 含义 | 单位 |
|------|--------|------|------|
| 0 | `X` | x 坐标 | m |
| 1 | `Y` | y 坐标 | m |
| 2 | `VX` | x 方向速度 | m/s |
| 3 | `VY` | y 方向速度 | m/s |
| 4 | `MASS` | 质量 | kg |
| 5 | `CHARGE` | 电荷 | C |
| 6 | `RADIUS` | 半径 | m |
| 7 | `BODY_TYPE` | 天体类型 (0/1/2/3) | - |
| 8 | `IS_STATIC` | 是否静态 (0/1) | - |
| 9 | `IS_ACTIVE` | 是否存活 (0/1) | - |

### 天体类型

| 值 | 常量 | 含义 |
|----|------|------|
| 0 | `BODY_TYPE_STAR` | 恒星 (大质量、发光、通常静态) |
| 1 | `BODY_TYPE_PLANET` | 行星 (普通天体、受引力影响) |
| 2 | `BODY_TYPE_PROBE` | 探测器 (玩家控制、燃料有限) |
| 3 | `BODY_TYPE_CHARGED` | 带电粒子 (受引力和库仑力) |

### 使用约定

```python
# 读取位置和速度
pos = bodies[:, [X, Y]]        # shape (N, 2)
vel = bodies[:, [VX, VY]]      # shape (N, 2)

# 读取质量数组
masses = bodies[:, MASS]       # shape (N,)

# 筛选活跃天体
active = bodies[bodies[:, IS_ACTIVE] == 1]

# 修改速度
bodies[:, VX] += ax * dt
```

## 4. 接口总览

所有接口定义在 `src.core.interfaces`，7 个抽象基类 (ABC):

| 接口 | 主要方法 | 调用者 | 实现者 |
|------|----------|--------|--------|
| `IPhysicsEngine` | `update()`, `compute_forces()`, `predict_trajectory()`, `handle_collisions()` | GameManager | physics.engine |
| `IQuadtree` | `insert()`, `rebuild()`, `query_range()`, `query_nearest()`, `barnes_hut_force()` | PhysicsEngine | quadtree |
| `ITrailBuffer` | `push_frame()`, `push_all()`, `get_trail()`, `rewind()`, `clear()`, `clear_all()` | Renderer, GameManager | quadtree.trail |
| `IRenderer` | `render()`, `render_background()`, `render_hud()`, `render_predicted_trajectory()` | 主循环 | rendering |
| `ICamera` | `world_to_screen()`, `screen_to_world()`, `pan()`, `zoom()`, `follow()`, `reset()` | Renderer, InputHandler | rendering.camera |
| `IGameManager` | `load_level()`, `check_win_condition()`, `check_lose_condition()`, `get_score()`, `set_state()` | 主循环 | game.manager |
| `IInputHandler` | `process_events()`, `get_mouse_world_pos()` | 主循环 | input.handler |

## 5. 主循环 Tick 流程

```
┌─────────────────────────────────────────────────┐
│  while running:                                 │
│                                                  │
│  1. clock.tick(TARGET_FPS) → dt                 │
│  2. events = input_handler.process_events()      │
│  3. 处理事件命令 (SELECT, PAUSE, PLACE_BODY...)  │
│  4. 如果 game_state == PLAYING:                  │
│     a. 重建四叉树 (如启用)                        │
│     b. 物理引擎更新:                              │
│        forces = compute_forces(bodies)           │
│        bodies = integrate(bodies, forces, dt)     │
│        bodies = handle_collisions(bodies)         │
│     c. 尾迹记录: trail_buffer.push_all(bodies)   │
│     d. 条件检查: check_win/lose                  │
│  5. 渲染:                                        │
│     renderer.render(bodies, trails, camera)      │
│     renderer.render_hud(game_state, score)       │
│  6. 如果 win/lose: 显示结算界面                   │
│                                                  │
└─────────────────────────────────────────────────┘
```

### 物理子步

每帧物理更新 (dt) 被拆分为多个子步以提高稳定性:

```python
dt_sub = dt / SUBSTEPS  # SUBSTEPS = 4
for _ in range(SUBSTEPS):
    forces = compute_forces(bodies)
    bodies = integrate(bodies, forces, dt_sub)
bodies = handle_collisions(bodies)
```

## 6. 配置常量

所有游戏常量集中在 `src/config.py`，按类别分组:

| 类别 | 关键常量 |
|------|----------|
| 物理 | `GRAVITATIONAL_CONSTANT`, `COULOMB_CONSTANT`, `TIME_STEP`, `SOFTENING`, `SUBSTEPS` |
| 渲染 | `WINDOW_WIDTH`, `WINDOW_HEIGHT`, `TARGET_FPS`, `BACKGROUND_COLOR`, `WORLD_SCALE` |
| 四叉树 | `BARNES_HUT_THETA`, `QUADTREE_CAPACITY`, `QUADTREE_FORCE_ENABLED` |
| 尾迹 | `MAX_TRAIL_LENGTH`, `TRAIL_COLOR_SLOW`, `TRAIL_COLOR_FAST` |
| 天体 | `BODY_TYPE_*`, `DEFAULT_RADIUS_*`, `DEFAULT_MASS_*` |
| 游戏 | `GAME_STATE_*`, `PROBE_FUEL_MAX`, `SCORE_WEIGHT_*` |
| 输入 | `CAMERA_PAN_SPEED`, `CAMERA_ZOOM_SPEED`, `CLICK_SELECTION_RADIUS` |

## 7. 关键设计决策

### 7.1 为什么用扁平的 NumPy 数组而不是对象列表?

- **向量化计算**: `np.linalg.norm`、广播操作比 Python for 循环快 10-100 倍
- **缓存友好**: 连续内存布局，CPU 缓存命中率高
- **接口简洁**: 渲染器和物理引擎交换一个数组，而不是复杂的对象图
- **易于扩展**: 增加新字段只需加一列，不影响现有代码

### 7.2 为什么用抽象基类 (ABC) 而不是 Protocol?

- ABC 强制子类实现所有抽象方法 (编译期/导入期检查)
- 适合本项目规模 (接口稳定、实现者固定)
- Protocol 适合"鸭子类型"场景 (本项目不需要)

### 7.3 为什么渲染器只读不写?

- 避免渲染器意外修改物理状态导致难以追踪的 Bug
- 物理引擎是唯一负责状态变更的模块
- 渲染器只从 BodyState 数组和 TrailBuffer 读取数据

### 7.4 为什么世界坐标用米 (m) 而不用像素?

- 物理计算 (G, k) 基于 SI 单位制，使用米直接计算
- 像素是显示层概念，物理层不应关心
- 通过 `WORLD_SCALE` (m/pixel) 和 `Camera` 完成单位转换

### 7.5 为什么四叉树和物理引擎分离?

- 四叉树可被物理引擎用于两个独立目的: 引力加速 (Barnes-Hut) 和碰撞检测加速 (范围查询)
- 分离后四叉树可独立替换 (例如换成网格哈希)
- 测试时可以分别注入 Mock

## 8. 数据流图

```
┌──────────┐    events     ┌──────────────┐
│  Pygame  │ ────────────> │ InputHandler │
│  Events  │               └──────┬───────┘
└──────────┘                      │ commands
                                  v
┌──────────┐    bodies     ┌──────────────┐    forces     ┌──────────────┐
│ Renderer │ <──────────── │ GameManager  │ ────────────> │ Phy Engine   │
│ (只读)   │               │ (orchestr)   │               │              │
└──────────┘               └──────┬───────┘               └──────┬───────┘
     ^                            │                              │
     │ trails                    │ bodies                       │ query
     v                            v                              v
┌──────────┐               ┌──────────────┐              ┌──────────────┐
│ TrailBuf │               │    Camera    │              │   Quadtree   │
│ (deque)  │               │  (transform) │              │  (Barnes-Hut)│
└──────────┘               └──────────────┘              └──────────────┘
```

## 9. 开发顺序

| Phase | 内容 | Agent | 产出 |
|-------|------|-------|------|
| **1** | 架构设计 | architect | 目录结构、接口、MAIN.md |
| **2a** | 物理引擎 | physics-engine | 力计算、积分器、碰撞检测 |
| **2b** | 四叉树 | quadtree-specialist | 空间划分、Barnes-Hut、尾迹 |
| **3** | 渲染与 UI | rendering-ui | Pygame 渲染、相机、HUD |
| **4** | 游戏逻辑 | game-designer | 关卡系统、状态机、评分 |

测试贯穿所有 Phase: tester agent 在每个 Phase 结束后介入。

## 10. 验收标准

- **物理正确性**:
  - 两体圆周运动误差 < 1%/轨道
  - 三体系统能量波动 < 0.1%/千步
  - 动量和能量守恒通过单元测试
- **性能**:
  - 500 天体时保持 60 FPS (含四叉树加速)
  - 1000 天体时 >30 FPS
- **游戏**:
  - 至少 3 个教学关卡可完整通关
  - 时间倒流平滑无卡顿
  - 预测轨迹与实际飞行路线偏差 < 5%
