# MiniSFS — Mini Space Flight Simulator 🚀

A **2D space sandbox simulator** based on real N-body physics gravity. Place stars, planets, probes, and watch their trajectories under gravitational and Coulomb forces.
> Think of it as a 2D version of Universe Sandbox, but lighter and more focused on physics experimentation and interaction.

---

## ✨ Features

- **N-body gravity + Coulomb force simulation** — Full O(n^2) force calculation, RK4 integrator, 4 sub-steps/frame
- **Quadtree acceleration** (optional) — Barnes-Hut approximation, O(N log N) performance
- **Place bodies** — Star (S), Planet (P), Probe (D), Custom particle (C), supports scientific notation parameter input
- **Grab and drag** — Left-click drag a body, time pauses, velocity resets on release
- **Reference frame mode** — Double-click a body to enter reference frame view (smooth follow + auto-zoom), Esc to exit
- **Trajectory preview** — Real-time predicted orbit display when setting placement velocity (RK4 + full gravity, ~10 seconds)
- **Probe aiming** — Right-click probe, then drag to set launch direction and speed
- **Edit body** — Right-click an existing body to edit mass/charge/radius (scientific notation)
- **Trail system** — Auto-record trajectories, 300-frame fade-out effect
- **Time control** — Pause / 1x / 2x / 4x / 8x speed
- **Coordinate grid** — Toggle with G key, adaptive spacing
- **Body labels** — Toggle with L key, automatic fade-out at distance
- **Shortcut panel** — Press H to view all shortcuts
- **Scale bar + status info** — Real-time FPS, body count, mouse world coordinates

---

## 🎮 Controls

| Action | Key |
|:-------|:----|
| Middle-click drag | Pan view |
| Scroll wheel | Zoom (centered on mouse) |
| Left-click body | Grab and drag (time pauses) |
| Double-click body | Enter reference frame follow mode |
| Right-click body | Edit parameters (mass/charge/radius) |
| Right-click probe | Aim, then drag to launch |
| Right-click empty | Cancel tool / deselect |
| `Esc` | Exit reference frame / close shortcut panel / exit menu / quit game |
| `Space` | Pause/resume |
| `R` | Reset camera |
| `G` | Toggle coordinate grid |
| `L` | Toggle body labels |
| `H` | Toggle shortcut panel |
| `T` | Toggle trail display |
| `F` | 2x speed |
| `6` | 4x speed |
| `7` | 8x speed |
| `0` | Restore 1x speed |
| `Del` / `Backspace` | Delete selected body |

### Toolbar

| Button | Shortcut | Function |
|:-------|:---------|:---------|
| **S** | `1` | Place star (static, place directly) |
| **P** | `2` | Place planet (click position, then drag to set velocity) |
| **D** | `3` | Place probe |
| **C** | `4` | Custom particle (scientific notation dialog) |

### Time Control

| Button | Shortcut | Function |
|:-------|:---------|:---------|
| `|<` | — | Restore 1x speed |
| `>` | `Space` | Play/pause |
| `>>` | `F` | 2x speed |
| `>>>` | `6` | 4x speed |
| `>>>>` | `7` | 8x speed |

---

## 📦 Installation

```bash
# Clone the repository
git clone https://github.com/Primuline/MiniSFS.git
cd MiniSFS

# Install dependencies (conda or venv recommended)
pip install pygame numpy
```

Requires Python 3.10+.

---

## 🚀 Running

```bash
python -m src.main
```

Default scene: one central star (mass 2x10^30 kg) + one orbiting planet (1 AU orbit).

---

## 🗂 Project Structure

```
MiniSFS/
├── src/
│   ├── main.py                 # Main entry point and main loop
│   ├── config.py               # Global constants (scales, default parameters, etc.)
│   ├── core/
│   │   ├── types.py            # Body state array definition (10 columns, float64)
│   │   └── interfaces.py       # Module abstract interfaces (ABC)
│   ├── physics/
│   │   ├── engine.py           # PhysicsEngine — core physics update
│   │   ├── forces.py           # Gravitational + Coulomb force calculations
│   │   ├── integrators.py      # RK4 / Euler / Velocity Verlet
│   │   └── collision.py        # Collision detection and response rules
│   ├── rendering/
│   │   ├── renderer.py         # Renderer — body drawing, glow, highlight
│   │   ├── camera.py           # Camera — viewport transformation, zoom, follow
│   │   ├── hud.py              # HUD — toolbar, time control, info panel, scale bar
│   │   ├── effects.py          # Trails, particle effects, nebula background, trajectory preview, grid, labels
│   │   └── input_dialog.py     # Scientific notation input dialog
│   ├── input/
│   │   └── handler.py          # Events to commands (input layer separated from rendering layer)
│   └── quadtree/
│       ├── quadtree.py         # Quadtree implementation
│       ├── barnes_hut.py       # Barnes-Hut approximation acceleration
│       └── trail.py            # TrailBuffer — deque-based trail with fade-out
├── tests/
│   ├── test_integration.py     # Integration tests (16 scenarios)
│   ├── test_physics.py         # Physics unit tests
│   └── test_quadtree.py        # Quadtree unit tests (60 tests)
├── docs/                       # Design documents / feature specs
└── .claude/                    # Sub-agent configuration and development conventions
```

---

## 🔧 Technical Details

| Concept | Value |
|:--------|:------|
| World scale | 800 km/px |
| Base time step | 1/60 s, 4 sub-steps/frame |
| Integrator | RK4 (4th order Runge-Kutta) |
| Time acceleration | Base 3125x, 1x/2x/4x/8x |
| Body array | 10 columns x float64 |

### Body State Array

`numpy.ndarray` with shape `(N, 10)`:

| Index | Field | Description |
|:------|:------|:------------|
| 0 | X | x coordinate (m) |
| 1 | Y | y coordinate (m) |
| 2 | VX | x velocity (m/s) |
| 3 | VY | y velocity (m/s) |
| 4 | MASS | mass (kg) |
| 5 | CHARGE | charge (C) |
| 6 | RADIUS | radius (m) |
| 7 | BODY_TYPE | 0=star, 1=planet, 2=probe, 3=charged |
| 8 | IS_STATIC | 0=dynamic, 1=static |
| 9 | IS_ACTIVE | 0=inactive, 1=alive |

### Collision Rules

- **Star vs Planet** → Star absorbs the planet (mass/charge added)
- **Planet vs Planet** → Centroid merger (momentum conserved)
- **Probe vs Anything** → Probe is destroyed
- **Star vs Star** → Elastic collision

---

## 🧪 Testing

```bash
pytest tests/ -v
```

---

## 📫 License

MIT
