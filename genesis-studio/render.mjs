// Genesis motion graphics: JSON in -> MP4 out. Headless, no GUI.
//   node render.mjs [props.json] [out.mp4] [compositionId]
import { bundle } from "@remotion/bundler";
import { selectComposition, renderMedia } from "@remotion/renderer";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const propsPath = process.argv[2] || path.join(__dirname, "input", "band.example.json");
const outPath = process.argv[3] || path.join(__dirname, "out", "band.mp4");
const compId = process.argv[4] || "StatsBand";

const inputProps = JSON.parse(fs.readFileSync(propsPath, "utf-8"));
fs.mkdirSync(path.dirname(outPath), { recursive: true });

console.log("[genesis-studio] bundling…");
const serveUrl = await bundle({ entryPoint: path.join(__dirname, "src", "index.ts") });

const composition = await selectComposition({ serveUrl, id: compId, inputProps });
console.log(`[genesis-studio] ${compId}: ${composition.durationInFrames}f @ ${composition.fps}fps -> ${outPath}`);

await renderMedia({
  composition,
  serveUrl,
  codec: "h264",
  outputLocation: outPath,
  inputProps,
  onProgress: ({ progress }) =>
    process.stdout.write(`\r[genesis-studio]   ${(progress * 100).toFixed(0)}%   `),
});
console.log("\n[genesis-studio] done");
