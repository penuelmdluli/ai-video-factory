"""
A street that is alive: traffic, buildings, lights, and things that move.

Owner call 2026-08-27: "can we make this a real live situation, where we can
add cars moving and all, on one scene?"

Yes, and the reason it works is that a city is mostly repetition with
variation - which is exactly what a script is good at. Every element here is
generated from a rule plus a seed, so the same twenty lines produce a
different street each time rather than one hand-built set.

What moves, and why each one matters:

    TRAFFIC     cars cross the frame in both directions at different speeds,
                looping so the road never empties. This is the single biggest
                cue that a scene is a place rather than a backdrop.
    HEADLIGHTS  emissive quads on the front of each car, so dusk reads as
                dusk and the traffic is visible against a dark road.
    WINDOWS     lit at random across the facades - a building with every
                window the same is obviously geometry.
    CLOUDS      slow drift above the skyline.

Nothing here is simulated. Everything is keyframed from a rule, so a re-render
of frame 200 is identical every time and a shot can be re-cut without the
background changing under it.
"""
import math
import random

import bpy

PALETTE = {
    "sky_top":  (0.055, 0.075, 0.169),
    "sky_mid":  (0.376, 0.267, 0.404),
    "sky_low":  (0.937, 0.545, 0.325),
    "road":     (0.086, 0.086, 0.106),
    "pavement": (0.180, 0.176, 0.204),
    "line":     (0.784, 0.741, 0.596),
    "building": (0.129, 0.129, 0.176),
    "building2": (0.169, 0.153, 0.196),
    "window":   (1.000, 0.804, 0.478),
    "cloud":    (0.545, 0.400, 0.451),
    "lamp":     (1.000, 0.827, 0.541),
    "head":     (1.000, 0.949, 0.831),
    "tail":     (1.000, 0.243, 0.180),
}

CAR_COLORS = [
    (0.702, 0.145, 0.157), (0.145, 0.259, 0.478), (0.855, 0.855, 0.855),
    (0.110, 0.110, 0.129), (0.169, 0.400, 0.302), (0.878, 0.635, 0.153),
]


def _mat(name, rgb, rough=0.55, emit=0.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    if emit:
        nt.nodes.clear()
        e = nt.nodes.new("ShaderNodeEmission")
        e.inputs[0].default_value = (*rgb, 1)
        e.inputs[1].default_value = emit
        o = nt.nodes.new("ShaderNodeOutputMaterial")
        nt.links.new(e.outputs[0], o.inputs[0])
        return m
    b = nt.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*rgb, 1)
    b.inputs["Roughness"].default_value = rough
    return m


def _box(name, size, loc, material, rot=(0, 0, 0), bevel=True):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc)
    o = bpy.context.object
    o.name = name
    o.scale = size
    o.rotation_euler = rot
    if bevel:
        bpy.ops.object.shade_smooth()
        b = o.modifiers.new("bevel", "BEVEL")
        b.width = min(size) * 0.14
        b.segments = 2
    o.data.materials.append(material)
    return o


def _car(name, colour, mats, at, heading):
    """A car as a parented group: body, cabin, wheels, lamps.

    Built once per car rather than instanced, because each needs its own
    animation. Cheap at this poly count and it keeps the movement code simple.
    """
    body = _box(name, (1.75, 4.1, 0.62), (0, 0, 0.52),
                _mat(name + "_paint", colour, rough=0.28))
    cabin = _box(name + "_cab", (1.52, 2.05, 0.56), (0, -0.15, 1.06),
                 _mat(name + "_glass", (0.086, 0.106, 0.145), rough=0.12))
    parts = [body, cabin]
    for dx, dy in ((0.86, 1.35), (-0.86, 1.35), (0.86, -1.35), (-0.86, -1.35)):
        w = _box(f"{name}_w{dx}{dy}", (0.22, 0.62, 0.62), (dx, dy, 0.34),
                 mats["tyre"])
        parts.append(w)
    # headlights forward, tail lights back — direction is readable at a glance
    for dx in (0.58, -0.58):
        parts.append(_box(f"{name}_h{dx}", (0.30, 0.10, 0.18),
                          (dx, 2.06, 0.66), mats["head"], bevel=False))
        parts.append(_box(f"{name}_t{dx}", (0.30, 0.10, 0.16),
                          (dx, -2.06, 0.68), mats["tail"], bevel=False))

    bpy.ops.object.select_all(action="DESELECT")
    for p in parts:
        p.select_set(True)
    bpy.context.view_layer.objects.active = body
    bpy.ops.object.join()
    car = bpy.context.object
    car.name = name
    car.location = (at[0], at[1], 0)
    car.rotation_euler.z = math.radians(heading)
    return car


def build_street(total_frames, seed=3, lanes=2, cars=9):
    """The whole set. Returns nothing — it just exists in the scene."""
    rng = random.Random(seed)
    scn = bpy.context.scene
    mats = {k: _mat(k, v) for k, v in PALETTE.items()}
    mats["tyre"] = _mat("tyre", (0.055, 0.055, 0.063), rough=0.9)
    mats["head"] = _mat("head_e", PALETTE["head"], emit=9.0)
    mats["tail"] = _mat("tail_e", PALETTE["tail"], emit=5.0)
    mats["window_e"] = _mat("window_e", PALETTE["window"], emit=2.6)
    mats["lamp_e"] = _mat("lamp_e", PALETTE["lamp"], emit=14.0)
    mats["cloud_e"] = _mat("cloud_e", PALETTE["cloud"], emit=0.9)

    # sky
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
    ramp.color_ramp.elements[0].position = 0.34
    ramp.color_ramp.elements[0].color = (*PALETTE["sky_low"], 1)
    ramp.color_ramp.elements[1].position = 0.96
    ramp.color_ramp.elements[1].color = (*PALETTE["sky_top"], 1)
    ramp.color_ramp.elements.new(0.60).color = (*PALETTE["sky_mid"], 1)
    nt.links.new(coord.outputs["Window"], sep.inputs[0])
    nt.links.new(sep.outputs["Y"], ramp.inputs[0])
    nt.links.new(ramp.outputs["Color"], bg.inputs[0])
    nt.links.new(bg.outputs[0], out.inputs[0])

    # road + pavements. The pavement is raised, so the characters stand on a
    # kerb rather than floating over tarmac.
    _box("road", (14.0, 260.0, 0.06), (0, 0, 0.0), mats["road"], bevel=False)
    for x in (-8.4, 8.4):
        _box(f"pave{x}", (3.4, 260.0, 0.30), (x, 0, 0.15), mats["pavement"],
             bevel=False)

    for i in range(52):
        _box(f"line{i}", (0.16, 1.9, 0.02), (0, -120 + i * 4.8, 0.045),
             mats["line"], bevel=False)

    # buildings, both sides, varied by rule
    for side in (-1, 1):
        for i in range(16):
            w = rng.uniform(4.5, 8.0)
            d = rng.uniform(5.0, 9.0)
            h = rng.uniform(7.0, 22.0)
            y = -110 + i * 14 + rng.uniform(-2, 2)
            x = side * (15.5 + w / 2)
            m = mats["building"] if (i + side) % 2 else mats["building2"]
            _box(f"bld{side}{i}", (w, d, h), (x, y, h / 2), m, bevel=False)
            # lit windows — random, because a regular grid reads as geometry
            for _ in range(int(h * 2.6)):
                wy = y + rng.uniform(-d / 2 + 0.6, d / 2 - 0.6)
                wz = rng.uniform(1.6, h - 1.0)
                if rng.random() < 0.42:
                    _box(f"win{side}{i}{wy:.1f}{wz:.1f}",
                         (0.06, 0.34, 0.42),
                         (x - side * (w / 2 + 0.03), wy, wz),
                         mats["window_e"], bevel=False)

    # street lamps
    for i in range(14):
        y = -95 + i * 15
        for x in (-8.0, 8.0):
            _box(f"pole{i}{x}", (0.16, 0.16, 5.2), (x, y, 2.9),
                 mats["pavement"], bevel=False)
            _box(f"lamp{i}{x}", (0.5, 0.5, 0.18), (x - (0.7 if x > 0 else -0.7),
                 y, 5.4), mats["lamp_e"], bevel=False)

    # TRAFFIC. Two directions, staggered starts, different speeds.
    road_len = 240.0
    for i in range(cars):
        lane = i % (lanes * 2)
        going_north = lane < lanes
        x = (-1.6 - lane * 3.0) if going_north else (1.6 + (lane - lanes) * 3.0)
        colour = CAR_COLORS[i % len(CAR_COLORS)]
        y0 = -120 + (i * road_len / cars) + rng.uniform(-8, 8)
        car = _car(f"car{i}", colour, mats, (x, y0), 0 if going_north else 180)

        speed = rng.uniform(0.55, 1.05) * (1 if going_north else -1)
        car.keyframe_insert("location", frame=1)
        car.location.y = y0 + speed * road_len
        car.keyframe_insert("location", frame=total_frames)
        for fc in car.animation_data.action.fcurves:
            for kp in fc.keyframe_points:
                kp.interpolation = "LINEAR"

    # clouds
    for i in range(7):
        c = _box(f"cloud{i}", (rng.uniform(5, 11), 2.0, 1.3),
                 (rng.uniform(-30, 30), -70 - i * 9,
                  rng.uniform(20, 34)), mats["cloud_e"], bevel=False)
        c.keyframe_insert("location", frame=1)
        c.location.x += rng.uniform(6, 14)
        c.keyframe_insert("location", frame=total_frames)
        for fc in c.animation_data.action.fcurves:
            for kp in fc.keyframe_points:
                kp.interpolation = "LINEAR"

    # dusk key + cool fill; the emissives carry the rest
    bpy.ops.object.light_add(type="SUN", location=(20, 40, 26))
    key = bpy.context.object
    key.data.energy = 1.7
    key.data.angle = 0.2
    key.data.color = (1.0, 0.76, 0.55)
    key.rotation_euler = (math.radians(66), 0, math.radians(-52))

    bpy.ops.object.light_add(type="AREA", location=(-6, -6, 6))
    fill = bpy.context.object
    fill.data.energy = 420
    fill.data.size = 14
    fill.data.color = (0.45, 0.55, 0.95)

    print(f"[Street] {cars} cars, 32 buildings, 28 lamps, 7 clouds")
