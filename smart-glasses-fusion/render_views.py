import FreeCAD as App
import FreeCADGui as Gui
from pathlib import Path


root = Path(__file__).resolve().parent
out = root / "preview"
out.mkdir(exist_ok=True)
doc = App.openDocument(str(root / "output" / "smart_glasses_v1.FCStd"))
Gui.activeDocument().activeView().setAnimationEnabled(False)

palette = {
    "FrontFrame": (0.12, 0.15, 0.18),
    "CameraPod": (0.12, 0.15, 0.18),
    "LeftTempleRail": (0.12, 0.15, 0.18),
    "RightTempleRail": (0.12, 0.15, 0.18),
    "ControllerHousing": (0.16, 0.19, 0.23),
    "BatteryHousing": (0.16, 0.19, 0.23),
    "AmplifierHousing": (0.16, 0.19, 0.23),
    "SpeakerHousing": (0.16, 0.19, 0.23),
    "CameraEnvelope": (0.10, 0.10, 0.12),
    "XIAOSenseEnvelope": (0.08, 0.45, 0.22),
    "BatteryEnvelope": (0.15, 0.42, 0.78),
    "AmplifierEnvelope": (0.08, 0.45, 0.22),
    "SpeakerEnvelope": (0.45, 0.45, 0.48),
    "AntennaEnvelope": (0.95, 0.70, 0.10),
    "PowerSwitchEnvelope": (0.85, 0.12, 0.12),
    "FPCRoute": (0.95, 0.45, 0.10),
    "CoaxRoute": (0.95, 0.70, 0.10),
}
for obj in doc.Objects:
    if not hasattr(obj, "ViewObject") or obj.ViewObject is None:
        continue
    if obj.Name in palette:
        obj.ViewObject.ShapeColor = palette[obj.Name]
    if obj.Name.endswith("Envelope") or obj.Name.endswith("Route"):
        obj.ViewObject.Transparency = 35

view = Gui.activeDocument().activeView()
view.setBackgroundColor("#f4f7fb")
view.setDrawStyle("Shaded")

shots = [
    ("front_XZ.png", view.viewFront),
    ("top_XY.png", view.viewTop),
    ("side_YZ.png", view.viewRight),
    ("isometric.png", view.viewAxonometric),
]
for filename, orient in shots:
    orient()
    view.fitAll(0.9)
    view.saveImage(str(out / filename), 1600, 1000, "Current")
    print(out / filename)
