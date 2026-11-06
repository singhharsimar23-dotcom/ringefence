// Act 4: proof the tenants are walled off at Airwallex, then four engineering decisions, each named the way a payments veteran names it.
import React from "react";
import {AbsoluteFill, Img, staticFile} from "remotion";
import {C, In, MONO, Receipt, Rise, SANS, at, ramp, useT} from "../base";
import {APPROVAL, FACTS, XFER, short} from "../facts";
import {Tag} from "../xray";

// ---- 4x4: every employer's token against every other account; the diagonal is your own ----
const WHO = ["platform", "northwind", "kestrel", "harbour"];
export const Isolation: React.FC<{t0: number}> = ({t0}) => {
  const t = useT();
  const go = 0.8;
  let k = 0;
  return (
    <AbsoluteFill style={{background: C.bg, justifyContent: "center", alignItems: "center"}}>
      <div style={{display: "grid", gridTemplateColumns: "230px repeat(4, 190px)", rowGap: 14, columnGap: 14, fontFamily: MONO, alignItems: "center"}}>
        <div style={{fontSize: 17, color: C.mute, letterSpacing: "0.06em"}}>TOKEN ↓ · ACCOUNT →</div>
        {WHO.map((w) => <div key={w} style={{fontSize: 20, color: C.mute, textAlign: "center"}}>{w}</div>)}
        {WHO.map((r) => (
          <React.Fragment key={r}>
            <div style={{fontSize: 22, color: C.ink}}>{r}</div>
            {WHO.map((c) => {
              const own = r === c;
              const p = own ? ramp(t, 0.3, 0.6) : ramp(t, go + 0.17 * k, go + 0.17 * k++ + 0.25);
              return (
                <div key={c} style={{height: 74, borderRadius: 8, display: "flex", alignItems: "center", justifyContent: "center", opacity: p,
                  border: `1px solid ${own ? C.line : "rgba(255,91,82,.45)"}`, background: own ? "transparent" : "rgba(255,91,82,.08)",
                  color: own ? C.dim : C.red, fontSize: own ? 18 : 30, fontWeight: 600}}>{own ? "own" : "401"}</div>
              );
            })}
          </React.Fragment>
        ))}
      </div>
      <div style={{fontFamily: MONO, fontSize: 24, color: C.ink, marginTop: 44, opacity: ramp(t, go + 2.3, go + 2.8)}}>
        {FACTS.gauntlet.isolation.directions} / 12 cross-account calls → 401 credentials_invalid
      </div>
      <Tag at={at("blocked me", t0) - t0} style={{marginTop: 40, width: 1400, textAlign: "center"}}>client-money segregation, enforced by Airwallex · not by a filter in my code</Tag>
      <Receipt kind="live" text="x-on-behalf-of · every direction" at={go} />
    </AbsoluteFill>
  );
};

// ---- the four decisions; the index stays on the left the whole time ----
const D = () => [
  {at: at("the model is never trusted"), k: "Model never trusted"},
  {at: at("Client money is never pooled"), k: "Money never pooled"},
  {at: at("Three, exactly once"), k: "Exactly once"},
  {at: at("Four, a bank"), k: "Bank changes held"},
];

const Box: React.FC<{at: number; children: React.ReactNode; w?: number; tone?: string}> = ({at: a, children, w = 400, tone = C.line}) => (
  <In at={a}><div style={{width: w, border: `1px solid ${tone}`, borderRadius: 12, padding: "22px 26px", fontFamily: MONO, fontSize: 24, color: C.ink, lineHeight: 1.5}}>{children}</div></In>
);
const Arrow: React.FC<{at: number}> = ({at: a}) => <In at={a}><div style={{fontFamily: MONO, fontSize: 40, color: C.mute, padding: "0 22px"}}>→</div></In>;

export const Decisions: React.FC<{t0: number}> = ({t0}) => {
  const t = useT();
  const ds = D().map((d) => ({...d, at: d.at - t0}));
  const four = at("Four decisions") - t0;
  const cur = ds.filter((d) => t >= d.at).length - 1;
  const r = (ph: string, after = 0) => at(ph, after) - t0;
  const panelOpacity = (i: number) => (cur === i ? ramp(t, ds[i].at, ds[i].at + 0.5) : 0);
  return (
    <AbsoluteFill style={{background: C.bg}}>
      {/* intro, then the index slides to the rail */}
      <AbsoluteFill style={{justifyContent: "center", alignItems: "center", opacity: 1 - ramp(t, ds[0].at - 0.4, ds[0].at)}}>
        <Rise text="For the engineers." size={92} />
        <div style={{height: 30}} />
        <Rise text="Four decisions." at={four} size={92} color={C.mute} />
      </AbsoluteFill>
      <div style={{position: "absolute", left: 90, top: 190, width: 360, opacity: ramp(t, ds[0].at - 0.3, ds[0].at + 0.3)}}>
        {ds.map((d, i) => (
          <div key={i} style={{fontFamily: MONO, fontSize: 24, padding: "16px 0", borderTop: `1px solid ${C.line}`, color: i === cur ? C.ink : C.dim,
            display: "flex", gap: 18}}>
            <span style={{color: i === cur ? C.accent : C.dim}}>{i + 1}</span>{d.k}
          </div>
        ))}
      </div>
      <div style={{position: "absolute", left: 540, right: 90, top: 190, bottom: 120}}>
        {/* 1: the model proposes, code decides */}
        <div style={{position: "absolute", inset: 0, opacity: panelOpacity(0)}}>
          <div style={{display: "flex", alignItems: "center"}}>
            <Box at={ds[0].at + 0.3} w={260}>Claude<div style={{color: C.mute, fontSize: 18}}>reads timesheets, emails</div></Box>
            <Arrow at={r("It writes a proposal")} />
            <Box at={r("It writes a proposal")} w={330}><span style={{color: C.mute}}>proposal</span><br />{`{contractor, hours}`}<div style={{color: C.mute, fontSize: 18}}>no amounts, no accounts</div></Box>
            <Arrow at={r("deterministic code")} />
            <Box at={r("deterministic code")} w={420} tone="rgba(138,169,255,.5)">
              code decides
              {["prices every line (Decimal)", "limits · mandate · FX band", "mints the request_id", "picks the employer's token"].map((x, i) => (
                <In key={x} at={r("deterministic code") + 0.3 + i * 0.3}><div style={{color: C.mute, fontSize: 20}}>{x}</div></In>
              ))}
            </Box>
          </div>
          <In at={r("the safety doesn't depend")} style={{marginTop: 70}}>
            <div style={{fontFamily: SANS, fontSize: 46, fontWeight: 650, letterSpacing: "-0.02em"}}>Swap in a model that obeys every attack.<br /><span style={{color: C.mute}}>Still $0 to a wrong payee.</span></div>
          </In>
          <Tag at={r("I'll prove that")} style={{marginTop: 50}}>the model proposes · deterministic code disposes · the LLM never holds a key</Tag>
        </div>
        {/* 2: never pooled */}
        <div style={{position: "absolute", inset: 0, opacity: panelOpacity(1)}}>
          <div style={{display: "flex", gap: 24}}>
            {[["Northwind", "acct_Y5VX…i15A"], ["Kestrel", "acct_FG3w…pelKHg"], ["Harbour", "acct_8bUT…xiutw"]].map(([n, a], i) => (
              <Box key={n} at={ds[1].at + 0.3 + i * 0.25} w={390}>
                {n}<div style={{color: C.mute, fontSize: 18, marginTop: 8}}>x-login-as {a}</div>
                <div style={{color: C.mute, fontSize: 18}}>own token · own payees · own balance</div>
              </Box>
            ))}
          </div>
          <In at={r("not even in a calculation")} style={{marginTop: 60}}>
            <span style={{position: "relative", fontFamily: MONO, fontSize: 56, color: C.ink}}>
              sum(balances)
              <span style={{position: "absolute", left: -6, right: -6, top: "52%", height: 6, background: C.red,
                transform: `scaleX(${ramp(t, r("not even in a calculation") + 0.4, r("not even in a calculation") + 0.8)})`, transformOrigin: "0 50%"}} />
            </span>
            <span style={{fontFamily: MONO, fontSize: 26, color: C.mute, marginLeft: 30}}>never computed</span>
          </In>
          <Tag at={r("enforced by the Airwallex")} style={{marginTop: 60}}>client-money segregation · one credential per client · no omnibus maths</Tag>
        </div>
        {/* 3: exactly once, as a sequence diagram with the real request_id */}
        <div style={{position: "absolute", inset: 0, opacity: panelOpacity(2)}}><Seq t0={t0} start={ds[2].at} /></div>
        {/* 4: bank change, then the signed batch */}
        <div style={{position: "absolute", inset: 0, opacity: panelOpacity(3)}}>
          <div style={{display: "flex", alignItems: "center"}}>
            <Box at={ds[3].at + 0.2} w={380}><span style={{color: C.mute, fontSize: 18}}>email</span><br />"Updated bank details"</Box>
            <Arrow at={r("That never happens")} />
            <Box at={r("That never happens")} w={300} tone="rgba(242,184,75,.6)"><span style={{color: C.amber}}>QUARANTINED</span><div style={{color: C.mute, fontSize: 18}}>old details stay live</div></Box>
            <Arrow at={r("different person")} />
            <Box at={r("different person")} w={380}>call-back by phone<div style={{color: C.mute, fontSize: 18}}>a second person, not the requester</div></Box>
          </div>
          <In at={r("approval signs a hash")} style={{marginTop: 70}}>
            <div style={{fontFamily: MONO, fontSize: 28, color: C.mute}}>{APPROVAL ? `${APPROVAL.approver} · ${APPROVAL.role} signed` : "approval signs"}</div>
            <div style={{fontFamily: MONO, fontSize: 34, color: C.ink, marginTop: 12}}>sha256( run · round · every line · request_id )</div>
            <div style={{fontFamily: MONO, fontSize: 26, color: C.accent, marginTop: 10}}>= {APPROVAL ? short(APPROVAL.batch_hash, 16, 8) : ""}</div>
          </In>
          <In at={r("nothing can be swapped")} style={{marginTop: 34}}>
            <div style={{fontFamily: MONO, fontSize: 28, color: C.ink}}>one line +0.01 → hash ≠ signed → <span style={{color: C.red}}>release refused</span></div>
          </In>
          <Tag at={r("nothing can be swapped") + 1.2} style={{marginTop: 46}}>out-of-band callback · four eyes · what you sign is what is paid</Tag>
        </div>
      </div>
    </AbsoluteFill>
  );
};

// ---- idempotency: the real request_id, a lost reply, a lookup instead of a resend, and a return after PAID ----
const Seq: React.FC<{t0: number; start: number}> = ({t0, start}) => {
  const r = (ph: string) => at(ph, 201) - t0;
  const L = 60, R = 860;
  const Msg: React.FC<{at: number; y: number; dir: 1 | -1; text: string; color?: string; dash?: boolean; cut?: boolean}> = ({at: a, y, dir, text, color = C.ink, dash, cut}) => {
    const p = ramp(useT(), a, a + 0.5);
    const x0 = dir === 1 ? L : R, w = (R - L) * p;
    return (
      <div style={{position: "absolute", top: y, left: 0, right: 0, opacity: p > 0 ? 1 : 0}}>
        <div style={{position: "absolute", left: dir === 1 ? x0 : x0 - w, width: cut ? w * 0.55 : w, top: 30, borderTop: `2px ${dash ? "dashed" : "solid"} ${color}`}} />
        {cut && p > 0.5 && <div style={{position: "absolute", left: R - (R - L) * 0.55 - 30, top: 6, color: C.red, fontFamily: MONO, fontSize: 36}}>✕</div>}
        <div style={{position: "absolute", left: L + 20, top: -6, fontFamily: MONO, fontSize: 22, color, opacity: p}}>{text}</div>
      </div>
    );
  };
  const rid = XFER?.request_id ?? "";
  return (
    <div style={{position: "absolute", inset: 0}}>
      {[["Ringfence", L], ["Airwallex", R]].map(([n, x]) => (
        <div key={n as string} style={{position: "absolute", left: (x as number) - 80, width: 160, textAlign: "center", fontFamily: MONO, fontSize: 22, color: C.mute}}>
          {n}<div style={{position: "absolute", left: 80, top: 40, height: 660, borderLeft: `1px dashed ${C.line}`}} />
        </div>
      ))}
      <In at={start + 0.3} style={{position: "absolute", top: 70, left: L + 20, fontFamily: MONO, fontSize: 20, color: C.accent}}>request_id = {rid.slice(0, 26)}… · stored before attempt 1</In>
      <Msg at={start + 1.2} y={130} dir={1} text="POST /transfers/create" />
      <Msg at={r("times out")} y={210} dir={-1} text="reply lost (timeout)" color={C.red} dash cut />
      <Msg at={r("never resends")} y={290} dir={1} text="no second POST · GET by request_id" color={C.accent} />
      <Msg at={r("looks it up") + 0.6} y={370} dir={-1} text={`found ${short(XFER?.id ?? "", 8, 4)} · adopt it`} color={C.green} />
      <Msg at={r("bounce back")} y={470} dir={-1} text="PAID → FAILED · bank returned" color={C.amber} />
      <In at={r("bounce back") + 0.8} style={{position: "absolute", top: 540, left: L + 20, fontFamily: MONO, fontSize: 20, color: C.mute}}>line reopens · nothing is final until it reconciles</In>
      <Tag at={r("bounce back") + 1.6} style={{position: "absolute", top: 620, left: 0, right: 0}}>idempotency key · reconcile before retry · returns after PAID</Tag>
    </div>
  );
};

// ---- the agent's whole tool surface; approval isn't on it ----
const TOOLS = ["get_status", "price_run", "propose_run", "request_release", "certificate"];
export const Mcp: React.FC<{t0: number}> = ({t0}) => {
  const t = useT();
  const human = at("A human always signs") - t0;
  return (
    <AbsoluteFill style={{background: C.bg, justifyContent: "center", paddingLeft: 300}}>
      <div style={{opacity: 1 - ramp(t, human - 0.3, human)}}>
        <div style={{fontFamily: MONO, fontSize: 20, letterSpacing: "0.14em", color: C.mute, marginBottom: 26}}>MCP SERVER · EVERY TOOL THE AGENT HAS</div>
        {TOOLS.map((x, i) => <In key={x} at={0.3 + i * 0.22}><div style={{fontFamily: MONO, fontSize: 44, lineHeight: 1.5}}>{x}</div></In>)}
        <In at={1.8}><div style={{fontFamily: MONO, fontSize: 44, lineHeight: 1.5, color: C.dim, textDecoration: "line-through", textDecorationColor: C.red}}>approve_release</div></In>
        <In at={2.4}><div style={{fontFamily: MONO, fontSize: 22, color: C.mute, marginTop: 14}}>request_release only asks · separation of duties</div></In>
      </div>
      <AbsoluteFill style={{justifyContent: "center", alignItems: "center", opacity: ramp(t, human, human + 0.3)}}>
        <Rise text="A human always signs." at={human} size={110} />
      </AbsoluteFill>
    </AbsoluteFill>
  );
};

// ---- Harsimar's own Airwallex dashboard screenshots, stacked; only used once they exist in public/awx/ ----
export const AWX = ["awx/1_accounts.png", "awx/2_kestrel_transfers.png", "awx/3_transfer.png", "awx/4_harbour_aud.png", "awx/5_api_key.png"];
export const AwxStack: React.FC<{t0: number; files: string[]}> = ({t0, files}) => {
  const t = useT();
  const step = (at("I even tried") - t0) / Math.max(1, files.length);
  return (
    <AbsoluteFill style={{background: C.bg}}>
      {files.map((f, i) => {
        const p = ramp(t, i * step, i * step + 0.6);
        return (
          <div key={f} style={{position: "absolute", left: 200 + i * 60, top: 90 + i * 40, width: 1400, opacity: p, borderRadius: 10, overflow: "hidden",
            boxShadow: "0 30px 90px rgba(0,0,0,.7)", border: `1px solid ${C.line}`, transform: `translateY(${(1 - p) * 60}px) scale(${1 - 0.02 * (files.length - 1 - i) * ramp(t, (i + 1) * step, (i + 1) * step + 0.6)})`}}>
            <Img src={staticFile(f)} style={{width: 1400, display: "block"}} />
          </div>
        );
      })}
      <Receipt kind="live" text={`transfer ${XFER ? short(XFER.id, 8, 4) : ""}`} at={0.4} />
    </AbsoluteFill>
  );
};
