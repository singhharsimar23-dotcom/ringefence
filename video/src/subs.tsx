// Subtitles: 2-7 words, bottom centre, broken at Harsimar's pauses, the spoken word lit. Hidden while big type says the same thing.
import React from "react";
import {AbsoluteFill} from "remotion";
import {SANS, WORDS, ramp, useT} from "./base";

// speech-recognition slips and spoken slips, fixed to what he meant (word sequences, matched without case or punctuation)
const FIX: [string, string][] = [
  ["Harsimur", "Harsimar Singh"],
  ["for lot of other", "for lots of other"],
  ["Airwallex API has its tools", "Airwallex's API as its tools"],
  ["I build an agent first and spend days", "I built that agent first and spent days"],
  ["the pay and says yes", "the payee and says yes."],
  ["no element", "no alert."],
  ["the agent loses the money", "the agent loses the reply"],
  ["can goes to another client's login", "can go out on another client's login."],
  ["two pound was moved", "two moved"],
  ["Paid people shows an unpaid", "Paid people show as unpaid,"],
  ["unpaid people shows that paid", "unpaid people show as paid."],
  ["So I built a ring fence around these findings and bugs", "So I built Ringfence from these findings."],
  ["every client contractor", "every client's contractors."],
  ["Kestrel account", "Kestrel's account."],
  ["Everyone sits paid", "Everyone's paid"],
  ["The bank swap issue is held", "The bank swap is held"],
  ["locked the exact bank detail", "locks the exact bank details"],
  ["and sends them into the payment", "and sends them with the payment."],
  ["The retry pays once before every payment id is fixed", "The retry pays once, because every payment's ID is fixed"],
  ["each agent run on its own login", "each client runs on its own login."],
  ["12 space", "twelve ways,"],
  ["from the engineer", "for the engineers."],
  ["Code log in each client and set amount limits and request id in decimal", "Code logs in as each client and sets amounts, limits and request IDs, in decimals."],
  ["It is never float", "Never floats."],
  ["chain had", "chain head"],
  ["Airwallex copies still will disagree", "Airwallex's copy still disagrees."],
  ["ring fence run as", "Ringfence runs as"],
  ["no approved tools", "no approve tool."],
  ["humans always sign", "a human always signs."],
  ["tagged", "attacked"],
  ["200 ledger added every one count", "200 ledger edits, every one caught,"],
  ["The demo is life", "The demo is live."],
  ["hashed chain", "hash-chained"],
  ["ring fence", "Ringfence"],
  ["air wallet", "Airwallex"],
  ["air wallets", "Airwallex"],
  ["North one", "Northwind"],
  ["North wind", "Northwind"],
  ["Harbor", "Harbour"],
  ["harbour", "Harbour"],
  ["Harbor's", "Harbour's"],
];

type W = {w: string; s: number; e: number};
const norm = (s: string) => s.toLowerCase().replace(/[^a-z0-9$]/g, "");

/** the spoken words with the fixes applied; a replaced span keeps its start and end, its new words share the time evenly */
export const SUBWORDS: W[] = (() => {
  const rules = FIX.map(([a, b]) => [a.split(/\s+/).map(norm), b.split(/\s+/)] as const);
  const out: W[] = [];
  for (let i = 0; i < WORDS.length; ) {
    const r = rules.find(([p]) => p.every((x, k) => WORDS[i + k] && WORDS[i + k].n === x));
    if (!r) { out.push(WORDS[i]); i++; continue; }
    const [p, to] = r, last = WORDS[i + p.length - 1], s = WORDS[i].s, d = (last.e - s) / to.length;
    const tail = /[.,?!]$/.test(last.w) && !/[.,?!]$/.test(to[to.length - 1]) ? last.w.slice(-1) : "";
    to.forEach((w, k) => out.push({w: k === to.length - 1 ? w + tail : w, s: s + k * d, e: s + (k + 1) * d}));
    i += p.length;
  }
  return out;
})();

type Chunk = {s: number; e: number; words: W[]};
export const CHUNKS: Chunk[] = (() => {
  const out: Chunk[] = [];
  let cur: W[] = [];
  SUBWORDS.forEach((w, i) => {
    cur.push(w);
    const next = SUBWORDS[i + 1];
    const chars = cur.map((x) => x.w).join(" ").length;
    const pause = next ? next.s - w.e : 9;
    if (!next || pause > 0.28 || /[.?!]$/.test(w.w) || (/,$/.test(w.w) && cur.length >= 3) || chars > 34 || cur.length >= 7) {
      out.push({s: cur[0].s, e: cur[cur.length - 1].e, words: cur});
      cur = [];
    }
  });
  return out;
})();

const glue = (w: string) => /^[,.?!]/.test(w);

export const Subs: React.FC<{hide: [number, number][]}> = ({hide}) => {
  const t = useT();
  const c = CHUNKS.find((x) => t >= x.s - 0.12 && t < Math.max(x.e + 0.25, x.s + 0.9));
  if (!c || hide.some(([a, b]) => t >= a && t < b)) return null;
  const p = ramp(t, c.s - 0.12, c.s);
  return (
    <AbsoluteFill style={{justifyContent: "flex-end", alignItems: "center", paddingBottom: 46, pointerEvents: "none"}}>
      <div style={{fontFamily: SANS, fontSize: 38, fontWeight: 600, letterSpacing: "-0.01em", maxWidth: 1240, textAlign: "center", opacity: p,
        background: "rgba(0,0,0,.78)", padding: "7px 20px 9px", borderRadius: 10, transform: `translateY(${(1 - p) * 6}px)`}}>
        {c.words.map((w, i) => {
          const on = t >= w.s - 0.04;
          const now = on && t < (c.words[i + 1]?.s ?? c.e + 0.25);
          return (
            <span key={i} style={{color: now ? "#fff" : on ? "rgba(255,255,255,.86)" : "rgba(255,255,255,.42)",
              textShadow: now ? "0 0 18px rgba(255,255,255,.35)" : "none"}}>
              {i > 0 && !glue(w.w) ? " " : ""}{w.w}
            </span>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};
