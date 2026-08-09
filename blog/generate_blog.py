#!/usr/bin/env python
"""Auto-blogging engine — the content hub that makes everything Google-discoverable.

Claude writes an SEO article per topic, embeds the matching YouTube video (drives
traffic to your channels), adds AdSense + affiliate slots (income), and renders a
fast static site for Cloudflare Pages. Cross-posts the link to Facebook.

Usage:
  python blog/generate_blog.py            # write the next rotating post + rebuild site
  python blog/generate_blog.py --seed     # generate one starter post per niche
Deploy (after `wrangler login` or a Pages token):
  cd blog && npx wrangler pages deploy build --project-name genesis-blog
"""
import os, sys, json, re, html, argparse, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BUILD = ROOT / "build"
POSTS = BUILD / "posts"
STATE = ROOT / "state.json"
SITE_NAME = "Genesis Hub"
SITE_TAGLINE = "Your home for music, learning & world stories — all in one place."
SITE_URL = os.getenv("BLOG_URL", "https://blog.genesisstudio.app")
CONTACT_EMAIL = os.getenv("BLOG_EMAIL", "mdlulipenuel@gmail.com")
ADSENSE_CLIENT = os.getenv("ADSENSE_CLIENT", "ca-pub-XXXXXXXXXXXXXXXX")  # set after AdSense approval
GSC_VERIFY = os.getenv("GSC_VERIFY", "")  # Google Search Console meta verification token

# The hub links out to every channel — one central home for all our video.
CHANNELS = [
    {"name": "AlphaZone Sounds", "url": "https://youtube.com/@AlphaZoneSound", "cat": "Music & Focus"},
    {"name": "Zuzu & Friends", "url": "https://youtube.com/@ZuzuAndFriends-u3o", "cat": "Kids"},
    {"name": "Herbal Organic Life", "url": "https://youtube.com/@herbalorganiclifeza", "cat": "Health & Organic"},
    {"name": "Tech Pulse Africa", "url": "https://youtube.com/@TechPulseAfricaZA", "cat": "World News"},
]
CATEGORIES = {"study": "Music & Focus", "sleep": "Music & Focus", "coding": "Music & Focus",
              "kids": "Kids", "wellness": "Health & Organic", "news": "World News",
              "sa": "South Africa", "viking": "Viking Saga"}
# Niches that need a "general info, not medical advice" note on their articles.
WELLNESS_NICHES = {"wellness"}
# Sensitive current-affairs niches: articles must stay neutral, balanced, solutions-focused;
# they get a light "general info, not legal advice" note.
NEUTRAL_NICHES = {"news", "sa"}

sys.path.insert(0, str(ROOT.parent))
try:
    from config import ANTHROPIC_API_KEY
except Exception:
    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

# topic -> which channel/video it promotes. Rotates for endless fresh content.
# Evergreen-weighted (best for steady ad revenue); news kept neutral & educational.
AZ = "dEAHmu2eWVg"; ZUZU = "MMcR0I1Y91g"; ZUZU2 = "8Rgg-neaA7E"; TPA = "s47wC1mEBME"
HERB = os.getenv("HERB_VIDEO", "")  # Herbal Organic featured video id (set after first safe upload)
MZANSI = os.getenv("MZANSI_VIDEO", "")  # Genesis News featured video id (set after first upload)
MZANSI_URL = os.getenv("MZANSI_URL", "https://www.facebook.com/1040762875792932")  # Genesis News page
TOPICS = [
    # ── Music & Focus (AlphaZone Sounds) ──
    {"niche": "study", "topic": "The best study music for deep focus and better grades",
     "video": AZ, "channel": "AlphaZone Sounds",
     "keywords": "study music, focus music, concentration, exam tips, deep work"},
    {"niche": "sleep", "topic": "How to fall asleep faster: a calm bedtime routine that works",
     "video": AZ, "channel": "AlphaZone Sounds",
     "keywords": "sleep music, fall asleep fast, bedtime routine, insomnia tips, relax"},
    {"niche": "coding", "topic": "The best music for coding and staying in flow as a developer",
     "video": AZ, "channel": "AlphaZone Sounds",
     "keywords": "coding music, programming focus, developer productivity, flow state"},
    {"niche": "study", "topic": "Focus music vs silence: what actually helps you concentrate",
     "video": AZ, "channel": "AlphaZone Sounds",
     "keywords": "focus music, concentration, background music, productivity, deep work"},
    {"niche": "sleep", "topic": "How rain sounds and white noise help you sleep and relax",
     "video": AZ, "channel": "AlphaZone Sounds",
     "keywords": "rain sounds, white noise, sleep sounds, relaxation, calm"},
    {"niche": "coding", "topic": "How to get into a flow state and stay productive for hours",
     "video": AZ, "channel": "AlphaZone Sounds",
     "keywords": "flow state, deep work, productivity, focus, time blocking"},
    {"niche": "study", "topic": "A simple study routine that helps you remember more",
     "video": AZ, "channel": "AlphaZone Sounds",
     "keywords": "study routine, memory, active recall, spaced repetition, exam prep"},
    {"niche": "sleep", "topic": "The science of meditation music for stress and better sleep",
     "video": AZ, "channel": "AlphaZone Sounds",
     "keywords": "meditation music, stress relief, calm, mindfulness, better sleep"},
    # ── Kids (Zuzu & Friends) ──
    {"niche": "kids", "topic": "Why nursery rhymes help toddlers learn (and the best ones to sing)",
     "video": ZUZU, "channel": "Zuzu & Friends",
     "keywords": "nursery rhymes, toddler learning, kids songs, early education, parenting"},
    {"niche": "kids", "topic": "Fun ways to teach toddlers their ABCs and numbers",
     "video": ZUZU2, "channel": "Zuzu & Friends",
     "keywords": "teach abc, counting for kids, early learning, preschool, toddler activities"},
    {"niche": "kids", "topic": "Screen time for toddlers: how to make it educational and calm",
     "video": ZUZU, "channel": "Zuzu & Friends",
     "keywords": "screen time, toddlers, educational videos, parenting tips, healthy habits"},
    {"niche": "kids", "topic": "Calm bedtime songs and routines for happy little ones",
     "video": ZUZU2, "channel": "Zuzu & Friends",
     "keywords": "bedtime songs, toddler sleep, lullaby, bedtime routine, parenting"},
    # ── World News (Tech Pulse Africa) — neutral, explainer style ──
    {"niche": "news", "topic": "Why the Red Sea shipping crisis affects fuel prices worldwide",
     "video": TPA, "channel": "Tech Pulse Africa",
     "keywords": "red sea, shipping, oil prices, global trade, economy explainer"},
    {"niche": "news", "topic": "How global shipping routes shape the prices you pay",
     "video": TPA, "channel": "Tech Pulse Africa",
     "keywords": "global trade, shipping routes, supply chain, prices, economy"},
    {"niche": "news", "topic": "Understanding world news: how to follow global events calmly",
     "video": TPA, "channel": "Tech Pulse Africa",
     "keywords": "world news, media literacy, global events, stay informed, explainer"},
]

# ── Health & Organic (Herbal Organic Life) — safe organic-lifestyle, no medical claims.
# Only added once a safe featured video exists (HERB set), so articles never embed old clickbait.
if HERB:
    TOPICS += [
        {"niche": "wellness", "topic": "Easy ways to add more vegetables to your meals every day",
         "video": HERB, "channel": "Herbal Organic Life",
         "keywords": "healthy eating, more vegetables, whole foods, organic food, healthy meals"},
        {"niche": "wellness", "topic": "How to start a simple herb garden on your windowsill",
         "video": HERB, "channel": "Herbal Organic Life",
         "keywords": "herb garden, grow herbs, windowsill garden, organic gardening, fresh herbs"},
        {"niche": "wellness", "topic": "Cooking with fresh herbs: simple flavour boosts for everyday meals",
         "video": HERB, "channel": "Herbal Organic Life",
         "keywords": "cooking with herbs, fresh herbs, flavour, healthy cooking, home cooking"},
        {"niche": "wellness", "topic": "How to read organic food labels when you shop",
         "video": HERB, "channel": "Herbal Organic Life",
         "keywords": "organic food labels, grocery shopping, organic living, healthy shopping"},
        {"niche": "wellness", "topic": "Simple whole-food breakfast ideas to start your day",
         "video": HERB, "channel": "Herbal Organic Life",
         "keywords": "healthy breakfast, whole foods, breakfast ideas, healthy habits, organic"},
    ]

# ── South Africa (Genesis News) — neutral, balanced current-affairs explainers.
# Added once the channel + first video exist (MZANSI set), so no broken embeds/links.
if MZANSI:
    CHANNELS.append({"name": "Genesis News", "url": MZANSI_URL, "cat": "South Africa"})
    TOPICS += [
        {"niche": "sa", "topic": "Where the jobs actually are in South Africa right now",
         "video": MZANSI, "channel": "Genesis News",
         "keywords": "South Africa jobs, employment, hiring sectors, youth jobs, careers SA"},
        {"niche": "sa", "topic": "How to spot and avoid job scams while job hunting in SA",
         "video": MZANSI, "channel": "Genesis News",
         "keywords": "job scams South Africa, job hunting, avoid scams, employment safety, careers"},
        {"niche": "sa", "topic": "Xenophobia in South Africa: the honest root causes and real solutions",
         "video": MZANSI, "channel": "Genesis News",
         "keywords": "South Africa, social cohesion, unemployment, community, solutions, unity"},
        {"niche": "sa", "topic": "Understanding new laws in South Africa and how they affect you",
         "video": MZANSI, "channel": "Genesis News",
         "keywords": "South Africa laws, your rights, regulations explained, citizens, government"},
        {"niche": "sa", "topic": "Practical ways South African families are beating the cost of living",
         "video": MZANSI, "channel": "Genesis News",
         "keywords": "cost of living South Africa, saving money, budgeting, families, tips"},
    ]

GSC_META = f'<meta name="google-site-verification" content="{GSC_VERIFY}">\n' if GSC_VERIFY else ""
FOOTER = (f'<footer>© {SITE_NAME} · <a href="/">Home</a> · <a href="/about">About</a> · '
          f'<a href="/privacy">Privacy</a> · <a href="mailto:{CONTACT_EMAIL}">Contact</a></footer>')

def _page(title, desc, body_html):
    """A simple static page (About / Privacy) sharing the site chrome + SEO."""
    return f"""<!doctype html><html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
{GSC_META}<title>{html.escape(title)} | {SITE_NAME}</title>
<meta name="description" content="{html.escape(desc)}">
<link rel="canonical" href="{SITE_URL}/{_slug(title)}">
<link rel="stylesheet" href="/style.css"></head><body>
<header><a class="logo" href="/">◆ {SITE_NAME}</a></header>
<main class="post"><h1>{html.escape(title)}</h1>{body_html}</main>
{FOOTER}</body></html>"""

def _about_body():
    ch = "".join(f'<li><a href="{c["url"]}" rel="noopener">{html.escape(c["name"])}</a> — {c["cat"]}</li>'
                 for c in CHANNELS)
    return (f"<p class='lead'>{html.escape(SITE_TAGLINE)}</p>"
            f"<p>{SITE_NAME} is a family of channels and guides covering focus &amp; sleep music, "
            f"kids learning, and clear, calm explainers on world events. We publish original videos "
            f"and practical articles so you can learn something new, relax, or get in the zone — all in one place.</p>"
            f"<h2>Our channels</h2><ul>{ch}</ul>"
            f"<h2>Contact</h2><p>Questions or feedback? Email "
            f"<a href='mailto:{CONTACT_EMAIL}'>{CONTACT_EMAIL}</a>.</p>")

def _privacy_body():
    return (f"<p class='date'>Last updated: {_today()}</p>"
            f"<p>{SITE_NAME} (\"we\", \"us\") respects your privacy. This page explains what data is "
            f"collected when you visit {SITE_URL} and how it is used.</p>"
            "<h2>Cookies &amp; advertising</h2><p>We may display ads served by Google AdSense and its "
            "partners. Third-party vendors, including Google, use cookies to serve ads based on your prior "
            "visits to this and other websites. Google's use of advertising cookies enables it and its "
            "partners to serve ads to you based on your visits. You may opt out of personalised advertising "
            "by visiting <a href='https://www.google.com/settings/ads' rel='noopener'>Google Ads Settings</a>.</p>"
            "<h2>Analytics</h2><p>We may use privacy-friendly analytics to understand overall traffic. "
            "We do not sell your personal information.</p>"
            "<h2>Embedded content</h2><p>Articles embed videos from YouTube. Watching them is subject to "
            "<a href='https://policies.google.com/privacy' rel='noopener'>Google's privacy policy</a>.</p>"
            "<h2>Your choices</h2><p>You can control cookies through your browser settings. By using this "
            f"site you consent to this policy.</p><h2>Contact</h2><p>Email <a href='mailto:{CONTACT_EMAIL}'>{CONTACT_EMAIL}</a>.</p>")

def _today():
    return __import__("datetime").date.today().isoformat()

def _slug(t):
    return re.sub(r"[^a-z0-9]+", "-", t.lower()).strip("-")[:70]

def _claude_article(topic, keywords, niche=""):
    """Return dict: {title, meta, intro, sections:[{h,p}], conclusion}. Falls back
    to a template if Claude is unavailable so the pipeline never hard-fails."""
    safety = ""
    if niche in NEUTRAL_NICHES:
        safety = ("This is sensitive current-affairs content. Stay STRICTLY NEUTRAL and "
                  "non-partisan — never endorse or attack any political party, leader or group; "
                  "be factual, balanced and calm; never inflammatory, fear-mongering or inciting. "
                  "For social tensions (e.g. xenophobia, immigration), focus on ROOT CAUSES and "
                  "CONSTRUCTIVE SOLUTIONS, never blaming or targeting any nationality; unifying tone. ")
    if ANTHROPIC_API_KEY:
        try:
            import anthropic
            c = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
            prompt = (f"Write a helpful, original SEO blog article about: {topic}\n"
                      f"Target keywords: {keywords}\n" + safety +
                      "Return ONLY JSON: {\"title\": \"catchy <60 char SEO title\", "
                      "\"meta\": \"<155 char meta description\", "
                      "\"intro\": \"2-sentence hook\", "
                      "\"sections\": [{\"h\": \"H2 heading\", \"p\": \"2-4 sentence paragraph\"}] (5 sections), "
                      "\"conclusion\": \"2-sentence wrap that invites watching the embedded video\"}. "
                      "Practical, genuine, friendly. No fluff, no medical/financial advice.")
            m = c.messages.create(model="claude-haiku-4-5-20251001", max_tokens=1600,
                                  messages=[{"role": "user", "content": prompt}])
            txt = m.content[0].text
            return json.loads(txt[txt.find("{"): txt.rfind("}") + 1])
        except Exception as e:
            print(f"[blog] Claude failed ({e}); template fallback")
    return {"title": topic[:60], "meta": topic[:150],
            "intro": f"Here is a practical guide to {topic.lower()}.",
            "sections": [{"h": "Overview", "p": f"Everything you need to know about {topic.lower()}."}],
            "conclusion": "Press play on the video below and enjoy."}

def _post_html(a, t):
    secs = "".join(
        f"<h2>{html.escape(s['h'])}</h2><p>{html.escape(s['p'])}</p>" for s in a.get("sections", []))
    ad = (f'<ins class="adsbygoogle" style="display:block" data-ad-client="{ADSENSE_CLIENT}" '
          f'data-ad-slot="0000000000" data-ad-format="auto" data-full-width-responsive="true"></ins>'
          f'<script>(adsbygoogle=window.adsbygoogle||[]).push({{}});</script>')
    if t.get("niche") in WELLNESS_NICHES:
        disc = ('<p class="disclaimer"><em>This article is general wellness &amp; lifestyle information, '
                'not medical advice. For questions about your health, please speak to a qualified '
                'professional.</em></p>')
    elif t.get("niche") in NEUTRAL_NICHES:
        disc = ('<p class="disclaimer"><em>This is general, balanced information to help you '
                'understand current events — not legal or professional advice. We aim to stay '
                'neutral and factual.</em></p>')
    else:
        disc = ""
    # Video block + share image differ for self-hosted (Viking mp4) vs embedded YouTube.
    if t.get("self_hosted"):
        og_image = f"{SITE_URL}{t.get('poster', '')}"
        watch_url = t.get("channel_url", SITE_URL)
        video_block = (
            f'<div class="vplayer"><video controls playsinline preload="none" '
            f'poster="{t.get("poster", "")}"><source src="{t["video"]}" type="video/mp4"></video></div>'
            f'<p class="cta">▶ Follow the saga on <a href="{watch_url}" rel="noopener">'
            f'{html.escape(t["channel"])}</a></p>')
    else:
        og_image = f"https://i.ytimg.com/vi/{t['video']}/maxresdefault.jpg"
        video_block = (
            f'<div class="video"><iframe src="https://www.youtube.com/embed/{t["video"]}" '
            f'title="Watch on {html.escape(t["channel"])}" frameborder="0" '
            f'allow="accelerometer;autoplay;clipboard-write;encrypted-media;gyroscope;picture-in-picture" '
            f'allowfullscreen loading="lazy"></iframe></div>'
            f'<p class="cta">▶ Watch more on <a href="https://youtube.com/watch?v={t["video"]}" '
            f'rel="noopener">{html.escape(t["channel"])}</a></p>')
    return f"""<!doctype html><html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
{GSC_META}<title>{html.escape(a['title'])} | {SITE_NAME}</title>
<meta name="description" content="{html.escape(a['meta'])}">
<meta name="keywords" content="{html.escape(t['keywords'])}">
<link rel="canonical" href="{SITE_URL}/posts/{t['slug']}">
<meta property="og:type" content="article"><meta property="og:title" content="{html.escape(a['title'])}">
<meta property="og:description" content="{html.escape(a['meta'])}">
<meta property="og:url" content="{SITE_URL}/posts/{t['slug']}">
<meta property="og:image" content="{og_image}">
<script type="application/ld+json">{{"@context":"https://schema.org","@type":"Article",
"headline":"{html.escape(a['title'])}","description":"{html.escape(a['meta'])}",
"datePublished":"{t['date']}","author":{{"@type":"Organization","name":"{SITE_NAME}"}}}}</script>
<script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client={ADSENSE_CLIENT}" crossorigin="anonymous"></script>
<link rel="stylesheet" href="/style.css"></head><body>
<header><a class="logo" href="/">◆ {SITE_NAME}</a></header>
<main class="post"><h1>{html.escape(a['title'])}</h1>
<p class="date">{t['date']}</p>
<p class="lead">{html.escape(a['intro'])}</p>
{ad}
{secs}
{video_block}
<p>{html.escape(a['conclusion'])}</p>
{disc}
{ad}
</main>{FOOTER}</body></html>"""

def _card(p):
    # Self-hosted posts (e.g. Viking) carry their own poster; YouTube posts use the YT thumbnail.
    thumb = p.get("poster") or f'https://i.ytimg.com/vi/{p["video"]}/mqdefault.jpg'
    return (f'<a class="card" href="/posts/{p["slug"]}">'
            f'<img loading="lazy" src="{thumb}" alt="">'
            f'<div><h3>{html.escape(p["title"])}</h3><span>{p["date"]} · {p["channel"]}</span></div></a>')

def _index_html(posts):
    # group posts by category for a true hub feel
    by_cat = {}
    for p in posts:
        by_cat.setdefault(CATEGORIES.get(p.get("niche", ""), "More"), []).append(p)
    sections = ""
    for cat, items in by_cat.items():
        sections += (f'<section class="cat"><h2>{html.escape(cat)}</h2>'
                     f'<div class="grid">{"".join(_card(p) for p in items)}</div></section>')
    chan = "".join(f'<a class="chip" href="{c["url"]}" rel="noopener">▶ {html.escape(c["name"])}</a>'
                   for c in CHANNELS)
    return f"""<!doctype html><html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{SITE_NAME} — Music, Learning &amp; World Stories</title>
<meta name="description" content="{html.escape(SITE_TAGLINE)} Study &amp; sleep music, coding focus, kids learning and world news — videos to watch and read.">
{GSC_META}<link rel="canonical" href="{SITE_URL}/">
<meta property="og:title" content="{SITE_NAME}"><meta property="og:description" content="{html.escape(SITE_TAGLINE)}">
<script type="application/ld+json">{{"@context":"https://schema.org","@type":"WebSite","name":"{SITE_NAME}","url":"{SITE_URL}/"}}</script>
<link rel="stylesheet" href="/style.css"></head><body>
<header><a class="logo" href="/">◆ {SITE_NAME}</a></header>
<div class="hero"><h1>{SITE_NAME}</h1><p class="lead">{html.escape(SITE_TAGLINE)}</p>
<div class="chips">{chan}</div></div>
<main>{sections}</main>
{FOOTER}</body></html>"""

STYLE = """*{box-sizing:border-box}body{margin:0;font-family:system-ui,Segoe UI,Roboto,sans-serif;color:#1a1a2e;background:#f7f7fb;line-height:1.6}
header{background:#1a1240;padding:16px 24px}.logo{color:#fff;font-weight:800;font-size:20px;text-decoration:none}
main{max-width:1040px;margin:0 auto;padding:24px}h1{font-size:2rem;line-height:1.2}.lead{font-size:1.15rem;color:#555}
.hero{background:linear-gradient(135deg,#1a1240,#4a2fb0);color:#fff;text-align:center;padding:56px 24px}
.hero h1{font-size:2.6rem;margin:0 0 8px}.hero .lead{color:#e6e0ff}
.chips{margin-top:18px;display:flex;gap:10px;justify-content:center;flex-wrap:wrap}
.chip{background:rgba(255,255,255,.14);color:#fff;padding:8px 16px;border-radius:22px;text-decoration:none;font-weight:600;font-size:.95rem}
.chip:hover{background:rgba(255,255,255,.26)}.cat{margin:34px 0}.cat h2{border-left:4px solid #6d3bd4;padding-left:12px}
.post{max-width:820px}
.date{color:#888;font-size:.9rem}.post h2{margin-top:1.6em}.video{position:relative;padding-top:56.25%;margin:24px 0;border-radius:12px;overflow:hidden}
.video iframe{position:absolute;inset:0;width:100%;height:100%}.cta a{color:#6d3bd4;font-weight:700}
.vplayer{max-width:360px;margin:24px auto;border-radius:12px;overflow:hidden;background:#000}
.vplayer video{width:100%;display:block;border-radius:12px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:18px}
.card{display:flex;flex-direction:column;background:#fff;border-radius:12px;overflow:hidden;text-decoration:none;color:inherit;box-shadow:0 2px 10px rgba(0,0,0,.06)}
.card img{width:100%;aspect-ratio:16/9;object-fit:cover}.card div{padding:12px}.card h3{margin:0 0 6px;font-size:1.05rem}
.card span{color:#888;font-size:.85rem}footer{text-align:center;padding:24px;color:#888}ins{margin:20px 0}
.disclaimer{background:#eef6ef;border-left:4px solid #5aa469;padding:10px 14px;border-radius:8px;color:#3a5a3a;font-size:.92rem;margin:20px 0}"""

def load_state():
    if STATE.exists():
        try: return json.loads(STATE.read_text())
        except Exception: pass
    return {"next": 0, "posts": []}

def build_post(t):
    a = _claude_article(t["topic"], t["keywords"], t.get("niche", ""))
    # stable slug from the TOPIC (not the AI title) so re-runs refresh the same URL
    t = dict(t); t["slug"] = _slug(t["topic"]); t["title"] = a["title"]
    t["date"] = datetime.date.today().isoformat()
    POSTS.mkdir(parents=True, exist_ok=True)
    (POSTS / f"{t['slug']}.html").write_text(_post_html(a, t), encoding="utf-8")
    print(f"[blog] wrote post: {t['slug']}")
    return {k: t[k] for k in ("slug", "title", "date", "video", "channel", "niche")}

def rebuild_site(posts):
    BUILD.mkdir(parents=True, exist_ok=True)
    (BUILD / "style.css").write_text(STYLE, encoding="utf-8")
    (BUILD / "index.html").write_text(_index_html(posts), encoding="utf-8")
    # AdSense-required trust pages
    (BUILD / "about.html").write_text(
        _page("About", f"About {SITE_NAME} — our channels and what we publish.", _about_body()), encoding="utf-8")
    (BUILD / "privacy.html").write_text(
        _page("Privacy", f"Privacy policy for {SITE_NAME}.", _privacy_body()), encoding="utf-8")
    # ads.txt (fill AdSense pub id after approval; harmless placeholder until then)
    pub = ADSENSE_CLIENT.replace("ca-pub-", "pub-")
    (BUILD / "ads.txt").write_text(f"google.com, {pub}, DIRECT, f08c47fec0942fa0\n", encoding="utf-8")
    urls = ([f"{SITE_URL}/", f"{SITE_URL}/about", f"{SITE_URL}/privacy"]
            + [f"{SITE_URL}/posts/{p['slug']}" for p in posts])
    (BUILD / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "".join(f"<url><loc>{u}</loc></url>\n" for u in urls) + "</urlset>", encoding="utf-8")
    (BUILD / "robots.txt").write_text(f"User-agent: *\nAllow: /\nSitemap: {SITE_URL}/sitemap.xml\n", encoding="utf-8")
    print(f"[blog] site rebuilt: {len(posts)} posts + about + privacy + ads.txt + sitemap + robots")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", action="store_true", help="one starter post per niche")
    a = ap.parse_args()
    st = load_state()
    if a.seed:
        st["posts"] = [build_post(t) for t in TOPICS]
    else:
        t = TOPICS[st["next"] % len(TOPICS)]
        st["next"] = (st["next"] + 1) % len(TOPICS)
        st["posts"] = [build_post(t)] + [p for p in st.get("posts", []) if p["slug"] != _slug(t["topic"])]
    rebuild_site(st["posts"])
    STATE.write_text(json.dumps(st, indent=2))
    print("[blog] DONE")

if __name__ == "__main__":
    main()
