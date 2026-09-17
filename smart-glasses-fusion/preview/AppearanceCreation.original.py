# Author-Autodesk Inc.
# Description-Demonstrates Appearances.add and the Appearance convenience properties (color, roughness, colorTexture, normalTexture, roughnessTexture).

# This sample creates three document-local appearances:
#
#   1. A solid red dielectric (color + roughness on an opaque surface).
#   2. A brushed chrome (color + roughness on a metallic surface).
#   3. A full PBR brick made from a diffuse / normal / roughness map set.
#
# Notes on the *Texture setters:
#   - Set colorTexture first when wiring up multiple maps. The normal and
#     roughness maps copy their UV scale from the first connected texture,
#     so they tile at the same rate without extra setup.
#   - normalTexture treats the supplied image as a tangent-space normal map
#     (the "OpenGL" / "_nor_gl_" variant from typical PBR sources).
#   - roughnessTexture resets the scalar `roughness` to 1.0 so the map's
#     grayscale values pass through directly. To attenuate, set `roughness`
#     after the texture:
#         brick.roughnessTexture = rough_path
#         brick.roughness = 0.7  # cap roughness at 70%
#   - For finer control over UV transforms, wrap modes, etc., access the
#     underlying AppearanceTexture via appearance.appearanceProperties.

import adsk.core
import adsk.fusion
import os
import traceback


def run(context):
    ui = None
    try:
        app = adsk.core.Application.get()
        ui = app.userInterface

        design = adsk.fusion.Design.cast(app.activeProduct)
        if not design:
            ui.messageBox("This sample requires an active Fusion Design document.")
            return

        appearances = design.appearances
        sample_dir = os.path.dirname(__file__)

        # ── Scenario 1: solid red opaque dielectric ──
        red = appearances.add("Sample Red")
        if not red:
            ui.messageBox("Failed to create the Sample Red appearance.")
            return
        red.color = adsk.core.Color.create(220, 30, 30, 255)
        red.roughness = 0.5

        # ── Scenario 2: brushed metal appearance ──
        chrome = appearances.add("Sample Chrome", adsk.core.AppearanceSurfaceTypes.MetallicAppearanceSurface)
        if chrome:
            chrome.color = adsk.core.Color.create(220, 220, 230, 255)
            chrome.roughness = 0.18

        # ── Scenario 3: full PBR brick ──
        # Replace these paths with any diffuse / normal / roughness image set
        # you have on disk; PNG and JPG are both supported. Set colorTexture
        # first so the normal and roughness maps inherit its UV scale (see
        # header notes).
        diffuse_path = os.path.join(sample_dir, "SampleBrick_Diff.png")
        normal_path = os.path.join(sample_dir, "SampleBrick_Normal.png")
        rough_path = os.path.join(sample_dir, "SampleBrick_Rough.png")
        brick = appearances.add("Sample Brick")
        if brick and all(os.path.isfile(p) for p in (diffuse_path, normal_path, rough_path)):
            brick.colorTexture = diffuse_path
            brick.normalTexture = normal_path
            brick.roughnessTexture = rough_path

        ui.messageBox(
            "Created appearances: 'Sample Red', 'Sample Chrome', 'Sample Brick'.\n"
            "Open the Appearance browser (Modify > Appearance) to see them under "
            "'In this Design'."
        )

    except:
        if ui:
            ui.messageBox("Failed:\n{}".format(traceback.format_exc()))
