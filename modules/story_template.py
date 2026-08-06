"""Story template — assemble the device toolkit into ONE $0 data-documentary reel.

A `spec` is a list of scene dicts; each renders via a device (hook / map / stat / bars /
quote / timeline / chart / flow / outro). They're concatenated, a narration voiceover +
word-highlighted captions are laid over, and a BREAKING badge + progress bar are burned in.
No RunPod, no LTX — every scene is local PIL/MoviePy, so a whole mini-documentary is ~$0.

    from modules.story_template import make_story_reel
    make_story_reel([
        {"type": "hook",  "text": "This strait controls the world's oil"},
        {"type": "map",   "headline": "Strait of Hormuz"},
        {"type": "stat",  "value": 20, "suffix": "%", "label": "of the world's oil"},
        {"type": "bars",  "title": "Top oil buyers", "items": [("China", 47), ("India", 22), ("EU", 15)], "suffix": "%"},
        {"type": "quote", "quote": "Whoever controls this water controls the flow.", "by": "Analyst"},
        {"type": "outro", "text": "Follow Tech Pulse Africa"},
    ], "story.mp4", narration_text="...", size=(1080, 1920))
"""
import re
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))   # repo root importable


def _render_scene(sc, out, size, accent, fps):
    t = sc.get("type"); dur = sc.get("seconds")
    if t == "hook":
        from modules.hook_card import make_hook_card
        return make_hook_card(sc.get("text", "BREAKING"), out, duration=dur or 1.7, size=size, accent=accent, fps=fps)
    if t in ("map", "route", "news_map"):
        from modules.map_zoom import make_news_map
        return make_news_map(sc.get("headline") or sc.get("text", ""), out, duration=dur or 3.8, size=size, accent=accent, fps=fps)
    if t == "stat":
        from modules.stat_counter import make_stat_clip
        return make_stat_clip(sc["value"], sc.get("label", ""), out, duration=dur or 2.6, size=size,
                              accent=accent, prefix=sc.get("prefix", ""), suffix=sc.get("suffix", ""), fps=fps)
    if t == "bars":
        from modules.bar_race import make_bar_race
        return make_bar_race(sc["items"], out, title=sc.get("title", ""), duration=dur or 3.6, size=size,
                             accent=accent, prefix=sc.get("prefix", ""), suffix=sc.get("suffix", ""), fps=fps)
    if t == "quote":
        from modules.quote_card import make_quote_card
        return make_quote_card(sc["quote"], sc.get("by", ""), out, duration=dur or 3.2, size=size, accent=accent, fps=fps)
    if t == "timeline":
        from modules.timeline import make_timeline_clip
        return make_timeline_clip(sc["events"], out, title=sc.get("title", ""), duration=dur or 5.0, size=size, accent=accent, fps=fps)
    if t == "chart":
        from modules.line_chart import make_line_chart_clip
        return make_line_chart_clip(sc["points"], out, title=sc.get("title", ""), duration=dur or 4.0, size=size,
                                    accent=accent, prefix=sc.get("prefix", ""), suffix=sc.get("suffix", ""), fps=fps)
    if t == "flow":
        from modules.flow_steps import make_flow_clip
        return make_flow_clip(sc["steps"], out, title=sc.get("title", ""), duration=dur or 4.0, size=size, accent=accent, fps=fps)
    if t == "outro":
        from modules.hook_card import make_hook_card
        return make_hook_card(sc.get("text", "FOLLOW FOR MORE"), out, duration=dur or 1.8, size=size, accent=accent, fps=fps)
    return None


def _ts(x):
    x = x.strip().replace(",", ".")
    h, m, s = x.split(":")
    return int(h) * 3600 + int(m) * 60 + float(s)


def _phrases_from_srt(path, per=4):
    """Group a word-level SRT into <=`per`-word caption phrases with (start, end, text)."""
    try:
        txt = Path(path).read_text(encoding="utf-8")
    except Exception:
        return []
    words = []
    for b in re.split(r"\n\s*\n", txt.strip()):
        lines = b.strip().splitlines()
        tline = next((l for l in lines if "-->" in l), None)
        if not tline:
            continue
        a, c = tline.split("-->")
        try:
            s, e = _ts(a), _ts(c)
        except Exception:
            continue
        wtext = " ".join(l for l in lines if "-->" not in l and not l.strip().isdigit())
        for w in wtext.split():
            words.append((s, e, w))
    phrases = []
    for i in range(0, len(words), per):
        grp = words[i:i + per]
        if grp:
            phrases.append((grp[0][0], grp[-1][1], " ".join(w for _, _, w in grp)))
    return phrases


def make_story_reel(spec, out_path, narration_text=None, size=(1080, 1920),
                    accent="#FF3131", fps=30, music=None, breaking=True, captions=False):
    """Render + concatenate device scenes into a data-documentary reel. Returns out_path.
    captions=False by default — every scene already carries its own on-screen text, so
    running subtitles would only clutter it (keep it clean)."""
    from moviepy import (VideoFileClip, concatenate_videoclips, ImageClip,
                         AudioFileClip, CompositeVideoClip, CompositeAudioClip, afx)
    W, H = int(size[0]), int(size[1])
    work = Path(tempfile.mkdtemp(prefix="story_"))
    try:
        paths = []
        for i, sc in enumerate(spec):
            p = _render_scene(sc, str(work / f"scene_{i}.mp4"), size, accent, fps)
            if p:
                paths.append(p)
        if not paths:
            return None

        vclips = [VideoFileClip(p) for p in paths]
        base = concatenate_videoclips(vclips, method="compose")
        total = base.duration

        overlays, audio_tracks = [], []
        if narration_text:
            import asyncio
            from modules.voice_generator import generate_voice
            try:
                res = asyncio.run(generate_voice(narration_text, work, "narr",
                                                 format_type="short", niche="tech_news"))
            except Exception:
                res = None
            if res and Path(res["audio_path"]).exists():
                audio_tracks.append(AudioFileClip(res["audio_path"]))
                if captions:   # off by default — scenes already carry their own text
                    from assemble_full import render_caption_png, CAP_H
                    for j, (s, e, txt) in enumerate(_phrases_from_srt(res.get("subtitle_path", ""))):
                        if s >= total:
                            break
                        png = render_caption_png(txt, W, str(work / f"cap_{j}.png"))
                        overlays.append(ImageClip(png).with_start(s)
                                        .with_duration(max(0.4, min(e, total) - s))
                                        .with_position(("center", int(H * 0.62) - CAP_H // 2)))
        if music and Path(music).exists():
            try:
                m = AudioFileClip(music).with_effects([afx.AudioLoop(duration=total),
                                                       afx.MultiplyVolume(0.16)])
                audio_tracks.append(m)
            except Exception:
                pass

        final = CompositeVideoClip([base] + overlays, size=(W, H)) if overlays else base
        if audio_tracks:
            final = final.with_audio(CompositeAudioClip(audio_tracks)).with_duration(total)

        base_out = work / "story_base.mp4"
        final.write_videofile(str(base_out), fps=fps, codec="libx264", audio_codec="aac",
                              preset="veryfast", logger=None)
        for c in vclips:
            try:
                c.close()
            except Exception:
                pass

        out_path = str(out_path); Path(out_path).parent.mkdir(parents=True, exist_ok=True)
        if breaking:
            from modules.overlays import add_news_overlays
            r = add_news_overlays(str(base_out), out_path, label="BREAKING", accent=accent)
            if not r:
                shutil.copy(str(base_out), out_path)
        else:
            shutil.copy(str(base_out), out_path)
        return out_path
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    make_story_reel([
        {"type": "hook",  "text": "This strait controls the world's oil"},
        {"type": "map",   "headline": "Strait of Hormuz"},
        {"type": "stat",  "value": 20, "suffix": "%", "label": "of the world's oil"},
        {"type": "bars",  "title": "Top oil buyers", "items": [("China", 47), ("India", 22), ("Europe", 15)], "suffix": "%"},
        {"type": "flow",  "title": "How it works", "steps": ["Oil loads at the Gulf", "Tankers pass the strait", "The world gets fuel"]},
        {"type": "quote", "quote": "Whoever controls this water controls the flow.", "by": "Analyst"},
        {"type": "outro", "text": "Follow Tech Pulse Africa"},
    ], "output/story_demo.mp4",
        narration_text=("This tiny strait controls twenty percent of the world's oil. "
                        "China, India and Europe depend on it. Tankers load at the Gulf, "
                        "pass through the narrow strait, and fuel the world. "
                        "Whoever controls this water controls the flow."),
        size=(720, 1280))
    print("wrote output/story_demo.mp4")
