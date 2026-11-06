// Act 2: the live app. Shots cut our own capture (public/cap/app.mp4) by its marks, and X-ray the real Airwallex calls behind it.
import React from "react";
import {AbsoluteFill, Img, staticFile} from "remotion";
import {Receipt, ramp, useT} from "../base";
import {Box, Cap, Zoom} from "../cap";
import {short} from "../facts";
import marks from "../../public/cap/app.json";

type M = [number, string, string?, number[]?];
const MK = marks as unknown as M[];
/** capture-time of a named mark */
export const mark = (name: string) => MK.find((m) => m[1] === name)![0];
/** the element box recorded for `sel` at or after `after` (capture time) */
const box = (sel: string, after = 0): Box => MK.find((m) => m[1] === "box" && m[2] === sel && m[0] >= after)![3] as Box;

const lane = (t: string) => `.lane[data-t=${t}] .status`;

/** the app at capture time `from`, with zooms placed in shot seconds */
export const App: React.FC<{from: number; rate?: number; zooms?: Zoom[]; dim?: number}> = (p) => <Cap src="cap/app.mp4" {...p} />;

export const Clients: React.FC = () => <App from={mark("run")} zooms={[{at: 2.5, box: box("#next button.primary"), scale: 1.25}]} />;

export const Running: React.FC = () => <App from={mark("run") + 4} rate={6} />; // 30 s of the agent reading, sped up

export const Kestrel: React.FC = () => <App from={42} zooms={[{at: 0.3, box: box(lane("kestrel"))}]} />;

/** the dialog with the actual timesheet CSV the agent read */
export const FilesRead: React.FC = () => <App from={61.8} rate={0.55} />;

export const Northwind: React.FC = () => <App from={mark("read") - 0.5} zooms={[{at: 0.3, box: box(lane("northwind"))}]} />;

export const Harbour: React.FC = () => <App from={mark("plan")} zooms={[{at: 0.3, box: box(lane("harbour"))}]} />;

export const Trap: React.FC = () => (
  <AbsoluteFill>
    <App from={mark("deposit")} zooms={[{at: 0.2, box: box(".card[data-id=other_tenant_deposit] [data-act=scenario]", mark("deposit")), scale: 1.3}]} />
    <Receipt kind="sim" text="USD 50,000 into Kestrel's account" at={0.6} />
  </AbsoluteFill>
);

export const NotYours: React.FC = () => <App from={mark("deposit") + 6.5} zooms={[{at: 0, box: box(lane("harbour"))}]} />;

// tail.mp4 / breakit.mp4: the rest of the real app, by capture second
export const AllPaid: React.FC = () => <Cap src="cap/tail.mp4" from={0} />;
export const BankChange: React.FC = () => <Cap src="cap/tail.mp4" from={29} />;
export const CrossLogin: React.FC = () => <Cap src="cap/tail.mp4" from={52.5} />;
export const Break: React.FC<{from: number; rate?: number}> = (p) => <Cap src="cap/breakit.mp4" {...p} />;

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
