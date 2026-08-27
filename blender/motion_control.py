"""
Controlling mocap: retime it, trim it, and layer behaviour on top of it.

Mixamo hands over a fixed performance. The question is how much of it we can
drive from code without an animator, and the answer is: most of the things
that matter for a channel.

    RETIME      scale every keyframe on the time axis. 0.5 is half speed,
                which reads as weight; 1.6 is comic urgency. The pose data is
                untouched - only when each pose happens changes.

    TRIM        use frames 40-90 of a 137-frame clip. Most mocap has a wind-up
                and a settle that a 6-second reel does not want.

    LOOK        a Damped Track constraint on the head, aimed at the camera.
                This is the interesting one: it is BEHAVIOUR layered over
                recorded motion. The body keeps performing the captured take
                while the head independently holds eye contact - something no
                single mocap clip contains, and the difference between a clip
                that plays at you and a character that is aware of you.

    LEAN        a constant additive rotation on the spine. Posture is
                character: the same walk leaning forward reads as determined,
                leaning back as arrogant.

    MIRROR      flip the performance left-to-right.

Everything here is a parameter, so one FBX yields many distinct takes.

    blender --background --python blender/motion_control.py -- \
        --fbx X.fbx --out Y --speed 0.7 --trim 30:110 --look --lean 8
"""
import argparse
import math
import sys

import bpy

sys.path.append(str(__import__("pathlib").Path(__file__).parent))
from mixamo_render import (build_camera, build_world, clear,  # noqa: E402
                           configure, import_character)


def retime(arm, factor):
    """Scale the action on the time axis. factor<1 slows, >1 speeds up."""
    if not (arm.animation_data and arm.animation_data.action) or factor == 1.0:
        return
    act = arm.animation_data.action
    for fc in act.fcurves:
        for kp in fc.keyframe_points:
            kp.co.x /= factor
            kp.handle_left.x /= factor
            kp.handle_right.x /= factor
        fc.update()
    print(f"[Motion] retimed x{factor}")


def trim(scn, arm, spec):
    """'40:110' -> render only that slice of the take."""
    if not spec:
        return
    a, _, b = spec.partition(":")
    start, end = int(a), int(b)
    scn.frame_start, scn.frame_end = start, end
    print(f"[Motion] trimmed to {start}-{end}")


def look_at(arm, target, strength=1.0):
    """Head holds eye contact while the body performs the captured take.

    A DAMPED_TRACK on the head bone, with influence, so the constraint bends
    the recorded rotation toward the target rather than replacing it. Set
    influence to 1.0 and the head snaps to the camera and stops acting; around
    0.6 it reads as a person glancing over while still doing what they were
    doing.
    """
    head = next((b for b in arm.pose.bones
                 if b.name.lower().endswith("head")), None)
    if not head:
        print("[Motion] no head bone — look skipped")
        return
    c = head.constraints.new("DAMPED_TRACK")
    c.target = target
    # TRACK_Z, established by rendering both candidates rather than guessing.
    # A Mixamo head bone runs UP through the skull, so TRACK_Y aims the top of
    # the cap at the camera - the first attempt produced a character bowing at
    # the lens. Z is the face normal.
    c.track_axis = "TRACK_Z"
    c.influence = strength
    print(f"[Motion] head '{head.name}' tracks the camera at {strength}")


def lean(arm, degrees):
    """Constant additive posture on the spine. Attitude, not animation."""
    if not degrees:
        return
    spine = next((b for b in arm.pose.bones
                  if b.name.lower().endswith("spine1")), None)
    spine = spine or next((b for b in arm.pose.bones
                           if b.name.lower().endswith("spine")), None)
    if not spine:
        return
    # A rotation added to an already-keyed bone would be overwritten on the
    # next frame, so it goes on as a constraint offset instead.
    c = spine.constraints.new("TRANSFORM")
    c.target = arm
    c.map_to = "ROTATION"
    c.to_min_x_rot = math.radians(degrees)
    c.to_max_x_rot = math.radians(degrees)
    c.mix_mode_rot = "AFTER"
    print(f"[Motion] spine leaning {degrees} deg")


def mirror(arm):
    """Flip the take left-to-right."""
    arm.scale.x *= -1
    print("[Motion] mirrored")


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--fbx", required=True)
    ap.add_argument("--out", default="//motion")
    ap.add_argument("--shot", default="medium",
                    choices=["wide", "medium", "close"])
    ap.add_argument("--speed", type=float, default=1.0)
    ap.add_argument("--trim", default="")
    ap.add_argument("--look", type=float, default=0.0)
    ap.add_argument("--lean", type=float, default=0.0)
    ap.add_argument("--mirror", action="store_true")
    ap.add_argument("--still", type=int, default=0)
    a = ap.parse_args(argv)

    clear()
    bpy.context.scene.render.fps = 30
    build_world()
    arm, meshes, rng = import_character(a.fbx)
    if not arm:
        print("[Motion] no armature")
        return

    retime(arm, a.speed)
    if a.mirror:
        mirror(arm)
    lean(arm, a.lean)

    cam = build_camera(arm, meshes, a.shot)
    if a.look:
        look_at(arm, cam, a.look)

    scn = bpy.context.scene
    end = int(rng[1] / a.speed) if a.speed != 1.0 else rng[1]
    configure(a.out, (rng[0], end))
    trim(scn, arm, a.trim)

    if a.still:
        scn.frame_set(a.still)
        scn.render.image_settings.file_format = "PNG"
        scn.render.filepath = a.out + f"_still_{a.still}"
        bpy.ops.render.render(write_still=True)
    else:
        bpy.ops.render.render(animation=True)
    print("[Motion] done ->", a.out)


if __name__ == "__main__":
    main()
