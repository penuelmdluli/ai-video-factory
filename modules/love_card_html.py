"""The supporters' wall, set in a browser instead of drawn with rectangles.

Owner 2026-09-04 on the card that went out: "no crest no nothing, that is not
our standard of post." Literally true - the PIL card had a gold bar top and
bottom, black behind, and no badge anywhere on it. It was not a design that
had gone wrong, it was the most a rectangle-drawing API can do.

What the browser adds here, none of which PIL can express:

    the CREST, ghosted large behind the content and small in the header
    DEPTH - each quote is a raised panel with a shadow and a gold edge, so a
      supporter's words read as a thing on the card rather than text on black
    a GRADIENT ground instead of flat #0a0a0a
    real TYPE - condensed bold via the variable axes, tight leading, and
      quote marks that hang outside the measure the way set text does

Everything stays inside the page's existing rules. The quote is the
supporter's own words, unedited. Only a first name appears. The wordmark and
colours come from club_brand, so this is the club's palette rather than a
designer's taste.

    from modules.love_card_html import render_love_card
    await render_love_card(path, "chiefs", "HOW LONG HAVE YOU BEEN KHOSI?",
                           quotes, "GENESIS NEWS", "9 SUPPORTERS ANSWERED")
"""
from pathlib import Path

W, H = 1080, 1350


def _esc(s) -> str:
    return (str(s).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def _card_html(club: str, headline: str, items: list, footer: str,
               count_line: str = "") -> str:
    from modules.browser_card import shell, img_data_uri, COND_BOLD, COND_MED
    from modules.club_brand import CLUB_BRAND, official_badge

    brand = CLUB_BRAND.get(club, {})
    r, g, b = tuple(brand.get("colors", {}).get("primary", (255, 193, 7)))
    gold = f"rgb({r},{g},{b})"
    wordmark = _esc(brand.get("wordmark", "AMAKHOSI"))
    crest = img_data_uri(official_badge(club) or "")

    # Quotes become panels; plain strings (the ASK version of this card, where
    # there are no answers yet) become quiet lines with no panel, so an empty
    # wall never looks like a broken one.
    blocks = []
    for it in items:
        if isinstance(it, dict):
            blocks.append(
                f'<div class="q"><p class="qt">{_esc(it["text"])}</p>'
                f'<p class="qn">{_esc(it["name"])}</p></div>')
        else:
            blocks.append(f'<p class="ln">{_esc(it)}</p>')

    body = f"""
<div class="ghost"></div>
<div class="wrap">
  <header>
    {f'<img class="badge" src="{crest}">' if crest else ''}
    <div class="ids"><p class="mark">{wordmark}</p>
      <p class="sub">GENESIS NEWS</p></div>
  </header>
  <h1>{_esc(headline)}</h1>
  {f'<p class="count">{_esc(count_line)}</p>' if count_line else ''}
  <div class="quotes">{''.join(blocks)}</div>
  <footer><span class="rule"></span>{_esc(footer)}</footer>
</div>"""

    css = f"""
body {{ background:
    radial-gradient(120% 80% at 50% 0%, #1b1b20 0%, #0b0b0e 55%, #050506 100%);
    color:#fff; position:relative; }}

/* The badge as ground, not decoration: large, low, and behind everything, so
   the card is unmistakably this club's even at thumbnail size. */
.ghost {{ position:absolute; inset:0;
  background-image:url('{crest}'); background-repeat:no-repeat;
  background-position:118% 78%; background-size:74%;
  opacity:.07; filter:grayscale(1) contrast(1.2); }}

.wrap {{ position:relative; height:100%; padding:74px 70px 64px;
  display:flex; flex-direction:column; }}

header {{ display:flex; align-items:center; gap:22px; margin-bottom:34px; }}
.badge {{ width:96px; height:96px; object-fit:contain;
  filter:drop-shadow(0 6px 14px rgba(0,0,0,.65)); }}
.mark {{ font-size:44px; letter-spacing:.03em; color:{gold}; {COND_BOLD}
  line-height:1; }}
.sub {{ font-size:24px; letter-spacing:.22em; color:#8b8f96; {COND_MED}
  margin-top:7px; }}

h1 {{ font-size:82px; line-height:.96; letter-spacing:-.005em; {COND_BOLD}
  text-transform:uppercase; text-shadow:0 3px 18px rgba(0,0,0,.55); }}

.count {{ margin-top:20px; font-size:34px; letter-spacing:.14em; color:{gold};
  {COND_MED}; }}

.quotes {{ margin-top:34px; display:flex; flex-direction:column; gap:18px;
  overflow:hidden; flex:1; }}

/* A quote is a raised panel with a gold edge - the depth is the whole point,
   and it is the thing ImageDraw cannot produce at all. */
.q {{ background:linear-gradient(180deg,#191a1e 0%,#141519 100%);
  border-left:7px solid {gold}; border-radius:14px; padding:22px 26px 19px;
  box-shadow:0 10px 26px rgba(0,0,0,.55), inset 0 1px 0 rgba(255,255,255,.05); }}
.qt {{ font-size:37px; line-height:1.24; color:#eef0f2; {COND_MED} }}
/* The curly quotes are written as characters, not as CSS C escapes:
   Chromium terminated the escape early and printed a literal C and D on the
   first card off this renderer. A character cannot be mis-parsed. */
.qt::before {{ content:'“'; }}
.qt::after {{ content:'”'; }}
.qn {{ margin-top:11px; font-size:29px; letter-spacing:.1em; color:{gold};
  {COND_BOLD} }}
.qn::before {{ content:'— '; }}

.ln {{ font-size:38px; line-height:1.32; color:#dfe2e5; {COND_MED} }}

footer {{ margin-top:auto; padding-top:26px; font-size:30px;
  letter-spacing:.2em; color:#9aa0a7; {COND_MED}; display:flex;
  align-items:center; gap:20px; }}
.rule {{ display:block; width:74px; height:5px; background:{gold};
  border-radius:3px; }}"""
    return shell(body, W, H, css)


async def render_love_card(out_path, club: str, headline: str, items: list,
                           footer: str, count_line: str = "") -> str:
    from modules.browser_card import render_html
    html = _card_html(club, headline, items, footer, count_line)
    return await render_html(html, W, H, out_path)
