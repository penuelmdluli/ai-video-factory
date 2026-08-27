"""
Availability gate — only argue about men who can actually play.

The injury list (modules/injuries.py) is authoritative but owner-maintained,
so an empty list means "nobody has been reported", not "everybody is fit".
Building a debate on that alone is how a page ends up asking 10,000 people to
choose between players who are not in the squad.

This adds the evidence the squad cache cannot give: the last real team sheet.
A man who started or sat on the bench in the most recent match is demonstrably
available. A man who was in neither is not necessarily injured — he may be
rotated, suspended, sold or simply out of favour — but we cannot vouch for
him, and a debate format asserts that every name is a live option.

So the rule is: CONFIRMED means seen in the last matchday squad. Everyone else
is held back. It errs toward a shorter, true list over a longer, hopeful one.
"""
import re


def _surname(entry: str) -> str:
    """'8 Ndlovu' -> 'ndlovu'; 'Siphesihle Ndlovu' -> 'ndlovu'."""
    s = re.sub(r"^\s*\d+\s+", "", str(entry or "")).strip()
    parts = s.split()
    return (parts[-1] if parts else s).lower()


async def confirmed_available(club: str, men: list[dict]) -> tuple:
    """Split contenders into (confirmed, held_back, evidence).

    men is [{"no","name"}]. held_back is [(man, reason)].
    """
    held, evidence = [], {}

    # 1. Reported out — authoritative, drops on its own.
    try:
        from modules.injuries import unavailable
        out_map = unavailable(club, [_surname(m["name"]) for m in men])
    except Exception:
        out_map = {}

    # 2. Last real team sheet — the positive evidence.
    sheet = None
    try:
        from modules.psl_fixtures import last_lineup
        sheet = await last_lineup(club)
    except Exception as e:
        print(f"[Avail] team sheet unavailable: {e}")

    seen = set()
    if sheet:
        for entry in (sheet.get("players") or []) + (sheet.get("bench") or []):
            seen.add(_surname(entry))
        evidence = {"match": sheet.get("match", ""), "date": sheet.get("date", ""),
                    "squad_size": len(seen)}

    confirmed = []
    for m in men:
        s = _surname(m["name"])
        if s in out_map:
            held.append((m, f"reported out: {out_map[s]}"))
        elif not sheet:
            # No sheet at all: fall back to the injury list only, and say so.
            confirmed.append(m)
        elif s in seen:
            confirmed.append(m)
        else:
            held.append((m, f"not in the matchday squad for {evidence.get('match','the last match')}"))
    return confirmed, held, evidence
