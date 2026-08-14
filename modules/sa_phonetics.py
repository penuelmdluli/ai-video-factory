"""
SA name phonetics — teach an American TTS voice to say Nguni/Sotho names.

Kokoro af_heart reads "Mkhulise" as "muh-KLOOZ" and "Hlongwane" as
"HLONG-wayne". The fix is feeding the VOICE a phonetic respelling while the
captions keep the correct spelling (safe now: modules/caption_align.py renders
captions from the original script text, so respellings never reach the screen).

Two layers:
  1. data/player_phonetics.json — generated respellings for every CURRENT PSL
     player (all 16 squads), built by `python modules/sa_phonetics.py --build`.
     Hand-corrections survive rebuilds: edit the "override" value and it wins.
  2. rule-based respell() for any name not in the file.

The rules approximate real Nguni/Sotho pronunciation:
  th -> t (aspirated t, never English "th")     Themba -> Tembah
  ph -> p (aspirated p, never "f")              Phakathi -> Pakati
  tsh/tj -> ch                                  Tshabalala -> Chabalala
  hl -> shl (lateral fricative approximation)   Hlongwane -> Shlongwane
  kh -> k                                       Mkhulise -> Mkulise
  leading M/N + consonant -> syllabic Mm/Nn     Mkhize -> Mm-kizeh
  final e is voiced                             Monyane -> Monyaneh
  clicks (c/q/x after n/g) -> hard k            Ngcobo -> Nkoboh
"""
import json
import re
import sys
from pathlib import Path

LEXICON = Path(__file__).parent.parent / "data" / "player_phonetics.json"


def respell(name: str) -> str:
    """Rule-based phonetic respelling of one name (surname or full name)."""
    out = []
    for w in name.split():
        s = w
        # click consonants first (approximate with k/g stops)
        s = re.sub(r"^N[gk]?[cqx]", "Nk", s)
        s = re.sub(r"(?<=[a-z])n[gk]?[cqx]", "nk", s, flags=re.IGNORECASE)
        # digraphs
        s = re.sub(r"tsh|tj", "ch", s, flags=re.IGNORECASE)
        s = re.sub(r"th", "t", s, flags=re.IGNORECASE)
        s = re.sub(r"ph", "p", s, flags=re.IGNORECASE)
        s = re.sub(r"hl", "shl", s, flags=re.IGNORECASE)
        s = re.sub(r"kh", "k", s, flags=re.IGNORECASE)
        s = re.sub(r"dl", "dhl", s, flags=re.IGNORECASE)
        # syllabic nasal starts: Mkulise -> Mm-kulise, Ndlovu -> Nn-dhlovu
        m = re.match(r"^([MN])([^aeiouy].*)$", s, flags=re.IGNORECASE)
        if m:
            s = f"{m.group(1)}{m.group(1).lower()}-{m.group(2)}"
        # voiced final e: Monyane -> Monyaneh
        if s[-1:].lower() == "e" and len(s) > 3:
            s = s + "h"
        # keep the original capitalisation shape
        if w[:1].isupper() and s[:1].islower():
            s = s[:1].upper() + s[1:]
        out.append(s)
    return " ".join(out)


def load_lexicon() -> dict:
    """{correct_name: spoken_form} — override wins over generated."""
    try:
        data = json.loads(LEXICON.read_text(encoding="utf-8"))
    except Exception:
        return {}
    out = {}
    for name, ent in data.items():
        spoken = (ent.get("override") or ent.get("generated") or "").strip()
        if spoken and spoken.lower() != name.lower():
            out[name] = spoken
    return out


async def build_lexicon():
    """(Re)generate respellings for every current player in the league.

    Existing hand overrides are preserved; only 'generated' is refreshed.
    """
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from modules.psl_squads import get_squad, ESPN_TEAMS
    try:
        old = json.loads(LEXICON.read_text(encoding="utf-8"))
    except Exception:
        old = {}
    data = {}
    for club in ESPN_TEAMS:
        for p in await get_squad(club):
            name = p["name"]
            surname = name.split()[-1]
            for key in {name, surname}:
                if len(key) < 4:
                    continue
                gen = respell(key)
                if gen.lower() == key.lower():
                    continue                     # already TTS-friendly
                data[key] = {"generated": gen,
                             "override": old.get(key, {}).get("override", "")}
    LEXICON.parent.mkdir(parents=True, exist_ok=True)
    LEXICON.write_text(json.dumps(data, indent=2, ensure_ascii=False, sort_keys=True),
                       encoding="utf-8")
    print(f"[Phonetics] {len(data)} names -> {LEXICON}")
    return data


if __name__ == "__main__":
    if "--build" in sys.argv:
        import asyncio
        asyncio.run(build_lexicon())
    else:
        for n in ("Mduduzi Shabalala", "Hlongwane", "Mkhulise", "Ngcobo",
                  "Themba Zwane", "Ndlovu", "Mthethwa", "Du Preez"):
            print(f"{n:24} -> {respell(n)}")
