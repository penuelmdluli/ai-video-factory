// Programmatic render: lesson JSON -> MP4. No Studio, no GUI.
//   node render.mjs [lesson.json] [out.mp4]
import { bundle } from "@remotion/bundler";
import { selectComposition, renderMedia } from "@remotion/renderer";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const lessonPath = process.argv[2] || path.join(__dirname, "input", "lesson.example.json");
const outPath = process.argv[3] || path.join(__dirname, "out", "episode.mp4");

const lesson = JSON.parse(fs.readFileSync(lessonPath, "utf-8"));
fs.mkdirSync(path.dirname(outPath), { recursive: true });

console.log("[remotion] bundling…");
const serveUrl = await bundle({ entryPoint: path.join(__dirname, "src", "index.ts") });

console.log("[remotion] selecting composition…");
const composition = await selectComposition({ serveUrl, id: "ZuzuEpisode", inputProps: lesson });

console.log(`[remotion] rendering ${composition.durationInFrames} frames @ ${composition.fps}fps -> ${outPath}`);
await renderMedia({
  composition,
  serveUrl,
  codec: "h264",
  outputLocation: outPath,
  inputProps: lesson,
  onProgress: ({ progress }) => process.stdout.write(`\r[remotion]   ${(progress * 100).toFixed(0)}%   `),
});
console.log(`\n[remotion] done -> ${outPath}`);
