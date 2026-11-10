// The real-proof layer: raw window screenshots, Harsimar's live face bubble, a chapter/timecode label, and hard-cut punch lines.
import React from "react";
import {AbsoluteFill, Img, OffthreadVideo, getStaticFiles, staticFile, useCurrentFrame} from "remotion";
import {C, FPS, MONO, SANS, ramp, useT} from "./base";

export const has = (file: string) => getStaticFiles().some((x) => x.name === file);

/** a real screenshot exactly as captured (title bar, tabs, taskbar and all), fitted whole to the frame, a 2% push and nothing else */
export const Raw: React.FC<{src: string}> = ({src}) => {
  const t = useT();
  return (
    <AbsoluteFill style={{background: "#000", alignItems: "center", justifyContent: "center", overflow: "hidden"}}>
      <Img src={staticFile(src)} style={{width: 1920, height: 1080, objectFit: "contain", transform: `scale(${1 + 0.02 * ramp(t, 0, 8, 0, 1, (x) => x)})`}} />
    </AbsoluteFill>
  );
};

/** hard cuts between screenshots on the voice: [voice second, file] */
export const RawCuts: React.FC<{t0: number; cuts: [number, string][]}> = ({t0, cuts}) => {
  const t = useT() + t0;
  const c = [...cuts].reverse().find(([s]) => t >= s) ?? cuts[0];
  return <Raw key={c[1]} src={c[1]} />;
};

// after the switch the Loom shows Harsimar in a circle bottom-left; this square crops it (raw Loom px, 1920x798)
const REGION = {x: 25, y: 303, s: 470};
export type Grow = {a: number; b: number; x: number; y: number; d: number}; // a..b: big at centre (x, y) with diameter d
const SMALL = {x: 40 + 105, y: 1080 - 40 - 105, d: 210};
/** his face, from the same Loom frame as the voice, so the lips always match; it grows at chapter openers and springs back */
export const FaceBubble: React.FC<{hide: [number, number][]; from: number; grows: Grow[]}> = ({hide, from, grows}) => {
  const t = useCurrentFrame() / FPS;
  if (t < from || hide.some(([a, b]) => t >= a && t < b)) return null;
  const g = grows.find((x) => t >= x.a - 0.05 && t < x.b + 0.8);
  const k = g ? ramp(t, g.a, g.a + 0.75) * (1 - ramp(t, g.b, g.b + 0.75)) : 0;
  const lerp = (u: number, v: number) => u + (v - u) * k;
  const D = g ? lerp(SMALL.d, g.d) : SMALL.d, cx = g ? lerp(SMALL.x, g.x) : SMALL.x, cy = g ? lerp(SMALL.y, g.y) : SMALL.y;
  const z = D / REGION.s;
  return (
    <div style={{position: "absolute", left: cx - D / 2, top: cy - D / 2, width: D, height: D, borderRadius: D, overflow: "hidden",
      border: `${2 + k}px solid rgba(255,255,255,${0.85 - 0.25 * k})`, boxShadow: `0 ${8 + 22 * k}px ${30 + 50 * k}px rgba(0,0,0,.6)`}}>
      <OffthreadVideo src={staticFile("loom_cut.mp4")} muted style={{position: "absolute", width: 1920 * z, height: 798 * z, left: -REGION.x * z, top: -REGION.y * z, maxWidth: "none"}} />
    </div>
  );
};

/** where we are in the film: running timecode + chapter, top-left */
export const Chapter: React.FC<{chapters: [number, string][]; until: number; from?: number}> = ({chapters, until, from = 0}) => {
  const t = useCurrentFrame() / FPS;
  if (t >= until || t < from) return null;
  const c = [...chapters].reverse().find(([s]) => t >= s)?.[1] ?? "";
  const mm = `${Math.floor(t / 60)}`.padStart(2, "0"), ss = `${Math.floor(t % 60)}`.padStart(2, "0");
  return (
    <div style={{position: "absolute", left: 36, top: 28, fontFamily: MONO, fontSize: 18, letterSpacing: "0.06em", color: C.ink, background: "rgba(0,0,0,.8)",
      padding: "8px 14px", borderRadius: 8, border: `1px solid ${C.line}`, whiteSpace: "pre"}}>
      <span style={{color: C.mute}}>{mm}:{ss}</span>  ·  {c}
    </div>
  );
};

/** a punch line on the voice: cuts in hard (3-frame settle), cuts out hard */
export const Bams: React.FC<{lines: [number, number, string][]}> = ({lines}) => {
  const t = useCurrentFrame() / FPS;
  const b = lines.find(([a, e]) => t >= a && t < e);
  if (!b) return null;
  const p = ramp(t, b[0], b[0] + 0.1, 0, 1, (x) => x);
  return (
    <div style={{position: "absolute", left: 36, top: 84, maxWidth: 1300, fontFamily: SANS, fontSize: 60, fontWeight: 780, letterSpacing: "-0.02em", lineHeight: 1.1,
      color: "#fff", background: "#000", padding: "14px 26px 18px", borderRadius: 8, transform: `scale(${1.06 - 0.06 * p})`, transformOrigin: "left top"}}>
      {b[2]}
    </div>
  );
};
