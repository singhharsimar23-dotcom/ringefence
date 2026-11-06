// The whole film: Harsimar's voice runs underneath; every shot starts on a phrase in the voice.
import React from "react";
import {AbsoluteFill, Audio, Sequence, staticFile} from "remotion";
import {C, FPS, MONO, Rise, SANS, Stage, TOTAL, at, f, ramp, useT} from "./base";
import {Face} from "./cap";
import {Subs} from "./subs";
import {Bureau, Decide, Email, Statement} from "./scenes/act1";
import {Blast, Evidence} from "./scenes/act3";
import {AllPaid, BankChange, Break, Clients, CrossLogin, FilesRead, Harbour, HarbourSigns, Kestrel, NotYours, Northwind, Pull, Running, Trap, TryIt} from "./scenes/act2";
import {FACTS, short} from "./facts";
import {Bams, Chapter, FaceBubble, Raw, RawCuts} from "./real";

export const OPEN = 0;
export const END_CARD = 5.5;
const OUTRO = 6.2; // black screen goodbyes, fills the film to just under 5:00
const FILM = TOTAL + END_CARD + OUTRO; // in voice time
export const LENGTH = OPEN + FILM; // under 5:00

type Shot = {from: number; to: number; el: (t0: number) => React.ReactNode; subs?: boolean; face?: boolean};
const S = (from: number, to: number, el: Shot["el"], subs = true): Shot => ({from, to, el, subs});
const face = (from: number, to: number, lower?: string): Shot => ({...S(from, to, (t0) => <Face t0={t0} lower={lower} />), face: true});
const raw = (from: number, to: number, file: string) => S(from, to, () => <Raw src={`real/${file}.png`} />);

const CLOSE = at("That's Ring Fence");
// later shots draw on top of earlier ones, so a base board can run under short overlays and keep its state
const SHOTS: Shot[] = [
  face(0, at("Some companies"), "HARSIMAR · RINGFENCE"),
  S(at("Some companies") - 0.1, at("My first question"), (t0) => <Bureau t0={t0} />),
  S(at("And it goes wrong") - 0.05, at("One, client's"), () => <Statement text="Two ways it goes wrong." size={118} />, false),
  S(at("or someone email") - 0.1, at("Now give that job"), (t0) => <Email t0={t0} />),
  face(at("My first question"), at("So here's what I did")),
  S(at("So here's what I did") - 0.1, at("Let me show you"), (t0) => <Decide t0={t0} />),
  S(at("Let me show you") - 0.1, at("I hit run"), () => <Clients />),
  S(at("I hit run") - 0.1, at("reads all"), () => <Running />),
  S(at("reads all") - 0.1, at("Kestrel had a normal"), () => <FilesRead />),
  S(at("Kestrel had a normal") - 0.1, at("Those are real"), () => <Kestrel />),
  raw(at("Those are real") - 0.1, at("North Wind changed"), "awx_2"),
  S(at("North Wind changed") - 0.1, at("Harbor this is"), () => <Northwind />),
  S(at("Harbor this is") - 0.1, at("And here's a trap"), () => <Harbour />),
  S(at("And here's a trap") - 0.1, at("lands in Kestrel") - 1, () => <Statement text="The trap." size={140} />, false),
  S(at("lands in Kestrel") - 1, at("But that's Kestrel's"), () => <Trap />),
  S(at("But that's Kestrel's") - 0.1, at("So how does Harbor"), () => <NotYours />),
  S(at("So how does Harbor") - 0.1, at("Honestly"), () => <Statement text="So how does Harbour get funded?" size={92} />, false),
  face(at("Honestly"), at("You probably saw")),
  S(at("You probably saw") - 0.1, at("So I asked myself"), (t0) => <Evidence t0={t0} />),
  S(at("So I asked myself") - 0.1, at("That's what I build"), () => <Statement text="A limit no stolen key can get around." size={96} />, false),
  raw(at("That's what I build") - 0.1, at("Count, we take"), "tx_bind"),
  raw(at("Count, we take") - 0.1, at("I press the button"), "code_mandate"),
  S(at("I press the button") - 0.1, at("a real transaction"), () => <Pull />),
  raw(at("a real transaction") - 0.1, at("Then I tried to cheat"), "tx_pull"),
  raw(at("Then I tried to cheat") - 0.1, at("Then I tried a fake"), "tx_over"),
  raw(at("Then I tried a fake") - 0.1, at("Even if someone"), "tx_poison"),
  S(at("Even if someone") - 0.1, at("The money lands"), (t0) => <Blast t0={t0} />),
  S(at("The money lands") - 0.1, at("Not one cent"), () => <HarbourSigns />),
  S(at("Not one cent") - 0.1, at("This is real Airwallex"), () => <AllPaid />),
  S(at("This is real Airwallex") - 0.1, at("I even tried"), (t0) => (
    <RawCuts t0={t0} cuts={[[0, "real/awx_1.png"], [at("the same transfer"), "real/awx_2.png"], [at("ID", at("the same transfer")), "real/awx_3.png"]]} />
  )),
  S(at("I even tried") - 0.1, at("So here's a quick one"), () => <CrossLogin />),
  S(at("So here's a quick one") - 0.1, at("One, the model"), () => <Statement text="Four decisions, in the code." size={110} />, false),
  raw(at("One, the model") - 0.1, at("Client money"), "code_gate"),
  raw(at("Client money") - 0.1, at("Three, exactly once"), "code_login"),
  raw(at("Three, exactly once") - 0.1, at("Four, a bank"), "code_once"),
  S(at("Four, a bank") - 0.1, at("The old details stay"), () => <BankChange />),
  raw(at("The old details stay") - 0.1, at("And then approval"), "code_quarantine"),
  raw(at("And then approval") - 0.1, at("It all is done"), "code_hash"),
  raw(at("It all is done") - 0.1, at("Then I tried really hard"), "code_mcp"),
  raw(at("Then I tried really hard") - 0.1, at("fell for all"), "app_proof"),
  raw(at("fell for all") - 0.1, at("I fired 20"), "code_gauntlet"),
  S(at("I fired 20") - 0.1, at("tampered"), () => <Break from={8.38} />),
  S(at("tampered") - 0.1, at("I think you get"), () => <Break from={25.7} rate={0.6} />),
  face(at("I think you get"), at("The demo's live")),
  S(at("The demo's live") - 0.1, at("So back to my question"), () => <TryIt />),
  face(at("So back to my question"), CLOSE),
  S(CLOSE, TOTAL + END_CARD, () => <EndCard />, false),
  S(TOTAL + END_CARD, FILM, () => <Outro />, false),
];

// one punch line per beat, only where the number is the point
const BAMS: [number, number, string][] = [
  [at("three clients"), at("I hit run"), "3 employers · 3 Airwallex accounts"],
  [at("Those are real"), at("North Wind changed"), "real transfers · 201 SCHEDULED"],
  [at("North Wind changed"), at("So I wait"), "rate change → held for a human"],
  [at("exactly what's missing"), at("And here's a trap"), "short AUD 1,240.17"],
  [at("But that's Kestrel's"), at("So how does Harbor"), "Kestrel's USD 50,000 · not touched"],
  [at("Count, we take"), at("I press the button"), "1 pull · ≤ 85.72 USDZ · our wallet · 1 h"],
  [at("one coin more"), at("Then I tried a fake"), "+1 coin → refused on-chain"],
  [at("My code catches"), at("Even if someone"), "lookalike 0x4b4d668b… → refused"],
  [at("Not one cent"), at("This is real Airwallex"), "0 cents crossed between employers"],
  [at("Of course"), at("So here's a quick one"), "HTTP 401 credentials_invalid"],
  [at("fell for all"), at("I fired 20"), "28 attacks · $0 moved"],
  [at("paid exactly once"), at("tampered"), "20 at once · paid once"],
  [at("tampered"), at("500 random"), "200/200 tampered caught"],
  [at("500 random"), at("I think you get"), "500 runs · 420 tests"],
];

const CHAPTERS: [number, string][] = [
  [0, "01 THE PROBLEM"],
  [at("Let me show you"), "02 LIVE ON AIRWALLEX"],
  [at("Honestly"), "03 THE METAL MANDATE"],
  [at("Not one cent"), "04 PROOF"],
  [at("So here's a quick one"), "05 FOR ENGINEERS"],
  [at("One, the model"), "05 ENGINEERS · 1/4 MODEL NEVER TRUSTED"],
  [at("Client money"), "05 ENGINEERS · 2/4 ONE KEY PER EMPLOYER"],
  [at("Three, exactly once"), "05 ENGINEERS · 3/4 EXACTLY ONCE"],
  [at("Four, a bank"), "05 ENGINEERS · 4/4 BANK CHANGE QUARANTINED"],
  [at("And then approval"), "05 ENGINEERS · APPROVAL SIGNS THE BATCH HASH"],
  [at("It all is done"), "05 ENGINEERS · MCP, NO APPROVE TOOL"],
  [at("Then I tried really hard"), "06 BREAK IT"],
  [at("I think you get"), "07 TRY IT"],
];

const EndCard: React.FC = () => {
  const t = useT();
  return (
    <Stage>
      <AbsoluteFill style={{alignItems: "center", justifyContent: "center", gap: 26}}>
        <Rise text="Ringfence" size={150} weight={780} stagger={0} />
        <div style={{fontFamily: SANS, fontSize: 34, fontWeight: 600, color: C.ink, opacity: ramp(t, 0.9, 1.4)}}>Check it out</div>
        <div style={{fontFamily: MONO, fontSize: 30, color: C.ink, letterSpacing: "0.02em", opacity: ramp(t, 1.2, 1.7)}}>
          github.com/singhharsimar23-dotcom/ringefence
        </div>
        <div style={{fontFamily: MONO, fontSize: 24, color: C.mute, letterSpacing: "0.04em", opacity: ramp(t, 1.5, 2)}}>
          ringfence-hs23-eu.indiasouthcentral.cloudapp.azure.com
        </div>
        <div style={{fontFamily: MONO, fontSize: 18, color: C.dim, letterSpacing: "0.04em", opacity: ramp(t, 2.1, 2.6)}}>
          ledger head {short(FACTS.head ?? "", 16, 0).replace("…", "")} · every event hash-chained
        </div>
      </AbsoluteFill>
    </Stage>
  );
};

// one word at a time on black, each in its own script: in from a blur, out into one
const BYES: [string, number, number][] = [["bye", 0.5, 2.0], ["adiós", 2.2, 3.7], ["नमस्ते", 3.9, 5.7]];
const Outro: React.FC = () => {
  const t = useT();
  return (
    <AbsoluteFill style={{background: "#000", alignItems: "center", justifyContent: "center"}}>
      {BYES.map(([w, a, b]) => {
        const i = ramp(t, a, a + 0.55), o = ramp(t, b - 0.4, b);
        return t >= a && t < b ? (
          <div key={w} style={{position: "absolute", fontFamily: `${SANS}, "Nirmala UI"`, fontSize: 132, fontWeight: 600, letterSpacing: "-0.03em", color: "#f5f5f7",
            opacity: i * (1 - o), filter: `blur(${(1 - i) * 18 + o * 14}px)`, transform: `scale(${0.94 + 0.06 * i + 0.03 * o})`}}>{w}</div>
        ) : null;
      })}
    </AbsoluteFill>
  );
};

// ---- music: none under the story; the last bars of the track build under the close and resolve on the end card ----
const MUSIC_IN = at("So back to my question");
const TRACK = 294.46; // music.mp3 length, so its own ending lands on the last frame
const musicVol = (i: number) => {
  const t = MUSIC_IN + i / FPS;
  const out = 1 - ramp(t, FILM - 1.5, FILM, 0, 1, (x) => x);
  return t < CLOSE ? 0.1 * ramp(t, MUSIC_IN, MUSIC_IN + 2, 0, 1, (x) => x) : (0.1 + 0.25 * ramp(t, CLOSE, CLOSE + 0.6, 0, 1, (x) => x)) * out;
};

// subtitles step aside while big type already says the same words
const HIDE: [number, number][] = [...SHOTS.filter((s) => !s.subs).map((s) => [s.from, s.to] as [number, number]), [at("The agent suggests") - 0.2, at("and every client")]];
// his face rides along on everything except his own full-frame shots and the type cards
const NO_BUBBLE: [number, number][] = SHOTS.filter((s) => !s.subs || s.face).map((s) => [s.from, s.to]);

export const Film: React.FC = () => (
  <AbsoluteFill style={{background: C.bg}}>
    {SHOTS.map((s, i) => (
      <Sequence key={i} from={f(s.from)} durationInFrames={Math.max(1, f(s.to) - f(s.from))} layout="none">
        <AbsoluteFill style={{color: C.ink, fontFamily: SANS}}>{s.el(s.from)}</AbsoluteFill>
      </Sequence>
    ))}
    <FaceBubble hide={NO_BUBBLE} />
    <Chapter chapters={CHAPTERS} until={CLOSE} />
    <Bams lines={BAMS} />
    <Subs hide={HIDE} />
    <Audio src={staticFile("loom_cut.mp4")} />
    <Sequence from={f(MUSIC_IN)} layout="none">
      <Audio src={staticFile("music.mp3")} startFrom={f(TRACK - (FILM - MUSIC_IN))} volume={musicVol} />
    </Sequence>
  </AbsoluteFill>
);
