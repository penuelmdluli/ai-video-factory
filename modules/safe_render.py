"""Temp audio belongs beside its own build, not in a shared spot in the root.

Incident 2026-09-02 21:54 - the role slot exited 1 and posted nothing. The
video had already finished encoding; it died in MoviePy's own cleanup:

    File ".../moviepy/video/VideoClip.py", line 411, in write_videofile
        os.remove(audiofile)
    PermissionError: [WinError 32] The process cannot access the file because
    it is being used by another process: 'finalTEMP_MPY_wvf_snd.mp4'

MoviePy names its temporary audio file after the OUTPUT file's basename and,
when `temp_audiofile_path` is left at its default of "", writes it to the
process's current directory rather than next to the output. Twenty-one
builders here write `work/final.mp4` and every one of them runs from the repo
root, so all of them resolve to one single shared file:

    output/role_chiefs_.../final.mp4    -> <repo>/finalTEMP_MPY_wvf_snd.mp4
    output/lineup_chiefs_.../final.mp4  -> <repo>/finalTEMP_MPY_wvf_snd.mp4

Builds overlap constantly here - the slot runner, the scheduler and matchday
all render unattended, and two were mid-render that night. When they overlap,
whichever finishes first deletes a file the other's ffmpeg still has open, and
the loser dies after doing all of its work. The two stray
`*TEMP_MPY_wvf_snd.mp4` files sitting in the repo root are the same collision
from April, left behind when the process that owned them was killed.

The crash is the mild version. The identical collision lets a finishing build
overwrite the temp audio a running build is still reading - the wrong
narration under a reel that then posts, with nothing in the log to show it.

WHY THIS IS PATCHED RATHER THAN PASSED AT EACH CALL

`check_render_safety.py` counts 43 write_videofile calls across 40 files with
no temp path. Editing all 43 fixes today and does nothing about the 44th
builder, and this repo's history is of the same bug returning in a new shape.
So the DEFAULT is made safe once, here: a call that names neither
`temp_audiofile` nor `temp_audiofile_path` gets its temp audio in the output
file's own directory, which is the timestamped build folder and therefore
already unique per run. A call that asks for a specific path is untouched.

Installed from modules/__init__.py, so it is live for anything that imports
`modules.*` - which is every builder in the factory.

    python check_render_safety.py     # proves it, including the live race
"""
import functools
import os

_MARK = "_factory_temp_audio_scoped"

# temp_audiofile and temp_audiofile_path are the 11th and 12th parameters
# after `filename`. Nothing here passes that many positionally, but if a
# caller ever does, leave it alone rather than hand the same argument twice.
_POSITIONAL_LIMIT = 10


def install():
    """Point MoviePy's temp audio at each build's own directory.

    Idempotent, and returns True only on the call that actually patched.
    """
    from moviepy.video.VideoClip import VideoClip

    original = VideoClip.write_videofile
    if getattr(original, _MARK, False):
        return False

    @functools.wraps(original)
    def write_videofile(self, filename, *args, **kwargs):
        if (not kwargs.get("temp_audiofile")
                and not kwargs.get("temp_audiofile_path")
                and len(args) <= _POSITIONAL_LIMIT):
            out_dir = os.path.dirname(os.path.abspath(str(filename)))
            # If the directory is missing the render is going to fail on the
            # output file anyway; don't mask that with a temp-path error.
            if os.path.isdir(out_dir):
                kwargs["temp_audiofile_path"] = out_dir
        return original(self, filename, *args, **kwargs)

    write_videofile.__dict__[_MARK] = True
    VideoClip.write_videofile = write_videofile
    return True


def temp_audio_path_for(filename):
    """Where MoviePy will put the temp audio for `filename`, as patched.

    Used by the checker to show the collision is gone without rendering.
    """
    from moviepy.Clip import Clip
    from moviepy.tools import find_extension

    name = os.path.splitext(os.path.basename(str(filename)))[0]
    out_dir = os.path.dirname(os.path.abspath(str(filename)))
    base = name + Clip._TEMP_FILES_PREFIX + "wvf_snd." + find_extension("aac")
    return os.path.join(out_dir, base)
