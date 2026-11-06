// Act 2: the live app. Shots cut our own capture (public/cap/app.mp4) by its marks, and X-ray the real Airwallex calls behind it.
import React from "react";
import {AbsoluteFill, Img, staticFile} from "remotion";
import {C, Receipt, at, ramp, useT} from "../base";
import {Box, Cap, Zoom} from "../cap";
import {FACTS, short} from "../facts";
import {Tag, Wire, XRay} from "../xray";
import marks from "../../public/cap/app.json";

type M = [number, string, string?, number[]?];
const MK = marks as unknown as M[];
/** capture-time of a named mark */
export const mark = (name: string) => MK.find((m) => m[1] === name)![0];
/** the element box recorded for `sel` at or after `after` (capture time) */
const box = (sel: string, after = 0): Box => MK.find((m) => m[1] === "box" && m[2] === sel && m[0] >= after)![3] as Box;

const lane = (t: string) => `.lane[data-t=${t}] .status`;
const kes = () => FACTS.transfers.find((x) => x.tenant === "kestrel") ?? FACTS.transfers[0];
const fund = () => FACTS.rows.find((r) => r.kind === "FUNDING_REQUESTED")?.payload as Record<string, string> | undefined;

/** the app at capture time `from`, with zooms placed in shot seconds */
export const App: React.FC<{from: number; rate?: number; zooms?: Zoom[]; dim?: number}> = (p) => <Cap src="cap/app.mp4" {...p} />;

export const Clients: React.FC = () => <App from={mark("run")} zooms={[{at: 2.5, box: box("#next button.primary"), scale: 1.25}]} />;

export const Running: React.FC = () => <App from={mark("run") + 4} rate={6} />; // 30 s of the agent reading, sped up

export const Kestrel: React.FC<{t0: number}> = ({t0}) => {
  const x = kes();
  const t1 = at("Those are real") - t0;
  const lines: Wire[] = x ? [
    {at: t1 + 0.4, text: `POST /transfers/create`, color: C.accent},
    {at: t1 + 0.7, text: `request_id  ${short(x.request_id, 18, 6)}`, size: 20, color: C.mute},
    {at: t1 + 1.0, text: `${x.amount.toFixed(2)} ${x.currency} · LOCAL`, size: 20, color: C.mute},
    {at: t1 + 1.4, text: `${x.status}${x.create_ms ? ` · ${x.create_ms} ms` : ""}`, color: C.green, gap: 22},
    {at: t1 + 1.6, text: `id ${short(x.id, 8, 4)} · ${x.short_reference_id ?? ""}`, size: 20},
  ] : [];
  return (
    <XRay title="WHAT JUST WENT OVER THE WIRE · KESTREL'S OWN TOKEN" lines={lines} out={99}
      under={<App from={42} zooms={[{at: 0.3, box: box(lane("kestrel"))}]} />} />
  );
};

export const Northwind: React.FC<{t0: number}> = ({t0}) => (
  <AbsoluteFill>
    <App from={mark("read") - 0.5} zooms={[{at: 0.3, box: box(lane("northwind"))}]} />
    <Tag at={at("So I wait") - t0} style={{position: "absolute", left: 120, right: 120, bottom: 170, background: "#000", color: C.ink, border: `1px solid ${C.line}`, borderRadius: 10, padding: "18px 24px"}}>
      rate change → held for finance:northwind · maker-checker, the agent can't approve
    </Tag>
  </AbsoluteFill>
);

export const Harbour: React.FC<{t0: number}> = ({t0}) => {
  const f = fund();
  const t1 = at("works out exactly") - t0;
  const lines: Wire[] = f ? [
    {at: t1, text: `harbour AUD available < payroll need`, color: C.ink},
    {at: t1 + 0.6, text: `short  AUD ${f.amount}`, size: 40, color: C.amber, gap: 18},
    {at: t1 + 1.6, text: `top up: BSB ${f.routing_value} · acct ${f.account_number}`, size: 20, color: C.mute, gap: 22},
    {at: t1 + 1.9, text: `reference ${f.reference}`, size: 20, color: C.mute},
    {at: at("before the deadline") - t0, text: `act by ${f.act_by.replace("T", " ").slice(0, 16)} AEDT`, size: 24, color: C.ink, gap: 18},
  ] : [];
  return (
    <XRay title="FUNDING REQUEST · HARBOUR'S OWN AUD ACCOUNT" lines={lines}
      under={<App from={mark("plan")} zooms={[{at: 0.3, box: box(lane("harbour"))}]} />} />
  );
};

export const Trap: React.FC = () => (
  <AbsoluteFill>
    <App from={mark("deposit")} zooms={[{at: 0.2, box: box(".card[data-id=other_tenant_deposit] [data-act=scenario]", mark("deposit")), scale: 1.3}]} />
    <Receipt kind="sim" text="USD 50,000 into Kestrel's account" at={0.6} />
  </AbsoluteFill>
);

export const NotYours: React.FC<{t0: number}> = ({t0}) => {
  const t1 = at("But that's Kestrel's") - t0;
  const lines: Wire[] = [
    {at: t1 + 0.3, text: "kestrel   USD +50,000  [SIMULATED]", color: C.mute},
    {at: t1 + 0.8, text: "harbour   still AWAITING_FUNDS", color: C.amber},
    {at: t1 + 1.6, text: "funding check reads one account only", size: 20, color: C.mute, gap: 24},
    {at: t1 + 2.0, text: "sum(balances)  never computed", size: 20, color: C.red},
  ];
  return <XRay title="PER-EMPLOYER FUNDING CHECK" lines={lines} under={<App from={mark("deposit") + 6.5} zooms={[{at: 0, box: box(lane("harbour"))}]} />} />;
};

export const Pull: React.FC = () => <App from={mark("metal_pulled") - 7} rate={3} zooms={[{at: 0.2, box: box("#chain [data-id=metal_topup]")}]} />;

/** the public Metal explorer page for a real tx (video/chain.py), slow push in on the Overview card */
export const Explorer: React.FC<{name: string; tx: string}> = ({name, tx}) => {
  const t = useT();
  const s = 1.5 + 0.12 * ramp(t, 0, 3, 0, 1, (x) => x);
  return (
    <AbsoluteFill style={{background: "#000", overflow: "hidden"}}>
      <Img src={staticFile(`chain/${name}.png`)} style={{position: "absolute", width: 1920, left: 0, top: 0, transformOrigin: "130px 150px", transform: `scale(${s})`}} />
      <Receipt kind="chain" text={`tx ${short(tx)} · finalized`} at={0.4} />
    </AbsoluteFill>
  );
};

export const HarbourSigns: React.FC = () => <App from={mark("approve_harbour") + 4.3} rate={2} />;

// shortcut: ends on "Writing…" because this capture predates the red-team decline fix (24859eb); re-capture after deploy to show the attack read
export const TryIt: React.FC = () => <Cap src="cap/try.mp4" from={17.8} rate={2} zooms={[{at: 0.2, box: [300, 150, 840, 460]}]} />;
