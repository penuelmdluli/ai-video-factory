"""
Render a Mixamo character + animation, headless, into a lit scene.

This replaces the scripted block figure. That rig proved the motion maths but
it had no face, and a character without a face has no performance - front and
back read identically, which is precisely why the walk direction was
ambiguous in every test frame.

A Mixamo FBX brings what a script cannot: a body, brows, EYES and a mouth, an
83-bone skeleton, and motion captured from a person. Everything around it -
world, light, camera, palette - is still built here in code, so the character
drops into the same scene the block figure walked through.

    blender --background --python blender/mixamo_render.py -- \
        --fbx "path/to/Character.fbx" --out output/x --still 60
"""
import argparse
import math
import sys

import bpy

PALETTE = {
    "sky_top": (0.086, 0.129, 0.243),
    "sky_mid": (0.478, 0.353, 0.451),
    "sky_low": (0.965, 0.612, 0.353),
    "ground":  (0.145, 0.133, 0.192),
    "set":     (0.216, 0.196, 0.286),
    "sun":     (1.000, 0.878, 0.612),
}


def clear():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def mat(name, rgb, rough=0.9):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*rgb, 1)
    b.inputs["Roughness"].default_value = rough
    return m


def box(name, size, loc, material):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc)
    o = bpy.context.object
    o.name = name
    o.scale = size
    bpy.ops.object.shade_smooth()
    b = o.modifiers.new("bevel", "BEVEL")
    b.width = min(size) * 0.2
    b.segments = 3
    o.data.materials.append(material)
    return o


def import_character(path):
    """Import the FBX and return (armature, meshes, frame_range).

    Mixamo ships a camera inside some exports and its own scene units; both
    are discarded so the scene here stays in charge of framing.
    """
    before = set(bpy.data.objects)
    bpy.ops.import_scene.fbx(filepath=path, automatic_bone_orientation=True)
    new = [o for o in bpy.data.objects if o not in before]

    for o in list(new):
        if o.type == "CAMERA":
            bpy.data.objects.remove(o, do_unlink=True)
            new.remove(o)

    arm = next((o for o in new if o.type == "ARMATURE"), None)
    meshes = [o for o in new if o.type == "MESH"]
    if not arm:
        return None, [], (1, 1)

    # Mixamo exports at centimetre scale — a 1.8m person arrives 180 units
    # tall. Normalise to metres so the lights, lens and set built here are
    # sized for a human rather than a skyscraper.
    h = max((o.dimensions.z for o in meshes), default=0)
    if h > 10:
        s = 1.0 / 100.0
        arm.scale = (s, s, s)
        bpy.context.view_layer.update()
        print(f"[Mixamo] scaled from {h:.0f} units to "
              f"{h * s:.2f}m")

    # sit the feet on the floor
    bpy.context.view_layer.update()
    lowest = min((o.matrix_world @ v.co).z
                 for o in meshes for v in o.data.vertices)
    arm.location.z -= lowest

    rng = (1, 100)
    if arm.animation_data and arm.animation_data.action:
        fr = arm.animation_data.action.frame_range
        rng = (int(fr[0]), int(fr[1]))
        print(f"[Mixamo] action '{arm.animation_data.action.name}' "
              f"{rng[0]}-{rng[1]}")
    return arm, meshes, rng


def build_world():
    scn = bpy.context.scene
    mats = {k: mat(k, v) for k, v in PALETTE.items()}

    world = bpy.data.worlds.new("sky")
    scn.world = world
    world.use_nodes = True
    nt = world.node_tree
    nt.nodes.clear()
    coord = nt.nodes.new("ShaderNodeTexCoord")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    bg = nt.nodes.new("ShaderNodeBackground")
    out = nt.nodes.new("ShaderNodeOutputWorld")
    ramp.color_ramp.elements[0].position = 0.30
    ramp.color_ramp.elements[0].color = (*PALETTE["sky_low"], 1)
    ramp.color_ramp.elements[1].position = 0.95
    ramp.color_ramp.elements[1].color = (*PALETTE["sky_top"], 1)
    ramp.color_ramp.elements.new(0.58).color = (*PALETTE["sky_mid"], 1)
    nt.links.new(coord.outputs["Window"], sep.inputs[0])
    nt.links.new(sep.outputs["Y"], ramp.inputs[0])
    nt.links.new(ramp.outputs["Color"], bg.inputs[0])
    nt.links.new(bg.outputs[0], out.inputs[0])

    bpy.ops.mesh.primitive_plane_add(size=200, location=(0, 0, 0))
    bpy.context.object.name = "ground"
    bpy.context.object.data.materials.append(mats["ground"])

    for i in range(16):
        y = -4 - i * 3.6
        h = 2.4 + (i % 3) * 0.6
        for x in (-3.4, 3.4):
            box(f"col{i}{x}", (0.5, 0.5, h), (x, y, h / 2), mats["set"])
            box(f"cap{i}{x}", (0.7, 0.7, 0.16), (x, y, h + 0.08), mats["set"])

    # Key light angled across the face. A character with eyes and a mouth is
    # worth lighting for - flat frontal light would throw away the one thing
    # this model has that the block figure did not.
    bpy.ops.object.light_add(type="SUN", location=(5, 6, 8))
    key = bpy.context.object
    key.data.energy = 4.0
    key.data.angle = 0.16
    key.data.color = PALETTE["sun"]
    key.rotation_euler = (math.radians(52), 0, math.radians(-34))

    bpy.ops.object.light_add(type="AREA", location=(-4, 3.5, 3))
    fill = bpy.context.object
    fill.data.energy = 260
    fill.data.size = 8
    fill.data.color = (0.58, 0.66, 0.98)

    # rim from behind, to lift the silhouette off the sky
    bpy.ops.object.light_add(type="AREA", location=(0, -5, 3.4))
    rim = bpy.context.object
    rim.data.energy = 320
    rim.data.size = 5
    rim.data.color = (1.0, 0.86, 0.72)
    rim.rotation_euler = (math.radians(-115), 0, 0)


def build_camera(arm, meshes, shot="medium"):
    """Frame the character for 9:16. Aim at the chest, never the origin."""
    top = max((o.matrix_world @ v.co).z for o in meshes for v in o.data.vertices)
    chest = top * 0.62

    # Aim at the HIPS BONE, not the armature object.
    #
    # In mocap the object origin never moves - the bones do. Parenting the aim
    # to the armature meant the camera stared at the spot where the character
    # started while he spun and staggered out of frame; the first render put
    # him half off the left edge. The hips bone is the closest thing a
    # skeleton has to a centre of mass, so tracking it keeps him framed
    # through any animation without knowing what the animation does.
    hips = next((b for b in arm.pose.bones
                 if b.name.lower().endswith("hips")), None)
    bpy.ops.object.empty_add(type="PLAIN_AXES", location=(0, 0, chest))
    aim = bpy.context.object
    aim.name = "aim"
    aim.parent = arm
    if hips:
        aim.parent_type = "BONE"
        aim.parent_bone = hips.name
        aim.location = (0, -0.15, 0)      # bone-space: back down toward pelvis
        print(f"[Mixamo] camera tracks bone '{hips.name}'")
    else:
        print("[Mixamo] no hips bone found — tracking the object origin")

    dist, height, lens = {
        "wide":   (6.2, 1.9, 40),
        "medium": (4.2, 1.5, 50),
        "close":  (2.4, 1.45, 72),
    }[shot]

    bpy.ops.object.camera_add(location=(dist * 0.55, dist, height))
    cam = bpy.context.object
    cam.data.lens = lens
    con = cam.constraints.new("TRACK_TO")
    con.target = aim
    con.track_axis = "TRACK_NEGATIVE_Z"
    con.up_axis = "UP_Y"
    bpy.context.scene.camera = cam
    print(f"[Mixamo] character {top:.2f}m tall, {shot} shot at {dist}m")
    return cam


def configure(out, rng):
    scn = bpy.context.scene
    scn.frame_start, scn.frame_end = rng
    scn.render.engine = "BLENDER_EEVEE_NEXT"
    scn.render.resolution_x = 1080
    scn.render.resolution_y = 1920
    scn.render.fps = 30
    scn.render.image_settings.file_format = "FFMPEG"
    scn.render.ffmpeg.format = "MPEG4"
    scn.render.ffmpeg.codec = "H264"
    scn.render.ffmpeg.constant_rate_factor = "HIGH"
    scn.render.filepath = out
    scn.eevee.taa_render_samples = 24
    try:
        scn.eevee.use_shadows = True
    except Exception:
        pass
    scn.view_settings.view_transform = "Standard"
    scn.view_settings.look = "None"


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--fbx", required=True)
    ap.add_argument("--out", default="//mixamo")
    ap.add_argument("--shot", default="medium",
                    choices=["wide", "medium", "close"])
    ap.add_argument("--still", type=int, default=0)
    a = ap.parse_args(argv)

    clear()
    bpy.context.scene.render.fps = 30
    build_world()
    arm, meshes, rng = import_character(a.fbx)
    if not arm:
        print("[Mixamo] no armature in that FBX")
        return
    build_camera(arm, meshes, a.shot)
    configure(a.out, rng)

    if a.still:
        bpy.context.scene.frame_set(a.still)
        bpy.context.scene.render.image_settings.file_format = "PNG"
        bpy.context.scene.render.filepath = a.out + f"_still_{a.still}"
        bpy.ops.render.render(write_still=True)
    else:
        bpy.ops.render.render(animation=True)
    print("[Mixamo] done ->", a.out)


if __name__ == "__main__":
    main()
