import adsk.core
import adsk.fusion
import traceback


BODY_STYLES = (
    ("AdultHeadReference", (210, 166, 140), 0.20),
    ("HeadComfortKeepout", (235, 72, 52), 0.10),
    ("HalfFrameBrow", (25, 31, 41), 1.00),
    ("LeftUniversalRail", (72, 87, 107), 1.00),
    ("RightUniversalRail", (26, 56, 87), 1.00),
    ("CameraMount", (16, 16, 18), 1.00),
    ("CameraEnvelope", (45, 45, 50), 0.65),
    ("XIAOSenseEnvelope", (13, 122, 64), 0.65),
    ("BatteryEnvelope", (31, 102, 209), 0.65),
    ("PowerSwitchEnvelope", (217, 31, 26), 0.80),
    ("AmplifierEnvelope", (191, 107, 20), 0.65),
    ("SpeakerEnvelope", (122, 125, 133), 0.65),
    ("ReserveBatteryA", (38, 178, 209), 0.55),
    ("ReserveBatteryB", (60, 207, 222), 0.55),
    ("AntennaEnvelope", (235, 171, 26), 0.55),
    ("FPCRoute", (242, 115, 20), 0.55),
    ("PowerAudioRoute", (247, 72, 93), 0.55),
)


def get_or_create_appearance(design, name, rgb):
    appearance = design.appearances.itemByName(name)
    if appearance:
        return appearance

    appearance = design.appearances.add(name)
    appearance.color = adsk.core.Color.create(rgb[0], rgb[1], rgb[2], 255)
    appearance.roughness = 0.55
    return appearance


def run(context):
    ui = None
    try:
        app = adsk.core.Application.get()
        ui = app.userInterface
        design = adsk.fusion.Design.cast(app.activeProduct)
        if not design:
            raise RuntimeError("The active Fusion document is not a design.")

        bodies = design.rootComponent.bRepBodies
        if bodies.count != len(BODY_STYLES):
            raise RuntimeError(
                "Expected {} V4 bodies, but Fusion contains {}. Make sure the active document "
                "is smart_glasses_v4_universal_rails_assembly.".format(len(BODY_STYLES), bodies.count)
            )

        for index, (body_name, rgb, opacity) in enumerate(BODY_STYLES):
            body = bodies.item(index)
            body.name = body_name
            body.appearance = get_or_create_appearance(design, "V4_" + body_name, rgb)
            body.opacity = opacity

        app.activeViewport.refresh()
        ui.messageBox("V4: renamed and colored {} bodies.".format(bodies.count))
    except Exception:
        if ui:
            ui.messageBox("V4 color assignment failed:\n" + traceback.format_exc())
