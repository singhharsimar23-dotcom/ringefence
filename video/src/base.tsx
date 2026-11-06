// Shared look, the word clock, and the small pieces every scene uses.
import React from "react";
import {AbsoluteFill, Easing, interpolate, spring, useCurrentFrame, useVideoConfig} from "remotion";
import data from "../public/words.json";

export const FPS = 30;
export const C = {
  bg: "#000", ink: "#fff", mute: "rgba(255,255,255,.58)", dim: "rgba(255,255,255,.3)", line: "rgba(255,255,255,.14)",
  panel: "#0b0b0c", accent: "#8aa9ff", red: "#ff5b52", amber: "#f2b84b", green: "#5ee38f",
};
export const SANS = "Geist, Inter, system-ui, sans-serif";
export const MONO = "'Geist Mono', ui-monospace, monospace";
export const EASE = Easing.bezier(0.16, 1, 0.3, 1); // expo-out: fast start, long soft landing

// ---- word clock: every shot is anchored to a phrase Harsimar says, never to a typed time ----
type Word = {w: string; s: number; e: number; o: number};
const norm = (s: string) => s.toLowerCase().replace(/[^a-z0-9$]/g, "");
export const WORDS: (Word & {n: string})[] = (data.words as Word[]).map((w) => ({...w, n: norm(w.w)}));
export const TOTAL: number = data.total;

const find = (phrase: string, after: number) => {
  const p = phrase.split(/\s+/).map(norm).filter(Boolean);
  for (let i = 0; i < WORDS.length; i++) {
    if (WORDS[i].s + 1e-6 < after) continue;
    if (p.every((x, k) => WORDS[i + k] && WORDS[i + k].n === x)) return [i, i + p.length - 1];
  }
  throw new Error(`phrase not in the voice: "${phrase}" after ${after}s`);
};
/** Second (in the cut voice) the phrase starts. */
export const at = (phrase: string, after = 0) => WORDS[find(phrase, after)[0]].s;
/** Second the phrase's last word ends. */
export const end = (phrase: string, after = 0) => WORDS[find(phrase, after)[1]].e;
export const f = (sec: number) => Math.round(sec * FPS);

// ---- motion helpers ----
export const useT = () => useCurrentFrame() / FPS; // seconds since the Sequence started
export const ramp = (t: number, a: number, b: number, from = 0, to = 1, ease = EASE) =>
  interpolate(t, [a, b], [from, to], {extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: ease});
export const useSpring = (delaySec = 0, damping = 200) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  return spring({frame: frame - delaySec * fps, fps, config: {damping, mass: 0.9}});
};

// ---- pieces ----
export const Stage: React.FC<{children: React.ReactNode; style?: React.CSSProperties}> = ({children, style}) => (
  <AbsoluteFill style={{background: C.bg, color: C.ink, fontFamily: SANS, ...style}}>{children}</AbsoluteFill>
);

/** Words rise out of a mask, staggered. `at` = seconds into the scene each line starts. */
export const Rise: React.FC<{text: string; at?: number; size?: number; weight?: number; color?: string; stagger?: number; style?: React.CSSProperties; mono?: boolean}> =
  ({text, at: start = 0, size = 112, weight = 760, color = C.ink, stagger = 0.045, style, mono}) => {
    const t = useT();
    return (
      <div style={{display: "flex", flexWrap: "wrap", gap: `0 ${size * 0.26}px`, justifyContent: "center", fontSize: size, fontWeight: weight,
        letterSpacing: mono ? "-0.01em" : "-0.035em", lineHeight: 1.06, fontFamily: mono ? MONO : SANS, color, ...style}}>
        {text.split(" ").map((w, i) => {
          const p = ramp(t, start + i * stagger, start + i * stagger + 0.5);
          return (
            <span key={i} style={{display: "inline-block", overflow: "hidden", padding: "0.06em 0", margin: "-0.06em 0"}}>
              <span style={{display: "inline-block", transform: `translateY(${(1 - p) * 105}%)`}}>{w}</span>
            </span>
          );
        })}
      </div>
    );
  };

/** Fade + slight lift in, used for secondary elements. */
export const In: React.FC<{at?: number; dur?: number; y?: number; children: React.ReactNode; style?: React.CSSProperties}> =
  ({at: start = 0, dur = 0.5, y = 14, children, style}) => {
    const p = ramp(useT(), start, start + dur);
    return <div style={{opacity: p, transform: `translateY(${(1 - p) * y}px)`, ...style}}>{children}</div>;
  };

/** Small mono stamp in the bottom-right: proof that the thing on screen is real. */
export const Receipt: React.FC<{kind: "live" | "chain" | "sim"; text: string; at?: number}> = ({kind, text, at: start = 0.25}) => {
  const t = useT();
  const p = ramp(t, start, start + 0.35);
  const label = {live: "LIVE · AIRWALLEX SANDBOX", chain: "ON CHAIN · METAL TESTNET", sim: "[SIMULATED] · SANDBOX"}[kind];
  const dot = {live: C.green, chain: C.accent, sim: C.amber}[kind];
  return (
    <div style={{position: "absolute", right: 56, top: 52, opacity: p, transform: `translateY(${(1 - p) * -8}px)`, fontFamily: MONO, fontSize: 19,
      letterSpacing: "0.04em", color: C.ink, background: "rgba(0,0,0,.72)", border: `1px solid ${C.line}`, borderRadius: 10, padding: "12px 16px",
      display: "grid", gap: 6, backdropFilter: "blur(8px)"}}>
      <div style={{display: "flex", alignItems: "center", gap: 10, color: C.mute, fontSize: 15}}>
        <span style={{width: 8, height: 8, borderRadius: 4, background: dot, boxShadow: `0 0 0 4px ${dot}33`}} />{label}
      </div>
      <div>{text}</div>
    </div>
  );
};

/** Marker sweep behind text, left to right. */
export const Mark: React.FC<{at: number; children: React.ReactNode; color?: string; dur?: number}> = ({at: start, children, color = C.accent, dur = 0.5}) => {
  const p = ramp(useT(), start, start + dur);
  return (
    <span style={{backgroundImage: `linear-gradient(${color}40, ${color}40)`, backgroundRepeat: "no-repeat", backgroundSize: `${p * 100}% 100%`,
      borderRadius: 4, padding: "0 4px", margin: "0 -4px", boxDecorationBreak: "clone", WebkitBoxDecorationBreak: "clone"}}>{children}</span>
  );
};

export const Center: React.FC<{children: React.ReactNode; gap?: number; style?: React.CSSProperties}> = ({children, gap = 28, style}) => (
  <AbsoluteFill style={{alignItems: "center", justifyContent: "center", flexDirection: "column", gap, padding: 120, ...style}}>{children}</AbsoluteFill>
);
