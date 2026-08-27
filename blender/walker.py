"""
A rigged character walking, in 3D. Built entirely from script, no GUI.

The first attempt at this channel was a seated silhouette that breathed, and
the owner was right to reject it - that is a still frame with a wobble, not
animation. What the reference videos show is ARTICULATION: limbs that swing
from joints, a body that rises and falls on the step, a world with depth the
camera moves through.

So this builds a real rig:

    root -> hips -> spine -> chest -> head
                 -> thigh.L/R -> shin.L/R -> foot.L/R
            chest -> upper_arm.L/R -> forearm.L/R

and drives it with a procedural walk cycle rather than hand-keyed poses.
Every joint is a phase-shifted sine, which is how a walk actually decomposes:

    thigh    swings +-26 deg, left and right exactly half a cycle apart
    shin     bends only on the back half of its leg's swing - a knee cannot
             bend forwards, and ignoring that is what makes bad walk cycles
             look like skating
    arms     opposite phase to the leg on the same side, which is what
             counter-rotation does in a real gait
    hips     rise twice per cycle, peaking mid-stance, not mid-step
    chest    counter-rotates against the hips

Body parts are separate meshes parented to bones (parent_type='BONE'), which
skips weight painting entirely - a deliberate trade: a jointed-puppet look
that is 100% scriptable, instead of smooth skinning that is not.

    blender --background --python blender/walker.py -- --out X --frames 300
"""
import argparse
import math
import sys

import bpy
from mathutils import Vector

PALETTE = {
    "sky_top":   (0.086, 0.129, 0.243),
    "sky_mid":   (0.478, 0.353, 0.451),
    "sky_low":   (0.965, 0.612, 0.353),
    "ground":    (0.129, 0.118, 0.176),
    "ground_2":  (0.169, 0.153, 0.216),
    "skin":      (0.847, 0.588, 0.427),
    "shirt":     (0.910, 0.376, 0.310),
    "trouser":   (0.204, 0.243, 0.373),
    "shoe":      (0.110, 0.118, 0.157),
    "hair":      (0.129, 0.106, 0.106),
    "far":       (0.216, 0.196, 0.286),
    "sun":       (1.000, 0.878, 0.612),
}

CYCLE = 28          # frames per full stride — 0.93s at 30fps, a natural pace


# ── helpers ────────────────────────────────────────────────────────────────

def clear():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def mat(name, rgb, rough=0.85):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*rgb, 1)
    b.inputs["Roughness"].default_value = rough
    return m


def box(name, size, loc, material, rot=(0, 0, 0)):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc)
    o = bpy.context.object
    o.name = name
    o.scale = size
    o.rotation_euler = rot
    bpy.ops.object.shade_smooth()
    for m in o.modifiers:
        o.modifiers.remove(m)
    b = o.modifiers.new("bevel", "BEVEL")
    b.width = min(size) * 0.22
    b.segments = 3
    o.data.materials.append(material)
    return o


def sphere(name, r, loc, material, scale=(1, 1, 1)):
    bpy.ops.mesh.primitive_uv_sphere_add(radius=r, segments=24, ring_count=16,
                                         location=loc)
    o = bpy.context.object
    o.name = name
    o.scale = scale
    bpy.ops.object.shade_smooth()
    o.data.materials.append(material)
    return o


# ── the rig ────────────────────────────────────────────────────────────────

BONES = [
    # name,          head,             tail,             parent
    ("root",        (0, 0, 0.00),     (0, 0, 0.08),     None),
    ("hips",        (0, 0, 0.92),     (0, 0, 1.10),     "root"),
    ("spine",       (0, 0, 1.10),     (0, 0, 1.34),     "hips"),
    ("chest",       (0, 0, 1.34),     (0, 0, 1.58),     "spine"),
    ("head",        (0, 0, 1.58),     (0, 0, 1.86),     "chest"),
    ("thigh.L",     (0.11, 0, 0.90),  (0.11, 0, 0.50),  "hips"),
    ("shin.L",      (0.11, 0, 0.50),  (0.11, 0, 0.10),  "thigh.L"),
    ("foot.L",      (0.11, 0, 0.10),  (0.11, -0.16, 0.06), "shin.L"),
    ("thigh.R",     (-0.11, 0, 0.90), (-0.11, 0, 0.50), "hips"),
    ("shin.R",      (-0.11, 0, 0.50), (-0.11, 0, 0.10), "thigh.R"),
    ("foot.R",      (-0.11, 0, 0.10), (-0.11, -0.16, 0.06), "shin.R"),
    ("upper_arm.L", (0.22, 0, 1.54),  (0.22, 0, 1.24),  "chest"),
    ("forearm.L",   (0.22, 0, 1.24),  (0.22, 0, 0.96),  "upper_arm.L"),
    ("upper_arm.R", (-0.22, 0, 1.54), (-0.22, 0, 1.24), "chest"),
    ("forearm.R",   (-0.22, 0, 1.24), (-0.22, 0, 0.96), "upper_arm.R"),
]


def build_rig():
    bpy.ops.object.armature_add(enter_editmode=True, location=(0, 0, 0))
    arm = bpy.context.object
    arm.name = "rig"
    eb = arm.data.edit_bones
    for b in list(eb):
        eb.remove(b)
    made = {}
    for name, head, tail, parent in BONES:
        b = eb.new(name)
        b.head = Vector(head)
        b.tail = Vector(tail)
        b.use_deform = False
        if parent:
            b.parent = made[parent]
            b.use_connect = False
        made[name] = b
    bpy.ops.object.mode_set(mode="OBJECT")
    return arm


def attach(obj, arm, bone_name):
    """Parent a mesh to a single bone — no weights, no skinning."""
    obj.parent = arm
    obj.parent_type = "BONE"
    obj.parent_bone = bone_name
    # Blender parents to the bone TAIL; offset back so the part sits on the
    # bone rather than beyond its end.
    bl = arm.data.bones[bone_name].length
    obj.matrix_parent_inverse = arm.matrix_world.inverted()
    obj.location.y -= bl


def build_body(arm):
    mats = {k: mat(k, v) for k, v in PALETTE.items()}

    parts = [
        # (bone,          maker,  args)
        ("head",        sphere, ("head", 0.17, (0, 0, 1.72), mats["skin"],
                                 (1.0, 0.92, 1.06))),
        ("chest",       box,    ("torso", (0.42, 0.24, 0.34), (0, 0, 1.44),
                                 mats["shirt"])),
        ("spine",       box,    ("belly", (0.36, 0.22, 0.24), (0, 0, 1.20),
                                 mats["shirt"])),
        ("hips",        box,    ("pelvis", (0.38, 0.24, 0.20), (0, 0, 1.00),
                                 mats["trouser"])),
        ("thigh.L",     box,    ("thighL", (0.16, 0.17, 0.42), (0.11, 0, 0.70),
                                 mats["trouser"])),
        ("shin.L",      box,    ("shinL", (0.13, 0.14, 0.40), (0.11, 0, 0.30),
                                 mats["trouser"])),
        ("foot.L",      box,    ("footL", (0.14, 0.28, 0.10), (0.11, -0.06, 0.06),
                                 mats["shoe"])),
        ("thigh.R",     box,    ("thighR", (0.16, 0.17, 0.42), (-0.11, 0, 0.70),
                                 mats["trouser"])),
        ("shin.R",      box,    ("shinR", (0.13, 0.14, 0.40), (-0.11, 0, 0.30),
                                 mats["trouser"])),
        ("foot.R",      box,    ("footR", (0.14, 0.28, 0.10), (-0.11, -0.06, 0.06),
                                 mats["shoe"])),
        ("upper_arm.L", box,    ("uarmL", (0.13, 0.13, 0.32), (0.22, 0, 1.39),
                                 mats["shirt"])),
        ("forearm.L",   box,    ("farmL", (0.11, 0.11, 0.30), (0.22, 0, 1.10),
                                 mats["skin"])),
        ("upper_arm.R", box,    ("uarmR", (0.13, 0.13, 0.32), (-0.22, 0, 1.39),
                                 mats["shirt"])),
        ("forearm.R",   box,    ("farmR", (0.11, 0.11, 0.30), (-0.22, 0, 1.10),
                                 mats["skin"])),
    ]
    made = []
    for bone, maker, args in parts:
        o = maker(*args)
        made.append((o, bone))

    # hair as a skull cap, so the head is not a bare ball
    hair = sphere("hair", 0.175, (0, -0.01, 1.76), mats["hair"],
                  (1.0, 0.95, 0.72))
    made.append((hair, "head"))

    # Parent AFTER all parts exist: bone-parenting bakes the current world
    # matrix, so a part moved afterwards would drift off its joint.
    for o, bone in made:
        world = o.matrix_world.copy()
        o.parent = arm
        o.parent_type = "BONE"
        o.parent_bone = bone
        o.matrix_world = world
    return made


# ── the walk ───────────────────────────────────────────────────────────────

def walk(arm, frames, speed=1.6):
    """Key every joint from phase-shifted sines. A gait, not a pose library."""
    scn = bpy.context.scene
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.mode_set(mode="POSE")
    pb = arm.pose.bones
    for b in pb:
        b.rotation_mode = "XYZ"

    def ph(f, offset=0.0):
        return (f / CYCLE + offset) * math.tau

    for f in range(1, frames + 1):
        a = ph(f)

        for side, off in (("L", 0.0), ("R", 0.5)):
            p = ph(f, off)
            swing = math.sin(p)

            # thigh drives the stride
            pb[f"thigh.{side}"].rotation_euler = (swing * 0.46, 0, 0)

            # A knee only bends one way. Taking max(0, ...) of the back half
            # of the swing gives a bend that appears as the foot leaves the
            # ground and vanishes as the leg straightens to plant - without
            # this the legs pass through each other and the walk reads as a
            # skate.
            bend = max(0.0, -math.sin(p - 0.6)) ** 1.4
            pb[f"shin.{side}"].rotation_euler = (-bend * 1.15, 0, 0)

            # ankle keeps the foot roughly level with the ground
            pb[f"foot.{side}"].rotation_euler = (
                (-swing * 0.30 + bend * 0.55), 0, 0)

            # arms swing against the leg on the SAME side
            arm_p = ph(f, off + 0.5)
            pb[f"upper_arm.{side}"].rotation_euler = (
                math.sin(arm_p) * 0.42, 0, 0)
            pb[f"forearm.{side}"].rotation_euler = (
                -0.25 - max(0.0, math.sin(arm_p)) * 0.35, 0, 0)

        # hips rise TWICE per stride, peaking mid-stance
        pb["hips"].location = (0, 0, abs(math.sin(a)) * 0.055 - 0.02)
        pb["hips"].rotation_euler = (0, math.sin(a) * 0.06, math.sin(a) * 0.10)
        # chest counter-rotates against the hips
        pb["chest"].rotation_euler = (0.04, -math.sin(a) * 0.09,
                                      -math.sin(a) * 0.12)
        pb["spine"].rotation_euler = (0.03, 0, -math.sin(a) * 0.05)
        # head stays level and looks ahead — it should not bob with the body
        pb["head"].rotation_euler = (-0.06, math.sin(a) * 0.04, 0)

        for name in ("hips", "chest", "spine", "head",
                     "thigh.L", "shin.L", "foot.L",
                     "thigh.R", "shin.R", "foot.R",
                     "upper_arm.L", "forearm.L", "upper_arm.R", "forearm.R"):
            pb[name].keyframe_insert("rotation_euler", frame=f)
        pb["hips"].keyframe_insert("location", frame=f)

    bpy.ops.object.mode_set(mode="OBJECT")

    # the whole rig travels forward — the walk is on the spot without this
    arm.location = (0, 0, 0)
    arm.keyframe_insert("location", frame=1)
    # He travels the way he FACES. The foot bones extend to -Y, so -Y is his
    # front - and the rig was being driven to +Y, which is why a camera placed
    # ahead of him kept looking at his back. He was walking backwards.
    arm.location = (0, -speed * frames / scn.render.fps, 0)
    arm.keyframe_insert("location", frame=frames)
    for c in arm.animation_data.action.fcurves:
        if c.data_path == "location":
            for kp in c.keyframe_points:
                kp.interpolation = "LINEAR"


# ── the world ──────────────────────────────────────────────────────────────

def build_world(frames, speed):
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
    ramp.color_ramp.elements[0].position = 0.28
    ramp.color_ramp.elements[0].color = (*PALETTE["sky_low"], 1)
    ramp.color_ramp.elements[1].position = 0.95
    ramp.color_ramp.elements[1].color = (*PALETTE["sky_top"], 1)
    ramp.color_ramp.elements.new(0.55).color = (*PALETTE["sky_mid"], 1)
    nt.links.new(coord.outputs["Window"], sep.inputs[0])
    nt.links.new(sep.outputs["Y"], ramp.inputs[0])
    nt.links.new(ramp.outputs["Color"], bg.inputs[0])
    nt.links.new(bg.outputs[0], out.inputs[0])

    bpy.ops.mesh.primitive_plane_add(size=400, location=(0, 60, 0))
    ground = bpy.context.object
    ground.name = "ground"
    ground.data.materials.append(mats["ground"])

    # A colonnade the character walks past. Depth is what sells 3D, and
    # nothing reads as depth like objects passing the camera at different
    # rates.
    travel = speed * frames / 30
    for i in range(26):
        y = 6 - i * 3.4
        h = 2.6 + (i % 3) * 0.55
        for x in (-3.1, 3.1):
            box(f"col_{i}_{x}", (0.5, 0.5, h), (x, y, h / 2), mats["ground_2"])
            # A capital ON the column, not a block hovering between them. The
            # first pass put a cube at (0, y, h) - centred in the gap with
            # nothing under it - and the render came back with slabs floating
            # in the sky.
            box(f"cap_{i}_{x}", (0.68, 0.68, 0.16), (x, y, h + 0.08),
                mats["far"])

    for i in range(14):
        box(f"far_{i}", (2.2, 2.2, 3 + (i % 4)), (-14 + (i % 7) * 4.4,
            -10 - i * 6, (3 + (i % 4)) / 2), mats["far"])

    bpy.ops.object.light_add(type="SUN", location=(6, -8, 9))
    sun = bpy.context.object
    sun.data.energy = 3.4
    sun.data.angle = 0.24
    sun.data.color = PALETTE["sun"]
    sun.rotation_euler = (math.radians(58), 0, math.radians(38))

    bpy.ops.object.light_add(type="AREA", location=(-5, -4, 4))
    fill = bpy.context.object
    fill.data.energy = 220
    fill.data.size = 9
    fill.data.color = (0.55, 0.62, 0.95)

    return travel


def build_camera(arm, frames, travel):
    """A tracking dolly that keeps the whole figure in a 9:16 frame.

    Two faults in the first version, both visible in the test render:
    the camera sat 3.4m away on a 40mm lens, which cropped the head off; and
    TRACK_TO aimed at the armature ORIGIN, which is between the feet, so the
    shot pointed at the legs. The aim target is now an empty at chest height,
    parented to the rig so it travels with the walk, and the camera sits far
    enough back that a 1.9m figure fits a tall frame with air above the head.
    """
    bpy.ops.object.empty_add(type="PLAIN_AXES", location=(0, 0, 1.25))
    aim = bpy.context.object
    aim.name = "cam_target"
    aim.parent = arm

    # PARENT the camera to the rig instead of keyframing a world path.
    #
    # The keyframed version had to guess where the character would be on every
    # frame, and got it wrong twice: it framed the legs, then on the second
    # attempt it dollied to x=4.6 while the colonnade stands at x=3.1 and
    # spent the shot inside a pillar. A parented camera holds its offset by
    # construction - it cannot fall behind the walk and it cannot wander into
    # the set, because it moves in the character's space, not the world's.
    bpy.ops.object.camera_add(location=(0, 0, 0))
    cam = bpy.context.object
    cam.data.lens = 50
    cam.parent = arm
    con = cam.constraints.new("TRACK_TO")
    con.target = aim
    con.track_axis = "TRACK_NEGATIVE_Z"
    con.up_axis = "UP_Y"

    # offsets are in the rig's space: +X right of him, -Y behind, +Z above.
    # x stays inside the 3.1m colonnade, so the lens never clips a pillar.
    # AHEAD of him and to one side. Behind the character we were watching a
    # shirt: the arms, the knee bend and the head are all on the front, and
    # a walk cycle only reads if you can see the leading leg swing through.
    cam.location = (2.1, -5.2, 1.72)
    cam.keyframe_insert("location", frame=1)
    cam.location = (1.15, -4.4, 1.48)
    cam.keyframe_insert("location", frame=frames)
    for c in cam.animation_data.action.fcurves:
        for kp in c.keyframe_points:
            kp.interpolation = "BEZIER"
            kp.easing = "EASE_IN_OUT"
    bpy.context.scene.camera = cam
    return cam


def configure(out, frames):
    scn = bpy.context.scene
    scn.frame_start, scn.frame_end = 1, frames
    scn.render.engine = "BLENDER_EEVEE_NEXT"
    scn.render.resolution_x = 1080
    scn.render.resolution_y = 1920
    scn.render.fps = 30
    scn.render.image_settings.file_format = "FFMPEG"
    scn.render.ffmpeg.format = "MPEG4"
    scn.render.ffmpeg.codec = "H264"
    scn.render.ffmpeg.constant_rate_factor = "HIGH"
    scn.render.filepath = out
    scn.eevee.taa_render_samples = 16
    try:
        scn.eevee.use_shadows = True
    except Exception:
        pass
    # Keep the palette. Blender's default AgX view transform is built to tame
    # photographic highlights, and on flat stylised colour it just desaturates
    # everything - the test render came back with a red shirt reading as pale
    # pink and the whole frame washed grey. Standard shows the colours that
    # were actually chosen.
    scn.view_settings.view_transform = "Standard"
    scn.view_settings.look = "None"


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="//walker")
    ap.add_argument("--frames", type=int, default=300)
    ap.add_argument("--speed", type=float, default=1.6)
    ap.add_argument("--still", type=int, default=0)
    a = ap.parse_args(argv)

    clear()
    bpy.context.scene.render.fps = 30
    travel = build_world(a.frames, a.speed)
    arm = build_rig()
    build_body(arm)
    walk(arm, a.frames, a.speed)
    build_camera(arm, a.frames, travel)
    configure(a.out, a.frames)

    if a.still:
        bpy.context.scene.frame_set(a.still)
        bpy.context.scene.render.image_settings.file_format = "PNG"
        bpy.context.scene.render.filepath = a.out + f"_still_{a.still}"
        bpy.ops.render.render(write_still=True)
    else:
        bpy.ops.render.render(animation=True)
    print("[Walker] done ->", a.out)


if __name__ == "__main__":
    main()
