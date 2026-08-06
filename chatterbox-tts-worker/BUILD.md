# Chatterbox-TTS RunPod worker — build, deploy & wire

Self-hosted **warm/expressive voices** for the factory (Chatterbox-TTS, MIT).
One worker serves every preset — the pipeline's `voice` field picks it:
`warm_teacher` (kids), `news_anchor` (news), `default`.

## 1. Build & push the image
```bash
cd chatterbox-tts-worker
docker build -t <your-dockerhub>/chatterbox-tts-worker:latest .
docker push <your-dockerhub>/chatterbox-tts-worker:latest
```
(Optional: drop `voices/warm_teacher.wav` and `voices/news_anchor.wav` in before
building to clone consistent character voices. Works fine without them.)

## 2. Create the RunPod serverless endpoint
- New **Serverless** endpoint → container image = the pushed tag.
- GPU: any 12–24GB card is plenty (Chatterbox needs ~4–8GB).
- **Attach a Network Volume** mounted at `/runpod-volume` (model weights
  auto-download there on the first request, ~cached after).
- Note the **Endpoint ID** (or the full `https://api.runpod.ai/v2/<id>` URL).

## 3. Wire it into the pipeline (.env)
The routing already exists in `modules/voice_generator.py` — just set the env:
```
RUNPOD_API_KEY=<your runpod key>          # already set for video
RUNPOD_TTS_ENDPOINT_KIDS=https://api.runpod.ai/v2/<id>
RUNPOD_TTS_ENDPOINT_NEWS=https://api.runpod.ai/v2/<id>
# (both can point at the SAME endpoint — the worker picks the preset from `voice`)
# or set just the generic one for all mapped niches:
# RUNPOD_TTS_ENDPOINT=https://api.runpod.ai/v2/<id>
```
Unset = pipeline is unchanged (Kokoro → edge-tts, exactly as before). Any worker
error/timeout automatically falls back to Kokoro, so this can never break a build.

## 4. Verify
```bash
# quick raw check (returns base64 WAV in .output.audio_base64):
curl -s -H "Authorization: Bearer $RUNPOD_API_KEY" -H "Content-Type: application/json" \
  -d '{"input":{"text":"Let'\''s write A. A says ah. A is for Apple!","voice":"warm_teacher"}}' \
  https://api.runpod.ai/v2/<id>/runsync | python -c "import sys,json,base64;o=json.load(sys.stdin)['output'];open('t.wav','wb').write(base64.b64decode(o['audio_base64']));print('wrote t.wav',o['sample_rate'],'Hz',o['duration'],'s')"

# then a real kids build (uses the warm voice automatically once env is set):
python make_zuzu.py --lesson phonics_abc --remotion --dry-run
```

## Contract
```
input:  {text, voice?, exaggeration?, cfg_weight?, seed?}
output: {audio_base64 (WAV), sample_rate, duration, seconds, voice}
error:  {error, trace}
```
Matches `modules/voice_runpod.py` (it reads `output.audio_base64`, transcodes WAV→mp3,
then whisper re-times the captions to the voice).

## Presets (tune in `handler.py`)
| voice | exaggeration | cfg_weight | feel |
|---|---|---|---|
| warm_teacher | 0.65 | 0.40 | warm, slow, expressive (kids) |
| news_anchor | 0.35 | 0.50 | measured, authoritative (news) |
| default | 0.50 | 0.50 | neutral |
