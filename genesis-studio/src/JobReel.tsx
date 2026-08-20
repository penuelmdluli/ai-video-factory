import React from "react";
import {
  AbsoluteFill, Img, interpolate, spring, staticFile,
  useCurrentFrame, useVideoConfig,
} from "remotion";

export type JobReelProps = {
  employer: string;
  role: string;
  positions?: number;
  details: string[];          // salary, centre, closing date
  closes?: string;
  entryLevel?: boolean;
  source?: string;
  photo?: string;
  durationInSeconds?: number;
};

const GREEN = "#2EC871";
const RED = "#DC3232";
const INK = "#0A0C0E";

/** The job alert reel.
 *
 * Built for the person who needs it most: someone without a degree looking
 * for work they can actually get. So the biggest thing on screen is HOW MANY
 * POSITIONS are open, then the pay, then where — and it says plainly when no
 * qualification is required.
 */
export const JobReel: React.FC<JobReelProps> = ({
  employer, role, positions = 1, details, closes, entryLevel, source, photo,
}) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();
  const t = frame / fps;
  const pop = (delay: number) =>
    spring({ frame: frame - delay * fps, fps, config: { damping: 13 } });

  // the count ticks up — a number climbing to 99 is the hook
  const shown = Math.round(
    positions * Math.min(1, Math.max(0, (t - 0.6) / 1.1)));

  return (
    <AbsoluteFill style={{
      background: `linear-gradient(160deg, #12241B 0%, ${INK} 60%)`,
      fontFamily: "Arial Black, Arial, sans-serif", color: "#fff",
    }}>
      {photo ? (
        <>
          <Img src={staticFile(photo)} style={{
            width: "100%", height: "100%", objectFit: "cover", opacity: 0.34,
          }} />
          <AbsoluteFill style={{
            background: `linear-gradient(to bottom, ${INK}CC, ${INK}F2)`,
          }} />
        </>
      ) : null}

      {/* pulsing verified frame */}
      <AbsoluteFill style={{
        border: `10px solid ${GREEN}`,
        opacity: 0.35 + 0.25 * Math.sin(t * 3),
      }} />

      <div style={{ padding: "44px 48px 0" }}>
        <div style={{ fontSize: 46 }}>MZANSI CAREERS</div>
        <div style={{ fontSize: 26, color: GREEN, fontWeight: 400 }}>
          VERIFIED · NEVER PAY TO APPLY
        </div>
      </div>

      <AbsoluteFill style={{
        justifyContent: "center", padding: "0 56px", gap: 26,
      }}>
        {positions > 1 ? (
          <div style={{ transform: `scale(${pop(0.4)})` }}>
            <div style={{
              fontSize: 190, lineHeight: 0.92, color: GREEN,
              fontVariantNumeric: "tabular-nums",
            }}>
              {shown}
            </div>
            <div style={{ fontSize: 44, letterSpacing: 1 }}>
              POSITIONS OPEN
            </div>
          </div>
        ) : null}

        <div style={{ fontSize: 62, lineHeight: 1.05, textWrap: "balance",
                      transform: `scale(${pop(0.9)})`, transformOrigin: "left" }}>
          {role.toUpperCase()}
        </div>
        <div style={{ fontSize: 34, fontWeight: 400, color: "#CBD3D8" }}>
          {employer}
        </div>

        {entryLevel ? (
          <div style={{
            alignSelf: "flex-start", background: GREEN, color: INK,
            padding: "12px 26px", borderRadius: 14, fontSize: 34,
            transform: `scale(${pop(1.5)})`,
          }}>
            NO DEGREE NEEDED
          </div>
        ) : null}

        <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
          {details.filter((d) => !/^\d+ positions/i.test(d)).map((d, i) => (
            <div key={d} style={{
              fontSize: 34, fontWeight: 400,
              opacity: interpolate(frame - (2.0 + i * 0.35) * fps,
                                   [0, 10], [0, 1], { extrapolateLeft: "clamp",
                                                      extrapolateRight: "clamp" }),
              borderLeft: `6px solid ${GREEN}`, paddingLeft: 18,
            }}>
              {d}
            </div>
          ))}
        </div>

        {closes ? (
          <div style={{
            background: RED, borderRadius: 16, padding: "18px 0",
            textAlign: "center", fontSize: 40, marginTop: 10,
            transform: `scale(${pop(3.2)})`,
          }}>
            {closes}
          </div>
        ) : null}
      </AbsoluteFill>

      {/* share ask — this page only works if people pass it on */}
      <div style={{
        position: "absolute", left: 0, right: 0, bottom: 74,
        textAlign: "center",
        opacity: interpolate(frame, [durationInFrames - 110,
                                     durationInFrames - 80], [0, 1],
                             { extrapolateLeft: "clamp",
                               extrapolateRight: "clamp" }),
      }}>
        <div style={{ fontSize: 44, color: GREEN }}>SHARE THIS POST</div>
        <div style={{ fontSize: 28, fontWeight: 400, color: "#C6CBD0" }}>
          someone you know needs this job
        </div>
        {source ? (
          <div style={{ fontSize: 20, fontWeight: 400, color: "#7C8891",
                        marginTop: 12 }}>
            {source}
          </div>
        ) : null}
      </div>
    </AbsoluteFill>
  );
};
