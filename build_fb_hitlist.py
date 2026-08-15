"""
Facebook engagement hit-list — the 5-minute manual visibility routine.

The API can't comment on other pages' posts, so the human does the last tap:
this generates today's target list — the hottest PSL stories, which page's
Facebook to visit, and a ready-to-paste comment in the Genesis News voice for
each. Open the file on your phone, comment AS the page, done.

Output: output/hitlists/hitlist_<date>.md  (scheduled daily 08:30)
Usage:  python build_fb_hitlist.py
"""
import asyncio
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

# Where the conversation happens — the outlets and clubs whose posts to hit.
SOURCE_PAGES = {
    "soccer laduma": ("Soccer Laduma", "https://www.facebook.com/SoccerLaduma"),
    "kickoff": ("KickOff", "https://www.facebook.com/kickoffmagazine"),
    "idiski": ("iDiski Times", "https://www.facebook.com/iDiskiTimes"),
    "sabc": ("SABC Sport", "https://www.facebook.com/SABCSportSA"),
    "goal": ("Goal Africa", "https://www.facebook.com/GoalAfrica"),
    "farpost": ("FARPost", "https://www.facebook.com/farpost.co.za"),
}
CLUB_PAGES = {
    "chiefs": ("Kaizer Chiefs (official)", "https://www.facebook.com/KaizerChiefs"),
    "pirates": ("Orlando Pirates (official)", "https://www.facebook.com/orlandopiratesfc"),
    "sundowns": ("Mamelodi Sundowns (official)", "https://www.facebook.com/Sundowns"),
}


async def build():
    from modules.psl_news import get_psl_briefing
    from modules.community_manager import generate_reply
    from modules.club_brand import resolve_club

    briefing = await get_psl_briefing()
    stories = []
    for key in ("chiefs", "pirates", "sundowns", "premiership", "cups"):
        for it in (briefing.get(key) or [])[:3]:
            if isinstance(it, dict) and it.get("title"):
                stories.append(it)
    # dedupe by title
    seen, uniq = set(), []
    for s in stories:
        t = s["title"].lower()[:60]
        if t not in seen:
            seen.add(t)
            uniq.append(s)
    uniq = uniq[:8]

    lines = [f"# Genesis News — FB Engagement Hit-List · {datetime.now():%a %d %b %Y}",
             "",
             "Comment AS the Genesis News page. One comment per target, "
             "space them out through the day. Value first — the page name does "
             "the marketing.", ""]
    for i, s in enumerate(uniq, 1):
        src = (s.get("source") or "").lower()
        page = next((v for k, v in SOURCE_PAGES.items() if k in src), None)
        if not page:
            ck = resolve_club(s["title"])
            page = CLUB_PAGES.get(ck) or SOURCE_PAGES["soccer laduma"]
        prompt = {"message": (f"(Write ONE comment to post under a Facebook post "
                              f"about this story: '{s['title']}'. Fan-to-fan, "
                              f"warm Mzansi banter, a real take or question that "
                              f"invites replies. NO links, NO self-promo. "
                              f"Max 2 sentences.)"),
                  "from_name": "", "post_context": s["title"]}
        comment = await generate_reply(prompt, "sa_pulse") or \
            "Big story this — what do the fans think? 👀⚽"
        lines += [f"## {i}. {s['title']}",
                  f"- **Where:** [{page[0]}]({page[1]}) — find their post on this story",
                  f"- **Paste this:** {comment}", ""]

    out = Path("output/hitlists")
    out.mkdir(parents=True, exist_ok=True)
    p = out / f"hitlist_{datetime.now():%Y%m%d}.md"
    p.write_text("\n".join(lines), encoding="utf-8")
    print(f"[Hitlist] {len(uniq)} targets -> {p}")
    return str(p)


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    asyncio.run(build())
