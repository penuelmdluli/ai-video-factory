import pathlib
import sys
import tempfile

sys.path.insert(0, ".")
import modules.publish_reel as pr

# point the ledger at a temp file so the repo's data/ is untouched
pr.DEDUPE_LOG = pathlib.Path(tempfile.mkdtemp()) / "publish_dedupe.json"

cap = "WHO STARTS HERE? Shabalala or Duba - one shirt, two names"
ct = pr._content_type(cap)
k = pr._dupe_key("sa_pulse", ct, cap)
print("content_type          =", ct)
print("first run duplicate?  ", k in pr._recent_keys())
pr._record_published(k)
print("after publish, dupe?  ", k in pr._recent_keys())
k2 = pr._dupe_key("sa_pulse", ct,
                  "WHO STARTS HERE? Shabalala or Duba -\n\none shirt, two names")
print("rewrapped same key?   ", k2 == k)
print("other page blocked?   ", pr._dupe_key("tech_news", ct, cap) in pr._recent_keys())
print("other caption blocked?", pr._dupe_key("sa_pulse", ct, cap + " extra") in pr._recent_keys())
pr.DEDUPE_LOG.write_text('{"posted": {"%s": "2026-08-27T10:00:00"}}' % k, encoding="utf-8")
print("stale entry kept?     ", k in pr._recent_keys())
pr.DEDUPE_LOG.write_text("not json", encoding="utf-8")
print("corrupt ledger ->     ", pr._recent_keys())
