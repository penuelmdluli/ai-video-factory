"""
The setting as a parameter: time of day, weather, place and mood.

Every scene so far has been dusk on the same street, because the palette and
the sun angle were hard-coded. That is fine for one film and useless for a
series - the fifth episode in identical light reads as the same episode.

Four axes, and they compose:

    TIME    dawn / morning / noon / golden / dusk / night
            Changes the sky ramp, the sun angle and colour, the fill, and
            whether the windows and street lamps are lit. Time of day is the
            single biggest lever on how a scene FEELS, and it costs nothing.

    WEATHER clear / overcast / rain
            Overcast kills the sun and raises ambient - flat, soft, sad.
            Rain adds falling streaks and wet reflective ground, which is the
            cheapest atmosphere in 3D and reads instantly.

    PLACE   street / park / rooftop / promenade
            What furniture the world is built from.

    MOOD    neutral / warm / cold / bleak
            A grade on top, so the same dusk can be nostalgic or hostile.

Consistency and variety at once: an episode picks a TIME and a MOOD, and the
same street becomes a different scene without a single new asset.
"""
import math
import random

import bpy

# (sky_low, sky_mid, sky_high, sun_colour, sun_energy, sun_elev, fill, lit)
TIME = {
    "dawn":    ((0.968, 0.667, 0.482), (0.678, 0.529, 0.647),
                (0.216, 0.259, 0.451), (1.00, 0.76, 0.55), 2.2, 8,
                (0.42, 0.52, 0.86), 420, True),
    "morning": ((0.812, 0.878, 0.949), (0.545, 0.706, 0.886),
                (0.239, 0.451, 0.749), (1.00, 0.95, 0.88), 4.6, 34,
                (0.55, 0.68, 0.95), 260, False),
    "noon":    ((0.847, 0.910, 0.965), (0.529, 0.729, 0.925),
                (0.196, 0.427, 0.796), (1.00, 0.98, 0.94), 6.0, 68,
                (0.62, 0.72, 0.95), 200, False),
    "golden":  ((1.000, 0.729, 0.404), (0.878, 0.522, 0.400),
                (0.361, 0.322, 0.510), (1.00, 0.71, 0.42), 3.4, 12,
                (0.45, 0.52, 0.86), 300, False),
    "dusk":    ((0.937, 0.545, 0.325), (0.376, 0.267, 0.404),
                (0.055, 0.075, 0.169), (1.00, 0.76, 0.55), 1.7, 6,
                (0.45, 0.55, 0.95), 420, True),
    "night":   ((0.145, 0.129, 0.220), (0.078, 0.078, 0.153),
                (0.020, 0.024, 0.063), (0.62, 0.71, 1.00), 0.35, 24,
                (0.35, 0.44, 0.86), 300, True),
}

MOOD = {
    "neutral": (1.00, 1.00, 1.00),
    "warm":    (1.08, 0.99, 0.90),
    "cold":    (0.90, 0.97, 1.10),
    "bleak":   (0.94, 0.95, 0.97),
}


def _emit(name, rgb, strength):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    e = nt.nodes.new("ShaderNodeEmission")
    e.inputs[0].default_value = (*rgb, 1)
    e.inputs[1].default_value = strength
    o = nt.nodes.new("ShaderNodeOutputMaterial")
    nt.links.new(e.outputs[0], o.inputs[0])
    return m


def apply_time(time_key="dusk", mood_key="neutral", weather="clear"):
    """Re-light the whole scene for a time of day. Call AFTER the set exists.

    Works by replacing the world shader and the lights rather than by editing
    every material, so any set - street, park, whatever gets built next -
    inherits the time of day for free.
    """
    scn = bpy.context.scene
    lo, mid, hi, sun_c, sun_e, elev, fill_c, fill_e, lit = TIME[time_key]
    grade = MOOD[mood_key]
    lo = tuple(c * g for c, g in zip(lo, grade))
    mid = tuple(c * g for c, g in zip(mid, grade))
    hi = tuple(c * g for c, g in zip(hi, grade))

    if weather == "overcast":
        # no direct sun; the sky becomes the light source
        sun_e *= 0.18
        fill_e *= 2.4
        lo = tuple(0.55 * c + 0.45 * 0.62 for c in lo)
        mid = tuple(0.55 * c + 0.45 * 0.58 for c in mid)

    world = bpy.data.worlds.new(f"sky_{time_key}")
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
    ramp.color_ramp.elements[0].color = (*lo, 1)
    ramp.color_ramp.elements[1].position = 0.96
    ramp.color_ramp.elements[1].color = (*hi, 1)
    ramp.color_ramp.elements.new(0.58).color = (*mid, 1)
    nt.links.new(coord.outputs["Window"], sep.inputs[0])
    nt.links.new(sep.outputs["Y"], ramp.inputs[0])
    nt.links.new(ramp.outputs["Color"], bg.inputs[0])
    nt.links.new(bg.outputs[0], out.inputs[0])
    bg.inputs[1].default_value = 0.9 if time_key != "night" else 0.35

    for o in [x for x in bpy.data.objects if x.type == "LIGHT"]:
        bpy.data.objects.remove(o, do_unlink=True)

    bpy.ops.object.light_add(type="SUN", location=(14, 26, 22))
    sun = bpy.context.object
    sun.data.energy = sun_e
    sun.data.angle = 0.22
    sun.data.color = tuple(c * g for c, g in zip(sun_c, grade))
    sun.rotation_euler = (math.radians(90 - elev), 0, math.radians(-46))

    bpy.ops.object.light_add(type="AREA", location=(-7, -6, 7))
    fill = bpy.context.object
    fill.data.energy = fill_e
    fill.data.size = 16
    fill.data.color = fill_c

    # Practical lights follow the clock: windows and street lamps go dark in
    # daylight. A noon street with every window glowing is the tell that a
    # scene was built for one time of day and re-used.
    for m in bpy.data.materials:
        if m.name.startswith(("window_e", "lamp_e", "head_e")):
            try:
                em = next(n for n in m.node_tree.nodes
                          if n.type == "EMISSION")
                base = {"window_e": 2.6, "lamp_e": 14.0, "head_e": 9.0}
                key = next(k for k in base if m.name.startswith(k))
                em.inputs[1].default_value = base[key] if lit else 0.0
            except Exception:
                pass

    print(f"[Setting] {time_key} / {mood_key} / {weather}"
          + ("  (practicals lit)" if lit else ""))
    return lit


def add_rain(total_frames, drops=900, area=42.0, seed=7):
    """Falling streaks plus a wet, reflective ground.

    Cheapest atmosphere available: thin emissive slivers falling on a loop.
    Nothing is simulated, so it costs a few hundred keyframes and renders as
    fast as the rest of the set.
    """
    rng = random.Random(seed)
    m = _emit("rain_e", (0.72, 0.80, 0.95), 1.4)

    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, 0))
    proto = bpy.context.object
    proto.name = "raindrop"
    proto.scale = (0.012, 0.012, 0.42)
    proto.data.materials.append(m)

    top, bottom = 16.0, -0.4
    for i in range(drops):
        d = proto.copy()
        d.data = proto.data
        bpy.context.collection.objects.link(d)
        x = rng.uniform(-area, area)
        y = rng.uniform(-area, area * 1.4)
        phase = rng.random()
        fall = rng.uniform(0.55, 0.95)
        d.location = (x, y, bottom + (top - bottom) * phase)
        d.keyframe_insert("location", frame=1)
        d.location.z -= (top - bottom) * fall * 2.2
        d.location.y -= 1.6
        d.keyframe_insert("location", frame=total_frames)
        for fc in d.animation_data.action.fcurves:
            for kp in fc.keyframe_points:
                kp.interpolation = "LINEAR"
    bpy.data.objects.remove(proto, do_unlink=True)

    # wet ground: drop roughness so the practicals streak across the tarmac
    for mat in bpy.data.materials:
        if mat.name in ("road", "pavement") and mat.use_nodes:
            try:
                b = mat.node_tree.nodes["Principled BSDF"]
                b.inputs["Roughness"].default_value = 0.14
                b.inputs["Metallic"].default_value = 0.25
            except Exception:
                pass
    print(f"[Setting] rain: {drops} drops, wet ground")
