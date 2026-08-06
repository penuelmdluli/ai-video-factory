# Genesis News — SA Current Affairs page setup

A dedicated, **safe** South-African current-affairs channel. Everything below is
already built in code + assets; the only thing left is the two accounts (which I
can't create) + handing me the tokens.

## ✅ Already done (in this repo)
- **Niche** `sa_pulse` in `config.py` — "Genesis News - SA Current Affairs", SA voice
  (`en-ZA-LukeNeural`), topic pool + trend keywords covering: jobs/opportunities, new
  laws & your rights, cost of living, tourism, borders/migration (policy & economics),
  service-delivery/protests (reported factually), and **xenophobia framed as root
  causes + solutions**.
- **Strict safety style guide** in `modules/script_writer.py` (`sa_pulse`): neutral,
  non-partisan, no incitement, no fabricated claims about real people, unifying
  "we rise together" tone, never targets any nationality/group.
- **Brand colours + voice** wired into thumbnails, reel covers, and in-video captions
  (SA gold + green). News "LIVE" badge enabled (it's a news page).
- **Brand kit** in `assets/youtube_branding/`:
  - `logo_sa_pulse.png` — profile picture / avatar (1080×1080)
  - `banner_sa_pulse.png` — YouTube channel banner (2560×1440, TV-safe)
  - `cover_sa_pulse.png` — Facebook page cover (1640×624)
  - `about_sa_pulse.txt` — channel/page description
- Token placeholders added to `.env` (empty = nothing posts by accident).
- **Not** in `BUILD_NICHES` yet, so scheduled runs ignore it until you connect it.

## �on you (≈5 min, I can't create accounts)
1. **Create a Facebook Page** — name e.g. **"Genesis News"**, category *News & Media / Media*.
2. **Create a YouTube channel** — same name, on your Google account.
   *(You can rename "Genesis News" to anything — just tell me the final name.)*

## 🤝 Then hand me
- **FB page token:** Graph API Explorer → generate a **User token** with
  `pages_show_list`, `pages_read_engagement`, `pages_manage_posts` → paste it; I pull the
  Genesis News page token from `/me/accounts` and write `FB_PAGE_ID_sa_pulse` /
  `FB_PAGE_TOKEN_sa_pulse` to `.env`.
- **YouTube:** say "connect YouTube" and I run the OAuth flow → you approve the new
  channel once in the browser → saved as `tokens/youtube_token_sa_pulse.json`.

## 🚀 What I do the moment you connect it
1. Upload the avatar + banner (YouTube) and avatar + cover + about (Facebook) via API.
2. Add `sa_pulse` to `BUILD_NICHES` + set a **daytime SAST schedule** (e.g. 08:00 / 12:30 / 17:00).
3. Build + post the first video, cross-post the reel to the page, add to the blog hub.
4. Same quality bar as the rest: karaoke captions, portrait cover + LIVE badge, nothing cut.

## 📝 Blog (already wired, activates with one env var)
The Genesis Hub blog now has a **South Africa** category with safe, neutral SA current-affairs
articles (root-causes + solutions framing, balanced disclaimer). Each SA article auto **cross-posts
to the Genesis News Facebook page**. It's gated so nothing breaks before the channel exists — set
`MZANSI_VIDEO=<first youtube id>` (and optionally `MZANSI_URL=<channel url>`) in `.env` after the
first upload and the SA blog track + FB cross-post switch on automatically.
Note: this pass also fixed a gap where **Herbal Organic blog posts never cross-posted** — every
niche now maps to its own FB page (music→limitless_you, kids→blissful_moments, news→Tech Pulse,
wellness→Herbal, sa→Genesis News).
