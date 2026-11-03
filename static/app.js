"use strict";
const $ = (s, el = document) => el.querySelector(s);
const TENANTS = ["northwind", "kestrel", "harbour"];
const qs = new URLSearchParams(location.search);
const PRESENT = qs.get("present") === "1";
if (PRESENT) document.body.classList.add("present");

Object.assign(ICON, {
  link: svg('<path d="M8 12l4-4"/><path d="M9 5.500l1-1a3 3 0 014.200 4.200l-1 1"/><path d="M11 14.500l-1 1a3 3 0 01-4.200-4.200l1-1"/>'),
  spark: svg('<path d="M10 2.500v15"/><path d="M3.500 6.250l13 7.500"/><path d="M3.500 13.750l13-7.500"/>'),
  more: svg('<path d="M5 8l5 5 5-5"/>'),
});

let S = null, TL = [], filter = "all", view = "pay", PROOF = null, busy = false, lastVer = null;
let pendingStart = false, tlSeen = -1, warnShown = "", whoKey = "", RULE = null, RULE_T = null, RULE_TEXT = "";
const expanded = {};
const cap = (s) => (s ? s[0].toUpperCase() + s.slice(1) : "");
const mid = (s, a = 9, b = 4) => (String(s).length > a + b + 1 ? `${String(s).slice(0, a)}…${String(s).slice(-b)}` : String(s));
const modelName = (m) => { const p = String(m).replace("claude-", "").split("-"); return `${cap(p[0])} ${p.slice(1).join(".")}`.trim(); };
const roleLabel = (u) => (u.role === "operator" ? "Operator" : `${cap(u.tenant)} Finance`);
const me = () => localStorage.getItem("rf_user") || "maya";
const nm = (t) => ((S && S.employers && S.employers[t]) || {}).name || cap(String(t));  // display names come from /api/state
const hasRunNow = () => S && TENANTS.some((t) => S.lanes[t].state);

/* ---------- plumbing ---------- */
async function api(path, body) {
  const opt = body === undefined ? {} : { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(body) };
  const r = await fetch(path, opt);
  let j = null;
  try { j = await r.json(); } catch (_) { /* non-JSON error page */ }
  if (!r.ok) {
    const d = j && j.detail;  // a list of {field, message} comes from the playground form checks
    const e = new Error(Array.isArray(d) ? d.map((x) => x.message || x.msg).join(" ") : d || `Request failed (${r.status}).`);
    e.status = r.status; e.detail = d; throw e;
  }
  return j;
}
let toastTimer;
function toast(msg) {
  const t = $("#toast"); t.textContent = msg; t.classList.add("on");
  clearTimeout(toastTimer); toastTimer = setTimeout(() => t.classList.remove("on"), 4200);
}
async function doAct(path, body, okMsg) {
  if (busy) return null;
  busy = true; render();
  try { const r = await api(path, { user: me(), ...body }); if (okMsg) toast(okMsg); return r; }
  catch (e) { toast(e.message); return null; }
  finally { busy = false; await refresh(); }
}

/* ---------- refresh ---------- */
async function refresh() {
  if (view === "try") return;  // the demo's state is not needed on the playground pages
  if (qs.get("state") === "loading") return render();
  try {
    if (qs.get("state") === "error") throw new Error("fixture");
    S = await api("/api/state");
    const after = TL.length ? TL[TL.length - 1].detail.seq : 0;
    TL = TL.concat(await api(`/api/timeline?after=${after}`)).slice(-300);
    if (S.head < after) { TL = await api("/api/timeline?after=0"); tlSeen = -1; }  // a reset restarts the ledger
    $("#errbar").hidden = true;
  } catch (e) {
    $("#errbar").hidden = false; $("#errbar").textContent = T.loadError;
  }
  render();
  if (view === "proof") loadProof();
}
function connect() {
  let fallback = setInterval(refresh, 4000);
  try {
    const es = new EventSource("/events");
    es.addEventListener("tick", (ev) => { if (ev.data === lastVer) return; lastVer = ev.data; refresh(); });
    es.onopen = () => clearInterval(fallback);
    es.onerror = () => { clearInterval(fallback); fallback = setInterval(refresh, 4000); };
  } catch (_) { /* polling only */ }
}

/* ---------- render ---------- */
function render() {
  document.body.classList.toggle("v-try", view === "try");
  for (const v of ["try", "pay", "rules", "proof"]) {
    $(`#view-${v}`).hidden = view !== v;
    if (view === v) $(`#tab-${v}`).setAttribute("aria-current", "page"); else $(`#tab-${v}`).removeAttribute("aria-current");
  }
  renderStatic();
  if (view === "try") return;  // the playground draws itself (play.js)
  if (!S) {
    $("#lanes").innerHTML = TENANTS.map(() => `<div class="lane" aria-busy="true"><div class="skel" style="width:60%"></div><div class="skel"></div><div class="skel" style="width:40%"></div></div>`).join("");
    return;
  }
  renderTop();
  if (view === "rules") renderRules();
  renderBanners(); renderIntro(); renderRail(); renderNaive(); renderLanes(); renderCards(); renderTimeline();
}
function renderStatic() {
  $("#kill").textContent = T.stopAll;
  $("#m-startover").textContent = T.startOver; $("#m-presenter").textContent = PRESENT ? "Leave presenter mode" : T.presenter;
  $("#m-details").textContent = document.body.classList.contains("details") ? T.hideDetails : T.showDetails;
  $("#brk").textContent = T.breakTitle; $("#brk-sub").textContent = T.breakSub; $("#ev-title").textContent = T.eventsTitle;
  $("#act-title").textContent = T.activityTitle;
}
function renderTop() {
  const live = S.backend === "live";
  $("#live").innerHTML = `<span class="dot ${live ? "" : "off"}"></span>${esc(live ? T.live : T.offline)}`;
  const scripted = S.agent === "offline agent" || S.agent_capped;
  const label = S.agent_capped ? T.agentCapped : scripted ? T.offlineRules : `Claude ${modelName(S.model || "")}`;
  $("#agent").innerHTML = `${S.agent_busy ? '<span class="dot busy"></span>' : ""}${scripted ? "" : ICON.spark}${esc(label)}`;
  $("#agent").title = scripted ? "The rules engine prepares the payroll. No model is called." : "Claude proposes. Code decides amounts, limits and request ids.";
  const u = S.users.find((x) => x.id === me()) || S.users[0];
  $("#who-btn").innerHTML = `<span class="avatar">${esc(u.id.slice(0, 2).toUpperCase())}</span><span>${esc(cap(u.id))}</span><span class="muted hide-sm">${esc(roleLabel(u))}</span>${ICON.more}`;
  const key = S.users.map((x) => x.id).join() + me();
  if (key !== whoKey) {
    whoKey = key;
    $("#pop-who").innerHTML = `<span class="small muted" style="padding:4px 12px">${esc(T.actingAs)} (${esc(T.demoOnly)})</span>` + S.users.map((x) =>
      `<button role="menuitemradio" aria-checked="${x.id === me()}" data-act="as" data-u="${esc(x.id)}"><span class="avatar">${esc(x.id.slice(0, 2).toUpperCase())}</span>${esc(cap(x.id))} <span class="muted">${esc(roleLabel(x))}</span></button>`).join("");
  }
  $("#kill").hidden = S.kill.on;
  $("#act-btn").hidden = view !== "pay";
  $("#act-btn").textContent = `${T.activity} (${TL.length})`;
}
function renderBanners() {
  const pb = $("#pubbar"); pb.hidden = !S.public; pb.textContent = S.public ? T.publicDemo : "";
  const kb = $("#killbar");
  kb.hidden = !S.kill.on;
  kb.innerHTML = S.kill.on ? `${ICON.pause}<span class="grow">All payments are stopped${S.kill.by ? ` by ${esc(S.kill.by)}` : ""}. Nothing new will be sent.</span><button data-act="unkill">${T.resumeAll}</button>` : "";
  const wb = $("#warnbar");
  wb.hidden = !S.error || S.error === warnShown;
  wb.innerHTML = wb.hidden ? "" : `${ICON.alert}<span class="grow">${esc(S.error)}</span><button data-act="warn-close">${T.dismiss}</button>`;
}
function renderIntro() {
  const el = $("#intro"), seen = localStorage.getItem("rf_intro_seen") === "1" || PRESENT;
  el.hidden = seen;
  if (!seen) el.innerHTML = `<ol>${T.intro.map((x) => `<li>${esc(x)}</li>`).join("")}</ol><button class="quiet" data-act="intro-close">${T.dismiss}</button>`;
}

/* progress rail + the one next action */
function stepNow() {
  const st = TENANTS.map((t) => S.lanes[t].state);
  if (st.some((s) => !s || s === "DRAFT")) return 1;
  if (st.every((s) => s === "DONE")) return 4;
  if (st.some((s) => ["AWAITING_APPROVAL", "AWAITING_FUNDS", "HELD"].includes(s))) return 2;
  return 3;
}
function nextAction() {
  if (S.agent_busy) return { text: `${S.agent === "offline agent" || S.agent_capped ? T.rulesReading : T.claudeReading} ${nm(S.agent_busy)}'s inbox` };
  if (!hasRunNow()) return pendingStart && !S.error ? { text: T.preparing } : { label: T.start, act: "start" };
  if (TENANTS.some((t) => !S.lanes[t].state)) return pendingStart && !S.error ? { text: T.preparing } : { label: T.again, act: "start" };
  pendingStart = false;
  for (const t of TENANTS) {
    const l = S.lanes[t], a = l.text.action;
    if (a === "approve") return { label: `Review ${nm(t)}`, act: "review", t };
    if (a === "review") return { label: `${T.reviewReturned}: ${nm(t)}`, act: "review", t };
    if (a === "copy_funding" && l.funding) return { label: `Fund ${nm(t)}`, copy: l.funding.reference };
    if (a === "resume") return { label: `Resume ${nm(t)}`, act: "resume", t };
  }
  if (stepNow() === 4) return { label: T.seeProof, act: "proof" };
  return { text: "Money is moving. Ringfence checks each payment with Airwallex." };
}
function renderRail() {
  const cur = stepNow();
  $("#rail").innerHTML = T.steps.map((s, i) => {
    const done = i + 1 < cur || cur === 4, here = i + 1 === cur;
    return `<li class="${done ? "done" : ""}" ${here ? 'aria-current="step"' : ""}><span class="n">${done ? ICON.check : i + 1}</span><span class="lbl">${esc(s)}</span></li>`;
  }).join("");
  const n = nextAction();
  $("#next").innerHTML = n.text
    ? `<span class="status-text" aria-live="polite">${S.agent_busy ? '<span class="dot busy"></span>' : ""}${esc(n.text)}</span>`
    : `<button class="primary" ${n.copy ? `data-copy="${esc(n.copy)}"` : `data-act="${n.act}" ${n.t ? `data-t="${n.t}"` : ""}`} ${busy ? "disabled" : ""}>${esc(n.label)}</button>`;
}
function renderNaive() {
  const el = $("#naive"), n = S.naive;
  el.hidden = !n || !S.lanes.harbour.funding;
  if (el.hidden) return;
  const amt = `<s>${esc(fmtMoney(n.currency, n.amount))}</s>`;
  el.innerHTML = n.covers
    ? `<span>${esc(T.pooled)}</span> ${amt}. <strong>${esc(T.pooledRefused)}</strong>`
    : `<span>${esc(T.pooledShort)}</span> ${amt} <span>${esc(T.pooledShortEnd)}</span><span class="real">${esc(T.pooledOwn)}</span>`;
}

/* lanes */
const pillHtml = (p) => `<span class="pill ${PILL_CLASS[p] || "grey"}">${ICON[PILL_ICON[p]] || ""}${esc(p)}</span>`;
const copyBtn = (v) => `<button class="quiet" data-copy="${esc(v)}" aria-label="Copy ${esc(v)}">Copy</button>`;
function sums(lines) {  // BigInt cents: no floats near money
  const m = {};
  for (const ln of lines) { const [w, f = ""] = String(ln.amount).split("."); m[ln.currency] = (m[ln.currency] || 0n) + BigInt(w + (f + "00").slice(0, 2)); }
  return Object.entries(m).sort().map(([c, v]) => [c, `${v / 100n}.${String(v % 100n).padStart(2, "0")}`]);
}
function fundingHtml(f, t) {
  if (!f) return "";
  const acct = f.account_number || f.iban || "";
  const rows = [["Pay into", `${nm(t)}'s own ${f.currency} account`], ["Account", acct], [(f.routing_type || "Routing").toUpperCase(), f.routing_value || ""], ["Reference", f.reference], [T.fundNeed, fmtMoney(f.currency, f.amount)]];
  return `<div class="funding" aria-label="${T.fundTitle}">${rows.filter((r) => r[1]).map((r) => `<div class="row"><span>${esc(r[0])}</span><span class="num">${esc(r[1])}${["Account", "Reference", T.fundNeed].includes(r[0]) ? " " + copyBtn(r[0] === T.fundNeed ? f.amount : r[1]) : ""}</span></div>`).join("")}</div>`;
}
function noteHtml(t, l) {
  const n = l.agent_note;
  if (l.state === "DONE") return ""; // the note describes the last tick, which is stale once paid
  if (S.agent_busy === t) return `<div class="note" aria-busy="true"><div class="skel" style="width:70%"></div><div class="skel"></div></div>`;
  if (!n) return `<div class="note"><p class="muted">${T.noNote}</p></div>`;
  const long = n.explanation.length > 100, open = expanded[t];
  return `<div class="note ${open ? "open" : ""}"><p class="who"><span>${n.mode === "claude" ? "Claude" : "Rules engine"}:</span> ${esc(n.headline)}</p>
    ${n.explanation ? `<p class="expl">${esc(n.explanation)}</p>` : ""}${long ? `<button class="link" data-act="more" data-t="${t}">${open ? T.less : T.more}</button>` : ""}</div>`;
}
function laneHtml(t) {
  const l = S.lanes[t], x = l.text;
  const f = l.funding;
  const act = { approve: `<button class="primary" data-act="review" data-t="${t}" ${busy ? "disabled" : ""}>${T.review}</button>`,
    copy_funding: `<button class="primary" data-copy="${esc(f ? f.reference : "")}">${T.copyFunding}</button>`,
    review: `<button class="primary" data-act="review" data-t="${t}">${T.reviewReturned}</button>`,
    proof: `<a class="btn primary" href="#/proof">${T.openProof}</a>`,
    resume: `<button class="primary" data-act="resume" data-t="${t}">${T.resume}</button>` }[x.action] || "";
  const hold = l.state && ["AWAITING_APPROVAL", "READY", "AWAITING_FUNDS"].includes(l.state) ? `<button data-act="hold" data-t="${t}">${T.hold}</button>` : "";
  const tone = { idle: "grey", amber: "amber", blue: "blue", green: "green", red: "red" }[x.tone] || "grey";
  const fx = l.path.fx.length ? `<div class="fxpath">${l.path.fx.map((g) => `${esc(g.sell)} ${ICON.arrow} ${esc(g.buy)}`).join(" · ")}</div>` : "";
  const amount = l.lines.length ? `<div class="amount" aria-label="Total">${sums(l.lines).map(([c, a]) => `<span>${money(c, a)}</span>`).join("")}</div>${fx}` : "";
  const wallet = Object.keys(l.wallet).length ? `<div class="wallet" aria-label="Own wallet">${Object.entries(l.wallet).map(([c, a]) => `<span class="chip num">${esc(fmtMoney(c, a))}</span>`).join("")}</div>` : "";
  const rows = l.lines.length ? `<ul class="lines">${l.lines.map((ln) => `<li><span class="nm" title="${esc(ln.name)}">${esc(ln.name)}</span><span class="num">${money(ln.currency, ln.amount)}</span>${pillHtml(ln.pill)}<a class="btn quiet" href="${esc(ln.track)}" target="_blank" rel="noopener" title="${T.contractorLink}" aria-label="${T.contractorLink}: ${esc(ln.name)}">${ICON.link}</a><span class="detail" title="${esc(ln.request_id)}">${esc(mid(ln.request_id, 10, 6))}</span></li>`).join("")}</ul>` : "";
  return `<article class="lane" data-t="${t}" aria-label="${esc(l.name)}">
    <div class="lane-head"><div class="row"><h2>${esc(l.name)}</h2><span class="mono muted" title="${esc(l.account)}">${esc(mid(l.account))}</span></div>
      <div class="meta">${ICON.lock}<span>${T.walled}</span></div></div>
    <div class="status"><span class="pill ${tone}">${ICON[TONE_ICON[x.tone]] || ICON.clock}${esc(l.state ? RUN_LABEL[l.state] : "No run")}</span><span class="txt">${esc(x.status)}</span></div>
    <p class="muted small">${esc(x.next)}</p>
    <div class="lane-body"><div class="col">${noteHtml(t, l)}${amount}${wallet}</div><div class="col">${fundingHtml(f, t)}${rows}</div></div>
    <div class="lane-foot">${act}${hold}</div></article>`;
}
function renderLanes() { $("#lanes").innerHTML = TENANTS.map(laneHtml).join(""); }

/* attacks */
function renderCards() {
  const byId = Object.fromEntries(S.scenarios.map((s) => [s.id, s]));
  const card = (id, i) => {
    const s = byId[id]; if (!s) return "";
    const r = s.last, tamperOn = id === "tamper_ledger" && r && r.bad_seq != null;  // only the edit result carries bad_seq
    return `<div class="card" data-id="${id}"><div class="title"><span>${esc(s.title)}</span>${PRESENT && i !== undefined ? `<span class="key">${i + 1}</span>` : ""}</div>
      <p class="line">${esc(s.line)}${SIMULATED_CARDS.has(id) ? ` <span class="chip sim">${T.simulated}</span>` : ""}</p>
      ${r ? `<div class="result"><div class="verdict ${r.ok ? "ok" : "no"}">${r.ok ? ICON.check : ICON.alert}<span>${esc(r.summary)}</span></div><p>${esc(r.defence || "")}</p>${(r.seqs || []).length ? `<button class="link" data-act="rows" data-id="${id}">${T.viewRows}</button>` : ""}</div>` : ""}
      <div class="acts"><button data-act="scenario" data-id="${id}" ${busy ? "disabled" : ""}>${tamperOn ? T.restore : T.runTest}</button></div></div>`;
  };
  $("#cards").innerHTML = CARD_ORDER.map(card).join("");
  $("#events").innerHTML = EVENT_ORDER.map((id) => card(id)).join("");
}

/* activity */
const chips = () => [["all", T.fAll], ...TENANTS.map((t) => [t, nm(t)]), ["blocked", T.fBlocked]];
function renderTimeline() {
  $("#chips").innerHTML = chips().map(([k, v]) => `<button data-act="filter" data-k="${k}" aria-pressed="${filter === k}">${v}</button>`).join("");
  const rows = TL.filter((r) => filter === "all" || (filter === "blocked" ? r.blocked : r.tenant === filter));
  $("#tlcount").textContent = `${rows.length} of ${TL.length}`;
  const ol = $("#tl");
  const stick = ol.scrollTop + ol.clientHeight >= ol.scrollHeight - 30;
  ol.innerHTML = rows.length ? rows.map((r) => {
    const d = r.detail || {}, isNew = tlSeen >= 0 && d.seq > tlSeen;
    const det = Object.entries(d).map(([k, v]) => `${k} ${k === "request_id" ? mid(v, 10, 6) : v}`).join(" · ");
    return `<li class="${r.blocked ? "blocked" : r.tenant ? "mine-" + r.tenant : ""} ${isNew ? "new" : ""}"><time>${clockSec(r.ts)}</time><span><span class="phase ${r.phase}">${r.phase}</span><br>${esc(r.text)}</span><span class="detail">${esc(det)}</span></li>`;
  }).join("") : `<li class="empty">${TL.length ? T.emptyFilter : T.emptyTimeline}</li>`;
  if (TL.length) tlSeen = TL[TL.length - 1].detail.seq;
  if (stick) ol.scrollTop = ol.scrollHeight;
}

/* ---------- dialogs ---------- */
function closeDlg(d) {
  if (!d.open) return;
  d.classList.add("closing");
  setTimeout(() => { d.close(); d.classList.remove("closing"); }, 150);
}
document.querySelectorAll("dialog").forEach((d) => d.addEventListener("cancel", (e) => { e.preventDefault(); closeDlg(d); }));
function ask(title, body, yes) {
  const d = $("#dlg-ask");
  d.innerHTML = `<header><h2 id="ask-title">${esc(title)}</h2></header><div class="body"><p>${esc(body)}</p></div><footer><button data-close>${T.close}</button><button class="primary" id="ask-yes">${esc(yes)}</button></footer>`;
  d.showModal();
  return new Promise((res) => { $("#ask-yes").onclick = () => { closeDlg(d); res(true); }; d.onclose = () => res(false); });
}
function diffHtml(d) {
  if (!d) return `<p class="empty">Still preparing this batch.</p>`;
  const rows = [];
  d.changes.forEach((c) => rows.push(`<div class="diff-row ${c.kind === "amount" && Math.abs(parseFloat(c.pct)) > 25 ? "red" : ""}"><span>${esc(c.name)}: ${c.kind === "new" ? "new payee" : `was ${esc(fmtMoney(c.currency, c.previous))} (${esc(c.pct)}%)`}</span><span class="num">${money(c.currency, c.amount)}</span></div>`));
  d.bank_changes.forEach((b) => rows.push(`<div class="diff-row red"><span>${esc(b.name)}: new bank details ending ${esc(b.last4)} (${esc(b.status.toLowerCase())})</span><span>${b.status === "PENDING" ? "Not paid until confirmed" : esc(b.status.toLowerCase())}</span></div>`));
  d.rate_requests.forEach((r) => rows.push(`<div class="diff-row red"><span>${esc(r.name || r.contractor_id || "A contractor")} asked for a new rate. Not applied.</span><span class="num">${esc(r.new_rate || "")}</span></div>`));
  rows.push(`<div class="diff-row fold"><span>${d.unchanged.count} unchanged</span><span class="num">${esc(totalsText(d.unchanged.totals))}</span></div>`);
  d.fx.forEach((g) => rows.push(`<div class="diff-row"><span>Convert ${esc(g.sell)} to ${esc(g.buy)} inside this account at ${esc(g.rate)}${g.band_bps != null ? ` (limit ${g.band_bps} bps)` : ""}</span><span class="num">${esc(fmtMoney(g.buy, g.buy_amount))}</span></div>`));
  return rows.join("");
}
function switchTarget(l) {  // the person who may sign this batch, when the current user may not
  const cur = S.users.find((u) => u.id === me());
  if (!cur || !l.diff || cur.role === l.diff.approver_role) return null;
  return S.users.find((u) => u.role === l.diff.approver_role) || null;
}
const switchLabel = (u, tail) => `${T.switchTo} ${cap(u.id)} (${cap(u.tenant)} Finance) ${tail}`;
function openApprove(t) {
  const l = S.lanes[t], d = $("#dlg-approve"), who = S.users.find((u) => u.id === me()), sw = switchTarget(l);
  const base = sw ? switchLabel(sw, T.andApprove) : T.holdToApprove;
  d.innerHTML = `<header><h2 id="ap-title">${esc(l.name)}: ${T.approveFor}</h2><button class="quiet" data-close aria-label="${T.close}">${T.close}</button></header>
    <div class="body"><p class="muted">Acting as ${esc(who ? `${cap(who.id)} (${roleLabel(who)})` : me())}. Only ${esc(nm(t))} ${T.onlyFinance}${l.diff ? ` Approver: ${esc(l.diff.approver_role.split(":").pop())}.` : ""}</p>${diffHtml(l.diff)}
    <div class="diff-row"><strong>Total</strong><strong class="num">${esc(l.diff ? totalsText(l.diff.totals) : "")}</strong></div></div>
    <footer><button data-close>${T.close}</button><button class="primary hold" id="hold-ok" ${l.diff ? "" : "disabled"}><span class="fill"></span><span class="lbl">${esc(base)}</span></button></footer>`;
  const bk = d.querySelector(".body");
  l.diff && l.diff.bank_changes.filter((b) => b.status === "PENDING").forEach((b) => {
    bk.insertAdjacentHTML("beforeend", `<div class="diff-row"><span>Confirm ${esc(b.name)}'s new details by phone (someone other than the requester)</span><button data-act="confirm" data-t="${t}" data-q="${b.id}" ${sw ? `data-sw="${esc(sw.id)}"` : ""}>${esc(sw ? switchLabel(sw, T.andConfirm) : T.confirmCall)}</button></div>`);
  });
  d.showModal();
  holdToApprove($("#hold-ok"), base, () => {
    closeDlg($("#dlg-approve"));
    if (sw) { localStorage.setItem("rf_user", sw.id); whoKey = ""; }
    doAct("/api/approve", { tenant: t }, `Approved ${nm(t)}.`);
  });
}
function holdToApprove(btn, base, onDone) {
  const fill = btn.querySelector(".fill"), label = btn.querySelector(".lbl");
  let start = 0, raf = 0, done = false;
  const tick = () => {
    const p = Math.min(1, (performance.now() - start) / 800); fill.style.clipPath = `inset(0 ${100 - p * 100}% 0 0)`;
    if (p >= 1) {
      done = true; cancelAnimationFrame(raf); onDone(); return;
    }
    raf = requestAnimationFrame(tick);
  };
  const down = (e) => {
    if (done || btn.disabled || start) return;
    if (e.type === "keydown" && e.key !== " " && e.key !== "Enter") return;
    if (e.repeat) return;
    fill.classList.remove("rel"); start = performance.now(); label.textContent = T.holding; raf = requestAnimationFrame(tick);
  };
  const up = () => {
    if (done || !start) return;
    cancelAnimationFrame(raf); start = 0; fill.classList.add("rel"); fill.style.clipPath = ""; label.textContent = base;
  };
  btn.addEventListener("pointerdown", down); btn.addEventListener("keydown", down);
  ["pointerup", "pointerleave", "keyup", "blur"].forEach((n) => btn.addEventListener(n, up));
}
function openRows(id) {
  const seqs = (S.scenarios.find((s) => s.id === id).last || {}).seqs || [];
  api(`/api/ledger?seqs=${seqs.slice(0, 50).join(",")}`).then((rows) => {
    const d = $("#dlg-rows");
    d.innerHTML = `<header><h2 id="rows-title">Ledger rows</h2><button class="quiet" data-close>${T.close}</button></header><div class="body">${rows.map((r) => `<div><strong>#${r.seq} ${esc(r.kind)}</strong> <span class="detail" style="display:inline" title="${esc(r.hash)}">${esc(mid(r.hash, 8, 6))}</span> ${copyBtn(r.hash)}<pre>${esc(JSON.stringify(r.payload, null, 1))}</pre></div>`).join("") || "<p>No rows.</p>"}</div>`;
    d.showModal();
  }).catch((e) => toast(e.message));
}

/* ---------- rules ---------- */
function renderRules() {
  const el = $("#view-rules"), u = S && S.users.find((x) => x.id === me());
  const t = RULE_T || (u && u.tenant) || "northwind";
  if (el.dataset.ready !== t) {
    el.dataset.ready = t; RULE = null;
    el.innerHTML = `<div class="two"><div class="panel" data-t="${t}"><header><h2>${T.rulesTitle}</h2>
      <select id="rule-t" aria-label="Employer">${TENANTS.map((x) => `<option value="${x}" ${x === t ? "selected" : ""}>${esc(nm(x))}</option>`).join("")}</select></header>
      <p class="muted">${T.rulesHint}</p>
      <textarea id="rule-text" rows="4" maxlength="600" aria-label="Rule">${esc(RULE_TEXT)}</textarea>
      <div class="chips" aria-label="Examples">${T.examples.map((x, i) => `<button data-act="example" data-i="${i}">${esc(x)}</button>`).join("")}</div>
      <div class="actions"><button class="primary" data-act="rule-draft">${T.preview}</button></div></div>
      <div class="panel" id="rule-out"></div></div>`;
  }
  if (!RULE) { $("#rule-out").innerHTML = `<p class="muted">${T.previewEmpty}</p>`; return; }
  const d = RULE, rp = d.replay, ok = (v) => (v ? "Allowed" : "Blocked");
  $("#rule-out").innerHTML = `<h3>What would change</h3><ul class="plain">${d.changes.map((c) => `<li>${esc(c.text)}</li>`).join("")}</ul>
    ${d.ignored.length ? `<p class="bad">Not understood, so not applied: ${d.ignored.map(esc).join("; ")}</p>` : ""}
    <h3>Last week's payments under this rule</h3>
    <table><tbody>${rp.lines.map((l) => `<tr><td>${esc(l.name)}</td><td class="r num">${money(l.currency, l.amount)}</td><td>${ok(l.was)}</td><td>${ok(l.now)}</td></tr>`).join("")}</tbody></table>
    <p>${rp.newly_blocked.length ? `Would have blocked ${rp.newly_blocked.length} line${rp.newly_blocked.length === 1 ? "" : "s"} that went through last week.` : "Nothing that went through last week would be blocked."}</p>
    <p class="muted">Nothing changes until ${esc(nm(d.tenant))} finance signs it.</p>
    <div class="actions"><button class="primary" data-act="rule-sign">Sign as ${esc(u ? cap(u.id) : me())}</button></div>`;
}

/* ---------- proof ---------- */
async function loadProof() {
  const el = $("#view-proof");
  if (!PROOF) el.innerHTML = `<div class="panel"><div class="skel" style="width:40%"></div><div class="skel"></div></div>`;
  try { PROOF = await api("/api/proof"); } catch (e) { el.innerHTML = `<div class="panel"><p>${esc(e.message)}</p></div>`; return; }
  renderProof();
}
function renderProof() {
  const P = PROOF, el = $("#view-proof"), ch = P.report.chain;
  const isoBad = TENANTS.filter((t) => !P.report.probes.filter((p) => p.from === t).every((p) => p.ok) || !P.report.tenants[t].checks.every((k) => k.ok));
  const certBad = TENANTS.filter((t) => !P.certs[t].valid);
  const items = [
    [isoBad.length === 0, `${T.isolation} ${isoBad.length ? T.fail.toUpperCase() : T.pass.toUpperCase()} for ${TENANTS.length - isoBad.length} ${T.of} ${TENANTS.length} ${T.employers}${isoBad.length ? `: ${isoBad.map((t) => nm(t)).join(", ")}` : ""}`],
    [ch.ok, ch.ok ? `${T.chain} (${ch.seq} entries)` : `Ledger chain broken: ${ch.reason}${ch.bad_seq ? ` at row ${ch.bad_seq}` : ""}`],
    [certBad.length === 0, `${TENANTS.length - certBad.length} ${T.of} ${TENANTS.length} ${T.certs}${certBad.length ? `: ${certBad.map((t) => nm(t)).join(", ")} invalid` : ""}`],
  ];
  const all = items.every((i) => i[0]);
  const verdict = `<div class="verdict-card ${all ? "" : "no"}" role="status">${all ? ICON.check : ICON.alert}${items.map((i, n) => `${n ? '<span class="sep">·</span>' : ""}<span>${esc(i[1])}</span>`).join("")}<span class="chip" style="margin-left:auto">${S ? esc(S.backend) : ""} backend</span><button data-act="reverify">${T.verifyAgain}</button></div>`;
  const panels = TENANTS.map((t) => {
    const r = P.report.tenants[t], c = P.certs[t];
    return `<div class="panel" data-t="${t}"><header><h2>${nm(t)}</h2><span class="chip">${c.valid ? "Signature valid" : "Signature invalid"} · ${esc(c.result)}</span></header>
      ${r.checks.map((k) => `<div class="check ${k.ok ? "ok" : "no"}">${k.ok ? ICON.check : ICON.alert}<span class="word">${k.ok ? T.pass : T.fail}</span><span>${esc(k.name)}${k.ok || !k.detail ? "" : ` <span class="bad">${esc(k.detail)}</span>`}</span></div>`).join("")}
      <div class="cols"><div><h3>Paid out</h3><p class="num">${esc(totalsText(r.totals_by_currency))}</p><p class="muted">${r.payees} payee${r.payees === 1 ? "" : "s"}${r.fee_gbp !== "0.00" ? ` · fee ${esc(fmtMoney("GBP", r.fee_gbp))}` : ""}</p></div>
      <div><h3>Debited transfers</h3>${r.debits.map((d) => `<div class="mono">${esc(d.transfer_id.slice(0, 8))} ${esc(fmtMoney(d.currency, d.amount))} ${esc(d.status || "")}</div>`).join("") || "<p>None.</p>"}</div></div>
      <div class="actions"><a class="btn" href="/api/cert/${t}">${T.download}</a><button data-act="print" data-t="${t}">${T.print}</button></div></div>`;
  }).join("");
  const pr = `<div class="panel"><h2>${T.probesTitle}</h2>${P.report.probes.map((p) => `<div class="check ${p.ok ? "ok" : "no"}">${p.ok ? ICON.lock : ICON.alert}<span class="word">${p.ok ? T.pass : T.fail}</span><span>${esc(nm(p.from))} token against ${esc(nm(p.to) || p.to)}: HTTP ${p.status} ${esc(p.code || "")}</span></div>`).join("")}</div>`;
  el.innerHTML = `<div class="stack">${verdict}${panels}${pr}</div>`;
}
function printCert(t) {
  const c = PROOF.certs[t].doc, b = c.body;
  $("#certprint").innerHTML = `<h1>Segregation certificate: ${esc(nm(t))}</h1><p>Run ${esc(b.run_id)} · issued ${esc(b.issued_at)} · backend ${esc(b.backend)} · result <strong>${esc(b.result)}</strong></p>
    <table><tbody>${b.checks.map((k) => `<tr><td>${k.ok ? T.pass : T.fail}</td><td>${esc(k.name)}</td></tr>`).join("")}</tbody></table>
    <p>Paid: ${esc(totalsText(b.totals_by_currency))} to ${b.payees} payees. Fee: ${esc(fmtMoney("GBP", b.fee_gbp))}.</p>
    <p class="mono">Ledger head ${b.ledger_head.seq} ${esc(b.ledger_head.hash)}<br>Signature (${esc(c.alg)}) ${esc(c.signature)}</p>`;
  window.print();
}

/* ---------- events ---------- */
function closeMenus() {
  document.querySelectorAll(".pop").forEach((p) => { p.hidden = true; });
  document.querySelectorAll("[data-act=menu]").forEach((b) => b.setAttribute("aria-expanded", "false"));
}
document.addEventListener("click", async (ev) => {
  const cp = ev.target.closest("[data-copy]");
  if (cp) {
    try { await navigator.clipboard.writeText(cp.dataset.copy); } catch (_) { /* clipboard blocked: still tell the user */ }
    const old = cp.textContent; cp.textContent = T.copied; setTimeout(() => (cp.textContent = old), 1500); return;
  }
  if (ev.target.closest("[data-close]")) { closeDlg(ev.target.closest("dialog")); return; }
  const b = ev.target.closest("[data-act]");
  if (!b) { if (!ev.target.closest(".menu")) closeMenus(); return; }
  const { act, t, id, k, q, u, i, m, sw } = b.dataset;
  if (act === "menu") {
    const pop = $(`#pop-${m}`), opening = pop.hidden; closeMenus(); pop.hidden = !opening; b.setAttribute("aria-expanded", String(opening)); return;
  }
  closeMenus();
  if (act === "start") { if (await doAct("/api/start", {}, hasRunNow() ? "Checking the inboxes." : "Payroll started.")) pendingStart = true; await refresh(); }
  else if (act === "review") openApprove(t);
  else if (act === "proof") location.hash = "#/proof";
  else if (act === "hold") await doAct("/api/hold", { tenant: t }, `Paused ${nm(t)}.`);
  else if (act === "resume") await doAct("/api/resume", { tenant: t }, `Resumed ${nm(t)}.`);
  else if (act === "kill") { if (await ask(T.killConfirmTitle, T.killConfirmBody, T.stopAll)) await doAct("/api/kill", { on: true }, "All payments stopped."); }
  else if (act === "unkill") await doAct("/api/kill", { on: false }, "Payments resumed.");
  else if (act === "startover") { if (await ask(T.startOverTitle, T.resetConfirm, T.startOverYes)) { await doAct("/api/reset", {}, "Started over."); TL = []; tlSeen = -1; PROOF = null; pendingStart = false; await refresh(); } }
  else if (act === "presenter") { qs.set("present", PRESENT ? "0" : "1"); location.search = qs.toString(); }
  else if (act === "scenario") await runScenario(id);
  else if (act === "rows") openRows(id);
  else if (act === "details") { const on = document.body.classList.toggle("details"); b.setAttribute("aria-pressed", on); renderStatic(); }
  else if (act === "filter") { filter = k; renderTimeline(); }
  else if (act === "drawer") { const on = $("#activity").classList.toggle("open"); b.setAttribute("aria-expanded", String(on)); }
  else if (act === "intro-close") { localStorage.setItem("rf_intro_seen", "1"); renderIntro(); }
  else if (act === "warn-close") { warnShown = S.error; renderBanners(); }
  else if (act === "more") { expanded[t] = !expanded[t]; renderLanes(); }
  else if (act === "as") { localStorage.setItem("rf_user", u); whoKey = ""; render(); }
  else if (act === "confirm") {
    if (sw) { localStorage.setItem("rf_user", sw); whoKey = ""; }
    await doAct("/api/confirm_bank", { tenant: t, qid: Number(q) }, "Bank details confirmed."); closeDlg($("#dlg-approve"));
  }
  else if (act === "reverify") loadProof();
  else if (act === "example") { const ta = $("#rule-text"); ta.value = T.examples[Number(i)]; RULE_TEXT = ta.value; ta.focus(); }
  else if (act === "rule-draft") {
    const tt = $("#rule-t").value; RULE_TEXT = $("#rule-text").value;
    try { RULE = (await api("/api/rules/draft", { user: me(), tenant: tt, text: RULE_TEXT })).draft; RULE_T = tt; $("#view-rules").dataset.ready = tt; } catch (e) { RULE = null; toast(e.message); }
    renderRules();
  }
  else if (act === "rule-sign") {
    const r = await doAct("/api/rules/sign", { tenant: RULE.tenant, text: RULE_TEXT }, "Rule signed.");
    if (r) { RULE = null; renderRules(); }
  }
  else if (act === "print") printCert(t);
});
document.addEventListener("change", (e) => {
  if (e.target.id === "rule-t") { RULE_T = e.target.value; RULE_TEXT = $("#rule-text").value; $("#view-rules").dataset.ready = ""; renderRules(); }
});
document.addEventListener("input", (e) => { if (e.target.id === "rule-text") RULE_TEXT = e.target.value; });
document.addEventListener("keydown", (e) => {
  if (e.key !== "Escape") return;
  closeMenus(); $("#activity").classList.remove("open"); $("#act-btn").setAttribute("aria-expanded", "false");
});
async function runScenario(id) {
  const r = await doAct(`/api/scenario/${id}`, {});
  if (r && r.result) toast(r.result.ok ? r.result.summary : `Not completed: ${r.result.summary}`);
}
window.addEventListener("hashchange", route);
function route() {
  const h = location.hash;
  view = h.startsWith("#/proof") ? "proof" : h.startsWith("#/rules") ? "rules" : h.startsWith("#/demo") ? "pay" : "try";
  render(); if (view === "proof") loadProof(); else if (view !== "try") refresh();
  Play.route(view === "try" ? h : null);
}

/* presenter mode: keys 1-6 run the cards, arrows move the caption, R starts over with a confirm */
const caption = (n) => { $("#cap-n").textContent = `Step ${n + 1} of ${BEATS.length}`; $("#cap-t").textContent = BEATS[n]; };
if (PRESENT) {
  let beat = 0; caption(0);
  document.addEventListener("keydown", async (e) => {
    if (e.target.closest("input,select,textarea") || e.metaKey || e.ctrlKey) return;
    if (e.key >= "1" && e.key <= "6") { await runScenario(CARD_ORDER[Number(e.key) - 1]); }
    else if (e.key === "ArrowRight" || e.key === "n") { beat = Math.min(BEATS.length - 1, beat + 1); caption(beat); }
    else if (e.key === "ArrowLeft") { beat = Math.max(0, beat - 1); caption(beat); }
    else if (e.key === "r" || e.key === "R") { if (confirm(T.resetConfirm)) { await doAct("/api/reset", {}, "Started over."); TL = []; tlSeen = -1; } }
  });
}

route(); (view === "try" ? Promise.resolve() : refresh()).then(() => { const a = qs.get("approve"); if (a && S && S.lanes[a]) openApprove(a); });  // ?approve=<tenant> opens the dialog (screenshots)
if (qs.get("nosse") !== "1") connect();  // nosse=1: one fetch, no stream (screenshots)
