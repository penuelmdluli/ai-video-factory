import React from "react";
import { Composition, Still } from "remotion";
import { StatsBand } from "./StatsBand";
import { JobCard } from "./JobCard";
import { NewsCard } from "./NewsCard";
import { JobReel } from "./JobReel";
import { CrestOutro } from "./CrestOutro";
import band from "../input/band.example.json";
import card from "../input/card.example.json";
import news from "../input/news.example.json";

export const RemotionRoot: React.FC = () => (
  <>
    <Composition
      id="CrestOutro"
      component={CrestOutro as any}
      durationInFrames={30 * 10}
      fps={30}
      width={1080}
      height={1920}
      defaultProps={{
        badge: "chiefs_badge.png",
        headline: "CHIEFS FANS ARE NUMBER 1",
        call: "WHO STARTS? COMMENT BELOW",
        sub: "SUBSCRIBE — GENESIS NEWS",
        accent: "#FFC107",
        ground: "#0C0E12",
      }}
    />
    <Composition
      id="StatsBand"
      component={StatsBand as any}
      durationInFrames={20 * 30}
      fps={30}
      width={1032}
      height={120}
      defaultProps={band as any}
    />
    <Still
      id="JobCard"
      component={JobCard as any}
      width={1080}
      height={1350}
      defaultProps={card as any}
    />
    <Composition
      id="JobReel"
      component={JobReel as any}
      durationInFrames={30 * 26}
      fps={30}
      width={1080}
      height={1920}
      defaultProps={{
        employer: "PUBLIC WORKS", role: "Road Worker", positions: 99,
        details: ["Salary: R170 226 per annum", "Centre: Durban Region",
                  "Closing date: 28 August 2026"],
        closes: "CLOSES 28 AUGUST 2026", entryLevel: true,
        source: "Public Service Vacancy Circular 29 of 2026",
      } as any}
      calculateMetadata={({ props }: any) => ({
        durationInFrames: Math.round((props.durationInSeconds || 26) * 30),
      })}
    />
    <Still
      id="NewsCard"
      component={NewsCard as any}
      width={1080}
      height={1920}
      defaultProps={news as any}
    />
  </>
);
