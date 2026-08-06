# Genesis Hub — the content blog / video hub

Live: **https://blog.genesisstudio.app**  (also https://genesis-hub.pages.dev)
Cloudflare Pages project: `genesis-hub` (account a21680c6…). Custom domain via CNAME `blog` → genesis-hub.pages.dev.

## What it does
A static SEO blog that is one central home for every channel's videos. Claude writes an
original article per topic, embeds the matching YouTube video (drives channel traffic),
adds AdSense + affiliate slots (income), and cross-posts the link to the matching Facebook page.

## Files
- `generate_blog.py` — writes the next rotating post + rebuilds the whole static site.
    - `--seed` regenerates one post per topic (currently 15).
    - Topics live in `TOPICS`; each maps to a niche → channel/video it promotes.
    - Emits: posts (clean URLs), index (category hub), about, privacy, ads.txt, sitemap.xml, robots.txt.
- `deploy.ps1` — `wrangler pages deploy build` to Cloudflare Pages.
- `cross_post_fb.py` — posts the newest article to its Facebook page. `--launch` = one per page.
- `state.json` — rotation cursor + published posts.

## Daily automation
Scheduled task **"Genesis Blog Factory"** runs `run_blog.bat` daily at 10:00 →
generate → deploy → Facebook cross-post. Runs forever.

## Auth (already done)
- Cloudflare: `wrangler login` (OAuth, persists & auto-refreshes). Account id is set in deploy.ps1.
- Google Search Console: domain property `genesisstudio.app` verified (DNS); sitemap submitted.

## Monetization — when ready
The site is AdSense-ready (privacy policy, about, ads.txt, clean nav, 15+ original articles).
When traffic has grown enough to apply and you're approved:
1. Set env `ADSENSE_CLIENT=ca-pub-XXXXXXXXXXXXXXXX` (your publisher id).
2. Re-run `python generate_blog.py --seed` and `deploy.ps1` (bakes the id into ads.txt + ad units).

## Optional env
- `BLOG_URL` (default https://blog.genesisstudio.app)
- `ADSENSE_CLIENT`, `GSC_VERIFY`, `BLOG_EMAIL`
