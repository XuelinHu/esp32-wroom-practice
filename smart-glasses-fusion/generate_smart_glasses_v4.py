import FreeCAD as App
import Mesh
import Part
from pathlib import Path


ROOT = Path(__file__).resolve().parent
OUT = ROOT / "output"
SOURCE = OUT / "smart_glasses_v2_right_side.FCStd"

COLORS = {
    "frame": (0.10, 0.12, 0.16),
    "left_rail": (0.28, 0.34, 0.42),
    "right_rail": (0.10, 0.22, 0.34),
    "camera": (0.04, 0.04, 0.05),
    "pcb": (0.05, 0.48, 0.25),
    "battery": (0.12, 0.40, 0.82),
    "reserve": (0.15, 0.70, 0.82),
    "audio": (0.75, 0.42, 0.08),
    "speaker": (0.48, 0.49, 0.52),
    "switch": (0.85, 0.12, 0.10),
    "head": (0.82, 0.65, 0.55),
    "keepout": (0.92, 0.28, 0.20),
}

WALL = 1.8
HEAD_CLEARANCE = 4.0


def add_shape(doc, name, label, shape, color, transparency=0, role="V4 packaging entity"):
    obj = doc.addObject("PartDesign::Feature", name)
    obj.Label = label
    obj.Shape = shape
    obj.addProperty("App::PropertyString", "DesignRole").DesignRole = role
    if obj.ViewObject is not None:
        obj.ViewObject.ShapeColor = color
        obj.ViewObject.Transparency = transparency
    return obj


def rounded_box(x_len, y_len, z_len, x, y, z, radius):
    box = Part.makeBox(x_len, y_len, z_len, App.Vector(x, y, z))
    try:
        fillet = box.makeFillet(radius, box.Edges)
        return fillet if fillet.isValid() else box
    except Exception:
        return box


def ellipsoid(center, radii):
    sphere = Part.makeSphere(1.0)
    matrix = App.Matrix()
    matrix.A11, matrix.A22, matrix.A33 = radii
    matrix.A14, matrix.A24, matrix.A34 = center
    return sphere.transformGeometry(matrix)


def curved_pipe(points, radius):
    curve = Part.BSplineCurve()
    curve.interpolate([App.Vector(*p) for p in points])
    path = Part.Wire(curve.toShape())
    start = App.Vector(*points[0])
    tangent = App.Vector(points[1][0] - points[0][0],
                         points[1][1] - points[0][1],
                         points[1][2] - points[0][2])
    profile = Part.Wire(Part.makeCircle(radius, start, tangent))
    return path.makePipeShell([profile], True, False)


def make_ear_hook(x):
    return curved_pipe([
        (x, 108, -1), (x, 124, -1), (x, 139, -5),
        (x, 150, -14), (x, 153, -28),
    ], 3.2)


def make_nose_bridge():
    # The center bows forward (negative Y), leaving room for the nose instead of being a straight bar.
    return curved_pipe([
        (-10, 0, 8), (-7, -1.8, 8), (-3.5, -3.8, 8),
        (0, -4.8, 8), (3.5, -3.8, 8), (7, -1.8, 8), (10, 0, 8),
    ], 3.0)


def enclosure(outer, inner, origin, opening="rear"):
    ox, oy, oz = outer
    ix, iy, iz = inner
    x, y, z = origin
    shell = rounded_box(ox, oy, oz, x, y, z, min(0.7, WALL - 0.1))
    if opening == "rear":
        cavity = Part.makeBox(ix, iy + WALL, iz,
                              App.Vector(x + (ox - ix) / 2, y + WALL, z + (oz - iz) / 2))
    else:
        cavity = Part.makeBox(ix + WALL, iy, iz,
                              App.Vector(x + WALL, y + (oy - iy) / 2, z + (oz - iz) / 2))
    return shell.cut(cavity)


def add_envelope(doc, name, label, dims, origin, color):
    shape = rounded_box(*dims, *origin, 0.8)
    return add_shape(doc, name, label, shape, color, 28, "Removable device envelope")


source = App.openDocument(str(SOURCE))
doc = App.newDocument("SmartGlasses_V4_UniversalRails")

sheet = doc.addObject("Spreadsheet::Sheet", "Parameters")
sheet.Label = "V4 PARAMETERS - universal equal-thickness rails"
sheet.set("A1", "Parameter")
sheet.set("B1", "Value")
rules = (
    ("Head reference", "152 x 190 x 205 mm"),
    ("Human clearance", "4 mm"),
    ("Rail outer width", "12 mm each side"),
    ("Rail vertical height", "24 mm each side"),
    ("Rail front to rear", "20 to 120 mm"),
    ("Nose bridge bow", "4.8 mm forward at center"),
    ("Brow beam radius", "1.8 mm"),
    ("Rail radius", "2.0 mm"),
    ("Electronics", "one continuous right rail"),
    ("Reserve", "two battery envelopes in left rail"),
)
for row, (key, value) in enumerate(rules, start=2):
    sheet.set(f"A{row}", key)
    sheet.set(f"B{row}", value)

# Human reference and comfort keepout remain visible but are not printable.
for name in ("AdultHeadReference", "HeadComfortKeepout"):
    src = source.getObject(name)
    add_shape(doc, name, src.Label, src.Shape.copy(), COLORS["head"] if name == "AdultHeadReference" else COLORS["keepout"],
              78 if name == "AdultHeadReference" else 90, "Human reference - do not manufacture")

# Half-frame: upper brow beams only, plus the ergonomic forward-bowed nose bridge.
left_brow = rounded_box(58, 5, 8, -67, 0, 8, 1.8)
right_brow = rounded_box(58, 5, 8, 9, 0, 8, 1.8)
left_end = rounded_box(18, 7, 10, -80, 0, 5, 2.0)
right_end = rounded_box(18, 7, 10, 62, 0, 5, 2.0)
front = left_brow.fuse(right_brow).fuse(left_end).fuse(right_end).fuse(make_nose_bridge())
add_shape(doc, "HalfFrameBrow", "Rounded upper brow beams and ergonomic nose bridge", front, COLORS["frame"], role="Printable V4 front structure")

# Equal left/right universal rails: one continuous rounded structural volume per side.
left_rail = rounded_box(12, 100, 24, -92, 20, -12, 2.0).fuse(make_ear_hook(-86))
right_rail = rounded_box(12, 100, 24, 80, 20, -12, 2.0).fuse(make_ear_hook(86))
add_shape(doc, "LeftUniversalRail", "Left universal rail - equal thickness reserve side", left_rail, COLORS["left_rail"], role="Printable V4 structural rail")
add_shape(doc, "RightUniversalRail", "Right universal rail - all device mounting side", right_rail, COLORS["right_rail"], role="Printable V4 structural rail")

# Camera is a slim forward clamp, not a bulky front pod. The camera body continues into the right rail.
camera_clamp = rounded_box(12, 18, 20, 80, 1, 0, 1.2)
camera_lens = Part.makeCylinder(5.5, 3, App.Vector(86, -2, 10), App.Vector(0, 1, 0))
add_shape(doc, "CameraMount", "Slim OV5640 front clamp", camera_clamp.cut(camera_lens), COLORS["camera"], role="Printable V4 camera mount")
add_envelope(doc, "CameraEnvelope", "OV5640 long camera envelope", (10, 32, 18), (81, 18, -7), COLORS["camera"])

# Device envelopes are aligned to the same right-side rail and use distinct colors.
add_envelope(doc, "XIAOSenseEnvelope", "XIAO ESP32-S3 Sense", (10, 22, 18), (81, 28, -9), COLORS["pcb"])
add_envelope(doc, "BatteryEnvelope", "Battery 50x16x8", (8, 50, 16), (82, 54, -8), COLORS["battery"])
add_envelope(doc, "PowerSwitchEnvelope", "Outside latching power switch", (8, 8, 8), (82, 76, 6), COLORS["switch"])
add_envelope(doc, "AmplifierEnvelope", "Amplifier 20x18x4", (6, 20, 18), (82, 92, -8), COLORS["audio"])
add_envelope(doc, "SpeakerEnvelope", "Speaker 38x25x7", (8, 38, 25), (82, 106, -29), COLORS["speaker"])

# Left reserve bays match the right rail's common envelope and can accept two battery packs later.
add_envelope(doc, "ReserveBatteryA", "Left reserve battery bay A", (8, 50, 16), (-90, 34, -8), COLORS["reserve"])
add_envelope(doc, "ReserveBatteryB", "Left reserve battery bay B", (8, 50, 16), (-90, 86, -8), COLORS["reserve"])

# Keep service routes on the same universal rail, separated from the antenna envelope.
add_envelope(doc, "AntennaEnvelope", "Right-side antenna keepout", (6, 35, 2), (86, 93, 10), (0.92, 0.67, 0.10))
add_envelope(doc, "FPCRoute", "Camera FPC route", (2, 35, 2), (86, 18, 8), (0.95, 0.45, 0.08))
add_envelope(doc, "PowerAudioRoute", "Power and audio route", (2, 76, 2), (86, 50, 8), (0.95, 0.45, 0.08))

doc.recompute()

printable_names = {"HalfFrameBrow", "LeftUniversalRail", "RightUniversalRail", "CameraMount", "RightUniversalRail"}
printable = [obj for obj in doc.Objects if obj.Name in printable_names]
invalid = [obj.Name for obj in printable if obj.Shape.isNull() or not obj.Shape.isValid()]
if invalid:
    raise RuntimeError("Invalid V4 printable shapes: " + ", ".join(invalid))

assembly = [obj for obj in doc.Objects if hasattr(obj, "Shape") and not obj.Shape.isNull()]
Part.export(assembly, str(OUT / "smart_glasses_v4_universal_rails_assembly.step"))
Part.export(printable, str(OUT / "smart_glasses_v4_universal_rails_shell.step"))
Mesh.export(printable, str(OUT / "smart_glasses_v4_universal_rails_shell.stl"))
doc.saveAs(str(OUT / "smart_glasses_v4_universal_rails.FCStd"))

print("Generated V4:")
for path in sorted(OUT.glob("smart_glasses_v4*")):
    print(f"  {path.name}: {path.stat().st_size} bytes")
