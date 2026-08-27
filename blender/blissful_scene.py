"""
BLISSFUL MOMENTS — a scripted cartoon scene. No GUI, no hand-modelling.

Run headless:
    blender --background --python blender/blissful_scene.py -- --out output/x --frames 480

Why this shape rather than Grease Pencil. Grease Pencil is the "real" 2D
answer and it is what a human animator should use - but a stroke is point
data, and scripting appealing hand-drawn strokes is the one thing that does
NOT automate well. Flat-shaded geometry with emission materials gives the same
storybook look, is fully parametric, and renders in EEVEE in seconds. The
character is built from primitives, so every property - palette, pose, sun
height, hill count - is a number this script can vary per episode.

Everything is emission-shaded: no lights, no shadows, no denoising. That is a
deliberate look (flat cut-paper storybook) and it is also why a 16-second
render finishes in the time a lit scene would spend on one frame.
"""
import argparse
import math
import sys

import bpy


# ── palette ────────────────────────────────────────────────────────────────
# Dusk over the Highveld: warm sky falling to deep indigo, hills receding into
# haze. Named so an episode can be re-keyed by swapping one dict.
PALETTE = {
    "sky_top": (0.129, 0.157, 0.310),
    "sky_mid": (0.639, 0.357, 0.376),
    "sky_low": (0.949, 0.596, 0.373),
    "sun": (1.000, 0.855, 0.545),
    "hill_far": (0.310, 0.286, 0.435),
    "hill_mid": (0.204, 0.204, 0.345),
    "hill_near": (0.110, 0.125, 0.235),
    "figure": (0.055, 0.063, 0.129),
    "bird": (0.086, 0.094, 0.176),
}


def clear():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def flat(name, rgb, strength=1.0):
    """An emission material. Flat colour, no lighting maths, no noise."""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs[0].default_value = (*rgb, 1.0)
    em.inputs[1].default_value = strength
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    nt.links.new(em.outputs[0], out.inputs[0])
    return m


def plane(name, w, h, loc, mat):
    bpy.ops.mesh.primitive_plane_add(size=1, location=loc)
    o = bpy.context.object
    o.name = name
    o.scale = (w, 1, h)
    o.rotation_euler = (math.radians(90), 0, 0)
    o.data.materials.append(mat)
    return o


def hill(name, width, height, y, wobble, mat, segments=48):
    """A rolling ridge: a filled profile built from a sine sum, not a mesh
    anyone had to model. Different wobble seeds give different skylines."""
    verts, faces = [], []
    base = -height
    for i in range(segments + 1):
        u = i / segments
        x = (u - 0.5) * width
        y_top = (height * 0.5
                 + math.sin(u * math.pi * 2 * wobble[0] + wobble[1]) * height * 0.16
                 + math.sin(u * math.pi * 5 * wobble[0] + wobble[2]) * height * 0.07)
        verts.append((x, 0, base))
        verts.append((x, 0, y_top))
    for i in range(segments):
        a = i * 2
        faces.append((a, a + 2, a + 3, a + 1))
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    me.update()
    o = bpy.data.objects.new(name, me)
    bpy.context.collection.objects.link(o)
    o.location = (0, y, 0)
    o.data.materials.append(mat)
    return o


def figure(y, mat):
    """A seated silhouette — head, body, knees. Read as a person, not a blob.

    Kept as a silhouette on purpose: no face to fall into the uncanny valley,
    no expression to animate wrong, and it reads at thumbnail size.
    """
    parts = []
    bpy.ops.mesh.primitive_circle_add(vertices=32, radius=0.19, fill_type="NGON",
                                      location=(0, y, 0.62))
    parts.append(bpy.context.object)

    bpy.ops.mesh.primitive_circle_add(vertices=32, radius=0.30, fill_type="NGON",
                                      location=(0, y, 0.22))
    body = bpy.context.object
    body.scale = (0.85, 1, 1.25)
    parts.append(body)

    bpy.ops.mesh.primitive_circle_add(vertices=32, radius=0.22, fill_type="NGON",
                                      location=(0.24, y, 0.02))
    knee = bpy.context.object
    knee.scale = (1.25, 1, 0.8)
    parts.append(knee)

    for p in parts:
        p.rotation_euler = (math.radians(90), 0, 0)
        p.data.materials.append(mat)

    bpy.ops.object.select_all(action="DESELECT")
    for p in parts:
        p.select_set(True)
    bpy.context.view_layer.objects.active = parts[0]
    bpy.ops.object.join()
    o = bpy.context.object
    o.name = "figure"
    return o


def bird(x, z, y, scale, mat):
    """Two strokes making a gull shape. Enough at this size."""
    verts = [(-1, 0, 0), (-0.45, 0, 0.34), (0, 0, 0.06),
             (0.45, 0, 0.34), (1, 0, 0), (0, 0, -0.10)]
    faces = [(0, 1, 2, 5), (2, 3, 4, 5)]
    me = bpy.data.meshes.new("bird")
    me.from_pydata(verts, [], faces)
    me.update()
    o = bpy.data.objects.new("bird", me)
    bpy.context.collection.objects.link(o)
    o.location = (x, y, z)
    o.scale = (scale, scale, scale)
    o.data.materials.append(mat)
    return o


def build(frames, seed=0):
    clear()
    scn = bpy.context.scene

    mats = {k: flat(k, v) for k, v in PALETTE.items()}

    # Sky: the WORLD, not an object.
    #
    # Two failed attempts taught this. First: three stacked coloured planes,
    # which left hard black seams wherever the edges did not meet to the
    # pixel. Second: one big plane with a gradient, which still left black
    # everywhere the plane did not reach - a backdrop has to be sized and
    # placed to cover a frustum, and any error shows as void.
    #
    # The world shader has no edges to get wrong. Window coordinates give a
    # 0-1 vertical ramp across the rendered frame, so the gradient is exact at
    # any resolution and nothing can leak through behind it.
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
    ramp.color_ramp.elements[1].position = 0.92
    ramp.color_ramp.elements[1].color = (*PALETTE["sky_top"], 1)
    mid = ramp.color_ramp.elements.new(0.55)
    mid.color = (*PALETTE["sky_mid"], 1)
    nt.links.new(coord.outputs["Window"], sep.inputs[0])
    nt.links.new(sep.outputs["Y"], ramp.inputs[0])
    nt.links.new(ramp.outputs["Color"], bg.inputs[0])
    nt.links.new(bg.outputs[0], out.inputs[0])

    # sun — rises across the shot
    bpy.ops.mesh.primitive_circle_add(vertices=64, radius=1.05, fill_type="NGON",
                                      location=(-2.2, 12.8, -0.3))
    sun = bpy.context.object
    sun.name = "sun"
    sun.rotation_euler = (math.radians(90), 0, 0)
    sun.data.materials.append(mats["sun"])

    # ridges, back to front
    h1 = hill("hill_far", 26, 3.4, 10.0, (1.0, 0.4 + seed, 1.1), mats["hill_far"])
    h1.location.z = -1.1
    h2 = hill("hill_mid", 24, 3.0, 7.0, (1.4, 2.1 + seed, 0.3), mats["hill_mid"])
    h2.location.z = -1.9
    h3 = hill("hill_near", 22, 2.8, 4.0, (0.8, 3.7 + seed, 2.2), mats["hill_near"])
    h3.location.z = -2.6

    fig = figure(4.6, mats["figure"])
    fig.location.z = -0.62

    birds = [bird(-3.4 + i * 1.5, 2.4 + (i % 3) * 0.5, 8.5, 0.16 + (i % 2) * 0.05,
                  mats["bird"]) for i in range(5)]

    # ── animation ─────────────────────────────────────────────────────────
    # Everything is keyed, nothing is simulated: a render is reproducible and
    # a re-render of frame 200 is identical every time.
    scn.frame_start, scn.frame_end = 1, frames

    sun.location.z = -0.3
    sun.keyframe_insert("location", frame=1)
    sun.location.z = 1.15
    sun.keyframe_insert("location", frame=frames)

    # the figure breathes — the only thing that says "alive"
    for f in range(1, frames + 1, 12):
        t = f / scn.render.fps
        fig.scale = (1.0, 1.0, 1.0 + 0.012 * math.sin(t * 1.5))
        fig.keyframe_insert("scale", frame=f)

    for i, b in enumerate(birds):
        x0 = b.location.x
        b.keyframe_insert("location", frame=1)
        b.location.x = x0 + 3.2 + i * 0.4
        b.location.z += 0.55
        b.keyframe_insert("location", frame=frames)

    # camera: a slow push, so a still frame is never the whole shot
    bpy.ops.object.camera_add(location=(0, -6.2, 0.35),
                              rotation=(math.radians(90), 0, 0))
    cam = bpy.context.object
    cam.data.lens = 52
    cam.keyframe_insert("location", frame=1)
    cam.location = (0, -5.4, 0.5)
    cam.keyframe_insert("location", frame=frames)
    scn.camera = cam

    for fc in bpy.data.actions:
        for c in fc.fcurves:
            for kp in c.keyframe_points:
                kp.interpolation = "BEZIER"
                kp.easing = "EASE_IN_OUT"


def configure(out_dir, frames):
    scn = bpy.context.scene
    scn.render.engine = "BLENDER_EEVEE_NEXT"
    scn.render.resolution_x = 1080
    scn.render.resolution_y = 1920
    scn.render.resolution_percentage = 100
    scn.render.fps = 30
    scn.render.image_settings.file_format = "FFMPEG"
    scn.render.ffmpeg.format = "MPEG4"
    scn.render.ffmpeg.codec = "H264"
    scn.render.ffmpeg.constant_rate_factor = "HIGH"
    scn.render.filepath = out_dir
    scn.eevee.taa_render_samples = 8       # flat colour needs almost no AA
    try:
        scn.eevee.use_raytracing = False
    except Exception:
        pass
    scn.view_settings.view_transform = "Standard"   # keep the palette exact


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="//blissful")
    ap.add_argument("--frames", type=int, default=480)
    ap.add_argument("--seed", type=float, default=0.0)
    ap.add_argument("--still", type=int, default=0)
    a = ap.parse_args(argv)

    build(a.frames, seed=a.seed)
    configure(a.out, a.frames)
    if a.still:
        bpy.context.scene.frame_set(a.still)
        bpy.context.scene.render.image_settings.file_format = "PNG"
        bpy.context.scene.render.filepath = a.out + f"_still_{a.still}"
        bpy.ops.render.render(write_still=True)
    else:
        bpy.ops.render.render(animation=True)
    print("[Blissful] done ->", a.out)


if __name__ == "__main__":
    main()
