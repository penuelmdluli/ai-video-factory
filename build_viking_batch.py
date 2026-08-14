#!/usr/bin/env python
"""Build SAGA OF THE NORTH episodes — the serialised Viking saga.

Each episode is 3 character-locked Veo shots (~24s) cut with the impact edit (grade, flash cuts,
shake on the hit, sub-bass booms, freeze-frame ending), narrated by the saga-teller over ducked
battle audio, and stamped with the series pack: episode badge, hook, lesson card, next-episode tease.

  python build_viking_batch.py                  # next 3 unbuilt episodes, in season order
  python build_viking_batch.py --count 5        # next 5 unbuilt
  python build_viking_batch.py --eps 1 2 3      # specific episodes (rebuilds even if built)
  python build_viking_batch.py --all            # the whole season
  python build_viking_batch.py --dry-run        # show the plan + cost, generate nothing
"""
import argparse
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from modules.veo_kie import generate_veo, upload_image, check_key, estimate_cost
from modules.impact_edit import impact_concat
from finish_short import finish
import viking_saga as saga

HERO = ROOT / "assets" / "viking" / "hero.png"
HOLD = 1.6   # freeze-frame tail the lesson card lives on


def built_eps():
    """Episode numbers that already have a finished final.mp4 on disk.

    Only the zero-padded series naming counts (viking_ep05_shieldwall_<stamp>), so builds from
    before the series rewrite don't mask an episode that still needs making.
    """
    out = set()
    for d in ROOT.glob("output/viking_ep*_*"):
        m = re.match(r"viking_ep(\d{2})_", d.name)
        if m and (d / "final.mp4").exists():
            out.add(int(m.group(1)))
    return out


def pick(args):
    if args.eps:
        return saga.get(eps=args.eps)
    todo = [e for e in saga.EPISODES if e["ep"] not in built_eps()]
    return todo if args.all else todo[:args.count]


def build_episode(ep, hero_url):
    stamp = time.strftime("%Y%m%d_%H%M%S")
    out = ROOT / "output" / f"viking_ep{ep['ep']:02d}_{ep['slug']}_{stamp}"
    out.mkdir(parents=True, exist_ok=True)
    print(f"\n--- EP.{ep['ep']} {ep['title']} ---", flush=True)

    clips = []
    for i, shot in enumerate(ep["shots"]):
        c = out / f"shot_{i}.mp4"
        try:
            generate_veo(saga.STYLE + shot, str(c), model="veo3_lite", aspect="9:16",
                         resolution="1080p", duration=8, image_urls=[hero_url],
                         generation_type="REFERENCE_2_VIDEO")
            clips.append(str(c))
        except Exception as e:
            print(f"  shot {i} FAILED: {e}", flush=True)
    if not clips:
        print(f"  EP.{ep['ep']} produced no clips — skipping", flush=True)
        return None

    # The shake goes on the hit; if that shot failed, put it on the last one we got.
    impact = ep["impact"] if ep["impact"] < len(clips) else len(clips) - 1
    if not impact_concat(clips, str(out / "visuals.mp4"), impact=impact, freeze=HOLD):
        print(f"  EP.{ep['ep']} concat failed", flush=True)
        return None

    return finish(str(out), saga=ep["saga"], beats=ep["beats"], comment=ep["comment"], hook=ep["hook"],
                  lesson=ep["lesson"], badge=saga.badge(ep), next_tease=saga.next_tease(ep),
                  voiceover=True, hold=HOLD)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--count", type=int, default=3, help="how many unbuilt episodes to build")
    ap.add_argument("--eps", type=int, nargs="+", help="specific episode numbers")
    ap.add_argument("--all", action="store_true", help="build every unbuilt episode")
    ap.add_argument("--dry-run", action="store_true", help="print the plan and cost only")
    args = ap.parse_args()

    todo = pick(args)
    if not todo:
        print("every episode in the bank is already built — add episodes to viking_saga.py", flush=True)
        return
    shots = sum(len(e["shots"]) for e in todo)
    cost = estimate_cost("veo3_lite", 8) * shots
    print(f"=== {saga.SERIES} S{saga.SEASON} — {len(todo)} episode(s) / {shots} shots ~${cost:.2f} ===",
          flush=True)
    for e in todo:
        print(f"  EP.{e['ep']:>2} {e['title']:<16} {e['hook']}", flush=True)
    if args.dry_run:
        return
    if not check_key():
        print("KIE_API_KEY not set.", flush=True)
        return
    if not HERO.exists():
        print(f"hero image missing: {HERO}", flush=True)
        return

    hero_url = upload_image(str(HERO))
    done = []
    for ep in todo:
        try:
            final = build_episode(ep, hero_url)
        except Exception as e:
            print(f"  EP.{ep['ep']} FAILED: {e}", flush=True)
            continue
        if final:
            done.append((ep, final))
            print(f"  DONE -> {final}", flush=True)

    print(f"\n=== {len(done)}/{len(todo)} EPISODES READY ===", flush=True)
    for ep, f in done:
        print(f"  EP.{ep['ep']:>2} {ep['title']:<16} {f}", flush=True)
    if done:
        print("\npost them in order with: python post_next_viking.py", flush=True)


if __name__ == "__main__":
    main()
