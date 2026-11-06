// Cold open, before Harsimar speaks: three real outcomes from live runs, one line each. The film's promise in 5 seconds.
import React from "react";
import {AbsoluteFill} from "remotion";
import {C, MONO, SANS, ramp, useT} from "../base";

const ROWS: {at: number; tried: string; got: string; red?: boolean}[] = [
  {at: 0.35, tried: "Kestrel's API key → Harbour's account", got: "401 credentials_invalid", red: true},
  {at: 1.25, tried: "20 releases at once, 3 replies lost", got: "1 · 1 · 1 transfers"},
  {at: 2.15, tried: "pull one coin over the mandate", got: "refused on-chain", red: true},
];

export const ColdOpen: React.FC = () => {
  const t = useT();
  const out = 1 - ramp(t, 4.55, 5);
  return (
    <AbsoluteFill style={{background: C.bg, justifyContent: "center", paddingLeft: 260, opacity: out}}>
      <div style={{display: "grid", gridTemplateColumns: "640px auto", rowGap: 34, alignItems: "baseline"}}>
        {ROWS.map((r) => {
          const p = ramp(t, r.at, r.at + 0.45);
          const q = ramp(t, r.at + 0.35, r.at + 0.7);
          return (
            <React.Fragment key={r.got}>
              <div style={{fontFamily: MONO, fontSize: 26, color: C.mute, opacity: p, transform: `translateY(${(1 - p) * 10}px)`}}>{r.tried}</div>
              <div style={{fontFamily: MONO, fontSize: 44, fontWeight: 600, letterSpacing: "-0.01em", color: r.red ? C.red : C.ink, opacity: q}}>{r.got}</div>
            </React.Fragment>
          );
        })}
      </div>
      <div style={{fontFamily: SANS, fontSize: 30, color: C.ink, marginTop: 70, opacity: ramp(t, 3.2, 3.7)}}>
        Every ID in this film comes from a live run.
      </div>
    </AbsoluteFill>
  );
};
