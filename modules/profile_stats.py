"""What each posted reel actually did, so the rotation can favour what works.

Owner 2026-09-08: "can we prioritise the videos that work on personal profile."

THE GAP THIS FILLS. dance_cast.pick() and dance_drivers.pick() are pure
fairness rotations - least-used setting, then character, then template. That
was the right first design: it stopped the profile posting the same braai
twenty times running. But it also means a combination that pulled 2.7M and one
that pulled 800 views are equally likely to come up next, which is a rota, not
a content strategy.

Most of what was needed already existed. output/reel_runs.jsonl records, for
every publish, the combo, the driver, the caption and - through the
first-comment step - the reel URL. The only missing piece was the one number
that matters, and this module fetches it.

WHY SCRAPING. There is no Graph API for a personal profile, which is the same
reason posting goes through a browser at all (see uploader_fb_profile). So
view counts come off the reels grid on the same cookie transport, with the
same caution: the selectors are Facebook's and they will move. Every failure
here is deliberately non-fatal - an unscored reel simply does not vote, and
the rotation falls back to the fairness order it uses today.

    py -m modules.profile_stats            # refresh, then print the table
    from modules.profile_stats import scores
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).parent.parent
RUNS = ROOT / "output" / "reel_runs.jsonl"
PERF = ROOT / "data" / "profile_perf.json"

# A reel tile carries its view count as text near the link. Facebook writes it
# as "2.7M", "520K" or "1,234" depending on size, so all three are parsed.
# Walking up from the anchor for text, rather than naming a class, is
# deliberate: the class names here are generated and change weekly, the shape
# does not.
_JS_VIEWS = r"""
() => {
  const out = {};
  document.querySelectorAll('a[href*="/reel/"]').forEach(a => {
    const m = a.href.match(/\/reel\/(\d+)/);
    if (!m) return;
    let node = a, text = '';
    for (let i = 0; i < 4 && node; i++) {
      text = node.innerText || '';
      if (text && text.length > 1) break;
      node = node.parentElement;
    }
    const v = text.match(/([\d.,]+)\s*([KMkm]?)/);
    if (!v) return;
    let n = parseFloat(v[1].replace(/,/g, ''));
    if (isNaN(n)) return;
    const suf = (v[2] || '').toUpperCase();
    if (suf === 'K') n *= 1e3;
    if (suf === 'M') n *= 1e6;
    if (out[m[1]] === undefined || n > out[m[1]]) out[m[1]] = Math.round(n);
  });
  return out;
}
"""

_SCRIPT = r'''
import json, sys, time
from playwright.sync_api import sync_playwright

args = json.loads(sys.argv[1])
with sync_playwright() as p:
    b = p.chromium.launch(headless=args.get("headless", True),
                          args=["--disable-blink-features=AutomationControlled"])
    ctx = b.new_context(
        viewport={"width": 1280, "height": 1400},
        user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"))
    ctx.add_cookies(args["cookies"])
    page = ctx.new_page()
    page.goto("https://www.facebook.com/me/reels",
              wait_until="domcontentloaded", timeout=90000)
    time.sleep(8)
    for _ in range(int(args.get("scrolls", 6))):
        page.mouse.wheel(0, 2400)
        time.sleep(2)
    try:
        data = page.evaluate(args["js"])
    except Exception as e:
        print(json.dumps({"status": "failed", "error": str(e)[:200]}), flush=True)
        b.close()
        sys.exit(0)
    print(json.dumps({"status": "ok", "views": data}), flush=True)
    b.close()
'''


def _runs() -> list:
    if not RUNS.exists():
        return []
    out = []
    for line in RUNS.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except Exception:
            continue
    return out


def _reel_id(row: dict) -> str:
    c = row.get("comment")
    url = c.get("url", "") if isinstance(c, dict) else ""
    return url.rsplit("/", 1)[-1] if "/reel/" in url else ""


def collect(headless: bool = True) -> dict:
    """{reel_id: views} read off the profile grid. {} on any failure."""
    from modules.profile_commenter import _get_auth
    auth = _get_auth()
    if not auth:
        print("[Stats] no profile cookies - set FB_PROFILE_C_USER / FB_PROFILE_XS")
        return {}
    payload = {"cookies": auth, "js": _JS_VIEWS, "headless": headless}
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False,
                                     encoding="utf-8") as f:
        f.write(_SCRIPT)
        script = f.name
    try:
        r = subprocess.run([sys.executable, script, json.dumps(payload)],
                           capture_output=True, text=True, encoding="utf-8",
                           timeout=420)
        lines = [l for l in (r.stdout or "").splitlines() if l.startswith("{")]
        if not lines:
            print("[Stats] no result from the browser: "
                  + (r.stderr or "")[:200])
            return {}
        d = json.loads(lines[-1])
        if d.get("status") != "ok":
            print("[Stats] " + str(d.get("error"))[:160])
            return {}
        return d.get("views", {})
    except Exception as e:
        print("[Stats] collect failed: " + str(e)[:160])
        return {}
    finally:
        Path(script).unlink(missing_ok=True)


def refresh(headless: bool = True) -> dict:
    """Fetch views and merge them into the performance ledger."""
    views = collect(headless=headless)
    if not views:
        return _perf()
    perf = _perf()
    perf.update({k: int(v) for k, v in views.items()})
    PERF.parent.mkdir(parents=True, exist_ok=True)
    PERF.write_text(json.dumps(perf, indent=2), encoding="utf-8")
    print("[Stats] %d reels measured, ledger holds %d" % (len(views), len(perf)))
    return perf


def _perf() -> dict:
    try:
        return json.loads(PERF.read_text(encoding="utf-8"))
    except Exception:
        return {}


def scores() -> dict:
    """Median views per choice, keyed by axis.

    MEDIAN, not mean. This profile's distribution is one 2.7M reel against a
    ~2.5K median, so an average would let a single outlier crown whatever
    setting it happened to use. The median asks the more useful question:
    what does a TYPICAL post with this choice do.

    Returns {"setting": {...}, "character": {...}, "template": {...},
             "driver": {...}, "n": posts_scored}.
    """
    perf = _perf()
    empty = {"setting": {}, "character": {}, "template": {}, "driver": {},
             "n": 0}
    if not perf:
        return empty
    buckets = {"setting": {}, "character": {}, "template": {}, "driver": {}}
    n = 0
    for row in _runs():
        if not row.get("posted"):
            continue
        rid = _reel_id(row)
        if rid not in perf:
            continue
        combo = (row.get("combo") or "").split("|")
        if len(combo) != 3:
            continue
        v = perf[rid]
        n += 1
        for axis, key in (("character", combo[0]), ("template", combo[1]),
                          ("setting", combo[2]), ("driver", row.get("driver"))):
            if key:
                buckets[axis].setdefault(key, []).append(v)

    def med(xs):
        xs = sorted(xs)
        m = len(xs) // 2
        return xs[m] if len(xs) % 2 else (xs[m - 1] + xs[m]) // 2

    out = {a: {k: med(vs) for k, vs in b.items()} for a, b in buckets.items()}
    out["n"] = n
    return out


if __name__ == "__main__":
    refresh(headless="--show" not in sys.argv)
    s = scores()
    print("\nscored posts: %d" % s["n"])
    for axis in ("setting", "template", "character", "driver"):
        rows = sorted(s[axis].items(), key=lambda kv: -kv[1])
        if rows:
            print("\n" + axis.upper())
            for k, v in rows:
                print("   %-22s %10s" % (k, "{:,}".format(v)))
