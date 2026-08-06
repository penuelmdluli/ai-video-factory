#!/usr/bin/env python
"""Zuzu & Friends — auto-pipeline.

Produces ONE edutainment video end-to-end and posts it:
  pick lesson -> 6 landscape images (local SDXL) -> animate each (RunPod LTX i2v)
  -> sung song (durable ACE-Step) -> captions -> 16:9 long-form + 9:16 Short
  -> post to YouTube (kids_songs) + Facebook (Mzansi Baby Stars / blissful_moments).

Usage:
  python make_zuzu.py                 # next lesson, produce + post 16:9 and Short
  python make_zuzu.py --lesson abc    # a specific lesson
  python make_zuzu.py --dry-run       # produce but DON'T post
  python make_zuzu.py --no-short      # skip the Short
"""
import os, sys, json, time, base64, subprocess, argparse, asyncio, random
from pathlib import Path

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))
from modules.zuzu_lessons import LESSONS, ZUZU, STYLE, get_lesson
from modules.zuzu_generator import generate_lesson, build_description

ENG = ROOT / "zuzu_engine"
ACEPY = ENG / "acestep_venv" / "Scripts" / "python.exe"
ACEMODEL = ENG / "models"
ACEGEN = ENG / "acestep_gen.py"
STATE = ENG / "state.json"

def _env(key):
    for line in (ROOT / ".env").read_text().splitlines():
        if line.startswith(key + "="):
            return line.split("=", 1)[1].strip().strip("'").strip('"')
    return os.getenv(key, "")

RUNPOD_KEY = _env("RUNPOD_API_KEY")
EP_LTX = "https://api.runpod.ai/v2/mp2awqavthuc2b"
NEG_IMG = ("scary, creepy, deformed, extra limbs, two trunks, mutated, ugly, blurry, "
           "text, watermark, realistic photo, human, adult, weapon, dark")
NEG_VID = "distortion, warping, morphing, extra limbs, deformed, flicker, jitter, blurry"

def log(m): print(f"[zuzu] {m}", flush=True)

# Playlists (discovery + session time). Every video -> main; + a topic playlist.
PLAYLISTS = {
    "main":     "PLZa1ZtuM9pzc",   # Nursery Rhymes & Kids Songs
    "learning": "PLCV4FgxG3s4Y",   # ABC, Numbers, Colors, Shapes
    "bedtime":  "PLT2cRq47h1mU",   # Bedtime Lullabies
    "animals":  "PLbK6aA8M-m9A",   # Animal Songs
}
def _playlists_for(category):
    c = (category or "").lower()
    pls = [PLAYLISTS["main"]]
    if any(k in c for k in ["letter", "number", "color", "colour", "shape", "abc", "count", "learn"]):
        pls.append(PLAYLISTS["learning"])
    elif any(k in c for k in ["bedtime", "lullaby", "sleep", "night"]):
        pls.append(PLAYLISTS["bedtime"])
    elif "animal" in c:
        pls.append(PLAYLISTS["animals"])
    return pls

def add_to_playlists(video_id, category):
    if not video_id:
        return
    try:
        from modules.uploader_youtube import _get_youtube_service
        yt = _get_youtube_service("kids_songs")
        for pl in _playlists_for(category):
            try:
                yt.playlistItems().insert(part="snippet", body={"snippet": {
                    "playlistId": pl, "resourceId": {"kind": "youtube#video", "videoId": video_id}}}).execute()
            except Exception as e:
                log(f"playlist {pl} add failed: {str(e)[:60]}")
        log(f"added {video_id} to {len(_playlists_for(category))} playlists")
    except Exception as e:
        log(f"playlist add skipped: {e}")

def set_video_thumbnail(video_id, thumb_path):
    if not video_id or not thumb_path or not Path(thumb_path).exists():
        return
    try:
        from modules.uploader_youtube import _get_youtube_service
        from googleapiclient.http import MediaFileUpload
        yt = _get_youtube_service("kids_songs")
        yt.thumbnails().set(videoId=video_id,
                            media_body=MediaFileUpload(str(thumb_path), mimetype="image/jpeg")).execute()
        log(f"custom thumbnail set for {video_id}")
    except Exception as e:
        log(f"thumbnail set skipped: {str(e)[:80]}")

def _ff():
    try:
        import imageio_ffmpeg; return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return "ffmpeg"
FF = _ff()

def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        log("FFMPEG ERR: " + " ".join(map(str, cmd))[:110]); print(r.stderr[-700:])
        raise SystemExit(1)

def dur(p):
    return float(subprocess.run(["ffprobe","-v","error","-show_entries","format=duration",
           "-of","default=nk=1:nw=1", str(p)], capture_output=True, text=True).stdout.strip())

# ---------- 1. pick lesson ----------
def _normalize_static(l):
    """Make a static library lesson look like a dynamic one."""
    l = dict(l)
    l.setdefault("star_id", "zuzu"); l.setdefault("star_name", "Zuzu")
    l["star_desc"] = ZUZU; l["star_seed"] = 777
    l["scene_prompts"] = [f"{ZUZU}, {s}, {STYLE}" for s in l["scenes"][:6]]
    return l

def get_lesson_for_run(forced=None, use_static=False):
    if forced:                                   # a specific static lesson (testing)
        l = get_lesson(forced)
        if not l: raise SystemExit(f"unknown lesson {forced}")
        return _normalize_static(l)
    if use_static:                               # rotate the fixed library
        # Only REVIEWED lessons auto-rotate — keeps unverified content (e.g. SA-language
        # lessons pending native-speaker check) from ever auto-posting.
        pool = [l for l in LESSONS if l.get("reviewed", True)]
        idx = 0
        if STATE.exists():
            try: idx = json.loads(STATE.read_text()).get("next", 0)
            except Exception: idx = 0
        STATE.write_text(json.dumps({"next": (idx + 1) % max(1, len(pool))}))
        return _normalize_static(pool[idx % len(pool)])
    return generate_lesson()                     # DEFAULT: fresh dynamic lesson

# ---------- 2. images (local SDXL, 16:9) ----------
def gen_images(lesson, out):
    import torch
    from diffusers import StableDiffusionXLPipeline, EulerDiscreteScheduler
    log("loading SDXL...")
    pipe = StableDiffusionXLPipeline.from_pretrained(
        "stabilityai/stable-diffusion-xl-base-1.0",
        torch_dtype=torch.float16, variant="fp16", use_safetensors=True)
    pipe.scheduler = EulerDiscreteScheduler.from_config(pipe.scheduler.config)
    pipe = pipe.to("cuda"); pipe.vae.enable_tiling()
    paths = []
    prompts = lesson["scene_prompts"]
    for i, prompt in enumerate(prompts):
        g = torch.Generator(device="cuda").manual_seed(lesson["star_seed"])
        with torch.inference_mode():
            img = pipe(prompt=prompt, negative_prompt=NEG_IMG, width=1344, height=768,
                       num_inference_steps=26, guidance_scale=6.5, generator=g).images[0]
        p = out / f"img{i}.png"; img.save(str(p)); paths.append(p)
        log(f"image {i+1}/{len(prompts)}")
    del pipe
    try:
        import torch; torch.cuda.empty_cache()
    except Exception: pass
    return paths

# ---------- 3. animate each (RunPod LTX i2v) ----------
def animate(img_path, motion, out_path):
    import requests
    H = {"Authorization": "Bearer " + RUNPOD_KEY, "Content-Type": "application/json"}
    b64 = base64.b64encode(Path(img_path).read_bytes()).decode()
    payload = {"image": b64,
               "prompt": f"a cute cartoon baby elephant, {motion}, smooth calm gentle motion, high quality kids animation",
               "negative_prompt": NEG_VID, "width": 832, "height": 480,
               "num_frames": 121, "fps": 24, "steps": 40, "seed": 7}
    jid = requests.post(f"{EP_LTX}/run", headers=H, json={"input": payload}, timeout=90).json().get("id")
    t0 = time.time()
    while time.time() - t0 < 900:
        time.sleep(12)
        s = requests.get(f"{EP_LTX}/status/{jid}", headers=H, timeout=30).json()
        st = s.get("status")
        if st == "COMPLETED":
            o = s.get("output") or {}
            if o.get("video_base64"):
                Path(out_path).write_bytes(base64.b64decode(o["video_base64"])); return True
            return False
        if st in ("FAILED", "TIMED_OUT", "CANCELLED"):
            log(f"animate {st}"); return False
    return False

MOTIONS = ["gently sways and blinks, ears wiggle","looks around in wonder, blinks, gentle sway",
           "bounces happily, points, blinks","sways gently, soft breathing, blinks",
           "claps and cheers gently, blinks","gentle sway, soft happy motion, blinks"]

# ---------- 4. song (durable ACE-Step) ----------
def gen_song(lesson, out):
    lyr = out / "lyrics.txt"; lyr.write_text(lesson["lyrics"], encoding="utf-8")
    song = out / "song.wav"
    if not ACEPY.exists():
        log("ACE-Step engine missing -> cannot make song"); return None
    seed = str(random.randint(1, 999999))   # random melody each time = song variety
    r = subprocess.run([str(ACEPY), str(ACEGEN), "--prompt", lesson["song_prompt"],
                        "--lyrics", str(lyr), "--out", str(song),
                        "--model", str(ACEMODEL), "--duration", "45", "--seed", seed],
                       capture_output=True, text=True, timeout=1800)
    if "SONG_OK" in (r.stdout or "") and song.exists():
        return song
    log("song failed: " + (r.stdout or "")[-200:] + (r.stderr or "")[-200:]); return None

# ---------- 5. captions (ASS, top sky) ----------
def make_ass(chunks, total, path):
    n = len(chunks); per = total / n
    def ts(t):
        h=int(t//3600); m=int((t%3600)//60); s=t%60; return f"{h:01d}:{m:02d}:{s:05.2f}"
    a = ["[Script Info]","ScriptType: v4.00+","PlayResX: 1920","PlayResY: 1080","WrapStyle: 2","",
     "[V4+ Styles]",
     "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
     "Style: Zuzu,Comic Sans MS,58,&H00FFFFFF,&H000000FF,&H00B05078,&H64000000,-1,0,0,0,100,100,0,0,1,5,2,8,60,60,60,1","",
     "[Events]","Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text"]
    for i, txt in enumerate(chunks):
        a.append(f"Dialogue: 0,{ts(i*per)},{ts((i+1)*per)},Zuzu,,0,0,0,,{txt}")
    Path(path).write_text("\n".join(a), encoding="utf-8")

# ---------- 6. assemble 16:9 ----------
def assemble(clips, song, chunks, work, out16):
    song_d = dur(song); n = len(clips); per = song_d / n
    norm = []
    for i, c in enumerate(clips):
        cd = dur(c); f = per / cd
        n_ = work / f"n{i}.mp4"
        run([FF,"-y","-i",str(c),"-an","-filter_complex",
             f"setpts={f:.4f}*PTS,scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080,fps=24",
             "-c:v","libx264","-pix_fmt","yuv420p",str(n_)]); norm.append(n_)
    lst = work / "list.txt"; lst.write_text("".join(f"file '{p.name}'\n" for p in norm))
    joined = work / "joined.mp4"
    run([FF,"-y","-f","concat","-safe","0","-i",str(lst),"-c","copy",str(joined)])
    ass = work / "cap.ass"; make_ass(chunks, song_d, ass)
    os.chdir(work)
    run([FF,"-y","-i","joined.mp4","-i",str(song),"-vf","subtitles=cap.ass",
         "-map","0:v","-map","1:a","-shortest","-c:v","libx264","-pix_fmt","yuv420p",
         "-c:a","aac","-b:a","192k",str(out16)])
    os.chdir(ROOT)

# ---------- 7. Short (9:16 from center) ----------
def make_short(video16, out9, seconds=50):
    run([FF,"-y","-t",str(seconds),"-i",str(video16),
         "-vf","crop=ih*9/16:ih,scale=1080:1920,fps=24","-c:v","libx264","-pix_fmt","yuv420p",
         "-c:a","aac","-b:a","192k",str(out9)])

# ---------- 7b. Loop to length (watch-time, $0 — nursery rhymes repeat) ----------
def loop_to_length(src, out, target_seconds=170):
    import math
    d = dur(src)
    if d <= 0:
        return str(src)
    loops = max(1, math.ceil(target_seconds / d))   # total plays to reach target
    run([FF,"-y","-stream_loop",str(loops-1),"-i",str(src),"-c","copy",str(out)])
    return str(out)

# ---------- 8. post ----------
async def post(video, short, lesson, do_short, thumb=None):
    from modules.uploader_youtube import upload_to_youtube
    from modules.uploader_facebook import upload_to_facebook
    desc = build_description(lesson)
    title = f"{lesson['title']} ⭐ Zuzu & Friends | Kids Learning Songs & Nursery Rhymes"[:100]
    res = {}
    res["yt_long"] = await upload_to_youtube(str(video), title, desc, lesson["tags"],
                        niche="kids_songs", is_short=False, privacy="public")
    log(f"YT long: {res['yt_long'].get('url', res['yt_long'])}")
    _vid = (res.get("yt_long") or {}).get("video_id")
    add_to_playlists(_vid, lesson.get("category", ""))
    set_video_thumbnail(_vid, thumb)
    # Facebook (Mzansi Baby Stars) = REELS only (<=90s, vertical). ALWAYS post the
    # SHORT vertical clip — NEVER fall back to the 3-min long-form (that fails the
    # Reel format and nothing lands on the page).
    try:
        if short and Path(short).exists():
            res["fb"] = await upload_to_facebook(str(short), title, desc,
                                                 niche="blissful_moments", is_reel=True)
            log(f"FB reel: {res['fb'].get('status', res['fb'])}")
        else:
            log("FB reel SKIPPED: no vertical short available (reels must be <=90s, 9:16)")
    except Exception as e:
        log(f"FB post error: {e}")
    if do_short and short and Path(short).exists():
        stitle = f"{lesson['title']} ⭐ Zuzu #shorts #kids #nurseryrhymes"[:100]
        res["yt_short"] = await upload_to_youtube(str(short), stitle, desc, lesson["tags"],
                            niche="kids_songs", is_short=True, privacy="public")
        log(f"YT short: {res['yt_short'].get('url', res['yt_short'])}")
    return res

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lesson"); ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--no-short", action="store_true")
    ap.add_argument("--static", action="store_true", help="rotate fixed library instead of dynamic")
    ap.add_argument("--remotion", action="store_true",
                    help="render a crisp programmatic Remotion episode instead of SDXL->LTX (no GPU wobble)")
    a = ap.parse_args()

    lesson = get_lesson_for_run(a.lesson, a.static)
    stamp = time.strftime("%Y%m%d_%H%M%S")
    work = ROOT / "output" / "zuzu" / f"{lesson['id']}_{stamp}"; work.mkdir(parents=True, exist_ok=True)
    log(f"LESSON: {lesson['title']} ({lesson['id']}) star={lesson.get('star_name')} "
        f"setting={lesson.get('setting','')[:30]}  ->  {work}")

    out16 = work / f"{lesson['id']}_16x9.mp4"
    # Teaching lessons on the Remotion path narrate each scene with a synced spoken
    # voice (generated inside render_zuzu_remotion) — no background song needed.
    learn_remotion = a.remotion and bool(lesson.get("edu"))
    if learn_remotion:
        song = ""
        log("STAGE narration (learning lesson — spoken teacher voice, synced per teaching beat)")
    else:
        log("STAGE song"); song = gen_song(lesson, work)
        if not song: raise SystemExit("no song — abort")
    imgs = []
    _remotion_short = None
    if a.remotion:
        # Crisp programmatic episode via Remotion — no SDXL/LTX, no GPU wobble, word-synced
        # karaoke. Render 16:9 (YT long) AND a NATIVE 9:16 reel (no crop that cuts Zuzu off).
        log("STAGE remotion render (16:9 + native 9:16 reel)")
        from zuzu_remotion import render_zuzu_remotion
        # Teaching lessons render the long (16:9) at ~60s and the short (9:16) at ~35s
        # DIRECTLY, by repeating teaching beats with one intro + one outro — so no
        # whole-clip loop that would stack repeated goodbyes.
        _long_t = 60 if learn_remotion else None
        _short_t = 35 if learn_remotion else None
        if not render_zuzu_remotion(lesson, str(song), str(out16), target_seconds=_long_t):
            raise SystemExit("remotion render failed")
        if not a.no_short:
            _rs = work / f"{lesson['id']}_short.mp4"
            _remotion_short = str(_rs) if render_zuzu_remotion(lesson, str(song), str(_rs), portrait=True, target_seconds=_short_t) else None
    else:
        log("STAGE 1/4 images"); imgs = gen_images(lesson, work)
        log("STAGE 2/4 animate")
        clips = []
        for i, img in enumerate(imgs):
            cp = work / f"clip{i}.mp4"
            ok = animate(img, MOTIONS[i % len(MOTIONS)], cp)
            clips.append(cp if ok else None)
            log(f"  clip {i+1}/{len(imgs)} {'ok' if ok else 'FAILED'}")
        clips = [c for c in clips if c]
        if len(clips) < 4: raise SystemExit(f"only {len(clips)} clips — abort")
        log("STAGE assemble")
        assemble(clips, song, lesson["captions"][:len(clips)*2], work, out16)
    short = None
    if not a.no_short:
        if _remotion_short and Path(_remotion_short).exists():
            short = Path(_remotion_short)   # native 9:16 reel — no crop
        else:
            short = work / f"{lesson['id']}_short.mp4"; make_short(out16, short)
    # Loop the song to ~3 min for watch-time (nursery rhymes repeat — $0, no re-render).
    # Teaching lessons are already rendered at their full length (beats repeated inside a
    # single render with one outro), so we DON'T whole-clip loop them — that would stack
    # repeated goodbyes.
    out_long = work / f"{lesson['id']}_16x9_long.mp4"
    if learn_remotion:
        out_long = out16
    else:
        loop_to_length(out16, out_long, 170)
    # auto thumbnail — bright hero scene + big title (needs verified channel to upload)
    thumb = None
    try:
        from modules.zuzu_thumbnail import make_thumbnail
        hero = None
        if imgs:
            hero = str(imgs[0])
        elif Path(out16).exists():
            # Remotion path has no SDXL stills — grab a bright teaching frame from the render
            hero = str(work / "hero.png")
            run([FF, "-y", "-ss", "3", "-i", str(out16), "-frames:v", "1", hero])
        if hero and Path(hero).exists():
            thumb = str(work / "thumb.jpg"); make_thumbnail(hero, lesson["title"], thumb)
    except Exception as e:
        log(f"thumbnail gen skipped: {e}")
    _lennote = "teaching, single outro" if learn_remotion else "looped ~3min"
    log(f"BUILT: {out_long} ({_lennote}) + {short}" + (" + thumb" if thumb else ""))
    if a.dry_run:
        log("DRY-RUN — not posting."); return
    log("STAGE 5/5 post"); asyncio.run(post(str(out_long), short, lesson, not a.no_short, thumb=thumb))
    log("DONE")

if __name__ == "__main__":
    main()
