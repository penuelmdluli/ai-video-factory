# Reference voices (optional — voice cloning)

Drop a short (~5–10s), clean WAV here to clone a **consistent character voice**:

- `warm_teacher.wav` — the kids-channel teacher (warm, friendly). Used for niches
  `kids_songs` / `blissful_moments`.
- `news_anchor.wav` — the news voice (calm, authoritative). Used for niches
  `tech_news` / `ai_money` / `daily_breakdown`.

If a file is absent, the worker uses Chatterbox's built-in voice with the preset's
emotion settings (still warm/expressive via the `exaggeration` value) — so the worker
runs fine with **no** reference clips at all.

The filename must match the `voice` preset name the pipeline sends
(see `PRESETS` in `handler.py`).
