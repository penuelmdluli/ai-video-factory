"""2-PERSON PODCAST orchestrator — movie-like live conversation.
Gemini dialogue -> Kokoro dual voices -> EchoMimicV3 talking avatars (lip-sync +
gestures) -> cut-between-hosts assembly. Style A.

Usage: python podcast.py "optional topic"   (default: a current Africa story)
"""
import asyncio, base64, json, re, subprocess, sys, time
from pathlib import Path
import requests

ROOT = Path(r"C:\Users\PenuelM\Documents\ai-video-factory")
sys.path.insert(0, str(ROOT))
OUT = ROOT / "output" / "podcast"; OUT.mkdir(parents=True, exist_ok=True)
PRES = ROOT / "assets" / "presenters"; PRES.mkdir(parents=True, exist_ok=True)

from config import GEMINI_API_KEY, ANTHROPIC_API_KEY
KEY = ""
for line in open(ROOT / ".env", encoding="utf-8", errors="ignore"):
    if line.startswith("RUNPOD_API_KEY="):
        KEY = line.split("=", 1)[1].strip()
H = {"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"}
EP_ECHO = "https://api.runpod.ai/v2/k526wl5smcg7h5"
W, HGT, FPS = 720, 1280, 24
MAX_TURNS = 3   # budget cap for the test

VOICES = {"A": "am_onyx", "B": "af_heart"}   # distinct male / female hosts


def _clean(t):
    t = re.sub(r"```(?:json)?", "", t).strip()
    m = re.search(r"\{.*\}", t, re.DOTALL)
    return m.group(0) if m else t


IMG_A = ("photorealistic tight CLOSE-UP head-and-shoulders portrait of a MALE African podcast host talking, "
         "face centered and filling the frame, wearing headphones, looking at the camera, softly blurred modern "
         "podcast studio background, warm lighting, 4k, highly detailed")
IMG_B = ("photorealistic tight CLOSE-UP head-and-shoulders portrait of a FEMALE African podcast host talking, "
         "face centered and filling the frame, wearing headphones, looking at the camera, softly blurred modern "
         "podcast studio background, warm lighting, 4k, highly detailed")


def gen_dialogue(topic):
    prompt = (
        f"Find the TOP TRENDING news stories RIGHT NOW across South Africa and Africa "
        f"(South Africa, Nigeria, Ghana, Kenya and the continent). Then write a punchy 2-host news-podcast clip "
        f"covering the biggest trending stories.\n"
        f"EXACTLY {MAX_TURNS} turns, alternating Host A (MALE) then Host B (FEMALE). Each turn is ONE natural "
        f"spoken sentence (max ~20 words), energetic and current, referencing REAL trending stories/countries. "
        f"Host A opens with the headline, Host B reacts/adds, and so on.\n"
        f"Return ONLY JSON: {{\"title\":\"<catchy show title>\",\"host_a\":{{\"name\":\"<male name>\"}},"
        f"\"host_b\":{{\"name\":\"<female name>\"}},\"turns\":[{{\"speaker\":\"A\",\"text\":\"..\"}},"
        f"{{\"speaker\":\"B\",\"text\":\"..\"}},{{\"speaker\":\"A\",\"text\":\"..\"}}]}}")
    try:
        from google import genai
        from google.genai import types
        c = genai.Client(api_key=GEMINI_API_KEY)
        try:
            cfg = types.GenerateContentConfig(tools=[types.Tool(google_search=types.GoogleSearch())])
        except Exception:
            cfg = None
        for m in ("gemini-2.5-flash", "gemini-2.0-flash"):
            try:
                r = (c.models.generate_content(model=m, contents=prompt, config=cfg) if cfg
                     else c.models.generate_content(model=m, contents=prompt))
                if r and r.text:
                    d = json.loads(_clean(r.text))
                    if d.get("turns"):
                        d["host_a"]["img"] = IMG_A
                        d["host_b"]["img"] = IMG_B
                        return d
            except Exception as e:
                print("gemini", e)
    except Exception as e:
        print("gemini unavailable", e)
    # fallback
    return {"title": "The Africa Brief", "host_a": {"name": "Thabo", "img": IMG_A},
            "host_b": {"name": "Lindiwe", "img": IMG_B},
            "turns": [{"speaker": "A", "text": "Top of the show — South Africa's headlines are dominating across the continent tonight."},
                      {"speaker": "B", "text": "And it's not just us — Nigeria, Ghana and Kenya all have major stories breaking right now."},
                      {"speaker": "A", "text": "From the economy to politics, Africa is moving fast — let's get into the trending stories."}]}


async def host_image(desc, path):
    from modules.ai_images import generate_image
    try:
        await generate_image(desc, path, size="1024x1024", niche="tech_news")
    except TypeError:
        await generate_image(desc, path)
    if path.exists():
        # SDXL ignores the size and returns landscape — center-crop to a SQUARE
        # (keeps the centered face) so the aspect stays consistent, no cut visuals.
        from PIL import Image
        im = Image.open(path).convert("RGB")
        s = min(im.size); l = (im.width - s) // 2; t = (im.height - s) // 2
        im.crop((l, t, l + s, t + s)).save(path)
        return path
    return None


def _poll(job, budget=1000, label=""):
    t0 = time.time(); last = None
    while time.time() - t0 < budget:
        time.sleep(12)
        s = requests.get(f"{EP_ECHO}/status/{job}", headers=H, timeout=30).json(); st = s.get("status")
        if st != last:
            print(f"    {label}[{int(time.time()-t0)}s] {st}", flush=True); last = st
        if st in ("COMPLETED", "FAILED", "TIMED_OUT", "CANCELLED"):
            return s
    return None


def echo_clip(img_path, wav_path, name):
    payload = {"input": {"image": base64.b64encode(Path(img_path).read_bytes()).decode(),
                         "audio": base64.b64encode(Path(wav_path).read_bytes()).decode(),
                         "prompt": "A podcast host talking to camera, natural hand gestures"}}
    r = requests.post(f"{EP_ECHO}/run", headers=H, json=payload, timeout=90)
    job = r.json().get("id")
    res = _poll(job, 1000, f"{name} ") if job else None
    if res and res.get("status") == "COMPLETED" and (res.get("output") or {}).get("video_base64"):
        f = OUT / f"{name}.mp4"; f.write_bytes(base64.b64decode(res["output"]["video_base64"]))
        return f
    print(f"    {name} echo failed: {(res or {}).get('status')} {str((res or {}).get('output'))[:300]}", flush=True)
    return None


async def kokoro(text, wav, voice):
    from modules.voice_generator import generate_voice_kokoro
    mp3 = Path(wav).with_suffix(".mp3")
    await generate_voice_kokoro(text, mp3, voice=voice, speed=1.0)
    import imageio_ffmpeg
    subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-i", str(mp3), str(wav)], capture_output=True)


def main():
    topic = " ".join(sys.argv[1:]) or "the global race for Africa's critical minerals and South Africa's role"
    print("=== PODCAST ===", flush=True)
    d = gen_dialogue(topic)
    print(f"  {d['title']}: {d['host_a']['name']} & {d['host_b']['name']} — {len(d['turns'])} turns", flush=True)

    print("[1] host images", flush=True)
    imgs = {}
    imgs["A"] = asyncio.run(host_image(d["host_a"]["img"], PRES / "podcast_host_a.png"))
    imgs["B"] = asyncio.run(host_image(d["host_b"]["img"], PRES / "podcast_host_b.png"))
    if not imgs["A"] or not imgs["B"]:
        raise SystemExit("host image generation failed")

    print("[2] per-turn voice + avatar", flush=True)
    clips = []
    for i, turn in enumerate(d["turns"][:MAX_TURNS]):
        sp = turn["speaker"]; name = f"turn{i:02d}_{sp}"
        wav = OUT / f"{name}.wav"
        asyncio.run(kokoro(turn["text"], wav, VOICES.get(sp, "am_onyx")))
        clip = echo_clip(imgs[sp], wav, name)
        if clip:
            label = d["host_a"]["name"] if sp == "A" else d["host_b"]["name"]
            clips.append((clip, label, turn["text"]))

    if len(clips) < 2:
        raise SystemExit(f"only {len(clips)} turns rendered — aborting")

    print("[3] assemble podcast", flush=True)
    from podcast_assemble import assemble_podcast
    from music_library import get_music_bed
    final = assemble_podcast(clips, get_music_bed(), OUT, W, HGT, FPS, title=d["title"])
    dest = Path(r"C:\Users\PenuelM\Desktop\AI_Videos\podcast_test.mp4")
    import imageio_ffmpeg
    subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-i", str(final), "-c:v", "libx264",
                    "-pix_fmt", "yuv420p", "-movflags", "+faststart", "-c:a", "aac", "-b:a", "160k", str(dest)],
                   capture_output=True)
    print(f"DONE -> {dest}", flush=True)


if __name__ == "__main__":
    main()
