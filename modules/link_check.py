"""
Link and claim gate for Mzansi Careers.

Two failures we are never repeating:
  1. A dead apply link went out on a page whose whole promise is "verified"
     (https://www.transnet.net/Careers/ 404s — the trailing slash breaks it,
     while /Careers is fine). Nothing posts now unless the link answers 200.
  2. Specifics were published that the official page never states — a closing
     date, a stipend, entry requirements, cities. On a jobs page a wrong
     deadline makes someone miss a real one. Every claim must now be found in
     the official source text, or it does not go in the post.
"""
import re

import requests

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")


def check_link(url: str, timeout=45) -> dict:
    """Follow the link like a person would. Returns {ok, status, final, note}.

    A redirect onto an error/default page counts as broken — several SharePoint
    sites answer 200 while quietly serving 'aspxerrorpath'.
    """
    try:
        r = requests.get(url, headers={"User-Agent": UA}, timeout=timeout,
                         allow_redirects=True)
    except Exception as e:
        return {"ok": False, "status": 0, "final": url,
                "note": f"unreachable: {e}"}
    final = str(r.url)
    if r.status_code != 200:
        return {"ok": False, "status": r.status_code, "final": final,
                "note": "not 200"}
    if "aspxerrorpath" in final or "error" in final.lower().split("/")[-1]:
        return {"ok": False, "status": 200, "final": final,
                "note": "redirected to an error page"}
    if len(r.text) < 500:
        return {"ok": False, "status": 200, "final": final,
                "note": "page is effectively empty"}
    return {"ok": True, "status": 200, "final": final, "note": "ok"}


def fetch_text(url: str, timeout=60) -> str:
    """Visible text of the official page, for claim checking."""
    r = requests.get(url, headers={"User-Agent": UA}, timeout=timeout)
    t = re.sub(r"<script.*?</script>|<style.*?</style>", " ", r.text,
               flags=re.S)
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", t))


def verify_claims(source_text: str, claims: list[str]) -> dict:
    """Which claims actually appear in the official source text."""
    found, missing = [], []
    for c in claims:
        needle = re.escape(c.strip())
        (found if re.search(needle, source_text, re.I) else missing).append(c)
    return {"found": found, "missing": missing,
            "ok": not missing}


def gate(job: dict) -> dict:
    """Hard gate before any careers post. Raises nothing — returns a verdict.

    job needs: apply_url, and 'must_verify' — the list of literal strings that
    have to appear on the official page (closing date, duration, requirements).
    """
    link = check_link(job.get("apply_url", ""))
    if not link["ok"]:
        return {"ok": False, "reason": f"apply link broken: {link['note']}",
                "link": link}
    must = job.get("must_verify") or []
    if not must:
        return {"ok": False, "link": link,
                "reason": "no must_verify claims listed — refusing to post "
                          "unverified specifics"}
    text = fetch_text(link["final"])
    v = verify_claims(text, must)
    if not v["ok"]:
        return {"ok": False, "link": link, "claims": v,
                "reason": "claims not found on the official page: "
                          + "; ".join(v["missing"])}
    return {"ok": True, "link": link, "claims": v, "reason": "verified"}
