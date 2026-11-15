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

  /* ---------- the graph workspace: one boundary per employer, payees outside it ---------- */
  const KIND_NODE = { RUN_CREATED: "inbox", AGENT_NOTE: "agent", PROPOSAL: "agent", ALERT: "agent", GATE_ALLOW: "rules", GATE_DENY: "rules",
    BENEFICIARY_QUARANTINED: "rules", FUNDING_REQUESTED: "funds", FUNDING_MATCHED: "funds", CALLBACK_CONFIRMED: "funds", FX_CONVERTED: "funds",
    APPROVED: "approve", HOLD: "approve", SUBMITTED: "pay", UNKNOWN: "pay", STATUS: "pay", RECONCILED: "pay", REOPENED: "pay", FEE_CHARGED: "pay", FEE_CREDIT: "pay" };
  const nodeOf = (r) => KIND_NODE[r.kind] || null;
  const PAYEE_STATE = { Paid: "done", Returned: "blocked", Held: "blocked", "On its way": "run" };

  /* how far a replay cursor has got for one employer: every step up to the furthest one reached, and the step of the cursor row */
  function reach(rows, cur) {
    let far = -1, refused = false;
    rows.forEach((r) => { const i = IDS.indexOf(nodeOf(r)); if (i > far) far = i; if (r.kind === "GATE_DENY" || r.kind === "BENEFICIARY_QUARANTINED") refused = true; });
    const ids = new Set(IDS.slice(0, far + 1));
    if (refused) ids.add("refused");
    if (ids.has("pay")) ids.add("payees");
    return { ids, cur: cur ? nodeOf(cur) : null };
  }

  const G = { DW: 152, DH: 52, NW: 160, NH: 84, PW: 184, PH: 56, BW: 160, BH: 60, GAP: 12, HEAD: 52, PAD: 24 };
  const COL = { docs: 24, agent: 236, rules: 436, funds: 636, approve: 836, pay: 1036 };
  const BOX_W = COL.pay + G.NW + G.PAD, PAY_X = BOX_W + 72, W = PAY_X + G.PW + 8;
  const stack = (n, h) => (n ? n * h + (n - 1) * G.GAP : 0);

  function edgeState(a, b) {
    if (b === "blocked") return "blocked";
    if (a === "run" || (a === "done" && (b === "run" || b === "you"))) return "live";
    if (a === "done" && b === "done") return "done";
    return "idle";
  }
  const curve = (x1, y1, x2, y2) => { const d = Math.max(28, Math.abs(x2 - x1) / 2); return `M${x1} ${y1} C${x1 + d} ${y1} ${x2 - d} ${y2} ${x2} ${y2}`; };
  const drop = (x1, y1, x2, y2) => { const d = Math.max(20, Math.abs(y2 - y1) / 2); return `M${x1} ${y1} C${x1} ${y1 + d} ${x2} ${y2 - d} ${x2} ${y2}`; };
  const box = (x, y, w, h) => `left:${x}px;top:${y}px;width:${w}px;height:${h}px`;

  /* lanes: [{t, name, sub, nodes, docs:[{label, sub, flag}], payees:[{name, amount (html), pill}], replay:{ids,cur}|null}]
     returns {html, w, h}. Every box is a button that selects a step, so the keyboard reaches all of it. */
  function graph(lanes, sel, tested) {
    const out = [], paths = [];
    let y = 0;
    lanes.forEach((L) => {
      const st = Object.fromEntries(L.nodes.map((n) => [n.id, n]));
      const docs = L.docs.length ? L.docs : [{ label: T.flow.nodes.inbox.name, sub: T.flow.nodes.inbox.kind }];
      const top = y + G.HEAD, span = Math.max(stack(docs.length, G.DH), stack(L.payees.length, G.PH), G.NH);
      const cy = top + span / 2, nyTop = cy - G.NH / 2, below = cy + G.NH / 2 + 44;
      const bottom = Math.max(top + span, below + G.BH) + G.PAD;
      const rp = L.replay, dim = (id) => (rp && !rp.ids.has(id) ? " dim" : ""), cur = (id) => (rp && rp.cur === id ? " cur" : "");
      const es = (a, b, idA, idB) => (rp && !rp.ids.has(idB) ? "idle" : edgeState(a, b)) + (rp && !rp.ids.has(idB) ? " dim" : "");
      out.push(`<div class="gbd" style="${box(0, y, BOX_W, bottom - y)}"><div class="gbh"><strong>${esc(L.name)}</strong><span>${esc(L.sub)}</span></div></div>`);
      out.push(`<p class="gpl" style="${box(PAY_X, y + 16, G.PW, 20)}">${esc(T.flow.payees)}</p>`);

      /* documents the agent was given */
      let dy = cy - stack(docs.length, G.DH) / 2;
      docs.forEach((d) => {
        out.push(`<button type="button" class="gn gd${d.flag ? " flag" : ""}${dim("inbox")}${cur("inbox")}${sel === "inbox" ? " sel" : ""}" data-fl="inbox" style="${box(COL.docs, dy, G.DW, G.DH)}">
          <span class="gt">${esc(d.label)}</span><span class="gs">${d.flag ? `<span class="gx">${esc(T.flow.flagged)}</span>` : esc(d.sub)}</span></button>`);
        paths.push([curve(COL.docs + G.DW, dy + G.DH / 2, COL.agent, cy), es(st.inbox.state === "idle" ? "idle" : "done", st.agent.state, "inbox", "agent")]);
        dy += G.DH + G.GAP;
      });

      /* the main steps */
      ["agent", "rules", "funds", "approve", "pay"].forEach((id, i, a) => {
        out.push(nodeBox(st[id], COL[id], nyTop, sel, tested, dim(id) + cur(id)));
        if (i < a.length - 1) paths.push([curve(COL[id] + G.NW, cy, COL[a[i + 1]], cy), es(st[id].state, st[a[i + 1]].state, id, a[i + 1])]);
      });

      /* the refused branch under Rules, the proof under Airwallex */
      const nref = st.rules.refused || 0, rx = COL.rules + (G.NW - G.BW) / 2;
      out.push(`<button type="button" class="gn gb ${nref ? "blocked" : "idle"}${dim("refused")}${sel === "rules" ? " sel" : ""}" data-fl="rules" style="${box(rx, below, G.BW, G.BH)}">
        <span class="gt">${dot(nref ? "blocked" : "idle")}${esc(T.flow.refusedName)}</span><span class="gs">${esc(nref ? T.flow.blocked.replace("{n}", nref) : T.flow.refusedNone)}</span></button>`);
      paths.push([drop(COL.rules + G.NW / 2, nyTop + G.NH, rx + G.BW / 2, below), nref ? `blocked${dim("refused")}` : "idle"]);
      const px = COL.pay + (G.NW - G.BW) / 2, pf = st.proof;
      out.push(`<button type="button" class="gn gb ${pf.state}${dim("proof")}${cur("proof")}${sel === "proof" ? " sel" : ""}" data-fl="proof" style="${box(px, below, G.BW, G.BH)}">
        <span class="gt">${dot(pf.state)}${esc(T.flow.nodes.proof.name)}</span><span class="gs">${esc(WORD(pf.state))}${tested && tested.has("proof") ? ` · ${esc(T.flow.tested)}` : ""}</span></button>`);
      paths.push([drop(COL.pay + G.NW / 2, nyTop + G.NH, px + G.BW / 2, below), es(st.pay.state === "done" ? "done" : "idle", pf.state, "pay", "proof")]);

      /* payees: outside the employer's box, reached only through Airwallex */
      let py = cy - stack(L.payees.length, G.PH) / 2;
      L.payees.forEach((p) => {
        const s = PAYEE_STATE[p.pill] || "idle";
        out.push(`<button type="button" class="gn gp ${s}${dim("payees")}${sel === "pay" ? " sel" : ""}" data-fl="pay" style="${box(PAY_X, py, G.PW, G.PH)}">
          <span class="gt"><span class="nm">${esc(p.name)}</span><span class="num">${p.amount}</span></span><span class="gs">${dot(s)}${esc(p.pill)}</span></button>`);
        paths.push([curve(COL.pay + G.NW, cy, PAY_X, py + G.PH / 2), rp && !rp.ids.has("payees") ? "idle dim" : s === "done" ? "done" : s === "blocked" ? "blocked" : s === "run" ? "live" : "idle"]);
        py += G.PH + G.GAP;
      });
      y = bottom + 40;
    });
    const h = Math.max(0, y - 40);
    const svg = `<svg class="ge" width="${W}" height="${h}" viewBox="0 0 ${W} ${h}" aria-hidden="true"><defs>${["idle", "done", "live", "blocked"].map((k) => `<marker id="ga-${k}" class="${k}" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="7" markerHeight="7" orient="auto"><path d="M0 0 L8 4 L0 8 z"/></marker>`).join("")}</defs>
      ${paths.map(([d, k]) => `<path class="${k}" d="${d}" marker-end="url(#ga-${k.split(" ")[0]})"/>`).join("")}</svg>`;
    return { html: `<div class="g" style="width:${W}px;height:${h}px">${svg}${out.join("")}</div>`, w: W, h };
  }

  function nodeBox(n, x, y, sel, tested, extra) {
    const t = T.flow.nodes[n.id];
    const metric = n.metric ? T.flow.metric[n.id].replace("{n}", n.metric) : "";
    return `<button type="button" class="gn gm ${n.state}${sel === n.id ? " sel" : ""}${extra}" data-fl="${n.id}" aria-pressed="${sel === n.id}" style="${box(x, y, G.NW, G.NH)}" aria-label="${esc(t.name)}: ${esc(WORD(n.state))}">
      <span class="gr">${esc(T.flow.role[n.id])}</span>
      <span class="gt">${dot(n.state)}${esc(t.name)}</span>
      <span class="gs">${esc(WORD(n.state))}${metric ? ` · <span class="num">${esc(metric)}</span>` : ""}${tested && tested.has(n.id) ? ` · ${esc(T.flow.tested)}` : ""}</span></button>`;
  }

  return { IDS, model, active, html, mini, graph, reach, nodeOf };
})();
if (typeof module !== "undefined") module.exports = Flow;
