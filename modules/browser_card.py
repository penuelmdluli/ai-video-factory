"""Render a card with a real browser engine instead of drawing it by hand.

Owner 2026-09-05, on the flat cards: "no crest no nothing, that is not our
standard of post." And earlier, the deeper version of the same complaint -
bring in a professional studio.

WHY A BROWSER. Everything this repo draws goes through PIL's ImageDraw, which
can place a rectangle and a glyph and essentially nothing else. It has no
shadows, no gradients, no blur, no blend modes, no rounded clipping, no text
layout beyond "draw this string here". Every card in this codebase looks flat
because flat is the only thing the tool can do.

Chromium can do all of it, it is already installed here for the TikTok
uploader, and it costs nothing extra. A card becomes HTML and CSS - which is
also far easier to change than two hundred lines of coordinate arithmetic, so
the next design revision is minutes instead of an afternoon.

This is the same engine Remotion renders with. Starting at stills rather than
at a video framework is deliberate: it proves the pipeline end to end without
adding a Node toolchain, and stills are where the page's design complaint
actually is.

FONTS. Bahnschrift is installed on this machine, so Chromium can set it by
name and reach its variable axes through font-variation-settings - the same
condensed bold the PIL renderer now uses via modules/typeface. The two paths
stay visually matched without shipping a font file.

OFFLINE BY CONSTRUCTION. The page is loaded via set_content and must not
reference the network: no CDN stylesheets, no remote images. Images are passed
as data: URIs by img_data_uri below. A card that silently renders without its
crest because a fetch failed is worse than one that fails loudly.

    from modules.browser_card import render_html, img_data_uri
    png = await render_html(html, 1080, 1350, "card.png")
"""
import base64
import mimetypes
from pathlib import Path

# The house face, matched to modules/typeface. Quoted family names first, with
# a real fallback stack: a machine without Bahnschrift still gets a condensed
# grotesque rather than Chromium's default serif.
FONT_STACK = ("'Bahnschrift', 'DIN Alternate', 'Franklin Gothic Medium', "
              "'Arial Narrow', Arial, sans-serif")

# Weight/width as variable-font axes. Bahnschrift carries wght 300-700 and
# wdth 75-100, so this is the same Bold Condensed instance the PIL side asks
# for by name.
COND_BOLD = "font-variation-settings:'wght' 700,'wdth' 75;"
COND_MED = "font-variation-settings:'wght' 500,'wdth' 75;"


def img_data_uri(path) -> str:
    """A local image as a data: URI, because the page has no network."""
    p = Path(path)
    if not p.exists():
        return ""
    mime = mimetypes.guess_type(p.name)[0] or "image/png"
    return f"data:{mime};base64,{base64.b64encode(p.read_bytes()).decode()}"


async def render_html(html: str, width: int, height: int, out_path,
                      scale: int = 2) -> str:
    """HTML -> PNG at width x height. Returns the path written.

    scale is Chromium's deviceScaleFactor: the page is laid out at `width`
    CSS pixels and rasterised at `width * scale` device pixels, then written
    down to size. That is the browser's own supersampling, and it is why the
    text and the shadows come out clean.

    Async because every builder that will call this is async, and Playwright's
    SYNC api raises inside a running event loop - the same conflict that made
    the TikTok uploader shell out to a subprocess.
    """
    from playwright.async_api import async_playwright
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    async with async_playwright() as p:
        browser = await p.chromium.launch(args=["--font-render-hinting=none"])
        try:
            page = await browser.new_page(
                viewport={"width": width, "height": height},
                device_scale_factor=scale)
            await page.set_content(html, wait_until="load")
            # Web fonts and layout settle a frame after load; without this a
            # card can be captured mid-reflow with fallback metrics.
            await page.evaluate("document.fonts.ready")
            await page.screenshot(path=str(out), type="png")
        finally:
            await browser.close()
    # Chromium writes the shot at width*scale; bring it to delivery size the
    # same way the tactics board resolves its supersample.
    if scale != 1:
        from PIL import Image
        im = Image.open(out)
        if im.size != (width, height):
            im = (im.reduce(scale) if im.width == width * scale
                  else im.resize((width, height), Image.LANCZOS))
            im.convert("RGB").save(out)
    return str(out)


def shell(body: str, width: int, height: int, css: str = "") -> str:
    """The page every card shares: house font, no margins, no scrollbars."""
    return f"""<!doctype html><html><head><meta charset="utf-8"><style>
* {{ margin:0; padding:0; box-sizing:border-box; }}
html,body {{ width:{width}px; height:{height}px; overflow:hidden; }}
body {{ font-family:{FONT_STACK}; {COND_BOLD}
        -webkit-font-smoothing:antialiased; text-rendering:optimizeLegibility; }}
{css}
</style></head><body>{body}</body></html>"""
