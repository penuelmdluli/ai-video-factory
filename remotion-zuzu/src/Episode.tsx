import React from "react";
import { AbsoluteFill, Audio, Series, staticFile } from "remotion";
import { Lesson, Scene, framesFor } from "./schema";
import {
  Background, TitleScene, CountingScene, LetterScene, PhonicsScene, AdditionScene,
  KaraokeScene, CharacterScene, OutroScene,
} from "./scenes";

// Rotate Zuzu poses: a different still per scene. Karaoke uses the open-mouth singing
// pose (imgs[1]) so Zuzu sings the visible words.
const poseFor = (type: string, imgs: string[], single: string) =>
  ((type === "title" ? imgs[0] : type === "character" ? imgs[1] : type === "karaoke" ? imgs[1]
    : type === "outro" ? imgs[2] : "") || single);

const renderScene = (s: Scene, character: string, imgs: string[], single: string,
                     mouthEnv: number[], startFrame: number, mouthX: number, mouthY: number) => {
  switch (s.type) {
    case "title": return <TitleScene text={s.text} subtitle={s.subtitle} char={poseFor("title", imgs, single)} />;
    case "counting": return <CountingScene count={s.count} emoji={s.emoji} label={s.label} />;
    case "letter": return <LetterScene letter={s.letter} word={s.word} emoji={s.emoji} />;
    case "phonics": return <PhonicsScene letter={s.letter} sound={s.sound} word={s.word} emoji={s.emoji} />;
    case "addition": return <AdditionScene a={s.a} b={s.b} emoji={s.emoji} label={s.label} />;
    case "karaoke": return <KaraokeScene lines={s.lines} durationInFrames={0} />;
    case "character": return <CharacterScene clip={s.clip} img={poseFor("character", imgs, single)} caption={s.caption}
                               character={character} mouthEnv={mouthEnv} startFrame={startFrame} mouthX={mouthX} mouthY={mouthY} />;
    case "outro": return <OutroScene text={s.text} character={character} char={poseFor("outro", imgs, single)} />;
    default: return null;
  }
};

export const Episode: React.FC<Lesson> = (lesson) => {
  const { scenes, fps, audio, color1, color2, character, characterImg, characterImgs, mouthEnv, mouthX, mouthY } = lesson;
  let acc = 0;
  return (
    <AbsoluteFill>
      <Background color1={color1} color2={color2} />
      {audio ? <Audio src={staticFile(audio)} /> : null}
      <Series>
        {scenes.map((s, i) => {
          const dur = framesFor(s, fps);
          const startFrame = acc; acc += dur;
          return (
            <Series.Sequence durationInFrames={dur} key={i}>
              {s.type === "karaoke"
                ? <KaraokeScene lines={s.lines} words={s.words} durationInFrames={dur} startFrame={startFrame}
                    img={poseFor("karaoke", characterImgs, characterImg)} mouthEnv={mouthEnv}
                    mouthX={mouthX} mouthY={mouthY} character={character} />
                : renderScene(s, character, characterImgs, characterImg, mouthEnv, startFrame, mouthX, mouthY)}
            </Series.Sequence>
          );
        })}
      </Series>
    </AbsoluteFill>
  );
};
