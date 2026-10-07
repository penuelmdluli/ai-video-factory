"""The slot must believe the receipt, not the exit code.

Covers the 2026-10-06 failure: build_matchday_hype published a roll call to
Facebook and YouTube and then died during interpreter shutdown with Windows
exit code 3221226505 (0xC0000409). The router read that code as "the slot
posted nothing", which skipped the daily ledger (letting a third roll call go
out past a cap of two) and raised a false build-failure alert that woke the
self-heal agent five times.

Run:  python tests/test_publish_receipt.py
"""
import json
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import modules.publish_reel as pr

FAILS = []


def check(name, cond):
    print(("  ok   " if cond else "  FAIL ") + name)
    if not cond:
        FAILS.append(name)


def with_temp_receipts(fn):
    """Each case gets its own receipts file - never touch the live one."""
    real = pr.RECEIPTS
    with tempfile.TemporaryDirectory() as d:
        pr.RECEIPTS = Path(d) / "publish_receipts.json"
        try:
            fn()
        finally:
            pr.RECEIPTS = real


def test_receipt_round_trip():
    print("receipt round trip")
    before = pr.receipt_ids()
    pr._record_receipt("sa_pulse", "rollcall", ["facebook", "youtube"])

    hits = pr.receipts_added(before, "sa_pulse")
    check("a publish leaves exactly one receipt", len(hits) == 1)
    check("the receipt names the channels that took it",
          hits and hits[0]["channels"] == ["facebook", "youtube"])
    check("the receipt names the page", hits and hits[0]["niche"] == "sa_pulse")

    check("another page's receipt is not this page's evidence",
          pr.receipts_added(before, "tech_news") == [])
    check("a receipt is new only once",
          pr.receipts_added(pr.receipt_ids(), "sa_pulse") == [])


def test_two_runs_back_to_back():
    """The flaw the first version of this fix shipped with.

    Timestamps needed slack for the gap between two clock reads, and that slack
    let a build which posted NOTHING inherit the previous build's receipt. Ids
    make the two runs distinguishable no matter how close together they land.
    """
    print("a failing run cannot inherit the previous run's post")
    first = pr.receipt_ids()
    pr._record_receipt("sa_pulse", "rollcall", ["facebook"])   # run 1 posts
    check("run 1 sees its own post", len(pr.receipts_added(first)) == 1)

    second = pr.receipt_ids()                                  # run 2 starts
    check("run 2 posts nothing and sees nothing",
          pr.receipts_added(second, "sa_pulse") == [])


def test_no_receipt_when_nothing_went_live():
    print("a slot that posted nothing leaves nothing")
    check("no receipt exists before anything publishes",
          pr.receipts_added(pr.receipt_ids(), "sa_pulse") == [])


def test_corrupt_file_is_not_evidence():
    print("a mangled receipts file reads as 'no evidence'")
    pr.RECEIPTS.parent.mkdir(parents=True, exist_ok=True)
    pr.RECEIPTS.write_text("{not json", encoding="utf-8")
    check("garbage never reads as a successful post",
          pr.receipts_added(set(), "sa_pulse") == [])
    # and the next real publish must still be recorded
    pr._record_receipt("sa_pulse", "rollcall", ["facebook"])
    check("a publish after corruption is still recorded",
          len(pr.receipts_added(set(), "sa_pulse")) == 1)


def test_receipts_are_capped():
    print("the receipts file cannot grow forever")
    for i in range(pr.RECEIPTS_KEEP + 25):
        pr._record_receipt("sa_pulse", "rollcall", ["facebook"])
    data = json.loads(pr.RECEIPTS.read_text(encoding="utf-8"))
    check(f"kept to the last {pr.RECEIPTS_KEEP}",
          len(data) == pr.RECEIPTS_KEEP)


def test_slot_trusts_the_receipt_over_the_exit_code():
    """The actual regression, through build_psl_slot._run."""
    print("build_psl_slot._run normalises a dirty shutdown")
    import build_psl_slot as slot

    CRASH = 3221226505          # 0xC0000409 STATUS_STACK_BUFFER_OVERRUN

    class FakeProc:
        def __init__(self, rc):
            self.returncode = rc

    calls = {"n": 0}

    def fake_run(published, rc):
        def _run(*a, **k):
            calls["n"] += 1
            if published:
                pr._record_receipt("sa_pulse", "rollcall",
                                   ["facebook", "youtube"])
            return FakeProc(rc)
        return _run

    real_run = slot.subprocess.run
    try:
        # 1. crashed at shutdown, but the reel is live -> success
        slot.subprocess.run = fake_run(published=True, rc=CRASH)
        check("a crash AFTER publishing reports success",
              slot._run(["py", "build_matchday_hype.py"]) == 0)

        # 2. crashed with nothing live -> still a real failure
        slot.subprocess.run = fake_run(published=False, rc=CRASH)
        check("a crash with nothing live still reports failure",
              slot._run(["py", "build_matchday_hype.py"]) == CRASH)

        # 3. an ordinary clean run is untouched
        slot.subprocess.run = fake_run(published=False, rc=0)
        check("a clean run still reports success",
              slot._run(["py", "build_matchday_hype.py"]) == 0)

        # 4. a FAILED build must not inherit the PREVIOUS slot's receipt
        slot.subprocess.run = fake_run(published=True, rc=0)
        slot._run(["py", "build_matchday_hype.py"])      # posts, succeeds
        slot.subprocess.run = fake_run(published=False, rc=1)
        check("a later failing build does not claim an earlier post",
              slot._run(["py", "build_psl_news.py"]) == 1)
    finally:
        slot.subprocess.run = real_run


if __name__ == "__main__":
    for t in (test_receipt_round_trip,
              test_two_runs_back_to_back,
              test_no_receipt_when_nothing_went_live,
              test_corrupt_file_is_not_evidence,
              test_receipts_are_capped,
              test_slot_trusts_the_receipt_over_the_exit_code):
        with_temp_receipts(t)
    print()
    if FAILS:
        print(f"{len(FAILS)} FAILED: " + "; ".join(FAILS))
        sys.exit(1)
    print("all green")
