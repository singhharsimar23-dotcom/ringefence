import React from "react";
import {Composition} from "remotion";
import {FPS} from "./base";
import {Film, LENGTH} from "./Film";

export const Root: React.FC = () => (
  <Composition id="Film" component={Film} width={1920} height={1080} fps={FPS} durationInFrames={Math.ceil(LENGTH * FPS)} />
);
