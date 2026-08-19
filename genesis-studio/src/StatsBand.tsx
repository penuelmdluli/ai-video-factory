import React from "react";
import {
  AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig,
} from "remotion";

export type LogRow = {
  rank: number;
  name: string;
  team_key: string;
  played: number;
  points: number;
};

export type StatsBandProps = {
  rows: LogRow[];
  club?: string;
  flipEvery?: number;      // seconds per panel
};

const GOLD = "#FFC800";
const INK = "#0A0C10";

/** The live league band that runs under the match footage.
 *
 * Same graphic as the PIL version, but the layout is CSS: no measuring text
 * by hand, no zone arithmetic, nothing to overflow. Springs give the motion
 * real weight instead of a hand-rolled ease.
 */
export const StatsBand: React.FC<StatsBandProps> = ({
  rows, club, flipEvery = 7,
}) => {
  const frame = useCurrentFrame();
  const { fps, width, height } = useVideoConfig();
  const t = frame / fps;
  const focus = rows.find((r) => r.team_key === club);
  const panel = focus && Math.floor(t / flipEvery) % 2 === 1 ? "focus" : "log";
  const local = t - Math.floor(t / flipEvery) * flipEvery;

  // gold sweep across the panel change
  const wipe = local < 0.28 && t > flipEvery * 0.5
    ? interpolate(local, [0, 0.28], [0, width]) : null;

  return (
    <AbsoluteFill style={{
      background: `${INK}EB`, borderRadius: 18, overflow: "hidden",
      fontFamily: "Arial Black, Arial, sans-serif", color: "#fff",
    }}>
      <div style={{
        display: "flex", alignItems: "baseline", gap: 14,
        padding: "10px 20px 0",
      }}>
        <span style={{ color: GOLD, fontSize: 24, letterSpacing: 0.5 }}>
          BETWAY LOG
        </span>
        <span style={{ color: "#78DC96", fontSize: 18 }}>LIVE</span>
      </div>

      {panel === "log" ? (
        <div style={{
          display: "flex", flex: 1, alignItems: "center",
          padding: "0 16px 8px", gap: 8,
        }}>
          {rows.slice(0, 6).map((r, i) => {
            const s = spring({
              frame: frame - i * 4, fps, config: { damping: 14, mass: 0.6 },
            });
            const hot = club && r.team_key === club;
            const pulse = 0.5 + 0.5 * Math.sin(t * 3.2);
            const pts = Math.round(r.points * Math.min(1, (t - i * 0.15) / 0.9));
            return (
              <div key={r.team_key} style={{
                flex: 1, minWidth: 0, padding: "6px 10px", borderRadius: 10,
                transform: `translateY(${(1 - s) * 26}px)`, opacity: s,
                background: hot
                  ? `rgb(255, ${Math.round(180 + 40 * pulse)}, 0)` : "transparent",
                color: hot ? "#0A0A0A" : "#EBEEF2",
              }}>
                <div style={{
                  fontSize: 26, whiteSpace: "nowrap", overflow: "hidden",
                  textOverflow: "ellipsis",
                }}>
                  {r.rank} {r.name}
                </div>
                <div style={{
                  fontSize: 22, opacity: hot ? 0.85 : 0.68, fontWeight: 400,
                }}>
                  {Math.max(0, pts)} pts
                </div>
              </div>
            );
          })}
        </div>
      ) : (
        <div style={{
          display: "flex", flex: 1, alignItems: "center",
          justifyContent: "space-between", padding: "0 24px 10px",
        }}>
          <div style={{
            fontSize: 46,
            transform: `scale(${spring({ frame, fps, config: { damping: 12 } })})`,
            transformOrigin: "left center",
          }}>
            {focus?.name.toUpperCase()}
          </div>
          <div style={{ display: "flex", gap: 40 }}>
            {[["POSITION", focus?.rank], ["POINTS", focus?.points],
              ["PLAYED", focus?.played]].map(([label, val]) => (
              <div key={String(label)} style={{ textAlign: "center" }}>
                <div style={{ fontSize: 40, color: GOLD }}>{val}</div>
                <div style={{ fontSize: 18, opacity: 0.65, fontWeight: 400 }}>
                  {label}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {wipe !== null && (
        <div style={{
          position: "absolute", top: 0, bottom: 0, left: wipe - 12, width: 24,
          background: GOLD, opacity: 0.85,
        }} />
      )}
    </AbsoluteFill>
  );
};
