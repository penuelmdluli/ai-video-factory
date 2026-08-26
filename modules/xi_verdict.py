"""
Our predicted XI, marked against the real team sheet.

Owner call 2026-08-26: use the line-up reel format for the CONFIRMED side too,
"check and analyse and offer even a prediction based on the line".

Re-skinning the morning reel would waste the one thing this page has that
rivals do not. Every other page reposts the team-sheet graphic within seconds
of it dropping, and it is the same graphic on all of them. We are the only
page that called a side eight hours earlier — so the confirmed post should
open by MARKING that call. It costs nothing (both XIs are structured data),
nobody else can copy it without having made a prediction first, and it is
inherently argumentative, which is what this page's numbers reward.

It also makes the morning prediction matter. A prediction nobody ever checks
is noise; a prediction that gets marked in public is a reason to come back at
half past six.

    from modules.xi_verdict import compare, verdict_lines
    v = compare(predicted_xi, confirmed_xi)
    v["hits"], v["missed"], v["surprises"], v["score"]
"""


def _surname(entry: str) -> str:
    parts = str(entry).split(None, 1)
    return (parts[1] if len(parts) > 1 else str(entry)).strip()


def _key(entry: str) -> str:
    return _surname(entry).lower()


def compare(predicted: list[str], confirmed: list[str]) -> dict:
    """Mark the call. Returns hits, the ones we missed, and the surprises.

    Matched on surname, because the number we carry comes from the squad
    cache and the number on the team sheet comes from the match feed — they
    disagree often enough that matching on "16 Leaner" would score a correct
    call as a miss.
    """
    pred = [p for p in (predicted or []) if str(p).strip()]
    conf = [c for c in (confirmed or []) if str(c).strip()]
    pk = {_key(p): p for p in pred}
    ck = {_key(c): c for c in conf}

    hits = [ck[k] for k in ck if k in pk]           # named, and they started
    missed = [pk[k] for k in pk if k not in ck]     # we named them, they did not start
    surprises = [ck[k] for k in ck if k not in pk]  # started, we did not see it

    n = len(conf) or 11
    return {
        "hits": hits, "missed": missed, "surprises": surprises,
        "n_hits": len(hits), "n_total": n,
        "score": f"{len(hits)}/{n}",
        "pct": (100.0 * len(hits) / n) if n else 0.0,
    }


def verdict_lines(club_name: str, v: dict, pred_formation: str,
                  real_formation: str) -> list[str]:
    """Narration for the verdict act — honest either way."""
    n, tot = v["n_hits"], v["n_total"]
    lines = [f"This morning we called this {club_name} side.",
             f"Here is how we did. {n} of {tot}."]

    if n == tot:
        lines.append("The full eleven. We called it exactly.")
    elif n >= tot - 2:
        lines.append("Close to the mark.")
    elif n <= tot // 2:
        lines.append("We got that one wrong, and we will say so.")

    if pred_formation and real_formation and pred_formation != real_formation:
        lines.append(f"We said {pred_formation.replace('-', ' ')}. "
                     f"It is {real_formation.replace('-', ' ')}.")

    sur = [_surname(s) for s in v["surprises"][:2]]
    mis = [_surname(m) for m in v["missed"][:2]]
    if sur:
        lines.append(("The surprise is " if len(sur) == 1
                      else "The surprises are ") + " and ".join(sur) + ".")
    if mis:
        lines.append(" and ".join(mis) +
                     (" misses out." if len(mis) == 1 else " miss out."))
    return lines
