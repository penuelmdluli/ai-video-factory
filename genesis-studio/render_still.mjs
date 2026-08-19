// Still frames (cards, thumbnails): JSON in -> PNG out.
//   node render_still.mjs props.json out.png JobCard
import { bundle } from "@remotion/bundler";
import { selectComposition, renderStill } from "@remotion/renderer";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const propsPath = process.argv[2] || path.join(__dirname, "input", "card.example.json");
const outPath = process.argv[3] || path.join(__dirname, "out", "card.png");
const compId = process.argv[4] || "JobCard";

const inputProps = JSON.parse(fs.readFileSync(propsPath, "utf-8"));
fs.mkdirSync(path.dirname(outPath), { recursive: true });

const serveUrl = await bundle({ entryPoint: path.join(__dirname, "src", "index.ts") });
const composition = await selectComposition({ serveUrl, id: compId, inputProps });
await renderStill({ composition, serveUrl, output: outPath, inputProps });
console.log(`[genesis-studio] ${compId} -> ${outPath}`);
