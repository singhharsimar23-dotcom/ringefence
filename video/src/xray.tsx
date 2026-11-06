// X-ray: the picture slides left and the real wire traffic underneath it slides in on the right. Lines come from /api/calls and the ledger.
import React from "react";
import {AbsoluteFill} from "remotion";
import {C, MONO, ramp, useT} from "./base";

export type Wire = {at: number; text: string; color?: string; size?: number; gap?: number};

export const XRay: React.FC<{under: React.ReactNode; lines: Wire[]; title: string; out?: number}> = ({under, lines, title, out = 99}) => {
  const t = useT();
  const p = ramp(t, 0, 0.7) * (1 - ramp(t, out, out + 0.6));
  const s = 1 - 0.5 * p; // 960 px wide, clear of the wire column at x >= 1100
  return (
    <AbsoluteFill style={{background: C.bg}}>
      <AbsoluteFill style={{transformOrigin: "0 50%", transform: `translateX(${p * 50}px) scale(${s})`, borderRadius: 14 * p, overflow: "hidden",
        outline: p > 0.01 ? `1px solid ${C.line}` : undefined}}>{under}</AbsoluteFill>
      <div style={{position: "absolute", top: 0, bottom: 0, right: 0, width: 860, padding: "0 70px 0 40px", display: "flex", flexDirection: "column",
        justifyContent: "center", opacity: p, transform: `translateX(${(1 - p) * 60}px)`}}>
        <div style={{fontFamily: MONO, fontSize: 16, letterSpacing: "0.14em", color: C.mute, marginBottom: 26}}>{title}</div>
        {lines.map((l, i) => <Line key={i} {...l} />)}
      </div>
    </AbsoluteFill>
  );
};

const Line: React.FC<Wire> = ({at, text, color = C.ink, size = 22, gap = 10}) => {
  const t = useT();
  const n = Math.floor(ramp(t, at, at + Math.min(0.6, text.length * 0.012), 0, text.length, (x) => x)); // typed on, fast
  return (
    <div style={{fontFamily: MONO, fontSize: size, color, whiteSpace: "pre-wrap", wordBreak: "break-all", lineHeight: 1.45, marginTop: gap, opacity: t >= at ? 1 : 0}}>
      {text.slice(0, n)}
    </div>
  );
};

/** The control named the way a payments veteran already names it. Small, mono, once. */
export const Tag: React.FC<{at?: number; children: React.ReactNode; style?: React.CSSProperties}> = ({at = 0, children, style}) => {
  const p = ramp(useT(), at, at + 0.5);
  return (
    <div style={{fontFamily: MONO, fontSize: 24, color: C.mute, letterSpacing: "0.02em", opacity: p, borderTop: `1px solid ${C.line}`, paddingTop: 18,
      transform: `translateY(${(1 - p) * 8}px)`, ...style}}>{children}</div>
  );
};
