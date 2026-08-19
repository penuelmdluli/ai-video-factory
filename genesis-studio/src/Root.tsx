import React from "react";
import { Composition, Still } from "remotion";
import { StatsBand } from "./StatsBand";
import { JobCard } from "./JobCard";
import { NewsCard } from "./NewsCard";
import band from "../input/band.example.json";
import card from "../input/card.example.json";
import news from "../input/news.example.json";

export const RemotionRoot: React.FC = () => (
  <>
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
    <Still
      id="NewsCard"
      component={NewsCard as any}
      width={1080}
      height={1920}
      defaultProps={news as any}
    />
  </>
);
