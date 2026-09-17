# Smart Glasses V1 Parameters

All dimensions are millimeters. Values marked `verify` are engineering defaults and must be
replaced after measuring the real part or wearer.

| Parameter | Value | Status |
|---|---:|---|
| Battery | 50 x 16 x 8 | measured |
| Speaker | 38 x 25 x 7 | measured |
| Amplifier PCB | 20 x 18 x 4 | thickness verify |
| XIAO ESP32S3 Sense envelope | 21 x 17.8 x 12 | height verify against official STEP |
| Camera envelope | 18 x 18 x 12 | verify |
| U.FL antenna | 35 x 6 x 1.2 | verify |
| Latching switch | 5.8 x 5.8 x 8 | verify after purchase |
| Frame width | 145 | wearer measurement required |
| Lens opening | 55 x 38 | wearer/lens measurement required |
| Bridge width | 17 | wearer measurement required |
| Temple length | 145 | wearer measurement required |
| Shell wall | 1.8 | suitable for FDM prototype |
| Part clearance | 0.7 | suitable for FDM prototype |

## Layout

- Front bridge: extended OV5640 camera pod.
- Left front temple: XIAO ESP32S3 Sense, USB-C and SD service side.
- Left rear temple: battery and latching power switch.
- Right front temple: amplifier.
- Right rear temple: speaker with vent face toward the ear.
- Right upper temple: U.FL antenna keepout; avoid battery, speaker magnet and metal screws.

## Files

- `output/smart_glasses_v1_assembly.step`: shell plus transparent component envelopes.
- `output/smart_glasses_v1_shell.step`: printable shell concepts only.
- `output/smart_glasses_v1_shell.stl`: combined prototype mesh.
- `output/smart_glasses_v1.FCStd`: parametric source used to generate the exchange files.
- `vendor/xiao-sense/Seeed Studio XIAO-ESP32-S3-Sense.step`: official Seeed model.

Import the assembly STEP into Fusion 360 for positioning and visual review. The V1 geometry is a
packaging prototype; hinges, nose pads, lens retention and final ergonomic curves belong to V2
after wearer and real-part measurements are available.
