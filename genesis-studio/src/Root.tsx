import React from "react";
import { Composition } from "remotion";
import { StatsBand } from "./StatsBand";
import sample from "../input/band.example.json";

export const RemotionRoot: React.FC = () => (
  <Composition
    id="StatsBand"
    component={StatsBand as any}
    durationInFrames={20 * 30}
    fps={30}
    width={1032}
    height={120}
    defaultProps={sample as any}
  />
);
