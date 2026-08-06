"""AUTONOMOUS reel: latest news (Gemini/Claude) -> fresh vertical video -> post to
Tech Pulse Africa -> log topic (never repeats). Designed to run 3x/day on a schedule.
"""
import asyncio, base64, subprocess, sys, time, traceback
from pathlib import Path
import requests

ROOT = Path(r"C:\Users\PenuelM\Documents\ai-video-factory")
sys.path.insert(0, str(ROOT))
from news_topic_generator import get_fresh_topic, log_posted

KEY = ""
for line in open(ROOT / ".env", encoding="utf-8", errors="ignore"):
    if line.startswith("RUNPOD_API_KEY="):
        KEY = line.split("=", 1)[1].strip()
H = {"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"}
EP_LTX = "https://api.runpod.ai/v2/mp2awqavthuc2b"
EP_MUSIC = "https://api.runpod.ai/v2/b13hwup9d6179v"
EP_WHISPER = "https://api.runpod.ai/v2/5r88ueysbd8tm8"
EP_FOLEY = "https://api.runpod.ai/v2/5arzy0p1wnm229"
W, HGT, FPS = 704, 1280, 24
NEG = ("worst quality, inconsistent motion, blurry, jittery, distorted, warped faces, extra limbs, "
       "text artifacts, watermark, low resolution, flickering, morphing")


def _submit(ep, p):
    return requests.post(f"{ep}/run", headers=H, json={"input": p}, timeout=90).json().get("id")


def _poll(ep, job, budget, label=""):
    t0 = time.time(); last = None
    while time.time() - t0 < budget:
        time.sleep(12)
        s = requests.get(f"{ep}/status/{job}", headers=H, timeout=30).json(); st = s.get("status")
        if st != last:
            print(f"    {label}[{int(time.time()-t0)}s] {st}", flush=True); last = st
        if st in ("COMPLETED", "FAILED", "TIMED_OUT", "CANCELLED"):
            return s
    return None


def _ff():
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


def main():
    stamp = time.strftime("%Y%m%d_%H%M%S", time.localtime())
    outc = Path(rf"C:\Users\PenuelM\Documents\runpod-ltx-video\output\auto_{stamp}"); outc.mkdir(parents=True, exist_ok=True)
    out = ROOT / "output" / f"auto_{stamp}"; out.mkdir(parents=True, exist_ok=True)

    print("=== AUTONOMOUS REEL ===", flush=True)
    print("[0] news brain (latest, non-repeating)", flush=True)
    pkg = get_fresh_topic()
    print(f"  TOPIC: {pkg['title']}  (src={pkg.get('source')})", flush=True)
    shots = pkg["shots"]

    print("[1] shots", flush=True)
    paths = []
    for s in shots:
        f = outc / f"{s['name']}.mp4"
        print(f"  {s['name']}", flush=True)
        job = _submit(EP_LTX, {"prompt": s["prompt"], "negative_prompt": NEG, "width": W, "height": HGT,
                               "num_frames": 97, "seed": 7})
        res = _poll(EP_LTX, job, 3000, f"{s['name']} ") if job else None
        if res and res.get("status") == "COMPLETED" and (res.get("output") or {}).get("video_base64"):
            f.write_bytes(base64.b64decode(res["output"]["video_base64"])); paths.append(f)
        else:
            paths.append(None)

    print("[2] foley — DISABLED (cost saving; free ambient bed + booms instead)", flush=True)

    print("[3] voice", flush=True)
    from modules.voice_generator import generate_voice_kokoro, generate_voice_edge_tts
    wav = out / "narration.wav"; mp3 = out / "narration.mp3"
    # Robust voice: try Kokoro first, but NEVER let a Kokoro failure abort the run.
    # Fall back to free edge-tts (British news voice) so the reel still posts.
    voice_ok = False
    try:
        vres = asyncio.run(generate_voice_kokoro(pkg["narration"], mp3, voice="am_onyx", speed=1.0))
        if vres and mp3.exists() and mp3.stat().st_size > 0:
            voice_ok = True
        else:
            print("  Kokoro returned falsy/empty output — falling back to edge-tts", flush=True)
    except Exception as e:
        print(f"  Kokoro voice failed ({e}) — falling back to edge-tts", flush=True)
    if not voice_ok:
        try:
            asyncio.run(generate_voice_edge_tts(pkg["narration"], mp3, voice="en-GB-RyanNeural"))
            if mp3.exists() and mp3.stat().st_size > 0:
                voice_ok = True
                print("  edge-tts fallback voice OK", flush=True)
        except Exception as e:
            print(f"  edge-tts fallback also failed ({e})", flush=True)
    if not voice_ok:
        raise SystemExit("both Kokoro and edge-tts voice generation failed — aborting post")
    subprocess.run([_ff(), "-y", "-i", str(mp3), str(wav)], capture_output=True)

    print("[4] music (reusable library — saves cost)", flush=True)
    from music_library import get_music_bed
    music = get_music_bed()   # reuse a cached bed instead of paying MusicGen every run

    print("[5] captions", flush=True)
    wj = _submit(EP_WHISPER, {"audio_base64": base64.b64encode(wav.read_bytes()).decode()})
    wres = _poll(EP_WHISPER, wj, 400, "whisper ") if wj else None
    words = (wres.get("output") or {}).get("words") or [] if wres and wres.get("status") == "COMPLETED" else []

    print("[6] assemble", flush=True)
    from assemble_full import assemble
    clips = [p for p in paths if p]
    if len(clips) < 4:
        raise SystemExit(f"only {len(clips)} shots — aborting post")
    final = assemble(clips, str(wav), str(music) if music else None, words, pkg["narration"], out, W, HGT, FPS,
                     target=28.0, flags=tuple(pkg.get("flags", ["ZA", "US"]))[:2],
                     lowerthird_label=pkg.get("lowerthird_label", "Breaking"),
                     ticker=pkg.get("ticker", pkg["title"]), live=True, tag_text="AI", shot_audios=None)
    dest = Path(rf"C:\Users\PenuelM\Desktop\AI_Videos\auto_{stamp}.mp4")
    subprocess.run([_ff(), "-y", "-i", str(final), "-c:v", "libx264", "-pix_fmt", "yuv420p",
                    "-movflags", "+faststart", "-c:a", "aac", "-b:a", "160k", str(dest)], capture_output=True)
    print(f"  built -> {dest}", flush=True)

    print("[7] POST reel", flush=True)
    from modules.uploader_facebook import upload_to_facebook
    # AI-transparency label (2026 platform policy for synthetic news visuals) +
    # existing website/description logic downstream in the uploader stays intact.
    desc = pkg.get("caption", pkg["title"]) + "\n\n\U0001F3AC AI-generated visualization"
    # Ensure the AI-labeling hashtag is present (dedupe case-insensitively, tolerate '#').
    hashtags = ["Africa", "Geopolitics", "BreakingNews", "Reels", "AIgenerated"]
    seen, deduped = set(), []
    for h in hashtags:
        k = h.lstrip("#").lower()
        if k not in seen:
            seen.add(k); deduped.append(h)
    res = asyncio.run(upload_to_facebook(video_path=str(dest), title=pkg["title"], description=desc,
                                         niche="tech_news", hashtags=deduped,
                                         is_reel=True))
    print("  POST:", res, flush=True)
    if res.get("status") == "uploaded":
        log_posted(pkg)
        print("  logged (won't repeat)", flush=True)
    print("DONE", flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        print("AUTO_REEL ERROR:\n" + traceback.format_exc(), flush=True)
