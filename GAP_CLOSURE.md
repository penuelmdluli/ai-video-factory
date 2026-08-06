# Gap Closure — what changed & what's yours to flip (2026-08-06)

Full strategy + competitor analysis: the "Content Network — Strategy & Gap Plan" artifact.

## ✅ Closed in code (live now, safe)

| Gap | What changed | Files |
|-----|--------------|-------|
| Bad news voice | Kokoro speed locked 1.0× (1.15× was pitch-shifting → robotic) | `modules/voice_generator.py` |
| No premium voice path | Drop-in RunPod TTS routing (Chatterbox=news, Orpheus=kids) in front of Kokoro; **env-gated, unset = no change** | `modules/voice_generator.py`, `modules/voice_runpod.py` (new) |
| Kids channel didn't teach | Phonics (letter **formation** trace + pen + sound + word) & Addition scenes; full **A–Z** phonics, **counting to 20**, **addition to 10** | `remotion-zuzu/src/*`, `zuzu_remotion.py`, `modules/zuzu_lessons.py` |
| News could go silent | edge-tts safety net in the news reel path | `auto_reel.py` |
| News stuck on one topic | Un-pinned Trump/Iran/Israel across topics, keywords, hashtags, scraper, persona → follows any breaking conflict + Africa angle | `config.py`, `modules/script_writer.py`, `news_scraper.py`, `hashtag_optimizer.py`, `community_manager.py`, `topic_generator.py` |
| AI-visual policy risk | "AI-generated visualization" label + `#AIgenerated` on news posts | `auto_reel.py` |
| Health/finance compliance | Script sanitizer: health cure-claims softened ("traditionally used for"), disclaimers appended; finance "not financial advice" | `modules/script_writer.py` |

## 🔧 Yours to flip (needs your account / credentials / a go-live decision)

### 1. Deploy the warm TTS voice to RunPod (turns on the voice upgrade)
A ready-to-deploy worker is in **`chatterbox-tts-worker/`** — one image serves both the
warm kids voice (`warm_teacher`) and the news voice (`news_anchor`); the pipeline's `voice`
field picks the preset. Full build/deploy steps: [chatterbox-tts-worker/BUILD.md](chatterbox-tts-worker/BUILD.md).
In short: `docker build` + push → create a RunPod serverless endpoint (attach a network
volume) → set in `.env`:
```
RUNPOD_API_KEY=<your key>   # already set for video
RUNPOD_TTS_ENDPOINT_KIDS=https://api.runpod.ai/v2/<id>
RUNPOD_TTS_ENDPOINT_NEWS=https://api.runpod.ai/v2/<id>   # can be the SAME endpoint
```
Until these are set, voice behaves exactly as today (Kokoro → edge-tts). Any endpoint error
auto-falls-back to Kokoro, so it can never break a build. The client↔worker contract is
verified; drop optional `voices/*.wav` reference clips to clone a consistent character.

### 2. Verify the Facebook page token (so posts don't silently fail)
```bash
python refresh_fb_token.py
```
Page tokens can expire; if Tech Pulse stops posting, this is the first thing to check.

### 3. Go live on the kids channel (safe — separate page, no conflict)
```bash
python make_zuzu.py --lesson phonics_stu --remotion --dry-run   # build, don't post
python make_zuzu.py --lesson phonics_stu --remotion             # build + post
```
Teaching lessons: `phonics_abc phonics_def phonics_ghi phonics_jkl phonics_mno phonics_pqr phonics_stu phonics_vwx phonics_yz count_add count_to_20 add_to_10`.

### 4. Reopen the dormant channels (the "one channel → network" flip)
Currently `BUILD_NICHES=["tech_news"]` in `config.py` — that's why only Tech Pulse posts. Add niches to go live:
```python
BUILD_NICHES = ["tech_news", "motivation", "blissful_moments", "ai_money"]  # example
```
**Rule: one poster per page.** Don't run `scheduler.py` AND enable the `auto_reel` / Genesis tasks on the same page — pick one owner, or they double-post. Recommend: enable channels a few at a time and watch the first posts.

## Suggested order
1. Deploy the two TTS endpoints (#1) → instantly better news + kids voice.
2. Go live on kids (#3) with the new curriculum — it's a fresh page, low risk.
3. Reopen 1–2 dormant channels (#4), watch the first posts, then add more.
4. Keep `refresh_fb_token.py` (#2) handy if any page stops posting.
