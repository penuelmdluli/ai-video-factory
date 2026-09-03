"""
The factory calls Claude when something breaks, instead of waiting for the owner.

Owner call 2026-08-27: "this now needs to be a self healing and improvement
tool". Every failure so far has followed the same shape - something breaks at
19:00, nobody sees it until the next morning, and a slot goes out wrong or not
at all. The knowledge to fix most of them is in this repo; what is missing is
somebody noticing at the time.

So: detectors run on a schedule, and when one fires, this launches Claude Code
headless in this directory with the evidence and a narrow brief.

WHAT IT MAY DO
  read the repo, run diagnostics, edit code, commit on a branch.

WHAT IT MAY NEVER DO
  post anything. Publishing is the one action that cannot be taken back, and
  an unattended agent must not be the thing that puts a wrong reel in front of
  10,000 supporters. Publishers are blocked by tool policy AND by the brief,
  and every run is committed to a heal/ branch so nothing lands on main
  unreviewed.

GUARDS
  * MAX_RUNS_PER_DAY - a broken detector cannot spawn agents all night
  * one run at a time, via a lock file
  * every run logged to data/heal_log.json with the diff it produced
  * --dry prints the brief and launches nothing

    python self_heal.py --dry
    python self_heal.py                 # heal if anything is broken
    python self_heal.py --check-only    # just report what is broken
"""
import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))
SAST = timezone(timedelta(hours=2))
LOG = ROOT / "data" / "heal_log.json"
LOCK = ROOT / "data" / ".heal.lock"
MAX_RUNS_PER_DAY = 4
TIMEOUT_S = 1800

# Never let an unattended agent run a publisher.
BLOCKED = ("build_careers_post.py", "build_psl_slot.py", "build_prematch.py",
           "build_countdown.py", "build_debate_video.py", "matchday.py",
           "build_participation.py", "uploader_facebook", "uploader_youtube",
           "uploader_tiktok", "post_comment")


def _now():
    return datetime.now(SAST)


def _log_read():
    if LOG.exists():
        try:
            d = json.loads(LOG.read_text(encoding="utf-8"))
            return d if isinstance(d, list) else []
        except Exception:
            return []
    return []


def _log_write(entry):
    d = _log_read()
    d.append(entry)
    LOG.parent.mkdir(exist_ok=True)
    LOG.write_text(json.dumps(d[-100:], indent=2, ensure_ascii=False),
                   encoding="utf-8")


def _runs_today():
    today = _now().date().isoformat()
    return sum(1 for e in _log_read() if e.get("at", "").startswith(today))


def _healed_at(problem: str) -> str:
    """When a run for `problem` last SUCCEEDED, as 'YYYY-MM-DD HH:MM'.

    Empty string if it never has. Entries record the moment the run started,
    which is the conservative end to compare an alert against.
    """
    done = [e.get("at", "") for e in _log_read()
            if e.get("problem") == problem and e.get("ok")]
    return max(done) if done else ""


# ---------------------------------------------------------------- detectors

async def detect_async() -> list:
    """[{name, severity, evidence, brief}] - everything currently wrong."""
    found = []

    # 1. The facts pack the comment engine speaks from.
    try:
        from check_facts_integrity import run as facts_run
        problems = await facts_run()
        if problems:
            found.append({
                "name": "facts_pack",
                "severity": "high",
                "evidence": "\n".join("- " + p for p in problems),
                "brief": ("The PSL facts pack that modules/community_manager.py "
                          "speaks from is failing its integrity check, so "
                          "football replies are being skipped entirely. Read "
                          "modules/psl_facts.py and check_facts_integrity.py, "
                          "find why, and fix it. Verify by running "
                          "'python check_facts_integrity.py' until it is "
                          "clean."),
            })
    except Exception as e:
        found.append({"name": "facts_check_broken", "severity": "high",
                      "evidence": str(e),
                      "brief": ("check_facts_integrity.py will not run: "
                                + str(e) + ". Fix the checker itself.")})

    # 2. Builds that failed since we last looked.
    #
    # A logged failure is history, not a diagnosis. The first run of this
    # detector fired on an alert written twenty minutes earlier by a test that
    # broke the facts pack on purpose to prove the checker worked - the pack
    # was already fixed. An alert whose check now passes is noise, and noise
    # here costs a full agent run, so historical alerts are only trusted when
    # the thing they describe is still broken RIGHT NOW.
    alerts = ROOT / "data" / "fail_alerts.json"
    live_checks_passing = not any(f["name"] == "facts_pack" for f in found)
    if alerts.exists():
        try:
            data = json.loads(alerts.read_text(encoding="utf-8"))
            recent = [a for a in (data if isinstance(data, list) else [])
                      if a.get("at", "") >= (_now() - timedelta(hours=24)
                                             ).strftime("%Y-%m-%d %H:%M")]
            if live_checks_passing:
                recent = [a for a in recent if a.get("check") != "psl_facts"]
            # An alert that has already been healed is history too. The filter
            # above can only speak for psl_facts, because that check re-runs
            # live; a slot builder that died last night cannot be re-run here
            # (it posts). So the heal log stands in as the evidence: if a
            # build_failures run has already succeeded SINCE the alert was
            # written, the alert has had its agent.
            #
            # Without this the 2026-09-02 21:54 slot failure would have kept
            # firing for a full 24 hours after it was fixed, spending the
            # remaining daily runs re-diagnosing a repaired factory - and
            # handing each of those agents a brief asserting something is
            # broken when it is not. That is not merely wasteful: the
            # 2026-08-30 run shows where a confident false brief leads, having
            # come one --delete away from destroying a correct comment.
            healed = _healed_at("build_failures")
            if healed:
                recent = [a for a in recent if a.get("at", "") > healed]
            if recent:
                found.append({
                    "name": "build_failures",
                    "severity": "high",
                    "evidence": json.dumps(recent[-5:], indent=2)[:2000],
                    "brief": ("Builds failed in the last 24 hours. The alerts "
                              "are below. Find the root cause in the repo and "
                              "fix it. Do NOT re-post anything - only repair "
                              "the code so the next scheduled run succeeds."),
                })
        except Exception:
            pass

    # 3. Our own comments that have gone wrong or stale.
    try:
        from sweep_comments import sweep
        res = await sweep("sa_pulse", do_delete=False, posts=30)
        bad = res.get("findings") or []
        if bad:
            found.append({
                "name": "bad_comments",
                "severity": "medium",
                "evidence": json.dumps(
                    [{"id": b["id"], "msg": b["message"][:160],
                      "problems": b["problems"]} for b in bad[:5]], indent=2),
                "brief": ("Our own comments are making claims that no longer "
                          "hold. Work out which detector in sweep_comments.py "
                          "caught them and whether the ENGINE that wrote them "
                          "(modules/community_manager.py, modules/psl_facts.py) "
                          "has a gap that lets this class of claim through. "
                          "Fix the engine. Do not delete the comments - report "
                          "them for the owner."),
            })
    except Exception:
        pass

    return found


def detect() -> list:
    """Sync wrapper around detect_async.

    This used to be a plain function calling asyncio.run() inside itself. That
    works from a script and raises the moment a caller already inside an event
    loop uses it - which is exactly what happened on brain.py's first cycle:
    every detector failed with 'coroutine was never awaited', the exceptions
    were swallowed by the try/except around each one, and the run cheerfully
    reported a healthy factory. A checker that goes silent under an unexpected
    caller is worse than no checker, because it manufactures confidence. So
    async callers must await detect_async, and are told so rather than being
    handed an empty list.
    """
    import asyncio
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(detect_async())
    raise RuntimeError("detect() called from inside a running event loop - "
                       "await detect_async() instead")


# ------------------------------------------------------------------ healing

def build_prompt(problem: dict) -> str:
    return f"""You are repairing the AI Video Factory, unattended, in {ROOT}.

PROBLEM DETECTED: {problem['name']} (severity: {problem['severity']})

EVIDENCE
{problem['evidence']}

YOUR BRIEF
{problem['brief']}

HARD RULES
1. NEVER post, publish, upload or comment to any platform. Do not run any of:
   {', '.join(BLOCKED)}. Publishing is irreversible and a supporter sees the
   result; that decision stays with the owner.
2. Fix the CAUSE, not the symptom. This repo has a history of the same bug
   returning in a new shape.
3. Prove the fix. Run the relevant check and paste real output. If you cannot
   verify it, say so plainly rather than claiming success.
4. Match the surrounding code: comments explain WHY, referencing the incident
   that motivated the change.
5. Touch only what this problem requires.

When done, summarise in under 12 lines: what was wrong, what you changed, and
the exact command output proving it works. If you could not fix it, say what
you ruled out and what you would try next."""


def claude_exe() -> str | None:
    """Absolute path to the Claude CLI, or None.

    The first live run failed instantly with "claude CLI not on PATH" while
    `which claude` in the shell resolved it fine. The npm install ships three
    files - `claude` (a bash shim with no extension), `claude.cmd` and
    `claude.ps1`. Git Bash finds the extensionless shim; Python's subprocess
    on Windows goes through CreateProcess, which only considers the
    extensions in PATHEXT, so it sees nothing. Resolving to the .cmd
    explicitly is the whole fix.

    Checked in order: PATH under each Windows extension, then the npm global
    directory, which is where it actually lives on this machine.
    """
    import shutil
    for name in ("claude.cmd", "claude.exe", "claude.bat", "claude"):
        found = shutil.which(name)
        if found and Path(found).suffix.lower() in (".cmd", ".exe", ".bat"):
            return found
    npm = Path(os.environ.get("APPDATA", "")) / "npm"
    for name in ("claude.cmd", "claude.exe", "claude.bat"):
        p = npm / name
        if p.exists():
            return str(p)
    return None


def heal(problem: dict, dry=False) -> dict:
    brief = build_prompt(problem)
    branch = "heal/" + problem["name"] + "-" + _now().strftime("%m%d-%H%M")

    if dry:
        print("=" * 70)
        print("WOULD RUN claude headless on branch " + branch)
        print("=" * 70)
        print(brief)
        return {"dry": True, "problem": problem["name"], "branch": branch}

    started = _now()

    # Resolve the CLI BEFORE branching. The first live run created a heal
    # branch, failed to find claude, and left the repo checked out on an
    # empty branch - the fix must be found before anything is disturbed.
    exe = claude_exe()
    if not exe:
        entry = {"at": started.strftime("%Y-%m-%d %H:%M"),
                 "problem": problem["name"], "branch": "", "ok": False,
                 "minutes": 0.0, "changed": "",
                 "summary": "Claude CLI not found - searched PATH for "
                            "claude.cmd/.exe/.bat and %APPDATA%\\npm"}
        _log_write(entry)
        print("[Heal] " + entry["summary"])
        return entry

    try:
        subprocess.run(["git", "checkout", "-b", branch], cwd=str(ROOT),
                       capture_output=True, text=True, timeout=60)
    except Exception as e:
        print("[Heal] could not branch: " + str(e))

    cmd = [exe, "-p", brief,
           "--allowedTools", "Read,Edit,Write,Grep,Glob,Bash",
           "--output-format", "json"]
    print("[Heal] " + problem["name"] + " -> claude on " + branch)
    try:
        r = subprocess.run(cmd, cwd=str(ROOT), capture_output=True,
                           text=True, timeout=TIMEOUT_S,
                           env={**os.environ, "CLAUDE_HEAL": "1"})
        raw = r.stdout or ""
        try:
            summary = json.loads(raw).get("result", raw)[:4000]
        except Exception:
            summary = raw[:4000]
        ok = r.returncode == 0
    except subprocess.TimeoutExpired:
        summary, ok = f"timed out after {TIMEOUT_S}s", False
    except FileNotFoundError:
        summary, ok = "claude CLI not on PATH", False
    except Exception as e:
        summary, ok = str(e), False

    try:
        diff = subprocess.run(["git", "diff", "--stat", "HEAD"], cwd=str(ROOT),
                              capture_output=True, text=True,
                              timeout=60).stdout.strip()
    except Exception:
        diff = ""

    entry = {"at": started.strftime("%Y-%m-%d %H:%M"), "problem": problem["name"],
             "severity": problem["severity"], "branch": branch, "ok": ok,
             "minutes": round((_now() - started).total_seconds() / 60, 1),
             "changed": diff, "summary": summary}
    _log_write(entry)
    print("[Heal] done in " + str(entry["minutes"]) + "m, changed: "
          + (diff.replace("\n", " | ") if diff else "nothing"))
    return entry


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--check-only", action="store_true")
    a = ap.parse_args()

    problems = detect()
    stamp = _now().strftime("%Y-%m-%d %H:%M")
    if not problems:
        print("[Heal] " + stamp + " - nothing broken")
        return 0

    print("[Heal] " + stamp + " - " + str(len(problems)) + " problem(s):")
    for p in problems:
        print("  ! " + p["name"] + " (" + p["severity"] + ")")
        for line in p["evidence"].splitlines()[:4]:
            print("      " + line[:120])
    if a.check_only:
        return 1

    if not a.dry:
        if _runs_today() >= MAX_RUNS_PER_DAY:
            print("[Heal] daily cap reached (" + str(MAX_RUNS_PER_DAY)
                  + ") - not launching. A detector may be stuck.")
            return 1
        if LOCK.exists():
            print("[Heal] another heal is running - skipping")
            return 1
        LOCK.parent.mkdir(exist_ok=True)
        LOCK.write_text(stamp, encoding="utf-8")

    try:
        # Highest severity first, one per run: a repo changing under a second
        # agent is how two fixes become one broken file.
        problems.sort(key=lambda p: 0 if p["severity"] == "high" else 1)
        heal(problems[0], dry=a.dry)
    finally:
        if LOCK.exists():
            try:
                LOCK.unlink()
            except OSError:
                pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
