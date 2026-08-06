import React from "react";
import {
  AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig, OffthreadVideo, Img, staticFile,
} from "remotion";

const FONT =
  '"Baloo 2", "Comic Sans MS", "Segoe UI", system-ui, sans-serif';

// ── Colourful animated background: gradient + gently floating bubbles ──
export const Background: React.FC<{ color1: string; color2: string }> = ({ color1, color2 }) => {
  const frame = useCurrentFrame();
  const bubbles = Array.from({ length: 14 }, (_, i) => i);
  return (
    <AbsoluteFill style={{ background: `linear-gradient(160deg, ${color1}, ${color2})` }}>
      {bubbles.map((i) => {
        const seed = (i * 97) % 100;
        const x = (seed / 100) * 100;
        const size = 40 + ((i * 53) % 90);
        const y = ((frame * (0.4 + (i % 5) * 0.15) + seed * 8) % 130) - 15;
        return (
          <div key={i} style={{
            position: "absolute", left: `${x}%`, top: `${y}%`, width: size, height: size,
            borderRadius: "50%", background: "rgba(255,255,255,0.14)", filter: "blur(1px)",
          }} />
        );
      })}
    </AbsoluteFill>
  );
};

const Center: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <AbsoluteFill style={{ justifyContent: "center", alignItems: "center", padding: 80, textAlign: "center", fontFamily: FONT, color: "#fff" }}>
    {children}
  </AbsoluteFill>
);

const pop = (frame: number, fps: number, delay = 0) =>
  spring({ frame: frame - delay, fps, config: { damping: 12, mass: 0.7 } });

// ── Title card ──
export const TitleScene: React.FC<{ text: string; subtitle: string; char?: string }> = ({ text, subtitle, char }) => {
  const frame = useCurrentFrame(); const { fps } = useVideoConfig();
  const s = pop(frame, fps);
  const hop = Math.abs(Math.sin(frame / 8)) * 26;   // bouncy entrance
  const sway = Math.sin(frame / 14) * 5;
  return (
    <Center>
      <div style={{ transform: `scale(${s})` }}>
        <div style={{ fontSize: 150, fontWeight: 800, textShadow: "0 8px 0 rgba(0,0,0,0.15)" }}>{text}</div>
        {subtitle ? <div style={{ fontSize: 70, marginTop: 20, opacity: interpolate(frame, [10, 25], [0, 1], { extrapolateRight: "clamp" }) }}>{subtitle}</div> : null}
      </div>
      {char ? <Img src={staticFile(char)} style={{ width: 300, height: 300, objectFit: "contain", borderRadius: 34, marginTop: 34,
        transformOrigin: "bottom center", transform: `translateY(${-hop}px) rotate(${sway}deg)`,
        filter: "drop-shadow(0 16px 32px rgba(0,0,0,0.28))" }} /> : null}
    </Center>
  );
};

// ── Counting: emoji items pop in one by one, big number tracks the count ──
export const CountingScene: React.FC<{ count: number; emoji: string; label: string }> = ({ count, emoji, label }) => {
  const frame = useCurrentFrame(); const { fps, durationInFrames } = useVideoConfig();
  const per = durationInFrames / (count + 1);
  const shown = Math.min(count, Math.floor(frame / per) + 1);
  const items = Array.from({ length: count }, (_, i) => i);
  return (
    <Center>
      <div style={{ fontSize: 260, fontWeight: 800, lineHeight: 1, textShadow: "0 10px 0 rgba(0,0,0,0.15)" }}>{shown}</div>
      <div style={{ display: "flex", gap: 24, marginTop: 30, flexWrap: "wrap", justifyContent: "center", maxWidth: "80%" }}>
        {items.map((i) => {
          const s = i < shown ? pop(frame, fps, i * per) : 0;
          return <span key={i} style={{ fontSize: 120, transform: `scale(${s})`, display: "inline-block" }}>{emoji}</span>;
        })}
      </div>
      {label ? <div style={{ fontSize: 64, marginTop: 24, fontWeight: 700 }}>{shown} {label}!</div> : null}
    </Center>
  );
};

// ── One alphabet letter + word ──
export const LetterScene: React.FC<{ letter: string; word: string; emoji: string }> = ({ letter, word, emoji }) => {
  const frame = useCurrentFrame(); const { fps } = useVideoConfig();
  const s = pop(frame, fps);
  return (
    <Center>
      <div style={{ transform: `scale(${s})`, background: "rgba(255,255,255,0.18)", borderRadius: 60, padding: "40px 90px" }}>
        <div style={{ fontSize: 340, fontWeight: 800, lineHeight: 1 }}>{letter}</div>
      </div>
      <div style={{ fontSize: 96, marginTop: 40, fontWeight: 700, opacity: interpolate(frame, [12, 28], [0, 1], { extrapolateRight: "clamp" }) }}>
        {emoji} {word}
      </div>
    </Center>
  );
};

// ── Phonics: TEACHES a letter — traces it being written, says its SOUND, blends to a word ──
// This is the "learn to read + write" scene. Three beats over the scene's duration:
//   1) the letter is "drawn" (SVG stroke reveal over a faint trace guide) → formation
//   2) its phonic SOUND appears ("A says /a/")                            → phonics
//   3) it blends into an example word + emoji ("A is for Apple 🍎")       → reading
export const PhonicsScene: React.FC<{ letter: string; sound: string; word: string; emoji: string }> = ({ letter, sound, word, emoji }) => {
  const frame = useCurrentFrame(); const { fps, durationInFrames } = useVideoConfig();
  const p = frame / Math.max(1, durationInFrames - 1);           // 0..1 progress
  const DASH = 1600;                                             // > any glyph outline length
  const drawn = interpolate(p, [0.05, 0.45], [DASH, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  const fill = interpolate(p, [0.42, 0.55], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  const soundS = pop(frame, fps, Math.round(durationInFrames * 0.52));
  const wordIn = interpolate(p, [0.72, 0.82], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  const wordPop = pop(frame, fps, Math.round(durationInFrames * 0.72));
  const svgText = { textAnchor: "middle" as const, dominantBaseline: "central" as const,
                    fontFamily: FONT, fontSize: 300, fontWeight: 800 };

  // ── travelling "pen": a light guide path across the letter that a glowing tip (✏️) follows
  //    while the ink is drawn, so it feels like the letter is being written by hand. The guide
  //    is a smooth top→bottom hand-writing sweep sampled over the glyph box (viewBox 0..400). ──
  const GN = 26;
  const guidePts = Array.from({ length: GN }, (_, i) => {
    const tt = i / (GN - 1);
    return [200 + 46 * Math.sin(tt * Math.PI * 2.5), 110 + tt * 200] as [number, number];
  });
  const guideD = "M " + guidePts.map(([x, y]) => `${x.toFixed(1)} ${y.toFixed(1)}`).join(" L ");
  const drawT = interpolate(p, [0.05, 0.45], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  const [penX, penY] = guidePts[Math.min(GN - 1, Math.round(drawT * (GN - 1)))];
  // pen fades in as writing starts, lifts away once the stroke reveal is done
  const penVis = interpolate(p, [0.03, 0.09, 0.44, 0.52], [0, 1, 1, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });

  return (
    <Center>
      <div style={{ fontSize: 56, fontWeight: 800, opacity: 0.9, marginBottom: 6 }}>Let&apos;s write {letter.toUpperCase()}</div>
      <svg viewBox="0 0 400 400" style={{ width: 360, height: 360 }}>
        {/* faint trace guide */}
        <text x="200" y="205" style={svgText} fill="none" stroke="rgba(255,255,255,0.28)" strokeWidth={5}>{letter}</text>
        {/* the ink being written */}
        <text x="200" y="205" style={svgText} fill={`rgba(255,255,255,${fill})`} stroke="#fff" strokeWidth={7}
              strokeLinejoin="round" strokeLinecap="round" strokeDasharray={DASH} strokeDashoffset={drawn}>{letter}</text>
        {/* light guide path the pen travels along */}
        <path d={guideD} fill="none" stroke="rgba(255,255,255,0.20)" strokeWidth={3}
              strokeLinecap="round" strokeDasharray="1 12" opacity={penVis} />
        {/* the pen tip: a glowing ink dot + a little pencil, following the guide as the letter draws */}
        <circle cx={penX} cy={penY} r={10} fill="#ffe66d" opacity={penVis}
                style={{ filter: "drop-shadow(0 0 7px rgba(255,230,109,0.95))" }} />
        <text x={penX + 20} y={penY - 22} fontSize={54} textAnchor="middle" opacity={penVis}>✏️</text>
      </svg>
      <div style={{ fontSize: 84, fontWeight: 800, marginTop: 10, transform: `scale(${soundS})`,
                    textShadow: "0 6px 0 rgba(0,0,0,0.18)" }}>
        {letter.toUpperCase()} says <span style={{ color: "#ffe66d" }}>{sound}</span>
      </div>
      <div style={{ fontSize: 76, fontWeight: 700, marginTop: 18, opacity: wordIn,
                    transform: `scale(${0.6 + wordPop * 0.4})` }}>
        {emoji} {letter.toUpperCase()} is for <b>{word}</b>
      </div>
    </Center>
  );
};

// ── Addition: early MATHS — a groups of objects + b groups, then the sum is revealed ──
// "2 🍎 + 1 🍎 = 3 🍎". Objects pop in, the equation builds, the answer lands with a pop.
export const AdditionScene: React.FC<{ a: number; b: number; emoji: string; label: string }> = ({ a, b, emoji, label }) => {
  const frame = useCurrentFrame(); const { fps, durationInFrames } = useVideoConfig();
  const p = frame / Math.max(1, durationInFrames - 1);
  const showB = p > 0.34;
  const showEq = p > 0.62;
  const sumPop = pop(frame, fps, Math.round(durationInFrames * 0.66));
  const group = (n: number, from: number, on: boolean) => (
    <div style={{ display: "flex", gap: 12, flexWrap: "wrap", justifyContent: "center", maxWidth: 360 }}>
      {Array.from({ length: n }, (_, i) => {
        const s = on ? pop(frame, fps, Math.round(durationInFrames * from) + i * 6) : 0;
        return <span key={i} style={{ fontSize: 92, transform: `scale(${s})`, display: "inline-block" }}>{emoji}</span>;
      })}
    </div>
  );
  return (
    <Center>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: 30, flexWrap: "wrap" }}>
        {group(a, 0.06, true)}
        <div style={{ fontSize: 150, fontWeight: 800 }}>+</div>
        <div style={{ opacity: showB ? 1 : 0 }}>{group(b, 0.36, showB)}</div>
        <div style={{ fontSize: 150, fontWeight: 800, opacity: showEq ? 1 : 0 }}>=</div>
        <div style={{ fontSize: 200, fontWeight: 800, transform: `scale(${showEq ? sumPop : 0})`,
                      color: "#ffe66d", textShadow: "0 8px 0 rgba(0,0,0,0.18)" }}>{a + b}</div>
      </div>
      <div style={{ fontSize: 76, fontWeight: 800, marginTop: 30 }}>
        {a} + {b} = <span style={{ color: "#ffe66d" }}>{a + b}</span> {label}
      </div>
    </Center>
  );
};

// ── Karaoke: words highlight in time + Zuzu sings the visible words ──
// With real `words` (global-frame f0/f1 from transcribing the sung audio) the highlight and
// Zuzu's mouth are driven by g = startFrame + frame, so they match the voice exactly.
// With no `words` it falls back to today's proportional highlight (amplitude still moves the mouth).
type KWord = { text: string; f0: number; f1: number; line: number };
export const KaraokeScene: React.FC<{
  lines: string[]; words?: KWord[]; durationInFrames: number; startFrame?: number;
  img?: string; mouthEnv?: number[]; mouthX?: number; mouthY?: number; character?: string;
}> = ({ lines, words, durationInFrames, startFrame = 0, img, mouthEnv, mouthX = 0.5, mouthY = 0.46 }) => {
  const frame = useCurrentFrame(); const { fps, durationInFrames: cfgDur } = useVideoConfig();
  const dur = durationInFrames || cfgDur;
  const g = startFrame + frame;                       // GLOBAL frame -> matches the audio clock
  const synced = !!(words && words.length);

  // rows of {text, idx} + which idx is active + whether a word is being sung right now
  const rows: { text: string; idx: number }[][] = [];
  let activeIdx = -1;
  let voiced = false;
  if (synced) {
    words!.forEach((w, i) => { (rows[w.line] ||= []).push({ text: w.text, idx: i }); });
    for (let i = 0; i < words!.length; i++) {
      if (words![i].f0 <= g) activeIdx = i; else break;   // last word that has started
    }
    voiced = activeIdx >= 0 && g < words![activeIdx].f1;   // inside the word (not the gap after)
  } else {
    let k = -1;
    lines.forEach((l) => rows.push(l.split(/\s+/).filter(Boolean).map((t) => { k += 1; return { text: t, idx: k }; })));
    const total = Math.max(1, k + 1);
    activeIdx = Math.min(total - 1, Math.floor((frame / dur) * total));
    voiced = true;   // no word boundaries -> let amplitude gate the mouth
  }

  // mouth openness: amplitude at this frame, gated by whether a word is being sung
  const rawOpen = mouthEnv && mouthEnv.length ? Math.min(1, mouthEnv[Math.min(g, mouthEnv.length - 1)] || 0) : 0;
  const mouthOpen = synced ? (voiced ? Math.max(0.12, rawOpen) : rawOpen * 0.3) : rawOpen;

  const t = frame / fps;
  const hop = Math.abs(Math.sin(t * 4.5)) * 20 + mouthOpen * 18;   // bops while singing
  const sway = Math.sin(t * 2.2) * 5;
  const breathe = 1 + Math.sin(t * 3) * 0.03 + mouthOpen * 0.07;
  const IMG = 300;

  return (
    <Center>
      <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 30 }}>
        <div style={{ maxWidth: "92%" }}>
          {rows.map((row, li) => row && (
            <div key={li} style={{ fontSize: 80, fontWeight: 800, lineHeight: 1.45 }}>
              {row.map(({ text, idx }, wi) => {
                const isActive = idx === activeIdx; const isPast = idx < activeIdx;
                return (
                  <span key={wi} style={{
                    display: "inline-block", margin: "0 17px",
                    color: isActive ? "#ffe66d" : isPast ? "#ffffff" : "rgba(255,255,255,0.55)",
                    transform: isActive ? "scale(1.25) translateY(-8px)" : "scale(1)",
                    textShadow: isActive ? "0 6px 0 rgba(0,0,0,0.2)" : "none",
                    transition: "transform 0.1s",
                  }}>{text}</span>
                );
              })}
            </div>
          ))}
        </div>
        {img ? (
          <div style={{ position: "relative", width: IMG, height: IMG, transformOrigin: "bottom center",
              transform: `translateY(${-hop}px) rotate(${sway}deg) scale(${breathe})`,
              filter: "drop-shadow(0 18px 34px rgba(0,0,0,0.30))" }}>
            <Img src={staticFile(img)} style={{ width: "100%", height: "100%", objectFit: "contain", borderRadius: 34 }} />
            <SingingMouth open={mouthOpen} mouthX={mouthX} mouthY={mouthY} />
          </div>
        ) : null}
      </div>
    </Center>
  );
};

// ── Shared procedural singing mouth: a dark ellipse that opens with `open` (0..1) ──
export const SingingMouth: React.FC<{ open: number; mouthX: number; mouthY: number }> = ({ open, mouthX, mouthY }) => (
  <div style={{
    position: "absolute", left: `${mouthX * 100}%`, top: `${mouthY * 100}%`,
    transform: "translate(-50%,-50%)",
    width: 30 + open * 8, height: 8 + open * 30,   // opens wider on loud vocals
    background: "radial-gradient(ellipse at 50% 35%, #c0505e 0%, #8a2433 55%, #5c1220 100%)",
    borderRadius: "50%", boxShadow: "inset 0 -3px 6px rgba(0,0,0,0.45)",
    border: "2px solid rgba(90,20,30,0.5)",
  }} />
);

// ── Character clip (AI wan-animate / i2v) composited; friendly placeholder if none ──
export const CharacterScene: React.FC<{ clip: string; img?: string; caption: string; character: string;
    mouthEnv?: number[]; startFrame?: number; mouthX?: number; mouthY?: number }> =
  ({ clip, img, caption, character, mouthEnv, startFrame = 0, mouthX = 0.5, mouthY = 0.46 }) => {
  const frame = useCurrentFrame(); const { fps } = useVideoConfig();
  const s = pop(frame, fps);
  const t = frame / fps;
  const sings = !!(mouthEnv && mouthEnv.length);
  // vocal loudness at THIS frame (global) -> drives the singing
  const g = startFrame + frame;
  const open = sings ? Math.min(1, mouthEnv![Math.min(g, mouthEnv!.length - 1)] || 0) : 0;
  const hop = Math.abs(Math.sin(t * 4.5)) * (sings ? 26 : 44) + open * 28;  // belts up on loud notes
  const sway = Math.sin(t * 2.2) * 7;
  const breathe = 1 + Math.sin(t * 3) * 0.03 + open * 0.09;                 // swells while singing
  const IMG = 560;
  return (
    <Center>
      {img
        ? <div style={{ position: "relative", width: IMG, height: IMG, transformOrigin: "bottom center",
              transform: `scale(${s * breathe}) translateY(${-hop}px) rotate(${sway}deg)`,
              filter: "drop-shadow(0 24px 46px rgba(0,0,0,0.30))" }}>
            <Img src={staticFile(img)} style={{ width: "100%", height: "100%", objectFit: "contain", borderRadius: 44 }} />
            {sings ? <SingingMouth open={open} mouthX={mouthX} mouthY={mouthY} /> : null}
          </div>
        : <div style={{ transform: `scale(${s})`, borderRadius: 40, overflow: "hidden", width: 900, height: 620, boxShadow: "0 20px 60px rgba(0,0,0,0.25)", background: "rgba(255,255,255,0.15)", display: "flex", alignItems: "center", justifyContent: "center" }}>
            {clip
              ? <OffthreadVideo src={staticFile(clip)} style={{ width: "100%", height: "100%", objectFit: "cover" }} />
              : <div style={{ fontSize: 90, fontWeight: 800, textAlign: "center" }}>🐘<br />{character}<br /><span style={{ fontSize: 40, opacity: 0.8 }}>(character clip goes here)</span></div>}
          </div>}
      {caption ? <div style={{ fontSize: 82, marginTop: 30, fontWeight: 800 }}>{caption}</div> : null}
    </Center>
  );
};

// ── Outro ──
export const OutroScene: React.FC<{ text: string; character: string; char?: string }> = ({ text, character, char }) => {
  const frame = useCurrentFrame(); const { fps } = useVideoConfig();
  const s = pop(frame, fps);
  const wave = Math.sin(frame / 5) * 12;
  const hop = Math.abs(Math.sin(frame / 7)) * 24;   // happy little hops
  return (
    <Center>
      {char
        ? <Img src={staticFile(char)} style={{ width: 340, height: 340, objectFit: "contain", borderRadius: 40,
            transformOrigin: "bottom center", transform: `translateY(${-hop}px) rotate(${wave}deg)`,
            filter: "drop-shadow(0 18px 36px rgba(0,0,0,0.28))" }} />
        : <div style={{ fontSize: 160, transform: `rotate(${wave}deg)` }}>👋</div>}
      <div style={{ fontSize: 110, fontWeight: 800, transform: `scale(${s})`, marginTop: 20 }}>{text}</div>
      <div style={{ fontSize: 56, marginTop: 20, opacity: 0.9 }}>Love, {character}</div>
    </Center>
  );
};
