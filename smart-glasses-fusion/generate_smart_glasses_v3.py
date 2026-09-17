import FreeCAD as App
import Mesh
import Part
from pathlib import Path


ROOT = Path(__file__).resolve().parent
OUT = ROOT / "output"
SOURCE = OUT / "smart_glasses_v2_right_side.FCStd"

SHELL_COLOR = (0.10, 0.14, 0.19)
REFERENCE_NAMES = {"AdultHeadReference", "HeadComfortKeepout"}
OLD_STRUCTURE = {"FrontFrame", "LeftTempleRail", "RightTempleRail"}
PRINTABLE_HOUSINGS = {
    "CameraPod", "ControllerHousing", "BatteryHousing",
    "AmplifierHousing", "SpeakerHousing",
}


def add_shape(doc, name, label, shape, color=SHELL_COLOR, transparency=0, role="Printable V3 shell"):
    obj = doc.addObject("PartDesign::Feature", name)
    obj.Label = label
    obj.Shape = shape
    obj.addProperty("App::PropertyString", "DesignRole").DesignRole = role
    if obj.ViewObject is not None:
        obj.ViewObject.ShapeColor = color
        obj.ViewObject.Transparency = transparency
    return obj


def rounded_box(length, depth, height, x, y, z, radius):
    base = Part.makeBox(length, depth, height, App.Vector(x, y, z))
    try:
        return base.makeFillet(radius, base.Edges)
    except Exception:
        return base


def safe_fillet(shape, radius):
    try:
        rounded = shape.makeFillet(radius, shape.Edges)
        if not rounded.isNull() and rounded.isValid():
            return rounded
    except Exception:
        pass
    return shape


def make_ear_hook(x_center):
    points = [
        App.Vector(x_center, 112, 0),
        App.Vector(x_center, 126, -1),
        App.Vector(x_center, 139, -6),
        App.Vector(x_center, 149, -15),
        App.Vector(x_center, 153, -27),
    ]
    curve = Part.BSplineCurve()
    curve.interpolate(points)
    path = Part.Wire(curve.toShape())
    profile_edge = Part.makeCircle(3.2, points[0], App.Vector(0, 1, 0))
    profile = Part.Wire(profile_edge)
    return path.makePipeShell([profile], True, False)


source = App.openDocument(str(SOURCE))
doc = App.newDocument("SmartGlasses_V3_HalfFrame")

# Copy the parameter table and all V2 packaging references except the old full frame and rails.
sheet = doc.addObject("Spreadsheet::Sheet", "Parameters")
sheet.Label = "V3 PARAMETERS - half frame and rounded ear hooks"
sheet.set("A1", "Design rule")
sheet.set("B1", "Value")
rules = (
    ("Nominal adult head", "152 x 190 x 205 mm"),
    ("Comfort keepout", "4 mm"),
    ("Brow beam fillet", "1.8 mm"),
    ("Temple fillet", "2.0 mm"),
    ("Housing fillet", "0.7 mm where geometry permits"),
    ("Ear hook drop", "27 mm"),
    ("Electronics layout", "all on right side"),
)
for row, (key, value) in enumerate(rules, start=2):
    sheet.set(f"A{row}", key)
    sheet.set(f"B{row}", value)

for src in source.Objects:
    if not hasattr(src, "Shape") or src.Shape.isNull() or src.Name in OLD_STRUCTURE:
        continue
    transparency = 0
    color = SHELL_COLOR
    role = "V3 packaging envelope"
    if src.ViewObject is not None:
        transparency = src.ViewObject.Transparency
        color = src.ViewObject.ShapeColor
    shape = src.Shape.copy()
    if src.Name in PRINTABLE_HOUSINGS:
        shape = safe_fillet(shape, 0.7)
        role = "Printable rounded V3 shell"
    elif src.Name in REFERENCE_NAMES:
        role = "Human reference - do not manufacture"
    add_shape(doc, src.Name, src.Label, shape, color, transparency, role)

# Half-frame front: only upper brow beams and the center bridge remain.
# There are no lower rims and no prescription-lens retention features.
left_brow = rounded_box(58, 5, 8, -67, 0, 8, 1.8)
right_brow = rounded_box(58, 5, 8, 9, 0, 8, 1.8)
center_bridge = rounded_box(18, 5, 7, -9, 0, 7, 1.6)
left_end = rounded_box(18, 7, 10, -80, 0, 5, 2.0)
right_end = rounded_box(18, 7, 10, 62, 0, 5, 2.0)
front = left_brow.fuse(right_brow).fuse(center_bridge).fuse(left_end).fuse(right_end)
front = safe_fillet(front, 0.8)
front_obj = add_shape(doc, "HalfFrameBrow", "Rounded upper brow frame without lower rims", front)

# Rounded straight sections stay outside the head; continuous swept hooks drop behind each ear.
left_link = rounded_box(15, 22, 7, -85, 2, -3.5, 2.0)
left_straight = rounded_box(6.4, 92, 7, -85, 20, -3.5, 2.0)
left_hook = make_ear_hook(-81.8)
left_temple = left_link.fuse(left_straight).fuse(left_hook)
left_obj = add_shape(doc, "LeftRoundedTemple", "Rounded lightweight left temple with ear hook",
                     left_temple)

right_link = rounded_box(15, 22, 7, 70, 2, -3.5, 2.0)
right_straight = rounded_box(6.4, 92, 7, 80, 20, -3.5, 2.0)
right_hook = make_ear_hook(83.2)
right_temple = right_link.fuse(right_straight).fuse(right_hook)
right_obj = add_shape(doc, "RightRoundedTemple", "Rounded right electronics spine with ear hook",
                      right_temple)

doc.recompute()

printable_names = {
    "HalfFrameBrow", "LeftRoundedTemple", "RightRoundedTemple",
    "CameraPod", "ControllerHousing", "BatteryHousing",
    "AmplifierHousing", "SpeakerHousing",
}
printable = [obj for obj in doc.Objects if obj.Name in printable_names]
invalid = [obj.Name for obj in printable if obj.Shape.isNull() or not obj.Shape.isValid()]
if invalid:
    raise RuntimeError("Invalid V3 printable shapes: " + ", ".join(invalid))

assembly = [obj for obj in doc.Objects if hasattr(obj, "Shape") and not obj.Shape.isNull()]
Part.export(assembly, str(OUT / "smart_glasses_v3_half_frame_assembly.step"))
Part.export(printable, str(OUT / "smart_glasses_v3_half_frame_shell.step"))
Mesh.export(printable, str(OUT / "smart_glasses_v3_half_frame_shell.stl"))
doc.saveAs(str(OUT / "smart_glasses_v3_half_frame.FCStd"))

print("Generated V3:")
for path in sorted(OUT.glob("smart_glasses_v3*")):
    print(f"  {path.name}: {path.stat().st_size} bytes")
