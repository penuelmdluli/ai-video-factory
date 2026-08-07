"""Beat-synced faceless reel — the voiceover IS the video.

Each beat = one short spoken line + its visual. The voice is generated PER BEAT and the visual
is rendered to that beat's EXACT voice length, so if you only heard the audio you'd have the whole
story, and every frame on screen matches the words being spoken. Then the engagement pack (badge,
progress bar, @handle watermark, FOLLOW, comment-bait) is burned in. No RunPod, ~$0.

    from modules.synced_reel import make_synced_reel
    make_synced_reel(beats, "reel.mp4", handle="TechPulseAfrica", follow=True)
"""
import asyncio
import shutil
import tempfile
from pathlib import Path


def make_synced_reel(beats, out_path, size=(1080, 1920), accent="#FF3131", fps=30, music=None,
                     breaking=True, label="BREAKING", handle="", follow=False, comment_prompt="",
                     niche="tech_news"):
    from moviepy import (VideoFileClip, AudioFileClip, concatenate_videoclips,
                         CompositeAudioClip, afx)
    from modules.voice_generator import generate_voice
    from modules.keyword_card import make_keyword_card
    from modules.hook_card import make_hook_card
    from modules.story_template import _render_scene
    from modules.motion_bg import make_bg_provider

    work = Path(tempfile.mkdtemp(prefix="synced_"))
    lines_spoken = []
    # one animated background per reel; seed from content so it's stable within a reel
    seed = sum(ord(c) for c in (beats[0].get("say", "") if beats else "x")) % 9973
    bg = make_bg_provider(accent=accent, seed=seed)
    offset = 0   # cumulative frames -> motion stays continuous across beats
    tcur = 0.0   # running start time (s) of each beat, for SFX placement
    beat_marks = []   # (time, sfx_name)
    try:
        clips = []
        for i, b in enumerate(beats):
            say = (b.get("say") or b.get("text") or "").strip()
            # 1. voice for THIS beat (so the visual can match its exact length)
            audio, dur = None, None
            if say:
                try:
                    res = asyncio.run(generate_voice(say, work, f"v{i}", format_type="short", niche=niche))
                except Exception:
                    res = None
                if res and Path(res["audio_path"]).exists():
                    audio = AudioFileClip(res["audio_path"]); dur = audio.duration
                    lines_spoken.append(say)
            dur = max(1.5, (dur or 2.0)) + 0.35    # small tail so nothing cuts on the last phoneme

            # 2. visual for this beat, rendered to that exact duration
            n_frames = max(2, int(round(dur * fps)))
            vpath = None
            if b.get("hook"):
                vpath = make_hook_card(say, str(work / f"hook_{i}.mp4"), duration=dur, size=size, accent=accent, fps=fps)
            elif b.get("device"):
                sc = dict(b["device"]); sc["seconds"] = dur
                vpath = _render_scene(sc, str(work / f"scene_{i}.mp4"), size, accent, fps)
            if not vpath:
                vpath = make_keyword_card(say, b.get("keyword"), b.get("emoji"),
                                          str(work / f"kw_{i}.mp4"), duration=dur, size=size, accent=accent,
                                          fps=fps, bg_provider=bg, frame_offset=offset)
            offset += n_frames
            if not vpath:
                continue
            clip = VideoFileClip(vpath)
            if audio is not None:
                clip = clip.with_audio(audio)

            # SFX marks (absolute time). whoosh on cuts, pop on emoji land, ticks+ding on counters
            if i > 0:
                beat_marks.append((tcur, "whoosh"))
            if b.get("hook"):
                beat_marks.append((tcur + 0.02, "ding"))
            elif (b.get("device") or {}).get("type") == "stat":
                for k in range(6):
                    beat_marks.append((tcur + 0.30 + k * 0.16, "tick"))
                beat_marks.append((tcur + min(dur - 0.4, 1.5), "ding"))
            else:
                beat_marks.append((tcur + 0.13, "pop"))
            clips.append(clip)
            tcur += clip.duration

        if not clips:
            return None
        base = concatenate_videoclips(clips, method="compose")
        total = base.duration

        # ---- audio: per-beat voice (already on base) + music bed ----
        if music and Path(music).exists():
            try:
                m = AudioFileClip(music).with_effects([
                    afx.AudioLoop(duration=total), afx.MultiplyVolume(0.16),
                    afx.AudioFadeIn(0.4), afx.AudioFadeOut(0.8)])
                tracks = [base.audio, m] if base.audio is not None else [m]
                base = base.with_audio(CompositeAudioClip(tracks))
            except Exception as e:
                print(f"[synced] music mix skipped: {e}", flush=True)

        base_out = work / "synced_base.mp4"
        base.write_videofile(str(base_out), fps=fps, codec="libx264", audio_codec="aac",
                             preset="veryfast", logger=None)
        for c in clips:
            try:
                c.close()
            except Exception:
                pass

        # ---- SFX punctuation: one full-length track mixed via ffmpeg (channel-safe) ----
        base_src = base_out
        if beat_marks:
            try:
                import subprocess
                import imageio_ffmpeg
                from modules.sfx_synth import arrays as _sfx_arrays, SR as _SR, write_stereo_wav
                sfx = _sfx_arrays()
                buf = __import__("numpy").zeros(int(total * _SR) + _SR, dtype="float32")
                vol = {"whoosh": 0.4, "pop": 0.5, "tick": 0.35, "ding": 0.42}
                for tstart, kind in beat_marks:
                    a = sfx.get(kind)
                    if a is None:
                        continue
                    off = int(max(0.0, tstart - (0.08 if kind == "whoosh" else 0.0)) * _SR)
                    seg = a * vol.get(kind, 0.4)
                    end = min(len(buf), off + len(seg))
                    if end > off:
                        buf[off:end] += seg[:end - off]
                sfx_wav = write_stereo_wav(str(work / "sfx_track.wav"), buf)
                ff = imageio_ffmpeg.get_ffmpeg_exe()
                mixed = work / "synced_sfx.mp4"
                subprocess.run([ff, "-y", "-i", str(base_out), "-i", str(sfx_wav),
                                "-filter_complex", "[0:a][1:a]amix=inputs=2:normalize=0:duration=first[a]",
                                "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", str(mixed)],
                               capture_output=True)
                if mixed.exists() and mixed.stat().st_size > 10000:
                    base_src = mixed
                else:
                    print("[synced] sfx mix produced no file — using clean audio", flush=True)
            except Exception as e:
                print(f"[synced] sfx skipped: {e}", flush=True)

        out_path = str(out_path); Path(out_path).parent.mkdir(parents=True, exist_ok=True)
        if breaking:
            from modules.overlays import add_news_overlays
            r = add_news_overlays(str(base_src), out_path, label=label, accent=accent,
                                  handle=handle, follow=follow, comment_prompt=comment_prompt)
            if not r:
                shutil.copy(str(base_src), out_path)
        else:
            shutil.copy(str(base_src), out_path)
        # the spoken lines, in order, are the standalone narration — return them for captions/description
        return {"path": out_path, "narration": " ".join(lines_spoken), "duration": total}
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    demo = [
        {"say": "A new currency could change Africa forever", "hook": True},
        {"say": "BRICS nations are building a rival to the dollar", "keyword": "BRICS", "emoji": "\U0001F310"},
        {"say": "Africa sits at the center of this shift", "device": {"type": "map", "headline": "Africa BRICS"}},
        {"say": "Trade worth 40 billion dollars is moving", "device": {"type": "stat", "value": 40, "prefix": "$", "suffix": "B", "label": "in new trade"}},
        {"say": "The real question is who controls the flow", "keyword": "CONTROL", "emoji": "\U0001F9ED"},
        {"say": "Follow Tech Pulse Africa", "keyword": "FOLLOW", "emoji": "\U0001F514", "outro": True},
    ]
    r = make_synced_reel(demo, "output/synced_demo.mp4", handle="TechPulseAfrica", follow=True,
                         comment_prompt="Will BRICS beat the dollar?")
    print(r)
