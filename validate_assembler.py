"""Quick smoke test of assemble_full on the one existing clip (catch MoviePy API bugs cheaply)."""
import asyncio
from pathlib import Path

ROOT = Path(r"C:\Users\PenuelM\Documents\ai-video-factory")
CLIP = Path(r"C:\Users\PenuelM\Documents\runpod-ltx-video\output\warpost\01_wide.mp4")
OUT = ROOT / "output" / "full_video_test"
OUT.mkdir(parents=True, exist_ok=True)


async def tts(text, wav):
    import edge_tts, subprocess, imageio_ffmpeg
    mp3 = str(OUT / "n.mp3")
    await edge_tts.Communicate(text, "en-US-GuyNeural").save(mp3)
    subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-i", mp3, wav], capture_output=True)


def main():
    import sys
    sys.path.insert(0, str(ROOT))
    from assemble_full import assemble
    wav = str(OUT / "n.wav")
    text = "This is a rendering test for the full pipeline assembler."
    asyncio.run(tts(text, wav))
    # fake whisper words so caption path runs
    words = [{"word": w, "start": i * 0.35, "end": i * 0.35 + 0.33} for i, w in enumerate(text.split())]
    final = assemble([CLIP, CLIP], wav, None, words, text, OUT, 1216, 704, 24, target=6.0)
    print("OK ->", final, Path(final).stat().st_size, "bytes")


if __name__ == "__main__":
    main()
