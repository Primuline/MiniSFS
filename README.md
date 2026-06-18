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
- **Trajectory preview** — Real-time predicted orbit display; reference frames use true future relative trajectories
- **Probe aiming** — Right-click probe, then drag to set launch direction and speed
- **Probe rocket control** — Probe placement opens a rocket parameter dialog; probe radius is the equilateral triangle side length
- **Edit body** — Right-click an existing body to edit mass/charge/radius (scientific notation)
- **Trail system** — Auto-record trajectories, with relative trails in reference frame mode
- **Time control** — Slow 2x / restore 1x / speed up 2x buttons, bounded from 1/64x to 64x
- **Coordinate grid** — Toggle with G key, adaptive spacing
- **Body labels** — Toggle with L key, automatic fade-out at distance
- **Shortcut panel** — Press H to view all shortcuts
- **Scale bar + status info** — Real-time FPS, body count, mouse world coordinates
- **Startup mode menu** — Choose Sandbox Mode or Level Mode; Level 1 provides a fixed Earth-Moon launch scene
- **Monochrome geometry UI** — Blank black background, white pixel borders, Ark Pixel font, and geometric body glyphs

---

## 🎮 Controls

| Action | Key |
|:-------|:----|
| Middle-click drag | Pan view |
| Scroll wheel | Zoom (centered on mouse) |
| Left-click body | Grab and drag (time pauses) |
| Double-click body | Enter reference frame follow mode |
| Arrow keys in probe reference frame | Fire probe thrusters (diagonal input is combined) |
| Right-click body | Edit parameters (mass/charge/radius) |
| Right-click probe | Aim, then drag to launch |
| Right-click empty | Cancel tool / deselect |
| `Esc` | Mode menu: quit; Sandbox: close shortcut panel / cancel placement / exit reference frame / quit game |
| `Space` | Pause/resume |
| `R` | Reset camera |
| `G` | Toggle coordinate grid |
| `L` | Toggle body labels |
| `H` | Toggle shortcut panel |
| `T` | Toggle trail display |
| `Del` / `Backspace` | Delete selected body |

### Toolbar

| Button | Shortcut | Function |
|:-------|:---------|:---------|
| **S** | `1` | Place star (static, place directly) |
| **P** | `2` | Place planet (click position, then drag to set velocity) |
| **D** | `3` | Place probe (configure total mass, fuel, exhaust velocity, mass flow, radius first) |
| **C** | `4` | Custom particle (scientific notation dialog) |

### Time Control

| Button | Shortcut | Function |
|:-------|:---------|:---------|
| `||` / `>` | `Space` | Pause/resume |
| `<<` | — | Slow time by 2x |
| `1x` | — | Restore 1x speed |
| `>>` | — | Speed up time by 2x |

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

The app opens on the mode menu. Select **Sandbox Mode** to start the current default scene:
one central star (mass 2x10^30 kg) + one orbiting planet (1 AU orbit).
**Level Mode** is visible but disabled until level flow is implemented.

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
│   │   ├── renderer.py         # Renderer — geometric body drawing, highlight
│   │   ├── camera.py           # Camera — viewport transformation, zoom, follow
│   │   ├── hud.py              # HUD — toolbar, time control, info panel, scale bar
│   │   ├── effects.py          # Trails, particle effects, trajectory preview, grid, labels
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
