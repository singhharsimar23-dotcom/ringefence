// Typed access to facts.json (written by video/facts.py from the live run). Everything on screen with an ID reads from here.
import raw from "./facts.json";

type Pull = {usdz: string; aud: string; tx: string; bind_tx: string; mandate: string; reference: string; expires_at: number};
type Refused = {code: string; usdz: string; tx: string; mandate: string; real?: string; to?: string; flag?: string};
const F = raw as unknown as {
  head: string; transfers: {tenant: string; id: string; request_id: string; amount: number; currency: string; short_reference_id?: string; status: string; create_http?: number; create_ms?: number}[];
  metal_pull: Pull[]; metal_refused: Refused[]; rows: {kind: string; payload: Record<string, unknown>}[];
  gauntlet: {evil: {fooled: number; expressible: number; money_moved: number}; claude: {fooled: number; expressible: number; model: string};
    storm: {parallel_releases: number; answers_lost: number; transfers_per_line: number[]; transfer_ids: string[]};
    sequences: {sequences: number; steps_run: number}; isolation: {directions: number}; tamper: {mutations: number; caught_at_the_right_row: number}; commit: string};
};
export const FACTS = F;
export const PULL = F.metal_pull[0];
export const OVER = F.metal_refused.find((r) => r.code === "mandate_cap_exceeded")!;
export const POISON = F.metal_refused.find((r) => r.code === "mandate_payee_not_listed")!;
export const APPROVAL = F.rows.find((r) => r.kind === "APPROVED" && r.payload.batch_hash)?.payload as {approver: string; role: string; batch_hash: string};
export const XFER = F.transfers[0];
export const short = (h: string, a = 6, b = 4) => (h.length > a + b + 1 ? `${h.slice(0, a)}…${h.slice(-b)}` : h);
