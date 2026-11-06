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

// the Loom keeps Harsimar full-frame until 61 s, then in a circle bottom-left; crop whichever is on screen
const LOOM_SWITCH = 61;
const REGION = (t: number) => (t < LOOM_SWITCH ? {x: 650, y: 50, s: 560} : {x: 10, y: 290, s: 500});
const D = 220;
/** his face, from the same Loom frame as the voice, so the lips always match */
export const FaceBubble: React.FC<{hide: [number, number][]}> = ({hide}) => {
  const t = useCurrentFrame() / FPS;
  if (hide.some(([a, b]) => t >= a && t < b)) return null;
  const r = REGION(t);
  const k = D / r.s;
  return (
    <div style={{position: "absolute", left: 36, bottom: 36, width: D, height: D, borderRadius: D, overflow: "hidden", border: "2px solid rgba(255,255,255,.85)",
      boxShadow: "0 8px 30px rgba(0,0,0,.5)"}}>
      <OffthreadVideo src={staticFile("loom_cut.mp4")} muted style={{position: "absolute", width: 1920 * k, height: 798 * k, left: -r.x * k, top: -r.y * k, maxWidth: "none"}} />
    </div>
  );
};

/** where we are in the film: running timecode + chapter, top-left */
export const Chapter: React.FC<{chapters: [number, string][]; until: number}> = ({chapters, until}) => {
  const t = useCurrentFrame() / FPS;
  if (t >= until) return null;
  const c = [...chapters].reverse().find(([s]) => t >= s)?.[1] ?? "";
  const mm = `${Math.floor(t / 60)}`.padStart(2, "0"), ss = `${Math.floor(t % 60)}`.padStart(2, "0");
  return (
    <div style={{position: "absolute", left: 36, top: 28, fontFamily: MONO, fontSize: 18, letterSpacing: "0.06em", color: C.ink, background: "rgba(0,0,0,.72)",
      padding: "7px 12px", borderRadius: 6}}>
      <span style={{color: "#ff4d4d"}}>●</span> {mm}:{ss} · {c}
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
