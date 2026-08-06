"""ACE-Step instrumental background music — genre-matched per niche, cached + rotated.

Reuses the SAME local ACE-Step engine that makes the Zuzu songs (zuzu_engine/acestep_venv)
to produce cinematic, non-boring instrumental beds. $0 (local GPU). The first few videos
per niche generate a fresh track (~1-2 min each); once the rotation reaches
ACE_MUSIC_VARIANTS, every build reuses an existing bed instantly (random pick = variety).
Falls back to None (caller uses its library) if the engine is missing or generation fails.
"""
import os
import random
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ENG = ROOT / "zuzu_engine"
ACEPY = ENG / "acestep_venv" / "Scripts" / "python.exe"
ACEGEN = ENG / "acestep_gen.py"
ACEMODEL = ENG / "models"
CACHE = ROOT / "assets" / "ace_music_cache"

ENABLE_ACE_MUSIC = os.getenv("ENABLE_ACE_MUSIC", "true").lower() in ("true", "1", "yes")
ACE_MUSIC_VARIANTS = int(os.getenv("ACE_MUSIC_VARIANTS", "5"))     # rotation size per niche
ACE_MUSIC_DURATION = int(os.getenv("ACE_MUSIC_DURATION", "45"))    # seconds per bed
# One CONSISTENT signature bed per niche (default) — same music every build = brand
# consistency. Set ACE_MUSIC_SIGNATURE=false to rotate a pool of ACE_MUSIC_VARIANTS instead.
ACE_MUSIC_SIGNATURE = os.getenv("ACE_MUSIC_SIGNATURE", "true").lower() in ("true", "1", "yes")

# Impactful, genre-matched INSTRUMENTAL prompts. Tuned so the bed sells the mood without
# fighting the voiceover (no vocals, strong but not chaotic).
NICHE_STYLES = {
    "tech_news": ("epic tense cinematic trailer instrumental, 120 bpm, driving taiko and orchestral "
                  "percussion, urgent staccato strings, dark brass stabs, dramatic breaking-news "
                  "documentary underscore, building suspense, Hans Zimmer style, powerful, "
                  "professional mix, stereo wide, no vocals"),
    "sa_pulse": ("modern cinematic documentary underscore, 100 bpm, serious yet hopeful, afrobeat "
                 "percussion with djembe and shaker, warm strings and piano, amapiano bass hint, "
                 "current-affairs news bed, steady momentum, professional mix, no vocals"),
    "health_wellness": ("calm healing ambient instrumental, 65 bpm, warm soft piano with reverb, "
                        "gentle fingerpicked acoustic guitar, lush evolving pads, nature sounds hint, "
                        "spa meditation, peaceful and uplifting, warm mix, no vocals"),
    "motivation": ("epic uplifting cinematic instrumental, 130 bpm, soaring strings with crescendo, "
                   "inspiring grand piano, powerful orchestral build, triumphant horns, driving "
                   "cinematic drums, victory anthem feel, wide stereo mix, no vocals"),
    "ai_money": ("modern electronic corporate instrumental, 110 bpm, clean synth bass, crisp hi-hats, "
                 "futuristic arpeggios, confident and sleek, tech startup energy, subtle dubstep "
                 "influence, professional polished mix, no vocals"),
    "blissful_moments": ("warm heartfelt acoustic instrumental, 85 bpm, gentle ukulele and soft piano, "
                         "light percussion with tambourine, feel-good and joyful, family vlog music, "
                         "bright and sunny, warm mix, no vocals"),
    "daily_breakdown": ("urgent modern news bed instrumental, 115 bpm, punchy electronic drums, "
                        "staccato synth stabs, tense strings, investigative documentary feel, "
                        "CNN-style breaking news underscore, professional mix, no vocals"),
    "limitless_you": ("futuristic inspirational electronic instrumental, 125 bpm, soaring synth leads, "
                      "epic build with orchestral elements, cyberpunk meets motivational, driving "
                      "four-on-the-floor kick, wide atmospheric pads, no vocals"),
}
DEFAULT_STYLE = ("modern cinematic instrumental underscore, 100 bpm, engaging and professional, "
                 "subtle percussion, warm strings and piano, tasteful energy, clean mix, no vocals")


def _style(niche: str) -> str:
    return NICHE_STYLES.get(niche, DEFAULT_STYLE)


def _cached(niche: str) -> list:
    d = CACHE / (niche or "default")
    return sorted(d.glob("*.wav")) if d.exists() else []


def _generate(niche: str) -> Path | None:
    """Render one instrumental bed for the niche via ACE-Step. Returns path or None."""
    if not (ACEPY.exists() and ACEGEN.exists() and ACEMODEL.exists()):
        print("[ACEMusic] engine not found — falling back to library")
        return None
    d = CACHE / (niche or "default")
    d.mkdir(parents=True, exist_ok=True)
    seed = random.randint(1, 999999)
    out = d / f"bed_{seed}.wav"
    lyr = d / "_instrumental.txt"
    if not lyr.exists():
        lyr.write_text("[instrumental]", encoding="utf-8")
    try:
        r = subprocess.run(
            [str(ACEPY), str(ACEGEN), "--prompt", _style(niche), "--lyrics", str(lyr),
             "--out", str(out), "--model", str(ACEMODEL),
             "--duration", str(ACE_MUSIC_DURATION), "--seed", str(seed)],
            capture_output=True, text=True, timeout=900,
        )
        if "SONG_OK" in (r.stdout or "") and out.exists():
            print(f"[ACEMusic] generated {niche or 'default'} bed -> {out.name}")
            return out
        print(f"[ACEMusic] generation failed: {((r.stdout or '') + (r.stderr or ''))[-200:]}")
    except Exception as e:
        print(f"[ACEMusic] error: {e}")
    return None


def get_ace_music_sync(niche: str = "", duration: float | None = None) -> str | None:
    """Genre-matched instrumental bed for the niche, or None to let the caller fall back.
    Grows a per-niche rotation up to ACE_MUSIC_VARIANTS (one new track per call until full),
    then reuses at random so beds stay fresh at $0."""
    if not ENABLE_ACE_MUSIC:
        return None
    have = _cached(niche)
    if ACE_MUSIC_SIGNATURE:
        # ONE consistent bed per niche: generate once, then reuse the SAME track every build
        if not have:
            if _generate(niche):
                have = _cached(niche)
        return str(have[0]) if have else None
    # rotation mode (legacy): grow a small pool, then pick at random
    if len(have) < ACE_MUSIC_VARIANTS:
        if _generate(niche):
            have = _cached(niche)
    return str(random.choice(have)) if have else None


if __name__ == "__main__":
    import sys
    n = sys.argv[1] if len(sys.argv) > 1 else "tech_news"
    print("RESULT:", get_ace_music_sync(n))
