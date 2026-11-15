"use strict";
/* The pipeline every payroll run goes through: Inbox, Agent, Rules, Funds, Approve, Airwallex, Proof.
   model() is a pure function of what the world already reports (lane state, ledger rows, calls, decisions), so a node test can run it.
   html() and mini() only draw. All words come from T.flow in copy.js. */
const Flow = (() => {
  const IDS = ["inbox", "agent", "rules", "funds", "approve", "pay", "proof"];
  const AFTER_APPROVAL = ["READY", "RELEASING", "RELEASED", "DONE"];
  const count = (rows, kinds) => rows.filter((r) => kinds.includes(r.kind)).length;

  /* lane: one entry of /api/state lanes (or null before the run starts)
     rows: ledger timeline rows for this employer. calls: /api/calls for this employer. dec: /api/decisions for this employer.
     busy: this employer's inbox is being read right now. proof: the proof report once every lane is DONE, else null. */
  function model({ lane, rows = [], calls = [], dec = [], busy = false, proof = null }) {
    const st = lane ? lane.state : null;
    const lines = lane ? lane.lines : [];
    const agentCalls = calls.filter((c) => c.kind === "claude" || c.kind === "rules_engine");
    const ok = dec.filter((d) => d.tone === "ok").length;
    const refused = dec.filter((d) => d.tone !== "ok").length;
    const paid = lines.filter((l) => l.pill === "Paid").length;
    const returned = lines.filter((l) => l.pill === "Returned").length;
    const sent = count(rows, ["SUBMITTED"]);
    const started = rows.length > 0 || !!st;
    const proposed = dec.length > 0 || count(rows, ["PROPOSAL", "AGENT_NOTE"]) > 0;
    const approved = AFTER_APPROVAL.includes(st) || count(rows, ["APPROVED"]) > 0;
    const done = st === "DONE";

    const node = (id, state, metric = "", edge = "") => ({ id, state, metric, edge });
    const inbox = node("inbox", started ? "done" : "idle", lines.length ? String(lines.length) : "", lines.length ? String(lines.length) : "");
    const agent = node("agent", busy ? "run" : proposed ? "done" : "idle", agentCalls.length ? String(agentCalls.length) : "", dec.length ? String(dec.length) : "");
    const rules = node("rules", proposed ? "done" : "idle", dec.length ? String(ok) : "", ok ? String(ok) : "");
    rules.ok = ok; rules.refused = refused;
    const short = st === "AWAITING_FUNDS" || !!(lane && lane.funding);
    const funds = node("funds", short ? "you" : proposed && st && st !== "DRAFT" ? "done" : "idle", lane && lane.funding ? lane.funding.currency : "", "");
    const held = st === "HELD";
    const approve = node("approve", st === "AWAITING_APPROVAL" || held ? "you" : approved ? "done" : "idle", "", approved ? "1" : "");
    const flying = approved && !done && returned === 0;
    const pay = node("pay", returned ? "blocked" : done ? "done" : flying || sent ? "run" : "idle", lines.length && approved ? `${paid}/${lines.length}` : "", paid ? String(paid) : "");
    const prf = node("proof", done && proof ? "done" : done ? "run" : "idle", "", "");
    return [inbox, agent, rules, funds, approve, pay, prf];
  }

  /* the node to look at now: the one that needs you, else the one running, else the last finished one */
  function active(nodes) {
    return (nodes.find((n) => n.state === "you") || nodes.find((n) => n.state === "run") || nodes.find((n) => n.state === "blocked")
      || [...nodes].reverse().find((n) => n.state === "done") || nodes[0]).id;
  }

  const WORD = (k) => T.flow.state[k];
  const dot = (s) => `<span class="fd ${s}" aria-hidden="true">${s === "blocked" ? "×" : ""}</span>`;
  const arrow = (on, going) => `<svg class="fe ${on ? "on" : ""} ${going ? "go" : ""}" viewBox="0 0 40 8" aria-hidden="true" preserveAspectRatio="none"><line x1="0" y1="4" x2="34" y2="4"/><polyline points="30,1 35,4 30,7"/></svg>`;

  /* esc is a global from copy.js; `sel` is the selected node id; `ids` lets the caller mark nodes that carry a scenario result */
  function nodeHtml(n, sel, tested) {
    const t = T.flow.nodes[n.id];
    const metric = n.metric ? T.flow.metric[n.id].replace("{n}", n.metric) : "";
    const warn = n.id === "rules" && n.refused ? `<span class="fb">${esc(T.flow.blocked.replace("{n}", n.refused))}</span>` : "";
    return `<li class="fn ${n.state} ${sel === n.id ? "sel" : ""}"><button type="button" data-fl="${n.id}" aria-pressed="${sel === n.id}" aria-label="${esc(t.name)}: ${esc(WORD(n.state))}">
      <span class="fh">${dot(n.state)}<span class="nm">${esc(t.name)}</span></span>
      <span class="fk">${esc(t.kind)}</span>
      <span class="fs">${esc(WORD(n.state))}${metric ? ` · <span class="num">${esc(metric)}</span>` : ""}</span>${warn}${tested && tested.has(n.id) ? `<span class="ft">${esc(T.flow.tested)}</span>` : ""}</button></li>`;
  }

  /* one row of connected nodes; the arrow after a node is lit once that node is done, and moves while it runs */
  function row(nodes, sel, tested) {
    return `<ol class="flow">${nodes.map((n, i) => `${nodeHtml(n, sel, tested)}${i < nodes.length - 1 ? `<li class="fa" aria-hidden="true">${arrow(n.state === "done", n.state === "run")}</li>` : ""}`).join("")}</ol>`;
  }

  /* lanes: [{name, nodes}]. One row per employer, and no arrow ever joins two rows. */
  function html(lanes, sel, tested) {
    return `<div class="flowbox">${lanes.map((l) => `${lanes.length > 1 ? `<h3 class="fl">${esc(l.name)}</h3>` : ""}${row(l.nodes, sel, tested)}`).join("")}
      ${lanes.length > 1 ? `<p class="small muted fnote">${esc(T.flow.separate)}</p>` : ""}</div>`;
  }

  /* small strip for the three-employer cards */
  function mini(nodes) {
    const a = active(nodes);
    return `<ol class="mini" aria-label="${esc(T.flow.title)}">${nodes.map((n) => `<li class="${n.state} ${n.id === a ? "cur" : ""}" title="${esc(T.flow.nodes[n.id].name)}: ${esc(WORD(n.state))}">${dot(n.state)}<span>${esc(T.flow.nodes[n.id].name)}</span></li>`).join("")}</ol>`;
  }

  return { IDS, model, active, html, mini };
})();
if (typeof module !== "undefined") module.exports = Flow;
