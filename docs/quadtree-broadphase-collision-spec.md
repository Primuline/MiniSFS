# 四叉树加速碰撞检测宽阶段 (Broad Phase)

## 1. 动机

碰撞检测当前使用 O(n²) 全量遍历，在大型场景下成为性能瓶颈：

| 天体数 | 碰撞检测耗时 |
|:------:|:-----------:|
| 50 | ~2ms |
| 200 | ~32ms |
| 500 | ~203ms |
| 1000 | ~834ms |

使用四叉树进行宽阶段（broad phase）过滤后，候选对数量从 n(n-1)/2 降至 O(n)：

| 天体数 | O(n²) | 四叉树宽阶段 | 加速比 |
|:------:|:-----:|:-----------:|:-----:|
| 100 | 7.87ms | 0.21ms | **38x** |
| 500 | 203ms | 1.35ms | **150x** |
| 1000 | 834ms | 3.12ms | **267x** |
| 2000 | 3398ms | 6.68ms | **509x** |

## 2. 设计

### 数据流

```
engine.update(bodies, dt)
  ├── substeps: RK4 积分（位置更新，不变）
  │
  ├── 条件判断: if n_active >= USE_QUADTREE_THRESHOLD（默认 50）
  │     ├── 构建四叉树: tree.rebuild(bodies)
  │     └── 宽阶段: candidates = tree.query_collision_candidates()
  │
  └── resolve_collisions(bodies, candidates=candidates)
        └── detect_collisions(bodies, candidates)
              ├── candidates=None → O(n²) 全量检测（小场景回退路径）
              └── candidates=[(id1,id2), ...] → 只检查候选对
```

### 接口变更

#### `src/physics/collision.py`

```python
def detect_collisions(
    bodies: np.ndarray,
    candidates: Optional[List[Tuple[int, int]]] = None,
) -> List[Tuple[int, int]]:
    """检测所有碰撞对。

    如果提供了 candidates（宽阶段候选对），只检查这些候选对；
    否则走 O(n²) 全量遍历（回退路径）。

    Args:
        bodies: 天体状态数组
        candidates: 四叉树宽阶段产出的候选对列表，可选

    Returns:
        实际碰撞对列表
    """
```

`handle_collisions()` 透传 `candidates` 参数：

```python
def handle_collisions(
    bodies: np.ndarray,
    merge_threshold: float = 10.0,
    collision_pairs: Optional[List[Tuple[int, int]]] = None,
) -> Tuple[np.ndarray, List[CollisionEvent]]:
```

#### `src/physics/engine.py`

`PhysicsEngine.__init__` 新增参数：

```python
class PhysicsEngine:
    def __init__(
        self,
        ...,
        use_quadtree: bool = False,
        quadtree_threshold: int = 50,
    ):
        self.use_quadtree = use_quadtree
        self.quadtree_threshold = quadtree_threshold
        self._quadtree: Optional[Quadtree] = None
```

`update()` 中碰撞处理前插入宽阶段：

```python
# 碰撞检测宽阶段（四叉树加速）
collision_candidates = None
if self.use_quadtree:
    n_active = int(np.sum(bodies[:, IS_ACTIVE] == 1.0))
    if n_active >= self.quadtree_threshold:
        if self._quadtree is None:
            from src.quadtree.quadtree import Quadtree
            self._quadtree = Quadtree(...)
        self._quadtree.rebuild(bodies)
        collision_candidates = self._quadtree.query_collision_candidates()

# 处理碰撞（传入候选对或 None 走回退路径）
bodies, _ = resolve_collisions(bodies, collision_pairs=collision_candidates)
```

### 边界自适应

`Quadtree.rebuild(bodies)` 已自动计算边界矩形（10% 边距），无需手动指定。

### 回退条件

当满足以下任一条件时，`detect_collisions` 走 O(n²) 全量路径：
- `candidates` 为 `None`
- `candidates` 为空列表（仅有 0 或 1 个活跃天体）
- 活跃天体数 < `quadtree_threshold`（宽阶段根本不启用）

## 3. 涉及文件

| 文件 | 改动 |
|:-----|:-----|
| `src/config.py` | 新增 `USE_QUADTREE_DEFAULT: bool = False`, `QUADTREE_COLLISION_THRESHOLD: int = 50` |
| `src/physics/collision.py` | `detect_collisions()` 和 `handle_collisions()` 新增 `candidates` 参数 |
| `src/physics/engine.py` | `PhysicsEngine.__init__` 新增 `use_quadtree`/`quadtree_threshold` 参数；`update()` 中碰撞前插入宽阶段 |
| `tests/test_physics.py` | 新增测试：四叉树宽阶段碰撞检测与 O(n²) 结果一致 |

## 4. 验收标准

1. `use_quadtree=False`（默认）时，行为与修改前完全一致（回退路径）
2. `use_quadtree=True, n < threshold` 时，行为与修改前完全一致（回退路径）
3. `use_quadtree=True, n >= threshold` 时，碰撞结果与 O(n²) 完全一致（宽阶段只过滤不相邻的候选对，不遗漏碰撞）
4. 基准测试：500 体场景下碰撞检测耗时 < 2ms（对比当前 ~200ms）
5. 所有已有测试通过

## 5. 注意事项

- `Quadtree.query_collision_candidates()` 返回共享同一叶节点的天体对，这些是**可能**发生碰撞的候选，不是实际碰撞。精确碰撞检测仍需在 `detect_collisions` 中做半径和检测。
- 四叉树容量 `QUADTREE_CAPACITY=4` 决定候选对粒度。容量越小，候选对越少但树越深。当前 4 是合理值。
