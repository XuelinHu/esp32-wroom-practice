# Smart Glasses V2 - Right-side Layout

V2 uses an adult head reference before component placement. The reference is a packaging aid,
not a medical or anthropometric fit guarantee.

## Human reference

| Item | Value |
|---|---:|
| Nominal head | 152 x 190 x 205 mm |
| Electronics-to-head clearance | 4 mm |
| Hinge spacing | 152 mm |
| Temple length | 145 mm |
| Temple rail inner spacing | 160 mm |

## Right-side component orientation

| Component | Along temple | Outward thickness | Vertical |
|---|---:|---:|---:|
| XIAO ESP32-S3 Sense | 21 | 12 | 17.8 |
| Battery | 50 | 8 | 16 |
| Amplifier | 20 | 4 | 18 |
| Speaker | 38 | 7 | 25 |

The camera, controller, battery, latching switch, amplifier, speaker, antenna and cable routes are
all on the right side. The battery and speaker long axes follow the temple instead of crossing the
head volume.

## Fusion review files

- `output/smart_glasses_v2_right_side_assembly.step`: full assembly including transparent human
  reference, comfort keepout and electronic envelopes.
- `output/smart_glasses_v2_right_side_shell.step`: printable concept shells only.
- `output/smart_glasses_v2_right_side_shell.stl`: printable concept mesh.
- `output/smart_glasses_v2_right_side.FCStd`: generated parametric source.

The next fit iteration should replace the nominal head with the wearer's measured head width,
temple-to-ear distance, ear height and nose bridge dimensions.
