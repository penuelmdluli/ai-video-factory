#!/usr/bin/env python
"""Focus / Study / Sleep / Meditation music channel — the ultra-cheap passive play.

One short AI music loop (MusicGen) + one calming, subtly-animated visual (SDXL -> LTX i2v),
looped to HOURS with ffmpeg. ~$0.10 for a 1-hour video; earns on long-watch mid-roll ads.
Reuses runpod-music + SDXL + LTX i2v + ffmpeg + the uploader.

Usage:
  python make_music.py --type sleep --minutes 60         # build + (later) post
  python make_music.py --type study --minutes 3 --dry-run # quick test, no post
"""
import os, sys, json, base64, time, subprocess, argparse, asyncio, random
from pathlib import Path

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

def _env(k):
    for line in (ROOT / ".env").read_text().splitlines():
        if line.startswith(k + "="):
            return line.split("=", 1)[1].strip().strip("'").strip('"')
    return os.getenv(k, "")

import requests
KEY = _env("RUNPOD_API_KEY")
EP_MUSIC = "https://api.runpod.ai/v2/b13hwup9d6179v"

def _ff():
    try:
        import imageio_ffmpeg; return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return "ffmpeg"
FF = _ff()
def log(m): print(f"[music] {m}", flush=True)
def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        log("FFMPEG ERR " + " ".join(map(str, cmd))[:100]); print(r.stderr[-600:]); raise SystemExit(1)
def dur(p):
    return float(subprocess.run(["ffprobe","-v","error","-show_entries","format=duration",
           "-of","default=nk=1:nw=1", str(p)], capture_output=True, text=True).stdout.strip() or 0)

CONTENT = {
 "sleep": {
   "title": "Deep Sleep Music • Fall Asleep Fast • Calm Relaxing Sleep",
   "music": "calm deep sleep music, 50 bpm, soft evolving ambient pads with warm reverb, gentle slow piano with sustain pedal, dreamy ethereal texture, binaural undertone, soothing, no drums, no percussion, peaceful",
   "visual": "a cozy dark bedroom at night, soft warm lamp glow, a big window with a starry night sky and a glowing moon, calm and peaceful, soft 3D cozy render, dreamy",
   "motion": "stars gently twinkling, soft clouds drifting slowly past the moon, very slow calm dreamy motion",
   "tags": ["sleep music","deep sleep","relaxing music","calm music","insomnia","fall asleep fast","sleeping music","meditation"]},
 "study": {
   "title": "Lofi Study Beats • Focus & Concentration • Chill Study Music",
   "music": "lofi hip hop study beats, chill mellow, 75 bpm, soft jazzy piano chords with warm analog bass, vinyl crackle and tape hiss, side-chain compression, mellow Rhodes keys, boom bap drums with soft kick, relaxed groove",
   "visual": "a cozy study desk at night by a window, warm desk lamp, books and a plant, rain on the window with soft city lights, lofi aesthetic, cozy 3D render",
   "motion": "soft rain running down the window, gentle steam rising from a warm cup, cozy calm subtle motion",
   "tags": ["lofi","study music","study beats","focus music","concentration","lofi hip hop","chill beats","relaxing"]},
 "focus": {
   "title": "Deep Focus Music • Concentration & Productivity • Ambient",
   "music": "deep focus ambient music, 60 bpm, minimal and spacious, warm evolving pads with slow filter sweep, subtle rhythmic pulse, granular texture, no drums, calm steady atmosphere, Brian Eno inspired, for concentration",
   "visual": "a calm minimal abstract scene, soft flowing gradients of blue and purple, gentle glowing particles, clean and serene, ambient",
   "motion": "soft glowing particles drifting slowly, gentle flowing gradient light, calm steady motion",
   "tags": ["focus music","deep focus","concentration music","ambient","productivity","work music","study","calm"]},
 "meditation": {
   "title": "Meditation Music • Calm Your Mind • Stress Relief & Healing",
   "music": "calm meditation music, 55 bpm, resonant tibetan singing bowls with long sustain, gentle bamboo flute melody, warm ambient drone in C major, peaceful healing frequencies, 432 Hz tuning feel, no drums, no percussion",
   "visual": "a serene zen scene at dawn, misty calm lake, soft mountains, a single glowing lantern, peaceful nature, soft 3D render",
   "motion": "soft mist drifting over the calm water, gentle ripples, slow peaceful dawn light, very calm motion",
   "tags": ["meditation music","meditation","calm music","stress relief","healing music","relaxing","zen","mindfulness"]},
 "rain": {
   "title": "Rain Sounds for Sleep • Relaxing Rain on Window • Sleep & Focus",
   "music": "gentle steady rain sounds with rich detail, soft rainfall ambience on rooftop, distant rumbling soft thunder, subtle wind, layered rain textures close and far, calm soothing ASMR quality, binaural, for sleep and focus",
   "visual": "rain streaming down a dark window at night, blurred warm city lights beyond, cozy and moody, soft cinematic 3D render",
   "motion": "heavy rain running down the window glass, blurred lights flickering softly, cozy rainy night motion",
   "tags": ["rain sounds","rain for sleeping","relaxing rain","rain on window","sleep sounds","white noise","calm","asmr"]},
 "coding": {
   "title": "Coding Music • Deep Focus for Programmers • Ambient Beats",
   "music": "deep coding focus music, 100 bpm, minimal techy ambient, steady electronic pulse with sidechain, warm analog synth pads, subtle glitchy textures, Boards of Canada influenced, clean and spacious mix, for programming and deep work",
   "visual": "a dark coder's desk at night with multiple monitors showing code, soft RGB glow, a plant, moody tech aesthetic, cinematic 3D render",
   "motion": "soft screen glow flickering gently, code scrolling very slowly, calm moody tech slow motion",
   "tags": ["coding music","programming music","music for coding","deep focus","developer music","ambient coding","concentration","work music"]},
 "work": {
   "title": "Work Music • Productivity & Concentration • Focus Beats",
   "music": "productive work music, 105 bpm, calm uplifting focus beats, steady gentle rhythm with crisp hi-hats, warm motivating piano melody, soft bass groove, positive energy, corporate but soulful, clean professional mix, for work and study",
   "visual": "a bright modern minimal workspace, clean desk, a plant, big window with soft daylight, calm productive aesthetic, 3D render",
   "motion": "soft daylight shifting gently, subtle dust motes floating, calm productive slow motion",
   "tags": ["work music","productivity music","focus music","concentration","office music","study music","deep work","motivation"]},
 "chill": {
   "title": "Chill Music • Relax & Unwind • Chillout Ambient Vibes",
   "music": "chillout music, 90 bpm, relaxed downtempo groove, warm mellow analog synth, soft jazzy chords, gentle beat with brushed snare, calm golden hour evening vibe, Tycho inspired, easy listening, wide stereo mix",
   "visual": "a cozy balcony at sunset with warm string lights, plants and a calm city view, chill relaxed aesthetic, soft 3D render",
   "motion": "warm string lights glowing softly, a gentle breeze, calm golden sunset slow motion",
   "tags": ["chill music","chillout","relaxing music","lofi chill","ambient chill","evening vibes","calm","unwind"]},
}

# Multiple visuals per type (rotated randomly) so the channel never looks repetitive.
VISUALS = {
 "sleep": [
   ("a cozy dark bedroom at night, soft warm lamp glow, a big window with a starry sky and glowing moon, calm peaceful, soft 3D cozy render", "stars gently twinkling, soft clouds drifting slowly past the moon, very slow dreamy motion"),
   ("a crackling fireplace in a cozy dark cabin at night, warm orange glow, soft blankets, peaceful", "flames flickering very softly, warm embers glowing, cozy calm slow motion"),
   ("a calm starry night sky over still mountains and a glassy lake, big soft moon, deep blue, serene", "stars twinkling slowly, gentle mist over the water, very slow peaceful motion"),
   ("soft glowing clouds drifting under a huge full moon, dreamy night sky, deep blue and purple, ethereal", "clouds drifting very slowly across the moon, soft dreamy slow motion"),
 ],
 "study": [
   ("a cozy study desk at night by a window, warm desk lamp, books and a plant, rain on the window with soft city lights, lofi aesthetic, cozy 3D render", "soft rain running down the window, gentle steam rising from a warm cup, cozy slow motion"),
   ("a warm cozy coffee-shop corner at night, soft lamps, plants, a window with rain, lofi aesthetic", "soft rain on the glass, gentle steam, warm cozy slow motion"),
   ("a cozy library nook, warm reading lamps, tall bookshelves, a rainy window, calm lofi mood", "soft rain outside, gentle warm light flicker, calm slow motion"),
 ],
 "focus": [
   ("a calm minimal abstract scene, soft flowing gradients of blue and purple, gentle glowing particles, clean serene ambient", "soft glowing particles drifting slowly, gentle flowing gradient light, calm slow motion"),
   ("a minimal modern desk by a bright window, one plant, soft morning light, clean and calm", "soft light shifting gently, dust motes floating slowly, calm slow motion"),
   ("flowing liquid light in deep blue and teal, smooth minimal abstract, serene and clean", "smooth slow flowing light waves, gentle calm slow motion"),
 ],
 "meditation": [
   ("a serene zen scene at dawn, misty calm lake, soft mountains, a single glowing lantern, peaceful nature, soft 3D render", "soft mist drifting over calm water, gentle ripples, slow peaceful dawn motion"),
   ("a peaceful zen garden with raked sand, smooth stones and a small bonsai, soft morning light, calm", "soft light shifting slowly, gentle drifting mist, very slow calm motion"),
   ("a single lotus flower floating on still calm water, soft glowing light, serene and minimal", "gentle ripples spreading slowly on the water, soft slow calm motion"),
 ],
 "rain": [
   ("rain streaming down a dark window at night, blurred warm city lights beyond, cozy moody, soft cinematic 3D render", "heavy rain running down the window glass, blurred lights flickering softly, cozy rainy slow motion"),
   ("rain on a cozy cabin window with a misty forest beyond, warm interior glow, moody and calm", "steady rain on the glass, gentle mist in the forest, cozy slow motion"),
   ("rain falling over a calm misty forest at dusk, soft grey-blue light, peaceful and moody", "steady rain falling, soft drifting mist, calm slow motion"),
 ],
 "coding": [
   ("a dark coder desk at night with multiple monitors showing glowing code, soft RGB backlight, a plant, moody cinematic tech aesthetic", "code scrolling very slowly, soft RGB glow pulsing gently, calm tech slow motion"),
   ("a moody home office at night, a laptop glowing, city lights through a rainy window, developer vibe", "soft screen glow, gentle rain on the window, calm slow motion"),
   ("a futuristic minimal desk with a holographic code display, deep blue glow, clean tech, cinematic", "soft holographic light drifting, gentle glow pulse, calm slow motion"),
 ],
 "work": [
   ("a bright modern minimal workspace, clean desk with a laptop and a plant, big window with soft daylight, calm productive", "soft daylight shifting gently, dust motes floating slowly, calm productive slow motion"),
   ("a cozy cafe workspace with a laptop, warm light, plants and a window, focused calm mood", "soft warm light, gentle steam from a cup, calm slow motion"),
   ("a sunlit desk by a window overlooking green trees, clean and calm, motivating morning light", "soft morning light shifting, leaves swaying gently outside, calm slow motion"),
 ],
 "chill": [
   ("a cozy balcony at golden sunset with warm string lights, plants and a calm city view, chill relaxed aesthetic", "warm string lights glowing softly, gentle breeze, golden sunset slow motion"),
   ("a relaxed rooftop at dusk with soft cushions, warm lanterns and a purple sky, chill vibe", "soft lanterns glowing, calm dusk sky shifting, gentle slow motion"),
   ("a calm beach at sunset with soft waves and warm orange sky, peaceful chill mood", "soft waves rolling in slowly, warm sunset light, calm slow motion"),
 ],
}

def gen_music_clip(prompt, out, seed):
    H = {"Authorization": "Bearer " + KEY, "Content-Type": "application/json"}
    payload = {"prompt": prompt, "duration": 29, "seed": seed}
    jid = requests.post(f"{EP_MUSIC}/run", headers=H, json={"input": payload}, timeout=90).json().get("id")
    t0 = time.time()
    while time.time() - t0 < 600:
        time.sleep(8)
        s = requests.get(f"{EP_MUSIC}/status/{jid}", headers=H, timeout=30).json()
        if s.get("status") == "COMPLETED":
            o = s.get("output") or {}
            if o.get("audio_base64"):
                Path(out).write_bytes(base64.b64decode(o["audio_base64"])); return str(out)
            return None
        if s.get("status") in ("FAILED", "TIMED_OUT", "CANCELLED"):
            return None
    return None

def gen_music_ace(prompt, out, seed):
    """Try local ACE-Step engine first (free, faster). Returns path or None."""
    acepy = ROOT / "zuzu_engine" / "acestep_venv" / "Scripts" / "python.exe"
    acegen = ROOT / "zuzu_engine" / "acestep_gen.py"
    acemodel = ROOT / "zuzu_engine" / "models"
    if not (acepy.exists() and acegen.exists() and acemodel.exists()):
        return None
    lyr = Path(out).parent / "_instrumental.txt"
    if not lyr.exists():
        lyr.write_text("[instrumental]", encoding="utf-8")
    try:
        r = subprocess.run(
            [str(acepy), str(acegen), "--prompt", prompt, "--lyrics", str(lyr),
             "--out", str(out), "--model", str(acemodel),
             "--duration", "45", "--seed", str(seed)],
            capture_output=True, text=True, timeout=900,
        )
        if "SONG_OK" in (r.stdout or "") and Path(out).exists():
            log(f"ACE-Step generated: {Path(out).name}")
            return str(out)
    except Exception as e:
        log(f"ACE-Step failed: {e}")
    return None


def build_base_track(cfg, work, n_clips=4):
    clips = []
    for i in range(n_clips):
        c = work / f"m{i}.wav"
        # Try free local ACE-Step first, fall back to RunPod MusicGen
        result = gen_music_ace(cfg["music"], c, seed=1000 + i * 37)
        if not result:
            result = gen_music_clip(cfg["music"], c, seed=1000 + i * 37)
        if result:
            clips.append(c); log(f"music clip {i+1}/{n_clips}")
    if not clips:
        return None
    # concat clips with smooth crossfades -> a longer, less-repetitive base
    base = work / "base.wav"
    if len(clips) == 1:
        run([FF, "-y", "-i", str(clips[0]), str(base)])
    else:
        inputs = []
        for c in clips: inputs += ["-i", str(c)]
        # acrossfade chain with 4s crossfade for smoother transitions
        fc = ""; prev = "0:a"
        for i in range(1, len(clips)):
            out = f"a{i}"
            fc += f"[{prev}][{i}:a]acrossfade=d=4:c1=tri:c2=tri[{out}];"
            prev = out
        fc = fc.rstrip(";")
        run([FF, "-y", *inputs, "-filter_complex", fc, "-map", f"[{prev}]", str(base)])
    return str(base)

def gen_visual(prompt, out):
    import asyncio as _a
    from modules.ai_images import generate_image_sdxl
    return _a.run(generate_image_sdxl(prompt, Path(out), niche="", orientation="landscape"))

def animate_loop(img, motion, out, slow=3.0):
    """i2v a gentle living loop -> SLOW it down (dreamy, calming for long sleep/
    ambient videos) -> boomerang for a seamless loop."""
    from modules.runpod_ltx import generate as ltx
    raw = str(Path(out).with_name("raw_motion.mp4"))
    clip = ltx(img, raw, f"{motion}, seamless calm loop, cinematic", 1152, 640, 97, 40)
    if not clip:
        return None
    # slow-motion (setpts) then boomerang forward+reverse -> seamless slow loop
    run([FF, "-y", "-i", clip, "-filter_complex",
         f"[0:v]setpts={slow}*PTS,fps=24[s];[s]split[a][b];[b]reverse[r];"
         f"[a][r]concat=n=2:v=1:a=0[v]", "-map", "[v]",
         "-c:v", "libx264", "-pix_fmt", "yuv420p", str(out)])
    return str(out)

def assemble(video_loop, base_track, minutes, out):
    target = int(minutes * 60)
    vloop = int(target / max(dur(video_loop), 1)) + 1
    aloop = int(target / max(dur(base_track), 1)) + 1
    run([FF, "-y",
         "-stream_loop", str(vloop), "-i", str(video_loop),
         "-stream_loop", str(aloop), "-i", str(base_track),
         "-t", str(target), "-map", "0:v", "-map", "1:a",
         "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "veryfast", "-crf", "22",
         "-c:a", "aac", "-b:a", "192k", "-shortest", str(out)])
    return str(out)

TYPE_PLAYLIST = {
    "focus": "PLABApsnBrOdo", "study": "PLVw2YlPwfLCo", "sleep": "PLSJETL6Xzhyw",
    "meditation": "PLPOVQikM0jdI", "rain": "PLMGSGk95gb3o",
    "coding": "PLbzjpC6bZUaQ", "work": "PLQTvndY8cz3I", "chill": "PLK4pVeAf6LYc",
}

def make_thumb(visual_img, title, out):
    from PIL import Image, ImageDraw, ImageFont
    W, H = 1280, 720
    img = Image.open(visual_img).convert("RGB")
    s = max(W / img.width, H / img.height)
    img = img.resize((int(img.width * s), int(img.height * s)))
    l, t = (img.width - W) // 2, (img.height - H) // 2
    img = img.crop((l, t, l + W, t + H))
    d = ImageDraw.Draw(img, "RGBA")
    d.rectangle([0, H - 230, W, H], fill=(0, 0, 0, 120))
    try:
        fnt = ImageFont.truetype(r"C:\Windows\Fonts\arialbd.ttf", 92)
    except Exception:
        fnt = ImageFont.load_default()
    txt = title.split("\u2022")[0].strip().upper()[:24]
    tw = d.textlength(txt, font=fnt)
    for dx in (-3, 0, 3):
        for dy in (-3, 0, 3):
            d.text(((W - tw) / 2 + dx, H - 175 + dy), txt, font=fnt, fill=(0, 0, 0))
    d.text(((W - tw) / 2, H - 175), txt, font=fnt, fill=(255, 255, 255))
    img.save(out, "JPEG", quality=88)
    return out

async def post(video, cfg, mtype, visual_img):
    from modules.uploader_youtube import upload_to_youtube, _get_youtube_service
    from googleapiclient.http import MediaFileUpload
    desc = (f"{cfg['title']}\n\nRelax, focus or fall asleep with this long-play music — perfect for "
            f"studying, working, meditation and sleep.\n\nSubscribe to AlphaZone Sounds for daily focus, "
            f"study, sleep and meditation music.")
    res = await upload_to_youtube(str(video), cfg["title"][:100], desc, cfg["tags"],
                                  niche="deep_chill", is_short=False, privacy="public")
    log(f"YT: {res.get('url', res)}")
    vid = res.get("video_id")
    if vid:
        try:
            yt = _get_youtube_service("deep_chill")
            pl = TYPE_PLAYLIST.get(mtype)
            if pl:
                yt.playlistItems().insert(part="snippet", body={"snippet": {"playlistId": pl,
                    "resourceId": {"kind": "youtube#video", "videoId": vid}}}).execute()
            th = str(Path(video).with_name("thumb.jpg")); make_thumb(visual_img, cfg["title"], th)
            yt.thumbnails().set(videoId=vid, media_body=MediaFileUpload(th, mimetype="image/jpeg")).execute()
            log("playlist + thumbnail set")
        except Exception as e:
            log(f"playlist/thumb skipped: {str(e)[:80]}")
    return res

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--type", default="rotate", choices=list(CONTENT) + ["rotate"])
    ap.add_argument("--minutes", type=float, default=0)  # 0 = per-type default length
    ap.add_argument("--clips", type=int, default=6)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    # rotate through types daily for a varied channel
    if a.type == "rotate":
        order = list(CONTENT)
        stf = ROOT / "output" / "music" / "rotate.json"; idx = 0
        if stf.exists():
            try: idx = json.loads(stf.read_text()).get("next", 0)
            except Exception: idx = 0
        a.type = order[idx % len(order)]
        stf.parent.mkdir(parents=True, exist_ok=True)
        stf.write_text(json.dumps({"next": (idx + 1) % len(order)}))
    # long-form for watch-time: sleep longest, others 1.5-2h
    DEFAULT_MIN = {"sleep": 180, "study": 120, "focus": 120, "meditation": 90, "rain": 120,
                   "coding": 120, "work": 120, "chill": 90}
    if a.minutes <= 0:
        a.minutes = DEFAULT_MIN.get(a.type, 120)
    cfg = CONTENT[a.type]
    stamp = time.strftime("%Y%m%d_%H%M%S")
    work = ROOT / "output" / "music" / f"{a.type}_{stamp}"; work.mkdir(parents=True, exist_ok=True)
    log(f"TYPE {a.type} | {a.minutes}min -> {work}")

    log("1/4 music"); base = build_base_track(cfg, work, a.clips)
    if not base: raise SystemExit("music failed")
    # pick a random visual+motion for this video so the channel stays fresh
    vis_prompt, motion = random.choice(VISUALS.get(a.type, [(cfg["visual"], cfg["motion"])]))
    log(f"2/4 visual ({vis_prompt[:40]}...)"); img = gen_visual(vis_prompt, work / "visual.png")
    if not img: raise SystemExit("visual failed")
    log("3/4 animate+loop"); vloop = animate_loop(img, motion, work / "vloop.mp4")
    if not vloop:
        log("i2v failed -> static gentle-zoom fallback")
        vloop = str(work / "vloop.mp4")
        run([FF, "-y", "-loop", "1", "-i", str(img), "-t", "8",
             "-vf", "scale=2304:1296,zoompan=z='min(zoom+0.0002,1.1)':d=192:s=1152x648:fps=24",
             "-c:v", "libx264", "-pix_fmt", "yuv420p", vloop])
    log(f"4/4 assemble {a.minutes}min"); out = assemble(vloop, base, a.minutes, work / f"{a.type}_{int(a.minutes)}min.mp4")
    log(f"BUILT: {out} ({dur(out):.0f}s)")
    if a.dry_run:
        log("DRY-RUN — not posting"); return
    log("posting to AlphaZone Sounds (deep_chill)...")
    asyncio.run(post(out, cfg, a.type, img))
    log("DONE")

if __name__ == "__main__":
    main()
