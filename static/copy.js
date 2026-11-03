/* Every word the page shows that the server does not send lives here. Plain, specific, no marketing. */
"use strict";

const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

/* Money is formatted from the API's decimal STRING. It is never parsed into a number. */
function fmtMoney(ccy, s) {
  const neg = String(s).startsWith("-");
  const [whole, frac = ""] = String(s).replace("-", "").split(".");
  const grouped = whole.replace(/\B(?=(\d{3})+(?!\d))/g, ",");
  return `${ccy} ${neg ? "-" : ""}${grouped}.${(frac + "00").slice(0, 2)}`;
}
const money = (ccy, s) => `<span class="ccy">${esc(ccy)}</span> <span class="amt">${esc(fmtMoney(ccy, s).slice(ccy.length + 1))}</span>`;
const totalsText = (t) => Object.entries(t || {}).sort().map(([c, a]) => fmtMoney(c, a)).join(" + ") || "nothing yet";

const STROKE = 'fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round"';
const svg = (d) => `<svg class="ico" viewBox="0 0 20 20" width="16" height="16" aria-hidden="true" ${STROKE}>${d}</svg>`;
const ICON = {
  check: svg('<path d="M4 10.5l4 4 8-9"/>'),
  clock: svg('<circle cx="10" cy="10" r="7"/><path d="M10 6v4.5l3 1.5"/>'),
  alert: svg('<path d="M10 3l8 14H2z"/><path d="M10 8.5v4"/><path d="M10 15v.01"/>'),
  lock: svg('<rect x="4" y="9" width="12" height="8" rx="2"/><path d="M7 9V6.5a3 3 0 016 0V9"/>'),
  arrow: svg('<path d="M3 10h13"/><path d="M12 6l4 4-4 4"/>'),
  shield: svg('<path d="M10 2.5l6.5 2.5v5c0 4-2.8 6.5-6.5 7.5C6.300 16.500 3.500 14 3.500 10V5z"/><path d="M7 10l2.200 2.200L13 8"/>'),
  return: svg('<path d="M8 5L3.500 9.500 8 14"/><path d="M4 9.500h8a4 4 0 010 8h-1"/>'),
  pause: svg('<path d="M7 4v12"/><path d="M13 4v12"/>'),
};
const TONE_ICON = { idle: "clock", amber: "alert", blue: "arrow", green: "check", red: "return" };

const RUN_LABEL = {
  DRAFT: "Draft", AWAITING_FUNDS: "Waiting for funds", AWAITING_APPROVAL: "Needs approval", READY: "Approved",
  RELEASING: "Sending", RELEASED: "Sent", DONE: "Done", HELD: "Held",
};
const PILL_ICON = { Planned: "clock", "Needs OK": "alert", "On its way": "arrow", Paid: "check", Returned: "return", Held: "pause" };
const PILL_CLASS = { Planned: "grey", "Needs OK": "amber", "On its way": "blue", Paid: "green", Returned: "red", Held: "red" };

const T = {
  publicDemo: "Shared sandbox demo. Test money only, on the Airwallex sandbox. Other visitors may be using it at the same time.",
  start: "Run Friday payroll", again: "Check inboxes now", pauseAll: "Pause all payouts", resumeAll: "Resume payouts",
  review: "Review and approve", reviewReturned: "Review returned payout", copyFunding: "Copy funding details",
  openProof: "Open proof page", resume: "Resume this run", hold: "Pause this run", close: "Close",
  holdToApprove: "Hold to approve", holding: "Keep holding", runTest: "Run this test", restore: "Restore the row",
  confirmCall: "Confirm by phone", copied: "Copied", viewRows: "View ledger rows",
  killConfirmTitle: "Pause all payouts?",
  killConfirmBody: "Nothing new will be sent. Payments already sent are still tracked until they land.",
  resetConfirm: "Archive this take and start a clean one? The old ledger stays verifiable in the archive.",
  emptyTimeline: "Nothing has happened yet. Run Friday payroll to start.",
  noRun: "No payroll run yet for this week.",
  loadError: "The page could not reach Ringfence. Check that the server is running, then reload.",
  actingAs: "Acting as", demoOnly: "demo only",
  simulated: "[SIMULATED]",
};

/* The demo script, one caption per beat (presenter mode). */
const BEATS = [
  "The problem: pool employers' money and one shortfall becomes everyone's problem.",
  "Run Friday payroll. Kestrel has no changes, so it pays by itself. Northwind needs one approval.",
  "Harbour is short. Another employer's deposit does not help it. Harbour's own top-up does.",
  "An email asks for new bank details and 3x pay. Ringfence holds the bank change and flags the email.",
  "A payout comes back after payment. Pay twice and one payment goes out. Drop the network and it is still one.",
  "Proof: each employer's money stayed in its own account. Edit one ledger row and verification fails there.",
];

const SIMULATED_CARDS = new Set(["bank_change_email", "network_drop", "tamper_ledger", "rate_move", "other_tenant_deposit", "harbour_topup", "late_return"]);
const CARD_ORDER = ["bank_change_email", "double_click", "network_drop", "tamper_ledger", "cross_tenant_call", "rate_move"];
const EVENT_ORDER = ["other_tenant_deposit", "harbour_topup", "late_return"];

const clock = (iso) => (iso ? new Date(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", hour12: false }) : "");
const clockSec = (iso) => (iso ? new Date(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false }) : "");
