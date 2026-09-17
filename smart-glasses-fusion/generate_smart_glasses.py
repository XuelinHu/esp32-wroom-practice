import FreeCAD as App
import Part
import Mesh
from pathlib import Path


ROOT = Path(__file__).resolve().parent
OUT = ROOT / "output"
OUT.mkdir(exist_ok=True)


P = {
    "frame_width": 145.0,
    "lens_width": 55.0,
    "lens_height": 38.0,
    "bridge_width": 17.0,
    "frame_depth": 4.0,
    "rim": 3.0,
    "temple_length": 145.0,
    "temple_height": 8.0,
    "temple_thickness": 5.0,
    "wall": 1.8,
    "clearance": 0.7,
    "battery": (50.0, 16.0, 8.0),
    "speaker": (38.0, 25.0, 7.0),
    "amplifier": (20.0, 18.0, 4.0),
    "xiao": (21.0, 17.8, 12.0),
    "camera": (18.0, 18.0, 12.0),
    "antenna": (35.0, 6.0, 1.2),
    "switch": (5.8, 5.8, 8.0),
}


COLORS = {
    "shell": (0.12, 0.15, 0.18),
    "battery": (0.18, 0.38, 0.68),
    "pcb": (0.08, 0.42, 0.22),
    "speaker": (0.35, 0.35, 0.38),
    "camera": (0.10, 0.10, 0.12),
    "antenna": (0.80, 0.62, 0.12),
    "switch": (0.75, 0.12, 0.12),
}


def add_part(doc, name, label, shape, color, transparency=0):
    obj = doc.addObject("PartDesign::Feature", name)
    obj.Label = label
    obj.Shape = shape
    obj.addProperty("App::PropertyString", "DesignRole").DesignRole = "Envelope / concept design"
    if obj.ViewObject is not None:
        obj.ViewObject.ShapeColor = color
        obj.ViewObject.Transparency = transparency
    return obj


def box_xyz(length, depth, height, x, y, z):
    return Part.makeBox(length, depth, height, App.Vector(x, y, z))


def enclosure(outer, inner, origin):
    ox, oy, oz = outer
    ix, iy, iz = inner
    x, y, z = origin
    shell = box_xyz(ox, oy, oz, x, y, z)
    cavity = box_xyz(ix, iy, iz, x + (ox - ix) / 2, y + P["wall"], z + (oz - iz) / 2)
    return shell.cut(cavity)


def frame_ring(center_x):
    ow = P["lens_width"] + 2 * P["rim"]
    oh = P["lens_height"] + 2 * P["rim"]
    outer = box_xyz(ow, P["frame_depth"], oh, center_x - ow / 2, 0, -oh / 2)
    inner = box_xyz(P["lens_width"], P["frame_depth"] + 2,
                    P["lens_height"], center_x - P["lens_width"] / 2,
                    -1, -P["lens_height"] / 2)
    return outer.cut(inner)


doc = App.newDocument("SmartGlasses_V1")

# Parameter spreadsheet stays visible after importing the FCStd into Fusion alternatives.
sheet = doc.addObject("Spreadsheet::Sheet", "Parameters")
sheet.Label = "PARAMETERS - millimeters"
sheet.set("A1", "Parameter")
sheet.set("B1", "Value_mm")
sheet.set("C1", "Status")
for row, (key, value) in enumerate(P.items(), start=2):
    sheet.set(f"A{row}", key)
    sheet.set(f"B{row}", " x ".join(str(v) for v in value) if isinstance(value, tuple) else str(value))
    sheet.set(f"C{row}", "measured" if key in {"battery", "speaker"} else "verify")

lens_center = P["bridge_width"] / 2 + P["lens_width"] / 2
front = frame_ring(-lens_center).fuse(frame_ring(lens_center))
bridge = box_xyz(P["bridge_width"], P["frame_depth"], 6.0,
                 -P["bridge_width"] / 2, 0, 5.0)
front = front.fuse(bridge)
front_obj = add_part(doc, "FrontFrame", "Front frame with lens openings", front, COLORS["shell"])

# Camera pod is centered above the bridge. A rear slot represents the extended FPC exit.
camera_outer = box_xyz(24, 16, 17, -12, 1, 12)
camera_cavity = box_xyz(20, 14, 14, -10, 2.8, 13.5)
camera_pod = camera_outer.cut(camera_cavity)
lens_hole = Part.makeCylinder(5.5, 4, App.Vector(0, 0, 20.5), App.Vector(0, 1, 0))
camera_pod = camera_pod.cut(lens_hole)
fpc_slot = box_xyz(12, 5, 2.0, -6, 12, 14)
camera_pod = camera_pod.cut(fpc_slot)
camera_pod_obj = add_part(doc, "CameraPod", "Camera pod - extended FPC", camera_pod, COLORS["shell"])

# Straight temple rails are replaceable by measured ergonomic curves in V2.
left_rail = box_xyz(P["temple_thickness"], P["temple_length"], P["temple_height"],
                    -P["frame_width"] / 2, 2, -4)
right_rail = box_xyz(P["temple_thickness"], P["temple_length"], P["temple_height"],
                     P["frame_width"] / 2 - P["temple_thickness"], 2, -4)
left_rail_obj = add_part(doc, "LeftTempleRail", "Left temple structural rail", left_rail, COLORS["shell"])
right_rail_obj = add_part(doc, "RightTempleRail", "Right temple structural rail", right_rail, COLORS["shell"])

# Left side: controller at the front, battery at the rear.
left_x = -P["frame_width"] / 2 - 4
controller_inner = (P["xiao"][0] + 2 * P["clearance"],
                    P["xiao"][1] + 2 * P["clearance"],
                    P["xiao"][2] + 2 * P["clearance"])
controller_outer = tuple(v + 2 * P["wall"] for v in controller_inner)
controller_shell = enclosure(controller_outer, controller_inner, (left_x, 10, -8))
controller_shell_obj = add_part(doc, "ControllerHousing", "Left controller housing", controller_shell, COLORS["shell"])

b_inner = tuple(v + 2 * P["clearance"] for v in P["battery"])
b_outer = tuple(v + 2 * P["wall"] for v in b_inner)
battery_shell = enclosure(b_outer, b_inner, (left_x, 58, -8))
battery_shell_obj = add_part(doc, "BatteryHousing", "Left battery housing", battery_shell, COLORS["shell"])

# Right side: amplifier at front, speaker at ear position.
right_x = P["frame_width"] / 2 - P["temple_thickness"] - 20
a_inner = tuple(v + 2 * P["clearance"] for v in P["amplifier"])
a_outer = tuple(v + 2 * P["wall"] for v in a_inner)
amp_shell = enclosure(a_outer, a_inner, (right_x, 18, -6))
amp_shell_obj = add_part(doc, "AmplifierHousing", "Right amplifier housing", amp_shell, COLORS["shell"])

s_inner = tuple(v + 2 * P["clearance"] for v in P["speaker"])
s_outer = tuple(v + 2 * P["wall"] for v in s_inner)
speaker_shell = enclosure(s_outer, s_inner, (right_x - 12, 76, -11))
for i in range(5):
    vent = Part.makeCylinder(1.2, P["wall"] + 1,
                             App.Vector(right_x - 4 + i * 5, 75, 0), App.Vector(0, 1, 0))
    speaker_shell = speaker_shell.cut(vent)
speaker_shell_obj = add_part(doc, "SpeakerHousing", "Right speaker housing with vents", speaker_shell, COLORS["shell"])

# Transparent electronic envelopes communicate fit and service access.
camera_env = box_xyz(*P["camera"], -P["camera"][0] / 2, 3, 14)
add_part(doc, "CameraEnvelope", "OV5640 camera envelope", camera_env, COLORS["camera"], 20)
xiao_env = box_xyz(*P["xiao"], left_x + P["wall"] + P["clearance"],
                   10 + P["wall"] + P["clearance"], -8 + P["wall"] + P["clearance"])
add_part(doc, "XIAOSenseEnvelope", "XIAO ESP32S3 Sense envelope", xiao_env, COLORS["pcb"], 20)
battery_env = box_xyz(*P["battery"], left_x + P["wall"] + P["clearance"],
                      58 + P["wall"] + P["clearance"], -8 + P["wall"] + P["clearance"])
add_part(doc, "BatteryEnvelope", "Battery 50x16x8", battery_env, COLORS["battery"], 20)
amp_env = box_xyz(*P["amplifier"], right_x + P["wall"] + P["clearance"],
                  18 + P["wall"] + P["clearance"], -6 + P["wall"] + P["clearance"])
add_part(doc, "AmplifierEnvelope", "Amplifier 20x18 envelope", amp_env, COLORS["pcb"], 20)
speaker_env = box_xyz(*P["speaker"], right_x - 12 + P["wall"] + P["clearance"],
                      76 + P["wall"] + P["clearance"], -11 + P["wall"] + P["clearance"])
add_part(doc, "SpeakerEnvelope", "Speaker 38x25x7", speaker_env, COLORS["speaker"], 20)
antenna_env = box_xyz(*P["antenna"], right_x - 8, 120, 4)
add_part(doc, "AntennaEnvelope", "U.FL antenna keepout", antenna_env, COLORS["antenna"], 35)
switch_env = box_xyz(*P["switch"], left_x - 1, 112, -1)
add_part(doc, "PowerSwitchEnvelope", "5.8mm latching power switch", switch_env, COLORS["switch"], 10)

# Cable channels represented as service envelopes.
fpc_route = box_xyz(2.2, 42, 1.5, -P["frame_width"] / 2 + 8, 4, 9)
add_part(doc, "FPCRoute", "Camera FPC routing keepout", fpc_route, (0.85, 0.55, 0.12), 35)
coax_route = box_xyz(1.5, 100, 1.5, P["frame_width"] / 2 - 4, 18, 4)
add_part(doc, "CoaxRoute", "U.FL coax routing keepout", coax_route, (0.9, 0.72, 0.18), 35)

doc.recompute()

printable = [front_obj, camera_pod_obj, left_rail_obj, right_rail_obj,
             controller_shell_obj, battery_shell_obj, amp_shell_obj, speaker_shell_obj]
Part.export(doc.Objects[1:], str(OUT / "smart_glasses_v1_assembly.step"))
Part.export(printable, str(OUT / "smart_glasses_v1_shell.step"))
Mesh.export(printable, str(OUT / "smart_glasses_v1_shell.stl"))
doc.saveAs(str(OUT / "smart_glasses_v1.FCStd"))

print("Generated:")
for path in sorted(OUT.iterdir()):
    print(f"  {path.name}: {path.stat().st_size} bytes")
