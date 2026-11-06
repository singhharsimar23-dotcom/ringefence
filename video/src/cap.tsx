// Our own screen capture with a camera on it. Boxes come from capture.py (CSS px in a 1440x810 viewport), so zooms land on the exact element.
import React from "react";
import {AbsoluteFill, OffthreadVideo, staticFile} from "remotion";
import {C, ramp, useT} from "./base";

export type Box = [number, number, number, number];
export type Zoom = {at: number; box?: Box; scale?: number}; // at = seconds into the shot; no box = back to the full frame
const K = 1920 / 1440;

const cam = (z: Zoom) => {
  if (!z.box) return {s: 1, x: 960, y: 540};
  const [x, y, w, h] = z.box;
  const s = z.scale ?? Math.min(1.8, Math.max(1.25, Math.min(1500 / (w * K), 820 / (h * K))));
  return {s, x: (x + w / 2) * K, y: (y + h / 2) * K};
};

export const Cap: React.FC<{src: string; from: number; rate?: number; zooms?: Zoom[]; dim?: number}> = ({src, from, rate = 1, zooms = [], dim = 0}) => {
  const t = useT();
  let a = cam({at: 0});
  let b = a;
  let p = 1;
  for (const z of zooms) {
    if (t < z.at) break;
    a = p < 1 ? lerp(a, b, p) : b; // a zoom that starts mid-travel continues from where the camera is
    b = cam(z);
    p = ramp(t, z.at, z.at + 0.9);
  }
  const c = lerp(a, b, p);
  const tx = clamp(960 - c.x * c.s, 1920 - 1920 * c.s, 0);
  const ty = clamp(540 - c.y * c.s, 1080 - 1080 * c.s, 0);
  return (
    <AbsoluteFill style={{background: C.bg, overflow: "hidden"}}>
      <div style={{position: "absolute", width: 1920, height: 1080, transformOrigin: "0 0", transform: `translate(${tx}px, ${ty}px) scale(${c.s})`}}>
        <OffthreadVideo src={staticFile(src)} startFrom={Math.round(from * 30)} playbackRate={rate} muted style={{width: 1920, height: 1080}} />
      </div>
      {dim > 0 && <AbsoluteFill style={{background: `rgba(0,0,0,${dim})`}} />}
    </AbsoluteFill>
  );
};

const lerp = (a: {s: number; x: number; y: number}, b: typeof a, p: number) => ({s: a.s + (b.s - a.s) * p, x: a.x + (b.x - a.x) * p, y: a.y + (b.y - a.y) * p});
const clamp = (v: number, lo: number, hi: number) => Math.min(hi, Math.max(lo, v));

/** Harsimar's own recording at the same moment of the voice: untouched, full frame, letterboxed. */
export const Face: React.FC<{t0: number; lower?: string}> = ({t0, lower}) => {
  const t = useT();
  return (
    <AbsoluteFill style={{background: C.bg, justifyContent: "center"}}>
      <OffthreadVideo src={staticFile("loom_cut.mp4")} startFrom={Math.round(t0 * 30)} muted style={{width: 1920, height: 798}} />
      {lower && (
        <div style={{position: "absolute", left: 96, top: 72, fontFamily: "'Geist Mono', monospace", fontSize: 24, letterSpacing: "0.06em", color: C.ink,
          opacity: ramp(t, 0.5, 1) * (1 - ramp(t, 3.2, 3.6)), borderLeft: `2px solid ${C.accent}`, paddingLeft: 16}}>{lower}</div>
      )}
    </AbsoluteFill>
  );
};
