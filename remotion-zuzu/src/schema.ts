import { z } from "zod";

// A "lesson" JSON drives the whole episode. Your existing Zuzu generator
// (modules/zuzu_generator.py) can emit this shape; feed it in and out pops an MP4.

const base = { seconds: z.number().default(3) };

export const sceneSchema = z.discriminatedUnion("type", [
  // Big animated title card.
  z.object({ type: z.literal("title"), text: z.string(), subtitle: z.string().default(""), ...base }),
  // Count 1..count, each with an emoji popping in — the classic kids counting bit.
  z.object({ type: z.literal("counting"), count: z.number().default(5), emoji: z.string().default("🍎"),
             label: z.string().default(""), ...base }),
  // One alphabet letter + a word + emoji.
  z.object({ type: z.literal("letter"), letter: z.string(), word: z.string(), emoji: z.string().default("⭐"), ...base }),
  // Phonics: TEACHES a letter — traces its formation, shows its sound, blends to a word.
  z.object({ type: z.literal("phonics"), letter: z.string(), sound: z.string().default(""),
             word: z.string().default(""), emoji: z.string().default("⭐"), ...base }),
  // Addition: early maths — a objects + b objects, then the sum is revealed.
  z.object({ type: z.literal("addition"), a: z.number().default(1), b: z.number().default(1),
             emoji: z.string().default("🍎"), label: z.string().default(""), ...base }),
  // Karaoke: each line's words highlight in time (bouncing active word).
  // `words` carries REAL per-word timings in GLOBAL frames (f0/f1 = round(sec*fps)), from
  // transcribing the actual sung audio — so the highlight + Zuzu's mouth match the voice.
  // `line` is the 0-based index into this scene's `lines`. Empty => proportional fallback.
  z.object({ type: z.literal("karaoke"), lines: z.array(z.string()).default([]),
             words: z.array(z.object({ text: z.string(), f0: z.number(), f1: z.number(),
                                       line: z.number().default(0) })).default([]),
             ...base }),
  // Composite an AI character clip (from wan-animate / i2v) with an optional caption.
  // Leave clip "" to render a friendly placeholder (so it works with no assets).
  z.object({ type: z.literal("character"), clip: z.string().default(""), caption: z.string().default(""), ...base }),
  // Outro / call-to-action.
  z.object({ type: z.literal("outro"), text: z.string().default("See you next time!"), ...base }),
]);

export type Scene = z.infer<typeof sceneSchema>;

export const lessonSchema = z.object({
  title: z.string().default("Learning with Zuzu"),
  character: z.string().default("Zuzu"),
  color1: z.string().default("#7c4dff"),   // background gradient top
  color2: z.string().default("#22d3ee"),   // background gradient bottom
  audio: z.string().default(""),           // filename in public/ (song/voiceover), "" = silent
  characterImg: z.string().default(""),    // Zuzu character image in public/, animated across scenes
  characterImgs: z.array(z.string()).default([]),  // rotating Zuzu poses (title / character / outro)
  mouthEnv: z.array(z.number()).default([]),        // per-frame vocal loudness 0..1 -> singing mouth
  mouthX: z.number().default(0.5),                  // mouth position on the character img (0..1)
  mouthY: z.number().default(0.46),
  fps: z.number().default(30),
  width: z.number().default(1920),
  height: z.number().default(1080),
  scenes: z.array(sceneSchema),
});

export type Lesson = z.infer<typeof lessonSchema>;

// Default props so the composition renders standalone (no assets needed).
export const exampleLesson: Lesson = {
  title: "Count to 5 with Zuzu!",
  character: "Zuzu",
  color1: "#7c4dff",
  color2: "#22d3ee",
  audio: "",
  characterImg: "",
  characterImgs: [],
  mouthEnv: [],
  mouthX: 0.5,
  mouthY: 0.46,
  fps: 30,
  width: 1920,
  height: 1080,
  scenes: [
    { type: "title", text: "Count to 5!", subtitle: "with Zuzu 🐘", seconds: 3 },
    { type: "counting", count: 5, emoji: "🍎", label: "apples", seconds: 8 },
    { type: "karaoke", lines: ["One little, two little,", "three little apples,", "four little, five little apples,", "count them all with me!"], words: [], seconds: 8 },
    { type: "letter", letter: "A", word: "Apple", emoji: "🍎", seconds: 3 },
    { type: "character", clip: "", caption: "Great counting, friends!", seconds: 4 },
    { type: "outro", text: "See you next time! 👋", seconds: 3 },
  ],
};

export const framesFor = (scene: Scene, fps: number) => Math.max(1, Math.round((scene.seconds ?? 3) * fps));
export const totalFrames = (lesson: Lesson) =>
  Math.max(1, lesson.scenes.reduce((sum, s) => sum + framesFor(s, lesson.fps), 0));
