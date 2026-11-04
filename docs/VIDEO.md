# The film: "The Ledger Cut"

You speak `docs/SPEAK.md` once, straight through. Everything below is Claude's job.

## The idea

The best technical YouTube edits share three habits:
- every line has a literal picture of what is being said, as proof on screen;
- the picture never sits still for more than about 2 seconds;
- the cuts get shorter as the video goes on, until it hard-cuts to black, with white text over the music.

Ringfence has something those videos fake: **a real, hash-chained record of everything that happened.** So the ledger edits the film.

- **The chain strip.** A thin strip along the bottom of the frame. Each time something happens on screen (a transfer, a hold, a refusal on chain), a new block lands in it, showing the event and its real hash prefix from `/api/ledger`. It starts with one block every few seconds and races by the end. The tempo isn't a style choice: it's the proof piling up.
- **Receipts.** Each claim gets a stamp holding the real ID: `LIVE · AIRWALLEX` with the transfer ID, `ON CHAIN · METAL` with the tx hash, or `[SIMULATED]` where it's a sandbox simulation. That makes it visible that this is real work, not a mock-up.
- **No waiting on screen.** The agent working, the Metal pull and page loads are never shown in real time. We jump to the result, or show a 6-frame `· · ·`.

## Tempo

| Act | Spoken lines | Shot length | Sound | Chain strip |
|---|---|---|---|---|
| 1 · Open | "Hi, I'm…" to "…enforced by Airwallex itself." | 4–5 s | silence, then a low pulse | empty, then a first block |
| 2 · Friday | "Here's a real Friday…" to "Harbour waits." | 2.5–3 s | the pulse, ducked under your voice | a block every few seconds |
| 3 · Metal | "So how does Harbour…" to "…Not one cent crossed." | 2 s | the beat builds | the three Metal blocks land big, then shrink into the strip |
| 4 · Proof | "And it's not a mock-up…" to "…Not one rule broken." | 1–1.5 s, cut on every number | full beat | racing |
| 5 · End | "Don't trust me…" to the last line | hard cut | music holds | everything stops |

## Shots

Your face is full frame at four moments: "Hi, I'm", "This is the part I'm proudest of", "Then I tried to break it", and the last line. Everywhere else your Loom bubble sits bottom left.

| Spoken line | Picture |
|---|---|
| "Picture a payroll bureau…" | Black screen. White mono text types: `FRIDAY 16:58 · 3 CLIENTS · $0 OF IT OURS`. Then the landing hero fades up. |
| "Or an email says 'I've switched banks'" | The landing email scene, pushed in on the bank-detail line, with the accent highlight on it. |
| "The agent proposes. Code decides." | A board: an `AGENT` box, an arrow to a `CODE GATE` box, an arrow to `AIRWALLEX`. Each box pops in on its word. |
| "its own Airwallex account" | Three account boxes, each holding its real `acct_…` ID, with walls drawn between them. |
| "I press run." | The app clip: the click, then a jump cut to the three cards filled. |
| "Kestrel is clean, so it pays." | Push in on the Kestrel card. Stamp: `LIVE · AIRWALLEX · 1796e54e…`. A block lands. |
| "waits for a human" | The Northwind card, with an amber highlight on "Needs approval". |
| "Harbour is short" | The Harbour card. `AUD 1,240.17` punches in at 1.15x. |
| "fifty thousand dollars lands in Kestrel" | Kestrel's balance counts up. Harbour's card stays amber. Text over it: `Σ across clients: never`. |
| "a mandate, on chain" | A full-frame Metal card: the mandate's terms type on (`one pull · cap = shortfall · payee = platform`), each with its tick. |
| "That's a real transaction" | The app's chain block turns green, then a cut to the explorer URL text with the tx hash highlighted. Stamp: `ON CHAIN · METAL`. |
| "one coin more. The chain refuses." | A red block. `mandate_cap_exceeded` slams in. Flash 1 of 2. |
| "almost exactly like the real one" | The two addresses stacked, the matching ends lit and the differing middle in red. Then `mandate_payee_not_listed`. |
| "The blockchain is the second lock." | Two padlocks: `RINGFENCE` and `METAL`. |
| "Not one cent crossed." | All three cards green. The chain strip pauses, the beat drops out for 0.5 s, then comes back. |
| "Here it is in Airwallex." | Your 5 screenshots as a stack of captures, each pushed in, with the accent box on the same ID shown in the app. |
| "Airwallex itself says no." | `401 credentials_invalid`, big, with `12 / 12` counting up. |
| "Then I tried to break it." | Your face. |
| The quick-fire numbers | One number per cut: `28/28 fooled · 0 moved`, `Claude 0/28`, the storm diagram racing, `200/200`, `500`, `420`. The chain strip runs at its fastest. |
| "Try it." | The Try it clip: Live demo, the guide widget popping up, Red-team me. Cuts of 1 s. |
| The last line | Hard cut to black, and the music holds. White mono text: `ringfence`, then `0 cents crossed`, then the final chain head hash, then the URL. Hold 3 s, then out. |

## How it's built

- **Platform clips:** `scripts/capture.py`, as before. Each clip saves the second each step happens, so the edit can jump straight to results.
- **Graphics:** one HTML page in the site's own style (Geist, black, one accent) animated with the GSAP we already ship. A script renders it frame by frame with transparent frames, so every number and hash is real text pulled from `/api/ledger`, `/api/state` and `docs/gauntlet/results.json`, not typed in by hand.
- **Sync:** faster-whisper gives word timings from your Loom. Every cut and every block landing is placed on a spoken word.
- **Composite:** ffmpeg layers the clips with slow push-ins (1.00 to 1.06), the graphics, your bubble cropped from the Loom, then your voice plus the music. The music is ducked under your voice, normalised to -16 LUFS, and swells when your voice stops.

## Music (you pick it, about 2 minutes of listening)

You need a royalty-free track, from the YouTube Audio Library or Pixabay Music: dark, minimal electronic, around 110–125 BPM, building with a clear drop. Save it as `var/music.mp3`. Claude sets the volume and times the end card to it.

## Airwallex screenshots

After Claude's recording run, Claude sends you the IDs. Full window, 100% zoom, sandbox, into `var/shots/`:
1. the account switcher with all 4 accounts;
2. Harbour's AUD global account and its deposit;
3. Kestrel's Transfers list;
4. one transfer opened, showing its ID;
5. Developer > Events, the webhook for it.

## Honesty rules for the edit

- Every number on screen comes from a live run or the Gauntlet.
- `[SIMULATED]` is shown on the sandbox deposit.
- "Fooled 28" is always captioned as the agent built to obey, never Claude.
