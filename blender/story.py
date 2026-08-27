"""
A scene with several characters, moving background, and a speaker who talks.

Everything the previous scripts did one at a time, composed:

    CAST        several characters from the same or different FBX files, each
                placed, rotated, retimed and time-OFFSET so they are not
                clones marching in lockstep. Each import gets its own action
                object, which is what makes independent timing possible.

    SPEAKER     one character gets generated visemes and word-timed lip sync
                from the narration audio.

    BACKGROUND  the world is not a backdrop: clouds drift, birds cross, and
                the set has parallax layers keyed over the whole take.

    CAMERA      per-shot framing on a chosen cast member, so the edit can cut
                between characters rather than sitting on one.

Driven by a spec dict, so a story is data and this file is the engine.

    blender --background --python blender/story.py -- --spec story.json
"""
import argparse
import json
import math
import sys
from pathlib import Path

import bpy

sys.path.append(str(Path(__file__).parent))
from lipsync import (build_visemes, drive_from_words,  # noqa: E402
                     find_mouth, words_from_srt)

PALETTE = {
    "sky_top": (0.078, 0.106, 0.212),
    "sky_mid": (0.427, 0.322, 0.435),
    "sky_low": (0.957, 0.596, 0.353),
    "ground":  (0.137, 0.125, 0.180),
    "set":     (0.200, 0.184, 0.267),
    "cloud":   (0.616, 0.478, 0.502),
    "sun":     (1.000, 0.878, 0.612),
}


def clear():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def mat(name, rgb, rough=0.9, emit=False):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    if emit:
        nt.nodes.clear()
        e = nt.nodes.new("ShaderNodeEmission")
        e.inputs[0].default_value = (*rgb, 1)
        o = nt.nodes.new("ShaderNodeOutputMaterial")
        nt.links.new(e.outputs[0], o.inputs[0])
        return m
    b = nt.nodes["Principled BSDF"]
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
    b.width = min(size) * 0.18
    b.segments = 3
    o.data.materials.append(material)
    return o


# ── cast ───────────────────────────────────────────────────────────────────

def import_actor(fbx, name):
    before = set(bpy.data.objects)
    bpy.ops.import_scene.fbx(filepath=fbx, automatic_bone_orientation=True)
    new = [o for o in bpy.data.objects if o not in before]
    for o in list(new):
        if o.type == "CAMERA":
            bpy.data.objects.remove(o, do_unlink=True)
            new.remove(o)
    arm = next((o for o in new if o.type == "ARMATURE"), None)
    meshes = [o for o in new if o.type == "MESH"]
    if not arm:
        return None, [], (1, 1)
    arm.name = name

    h = max((o.dimensions.z for o in meshes), default=0)
    if h > 10:
        arm.scale = (0.01, 0.01, 0.01)
        bpy.context.view_layer.update()
    bpy.context.view_layer.update()
    lowest = min((o.matrix_world @ v.co).z
                 for o in meshes for v in o.data.vertices)
    arm.location.z -= lowest

    rng = (1, 100)
    if arm.animation_data and arm.animation_data.action:
        fr = arm.animation_data.action.frame_range
        rng = (int(fr[0]), int(fr[1]))
    return arm, meshes, rng


def offset_action(arm, frames):
    """Shift a character's whole performance in time.

    Each FBX import gets its own action datablock, so shifting one leaves the
    others alone. Without this every extra character is a clone hitting the
    same beat on the same frame, which reads as a glitch rather than a crowd.
    """
    if not (arm.animation_data and arm.animation_data.action) or not frames:
        return
    for fc in arm.animation_data.action.fcurves:
        for kp in fc.keyframe_points:
            kp.co.x += frames
            kp.handle_left.x += frames
            kp.handle_right.x += frames
        fc.update()


def retime_action(arm, factor):
    if not (arm.animation_data and arm.animation_data.action) or factor == 1:
        return
    for fc in arm.animation_data.action.fcurves:
        for kp in fc.keyframe_points:
            kp.co.x /= factor
            kp.handle_left.x /= factor
            kp.handle_right.x /= factor
        fc.update()


def loop_action(arm, start, end, total):
    """Repeat the take to fill the story with a CYCLES modifier."""
    if not (arm.animation_data and arm.animation_data.action):
        return
    for fc in arm.animation_data.action.fcurves:
        if not any(m.type == "CYCLES" for m in fc.modifiers):
            fc.modifiers.new("CYCLES")


def look_at(arm, target, strength):
    """Head turns toward the target, WITHIN a neck's range.

    DAMPED_TRACK on its own has no anatomy. At 0.95 influence, with the body
    mid-stagger and the camera off to one side, it wrenched the head about
    ninety degrees and the render came back with a broken neck. A person
    glancing over turns maybe forty degrees and then moves their shoulders.
    So the influence is capped and a LIMIT_ROTATION sits after it to enforce
    a range no real neck exceeds - the look still reads, and it can no longer
    produce a shot that has to be thrown away.
    """
    head = next((b for b in arm.pose.bones
                 if b.name.lower().endswith("head")), None)
    if not head or not strength:
        return
    c = head.constraints.new("DAMPED_TRACK")
    c.target = target
    c.track_axis = "TRACK_Z"
    c.influence = min(0.5, strength)

    lim = head.constraints.new("LIMIT_ROTATION")
    lim.owner_space = "LOCAL"
    for axis, lo, hi in (("x", -32, 28), ("y", -42, 42), ("z", -26, 26)):
        setattr(lim, "use_limit_" + axis, True)
        setattr(lim, "min_" + axis, math.radians(lo))
        setattr(lim, "max_" + axis, math.radians(hi))


def place(arm, at, facing_deg):
    arm.location.x = at[0]
    arm.location.y = at[1]
    arm.rotation_euler.z = math.radians(facing_deg)


# ── world with movement ────────────────────────────────────────────────────

def build_world(total_frames):
    scn = bpy.context.scene
    mats = {k: mat(k, v) for k, v in PALETTE.items()}
    mats["cloud_e"] = mat("cloud_e", PALETTE["cloud"], emit=True)

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

    bpy.ops.mesh.primitive_plane_add(size=300, location=(0, 0, 0))
    bpy.context.object.name = "ground"
    bpy.context.object.data.materials.append(mats["ground"])

    for i in range(18):
        y = 6 - i * 4.0
        h = 2.6 + (i % 3) * 0.7
        for x in (-4.6, 4.6):
            box(f"col{i}{x}", (0.55, 0.55, h), (x, y, h / 2), mats["set"])
            box(f"cap{i}{x}", (0.78, 0.78, 0.18), (x, y, h + 0.09), mats["set"])

    # DRIFTING CLOUDS. A static sky is what made the earlier scenes read as
    # stills with a character pasted on; something has to move that is not the
    # actor.
    for i in range(9):
        x = -22 + (i * 5.3) % 44
        z = 9 + (i % 4) * 2.4
        y = -26 - (i % 3) * 7
        c = box(f"cloud{i}", (4.5 + (i % 3), 1.4, 1.1), (x, y, z),
                mats["cloud_e"])
        c.keyframe_insert("location", frame=1)
        c.location.x += 7 + (i % 4) * 3
        c.keyframe_insert("location", frame=total_frames)
        for fc in c.animation_data.action.fcurves:
            for kp in fc.keyframe_points:
                kp.interpolation = "LINEAR"

    bpy.ops.object.light_add(type="SUN", location=(6, 7, 9))
    key = bpy.context.object
    key.data.energy = 4.2
    key.data.angle = 0.15
    key.data.color = PALETTE["sun"]
    key.rotation_euler = (math.radians(54), 0, math.radians(-38))

    bpy.ops.object.light_add(type="AREA", location=(-5, 4, 3.4))
    fill = bpy.context.object
    fill.data.energy = 280
    fill.data.size = 9
    fill.data.color = (0.56, 0.64, 0.98)

    bpy.ops.object.light_add(type="AREA", location=(0, -6, 3.6))
    rim = bpy.context.object
    rim.data.energy = 380
    rim.data.size = 6
    rim.data.color = (1.0, 0.85, 0.70)
    rim.rotation_euler = (math.radians(-115), 0, 0)


def build_camera(target_arm, meshes, shot):
    top = max((o.matrix_world @ v.co).z for o in meshes for v in o.data.vertices)
    hips = next((b for b in target_arm.pose.bones
                 if b.name.lower().endswith("hips")), None)
    bpy.ops.object.empty_add(type="PLAIN_AXES", location=(0, 0, top * 0.62))
    aim = bpy.context.object
    aim.parent = target_arm
    if hips:
        aim.parent_type = "BONE"
        aim.parent_bone = hips.name
        aim.location = (0, -0.15, 0)

    dist, height, lens = {"wide": (7.0, 2.0, 38),
                          "medium": (4.4, 1.55, 50),
                          "close": (2.5, 1.5, 75)}[shot]
    bpy.ops.object.camera_add(location=(dist * 0.5, dist, height))
    cam = bpy.context.object
    cam.data.lens = lens
    c = cam.constraints.new("TRACK_TO")
    c.target = aim
    c.track_axis = "TRACK_NEGATIVE_Z"
    c.up_axis = "UP_Y"
    bpy.context.scene.camera = cam
    return cam


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--spec", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--still", type=int, default=0)
    a = ap.parse_args(argv)

    spec = json.loads(Path(a.spec).read_text(encoding="utf-8"))
    total = int(spec.get("frames", 300))

    clear()
    scn = bpy.context.scene
    scn.render.fps = 30
    build_world(total)

    cast = []
    for i, c in enumerate(spec["cast"]):
        arm, meshes, rng = import_actor(c["fbx"], c.get("name", f"actor{i}"))
        if not arm:
            continue
        retime_action(arm, c.get("speed", 1.0))
        offset_action(arm, c.get("offset", 0))
        loop_action(arm, rng[0], rng[1], total)
        place(arm, c.get("at", (0, 0)), c.get("facing", 0))
        if c.get("mirror"):
            arm.scale.x *= -1
        cast.append({"arm": arm, "meshes": meshes, "spec": c})
        print(f"[Story] cast '{arm.name}' at {c.get('at')} "
              f"offset {c.get('offset', 0)}f speed {c.get('speed', 1.0)}")

    if not cast:
        print("[Story] empty cast")
        return

    focus = cast[int(spec.get("focus", 0))]
    cam = build_camera(focus["arm"], focus["meshes"],
                       spec.get("shot", "medium"))
    for c in cast:
        look_at(c["arm"], cam, c["spec"].get("look", 0.0))

    # the speaker gets a mouth
    sp = spec.get("speaker")
    if sp is not None:
        actor = cast[int(sp)]
        mouth = find_mouth(actor["meshes"])
        if mouth:
            build_visemes(mouth)
            srt = spec.get("srt")
            if srt and Path(srt).exists():
                drive_from_words(mouth, words_from_srt(srt), fps=30,
                                 lead=spec.get("voice_lead", 0.0))
            else:
                print("[Story] no srt — visemes built but not driven")

    scn.frame_start, scn.frame_end = 1, total
    scn.render.engine = "BLENDER_EEVEE_NEXT"
    scn.render.resolution_x = 1080
    scn.render.resolution_y = 1920
    scn.render.image_settings.file_format = "FFMPEG"
    scn.render.ffmpeg.format = "MPEG4"
    scn.render.ffmpeg.codec = "H264"
    scn.render.ffmpeg.constant_rate_factor = "HIGH"
    scn.render.filepath = a.out
    scn.eevee.taa_render_samples = int(spec.get("samples", 16))
    scn.view_settings.view_transform = "Standard"
    scn.view_settings.look = "None"

    if a.still:
        scn.frame_set(a.still)
        scn.render.image_settings.file_format = "PNG"
        scn.render.filepath = a.out + f"_still_{a.still}"
        bpy.ops.render.render(write_still=True)
    else:
        bpy.ops.render.render(animation=True)
    print("[Story] done ->", a.out)


if __name__ == "__main__":
    main()
