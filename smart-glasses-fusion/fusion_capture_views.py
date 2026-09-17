import adsk.core
import os
import traceback


OUTPUT_DIR = r"D:\workspace\things\esp32-wroom-practice\smart-glasses-fusion\preview\fusion"


def run(context):
    ui = None
    try:
        app = adsk.core.Application.get()
        ui = app.userInterface
        viewport = app.activeViewport
        os.makedirs(OUTPUT_DIR, exist_ok=True)

        views = (
            ("front_XZ.png", adsk.core.ViewOrientations.FrontViewOrientation),
            ("top_XY.png", adsk.core.ViewOrientations.TopViewOrientation),
            ("side_YZ.png", adsk.core.ViewOrientations.RightViewOrientation),
            ("isometric.png", adsk.core.ViewOrientations.IsoTopRightViewOrientation),
        )

        for filename, orientation in views:
            camera = viewport.camera
            camera.isSmoothTransition = False
            camera.isFitView = True
            camera.viewOrientation = orientation
            viewport.camera = camera
            viewport.refresh()
            adsk.doEvents()
            if not viewport.saveAsImageFile(os.path.join(OUTPUT_DIR, filename), 1600, 1000):
                raise RuntimeError("Fusion failed to save " + filename)

        ui.messageBox("Four Fusion 360 views were saved to:\n" + OUTPUT_DIR)
    except Exception:
        if ui:
            ui.messageBox("Capture failed:\n" + traceback.format_exc())
