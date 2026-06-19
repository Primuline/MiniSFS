# MiniSFS Testing Notes

This file records stable test commands and what they cover.

## Baseline

Run before committing broad or cross-module work:

```powershell
pytest tests -q
```

Current recent baseline after Level 1 objective/result work:

```text
158 passed, 1 warning
```

The warning is from pygame/pkg_resources deprecation and is not currently treated as failure.

## Focused Commands

Level 1 and menu/HUD flow:

```powershell
pytest tests\test_level_1_scene.py tests\test_mode_menu.py -q
```

Rendering/probe UI:

```powershell
pytest tests\test_rendering_monochrome_ui.py tests\test_rendering_probe_ui.py -q
```

Physics and collisions:

```powershell
pytest tests\test_physics.py -q
```

Reference-frame trails and prediction:

```powershell
pytest tests\test_reference_frame_trails.py tests\test_reference_frame_camera.py -q
```

Packaging smoke test after PyInstaller build:

```powershell
python -m PyInstaller --noconfirm --clean MiniSFS.spec
$p = Start-Process -FilePath (Join-Path (Resolve-Path .).Path 'dist\MiniSFS.exe') -WorkingDirectory (Resolve-Path .).Path -PassThru
Start-Sleep -Seconds 3
if ($p.HasExited) { Write-Host "EXIT:$($p.ExitCode)" } else { Stop-Process -Id $p.Id -Force; Write-Host "RUNNING_OK_KILLED:$($p.Id)" }
```

## Test Policy

- Add focused regression tests for every fixed bug that has a stable assertion.
- For UI visual changes, prefer testing geometry/state helpers where possible; use Pygame dummy video driver for render smoke tests.
- Do not rely only on formula tests when the bug is about rendered pixels; add an actual rendered-surface test when practical.

