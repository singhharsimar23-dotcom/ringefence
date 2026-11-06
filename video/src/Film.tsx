// The whole film: Harsimar's voice runs underneath; every shot starts on a phrase in the voice.
import React from "react";
import {AbsoluteFill, Audio, Sequence, getStaticFiles, staticFile} from "remotion";
import {C, FPS, MONO, Rise, SANS, Stage, TOTAL, WORDS, at, end, f, ramp, useT} from "./base";
import {Face} from "./cap";
import {Subs} from "./subs";
import {Bureau, Decide, Email, Statement} from "./scenes/act1";
import {ColdOpen} from "./scenes/open";
import {Blast, Evidence, Mandate, Overpull, Poison} from "./scenes/act3";
import {AWX, AwxStack, Decisions, Isolation, Mcp} from "./scenes/act4";
import {Gauntlet} from "./scenes/act5";
import {Clients, Explorer, Harbour, HarbourSigns, Kestrel, NotYours, Northwind, Pull, Running, Trap, TryIt} from "./scenes/act2";
import {FACTS, PULL, short} from "./facts";

export const OPEN = 5; // cold open of real receipts before the voice starts
export const END_CARD = 5.5;
const FILM = TOTAL + END_CARD; // in voice time
export const LENGTH = OPEN + FILM; // under 5:00

type Shot = {from: number; to: number; el: (t0: number) => React.ReactNode; subs?: boolean};
const S = (from: number, to: number, el: Shot["el"], subs = true): Shot => ({from, to, el, subs});
const face = (from: number, to: number, lower?: string) => S(from, to, (t0) => <Face t0={t0} lower={lower} />);

const CLOSE = at("That's Ring Fence");
const AWX_HAVE = AWX.filter((a) => getStaticFiles().some((x) => x.name === a));
// later shots draw on top of earlier ones, so a base board can run under short overlays and keep its state
const SHOTS: Shot[] = [
  face(0, at("Some companies"), "HARSIMAR · RINGFENCE"),
  S(at("Some companies") - 0.1, at("My first question"), (t0) => <Bureau t0={t0} />),
  S(at("And it goes wrong") - 0.05, at("One, client's"), () => <Statement text="Two ways it goes wrong." size={118} />, false),
  S(at("or someone email") - 0.1, at("Now give that job"), (t0) => <Email t0={t0} />),
  face(at("My first question"), at("So here's what I did")),
  S(at("So here's what I did") - 0.1, at("Let me show you"), (t0) => <Decide t0={t0} />),
  S(at("Let me show you") - 0.1, at("I hit run"), () => <Clients />),
  S(at("I hit run") - 0.1, at("Kestrel had a normal"), () => <Running />),
  S(at("Kestrel had a normal") - 0.1, at("North Wind changed"), (t0) => <Kestrel t0={t0} />),
  S(at("North Wind changed") - 0.1, at("Harbor this is"), (t0) => <Northwind t0={t0} />),
  S(at("Harbor this is") - 0.1, at("And here's a trap"), (t0) => <Harbour t0={t0} />),
  S(at("And here's a trap") - 0.1, at("lands in Kestrel") - 1, () => <Statement text="The trap." size={140} />, false),
  S(at("lands in Kestrel") - 1, at("But that's Kestrel's"), () => <Trap />),
  S(at("But that's Kestrel's") - 0.1, at("So how does Harbor"), (t0) => <NotYours t0={t0} />),
  S(at("So how does Harbor") - 0.1, at("Honestly"), () => <Statement text="So how does Harbour get funded?" size={92} />, false),
  face(at("Honestly"), at("You probably saw")),
  S(at("You probably saw") - 0.1, at("So I asked myself"), (t0) => <Evidence t0={t0} />),
  S(at("So I asked myself") - 0.1, at("That's what I build"), () => <Statement text="A limit no stolen key can get around." size={96} />, false),
  S(at("That's what I build") - 0.1, at("I press the button"), (t0) => <Mandate t0={t0} />),
  S(at("I press the button") - 0.1, at("a real transaction"), () => <Pull />),
  S(at("a real transaction") - 0.1, at("Then I tried to cheat"), () => <Explorer name="pull" tx={PULL.tx} />),
  S(at("Then I tried to cheat") - 0.1, at("Then I tried a fake"), (t0) => <Overpull t0={t0} />),
  S(at("Then I tried a fake") - 0.1, at("Even if someone"), (t0) => <Poison t0={t0} />),
  S(at("Even if someone") - 0.1, at("The money lands"), (t0) => <Blast t0={t0} />),
  S(at("The money lands") - 0.1, at("Not one cent"), () => <HarbourSigns />),
  S(at("Not one cent") - 0.1, AWX_HAVE.length ? at("This is real Airwallex") : at("I even tried"), () => <Statement text="0 cents crossed between employers." size={100} />, false),
  ...(AWX_HAVE.length ? [S(at("This is real Airwallex") - 0.1, at("I even tried"), (t0) => <AwxStack t0={t0} files={AWX_HAVE} />)] : []),
  S(at("I even tried") - 0.1, at("So here's a quick one"), (t0) => <Isolation t0={t0} />),
  S(at("So here's a quick one") - 0.1, at("It all is done"), (t0) => <Decisions t0={t0} />),
  S(at("It all is done") - 0.1, at("Then I tried really hard"), (t0) => <Mcp t0={t0} />),
  S(at("Then I tried really hard") - 0.1, at("I think you get"), (t0) => <Gauntlet t0={t0} />, false),
  face(at("I think you get"), at("The demo's live")),
  S(at("The demo's live") - 0.1, at("So back to my question"), () => <TryIt />),
  face(at("So back to my question"), CLOSE),
  S(CLOSE, FILM, () => <EndCard />, false),
];

const EndCard: React.FC = () => {
  const t = useT();
  return (
    <Stage>
      <AbsoluteFill style={{alignItems: "center", justifyContent: "center", gap: 26}}>
        <Rise text="Ringfence" size={150} weight={780} stagger={0} />
        <div style={{fontFamily: MONO, fontSize: 24, color: C.mute, letterSpacing: "0.04em", opacity: ramp(t, 1.2, 1.8)}}>
          ringfence-hs23-eu.indiasouthcentral.cloudapp.azure.com
        </div>
        <div style={{fontFamily: MONO, fontSize: 18, color: C.dim, letterSpacing: "0.04em", opacity: ramp(t, 2, 2.6)}}>
          ledger head {short(FACTS.head ?? "", 16, 0).replace("…", "")} · every event hash-chained
        </div>
      </AbsoluteFill>
    </Stage>
  );
};

// ---- music: a low bed under the voice, ducked further under speech, out of the way at the dramatic beats, up on the end card ----
const MUSIC = (() => {
  const n = Math.ceil(LENGTH * FPS);
  const talk = new Uint8Array(n);
  for (const w of WORDS) for (let i = f(OPEN + w.s - 0.1); i <= f(OPEN + w.e + 0.3) && i < n; i++) if (i >= 0) talk[i] = 1;
  const quiet: [number, number][] = [[at("So how does Harbor") - 0.2, at("You probably saw")], [at("Then I tried really hard") - 0.2, end("Then I tried really hard to break it") + 0.6]];
  const out = new Float32Array(n);
  let g = 0;
  for (let i = 0; i < n; i++) {
    const t = i / FPS - OPEN; // voice time
    let want = t < 0 ? 0.3 : talk[i] ? 0.1 : 0.15;
    if (quiet.some(([a, b]) => t >= a && t < b)) want = 0.025;
    if (t >= CLOSE) want = 0.42 * (1 - ramp(t, FILM - 1.6, FILM, 0, 1, (x) => x));
    g += (want - g) * (want < g ? 0.35 : 0.06); // fast duck (~3 frames), slow release (~0.5 s)
    out[i] = g * ramp(i / FPS, 0, 1.5, 0, 1, (x) => x);
  }
  return out;
})();

// subtitles step aside while big type already says the same words
const HIDE: [number, number][] = [...SHOTS.filter((s) => !s.subs).map((s) => [s.from, s.to] as [number, number]), [at("The agent suggests") - 0.2, at("and every client")]];

export const Film: React.FC = () => (
  <AbsoluteFill style={{background: C.bg}}>
    <Sequence durationInFrames={f(OPEN)} layout="none">
      <ColdOpen />
    </Sequence>
    <Sequence from={f(OPEN)} layout="none">
      {SHOTS.map((s, i) => (
        <Sequence key={i} from={f(s.from)} durationInFrames={Math.max(1, f(s.to) - f(s.from))} layout="none">
          <AbsoluteFill style={{color: C.ink, fontFamily: SANS}}>{s.el(s.from)}</AbsoluteFill>
        </Sequence>
      ))}
      <Subs hide={HIDE} />
      <Audio src={staticFile("loom_cut.mp4")} />
    </Sequence>
    <Audio src={staticFile("music.mp3")} volume={(i) => MUSIC[Math.min(i, MUSIC.length - 1)]} />
  </AbsoluteFill>
);
