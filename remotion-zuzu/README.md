# remotion-zuzu — the programmatic spine for Zuzu episodes

Feed a **lesson JSON** → get an **animated MP4**. Fully code-driven (no timeline
GUI), data-driven, version-controlled. This is the "assembly" layer of the
animation stack: it sequences scenes, animates counting / karaoke lyrics /
alphabet, composites AI character clips, syncs the song, and renders.

```
lesson JSON ──▶ remotion-zuzu ──▶ episode.mp4
   ▲                                  ▲
   │ your Zuzu generator (Python)     │ character clips: RunPod wan-animate / i2v
   └── song: ACE-Step ────────────────┘
```

## Scene types (see `src/schema.ts`)
`title` · `counting` (emoji pop-in + big number) · `letter` (ABC) ·
`karaoke` (words highlight/bounce in time) · `character` (composite a clip, or a
friendly placeholder) · `outro`. Each has a `seconds` field; total duration is
computed automatically.

## Run it
```bash
cd remotion-zuzu
npm install                 # first time (~1-2 min)
npm run render              # renders input/lesson.example.json -> out/episode.mp4
# or a specific lesson:
node render.mjs input/lesson.json out/ep1.mp4
# live-edit in the browser:
npm run studio
```

## From your factory (Python)
```python
from make_remotion_episode import render_episode
render_episode(lesson_dict, "output/zuzu/ep1.mp4",
               assets={"audio": "song.mp3"})   # character clips referenced in scenes are auto-staged
```
`render_episode` copies your song + any `character.clip` files into `public/`,
writes the lesson, and renders. Runs `npm install` automatically on first use.

## Local vs RunPod
- **Local (CPU):** this whole assembly render — fast, free.
- **RunPod (GPU):** the *character clips* (SDXL char + wan-animate/i2v singing) and
  the *song* (ACE-Step). Generate those on RunPod, pass the file paths into the
  lesson's `character` scenes + `assets.audio`, and Remotion composites them here.

## The one manual investment (the moat)
A **consistent Zuzu**: either a trained SDXL character LoRA or a rigged Blender
character. Do it once; every episode after is automatic. Until then the
`character` scenes render a placeholder so the pipeline works end-to-end today.
