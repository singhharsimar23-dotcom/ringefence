// Minimal subtitles: one line, bottom centre, broken at Harsimar's pauses. Hidden while big type says the same thing.
import React from "react";
import {AbsoluteFill} from "remotion";
import {SANS, WORDS, ramp, useT} from "./base";

// speech-recognition slips, fixed to what was said or meant; wording otherwise kept as spoken
const FIX: [RegExp, string][] = [
  [/\bair ?wallets?\b/gi, "Airwallex"], [/\bNorth ?(One|Wind)\b/g, "Northwind"], [/\bHarbor Food\b/g, "Harbour Foods"], [/\bHarbor\b/g, "Harbour"],
  [/\bRing Fence\b/g, "Ringfence"], [/\bmy court\b/g, "my code"], [/\bI build Ringfence/g, "I built Ringfence"], [/\bget it its own\b/g, "gets its own"], [/\bclient get$/, "client gets"], [/^it its own\b/, "its own"],
  [/\bthat's what I build\b/gi, "That's what I built"], [/\bCount, we\b/g, "We"], [/\buntil failure\b/g, "under failure"],
  [/\bafter it marks fail\b/g, "after it's marked paid"], [/\binto their own account\b/g, "into our own account"],
  [/\bEach credential and client has its own Airwallex credential\b/g, "Each client has its own Airwallex credential"],
  [/\bwhatever it told\b/g, "whatever it's told"], [/\b28 attack\b/g, "28 attacks"], [/\bapproved tool\b/g, "approve tool"],
  [/\bsign up and release\b/g, "sign-off and release"], [/\byour own payload\b/g, "your own payroll"], [/\b20 payment\b/g, "20 payments"],
  [/\bA bank changes\b/g, "A bank change"], [/\btimesheet and email\b/g, "timesheets and emails"], [/\bdeterministic code, prices, every/g, "deterministic code prices every"],
];

type Chunk = {s: number; e: number; text: string};
export const CHUNKS: Chunk[] = (() => {
  const out: Chunk[] = [];
  let cur: typeof WORDS = [];
  const flush = () => {
    if (!cur.length) return;
    let text = cur.map((w) => w.w).join(" ").replace(/\s+([,.?!])/g, "$1");
    for (const [re, to] of FIX) text = text.replace(re, to);
    out.push({s: cur[0].s, e: cur[cur.length - 1].e, text: text.replace(/[,]$/, "")});
    cur = [];
  };
  WORDS.forEach((w, i) => {
    cur.push(w);
    const next = WORDS[i + 1];
    const chars = cur.map((x) => x.w).join(" ").length;
    const pause = next ? next.s - w.e : 9;
    if (!next || pause > 0.28 || /[.?!]$/.test(w.w) || (/,$/.test(w.w) && cur.length >= 3) || chars > 36 || cur.length >= 7) flush();
  });
  return out;
})();

export const Subs: React.FC<{hide: [number, number][]}> = ({hide}) => {
  const t = useT();
  const c = CHUNKS.find((x) => t >= x.s - 0.15 && t < Math.max(x.e + 0.25, x.s + 0.9));
  if (!c || hide.some(([a, b]) => t >= a && t < b)) return null;
  const p = ramp(t, c.s - 0.15, c.s - 0.02);
  return (
    <AbsoluteFill style={{justifyContent: "flex-end", alignItems: "center", paddingBottom: 54, pointerEvents: "none"}}>
      <div style={{fontFamily: SANS, fontSize: 36, fontWeight: 500, letterSpacing: "-0.01em", color: "rgba(255,255,255,.9)", opacity: p,
        textShadow: "0 1px 2px rgba(0,0,0,.9)", maxWidth: 1300, textAlign: "center",
        background: "rgba(0,0,0,.66)", padding: "6px 18px", borderRadius: 8}}>{c.text}</div>
    </AbsoluteFill>
  );
};
