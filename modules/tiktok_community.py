"""
TikTok community engine — the "family we chat" rule, extended to TikTok.

TikTok has no comment API, so this drives the web UI with the same session
cookie the uploader uses. It is deliberately CONSERVATIVE: TikTok punishes
bot-like engagement much harder than bot-like posting, so per run it makes at
most MAX_ACTIONS comment actions with human-like pauses, and it only ever
touches OUR OWN videos:
  1. seeds one engagement comment on any recent video of ours that has none
  2. replies to a handful of unanswered fan comments (same Claude->Gemini->
     template brain as YouTube/Facebook)

Dedupe lives in data/tt_replied.json. Runs from Task Scheduler 3x/day.

Usage: python -m modules.tiktok_community
"""
import asyncio
import json
import os
import random
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from dotenv import load_dotenv
load_dotenv(override=True)

PROFILE = "https://www.tiktok.com/@genesisnewspsl"
STORE = Path(__file__).parent.parent / "data" / "tt_replied.json"
MAX_VIDEOS = 4
MAX_ACTIONS = 6

SEEDS = [
    "PSL family - what's your take? Drop it below",
    "Rate this out of 10, Mzansi",
    "Chiefs, Pirates or Sundowns - who's your team? Tell us below",
    "What's your score prediction? Let's hear it",
]


def _store() -> dict:
    try:
        return json.loads(STORE.read_text(encoding="utf-8"))
    except Exception:
        return {"seeded": [], "replied": []}


def _save(s: dict):
    STORE.parent.mkdir(parents=True, exist_ok=True)
    STORE.write_text(json.dumps(s, indent=2), encoding="utf-8")


def _pause(a=2.5, b=6.0):
    time.sleep(random.uniform(a, b))


def run() -> int:
    from playwright.sync_api import sync_playwright

    sid = os.getenv("TIKTOK_SESSION_ID", "").strip()
    if not sid:
        print("[TT-Community] no TIKTOK_SESSION_ID")
        return 0
    store = _store()
    actions = 0

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(
            user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/126.0.0.0 Safari/537.36"))
        ctx.add_cookies([{"name": "sessionid", "value": sid,
                          "domain": ".tiktok.com", "path": "/"}])
        page = ctx.new_page()
        page.goto(PROFILE, wait_until="domcontentloaded", timeout=60000)
        _pause(6, 9)
        page.mouse.wheel(0, 600)
        _pause(2, 4)

        links = page.eval_on_selector_all(
            '[data-e2e="user-post-item"] a[href*="/video/"]',
            "els => els.map(e => e.href)")
        if not links:      # fallback: any grid anchor
            links = page.eval_on_selector_all(
                'a[href*="/video/"]', "els => els.map(e => e.href)")
        links = list(dict.fromkeys(links))[:MAX_VIDEOS]
        print(f"[TT-Community] {len(links)} recent videos")

        for url in links:
            if actions >= MAX_ACTIONS:
                break
            vid = url.rstrip("/").split("/")[-1].split("?")[0]
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=60000)
                _pause(8, 11)
                # comments live behind the right panel's "Comments" tab — an ad
                # overlay blocks normal clicks, so dispatch real events in JS
                # on the deepest element whose text is exactly "Comments"
                opened = False
                for _attempt in range(3):
                    page.evaluate(
                        "() => {"
                        " const cands=[...document.querySelectorAll('*')]"
                        "  .filter(e=>e.textContent.trim().replace(/\\s*\\d+$/,'')==='Comments'"
                        "          && e.getBoundingClientRect().width>0);"
                        " if (!cands.length) return false;"
                        " const t=cands[cands.length-1];"
                        " for (const ev of ['pointerdown','mousedown','pointerup','mouseup','click'])"
                        "  t.dispatchEvent(new MouseEvent(ev,{bubbles:true,cancelable:true,view:window}));"
                        " return true; }")
                    _pause(3, 5)
                    if page.query_selector('div[contenteditable="true"]'):
                        opened = True
                        break
                if not opened:
                    print(f"[TT-Community] {vid}: comment panel didn't open")
                    continue

                # seed one engagement comment if we never have
                if vid not in store["seeded"]:
                    focused = page.evaluate(
                        "() => { const b=document.querySelector("
                        "'div[contenteditable=\"true\"]');"
                        " if (!b) return false; b.scrollIntoView();"
                        " b.focus(); return true; }")
                    if focused:
                        _pause(1, 2)
                        page.keyboard.type(random.choice(SEEDS),
                                           delay=random.randint(40, 90))
                        _pause(1, 2)
                        posted = page.evaluate(
                            "() => { const p=document.querySelector("
                            "'[data-e2e=\"comment-post\"]');"
                            " if (!p) return false;"
                            " for (const ev of ['pointerdown','mousedown',"
                            "'pointerup','mouseup','click'])"
                            "  p.dispatchEvent(new MouseEvent(ev,"
                            "{bubbles:true,cancelable:true,view:window}));"
                            " return true; }")
                        if posted:
                            store["seeded"].append(vid)
                            actions += 1
                            print(f"[TT-Community] seeded comment on {vid}")
                            _save(store)
                            _pause(5, 9)

                # reply to unanswered fan comments
                items = page.query_selector_all(
                    '[data-e2e="comment-level-1"]')[:8]
                for it in items:
                    if actions >= MAX_ACTIONS:
                        break
                    text = (it.inner_text() or "").strip()
                    if not text:
                        continue
                    key = f"{vid}:{hash(text) & 0xffffffff}"
                    if key in store["replied"]:
                        continue
                    container = it.evaluate_handle(
                        "e => e.closest('[class*=CommentItem], [data-e2e*=comment-item]') || e.parentElement.parentElement")
                    reply_btn = container.as_element().query_selector(
                        'span[data-e2e="comment-reply-1"], [data-e2e*="reply"]') \
                        if container else None
                    if not reply_btn:
                        continue
                    try:
                        from modules.community_manager import generate_reply
                        reply = asyncio.run(generate_reply(
                            {"text": text, "author": ""}, "sa_pulse"))
                    except Exception:
                        reply = "Love this - keep it coming, PSL family!"
                    if not reply:
                        continue
                    reply_btn.click()
                    _pause(1, 2)
                    box = page.query_selector(
                        '[data-e2e="comment-input"] [contenteditable="true"], '
                        'div[contenteditable="true"]')
                    if not box:
                        continue
                    box.type(reply[:140], delay=random.randint(40, 90))
                    _pause(1, 2)
                    post = page.query_selector('[data-e2e="comment-post"]')
                    if post:
                        post.click()
                        store["replied"].append(key)
                        actions += 1
                        print(f"[TT-Community] replied on {vid}: {text[:40]!r}")
                        _save(store)
                        _pause(6, 12)
            except Exception as e:
                print(f"[TT-Community] {vid} skipped: {str(e)[:100]}")
        browser.close()
    print(f"[TT-Community] done — {actions} actions")
    return actions


if __name__ == "__main__":
    try:
        run()
    except Exception as e:
        print(f"[TT-Community] FAILED: {e}")
        try:
            from modules.notify_whatsapp import notify_failure
            notify_failure("tt-community",
                           f"TIKTOK COMMUNITY FAILED: {type(e).__name__}: {str(e)[:120]}")
        except Exception:
            pass
        raise
