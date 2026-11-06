// Act 5: the gauntlet. Every number is from docs/gauntlet/results.json (via facts.json); each row lands on the line that says it.
import React from "react";
import {AbsoluteFill} from "remotion";
import {C, MONO, Receipt, SANS, at, ramp, useT} from "../base";
import {FACTS} from "../facts";

const G = FACTS.gauntlet;
const Row: React.FC<{at: number; what: string; n: string; note: string; red?: boolean}> = ({at: a, what, n, note, red}) => {
  const t = useT();
  const p = ramp(t, a, a + 0.5);
  return (
    <div style={{display: "grid", gridTemplateColumns: "560px 420px auto", alignItems: "baseline", padding: "22px 0", borderTop: `1px solid ${C.line}`,
      opacity: p, transform: `translateY(${(1 - p) * 12}px)`}}>
      <div style={{fontFamily: SANS, fontSize: 30, color: C.mute}}>{what}</div>
      <div style={{fontFamily: MONO, fontSize: 52, fontWeight: 650, color: red ? C.red : C.ink}}>{n}</div>
      <div style={{fontFamily: MONO, fontSize: 20, color: C.mute}}>{note}</div>
    </div>
  );
};

export const Gauntlet: React.FC<{t0: number}> = ({t0}) => {
  const r = (ph: string) => at(ph, 242) - t0;
  const s = G.storm;
  return (
    <AbsoluteFill style={{background: C.bg, justifyContent: "center", padding: "0 120px"}}>
      <div style={{fontFamily: MONO, fontSize: 20, letterSpacing: "0.14em", color: C.mute, marginBottom: 20}}>GAUNTLET · COMMIT {G.commit}</div>
      <Row at={r("test agent")} what={`Obedient test agent · ${G.evil.expressible} attacks`} n={`fooled ${G.evil.fooled}`} note="it does whatever the document says" red />
      <Row at={r("still didn't send")} what="Money to a wrong payee" n={`$${G.evil.money_moved}`} note="the gate, not the model" />
      <Row at={r("Claude didn't fall")} what="Claude, same attacks" n={`fooled ${G.claude.fooled}`} note={G.claude.model} />
      <Row at={r("I fired")} what={`${s.parallel_releases} releases at once · ${s.answers_lost} replies cut`} n={s.transfers_per_line.join(" · ")}
        note={`live: ${s.transfer_ids.map((x) => x.slice(0, 8)).join(" · ")}`} />
      <Row at={r("I tampered")} what={`${G.tamper.mutations} ledger tamperings`} n={`${G.tamper.caught_at_the_right_row} / ${G.tamper.mutations}`} note="caught at the exact row" />
      <Row at={r("500 random")} what={`${G.sequences.sequences} random runs · ${G.sequences.steps_run.toLocaleString("en-US")} steps`} n="0 broken" note="421 tests" />
      <Receipt kind="live" text="storm run on the live sandbox" at={r("I fired") + 0.4} />
    </AbsoluteFill>
  );
};
