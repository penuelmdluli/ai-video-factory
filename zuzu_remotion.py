#!/usr/bin/env python
"""Render a Zuzu episode with the REMOTION spine (crisp, deterministic, no GPU wobble)
instead of the SDXL->LTX AI route.

Maps a make_zuzu / zuzu_lessons lesson -> the Remotion scene schema (title, counting,
letter, karaoke lyrics, character, outro), times the scenes to the song, and renders
via make_remotion_episode.render_episode (headless Chromium).

CLI:
  python zuzu_remotion.py                       # ABC lesson + newest existing song
  python zuzu_remotion.py <lesson_id> <song>    # specific lesson + song file
Lib:
  from zuzu_remotion import render_zuzu_remotion
  render_zuzu_remotion(lesson, song_path, "out.mp4", char_clip=None)
"""
import sys, glob, os
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from make_remotion_episode import render_episode

C1, C2 = "#7c4dff", "#22d3ee"
LETTER_WORDS = {"A": ("Apple", "🍎"), "B": ("Ball", "⚽"), "C": ("Cat", "🐱"),
                "D": ("Dog", "🐶"), "E": ("Egg", "🥚"), "F": ("Fish", "🐟")}


def _song_seconds(path):
    try:
        from moviepy import AudioFileClip
        with AudioFileClip(str(path)) as a:
            return float(a.duration)
    except Exception:
        return 40.0


def _is_learn(lesson) -> bool:
    """A teaching lesson carries an `edu` list of phonics/counting/addition scenes.
    Those drive a dedicated LEARNING layout (real instruction) instead of karaoke."""
    return bool(lesson.get("edu"))


def _learning_scenes(lesson, song_secs):
    """Teaching layout: title -> educational scenes spread across the WHOLE song -> outro.
    The sung phonics/counting song plays underneath; the teaching scenes carry the lesson.
    Scenes cycle if the song outlasts the edu list — repetition is the point for ages 3-7."""
    title = (lesson.get("title") or "Learn with Zuzu").strip()[:26]
    edu = [dict(s) for s in (lesson.get("edu") or []) if s.get("type")]
    if not edu:
        return None
    avail = max(8.0, song_secs - 6)                      # minus title (3) + outro (3)
    nslots = max(len(edu), int(round(avail / 5.0)))      # ~5s per teaching beat
    per = round(avail / nslots, 1)
    scenes = [{"type": "title", "text": title, "subtitle": "with Zuzu 🐘", "seconds": 3}]
    for i in range(nslots):
        sc = dict(edu[i % len(edu)]); sc["seconds"] = per
        scenes.append(sc)
    scenes.append({"type": "outro", "text": "Great job! 👋", "seconds": 3})
    return scenes


def _even_karaoke_scenes(title, cat, lines, song_secs):
    """FALLBACK layout (no reliable transcription): title + a themed edu scene + karaoke
    split EVENLY across the song + character + outro. Karaoke scenes carry words:[] so the
    Remotion side uses proportional highlight (today's behaviour). Zuzu still sings (mouth
    from the amplitude envelope)."""
    scenes = [{"type": "title", "text": title[:26], "subtitle": "with Zuzu 🐘", "seconds": 3}]
    edu_secs = 0
    if any(k in cat for k in ("count", "number")):
        scenes.append({"type": "counting", "count": 5, "emoji": "🍎", "label": "apples", "seconds": 6}); edu_secs = 6
    elif any(k in cat for k in ("letter", "abc", "alphabet")):
        for L in ("A", "B", "C"):
            w, e = LETTER_WORDS[L]
            scenes.append({"type": "letter", "letter": L, "word": w, "emoji": e, "seconds": 2.5})
        edu_secs = 7.5
    elif any(k in cat for k in ("color", "colour", "shape")):
        scenes.append({"type": "counting", "count": 3, "emoji": "🎨", "label": "colours", "seconds": 6}); edu_secs = 6

    fixed = 3 + edu_secs + 4 + 3  # title + edu + character + outro
    karaoke_budget = max(8.0, song_secs - fixed)
    chunks = [lines[i:i + 3] for i in range(0, len(lines), 3)] or [lines]
    per = karaoke_budget / len(chunks)
    for ch in chunks:
        scenes.append({"type": "karaoke", "lines": ch, "words": [], "seconds": round(max(4.0, per), 1)})

    scenes.append({"type": "character", "clip": "", "caption": "Great job, friends!", "seconds": 4})
    scenes.append({"type": "outro", "text": "See you next time! 👋", "seconds": 3})
    return scenes


def build_remotion_lesson(lesson: dict, audio_name: str = "", song_secs: float = 40.0,
                          char_clip: str = "", char_img: str = "", char_imgs=None,
                          portrait: bool = False, word_tokens=None, match_ratio: float = 0.0,
                          fps: int = 30) -> dict:
    """make_zuzu lesson -> Remotion lesson dict.
    When real per-word timings are available (word_tokens + match_ratio>=0.5) the karaoke
    is WORD-SYNCED to the actual sung vocals and Zuzu sings the visible words; otherwise it
    falls back to the even-timed layout. portrait=True renders NATIVE 1080x1920 (reels)."""
    title = (lesson.get("title") or "Learn with Zuzu").strip()
    cat = (lesson.get("category") or "").lower()

    raw = (lesson.get("lyrics") or "")
    lines = [ln.strip() for ln in raw.replace("[verse]", "").replace("[chorus]", "")
             .replace("[bridge]", "").splitlines() if ln.strip()]
    if not lines:
        lines = [c for c in (lesson.get("captions") or []) if c][:8] or ["La la la, sing with me!"]

    if _is_learn(lesson):
        scenes = _learning_scenes(lesson, song_secs)
        print(f"[zuzu-remotion] LEARNING layout: {len(scenes)} teaching scenes over {song_secs:.0f}s song")
    elif word_tokens and match_ratio >= 0.5:
        scenes, fs, le = _timed_karaoke_scenes(title, word_tokens, fps, song_secs)
        print(f"[zuzu-remotion] WORD-SYNCED karaoke: vocals {fs:.1f}s..{le:.1f}s, "
              f"lyric match {match_ratio:.0%}, {len(scenes)} scenes")
    else:
        scenes = _even_karaoke_scenes(title, cat, lines, song_secs)
        print(f"[zuzu-remotion] even-timed karaoke fallback (lyric match {match_ratio:.0%})")

    W, H = (1080, 1920) if portrait else (1920, 1080)
    return {"title": title, "character": "Zuzu", "color1": C1, "color2": C2,
            "audio": audio_name, "characterImg": char_img, "characterImgs": char_imgs or [],
            "mouthEnv": [], "mouthX": 0.50, "mouthY": 0.47,
            "fps": fps, "width": W, "height": H, "scenes": scenes}


def _default_zuzu_still() -> str:
    """A clean, consistent Zuzu still (from the LoRA dataset) for the character."""
    cands = sorted(glob.glob(str(ROOT / "zuzu_lora" / "dataset" / "zuzu_0*.png")))
    return cands[0] if cands else ""


def _zuzu_poses() -> list:
    """Three varied Zuzu poses -> title / character(SINGING) / outro. The character
    scene uses zuzu_04 (open, happy mouth) so the singing mouth sits naturally."""
    ds = ROOT / "zuzu_lora" / "dataset"
    want = ["zuzu_00.png", "zuzu_04.png", "zuzu_05.png"]  # standing, open-mouth (sings), waving
    picks = [str(ds / w) for w in want if (ds / w).exists()]
    if len(picks) < 3:
        allp = sorted(glob.glob(str(ds / "zuzu_*.png")))
        picks = (allp + allp + allp)[:3]
    return picks


def _word_timings(song_path, initial_prompt="", model_size="small"):
    """Transcribe the ACTUAL sung audio -> real per-word [{word,start,end}] (seconds).
    This is what makes the on-screen karaoke + Zuzu's mouth line up EXACTLY with the
    voice (ACE-Step uses a random seed, so timing is never known ahead). [] on failure.
    Biases recognition with the known lyrics (initial_prompt) for cleaner sung words.
    Uses the RTX 2080 Ti (cuda/float16) when available, falls back to CPU int8."""
    from faster_whisper import WhisperModel
    last = None
    for device, ctype in (("cuda", "float16"), ("cpu", "int8")):
        try:
            model = WhisperModel(model_size, device=device, compute_type=ctype)
            seg_iter, _info = model.transcribe(
                str(song_path), word_timestamps=True,
                initial_prompt=(initial_prompt or None))
            words = []
            for seg in seg_iter:
                for w in (seg.words or []):
                    tok = (w.word or "").strip()
                    if tok and w.start is not None and w.end is not None:
                        words.append({"word": tok, "start": float(w.start), "end": float(w.end)})
            print(f"[zuzu-remotion] transcribed {len(words)} sung words ({device}) for exact sync")
            return words
        except Exception as e:
            last = e
            continue
    print(f"[zuzu-remotion] transcription failed ({last}) — falling back to even karaoke timing")
    return []


def _tokenize_lyrics(lines):
    """Clean, kid-safe lyric tokens with their source-line index."""
    toks = []
    for li, ln in enumerate(lines):
        for w in ln.split():
            toks.append({"text": w, "line": li})
    return toks


def _reconcile(intended, asr, song_secs):
    """Keep the CLEAN intended lyric words but borrow the REAL sung timestamps from the
    ASR, via difflib alignment. Unmatched words get None times (interpolated later).
    Returns (tokens, match_ratio) — match_ratio gates the even-timing fallback."""
    import difflib
    strip = ",.!?¿¡\"'’“”-—…()"
    a = [t["text"].lower().strip(strip) for t in intended]
    b = [(w["word"] or "").lower().strip(strip) for w in asr]
    sm = difflib.SequenceMatcher(a=a, b=b, autojunk=False)
    out, hits = [], 0
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            for k in range(i2 - i1):
                it, wj = intended[i1 + k], asr[j1 + k]
                out.append({"text": it["text"], "line": it["line"],
                            "start": float(wj["start"]), "end": float(wj["end"])})
            hits += (i2 - i1)
        elif tag in ("replace", "delete"):
            for k in range(i1, i2):
                it = intended[k]
                out.append({"text": it["text"], "line": it["line"], "start": None, "end": None})
        # "insert" = ASR ad-lib not in the lyrics -> dropped (mouth still moves via envelope)
    _fill_none_by_interp(out, song_secs)
    return out, hits / max(1, len(intended))


def _fill_none_by_interp(tokens, song_secs):
    """Linearly interpolate any unmatched word's start time from known neighbours, then
    make times monotonic and give each word an end (next word's start). In-place."""
    n = len(tokens)
    if not n:
        return
    anchors = [(i, t["start"]) for i, t in enumerate(tokens) if t["start"] is not None]
    if not anchors:
        for i, t in enumerate(tokens):
            t["start"] = song_secs * i / n
    else:
        if anchors[0][0] != 0:
            anchors = [(0, 0.0)] + anchors
        if anchors[-1][0] != n - 1:
            anchors = anchors + [(n - 1, max(anchors[-1][1], song_secs))]
        ai = 0
        for i in range(n):
            if tokens[i]["start"] is not None:
                continue
            while ai + 1 < len(anchors) and anchors[ai + 1][0] < i:
                ai += 1
            (li, lt), (ri, rt) = anchors[ai], anchors[ai + 1]
            frac = (i - li) / (ri - li) if ri > li else 0.0
            tokens[i]["start"] = lt + (rt - lt) * frac
    for i in range(1, n):                       # enforce monotonic starts
        if tokens[i]["start"] < tokens[i - 1]["start"]:
            tokens[i]["start"] = tokens[i - 1]["start"]
    for i in range(n):                          # ends = up to next start
        nxt = tokens[i + 1]["start"] if i + 1 < n else song_secs
        end = tokens[i]["end"]
        if end is None or end <= tokens[i]["start"]:
            end = min(nxt, tokens[i]["start"] + 0.6)
        tokens[i]["end"] = max(tokens[i]["start"] + 0.08,
                               min(end, nxt if nxt > tokens[i]["start"] else tokens[i]["start"] + 0.3))


def _timed_karaoke_scenes(title, tokens, fps, song_secs, lines_per=2):
    """Build title + word-synced karaoke + outro scenes whose positions match the real
    sung timeline. Each karaoke scene carries `words:[{text,f0,f1,line}]` in GLOBAL frames
    so the highlight AND Zuzu's mouth read the same clock as the audio (which starts at
    video frame 0). Returns (scenes, first_start, last_end)."""
    for t in tokens:
        t["f0"] = int(round(t["start"] * fps))
        t["f1"] = max(t["f0"] + 1, int(round(t["end"] * fps)))
    first_f, last_f = tokens[0]["f0"], tokens[-1]["f1"]
    first_start, last_end = first_f / fps, last_f / fps

    # group tokens by source line, then chunk consecutive lines
    by_line, order = {}, []
    for t in tokens:
        li = t.get("line", 0)
        if li not in by_line:
            by_line[li] = []; order.append(li)
        by_line[li].append(t)
    chunks = [order[i:i + lines_per] for i in range(0, len(order), lines_per)] or [order]

    # pre-roll title occupies exactly [0, first_f) so karaoke starts on the vocal onset
    scenes = [{"type": "title", "text": title[:26], "subtitle": "with Zuzu 🐘",
               "seconds": round(max(0.6, first_f / fps), 3)}]

    chunk_first_f, built = [], []
    for line_idxs in chunks:
        toks = [t for li in line_idxs for t in by_line[li]]
        chunk_first_f.append(toks[0]["f0"])
        local_lines, words = [], []
        for local_i, li in enumerate(line_idxs):
            local_lines.append(" ".join(x["text"] for x in by_line[li]))
            for x in by_line[li]:
                words.append({"text": x["text"], "f0": x["f0"], "f1": x["f1"], "line": local_i})
        built.append((local_lines, words))
    for ci, (local_lines, words) in enumerate(built):
        start_f = chunk_first_f[ci]
        end_f = chunk_first_f[ci + 1] if ci + 1 < len(chunk_first_f) else last_f
        secs = round(max(1.0, (end_f - start_f) / fps), 3)
        scenes.append({"type": "karaoke", "lines": local_lines, "words": words, "seconds": secs})

    scenes.append({"type": "outro", "text": "See you next time! 👋",
                   "seconds": round(max(2.5, song_secs - last_end), 3)})
    return scenes, first_start, last_end


def _audio_envelope(song_path, fps=30, n_frames=None):
    """Per-frame vocal loudness 0..1 from the song — drives Zuzu's singing mouth."""
    try:
        from moviepy import AudioFileClip
        import numpy as np
        with AudioFileClip(str(song_path)) as a:
            dur = a.duration
            arr = a.to_soundarray(fps=16000)
        mono = arr.mean(axis=1) if getattr(arr, "ndim", 1) > 1 else arr
        sr = 16000
        win = max(1, int(sr / fps))
        total = n_frames or int(dur * fps)
        env = []
        for f in range(total):
            seg = mono[f * win: f * win + win]
            env.append(float((seg ** 2).mean() ** 0.5) if len(seg) else 0.0)
        m = max(env) or 1.0
        # normalise, gamma to emphasise sung syllables, clamp
        return [min(1.0, (e / m) ** 0.7 * 1.15) for e in env]
    except Exception as e:
        print(f"[zuzu-remotion] envelope failed ({e}) — no singing mouth")
        return []


# ─────────────────────────────────────────────────────────────────────────────
# NARRATED TEACHING (synced spoken voice)
# For teaching lessons we don't sing a background song the visuals drift against —
# instead we generate a short spoken narration PER teaching scene ("Let's write A.
# A says ah. A is for Apple!"), set each scene's on-screen duration to the length of
# its own narration, and concatenate the clips into one track. Because scene N starts
# exactly when clip N starts, the VOICE and the on-screen teaching beat stay in sync.
# Voice comes from the normal router (RunPod Orpheus warm-teacher when configured,
# else Kokoro af_bella, else edge-tts) via niche="kids_songs".
# ─────────────────────────────────────────────────────────────────────────────
_NUM_WORDS = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight",
              "nine", "ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen",
              "sixteen", "seventeen", "eighteen", "nineteen", "twenty"]


def _ff_exe():
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return "ffmpeg"


def _audio_dur(path) -> float:
    try:
        from moviepy import AudioFileClip
        with AudioFileClip(str(path)) as a:
            return float(a.duration)
    except Exception:
        return 0.0


def _num_word(n: int) -> str:
    return _NUM_WORDS[n] if 0 <= n < len(_NUM_WORDS) else str(n)


def _scene_narration(sc: dict, title: str) -> str:
    """The spoken line for a teaching scene — this is what the child HEARS while the
    matching visual plays, so it must describe exactly what is on screen."""
    t = sc.get("type")
    if t == "title":
        return f"{title}! Let's learn with Zuzu!"
    if t == "phonics":
        L = str(sc.get("letter", "")).upper(); snd = sc.get("sound", ""); w = sc.get("word", "")
        return f"Let's write {L}. {L} says {snd}, {snd}, {snd}. {L} is for {w}!"
    if t == "counting":
        c = int(sc.get("count", 3)); lab = sc.get("label", "")
        if 1 <= c <= 10:
            nums = ", ".join(_num_word(i) for i in range(1, c + 1))
            return f"Let's count! {nums}! {c} {lab}!"
        return f"Let's count to {c}! {c} {lab}!"
    if t == "addition":
        a = int(sc.get("a", 1)); b = int(sc.get("b", 1)); lab = sc.get("label", "")
        return f"{_num_word(a)} plus {_num_word(b)} equals {_num_word(a + b)}! {a + b} {lab}!"
    if t == "outro":
        return "Great job! See you next time!"
    return title


def _concat_padded_audio(items, out_path) -> str | None:
    """items: list of (clip_path, seconds). Pad each clip with trailing silence to its
    scene length, then concatenate into one gapless wav so the audio timeline matches
    the scene timeline exactly. Returns out_path or None."""
    import subprocess
    ff = _ff_exe()
    work = Path(out_path).parent
    parts = []
    for i, (clip, sec) in enumerate(items):
        if not clip or not Path(clip).exists():
            # missing narration -> emit `sec` of pure silence so timing stays aligned
            p = work / f"_pad{i}.wav"
            subprocess.run([ff, "-y", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
                            "-t", f"{sec:.2f}", "-ar", "44100", "-ac", "2", str(p)],
                           capture_output=True)
            parts.append(p); continue
        p = work / f"_pad{i}.wav"
        subprocess.run([ff, "-y", "-i", str(clip), "-af", "apad", "-t", f"{sec:.2f}",
                        "-ar", "44100", "-ac", "2", str(p)], capture_output=True)
        parts.append(p)
    if not parts:
        return None
    lst = work / "_alist.txt"
    lst.write_text("".join(f"file '{p.name}'\n" for p in parts), encoding="utf-8")
    r = subprocess.run([ff, "-y", "-f", "concat", "-safe", "0", "-i", str(lst),
                        "-ar", "44100", "-ac", "2", str(out_path)],
                       capture_output=True, text=True, cwd=str(work))
    return str(out_path) if Path(out_path).exists() and Path(out_path).stat().st_size > 1000 else None


def _render_narrated_learning(lesson: dict, out_path: str, portrait: bool,
                              char_imgs, char_img, target_seconds: float | None = None) -> str | None:
    """Build title + teaching scenes + ONE outro, narrate each, sync durations to the
    narration, concat the audio, and render. This is the synced-voice teaching path.

    A longer video is made by REPEATING THE TEACHING BEATS (repetition helps ages 3-7),
    NOT by duplicating the whole clip — so there is exactly one intro and one goodbye,
    never a stack of repeated 'goodbyes'. Repeated beats reuse the same narration audio,
    so extra length costs no extra voice generation."""
    import asyncio
    title = (lesson.get("title") or "Learn with Zuzu").strip()
    edu = [dict(s) for s in (lesson.get("edu") or []) if s.get("type")]
    if not edu:
        return None
    # how many teaching beats: fill the target (~5s each) or a single pass through edu
    if target_seconds and target_seconds > 0:
        nbeats = max(len(edu), int(round((target_seconds - 6) / 5.0)))
    else:
        nbeats = len(edu)
    scenes = [{"type": "title", "text": title[:26], "subtitle": "with Zuzu 🐘"}]
    for i in range(nbeats):
        scenes.append(dict(edu[i % len(edu)]))          # cycle the teaching beats
    scenes.append({"type": "outro", "text": "Great job! 👋"})   # exactly ONE goodbye

    work = Path(out_path).parent / "narration"
    work.mkdir(parents=True, exist_ok=True)

    async def _gen_all():
        from modules.voice_generator import generate_voice
        cache = {}          # narration text -> audio path; repeated beats reuse the clip
        clips = []
        for sc in scenes:
            txt = _scene_narration(sc, title)
            if txt in cache:
                clips.append(cache[txt]); continue
            try:
                res = await generate_voice(txt, work, f"nar{len(cache)}", format_type="short", niche="kids_songs")
                ap = res.get("audio_path") if res else None
            except Exception as e:
                print(f"[zuzu-remotion] narration failed ({e})"); ap = None
            cache[txt] = ap; clips.append(ap)
        return clips

    clips = asyncio.run(_gen_all())

    # scene length = its narration length (+ a short breath), so voice & visual stay locked
    total = 0.0
    for sc, clip in zip(scenes, clips):
        d = _audio_dur(clip) if clip else 0.0
        sc["seconds"] = round(max(1.8, d) + 0.35, 2)
        total += sc["seconds"]

    audio_path = _concat_padded_audio([(c, sc["seconds"]) for sc, c in zip(scenes, clips)],
                                      work / "narration.wav")

    W, H = (1080, 1920) if portrait else (1920, 1080)
    # Teaching cards are text/emoji only (no character stills) — keeps the render fast and
    # reliable, and the teaching scenes are the content. (Mascot on title/outro is a future
    # enhancement once the Remotion image-load timeout is raised.)
    rl = {"title": title, "character": "Zuzu", "color1": C1, "color2": C2,
          "audio": audio_path or "", "characterImg": "",
          "characterImgs": [], "mouthEnv": [], "mouthX": 0.50, "mouthY": 0.47,
          "fps": 30, "width": W, "height": H, "scenes": scenes}
    print(f"[zuzu-remotion] NARRATED teaching: {len(scenes)} scenes, ~{total:.0f}s, "
          f"synced voice{' + audio' if audio_path else ' (SILENT — narration failed)'}")
    assets = {"audio": audio_path} if audio_path else None
    return render_episode(rl, out_path, assets=assets)


def render_zuzu_remotion(lesson: dict, song_path: str, out_path: str, char_clip: str = "",
                         char_img: str | None = None, char_imgs=None, portrait: bool = False,
                         target_seconds: float | None = None) -> str | None:
    if char_imgs is None:
        char_imgs = _zuzu_poses()
    if char_img is None:
        char_img = (char_imgs[0] if char_imgs else _default_zuzu_still())

    # Teaching lessons -> synced spoken narration (one clip per scene) instead of a
    # background song the visuals drift against. target_seconds fills length by REPEATING
    # teaching beats (single intro/outro), not by duplicating the whole clip.
    if _is_learn(lesson):
        return _render_narrated_learning(lesson, out_path, portrait, char_imgs, char_img,
                                         target_seconds=target_seconds)

    secs = _song_seconds(song_path)

    # Transcribe the ACTUAL sung audio -> real per-word times, reconciled against the clean
    # known lyrics, so the karaoke highlight + Zuzu's mouth match the voice exactly.
    raw = (lesson.get("lyrics") or "")
    clean_lines = [ln.strip() for ln in raw.replace("[verse]", "").replace("[chorus]", "")
                   .replace("[bridge]", "").splitlines() if ln.strip()]
    tokens, ratio = [], 0.0
    if not _is_learn(lesson) and song_path and Path(song_path).exists() and clean_lines:
        try:
            asr = _word_timings(song_path, initial_prompt=" ".join(clean_lines))
            if asr:
                tokens, ratio = _reconcile(_tokenize_lyrics(clean_lines), asr, secs)
        except Exception as e:
            print(f"[zuzu-remotion] sync prep failed ({e}) — even timing")
            tokens, ratio = [], 0.0

    rl = build_remotion_lesson(lesson, song_secs=secs, char_clip=char_clip, char_img=char_img,
                               char_imgs=char_imgs, portrait=portrait,
                               word_tokens=tokens, match_ratio=ratio, fps=30)
    total = sum(s["seconds"] for s in rl["scenes"])
    if song_path and Path(song_path).exists():
        rl["mouthEnv"] = _audio_envelope(song_path, fps=rl["fps"], n_frames=int(total * rl["fps"]))
    print(f"[zuzu-remotion] '{lesson.get('title')}' | song {secs:.0f}s | {len(rl['scenes'])} scenes | "
          f"{total:.0f}s video | mouthEnv {len(rl['mouthEnv'])} frames (singing)")
    assets = {"audio": song_path} if song_path and Path(song_path).exists() else None
    return render_episode(rl, out_path, assets=assets)


if __name__ == "__main__":
    from modules.zuzu_lessons import LESSONS
    lid = sys.argv[1] if len(sys.argv) > 1 else "abc"
    lesson = next((l for l in LESSONS if l.get("id") == lid), LESSONS[0])
    if len(sys.argv) > 2:
        song = sys.argv[2]
    else:
        songs = sorted(glob.glob("output/zuzu/*/song.wav"), key=os.path.getmtime, reverse=True)
        # prefer a song from the same lesson id if present
        song = next((s for s in songs if lid in s), songs[0] if songs else "")
    out = f"output/zuzu_remotion/{lesson['id']}_episode.mp4"
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    print("RESULT:", render_zuzu_remotion(lesson, song, out))
