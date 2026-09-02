"""
An instrumental bed under a finished reel — generated locally, owned by us.

Owner asked twice for a commercial track: "Sicela Ucolo Nothando", then "Love
and Peace". Neither can be sourced or embedded from here. Facebook and YouTube
both run Content ID on every upload, so the realistic outcome is a muted or
region-blocked reel on the surface that matters, and repeat claims carry
strike risk for the page. Owner call 2026-08-26: use our own instrumental.

ACE-Step generates it on this machine, so there is nothing to license and
nothing to claim. Mixed well under the voice — a bed is meant to be felt, not
listened to; if it competes with the narration on a phone speaker it is too
loud.

The whole thing is best-effort. A reel with no music still posts; a reel that
failed to build because the music model was busy does not.

    from modules.music_bed import add_bed
    final = add_bed(voiced, work / "final.mp4", "sa_pulse", dur)
"""
from pathlib import Path

# 0.18 was barely there under the narration — the owner wants the
# bed audible so a lineup reel feels like a broadcast, not a slideshow.
DEFAULT_VOL = 0.34


def add_bed(video_path, out_path, niche: str, duration: float,
            vol: float = DEFAULT_VOL, log=print):
    """Mix a locally generated instrumental under `video_path`.

    Returns the mixed file, or the ORIGINAL path if anything at all goes
    wrong — audio must never be the reason a post does not go out.
    """
    video_path, out_path = Path(video_path), Path(out_path)
    try:
        # THE OWNER'S OWN TRACKS COME FIRST.
        #
        # Owner 2026-09-02: "from now on all our videos should use this music,
        # both, change it around always" - and then "use the music on all our
        # videos". Every Genesis builder that scores a reel goes through this
        # one function (lineup, official XI, matchday hype, prematch, gaps,
        # news), so routing it here is what makes "all our videos" true rather
        # than six separate edits that drift apart.
        #
        # The generated instrumental stays as the fallback for the day the
        # library is empty - a silent reel would be worse than a generic bed.
        bed, owner = "", False
        try:
            from modules.owner_music import next_track, record_used
            bed = next_track()
            owner = bool(bed)
        except Exception as e:
            log(f"[Music] owner library unavailable ({str(e)[:60]})")
        if not bed:
            from modules.ace_music import get_ace_music_sync
            bed = get_ace_music_sync(niche, duration=duration)
        if not bed or not Path(bed).exists():
            log("[Music] no bed available — voice only")
            return video_path

        from moviepy import (VideoFileClip, AudioFileClip,
                             CompositeAudioClip, afx)
        v = VideoFileClip(str(video_path))
        m = AudioFileClip(str(bed)).with_effects([afx.MultiplyVolume(vol)])
        if m.duration > v.duration:
            m = m.subclipped(0, v.duration)
        elif m.duration < v.duration - 0.5:
            # Loop rather than let the last stretch fall silent — the shape
            # section is the back half of the reel and it is the part that
            # most needs something underneath it.
            reps, cuts = [], 0.0
            while cuts < v.duration:
                take = min(m.duration, v.duration - cuts)
                reps.append(m.subclipped(0, take))
                cuts += take
            from moviepy import concatenate_audioclips
            m = concatenate_audioclips(reps)

        tracks = [v.audio, m] if v.audio is not None else [m]
        v.with_audio(CompositeAudioClip(tracks)).write_videofile(
            str(out_path), codec="libx264", audio_codec="aac", logger=None)
        v.close()
        m.close()
        if owner:
            # Recorded on a successful MIX rather than on a confirmed post,
            # unlike the other ledgers here. add_bed has no idea whether the
            # caller will publish, and with a two-track library the cost of a
            # wasted turn is that the next build alternates anyway.
            try:
                record_used(bed)
            except Exception:
                pass
            log(f"[Music] {Path(bed).name} mixed at {int(vol * 100)}%")
        else:
            log(f"[Music] instrumental bed mixed at {int(vol * 100)}%")
        return out_path
    except Exception as e:
        log(f"[Music] bed skipped: {str(e)[:120]}")
        return video_path
