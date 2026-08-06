# Make Zuzu sing along (lip-sync) — setup

Two ways to get Zuzu's mouth moving with the song. For a **cartoon** character, read the
important caveat first — the free procedural route is often the better choice.

---

## ⚠️ Cartoon caveat (read this)
Standard lip-sync models (Wav2Lip, SadTalker, Sonic, LatentSync, Hallo) are trained on
**real human faces** and rely on **face-landmark detection**. A 3D cartoon elephant has no
detectable human face, so these models frequently **fail or produce garbage** on Zuzu.
So there are two realistic paths:

- **A) Procedural mouth (Remotion, FREE, cartoon-friendly)** — recommended.
- **B) AI lip-sync on RunPod (GPU)** — only worth it with a model that handles stylized
  characters; needs testing on Zuzu first.

---

## A) Procedural mouth — recommended for a cartoon (no GPU, no endpoint)
Analyse the song's **loudness envelope** and open/close a mouth overlay on Zuzu in time
with it. This is exactly what most nursery-rhyme channels do, it's deterministic, cheap,
and it always works on a cartoon.

Pipeline:
1. `zuzu_remotion.py`: compute an amplitude envelope from the song (30 fps) with librosa
   or moviepy, e.g. `env[frame] = RMS(audio_window)` normalised 0..1. Pass it into the
   lesson as `mouthEnv: number[]` (one value per frame).
2. `remotion-zuzu/src/scenes.tsx` CharacterScene: overlay a mouth `<div>`/SVG on the Zuzu
   image whose height scales with `mouthEnv[frame]` (closed at 0, open "O" at 1). Position
   it over Zuzu's mouth (a fixed offset for a fixed pose).
3. Add a tiny head-bob tied to the beat for life.

Effort: ~1 file of Python (envelope) + ~15 lines of Remotion. **I can build this — no
infra, works today.** Best fit for Zuzu.

---

## B) AI lip-sync endpoint on RunPod (GPU) — if you want photoreal-style
Same pattern as your Wan 2.2 video endpoint.

**Model choice (best-to-worst for a stylized character):**
1. **wan-animate** — Wan-based image+audio animation; handles stylised characters best.
2. **Sonic** (`jixiaozhong/Sonic`) — high-quality audio-driven portrait; test on Zuzu.
3. **SadTalker** — most available on RunPod Hub; likely needs a face, test first.

**Deploy (RunPod serverless):**
- RunPod Hub → search the model (e.g. "SadTalker", "Sonic") → deploy a Serverless Endpoint
  (GPU: 4090/A5000). Or build a custom worker (Dockerfile wrapping the model's inference).
- Note the endpoint id → put in `.env` as `RUNPOD_LIPSYNC_ENDPOINT_ID`.

**Contract (target):**
```
POST https://api.runpod.ai/v2/{ENDPOINT}/run
  {"input": {"image_base64": "<Zuzu still, raw b64>", "audio_base64": "<song, raw b64>",
             "fps": 30}}
-> COMPLETED {"video": "data:video/mp4;base64,..."}   # Zuzu singing clip
```

**Wiring (I'll add a `modules/runpod_lipsync.py` client, mirroring `runpod_wan.py`):**
```python
clip = lipsync_generate(zuzu_still, song_path, out="zuzu_sing.mp4")  # RunPod
# then in zuzu_remotion.build_remotion_lesson: character scene gets clip=zuzu_sing.mp4
# Remotion's CharacterScene already plays a clip via <OffthreadVideo>.
```
So the singing clip drops straight into the existing character scene — no schema changes.

**Cost:** ~$0.05–0.15 per clip (a few seconds of GPU), like the Wan endpoint.

---

## My recommendation
Do **(A) procedural mouth** — it's free, reliable on a cartoon, and looks great for a kids
song. Keep **(B)** in your back pocket if you later want a photoreal talking character.
Tell me which and I'll build it.
