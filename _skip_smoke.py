import pathlib
import tempfile

import modules.cc_clips as cc

cc.SKIPS = pathlib.Path(tempfile.mkdtemp()) / "clip_skips.json"
vid = "abc123"
print("skipped before:", cc._skipped(vid))
cc._note_failure(vid, "ERROR: unable to download video data: HTTP Error 403: Forbidden")
print("after 1 fail, skipped:", cc._skipped(vid))
cc._note_failure(vid, "Postprocessing: ffmpeg exited with code 3436169992")
print("after 2 fails, skipped:", cc._skipped(vid))
print(cc.SKIPS.read_text())
cc._note_failure("other", "some random timeout")
print("non-hard failure recorded?", "other" in cc._load_skips())
cc._clear_failure(vid)
print("after success, skipped:", cc._skipped(vid))
