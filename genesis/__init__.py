"""Genesis Content Engine — Full Automation for 4 Brands."""
import sys
import io

# Fix Windows console encoding for emoji/unicode in print statements
if sys.platform == "win32":
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
    except Exception:
        pass
