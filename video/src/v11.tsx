// v11 scenes: real proof first (terminal replays, recorded outputs, dashboard screenshots), smooth animation only for theory.
import React from "react";
import {AbsoluteFill, Img, OffthreadVideo, staticFile, useCurrentFrame} from "remotion";
import {C, FPS, MONO, Rise, SANS, ramp, useT} from "./base";
import {SUBWORDS} from "./subs";
import snippets from "./data/snippets.json";

// ---------------------------------------------------------------- terminal replay ----
type Seg = {text: string; color?: string; dim?: boolean; bold?: boolean};
const ANSI: Record<string, string> = {"31": C.red, "91": C.red, "32": C.green, "92": C.green, "33": C.amber, "93": C.amber, "36": C.accent, "96": C.accent};
const parseAnsi = (s: string): Seg[] => {
  const out: Seg[] = [];
  let cur: Omit<Seg, "text"> = {};
  for (const part of s.split(/(\x1b\[[0-9;]*m)/)) {
    const m = part.match(/^\x1b\[([0-9;]*)m$/);
    if (!m) { if (part) out.push({text: part, ...cur}); continue; }
    for (const c of (m[1] || "0").split(";")) {
      if (c === "0" || c === "") cur = {};
      else if (c === "1") cur = {...cur, bold: true};
      else if (c === "2") cur = {...cur, dim: true};
      else if (c === "90") cur = {...cur, dim: true};
      else if (ANSI[c]) cur = {...cur, color: ANSI[c]};
    }
  }
  return out;
};
const plain = (s: string) => s.replace(/\x1b\[[0-9;]*m/g, "");
// a line with no colour code of its own still reads by its mark
const tint = (s: string) => (/✗/.test(s) ? C.red : /✓/.test(s) ? C.green : /\[SIMULATED\]/.test(s) ? C.amber : undefined);

export type TermData = {lines: [number, string][]};
/** a faithful replay: each recorded line appears at its own recorded second (at0 = the recorded second at the shot's first frame) */
export const Term: React.FC<{data: TermData; pick: number[]; at0: number; rate?: number; title: string; stamp: string; live?: boolean;
  hot?: number[]; top?: number; font?: number; strike?: number[]}> = ({data, pick, at0, rate = 1, title, stamp, live = true, hot = [], top = 150, font = 26, strike = []}) => {
  const t = useT();
  const now = at0 + t * rate;
  const open = ramp(t, 0, 0.35);
  return (
    <AbsoluteFill style={{background: C.bg}}>
      <div style={{position: "absolute", left: 150, right: 150, top, opacity: open, transform: `translateY(${(1 - open) * 18}px) scale(${0.985 + 0.015 * open})`,
        background: "#0a0a0b", border: `1px solid ${C.line}`, borderRadius: 14, overflow: "hidden", boxShadow: "0 30px 80px rgba(0,0,0,.6)"}}>
        <div style={{display: "flex", alignItems: "center", gap: 10, padding: "13px 18px", borderBottom: `1px solid ${C.line}`, background: "#111113"}}>
          {[0, 1, 2].map((i) => <span key={i} style={{width: 12, height: 12, borderRadius: 6, background: "rgba(255,255,255,.18)"}} />)}
          <span style={{fontFamily: MONO, fontSize: 18, color: C.mute, marginLeft: 14}}>{title}</span>
          <span style={{flex: 1}} />
          {rate !== 1 && <span style={{fontFamily: MONO, fontSize: 16, color: C.mute, border: `1px solid ${C.line}`, borderRadius: 6, padding: "3px 8px", marginRight: 10}}>replay {rate}×</span>}
          <span style={{fontFamily: MONO, fontSize: 16, letterSpacing: "0.05em", color: C.ink, display: "flex", alignItems: "center", gap: 8}}>
            <span style={{width: 8, height: 8, borderRadius: 4, background: live ? C.green : C.mute}} />{stamp}
          </span>
        </div>
        <div style={{padding: "22px 30px 26px", fontFamily: MONO, fontSize: font, lineHeight: 1.55, minHeight: 200}}>
          {pick.filter((i) => data.lines[i][0] <= now + 1e-6).map((i) => {
            const age = (now - data.lines[i][0]) / rate;
            const p = data.lines[i][0] <= at0 ? 1 : ramp(age, 0, 0.18);
            const raw = data.lines[i][1];
            const isHot = hot.includes(i);
            const flash = isHot ? 1 - ramp(age, 0.15, 1.6) : 0;
            const fallback = tint(plain(raw));
            return (
              <div key={i} style={{opacity: p, transform: `translateX(${(1 - p) * -10}px)`, whiteSpace: "pre-wrap", minHeight: font * 1.55,
                background: isHot ? `rgba(255,91,82,${0.08 + 0.22 * flash})` : "transparent", margin: "0 -12px", padding: "0 12px", borderRadius: 6,
                textDecoration: strike.includes(i) ? "line-through" : "none"}}>
                {parseAnsi(raw).map((g, k) => (
                  <span key={k} style={{color: g.color ?? fallback ?? (g.dim ? C.mute : C.ink), opacity: g.dim && !g.color ? 0.75 : 1, fontWeight: g.bold || isHot ? 650 : 400}}>{g.text}</span>
                ))}
              </div>
            );
          })}
          <span style={{display: "inline-block", width: font * 0.55, height: font * 1.1, background: C.ink, opacity: Math.floor(t * 2) % 2 ? 0 : 0.7, verticalAlign: "middle"}} />
        </div>
      </div>
    </AbsoluteFill>
  );
};

/** a recorded text file shown as a terminal `cat`: lines revealed on the voice (offsets in seconds into the shot) */
export const fileData = (lines: string[], times: number[]): TermData => ({lines: lines.map((s, i) => [times[i] ?? times[times.length - 1], s])});

// ---------------------------------------------------------------- screenshot with a camera ----
export type Box = [number, number, number, number]; // natural image px
type SZoom = {at: number; box?: Box; s?: number};
type SMark = {at: number; box: Box; color: string; label: string; below?: boolean};
export const Shot: React.FC<{src: string; w: number; h: number; zooms?: SZoom[]; marks?: SMark[]; cy?: number}> = ({src, w, h, zooms = [], marks = [], cy = 470}) => {
  const t = useT();
  const s0 = Math.min(1920 / w, 1080 / h), ox = (1920 - w * s0) / 2, oy = (1080 - h * s0) / 2;
  const cam = (z: SZoom) => {
    if (!z.box) return {s: 1, x: 960, y: 540};
    const [x, y, bw, bh] = z.box;
    const s = z.s ?? Math.min(2.2, Math.max(1.2, Math.min(1500 / (bw * s0), 640 / (bh * s0))));
    return {s, x: ox + (x + bw / 2) * s0, y: oy + (y + bh / 2) * s0};
  };
  let a = cam({at: 0}), b = a, p = 1;
  for (const z of zooms) {
    if (t < z.at) break;
    a = p < 1 ? mix(a, b, p) : b;
    b = cam(z);
    p = ramp(t, z.at, z.at + 1.0);
  }
  const c = mix(a, b, p);
  const aim = c.s > 1 ? cy : 540;
  const tx = clamp(960 - c.x * c.s, 1920 - 1920 * c.s, 0), ty = clamp(aim - c.y * c.s, 1080 - 1080 * c.s, 0);
  return (
    <AbsoluteFill style={{background: "#000", overflow: "hidden"}}>
      <div style={{position: "absolute", width: 1920, height: 1080, transformOrigin: "0 0", transform: `translate(${tx}px, ${ty}px) scale(${c.s})`}}>
        <Img src={staticFile(src)} style={{position: "absolute", left: ox, top: oy, width: w * s0, height: h * s0}} />
        {marks.map((m, i) => {
          const q = ramp(t, m.at, m.at + 0.35);
          if (q <= 0) return null;
          const [x, y, bw, bh] = m.box;
          return (
            <div key={i} style={{position: "absolute", left: ox + x * s0 - 6, top: oy + y * s0 - 6, width: bw * s0 + 12, height: bh * s0 + 12,
              border: `${3 / c.s}px solid ${m.color}`, borderRadius: 8, opacity: q, boxShadow: `0 0 0 ${2000}px rgba(0,0,0,${0.0 * q})`}}>
              <div style={{position: "absolute", left: -2, [m.below ? "top" : "bottom"]: "100%", margin: m.below ? "6px 0 0" : "0 0 6px", whiteSpace: "nowrap",
                fontFamily: MONO, fontSize: 22 / c.s, fontWeight: 650, color: "#000", background: m.color, padding: `${4 / c.s}px ${10 / c.s}px`, borderRadius: 6 / c.s}}>{m.label}</div>
            </div>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};
const mix = (a: {s: number; x: number; y: number}, b: typeof a, p: number) => ({s: a.s + (b.s - a.s) * p, x: a.x + (b.x - a.x) * p, y: a.y + (b.y - a.y) * p});
const clamp = (v: number, lo: number, hi: number) => Math.min(hi, Math.max(lo, v));

/** mono lines printed by a live API call, pinned bottom-right over a screenshot */
export const Fetched: React.FC<{at?: number; title: string; lines: [string, string?][]; bottom?: number}> = ({at = 0.6, title, lines, bottom = 250}) => {
  const p = ramp(useT(), at, at + 0.4);
  return (
    <div style={{position: "absolute", right: 56, bottom, opacity: p, transform: `translateY(${(1 - p) * 12}px)`, background: "rgba(8,8,9,.94)", border: `1px solid ${C.line}`,
      borderRadius: 12, padding: "14px 20px", fontFamily: MONO, fontSize: 21, lineHeight: 1.55, maxWidth: 1000, boxShadow: "0 20px 60px rgba(0,0,0,.6)"}}>
      <div style={{fontSize: 15, letterSpacing: "0.06em", color: C.mute, marginBottom: 6, display: "flex", gap: 8, alignItems: "center"}}>
        <span style={{width: 8, height: 8, borderRadius: 4, background: C.green}} />{title}
      </div>
      {lines.map(([s, col], i) => <div key={i} style={{color: col ?? C.ink, whiteSpace: "pre"}}>{s}</div>)}
    </div>
  );
};

// ---------------------------------------------------------------- overlays keyed to the voice ----
export type Finding = {id: string; name: string; sev: string; ev: string; loss: string; fix: string; from: number; to: number; lossAt: number};
/** top strip: which finding, how bad, what proves it. bottom: what the reference agent lost (red) and why Ringfence doesn't (green) */
export const FindingOverlay: React.FC<{items: Finding[]}> = ({items}) => {
  const t = useCurrentFrame() / FPS;
  const f = [...items].reverse().find((x) => t >= x.from && t < x.to);
  if (!f) return null;
  const pin = ramp(t, f.from, f.from + 0.4), pout = 1 - ramp(t, f.to - 0.25, f.to);
  const l = ramp(t, f.lossAt, f.lossAt + 0.3), g = ramp(t, f.lossAt + 1.4, f.lossAt + 1.8);
  const lossFlash = 1 - ramp(t, f.lossAt + 0.2, f.lossAt + 1.4);
  return (
    <>
      <div style={{position: "absolute", left: 36, top: 82, opacity: pin * pout, display: "flex", gap: 0, fontFamily: MONO, fontSize: 19, letterSpacing: "0.04em",
        background: "rgba(0,0,0,.85)", border: `1px solid ${C.line}`, borderRadius: 8, overflow: "hidden"}}>
        <span style={{padding: "8px 14px", background: C.ink, color: "#000", fontWeight: 700}}>{f.id}</span>
        <span style={{padding: "8px 16px", color: C.ink, fontWeight: 600}}>{f.name}</span>
        <span style={{padding: "8px 16px", color: C.mute, borderLeft: `1px solid ${C.line}`}}>SEVERITY <span style={{color: C.ink}}>{f.sev}</span></span>
        <span style={{padding: "8px 16px", color: C.mute, borderLeft: `1px solid ${C.line}`}}>EVIDENCE <span style={{color: C.ink}}>{f.ev}</span></span>
      </div>
      {l > 0 && (
        <div style={{position: "absolute", left: 290, right: 56, bottom: 128, opacity: pout, display: "grid", gap: 8}}>
          <div style={{opacity: l, transform: `translateY(${(1 - l) * 10}px) scale(${1 + 0.02 * lossFlash})`, transformOrigin: "left center", display: "flex", alignItems: "baseline", gap: 18,
            background: `rgba(30,6,6,${0.9})`, border: `1px solid ${C.red}66`, borderRadius: 10, padding: "10px 18px"}}>
            <span style={{fontFamily: MONO, fontSize: 16, letterSpacing: "0.08em", color: C.red, whiteSpace: "nowrap"}}>✗ REFERENCE AGENT</span>
            <span style={{fontFamily: SANS, fontSize: 32, fontWeight: 720, color: C.red, letterSpacing: "-0.01em"}}>{f.loss}</span>
          </div>
          <div style={{opacity: g, transform: `translateY(${(1 - g) * 10}px)`, display: "flex", alignItems: "baseline", gap: 18,
            background: "rgba(6,24,13,.92)", border: `1px solid ${C.green}55`, borderRadius: 10, padding: "9px 18px"}}>
            <span style={{fontFamily: MONO, fontSize: 16, letterSpacing: "0.08em", color: C.green, whiteSpace: "nowrap"}}>✓ RINGFENCE</span>
            <span style={{fontFamily: SANS, fontSize: 26, fontWeight: 600, color: C.green}}>{f.fix}</span>
          </div>
        </div>
      )}
    </>
  );
};

/** retest verdicts on the live app: the old loss struck through, the Ringfence result in green */
export type Verdict = {from: number; to: number; id: string; was: string; now: string};
export const RetestOverlay: React.FC<{items: Verdict[]}> = ({items}) => {
  const t = useCurrentFrame() / FPS;
  const v = items.find((x) => t >= x.from && t < x.to);
  if (!v) return null;
  const p = ramp(t, v.from + 0.3, v.from + 0.7), s = ramp(t, v.from + 0.9, v.from + 1.4), g = ramp(t, v.from + 1.2, v.from + 1.6), out = 1 - ramp(t, v.to - 0.2, v.to);
  return (
    <div style={{position: "absolute", left: 290, right: 56, bottom: 128, opacity: p * out, display: "grid", gap: 8}}>
      <div style={{display: "flex", alignItems: "baseline", gap: 16, fontFamily: MONO, fontSize: 22, color: C.red, opacity: 0.85, background: "rgba(0,0,0,.85)", borderRadius: 10, padding: "8px 18px"}}>
        <span style={{color: C.ink, fontWeight: 700}}>{v.id}</span>
        <span style={{position: "relative"}}>{v.was}<span style={{position: "absolute", left: 0, top: "55%", height: 3, width: `${s * 100}%`, background: C.red}} /></span>
      </div>
      <div style={{opacity: g, transform: `translateY(${(1 - g) * 10}px)`, display: "flex", alignItems: "baseline", gap: 16, background: "rgba(6,24,13,.94)",
        border: `1px solid ${C.green}66`, borderRadius: 10, padding: "10px 18px"}}>
        <span style={{fontFamily: MONO, fontSize: 16, letterSpacing: "0.08em", color: C.green}}>✓ RINGFENCE · LIVE APP</span>
        <span style={{fontFamily: SANS, fontSize: 32, fontWeight: 700, color: C.green}}>{v.now}</span>
      </div>
    </div>
  );
};

/** Goal → Plan → New info → Revised → Result, lit as the week unfolds */
export const Rubric: React.FC<{from: number; to: number; steps: [string, number][]}> = ({from, to, steps}) => {
  const t = useCurrentFrame() / FPS;
  if (t < from || t >= to) return null;
  const o = ramp(t, from, from + 0.4) * (1 - ramp(t, to - 0.3, to));
  return (
    <div style={{position: "absolute", left: 36, top: 82, opacity: o, display: "flex", alignItems: "center", gap: 10, fontFamily: MONO, fontSize: 18,
      letterSpacing: "0.05em", background: "rgba(0,0,0,.85)", border: `1px solid ${C.line}`, borderRadius: 999, padding: "8px 18px"}}>
      {steps.map(([s, at], i) => {
        const on = ramp(t, at, at + 0.35);
        const cur = t >= at && (i === steps.length - 1 || t < steps[i + 1][1]);
        return (
          <React.Fragment key={s}>
            {i > 0 && <span style={{color: C.dim}}>→</span>}
            <span style={{color: cur ? "#000" : on > 0.5 ? C.ink : C.dim, background: cur ? C.ink : "transparent", borderRadius: 999, padding: "2px 10px", fontWeight: cur ? 700 : 400}}>{s.toUpperCase()}</span>
          </React.Fragment>
        );
      })}
    </div>
  );
};

/** persistent corner tag: what world this is */
export const SandboxTag: React.FC<{from: number; to: number}> = ({from, to}) => {
  const t = useCurrentFrame() / FPS;
  if (t < from || t >= to) return null;
  return (
    <div style={{position: "absolute", right: 36, top: 28, fontFamily: MONO, fontSize: 16, letterSpacing: "0.07em", color: C.ink, background: "rgba(0,0,0,.8)",
      border: `1px solid ${C.line}`, borderRadius: 8, padding: "8px 14px", display: "flex", alignItems: "center", gap: 9, opacity: ramp(t, from, from + 0.5)}}>
      <span style={{width: 8, height: 8, borderRadius: 4, background: C.amber}} />AIRWALLEX SANDBOX · TEST MONEY
    </div>
  );
};

/** a small stamp under the corner tag: where this footage comes from */
export const Stamp: React.FC<{text: string; kind?: "live" | "sim" | "file"}> = ({text, kind = "live"}) => {
  const p = ramp(useT(), 0.2, 0.55);
  const dot = {live: C.green, sim: C.amber, file: C.mute}[kind];
  return (
    <div style={{position: "absolute", right: 36, top: 76, opacity: p, fontFamily: MONO, fontSize: 16, letterSpacing: "0.05em", color: C.ink, background: "rgba(0,0,0,.85)",
      border: `1px solid ${C.line}`, borderRadius: 8, padding: "8px 14px", display: "flex", alignItems: "center", gap: 9}}>
      <span style={{width: 8, height: 8, borderRadius: 4, background: dot}} />{text}
    </div>
  );
};

export const Chip: React.FC<{text: string}> = ({text}) => (
  <div style={{position: "absolute", right: 56, bottom: 140, fontFamily: MONO, fontSize: 18, color: C.ink, background: "rgba(0,0,0,.85)", border: `1px solid ${C.line}`,
    borderRadius: 8, padding: "8px 14px", opacity: ramp(useT(), 0.2, 0.5)}}>{text}</div>
);

// ---------------------------------------------------------------- face ----
/** the opening: his camera, full frame, cropped 16:9 clear of Loom's controls */
export const FaceFull: React.FC<{t0: number; notes?: [number, number, string, string][]}> = ({t0, notes = []}) => {
  const t = useT(), abs = t0 + t;
  return (
    <AbsoluteFill style={{background: C.bg, overflow: "hidden"}}>
      <OffthreadVideo src={staticFile("loom_cut.mp4")} startFrom={Math.round(t0 * FPS)} muted
        style={{position: "absolute", width: 1920, height: 798, left: 0, top: (1080 - 798) / 2}} />
      <div style={{position: "absolute", left: 72, bottom: 150, opacity: ramp(t, 0.6, 1.1) * (1 - ramp(t, 4.4, 4.9)), borderLeft: `3px solid ${C.ink}`, paddingLeft: 20,
        background: "rgba(0,0,0,.55)", padding: "12px 22px"}}>
        <div style={{fontFamily: SANS, fontSize: 44, fontWeight: 720, letterSpacing: "-0.02em"}}>Harsimar Singh</div>
        <div style={{fontFamily: MONO, fontSize: 20, color: C.mute, letterSpacing: "0.05em", marginTop: 4}}>RINGFENCE · AIRWALLEX AGENTIC BANKING HACKATHON · KIT 06</div>
      </div>
      {notes.map(([a, b, big, small], i) => {
        const p = ramp(abs, a, a + 0.5) * (1 - ramp(abs, b - 0.3, b));
        return p > 0 ? (
          <div key={i} style={{position: "absolute", right: 36, top: 300, width: 470, opacity: p, transform: `translateX(${(1 - p) * 24}px)`, background: "rgba(0,0,0,.72)",
            border: `1px solid ${C.line}`, borderRadius: 14, padding: "26px 30px"}}>
            <div style={{fontFamily: SANS, fontSize: 46, fontWeight: 740, letterSpacing: "-0.025em", lineHeight: 1.08}}>{big}</div>
            <div style={{fontFamily: SANS, fontSize: 26, color: C.mute, marginTop: 12, lineHeight: 1.3}}>{small}</div>
          </div>
        ) : null;
      })}
    </AbsoluteFill>
  );
};

// ---------------------------------------------------------------- type cards ----
/** his own sentence in big type, each word lit as he says it */
export const Karaoke: React.FC<{t0: number; from: number; to: number; size?: number; left?: number; width?: number; kicker?: string; red?: string[]}> =
  ({t0, from, to, size = 84, left, width = 1500, kicker, red = []}) => {
    const abs = t0 + useT();
    const ws = SUBWORDS.filter((w) => w.s >= from - 0.01 && w.s < to);
    return (
      <AbsoluteFill style={{background: C.bg, justifyContent: "center", alignItems: left === undefined ? "center" : "flex-start", paddingLeft: left}}>
        {kicker && <div style={{fontFamily: MONO, fontSize: 22, letterSpacing: "0.1em", color: C.mute, marginBottom: 28, width, textAlign: left === undefined ? "center" : "left"}}>{kicker}</div>}
        <div style={{width, fontFamily: SANS, fontSize: size, fontWeight: 740, letterSpacing: "-0.035em", lineHeight: 1.1, textAlign: left === undefined ? "center" : "left"}}>
          {ws.map((w, i) => {
            const on = ramp(abs, w.s - 0.05, w.s + 0.12);
            const isRed = red.some((r) => w.w.toLowerCase().startsWith(r));
            return <span key={i} style={{color: isRed && on > 0.5 ? C.ink : C.ink, opacity: 0.16 + 0.84 * on}}>{i ? " " : ""}{w.w}</span>;
          })}
        </div>
      </AbsoluteFill>
    );
  };

export const Statement: React.FC<{lines: [string, number][]; size?: number; sub?: string}> = ({lines, size = 96, sub}) => (
  <AbsoluteFill style={{background: C.bg, alignItems: "center", justifyContent: "center", flexDirection: "column", gap: 10}}>
    {lines.map(([s, a], i) => <Rise key={i} text={s} at={a} size={size} />)}
    {sub && <div style={{fontFamily: MONO, fontSize: 24, color: C.mute, marginTop: 30, letterSpacing: "0.05em", opacity: ramp(useT(), 0.8, 1.3)}}>{sub}</div>}
  </AbsoluteFill>
);

/** chapter opener: his face grows on the left (FaceBubble does that), the chapter on the right */
export const Opener: React.FC<{num: string; title: string; sub: string; pre?: [string, number]}> = ({num, title, sub, pre}) => {
  const t = useT();
  const a = pre ? pre[1] : 0;
  return (
    <AbsoluteFill style={{background: C.bg}}>
      {pre && (
        <div style={{position: "absolute", left: 960, top: 380, width: 860, opacity: ramp(t, 0.1, 0.5) * (1 - ramp(t, a - 0.3, a))}}>
          <Rise text={pre[0]} size={72} style={{justifyContent: "flex-start"}} />
        </div>
      )}
      <div style={{position: "absolute", left: 960, top: 360, width: 860, opacity: ramp(t, a, a + 0.3)}}>
        <div style={{fontFamily: MONO, fontSize: 26, letterSpacing: "0.12em", color: C.mute, marginBottom: 18}}>{num}</div>
        <Rise text={title} at={a + 0.05} size={104} style={{justifyContent: "flex-start"}} />
        <div style={{fontFamily: SANS, fontSize: 32, color: C.mute, marginTop: 22, opacity: ramp(t, a + 0.5, a + 0.9)}}>{sub}</div>
      </div>
    </AbsoluteFill>
  );
};

// ---------------------------------------------------------------- the setup ----
const ACCTS: [string, string, string][] = [
  ["Northwind Studio", "Employer A", "acct_Y5VX3QXWNSyiun0cbai15A"],
  ["Kestrel Labs", "Employer B", "acct_FG3wEt9HNg29C0zhpelKHg"],
  ["Harbour Foods", "Employer C", "acct_8bUTqZJePIG80-z_-xiutw"],
];
export const Setup: React.FC<{kids: number; ring: number}> = ({kids, ring}) => {
  const t = useT();
  const top = ramp(t, 0.1, 0.6);
  return (
    <AbsoluteFill style={{background: C.bg}}>
      <div style={{position: "absolute", left: 660, top: 170, width: 600, opacity: top, transform: `translateY(${(1 - top) * 16}px)`, border: `1px solid ${C.ink}`, borderRadius: 16,
        padding: "22px 28px", textAlign: "center", background: C.panel}}>
        <div style={{fontFamily: MONO, fontSize: 18, color: C.mute, letterSpacing: "0.08em"}}>PAYROLL PROVIDER · THE OPERATOR</div>
        <div style={{fontFamily: SANS, fontSize: 40, fontWeight: 720, marginTop: 6}}>Sandbox Business</div>
        <div style={{fontFamily: MONO, fontSize: 20, color: C.mute, marginTop: 6}}>acct_NIym7HZZOOOqBCE7F6LkMA</div>
      </div>
      <svg width={1920} height={1080} style={{position: "absolute"}}>
        {ACCTS.map((_, i) => {
          const p = ramp(t, kids + i * 0.15, kids + i * 0.15 + 0.6);
          const x = 360 + i * 600;
          return <path key={i} d={`M960 330 C 960 400, ${x} 380, ${x} 470`} stroke="rgba(255,255,255,.35)" strokeWidth={2} fill="none" strokeDasharray={600} strokeDashoffset={600 * (1 - p)} />;
        })}
      </svg>
      {ACCTS.map(([n, e, id], i) => {
        const p = ramp(t, kids + 0.3 + i * 0.15, kids + 0.8 + i * 0.15);
        const r = ramp(t, ring + i * 0.12, ring + 0.5 + i * 0.12);
        return (
          <div key={n} style={{position: "absolute", left: 360 + i * 600 - 260, top: 480, width: 520, opacity: p, transform: `translateY(${(1 - p) * 20}px)`}}>
            <div style={{border: `1px solid ${C.line}`, borderRadius: 16, padding: "22px 26px", background: C.panel, textAlign: "center",
              outline: `2px dashed rgba(255,255,255,${0.55 * r})`, outlineOffset: 10 + 6 * (1 - r)}}>
              <div style={{fontFamily: MONO, fontSize: 17, color: C.mute, letterSpacing: "0.08em"}}>CLIENT · {e.toUpperCase()}</div>
              <div style={{fontFamily: SANS, fontSize: 38, fontWeight: 720, marginTop: 4}}>{n}</div>
              <div style={{fontFamily: MONO, fontSize: 19, color: C.mute, marginTop: 6}}>{id}</div>
            </div>
            <div style={{fontFamily: MONO, fontSize: 19, color: C.ink, textAlign: "center", marginTop: 22, opacity: r}}>own account · own login</div>
          </div>
        );
      })}
    </AbsoluteFill>
  );
};

export const Guide: React.FC<{steps: number[]}> = ({steps}) => {
  const t = useT();
  const boxes = [["FRONTIER MODEL", "reads, decides, calls tools"], ["AIRWALLEX API AS TOOLS", "payees · transfers · balances"], ["A HUMAN APPROVES", "every payment"]];
  return (
    <AbsoluteFill style={{background: C.bg}}>
      <div style={{position: "absolute", top: 200, width: "100%", textAlign: "center", fontFamily: MONO, fontSize: 24, letterSpacing: "0.1em", color: C.mute, opacity: ramp(t, 0.1, 0.5)}}>
        THE PLATFORM GUIDE&apos;S PAYMENT AGENT
      </div>
      <div style={{position: "absolute", top: 400, left: 0, right: 0, display: "flex", justifyContent: "center", alignItems: "center", gap: 0}}>
        {boxes.map(([a, b], i) => {
          const p = ramp(t, steps[i], steps[i] + 0.55);
          return (
            <React.Fragment key={a}>
              {i > 0 && <div style={{width: 110, height: 2, background: C.ink, opacity: 0.5, transform: `scaleX(${p})`, transformOrigin: "left"}} />}
              <div style={{width: 430, opacity: p, transform: `translateY(${(1 - p) * 18}px)`, border: `1px solid ${i === 2 ? C.ink : C.line}`, borderRadius: 18, padding: "34px 30px",
                background: C.panel, textAlign: "center"}}>
                <div style={{fontFamily: MONO, fontSize: 22, letterSpacing: "0.08em"}}>{a}</div>
                <div style={{fontFamily: SANS, fontSize: 28, color: C.mute, marginTop: 12}}>{b}</div>
              </div>
            </React.Fragment>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};

export const Scope: React.FC<{card: number}> = ({card}) => {
  const t = useT();
  const p = ramp(t, card, card + 0.5);
  return (
    <AbsoluteFill style={{background: C.bg, alignItems: "center", justifyContent: "center", flexDirection: "column", gap: 8}}>
      <Rise text="I built that agent first," size={92} />
      <Rise text="then spent days trying to break it." at={0.5} size={92} />
      <div style={{marginTop: 60, opacity: p, transform: `translateY(${(1 - p) * 14}px)`, fontFamily: MONO, fontSize: 26, border: `1px solid ${C.line}`, borderRadius: 12,
        padding: "18px 28px", display: "flex", gap: 22, alignItems: "center", background: C.panel}}>
        <span style={{color: C.mute, letterSpacing: "0.1em"}}>SCOPE</span>
        <span>Sandbox only · own 4 accounts · ≤ GBP/EUR 5 · every transfer cancelled or reversed</span>
      </div>
    </AbsoluteFill>
  );
};

// ---------------------------------------------------------------- theory: findings ----
const card: React.CSSProperties = {background: C.panel, border: `1px solid ${C.line}`, borderRadius: 18, padding: "28px 34px"};
const Row: React.FC<{k: string; v: string; p: number; tick?: number; dim?: boolean}> = ({k, v, p, tick = 0, dim}) => (
  <div style={{display: "flex", alignItems: "baseline", gap: 18, padding: "12px 0", borderTop: `1px solid ${C.line}`, opacity: p}}>
    <span style={{width: 210, fontFamily: MONO, fontSize: 20, color: C.mute, letterSpacing: "0.05em"}}>{k}</span>
    <span style={{flex: 1, fontFamily: SANS, fontSize: 34, fontWeight: 600, color: dim ? C.dim : C.ink}}>{v}</span>
    <span style={{fontFamily: SANS, fontSize: 32, opacity: tick, transform: `scale(${0.6 + 0.4 * tick})`}}>✓</span>
  </div>
);

/** F1, what the approver sees: every field checks out */
export const Approve: React.FC<{ticks: number[]; yes: number}> = ({ticks, yes}) => {
  const t = useT();
  const y = ramp(t, yes, yes + 0.35);
  return (
    <AbsoluteFill style={{background: C.bg, alignItems: "center", justifyContent: "center"}}>
      <div style={{...card, width: 900, opacity: ramp(t, 0, 0.4)}}>
        <div style={{fontFamily: MONO, fontSize: 20, color: C.mute, letterSpacing: "0.08em", marginBottom: 14}}>APPROVAL REQUEST · REFERENCE AGENT</div>
        <Row k="PAYEE" v="Ben" p={1} tick={ramp(t, ticks[0], ticks[0] + 0.25)} />
        <Row k="AMOUNT" v="GBP 2.00" p={1} tick={ramp(t, ticks[1], ticks[1] + 0.25)} />
        <Row k="PAYEE ID" v="92f13a55…" p={1} tick={ramp(t, ticks[2], ticks[2] + 0.25)} />
        <Row k="BANK ACCOUNT" v="not on the card" p={1} dim />
        <div style={{marginTop: 26, display: "flex", justifyContent: "flex-end"}}>
          <div style={{fontFamily: SANS, fontSize: 30, fontWeight: 700, borderRadius: 12, padding: "14px 34px", border: `1px solid ${C.ink}`,
            background: y > 0.5 ? C.ink : "transparent", color: y > 0.5 ? "#000" : C.ink, transform: `scale(${1 - 0.05 * Math.sin(Math.PI * y)})`}}>{y > 0.5 ? "Approved ✓" : "Approve"}</div>
        </div>
      </div>
    </AbsoluteFill>
  );
};

/** the payee stays saved: every later run follows the same pointer, and nothing says so */
export const RunsLand: React.FC<{runs: number; quiet: number}> = ({runs, quiet}) => {
  const t = useT();
  return (
    <AbsoluteFill style={{background: C.bg}}>
      <div style={{position: "absolute", top: 160, width: "100%", textAlign: "center", fontFamily: MONO, fontSize: 20, letterSpacing: "0.1em", color: C.mute}}>ILLUSTRATION · THE SAVED PAYEE</div>
      <div style={{...card, position: "absolute", left: 220, top: 330, width: 460, opacity: ramp(t, 0, 0.4)}}>
        <div style={{fontFamily: MONO, fontSize: 18, color: C.mute, letterSpacing: "0.08em"}}>SAVED PAYEE</div>
        <div style={{fontFamily: SANS, fontSize: 44, fontWeight: 720, marginTop: 6}}>Ben</div>
        <div style={{fontFamily: MONO, fontSize: 22, color: C.mute, marginTop: 4}}>92f13a55…</div>
        <div style={{fontFamily: MONO, fontSize: 24, color: C.red, marginTop: 14}}>→ bank ..9901 · sort 200000</div>
      </div>
      {["Next payroll run", "The run after", "And the next"].map((s, i) => {
        const a = runs + i * 0.7, p = ramp(t, a, a + 0.5), d = ramp(t, a + 0.2, a + 0.8);
        return (
          <div key={s} style={{position: "absolute", left: 800, top: 300 + i * 120, width: 900, display: "flex", alignItems: "center", gap: 24, opacity: p}}>
            <span style={{fontFamily: SANS, fontSize: 34, fontWeight: 600, width: 330}}>{s}</span>
            <div style={{flex: 1, height: 2, background: C.red, transform: `scaleX(${d})`, transformOrigin: "left"}} />
            <span style={{fontFamily: MONO, fontSize: 30, color: C.red, opacity: d}}>..9901</span>
          </div>
        );
      })}
      <div style={{position: "absolute", left: 800, top: 680, fontFamily: MONO, fontSize: 28, opacity: ramp(t, quiet, quiet + 0.4), color: C.ink, border: `1px solid ${C.line}`,
        borderRadius: 10, padding: "12px 20px"}}>alerts fired: 0</div>
    </AbsoluteFill>
  );
};

/** theory: the approval holds a label; the money follows whatever the label points to */
export const LabelPointer: React.FC<{swap: number; pay: number}> = ({swap, pay}) => {
  const t = useT();
  const sw = ramp(t, swap, swap + 0.7), m = ramp(t, pay, pay + 1.1);
  const x0 = 760, y0 = 520, a = {x: 1200, y: 380}, b = {x: 1200, y: 680};
  const tx = a.x + (b.x - a.x) * sw, ty = a.y + (b.y - a.y) * sw;
  const dot = {x: x0 + (tx - x0) * m, y: y0 + (ty - y0) * m};
  return (
    <AbsoluteFill style={{background: C.bg}}>
      <div style={{position: "absolute", top: 150, width: "100%", textAlign: "center"}}>
        <Rise text="The approval checks a label." size={64} />
        <div style={{height: 10}} />
        <Rise text="The money follows whatever it points to." at={swap} size={64} />
      </div>
      <div style={{...card, position: "absolute", left: 300, top: 420, width: 460}}>
        <div style={{fontFamily: MONO, fontSize: 18, color: C.mute, letterSpacing: "0.08em"}}>APPROVED</div>
        <div style={{fontFamily: SANS, fontSize: 46, fontWeight: 740, marginTop: 6}}>Ben · GBP 2.00 ✓</div>
        <div style={{fontFamily: MONO, fontSize: 20, color: C.mute, marginTop: 6}}>payee 92f13a55…</div>
      </div>
      <svg width={1920} height={1080} style={{position: "absolute"}}>
        <defs><marker id="ah" markerWidth="10" markerHeight="10" refX="8" refY="5" orient="auto"><path d="M0,0 L10,5 L0,10 z" fill={sw > 0.5 ? C.red : C.ink} /></marker></defs>
        <line x1={x0} y1={y0} x2={tx - 10} y2={ty} stroke={sw > 0.5 ? C.red : C.ink} strokeWidth={3} markerEnd="url(#ah)" />
        {m > 0 && m < 1 && <circle cx={dot.x} cy={dot.y} r={12} fill={C.red} />}
      </svg>
      {[[a, "..0002", "the account he checked", 1 - sw], [b, "..9901", "swapped in", sw]].map(([pt, n, s, on]: any, i) => (
        <div key={i} style={{position: "absolute", left: pt.x, top: pt.y - 60, width: 420, ...card, padding: "20px 26px",
          borderColor: i === 1 && on > 0.5 ? C.red : C.line, opacity: 0.35 + 0.65 * on}}>
          <div style={{fontFamily: MONO, fontSize: 40, color: i === 1 && on > 0.5 ? C.red : C.ink}}>{n}</div>
          <div style={{fontFamily: SANS, fontSize: 24, color: C.mute}}>{s}</div>
          {i === 1 && <div style={{fontFamily: MONO, fontSize: 24, color: C.red, marginTop: 6, opacity: ramp(t, pay + 1.0, pay + 1.3)}}>GBP 2.00 paid here</div>}
        </div>
      ))}
    </AbsoluteFill>
  );
};

/** theory: a lost reply plus a fresh request ID = a second payment */
export const RetryTwice: React.FC<{lost: number; again: number}> = ({lost, again}) => {
  const t = useT();
  const one = ramp(t, 0.2, 0.8), l = ramp(t, lost, lost + 0.5), two = ramp(t, again, again + 0.6);
  const moved = two > 0.9 ? 2 : one > 0.9 ? 1 : 0;
  const lane = (y: number, label: string, p: number, col: string, dashed = false, back = false) => (
    <div style={{position: "absolute", left: 520, top: y, width: 880, opacity: p}}>
      <div style={{height: 3, background: dashed ? "transparent" : col, borderTop: dashed ? `3px dashed ${col}` : undefined, transform: `scaleX(${p})`, transformOrigin: back ? "right" : "left"}} />
      <div style={{fontFamily: MONO, fontSize: 24, color: col, marginTop: 12, textAlign: back ? "right" : "left"}}>{label}</div>
    </div>
  );
  return (
    <AbsoluteFill style={{background: C.bg}}>
      <div style={{position: "absolute", top: 150, width: "100%", textAlign: "center", fontFamily: MONO, fontSize: 20, letterSpacing: "0.1em", color: C.mute}}>ILLUSTRATION · A RETRY WITH A NEW ID</div>
      {[["AGENT", 200], ["AIRWALLEX", 1420]].map(([s, x]: any) => (
        <div key={s} style={{...card, position: "absolute", left: x, top: 300, width: 300, height: 420, display: "flex", alignItems: "flex-start", justifyContent: "center"}}>
          <span style={{fontFamily: MONO, fontSize: 24, letterSpacing: "0.1em"}}>{s}</span>
        </div>
      ))}
      {lane(380, "pay GBP 1 · request ID  A", one, C.ink)}
      {lane(480, "reply lost ✗", l, C.mute, true, true)}
      {lane(580, "pay GBP 1 · request ID  B  (new)", two, C.red)}
      <div style={{position: "absolute", left: 1440, top: 560, width: 260, textAlign: "center"}}>
        <div style={{fontFamily: MONO, fontSize: 18, color: C.mute}}>MOVED</div>
        <div style={{fontFamily: SANS, fontSize: 64, fontWeight: 760, color: moved === 2 ? C.red : C.ink}}>GBP {moved}</div>
      </div>
    </AbsoluteFill>
  );
};

/** three places the money path can be bent; the active one lit */
const PATH: [string, [string, string][]][] = [
  ["WHO IT'S PAID TO", [["F1", "Approval swap"], ["F2", "Bank change from an email"]]],
  ["HOW IT'S SENT", [["F5", "Batch payroll"], ["F3", "SDK shares one login"], ["F4", "Retry pays twice"]]],
  ["HOW THE AGENT CHECKS", [["F6", "Payment list repeats"], ["F7", "SDK retry drops its filter"]]],
];
export const PathMap: React.FC<{lit: number; done: number}> = ({lit, done}) => {
  const t = useT();
  return (
    <AbsoluteFill style={{background: C.bg}}>
      <div style={{position: "absolute", top: 170, width: "100%", textAlign: "center"}}><Rise text="The same weakness, across the stack." size={64} /></div>
      <div style={{position: "absolute", top: 380, left: 160, right: 160, display: "flex", gap: 40}}>
        {PATH.map(([h, rows], i) => {
          const on = i === lit, p = ramp(t, 0.3 + i * 0.15, 0.8 + i * 0.15);
          return (
            <div key={h} style={{flex: 1, ...card, opacity: p * (on ? 1 : i < done ? 0.55 : 0.4), borderColor: on ? C.ink : C.line, transform: `translateY(${(1 - p) * 20}px)`}}>
              <div style={{fontFamily: MONO, fontSize: 21, letterSpacing: "0.1em", color: on ? C.ink : C.mute, marginBottom: 18}}>{h}</div>
              {rows.map(([id, n]) => (
                <div key={id} style={{display: "flex", gap: 16, alignItems: "baseline", padding: "10px 0", borderTop: `1px solid ${C.line}`}}>
                  <span style={{fontFamily: MONO, fontSize: 22, color: C.red}}>{id}</span>
                  <span style={{fontFamily: SANS, fontSize: 30, fontWeight: 600}}>{n}</span>
                  {i < done && <span style={{marginLeft: "auto", fontFamily: MONO, fontSize: 20, color: C.mute}}>shown</span>}
                </div>
              ))}
            </div>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};

/** Airwallex's own isolation: 12 cross-client logins, 12 refusals */
const WHO = ["Northwind", "Kestrel", "Harbour", "Platform"];
export const IsoGrid: React.FC<{from?: number}> = ({from = 0.2}) => {
  const t = useT();
  const cells = WHO.flatMap((a) => WHO.filter((b) => b !== a).map((b) => [a, b]));
  return (
    <AbsoluteFill style={{background: C.bg}}>
      <div style={{position: "absolute", top: 150, width: "100%", textAlign: "center", fontFamily: MONO, fontSize: 22, letterSpacing: "0.08em", color: C.mute}}>
        ONE CLIENT&apos;S LOGIN → ANOTHER ACCOUNT · LIVE · AIRWALLEX SANDBOX
      </div>
      <div style={{position: "absolute", top: 230, left: 260, right: 260, display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 16}}>
        {cells.map(([a, b], i) => {
          const p = ramp(t, from + i * 0.09, from + i * 0.09 + 0.35);
          return (
            <div key={i} style={{opacity: p, transform: `scale(${0.94 + 0.06 * p})`, border: `1px solid ${C.green}55`, borderRadius: 12, padding: "16px 18px", background: "rgba(6,24,13,.6)"}}>
              <div style={{fontFamily: SANS, fontSize: 24, fontWeight: 600}}>{a} → {b}</div>
              <div style={{fontFamily: MONO, fontSize: 20, color: C.green, marginTop: 4}}>401 credentials_invalid</div>
            </div>
          );
        })}
      </div>
      <div style={{position: "absolute", top: 720, width: "100%", textAlign: "center", fontFamily: SANS, fontSize: 52, fontWeight: 740, color: C.green,
        opacity: ramp(t, from + 1.3, from + 1.7)}}>Isolation held · 12 / 12 blocked</div>
    </AbsoluteFill>
  );
};

// ---------------------------------------------------------------- the board ----
type BRow = [string, string, string, string, string]; // id, name, severity, what was lost, Ringfence
export const BOARD: BRow[] = [
  ["F1", "Approval swap", "High", "paid ..9901 · 3/3", "bank details signed into the approval → HELD"],
  ["F2", "Bank change from an email", "High", "paid ..9901 · 5/5", "quarantined until a phone callback"],
  ["F5", "Batch payroll", "Medium", "booked ..9901 · can't cancel", "no batches · details inline"],
  ["F3", "SDK shares one login", "High", "A's payment on B's login", "own login per client, set by code"],
  ["F4", "Retry pays twice", "Medium", "GBP 2 moved for GBP 1", "ID fixed before the first try → once"],
  ["F6", "Payment list repeats", "Low", "122 look unpaid → paid again", "cursor paging → 222 of 222"],
  ["F7", "SDK retry drops its filter", "Low", "'it landed' → never paid", "request_id matched on every item"],
];
export const Board: React.FC<{title: string; fix?: number; fixStep?: number; head?: string; foot?: string}> = ({title, fix, fixStep = 0.25, head = "RINGFENCE", foot}) => {
  const t = useT();
  return (
    <AbsoluteFill style={{background: C.bg}}>
      <div style={{position: "absolute", top: 120, left: 160, right: 160}}>
        <div style={{fontFamily: SANS, fontSize: 54, fontWeight: 740, letterSpacing: "-0.03em", marginBottom: 26, opacity: ramp(t, 0, 0.4)}}>{title}</div>
        <div style={{display: "grid", gridTemplateColumns: "80px 1fr 130px 1fr 1fr", fontFamily: MONO, fontSize: 17, letterSpacing: "0.08em", color: C.mute, padding: "0 0 10px"}}>
          <span>ID</span><span>FINDING</span><span>SEVERITY</span><span>REFERENCE AGENT</span><span>{head}</span>
        </div>
        {BOARD.map((r, i) => {
          const p = ramp(t, 0.15 + i * 0.07, 0.5 + i * 0.07);
          const g = fix === undefined ? 0 : ramp(t, fix + i * fixStep, fix + i * fixStep + 0.35);
          return (
            <div key={r[0]} style={{display: "grid", gridTemplateColumns: "80px 1fr 130px 1fr 1fr", alignItems: "baseline", padding: "13px 0", borderTop: `1px solid ${C.line}`,
              opacity: p, transform: `translateY(${(1 - p) * 10}px)`}}>
              <span style={{fontFamily: MONO, fontSize: 24, fontWeight: 700}}>{r[0]}</span>
              <span style={{fontFamily: SANS, fontSize: 28, fontWeight: 600}}>{r[1]}</span>
              <span style={{fontFamily: MONO, fontSize: 20, color: C.mute}}>{r[2]}</span>
              <span style={{fontFamily: MONO, fontSize: 21, color: C.red}}>{r[3]}</span>
              <span style={{fontFamily: MONO, fontSize: 21, color: C.green, opacity: g, transform: `translateX(${(1 - g) * 12}px)`}}>✓ {r[4]}</span>
            </div>
          );
        })}
        <div style={{display: "grid", gridTemplateColumns: "80px 1fr 130px 1fr 1fr", alignItems: "baseline", padding: "13px 0", borderTop: `1px solid ${C.line}`, opacity: ramp(t, 0.8, 1.2)}}>
          <span />
          <span style={{fontFamily: SANS, fontSize: 28, fontWeight: 600}}>Airwallex isolation</span>
          <span />
          <span style={{fontFamily: MONO, fontSize: 21, color: C.green}}>held · 12/12 blocked</span>
          <span />
        </div>
        {foot && <div style={{fontFamily: MONO, fontSize: 26, marginTop: 30, opacity: ramp(t, 1.2, 1.6)}}>{foot}</div>}
      </div>
    </AbsoluteFill>
  );
};

// ---------------------------------------------------------------- code ----
type Snip = {file: string; start: number; lines: string[]; hl: number[]};
const SN = snippets as Record<string, Snip>;
const color = (s: string) => {
  const out: React.ReactNode[] = [];
  const re = /(#.*$|"""[^"]*"""|"[^"]*"|'[^']*'|\b(?:def|return|if|else|elif|for|in|not|None|class|from|import|try|except|and|or|is)\b|\bDecimal\b|x-login-as)/g;
  let last = 0, m: RegExpExecArray | null;
  while ((m = re.exec(s))) {
    if (m.index > last) out.push(s.slice(last, m.index));
    const g = m[0];
    const st: React.CSSProperties = g.startsWith("#") ? {color: C.dim} : /^["']/.test(g) ? {color: "#c6d0f5"} : g === "Decimal" || g === "x-login-as" ? {color: C.ink, fontWeight: 700} : {color: C.mute};
    out.push(<span key={m.index} style={st}>{g}</span>);
    last = m.index + g.length;
  }
  out.push(s.slice(last));
  return out;
};
export const Code: React.FC<{k: string; caption: string; sub?: string; hlAt?: number; font?: number}> = ({k, caption, sub, hlAt = 0.6, font = 24}) => {
  const t = useT();
  const sn = SN[k];
  const strip = Math.min(...sn.lines.filter((l) => l.trim()).map((l) => l.match(/^ */)![0].length));
  return (
    <AbsoluteFill style={{background: C.bg}}>
      <div style={{position: "absolute", top: 120, left: 150, right: 150}}>
        <Rise text={caption} size={52} style={{justifyContent: "flex-start"}} />
        {sub && <div style={{fontFamily: SANS, fontSize: 28, color: C.mute, marginTop: 10, opacity: ramp(t, 0.4, 0.8)}}>{sub}</div>}
      </div>
      <div style={{position: "absolute", top: sub ? 300 : 250, left: 150, right: 150, background: "#0a0a0b", border: `1px solid ${C.line}`, borderRadius: 14, overflow: "hidden",
        opacity: ramp(t, 0.15, 0.5), transform: `translateY(${(1 - ramp(t, 0.15, 0.6)) * 16}px)`}}>
        <div style={{display: "flex", alignItems: "center", gap: 12, padding: "11px 18px", background: "#111113", borderBottom: `1px solid ${C.line}`, fontFamily: MONO, fontSize: 18}}>
          <span style={{color: C.ink}}>{sn.file}</span><span style={{color: C.dim}}>:{sn.start}</span>
          <span style={{flex: 1}} /><span style={{color: C.mute, fontSize: 15, letterSpacing: "0.06em"}}>FROM THE REPO · RINGFENCE</span>
        </div>
        <div style={{padding: "16px 0", fontFamily: MONO, fontSize: font, lineHeight: 1.6}}>
          {sn.lines.map((l, i) => {
            const n = sn.start + i, on = sn.hl.includes(n) ? ramp(t, hlAt + sn.hl.indexOf(n) * 0.12, hlAt + 0.35 + sn.hl.indexOf(n) * 0.12) : 0;
            return (
              <div key={i} style={{display: "flex", whiteSpace: "pre", background: `rgba(94,227,143,${0.1 * on})`, boxShadow: on ? `inset 3px 0 0 ${C.green}` : "none"}}>
                <span style={{width: 76, textAlign: "right", paddingRight: 22, color: C.dim}}>{n}</span>
                <span style={{opacity: sn.hl.length && !on ? 0.62 : 1}}>{color(l.slice(strip))}</span>
              </div>
            );
          })}
        </div>
      </div>
    </AbsoluteFill>
  );
};
