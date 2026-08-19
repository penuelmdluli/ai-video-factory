import React from "react";
import { AbsoluteFill, Img, staticFile } from "remotion";

export type NewsCardProps = {
  headline: string;
  kicker?: string;          // club or section name
  credit?: string;          // photo attribution + licence
  photo?: string;           // filename inside public/
  clubColor?: string;       // club primary, for the kicker chip
  archiveYear?: string;     // stamped when the photo is not from this story
  logRows?: { rank: number; name: string; points: number;
              team_key: string }[];
  clubKey?: string;
  /** The reel plays live footage in a window over this card (y 178-958) and
   *  composites its own animated log band at y 824-944. In that mode the card
   *  must leave the zone clear and sit its type BELOW it, or the two collide. */
  videoMode?: boolean;
};

const GOLD = "#FFC800";
const INK = "#0A0C10";

/** The PSL news card.
 *
 * Headlines are the most variable text we publish — anything from four words
 * to a full sentence — so this is where hand-computed layout hurt most. Here
 * the headline sizes itself by clamp() and wraps, the photo is a cover-fit
 * background, and the log strip is a flex row that cannot overflow.
 */
export const NewsCard: React.FC<NewsCardProps> = ({
  headline, kicker, credit, photo, clubColor = GOLD, archiveYear,
  logRows = [], clubKey, videoMode = false,
}) => (
  <AbsoluteFill style={{
    background: INK, fontFamily: "Arial Black, Arial, sans-serif",
    color: "#fff",
  }}>
    {photo && !videoMode ? (
      <>
        <Img src={staticFile(photo)} style={{
          width: "100%", height: "100%", objectFit: "cover",
        }} />
        <AbsoluteFill style={{
          background:
            `linear-gradient(to bottom, ${INK}D9 0%, ${INK}33 32%, ` +
            `${INK}E6 66%, ${INK} 100%)`,
        }} />
      </>
    ) : null}

    {videoMode ? (
      <div style={{
        position: "absolute", left: 0, right: 0, top: 178, height: 780,
        background: "#0C0E12",
      }} />
    ) : null}

    {/* masthead */}
    <AbsoluteFill style={{ padding: "40px 44px", justifyContent: "flex-start" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 18 }}>
        <div style={{
          width: 64, height: 64, borderRadius: 32, border: `4px solid ${GOLD}`,
          display: "flex", alignItems: "center", justifyContent: "center",
          fontSize: 26, color: GOLD, background: "#0A0A0Ccc",
        }}>
          G
        </div>
        <div>
          <div style={{ fontSize: 40, lineHeight: 1 }}>GENESIS NEWS</div>
          <div style={{
            fontSize: 21, color: GOLD, fontWeight: 400, marginTop: 4,
          }}>
            PSL &middot; MZANSI FOOTBALL
          </div>
        </div>
        {archiveYear ? (
          <div style={{
            marginLeft: "auto", background: "#B3382D", padding: "8px 16px",
            borderRadius: 10, fontSize: 22,
          }}>
            ARCHIVE {archiveYear}
          </div>
        ) : null}
      </div>
    </AbsoluteFill>

    {/* headline block, anchored low */}
    <div style={{
      position: "absolute", left: 0, right: 0,
      // In video mode the karaoke captions and the subscribe strip own the
      // bottom ~520px. The headline sits directly under the log band instead,
      // or the two draw straight through each other.
      top: videoMode ? 978 : 0,
      bottom: videoMode ? 520 : 0,
      display: "flex", flexDirection: "column",
      justifyContent: videoMode ? "flex-start" : "flex-end",
      padding: videoMode ? "0 44px" : "0 44px 56px", gap: 20,
    }}>
      {logRows.length && !videoMode ? (
        <div style={{
          display: "flex", gap: 8, background: "#0A0C10EB", borderRadius: 16,
          padding: "12px 14px", marginBottom: 6,
        }}>
          {logRows.slice(0, 6).map((r) => {
            const hot = r.team_key === clubKey;
            return (
              <div key={r.team_key} style={{
                flex: 1, minWidth: 0, padding: "4px 8px", borderRadius: 8,
                background: hot ? GOLD : "transparent",
                color: hot ? "#0A0A0A" : "#E7EAEE",
              }}>
                <div style={{
                  fontSize: 22, whiteSpace: "nowrap", overflow: "hidden",
                  textOverflow: "ellipsis",
                }}>
                  {r.rank} {r.name}
                </div>
                <div style={{ fontSize: 19, fontWeight: 400, opacity: 0.75 }}>
                  {r.points} pts
                </div>
              </div>
            );
          })}
        </div>
      ) : null}

      {kicker ? (
        <div style={{
          alignSelf: "flex-start", background: clubColor, color: "#0A0A0C",
          padding: "10px 22px", borderRadius: 12, fontSize: 30,
          letterSpacing: 0.5,
        }}>
          {kicker.toUpperCase()}
        </div>
      ) : null}

      {/* clamp keeps a four-word hook and a full sentence both legible */}
      <div style={{
        fontSize: `clamp(50px, ${Math.round(3400 /
          Math.max(18, headline.length))}px, 92px)`,
        lineHeight: 1.06, textWrap: "balance",
        textShadow: "0 4px 26px rgba(0,0,0,.75)",
      }}>
        {headline}
      </div>

      <div style={{ width: 150, height: 8, background: GOLD }} />

      {credit ? (
        <div style={{ fontSize: 22, fontWeight: 400, color: "#AEB6BD" }}>
          {credit}
        </div>
      ) : null}
    </div>
  </AbsoluteFill>
);
