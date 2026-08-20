import React from "react";
import { AbsoluteFill, Img, staticFile } from "remotion";

export type JobCardProps = {
  employer: string;
  programme: string;
  details: string[];
  closes?: string;          // "" when the source publishes no date
  applyLine?: string;
  source?: string;
  photo?: string;           // optional employer/backdrop image URL
  photoCredit?: string;
};

const GREEN = "#2EC871";
const INK = "#0A0C0E";

/** The shareable job card.
 *
 * The PIL version had to shrink fonts by measuring strings, and still shipped
 * "CORRECTIONAL SERVICES" running off both edges and details cut mid-sentence
 * at 38 characters. Here the type simply wraps and the panels size to their
 * content, so neither failure is expressible.
 */
export const JobCard: React.FC<JobCardProps> = ({
  employer, programme, details, closes = "", applyLine, source, photo,
  photoCredit,
}) => (
  <AbsoluteFill style={{
    background: `linear-gradient(165deg, #16281E 0%, ${INK} 55%)`,
    fontFamily: "Arial Black, Arial, sans-serif", color: "#fff",
    display: "flex", flexDirection: "column",
  }}>
    {/* diagonal brand ribbing */}
    <AbsoluteFill style={{
      backgroundImage:
        `repeating-linear-gradient(-45deg, ${GREEN}0F 0 6px, transparent 6px 60px)`,
    }} />

    <div style={{
      background: "#0A0A0C", padding: "22px 44px 18px", zIndex: 1,
    }}>
      <div style={{ fontSize: 44, letterSpacing: 0.5 }}>MZANSI CAREERS</div>
      <div style={{ fontSize: 24, color: GREEN, fontWeight: 400, marginTop: 6 }}>
        VERIFIED OPPORTUNITY
      </div>
    </div>

    {photo ? (
      <div style={{ height: 430, overflow: "hidden", position: "relative" }}>
        {/* staticFile: a bare filename is not a URL Remotion can load, and
            the failed image cancelled the whole render — which is why every
            card with a photo silently fell back to PIL */}
        <Img src={staticFile(photo)} style={{
          width: "100%", height: "100%", objectFit: "cover",
        }} />
        <AbsoluteFill style={{
          background: `linear-gradient(to bottom, transparent 40%, ${INK} 100%)`,
        }} />
      </div>
    ) : null}

    <div style={{
      flex: 1, padding: "28px 44px 0", zIndex: 1, display: "flex",
      flexDirection: "column", gap: 18, justifyContent: "center",
    }}>
      <div style={{
        alignSelf: "flex-start", background: GREEN, color: "#0A0A0C",
        padding: "10px 24px", borderRadius: 16, fontSize: 34,
      }}>
        JOB ALERT
      </div>

      {/* wraps instead of running off the edge */}
      <div style={{ fontSize: 76, lineHeight: 1.02, textWrap: "balance" }}>
        {employer}
      </div>
      <div style={{
        fontSize: 36, fontWeight: 400, color: "#DCE0E4", marginTop: -6,
      }}>
        {programme}
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
        {details.map((d) => (
          <div key={d} style={{
            display: "flex", gap: 16, alignItems: "flex-start", fontSize: 30,
          }}>
            <div style={{
              width: 22, height: 22, borderRadius: 11, background: GREEN,
              marginTop: 8, flexShrink: 0,
            }} />
            <div style={{ fontWeight: 400, lineHeight: 1.25 }}>{d}</div>
          </div>
        ))}
      </div>
    </div>

    <div style={{ padding: "0 44px 34px", zIndex: 1 }}>
      <div style={{
        background: closes ? "#DC3232" : "transparent",
        border: closes ? "none" : `3px solid ${GREEN}`,
        color: closes ? "#fff" : GREEN,
        borderRadius: 18, padding: "20px 0", textAlign: "center",
        fontSize: closes ? 42 : 32,
      }}>
        {closes || "OPEN — CHECK THE PORTAL FOR DATES"}
      </div>
      {applyLine ? (
        <div style={{
          textAlign: "center", color: GREEN, fontSize: 27, fontWeight: 400,
          marginTop: 16,
        }}>
          {applyLine}
        </div>
      ) : null}
      <div style={{
        textAlign: "center", color: "#C6CBD0", fontSize: 25, fontWeight: 400,
        marginTop: 10,
      }}>
        We verify every post — no scams, no fees, ever.
      </div>
      {source ? (
        <div style={{
          textAlign: "center", color: "#7C8891", fontSize: 20,
          fontWeight: 400, marginTop: 12,
        }}>
          {source}{photoCredit ? ` · ${photoCredit}` : ""}
        </div>
      ) : null}
    </div>
  </AbsoluteFill>
);
