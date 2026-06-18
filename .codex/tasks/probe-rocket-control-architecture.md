# Probe Rocket Control Architecture Review

## Scope

This review covers the data model and cross-module boundaries for the first
probe rocket-control implementation. It does not require changing `src/`
business code.

Documents reviewed:

- `.codex/docs/guideline.md`
- `.codex/docs/python.md`
- `.codex/docs/git.md`
- `.codex/agents/architect.md`
- `README.md`
- `MAIN.md`
- `.codex/tasks/probe-rocket-control.md`
- `src/core/interfaces.py`
- `src/core/types.py`

## Recommendation: use a sidecar for v1

For the first version, keep `BodyState` at the existing 10-column shape and store
rocket-only state in a sidecar registry.

Reasons:

- `BodyState` is the physics/rendering exchange format. Its stable columns are
  position, velocity, mass, charge, radius, type, static flag, and active flag.
  Fuel mass, dry mass, exhaust velocity, and mass-flow rate are gameplay/control
  state, not universal physical body fields.
- Expanding `BodyState` would touch physics, rendering, quadtree, factories,
  tests, docs, and likely every place assuming `NUM_FIELDS == 10`. That is too
  much surface for a first feature pass.
- Renderer should continue to read `BodyState` only for body drawing. Fuel HUD
  should receive an explicit read-only view/model from game/UI orchestration, not
  infer rocket state from extra body columns.
- The physics formula can be implemented as a pure function that mutates only
  `MASS`, `VX`, and `VY` through a narrow orchestration API. The sidecar remains
  the owner of fuel-specific fields.

Recommended first-version model:

```python
@dataclass
class ProbeRocketState:
    dry_mass: float
    fuel_mass: float
    exhaust_velocity: float
    mass_flow_rate: float
```

Use `dict[int, ProbeRocketState]` only as a temporary row-index sidecar, and
document that keys are volatile body rows, not stable entity IDs.

## Row-index compression risk

Current architecture treats many IDs as row indices. This is workable for local
queries but risky for persistent gameplay state:

- `PhysicsEngine.update()` removes inactive rows after collision handling, so
  row count can shrink and all later row indices can shift.
- `remove_body_from_array()` also filters active rows immediately after marking a
  body inactive.
- Collision handling can destroy probes, merge bodies, or remove earlier rows in
  the array, invalidating any sidecar entries keyed by old row indices.
- `reference_body_id`, selected body IDs, trails, and quadtree IDs are already
  row-index based; rocket fuel state would add one more consumer that can become
  stale.
- Without a stable body ID or an old-index to new-index mapping, remapping after
  compaction is not fully reliable. Matching by position/velocity is a heuristic
  and can fail with nearby probes, identical probes, or high-speed motion.

Therefore, the implementation must not let raw row-index dictionaries survive a
delete/collision/update boundary without reconciliation.

## Recommended API boundary

For v1, keep rocket logic outside renderer and outside generic force
calculation. The main loop or future game manager should orchestrate it in this
order:

1. Resolve input context: arrow keys become thrust only when the current
   reference body is an active probe with rocket state.
2. Apply rocket thrust before `physics.update()` using a pure physics helper.
3. Run `physics.update()`.
4. Reconcile row-index sidecars and UI selection/reference IDs after any
   operation that can compact `bodies`.
5. Pass a read-only fuel display model to HUD.

Recommended pure helper API:

```python
def apply_probe_thrust(
    body_row: np.ndarray,
    rocket: ProbeRocketState,
    direction: tuple[float, float],
    dt: float,
) -> ProbeRocketState:
    """Apply thrust to one probe row and return updated rocket state."""
```

Behavior:

- Normalize non-zero direction before calling or inside the helper.
- If `fuel_mass <= 0`, leave velocity and mass unchanged.
- Compute actual fuel use with `min(fuel_mass, mass_flow_rate * dt)`.
- Apply `delta_v = direction * exhaust_velocity * fuel_used / current_mass`.
- Update `body_row[MASS] = dry_mass + remaining_fuel_mass`.
- Return a new `ProbeRocketState` or mutate through a clearly documented
  registry method, but do not put fuel fields into `BodyState`.

Recommended registry/reconciliation API:

```python
def reconcile_rocket_states(
    old_bodies: np.ndarray,
    new_bodies: np.ndarray,
    old_states: dict[int, ProbeRocketState],
) -> dict[int, ProbeRocketState]:
    """Return sidecar states remapped to compacted body rows."""
```

This API is acceptable only as a v1 bridge. The robust form should be:

```python
@dataclass
class BodyUpdateResult:
    bodies: np.ndarray
    index_map: dict[int, int]
    removed_indices: set[int]

def update_with_mapping(bodies: np.ndarray, dt: float) -> BodyUpdateResult:
    """Update physics and report old-row to new-row mapping after compaction."""
```

If implementation stays inside current APIs, add a small compaction helper at
the same orchestration layer that performs deletion and returns both
`new_bodies` and `index_map`. For collision-driven removals, the physics layer
should eventually expose the same mapping; otherwise rocket sidecar remapping is
best-effort only.

## Boundary decisions

- `src/physics/rocket.py` may contain pure thrust/fuel math. It should not import
  Pygame and should not know about keyboard state or HUD.
- `src/main.py` or future `src/game` owns the sidecar registry, reference-body
  context, and mapping/reconciliation.
- `src/rendering/hud.py` receives a display value such as fuel percent and fuel
  mass. It should not index into the sidecar registry directly.
- `src/core/types.py` should not add rocket columns in v1.
- `src/core/interfaces.py` does not need a breaking change for v1, but a future
  non-breaking `update_with_mapping()` or result object is recommended before
  more gameplay state depends on body identity.

## Acceptance notes for implementers

- Tests must cover deleting a probe, deleting a body before a probe, and
  collision-destroying a probe; stale fuel HUD or thrust on the wrong row should
  be treated as a failure.
- Tests must cover that non-probe reference frames keep arrow-key camera pan
  behavior.
- Manual validation should include two probes with different fuel values, then
  deleting or destroying the earlier row to verify fuel state does not attach to
  the wrong probe.
