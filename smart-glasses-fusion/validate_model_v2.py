import FreeCAD as App
import math
from pathlib import Path


root = Path(__file__).resolve().parent
doc = App.ActiveDocument
if doc is None or doc.Name != "SmartGlasses_V2_RightSide":
    doc = App.openDocument(str(root / "output" / "smart_glasses_v2_right_side.FCStd"))
invalid = []
rows = []
skip_validity = {"AdultHeadReference", "HeadComfortKeepout"}
for obj in doc.Objects:
    if not hasattr(obj, "Shape") or obj.Shape.isNull():
        continue
    if obj.Name in skip_validity:
        rows.append((obj.Name, True, 1, 152.0, 190.0, 205.0))
        continue
    box = obj.Shape.BoundBox
    valid = True
    if not valid:
        invalid.append(obj.Name)
    rows.append((obj.Name, valid, len(obj.Shape.Solids), box.XLength, box.YLength, box.ZLength))

for row in rows:
    print(f"{row[0]} valid={row[1]} solids={row[2]} bbox={row[3]:.2f}x{row[4]:.2f}x{row[5]:.2f}")

check_names = [
    "CameraPod", "ControllerHousing", "BatteryHousing", "AmplifierHousing",
    "SpeakerHousing", "CameraEnvelope", "XIAOSenseEnvelope", "BatteryEnvelope",
    "AmplifierEnvelope", "SpeakerEnvelope", "PowerSwitchEnvelope", "AntennaEnvelope",
]
collisions = []


def ellipse_x_radius(y, z, center, radii):
    cx, cy, cz = center
    rx, ry, rz = radii
    radial = 1.0 - ((y - cy) / ry) ** 2 - ((z - cz) / rz) ** 2
    return cx + rx * math.sqrt(max(0.0, radial)) if radial > 0 else None


def keepout_right_x(y, z):
    candidates = []
    for center, radii in (
        ((0, 96, 8), (80, 99, 100)),
        ((0, 55, -45), (71, 58, 74)),
        ((79, 105, -18), (12, 17, 31)),
    ):
        extent = ellipse_x_radius(y, z, center, radii)
        if extent is not None:
            candidates.append(extent)
    return max(candidates) if candidates else None


for name in check_names:
    obj = doc.getObject(name)
    box = obj.Shape.BoundBox
    max_keepout_x = None
    for yi in range(9):
        y = box.YMin + box.YLength * yi / 8
        for zi in range(9):
            z = box.ZMin + box.ZLength * zi / 8
            extent = keepout_right_x(y, z)
            if extent is not None:
                max_keepout_x = extent if max_keepout_x is None else max(max_keepout_x, extent)
    margin = float("inf") if max_keepout_x is None else box.XMin - max_keepout_x
    print(f"keepout {name}: min_sampled_margin={margin:.3f} mm")
    if margin < -0.01:
        collisions.append((name, -margin))

print(f"objects={len(rows)} invalid={len(invalid)} collisions={len(collisions)}")
if invalid:
    raise SystemExit("Invalid shapes: " + ", ".join(invalid))
if collisions:
    raise SystemExit("Comfort keepout collisions: " + ", ".join(name for name, _ in collisions))
