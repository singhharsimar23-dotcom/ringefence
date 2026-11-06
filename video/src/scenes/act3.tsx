// Act 3: why the Metal mandate exists. Real coverage (all published 3 Nov 2026), then the limit no stolen key can get around.
import React from "react";
import {AbsoluteFill, Img, staticFile} from "remotion";
import {C, In, MONO, Receipt, SANS, at, ramp, useT} from "../base";
import {OVER, POISON, PULL, short} from "../facts";
import {Tag} from "../xray";

type HL = {x: number; y: number; w: number; h: number; at: number}; // in source-image pixels
const Paper: React.FC<{src: string; iw: number; w: number; t0: number; enter: number; x: number; y: number; rot: number; hl: HL[]; label: string; dim?: number}> =
  ({src, iw, w, t0, enter, x, y, rot, hl, label, dim = 99}) => {
    const t = useT();
    const p = ramp(t, enter - t0, enter - t0 + 0.7);
    const d = ramp(t, dim - t0, dim - t0 + 0.6);
    const k = w / iw;
    return (
      <div style={{position: "absolute", left: x, top: y, width: w, opacity: p * (1 - 0.65 * d),
        transform: `translateY(${(1 - p) * 70}px) rotate(${rot}deg) scale(${1 - 0.04 * d})`, transformOrigin: "50% 50%"}}>
        <div style={{position: "relative", background: "#fff", borderRadius: 6, overflow: "hidden", boxShadow: "0 30px 80px rgba(0,0,0,.6)"}}>
          <Img src={staticFile(src)} style={{width: w, display: "block"}} />
          {hl.map((h, i) => {
            const q = ramp(t, h.at - t0, h.at - t0 + 0.45);
            return <div key={i} style={{position: "absolute", left: h.x * k, top: h.y * k, width: h.w * k * q, height: h.h * k, background: "#ffd84a", mixBlendMode: "multiply"}} />;
          })}
        </div>
        <div style={{fontFamily: MONO, fontSize: 18, color: C.mute, marginTop: 14, letterSpacing: "0.04em"}}>{label}</div>
      </div>
    );
  };

export const Evidence: React.FC<{t0: number}> = ({t0}) => {
  const t = useT();
  const tl = at("Once they were in") - t0;
  return (
    <AbsoluteFill style={{background: C.bg}}>
      <Paper src="news/guardian_h.png" iw={2300} w={1180} t0={t0} enter={t0} x={120} y={110} rot={-1.2} label="THE GUARDIAN · 3 NOV 2026"
        hl={[{x: 857, y: 483, w: 205, h: 76, at: at("billion gone")}]} dim={at("fake job")} />
      <Paper src="news/bbc_h.png" iw={1600} w={980} t0={t0} enter={at("fake job") - 0.35} x={820} y={300} rot={1.0} label="BBC NEWS · 3 NOV 2026"
        hl={[{x: 600, y: 48, w: 685, h: 80, at: at("fake job") + 0.1}]} dim={at("ended with")} />
      <Paper src="news/coindesk_h.png" iw={1440} w={1000} t0={t0} enter={at("ended with") - 0.3} x={300} y={420} rot={-0.6} label="COINDESK · 3 NOV 2026"
        hl={[{x: 458, y: 393, w: 478, h: 50, at: at("inside the system")}]} dim={at("Once they were in")} />
      {/* the window CoinDesk reports: funds leaving 20:05 UTC 29 Oct, contained 00:10 UTC 30 Oct */}
      <AbsoluteFill style={{justifyContent: "center", alignItems: "center", opacity: ramp(t, tl, tl + 0.5), background: "rgba(0,0,0,.93)"}}>
        <div style={{width: 1300}}>
          <div style={{display: "flex", justifyContent: "space-between", fontFamily: MONO, fontSize: 26, color: C.mute}}>
            <span>20:05 UTC · 29 Oct</span><span>00:10 UTC · 30 Oct</span>
          </div>
          <div style={{height: 10, background: C.line, borderRadius: 5, margin: "22px 0 30px", overflow: "hidden"}}>
            <div style={{height: "100%", width: `${ramp(t, tl + 0.4, tl + 3.6, 0, 100, (x) => x)}%`, background: C.red}} />
          </div>
          <div style={{fontFamily: SANS, fontSize: 64, fontWeight: 760, letterSpacing: "-0.03em", color: C.ink}}>
            ≈ 4 hours <span style={{color: C.mute, fontWeight: 600}}>before it was contained.</span>
          </div>
        </div>
      </AbsoluteFill>
    </AbsoluteFill>
  );
};

const SETTLEMENT = "0x4b4dFF14d5cb002036A8ac2201F038A3f2654b00"; // the Ringfence settlement wallet (fixed across runs)

// ---- the mandate: each term lands on the phrase that says it, with the real values from the live run ----
const Term: React.FC<{at: number; k: string; v: string; note: string}> = ({at: a, k, v, note}) => {
  const p = ramp(useT(), a, a + 0.5);
  return (
    <>
      <div style={{fontFamily: MONO, fontSize: 24, color: C.mute, opacity: p, letterSpacing: "0.08em"}}>{k}</div>
      <div style={{fontFamily: MONO, fontSize: 50, fontWeight: 600, color: C.ink, opacity: p, transform: `translateX(${(1 - p) * 16}px)`}}>{v}</div>
      <div style={{fontFamily: MONO, fontSize: 22, color: C.mute, opacity: ramp(useT(), a + 0.3, a + 0.8)}}>{note}</div>
    </>
  );
};

export const Mandate: React.FC<{t0: number}> = ({t0}) => {
  const r = (ph: string) => at(ph, 112) - t0;
  return (
    <AbsoluteFill style={{background: C.bg, justifyContent: "center", paddingLeft: 170}}>
      <In at={r("signs a rule")}>
        <div style={{fontFamily: MONO, fontSize: 20, letterSpacing: "0.14em", color: C.mute}}>MANDATE {short(PULL.mandate, 10, 6)} · SIGNED BY HARBOUR ON METAL</div>
      </In>
      <div style={{display: "grid", gridTemplateColumns: "190px 520px auto", columnGap: 40, rowGap: 34, alignItems: "baseline", marginTop: 56}}>
        <Term at={r("exactly one")} k="COUNT" v="1 pull" note="a second pull is refused" />
        <Term at={r("missing")} k="CAP" v={`${PULL.usdz} USDZ`} note={`= AUD ${PULL.aud}, exactly what Harbour is short`} />
        <Term at={r("only into our")} k="PAYEE" v={short(POISON?.real ?? SETTLEMENT, 8, 6)} note="the Ringfence settlement wallet, nobody else" />
        <Term at={r("next hour")} k="EXPIRES" v="3600 s" note="then the mandate is dead" />
      </div>
      <Tag at={r("next hour") + 1.3} style={{marginTop: 64, width: 1300}}>VRP-style mandate · count, cap, payee, expiry · enforced by the chain, not by my server</Tag>
      <Receipt kind="chain" text={`bind tx ${short(PULL.bind_tx)}`} at={r("signs a rule") + 0.4} />
    </AbsoluteFill>
  );
};

// ---- one coin more ----
export const Overpull: React.FC<{t0: number}> = ({t0}) => {
  const t = useT();
  const a = at("one coin more", 130) - t0;
  const b = at("refused", a + t0) - t0;
  return (
    <AbsoluteFill style={{background: C.bg, justifyContent: "center", paddingLeft: 260}}>
      <div style={{display: "grid", gridTemplateColumns: "260px auto", rowGap: 18, fontFamily: MONO, alignItems: "baseline"}}>
        <div style={{fontSize: 26, color: C.mute}}>MANDATE CAP</div><div style={{fontSize: 64, color: C.mute}}>{PULL.usdz} USDZ</div>
        <div style={{fontSize: 26, color: C.mute, opacity: ramp(t, a, a + 0.4)}}>ASKED FOR</div>
        <div style={{fontSize: 64, color: C.ink, opacity: ramp(t, a, a + 0.4)}}>{OVER.usdz} USDZ <span style={{color: C.amber, fontSize: 40}}>+1.00</span></div>
      </div>
      <div style={{fontFamily: MONO, fontSize: 56, fontWeight: 700, color: C.red, marginTop: 60, opacity: ramp(t, b, b + 0.3), transform: `scale(${1.06 - 0.06 * ramp(t, b, b + 0.4)})`, transformOrigin: "0 50%"}}>
        REFUSED · mandate_cap_exceeded
      </div>
      <Receipt kind="chain" text={`tx ${short(OVER.tx)}`} at={b + 0.3} />
    </AbsoluteFill>
  );
};

// ---- the lookalike wallet: same first four, same last four ----
const Addr: React.FC<{s: string; vs: string; red: number}> = ({s, vs, red}) => (
  <span>{s.split("").map((ch, i) => {
    const same = ch.toLowerCase() === (vs[i] ?? "").toLowerCase();
    return <span key={i} style={{color: same ? C.ink : `rgba(255,91,82,${0.25 + 0.75 * red})`, opacity: same ? 1 : 0.55 + 0.45 * red}}>{ch}</span>;
  })}</span>
);

export const Poison: React.FC<{t0: number}> = ({t0}) => {
  const t = useT();
  const real = POISON?.real ?? SETTLEMENT, fake = POISON?.to ?? "";
  const a = at("My code catches", 136) - t0, b = at("refuses it anyway", 136) - t0;
  const diff = ramp(t, 1.6, 2.4);
  return (
    <AbsoluteFill style={{background: C.bg, justifyContent: "center", paddingLeft: 170}}>
      <div style={{display: "grid", gridTemplateColumns: "200px auto", rowGap: 22, fontFamily: MONO, fontSize: 46, alignItems: "baseline"}}>
        <div style={{fontSize: 24, color: C.mute}}>OUR WALLET</div><div><Addr s={real} vs={real} red={0} /></div>
        <div style={{fontSize: 24, color: C.mute, opacity: ramp(t, 0.5, 0.9)}}>LOOKALIKE</div>
        <div style={{opacity: ramp(t, 0.5, 0.9)}}><Addr s={fake} vs={real} red={diff} /></div>
      </div>
      <div style={{fontFamily: MONO, fontSize: 24, color: C.mute, marginTop: 26, opacity: ramp(t, 2.2, 2.7)}}>address poisoning · same first four, same last four · people check the ends</div>
      <div style={{display: "grid", gridTemplateColumns: "60px 300px auto", rowGap: 20, marginTop: 70, fontFamily: MONO, fontSize: 34, alignItems: "baseline"}}>
        <In at={a}><span style={{color: C.mute}}>1</span></In><In at={a}>Ringfence</In><In at={a}><span style={{color: C.red}}>flag: {POISON?.flag ?? "address_poisoning"}</span></In>
        <In at={b}><span style={{color: C.mute}}>2</span></In><In at={b}>Metal</In><In at={b}><span style={{color: C.red}}>refused: {POISON?.code}</span></In>
      </div>
      <Receipt kind="chain" text={`tx ${short(POISON?.tx ?? "")}`} at={b + 0.3} />
    </AbsoluteFill>
  );
};

// ---- blast radius: what a stolen key is worth ----
export const Blast: React.FC<{t0: number}> = ({t0}) => {
  const t = useT();
  const strike = at("billion", 145) - t0;
  const most = at("the most they could do", 145) - t0;
  const col = (x: number): React.CSSProperties => ({position: "absolute", left: x, top: 230, width: 760});
  const head: React.CSSProperties = {fontFamily: MONO, fontSize: 22, letterSpacing: "0.12em", color: C.mute, marginBottom: 30};
  return (
    <AbsoluteFill style={{background: C.bg}}>
      <div style={{position: "absolute", left: 960, top: 210, bottom: 250, width: 1, background: C.line}} />
      <div style={col(130)}>
        <div style={head}>A SIGNING KEY WITH NO LIMIT</div>
        <div style={{fontFamily: SANS, fontSize: 40, color: C.ink, fontWeight: 600}}>whatever the key can sign</div>
        <div style={{position: "relative", display: "inline-block", fontFamily: SANS, fontSize: 104, fontWeight: 760, letterSpacing: "-0.03em", marginTop: 40, color: C.ink}}>
          $6,300,000,000
          <div style={{position: "absolute", left: -8, top: "52%", height: 8, background: C.red, width: `${ramp(t, strike, strike + 0.5) * 104}%`}} />
        </div>
        <div style={{fontFamily: MONO, fontSize: 18, color: C.dim, marginTop: 18}}>as reported · a scale, not a claim about that incident</div>
      </div>
      <div style={col(1030)}>
        <div style={head}>A STOLEN RINGFENCE KEY</div>
        {["1 pull", `≤ ${PULL.usdz} USDZ`, "only to the listed payee", "within the hour"].map((x, i) => (
          <In key={x} at={most + i * 0.35}><div style={{fontFamily: MONO, fontSize: 50, fontWeight: 600, color: C.ink, lineHeight: 1.55}}>{x}</div></In>
        ))}
      </div>
      <Tag at={most + 2.2} style={{position: "absolute", left: 130, right: 130, bottom: 140}}>blast radius = the mandate, not the key</Tag>
    </AbsoluteFill>
  );
};
