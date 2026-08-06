"""Re-render the final video with the BEST voice (Chatterbox) instead of edge-tts.
Reuses the existing 8 LTX shots + music bed; only swaps narration + captions."""
import base64
import time
from pathlib import Path

import requests

ROOT = Path(r"C:\Users\PenuelM\Documents\ai-video-factory")
LTX_CLIPS = Path(r"C:\Users\PenuelM\Documents\runpod-ltx-video\output\warpost")
OUT = ROOT / "output" / "full_video"
MUSIC = OUT / "music.wav"

KEY = ""
for line in open(ROOT / ".env", encoding="utf-8", errors="ignore"):
    if line.startswith("RUNPOD_API_KEY="):
        KEY = line.split("=", 1)[1].strip()
H = {"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"}
EP_CBOX = "https://api.runpod.ai/v2/55tbvsoj6m78m8"
EP_WHISPER = "https://api.runpod.ai/v2/5r88ueysbd8tm8"

TEXT = ("Breaking news. Urgent reports confirm soaring tensions in the critical Red Sea shipping lanes. "
        "Naval forces are converging as global powers watch closely. The lanes that carry the world's oil "
        "now sit at the center of a dangerous standoff. Analysts warn a single misstep could ignite a far "
        "wider conflict. For now, the world watches, and waits.")

SHOT_ORDER = ["01_wide", "02_tracking", "03_aerial", "04_detail", "05_radar", "06_tanker", "07_watch", "08_horizon"]


def _poll(ep, job, budget=900, label=""):
    t0 = time.time(); last = None
    while time.time() - t0 < budget:
        time.sleep(10)
        s = requests.get(f"{ep}/status/{job}", headers=H, timeout=30).json()
        st = s.get("status")
        if st != last:
            print(f"  {label}[{int(time.time()-t0)}s] {st}", flush=True); last = st
        if st in ("COMPLETED", "FAILED", "TIMED_OUT", "CANCELLED"):
            return s
    return None


def _to_wav(src, wav_path):
    import subprocess, imageio_ffmpeg
    subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-i", str(src), str(wav_path)], capture_output=True)


def _edge_fallback(text, wav_path):
    import asyncio, edge_tts
    print("[voice] falling back to edge-tts", flush=True)
    mp3 = str(Path(wav_path).with_suffix(".mp3"))
    asyncio.run(edge_tts.Communicate(text, "en-US-GuyNeural", rate="+4%").save(mp3))
    _to_wav(mp3, wav_path)


def chatterbox(text, wav_path):
    """Best voice = local Kokoro (am_onyx, deep male news voice). edge-tts fallback."""
    print("[voice] Kokoro (am_onyx) generating locally...", flush=True)
    try:
        import asyncio, sys
        sys.path.insert(0, str(ROOT))
        from modules.voice_generator import generate_voice_kokoro
        mp3 = Path(wav_path).with_suffix(".kok.mp3")
        res = asyncio.run(generate_voice_kokoro(text, mp3, voice="am_onyx", speed=1.0))
        if res and Path(mp3).exists() and Path(mp3).stat().st_size > 2000:
            _to_wav(mp3, wav_path)
            print(f"[voice] Kokoro OK -> {wav_path} ({Path(wav_path).stat().st_size/1e6:.2f}MB)", flush=True)
            return
        print("[voice] Kokoro produced nothing usable", flush=True)
    except Exception as e:
        print(f"[voice] Kokoro error: {e}", flush=True)
    _edge_fallback(text, wav_path)


def captions(wav_path):
    b64 = base64.b64encode(Path(wav_path).read_bytes()).decode()
    r = requests.post(f"{EP_WHISPER}/run", headers=H, json={"input": {"audio_base64": b64}}, timeout=60)
    job = r.json().get("id")
    res = _poll(EP_WHISPER, job, budget=300, label="whisper ")
    if res and res.get("status") == "COMPLETED":
        return (res.get("output") or {}).get("words") or []
    return []


def main():
    import sys
    sys.path.insert(0, str(ROOT))
    from assemble_full import assemble

    wav = str(OUT / "narration_cbox.wav")
    chatterbox(TEXT, wav)
    words = captions(wav)
    print(f"[captions] {len(words)} words", flush=True)

    clips = [LTX_CLIPS / f"{n}.mp4" for n in SHOT_ORDER if (LTX_CLIPS / f"{n}.mp4").exists()]
    music = MUSIC if MUSIC.exists() else None
    print(f"[assemble] {len(clips)} clips, music={'yes' if music else 'no'}", flush=True)

    out = OUT / "final_30s_bestvoice.mp4"
    # assemble writes final_30s.mp4; do it then rename
    from assemble_full import assemble as _a
    final = _a(clips, wav, music, words, TEXT, OUT, 1216, 704, 24, target=0)
    Path(final).replace(out)
    print(f"DONE -> {out}", flush=True)


if __name__ == "__main__":
    main()
