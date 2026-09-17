import FreeCAD as App
import Mesh
import Part
from pathlib import Path


ROOT = Path(__file__).resolve().parent
OUT = ROOT / "output"
OUT.mkdir(exist_ok=True)

P = {
    "lens_width": 52.0,
    "lens_height": 38.0,
    "bridge_width": 18.0,
    "frame_depth": 4.0,
    "rim": 3.0,
    "hinge_spacing": 152.0,
    "temple_length": 145.0,
    "temple_height": 8.0,
    "temple_thickness": 5.0,
    "wall": 1.8,
    "part_clearance": 0.7,
    "body_clearance": 4.0,
    "head_width": 152.0,
    "head_depth": 190.0,
    "head_height": 205.0,
    "battery": (50.0, 16.0, 8.0),
    "speaker": (38.0, 25.0, 7.0),
    "amplifier": (20.0, 18.0, 4.0),
    "xiao": (21.0, 17.8, 12.0),
    "camera": (18.0, 18.0, 12.0),
    "antenna": (35.0, 6.0, 1.2),
    "switch": (5.8, 5.8, 8.0),
}

COLORS = {
    "shell": (0.10, 0.14, 0.19),
    "head": (0.83, 0.66, 0.55),
    "keepout": (0.92, 0.32, 0.22),
    "battery": (0.14, 0.39, 0.72),
    "pcb": (0.06, 0.43, 0.22),
    "speaker": (0.36, 0.37, 0.40),
    "camera": (0.08, 0.09, 0.11),
    "antenna": (0.92, 0.67, 0.10),
    "switch": (0.80, 0.10, 0.10),
    "cable": (0.95, 0.45, 0.08),
}


def add_part(doc, name, label, shape, color, transparency=0, role="Packaging envelope"):
    obj = doc.addObject("PartDesign::Feature", name)
    obj.Label = label
    obj.Shape = shape
    obj.addProperty("App::PropertyString", "DesignRole").DesignRole = role
    if obj.ViewObject is not None:
        obj.ViewObject.ShapeColor = color
        obj.ViewObject.Transparency = transparency
    return obj


def box_xyz(x_len, y_len, z_len, x, y, z):
    return Part.makeBox(x_len, y_len, z_len, App.Vector(x, y, z))


def ellipsoid(center, radii):
    sphere = Part.makeSphere(1.0)
    matrix = App.Matrix()
    matrix.A11, matrix.A22, matrix.A33 = radii
    matrix.A14, matrix.A24, matrix.A34 = center
    return sphere.transformGeometry(matrix)


def enclosure(outer, inner, origin, opening="rear"):
    ox, oy, oz = outer
    ix, iy, iz = inner
    x, y, z = origin
    shell = box_xyz(ox, oy, oz, x, y, z)
    if opening == "rear":
        cavity = box_xyz(ix, iy + P["wall"], iz,
                         x + (ox - ix) / 2, y + P["wall"], z + (oz - iz) / 2)
    else:
        cavity = box_xyz(ix + P["wall"], iy, iz,
                         x + P["wall"], y + (oy - iy) / 2, z + (oz - iz) / 2)
    return shell.cut(cavity)


def padded(component_xyz):
    return tuple(v + 2 * P["part_clearance"] for v in component_xyz)


def outer_for(inner_xyz):
    return tuple(v + 2 * P["wall"] for v in inner_xyz)


def frame_ring(center_x):
    outer_w = P["lens_width"] + 2 * P["rim"]
    outer_h = P["lens_height"] + 2 * P["rim"]
    outer = box_xyz(outer_w, P["frame_depth"], outer_h,
                    center_x - outer_w / 2, 0, -outer_h / 2)
    inner = box_xyz(P["lens_width"], P["frame_depth"] + 2, P["lens_height"],
                    center_x - P["lens_width"] / 2, -1, -P["lens_height"] / 2)
    return outer.cut(inner)


doc = App.newDocument("SmartGlasses_V2_RightSide")

sheet = doc.addObject("Spreadsheet::Sheet", "Parameters")
sheet.Label = "V2 PARAMETERS - millimeters"
sheet.set("A1", "Parameter")
sheet.set("B1", "Value_mm")
sheet.set("C1", "Status")
for row, (key, value) in enumerate(P.items(), start=2):
    sheet.set(f"A{row}", key)
    sheet.set(f"B{row}", " x ".join(str(v) for v in value) if isinstance(value, tuple) else str(value))
    sheet.set(f"C{row}", "measured" if key in {"battery", "speaker"} else "verify")

# Adult reference: a rounded cranium, tapered lower face, ears and a 4 mm comfort keepout.
cranium = ellipsoid((0, 96, 8), (76, 95, 96))
face = ellipsoid((0, 55, -45), (67, 54, 70))
head = cranium.fuse(face)
left_ear = ellipsoid((-79, 105, -18), (8, 13, 27))
right_ear = ellipsoid((79, 105, -18), (8, 13, 27))
head_with_ears = head.fuse(left_ear).fuse(right_ear)
head_ref = add_part(doc, "AdultHeadReference", "Adult head reference 152x190x205",
                    head_with_ears, COLORS["head"], 72, "Human reference - do not manufacture")

comfort_head = ellipsoid((0, 96, 8), (80, 99, 100)).fuse(
    ellipsoid((0, 55, -45), (71, 58, 74)))
comfort_head = comfort_head.fuse(ellipsoid((-79, 105, -18), (12, 17, 31)))
comfort_head = comfort_head.fuse(ellipsoid((79, 105, -18), (12, 17, 31)))
comfort_ref = add_part(doc, "HeadComfortKeepout", "Head plus 4 mm comfort keepout",
                       comfort_head, COLORS["keepout"], 88, "No-electronics keepout")

# Front frame with full-width end pieces. The electronics start at the right end piece.
lens_center = P["bridge_width"] / 2 + P["lens_width"] / 2
front = frame_ring(-lens_center).fuse(frame_ring(lens_center))
front = front.fuse(box_xyz(P["bridge_width"], P["frame_depth"], 6,
                           -P["bridge_width"] / 2, 0, 5))
front = front.fuse(box_xyz(18, P["frame_depth"], 8, -76, 0, -4))
front = front.fuse(box_xyz(18, P["frame_depth"], 8, 58, 0, -4))
front_obj = add_part(doc, "FrontFrame", "Front frame with 152 mm hinge spacing",
                     front, COLORS["shell"], role="Printable concept shell")

# Both rails sit outside the nominal head. The right rail is the common electronics spine.
left_front_link = box_xyz(14, 22, 8, -85, 2, -4)
left_rail = left_front_link.fuse(box_xyz(5, 125, 8, -85, 22, -4))
right_front_link = box_xyz(14, 22, 8, 71, 2, -4)
right_rail = right_front_link.fuse(box_xyz(5, 125, 8, 80, 22, -4))
left_rail_obj = add_part(doc, "LeftTempleRail", "Lightweight left temple rail",
                         left_rail, COLORS["shell"], role="Printable concept shell")
right_rail_obj = add_part(doc, "RightTempleRail", "Right electronics structural spine",
                          right_rail, COLORS["shell"], role="Printable concept shell")

# Camera at the right front, lens facing forward. It no longer occupies the bridge center.
camera_outer = (24.0, 17.0, 24.0)
camera_inner = (20.0, 14.0, 20.0)
camera_origin = (58.0, 1.0, 3.0)
camera_pod = enclosure(camera_outer, camera_inner, camera_origin, "rear")
lens_hole = Part.makeCylinder(5.5, 4.0, App.Vector(70, 0, 15), App.Vector(0, 1, 0))
camera_pod = camera_pod.cut(lens_hole)
camera_pod_obj = add_part(doc, "CameraPod", "Right-front OV5640 camera pod",
                          camera_pod, COLORS["shell"], role="Printable concept shell")
camera_env = box_xyz(18, 12, 18, 61, 3, 6)
add_part(doc, "CameraEnvelope", "OV5640 camera envelope", camera_env,
         COLORS["camera"], 25)

# All remaining hardware runs longitudinally on the outside of the right temple.
outer_x = 80.0

# XIAO orientation: outside thickness 12, along-temple length 21, vertical 17.8.
xiao_oriented = (12.0, 21.0, 17.8)
xiao_inner = padded(xiao_oriented)
xiao_outer = outer_for(xiao_inner)
xiao_origin = (outer_x, 24.0, -8.9)
xiao_shell = enclosure(xiao_outer, xiao_inner, xiao_origin, "rear")
xiao_shell_obj = add_part(doc, "ControllerHousing", "Right-side XIAO ESP32-S3 Sense housing",
                          xiao_shell, COLORS["shell"], role="Printable concept shell")
xiao_env = box_xyz(*xiao_oriented,
                   xiao_origin[0] + P["wall"] + P["part_clearance"],
                   xiao_origin[1] + P["wall"] + P["part_clearance"],
                   xiao_origin[2] + P["wall"] + P["part_clearance"])
add_part(doc, "XIAOSenseEnvelope", "XIAO ESP32-S3 Sense rotated along temple",
         xiao_env, COLORS["pcb"], 22)

# Battery orientation: outside thickness 8, along-temple length 50, vertical 16.
battery_oriented = (8.0, 50.0, 16.0)
battery_inner = padded(battery_oriented)
battery_outer = outer_for(battery_inner)
battery_origin = (outer_x, 48.0, -8.0)
battery_shell = enclosure(battery_outer, battery_inner, battery_origin, "rear")
battery_shell_obj = add_part(doc, "BatteryHousing", "Right-side longitudinal battery housing",
                             battery_shell, COLORS["shell"], role="Printable concept shell")
battery_env = box_xyz(*battery_oriented,
                      battery_origin[0] + P["wall"] + P["part_clearance"],
                      battery_origin[1] + P["wall"] + P["part_clearance"],
                      battery_origin[2] + P["wall"] + P["part_clearance"])
add_part(doc, "BatteryEnvelope", "Battery 50x16x8 rotated along temple",
         battery_env, COLORS["battery"], 22)

# Latching switch is accessible on the outside wall between controller and battery.
switch_origin = (90.8, 50.0, 2.0)
switch_env = box_xyz(5.8, 5.8, 8.0, *switch_origin)
add_part(doc, "PowerSwitchEnvelope", "Outside latching power switch",
         switch_env, COLORS["switch"], 10)

# Amplifier is vertical and longitudinal, sharing the speaker zone but farther outside.
amp_oriented = (4.0, 20.0, 18.0)
amp_inner = padded(amp_oriented)
amp_outer = outer_for(amp_inner)
amp_origin = (91.0, 101.0, 2.0)
amp_shell = enclosure(amp_outer, amp_inner, amp_origin, "rear")
amp_shell_obj = add_part(doc, "AmplifierHousing", "Right-rear amplifier housing",
                         amp_shell, COLORS["shell"], role="Printable concept shell")
amp_env = box_xyz(*amp_oriented,
                  amp_origin[0] + P["wall"] + P["part_clearance"],
                  amp_origin[1] + P["wall"] + P["part_clearance"],
                  amp_origin[2] + P["wall"] + P["part_clearance"])
add_part(doc, "AmplifierEnvelope", "Amplifier 20x18x4 rotated along temple",
         amp_env, COLORS["pcb"], 22)

# Speaker orientation: outside thickness 7, along-temple length 38, vertical 25.
# It starts beyond the ear keepout and vents toward the ear without intersecting it.
speaker_oriented = (7.0, 38.0, 25.0)
speaker_inner = padded(speaker_oriented)
speaker_outer = outer_for(speaker_inner)
speaker_origin = (91.0, 102.0, -26.0)
speaker_shell = enclosure(speaker_outer, speaker_inner, speaker_origin, "rear")
for z in (-17.0, -11.0, -5.0):
    vent = Part.makeCylinder(1.25, P["wall"] + 1.0,
                             App.Vector(90.0, 112.0, z), App.Vector(1, 0, 0))
    speaker_shell = speaker_shell.cut(vent)
speaker_shell_obj = add_part(doc, "SpeakerHousing", "Right-ear longitudinal speaker housing",
                             speaker_shell, COLORS["shell"], role="Printable concept shell")
speaker_env = box_xyz(*speaker_oriented,
                      speaker_origin[0] + P["wall"] + P["part_clearance"],
                      speaker_origin[1] + P["wall"] + P["part_clearance"],
                      speaker_origin[2] + P["wall"] + P["part_clearance"])
add_part(doc, "SpeakerEnvelope", "Speaker 38x25x7 rotated along temple",
         speaker_env, COLORS["speaker"], 22)

# Antenna and cable routes stay on the same side, above the battery and speaker magnet.
antenna_env = box_xyz(6.0, 35.0, 1.2, 92.0, 105.0, 22.0)
add_part(doc, "AntennaEnvelope", "Right-side antenna keepout",
         antenna_env, COLORS["antenna"], 35)
fpc_route = box_xyz(2.0, 32.0, 1.5, 78.0, 10.0, 12.0)
add_part(doc, "FPCRoute", "Right-side camera FPC route",
         fpc_route, COLORS["cable"], 35)
power_route = box_xyz(1.5, 92.0, 1.5, 88.0, 35.0, 10.0)
add_part(doc, "PowerAudioRoute", "Right-side power and audio route",
         power_route, COLORS["cable"], 35)

doc.recompute()

printable = [front_obj, camera_pod_obj, left_rail_obj, right_rail_obj,
             xiao_shell_obj, battery_shell_obj, amp_shell_obj, speaker_shell_obj]
invalid_printable = [obj.Name for obj in printable if not obj.Shape.isValid()]
if invalid_printable:
    raise RuntimeError("Invalid printable shapes: " + ", ".join(invalid_printable))
assembly = [obj for obj in doc.Objects if hasattr(obj, "Shape") and not obj.Shape.isNull()]
Part.export(assembly, str(OUT / "smart_glasses_v2_right_side_assembly.step"))
Part.export(printable, str(OUT / "smart_glasses_v2_right_side_shell.step"))
Mesh.export(printable, str(OUT / "smart_glasses_v2_right_side_shell.stl"))
doc.saveAs(str(OUT / "smart_glasses_v2_right_side.FCStd"))

print("Generated V2:")
for path in sorted(OUT.glob("smart_glasses_v2*")):
    print(f"  {path.name}: {path.stat().st_size} bytes")
