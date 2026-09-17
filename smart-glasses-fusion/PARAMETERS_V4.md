# Smart Glasses V4 - Universal Equal-Thickness Rails

V4 removes the bulky camera pod and replaces the previous collection of side boxes with two
equal-size continuous universal rails. The right rail carries the current electronics; the left
rail has two reserve battery envelopes with matching clearance.

## Main changes

- Ergonomic nose bridge bows forward `4.8 mm` at its center.
- Left and right universal rails are both `12 mm` wide, `24 mm` high, and run from `Y=20` to `Y=120`.
- The camera is represented by a slim front clamp and a longer aligned camera envelope.
- Right-side envelopes: camera, XIAO ESP32-S3 Sense, battery, switch, amplifier and speaker.
- Left-side reserve: two battery positions, not installed by default.
- Distinct colors identify the frame, rails, camera, PCB, battery, reserve battery, audio board,
  speaker, switch, antenna and cable routes.
- No lower lens frame is included.

## Files

- `output/smart_glasses_v4_universal_rails_assembly.step`: review assembly with human reference.
- `output/smart_glasses_v4_universal_rails_shell.step`: structural shells only.
- `output/smart_glasses_v4_universal_rails_shell.stl`: structural prototype mesh.
- `output/smart_glasses_v4_universal_rails.FCStd`: generated source.

The human reference and colored device envelopes are for packaging review and are not printable
parts. Actual device measurements and wearer measurements are still required before fabrication.
