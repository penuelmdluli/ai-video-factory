/**
 * CREST OUTRO — the same closing beat as modules/reveal_kit.crest_outro,
 * rebuilt in Remotion so the two can be compared honestly.
 *
 * The PIL version draws every element by hand, per frame: turning rays as
 * line() calls, pulse rings as ellipse() outlines, the badge composited with
 * paste(). It works, but it is a paint library being asked to animate, and it
 * costs roughly a second of wall clock per second of video.
 *
 * Here the same design is a component. Rays are one div rotated by transform,
 * rings are borders scaled by a spring, the badge is an <img>. The browser
 * does the compositing on the GPU, and every value is a pure function of the
 * frame, so nothing is drawn twice.
 *
 * Deliberately matched to the original, not improved: same gold, same dark,
 * same copy, same beats. A comparison is only worth anything if the design is
 * held constant.
 */
import React from "react";
import {
  AbsoluteFill,
  Img,
  interpolate,
  spring,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";

export type CrestOutroProps = {
  badge: string;        // filename in public/, e.g. "chiefs_badge.png"
  headline: string;
  call: string;
  sub: string;
  accent: string;
  ground: string;
};

const RAYS = 18;

export const CrestOutro: React.FC<CrestOutroProps> = ({
  badge,
  headline,
  call,
  sub,
  accent,
  ground,
}) => {
  const frame = useCurrentFrame();
  const { fps, width, height } = useVideoConfig();
  const t = frame / fps;

  // Entrance: overshoot, then settle into a slow breath. Same shape as the
  // PIL _over() curve, but the spring gives it real physics for free.
  const enter = spring({ frame, fps, config: { damping: 12, mass: 0.7 } });
  const breathe = 1 + 0.025 * Math.sin(t * 2.4);
  const badgeScale = enter * breathe;

  const cy = height * 0.44;
  const fadeIn = (start: number, len = 0.5) =>
    interpolate(t, [start, start + len], [0, 1], {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
    });

  return (
    <AbsoluteFill style={{ backgroundColor: ground, overflow: "hidden" }}>
      {/* turning rays */}
      <AbsoluteFill
        style={{
          transform: `rotate(${t * 11}deg)`,
          transformOrigin: `${width / 2}px ${cy}px`,
        }}
      >
        {Array.from({ length: RAYS }).map((_, i) => {
          const a = 0.05 + 0.05 * (0.5 + 0.5 * Math.sin(t * 2 + i));
          return (
            <div
              key={i}
              style={{
                position: "absolute",
                left: width / 2,
                top: cy - 13,
                width: 520,
                height: 26,
                background: accent,
                opacity: a,
                transformOrigin: "0 50%",
                transform: `rotate(${(360 / RAYS) * i}deg)`,
              }}
            />
          );
        })}
      </AbsoluteFill>

      {/* pulse rings on a slow beat */}
      {[0, 1].map((k) => {
        const ph = (t * 0.55 + k * 0.5) % 1;
        const r = 230 + ph * 330;
        return (
          <div
            key={k}
            style={{
              position: "absolute",
              left: width / 2 - r,
              top: cy - r,
              width: r * 2,
              height: r * 2,
              borderRadius: "50%",
              border: `4px solid ${accent}`,
              opacity: (1 - ph) * 0.34,
            }}
          />
        );
      })}

      {/* the badge */}
      <div
        style={{
          position: "absolute",
          left: 0,
          top: cy - 230,
          width,
          display: "flex",
          justifyContent: "center",
        }}
      >
        <Img
          src={staticFile(badge)}
          style={{
            width: 460,
            height: 460,
            objectFit: "contain",
            transform: `scale(${badgeScale})`,
          }}
        />
      </div>

      {/* scrim behind the words — the rays run straight through this band and
          the call to action was disappearing into them in the PIL build */}
      <div
        style={{
          position: "absolute",
          left: 0,
          top: cy + 300,
          width,
          height: 300,
          background: `linear-gradient(to bottom, transparent, ${ground} 22%, ${ground} 78%, transparent)`,
          opacity: fadeIn(0.4),
        }}
      />

      <div
        style={{
          position: "absolute",
          left: 0,
          top: cy + 322,
          width,
          textAlign: "center",
          fontFamily: "Arial Black, Arial, sans-serif",
        }}
      >
        <div
          style={{
            fontSize: 62,
            fontWeight: 900,
            color: accent,
            opacity: fadeIn(0.5),
            letterSpacing: "-0.01em",
          }}
        >
          {headline}
        </div>
        <div
          style={{
            fontSize: 54,
            fontWeight: 900,
            color: "#fff",
            marginTop: 26,
            opacity: fadeIn(0.9),
            textShadow: "0 3px 0 #06080a, 0 -3px 0 #06080a, 3px 0 0 #06080a, -3px 0 0 #06080a",
          }}
        >
          {call}
        </div>
        <div
          style={{
            fontSize: 40,
            fontWeight: 700,
            color: accent,
            marginTop: 22,
            opacity: (0.6 + 0.4 * (0.5 + 0.5 * Math.sin(t * 3.4))) * fadeIn(1.3),
            letterSpacing: "0.04em",
          }}
        >
          {sub}
        </div>
      </div>
    </AbsoluteFill>
  );
};
