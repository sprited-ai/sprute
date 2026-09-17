# Preserved driver inputs

These are the exact rendered MP4 inputs used or prepared in the September17 experiments, not previews or newly compressed substitutes. The manifest records SHA256 hashes, stream geometry, source cycles and rendering provenance.

| Preset | MP4 frames / FPS | Original cycle | Notes |
|---|---|---|---|
| idle | 120 /24 | 60 frames /24fps | Two cycles, rendered using run's white-body scene |
| walk | 120 /24 | 32 frames /24fps |5s of repeated walking; file end is not a cycle boundary |
| run | 65 /24 |25 frames /30fps | Original experiment477 video, unchanged |

All use768×768,3×3 with empty center,15° orthographic camera,gray background,white body and retained head/face textures. Runtime frame timing is carried by the MP4; do not reinterpret the run source cycle as25 frames at24fps.

These rendered inputs are retained for reproducibility. The original third-party VRM and motion libraries are not included; their rights are separate from the script source code. These files are not generated character animation outputs.
