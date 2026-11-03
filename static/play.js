"use strict";
/* The playground: describe a payroll, review what was understood, then watch a run in its own world.
   Everything a judge types is text. It goes out through esc() and never becomes HTML. Money is BigInt cents or the API's strings. */
const Play = (() => {
  const root = () => $("#view-try");
  const fmt = (s, o) => String(s).replace(/\{(\w+)\}/g, (_, k) => o[k]);
  const reduced = () => matchMedia("(prefers-reduced-motion: reduce)").matches;
  const NAME_RE = /^[\p{L}\p{N} .&'-]{1,40}$/u;
  const NUM_RE = /^\d{1,7}(\.\d{1,2})?$/;
  const ORDER = ["GB", "DE", "US", "AU"];
  const MAX_TEXT = 4000, MAX_FILE = 50 * 1024;

  /* ---------- money helpers (display only; the server recalculates with Decimal) ---------- */
  const cents = (s) => { const [w, f = ""] = String(s).trim().split("."); return BigInt(w + (f + "00").slice(0, 2)); };
  const groupC = (c) => { const neg = c < 0n; const a = neg ? -c : c; return `${neg ? "-" : ""}${String(a / 100n).replace(/\B(?=(\d{3})+(?!\d))/g, ",")}.${String(a % 100n).padStart(2, "0")}`; };
  const lineCents = (h, r) => (cents(h) * cents(r) + 50n) / 100n;
  const ccyOf = (cc) => (T.countries[cc] || ["", ""])[1];

  /* ---------- state ---------- */
  let info = { live: false, presets: [], limits: {} };
  const H = { text: "", backend: "fake", phase: "compose", reading: false, form: null, notes: [], src: "", serr: {}, ferr: "", note: [], starting: false, rerr: null, drag: 0 };
  let R = null;  // the open run, or null

  /* ---------- routing ---------- */
  function route(hash) {
    loadInfo();
    if (hash === null) { stopRun(); return; }
    const m = /^#\/try\/([\w-]{6,40})$/.exec(hash);
    if (m) { if (!R || R.wid !== m[1]) openRun(m[1]); return; }
    stopRun();
    home();
  }
  let loaded = false;
  function loadInfo() {  // app.js defines api(), so this runs on the first route, not at load
    if (loaded) return;
    loaded = true;
    api("/api/play/info").then((i) => { info = i; if (!H.touchedBackend) H.backend = i.live ? "live" : "fake"; if (!R) { paintSeg(); paintBadge(); if (i.metal && $(".hero") && !$("#pl-text").value) home(); } }).catch(() => { loaded = false; });
  }
  function paintBadge() {
    $("#live").innerHTML = `<span class="dot ${info.live ? "" : "off"}"></span>${esc(info.live ? T.liveChip : T.backendSim)}`;
  }

  /* ---------- home: composer ---------- */
  const isMulti = () => !!(H.form && H.form.employers.length > 1);
  const backend = () => (isMulti() || !info.live ? "fake" : H.backend);
  const kbd = () => (/Mac|iPhone|iPad/.test(navigator.platform) ? "⌘↵" : "Ctrl ↵");

  function segHtml() {
    const multi = isMulti(), b = backend();
    const opt = (v, label, off) => `<button type="button" role="radio" aria-checked="${b === v}" data-pl="be" data-v="${v}" ${off ? "disabled" : ""}>${esc(label)}</button>`;
    return `<div class="seg" role="radiogroup" aria-label="${esc(T.backendLabel)}">${opt("live", T.backendLive, !info.live || multi)}${opt("fake", T.backendSim, false)}</div>`;
  }
  const segNote = () => (isMulti() ? T.twoEmployers : backend() === "live" ? T.liveNote : T.simNote);

  function home() {
    document.title = "Ringfence";
    if (!R && !H.touchedBackend) H.backend = info.live ? "live" : "fake";
    root().className = "play home";
    root().innerHTML = H.phase === "review" && H.form ? reviewHtml() : composeHtml();
    wireHome();
    paintBadge();
  }

  function composeHtml() {
    const ex = T.presets.map((p, i) => `<button type="button" class="ex" data-pl="ex" data-i="${i}">${esc(p.label)}${p.sim ? ` <span class="chip sim">${esc(T.simulated)}</span>` : ""}</button>`).join("");
    return `<div class="hero"><h1><span>${esc(T.h1a)}</span> <span>${esc(T.h1b)}</span></h1>
      <p class="lede">${esc(T.lede)}</p>${info.metal ? `<a class="metal-pill" href="#/demo"><span class="dot"></span>${esc(T.metalHome)}<span class="go">${esc(T.metalTry)} &rarr;</span></a>` : ""}</div>
    <div class="composer" id="pl-comp">
      <label class="sr" for="pl-text">${esc(T.composerHint)}</label>
      <textarea id="pl-text" rows="4" placeholder="${esc(T.composerHint)}" spellcheck="false">${esc(H.text)}</textarea>
      <div class="veil" id="pl-veil" hidden>${esc(T.dropHere)}</div>
      <div class="cbar">
        <label class="btn" for="pl-file">${esc(T.attach)}</label><input type="file" id="pl-file" accept=".csv,.txt,text/csv,text/plain" hidden>
        <span class="counter small" id="pl-count" aria-live="polite"></span>
        <span class="grow"></span>
        <span id="pl-seg">${segHtml()}</span>
        <button type="button" class="primary" id="pl-read" data-pl="read"></button>
      </div>
    </div>
    <p class="small muted pl-segnote" id="pl-segnote">${esc(segNote())}</p>
    <p class="small ferr" id="pl-ferr" role="alert">${esc(H.ferr)}</p>
    <div class="pl-notes" id="pl-notes" role="status">${H.note.map((n) => `<p>${esc(n)}</p>`).join("")}</div>
    <div class="examples"><div class="exs">${ex}</div></div>
    <p class="small faint">${esc(T.retention)}</p>`;
  }

  function paintRead() {
    const b = $("#pl-read"), ta = $("#pl-text"), c = $("#pl-count");
    if (!b || !ta) return;
    const n = ta.value.length, over = n - MAX_TEXT;
    c.textContent = over > 0 ? `${T.counterOver} ${over}` : n >= 3500 ? `${n} / ${MAX_TEXT}` : "";
    c.classList.toggle("warn", over > 0);
    b.disabled = H.reading || !ta.value.trim() || over > 0;
    b.innerHTML = H.reading ? `<span class="dot busy"></span>${esc(T.reading)}` : `${esc(T.readIt)} <kbd>${esc(kbd())}</kbd>`;
    ta.readOnly = H.reading;
    ta.style.height = "auto";
    ta.style.height = `${Math.min(Math.max(ta.scrollHeight, 100), 300)}px`;  // 4 to 12 rows
  }
  function paintSeg() { if ($("#pl-seg")) { $("#pl-seg").innerHTML = segHtml(); $("#pl-segnote").textContent = segNote(); } if ($("#pl-seg2")) { $("#pl-seg2").innerHTML = segHtml(); $("#pl-segnote2").textContent = segNote(); } }

  function wireHome() {
    const ta = $("#pl-text");
    if (ta) {
      ta.addEventListener("input", () => { H.text = ta.value; H.ferr = ""; $("#pl-ferr").textContent = ""; paintRead(); });
      $("#pl-file").addEventListener("change", (e) => { const f = e.target.files[0]; e.target.value = ""; if (f) takeFile(f); });
      paintRead();
    } else paint();
  }

  async function takeFile(f) {
    const bad = (m) => { H.ferr = m; const el = $("#pl-ferr"); if (el) el.textContent = m; };
    if (!/\.(csv|txt)$/i.test(f.name)) return bad(T.fileKind);
    if (f.size > MAX_FILE) return bad(T.fileBig);
    try {
      const t = await f.text();
      const ta = $("#pl-text");
      if (!ta) return;
      H.ferr = ""; $("#pl-ferr").textContent = "";
      ta.value = ta.value.trim() ? `${ta.value.trimEnd()}\n\n${t}` : t;
      H.text = ta.value; paintRead(); ta.focus();
    } catch (_) { bad(T.fileRead); }
  }

  async function doRead() {
    const ta = $("#pl-text");
    if (!ta || H.reading || !ta.value.trim() || ta.value.length > MAX_TEXT) return;
    H.reading = true; H.note = []; paintRead();
    try {
      const d = await api("/api/play/draft", { text: ta.value });
      H.reading = false;
      if (!d.spec) { H.note = d.notes && d.notes.length ? d.notes : [T.readNone]; home(); const t2 = $("#pl-text"); if (t2) t2.focus(); return; }
      H.form = normalize(d.spec); H.notes = d.notes || []; H.src = d.source; H.serr = errMap(d.errors);
      H.rerr = null; H.starting = false; H.phase = "review";
      if (H.form.employers.length > 1) H.backend = "fake";
      home(); window.scrollTo(0, 0);
    } catch (e) {
      H.reading = false; H.ferr = e.status === 429 || e.status === 422 ? e.message : T.readFail;
      home();
    }
  }

  /* ---------- review form ---------- */
  const normalize = (spec) => ({
    employers: spec.employers.map((e) => ({
      name: e.name || "", pays_from: e.pays_from || "GBP", local_only: !!e.local_only, per_line_cap: e.per_line_cap || "10000.00",
      per_run_cap: e.per_run_cap || "100000.00", approval: e.approval || "finance",
      people: (e.people || []).map((p) => ({ name: p.name || "", country: p.country || "GB", hours: String(p.hours ?? ""), rate: String(p.rate ?? "") })),
      emails: (e.emails || []).map((m) => ({ from: m.from ?? m.sender ?? "", body: m.body || "" })),
    })),
  });
  const errMap = (list) => Object.fromEntries((list || []).map((x) => [x.field || "employers", x.message || x.msg]));
  const toSpec = (f) => ({
    employers: f.employers.map((e) => ({
      name: e.name.trim(), pays_from: e.pays_from, local_only: e.local_only, per_line_cap: e.per_line_cap.trim(), per_run_cap: e.per_run_cap.trim(), approval: e.approval,
      people: e.people.map((p) => ({ name: p.name.trim(), country: p.country, hours: p.hours.trim(), rate: p.rate.trim() })),
      emails: e.emails.map((m) => ({ from: m.from.trim(), body: m.body.trim() })),
    })),
  });

  function validate(f) {
    const e = {};
    const nameErr = (v) => (v.trim().length < 1 || v.trim().length > 40 ? T.errLen40 : NAME_RE.test(v.trim()) ? "" : T.errName);
    const rng = (v, lo, hi, msg) => (!NUM_RE.test(v.trim()) ? T.errNum : cents(v) < lo || cents(v) > hi ? msg : "");
    const seen = new Set();
    f.employers.forEach((m, i) => {
      const p = `employers.${i}`;
      const set = (k, msg) => { if (msg) e[`${p}.${k}`] = msg; };
      set("name", nameErr(m.name));
      const key = m.name.trim().toLowerCase();
      if (!e[`${p}.name`] && seen.has(key)) set("name", T.errDupe);
      seen.add(key);
      set("per_line_cap", rng(m.per_line_cap, 100n, 10000000n, T.errLimit));
      set("per_run_cap", rng(m.per_run_cap, 100n, 10000000n, T.errLimit));
      if (!e[`${p}.per_line_cap`] && !e[`${p}.per_run_cap`] && cents(m.per_run_cap) < cents(m.per_line_cap)) set("per_run_cap", T.errRunLimit);
      if (!m.people.length) set("people", T.errNoPeople);
      m.people.forEach((x, j) => {
        const q = `people.${j}`;
        set(`${q}.name`, nameErr(x.name)); set(`${q}.hours`, rng(x.hours, 1n, 8000n, T.errHours)); set(`${q}.rate`, rng(x.rate, 100n, 100000n, T.errRate));
      });
      m.emails.forEach((x, j) => {
        set(`emails.${j}.from`, x.from.trim().length < 1 || x.from.trim().length > 80 ? T.errLen80 : "");
        set(`emails.${j}.body`, x.body.trim().length < 1 || x.body.trim().length > 2000 ? T.errLen2000 : "");
      });
    });
    return e;
  }

  const fld = (path, label, ctl, cls = "") => `<label class="fld ${cls}"><span class="lb">${esc(label)}</span>${ctl}<span class="err" data-err="${esc(path)}"></span></label>`;
  const inp = (path, v, extra = "") => `<input data-f="${esc(path)}" value="${esc(v)}" autocomplete="off" spellcheck="false" ${extra}>`;
  const sel = (path, v, opts) => `<select data-f="${esc(path)}">${opts.map(([k, l]) => `<option value="${esc(k)}" ${k === v ? "selected" : ""}>${esc(l)}</option>`).join("")}</select>`;

  function empHtml(m, i) {
    const p = `employers.${i}`, many = H.form.employers.length > 1;
    const people = m.people.map((x, j) => {
      const q = `${p}.people.${j}`;
      return `<div class="prow"><span class="rn" aria-label="Row ${j + 1}">${j + 1}</span>
        ${fld(`${q}.name`, T.fName, inp(`${q}.name`, x.name), "c-name")}
        ${fld(`${q}.country`, T.fCountry, sel(`${q}.country`, x.country, ORDER.map((c) => [c, `${T.countries[c][0]} · ${T.countries[c][1]}`])), "c-ctry")}
        ${fld(`${q}.hours`, T.fHours, inp(`${q}.hours`, x.hours, 'inputmode="decimal"'), "c-num")}
        ${fld(`${q}.rate`, T.fRate, inp(`${q}.rate`, x.rate, 'inputmode="decimal"'), "c-num")}
        <div class="fld c-amt"><span class="lb">${esc(T.fAmount)}</span><output class="num" data-amt="${esc(q)}"></output></div>
        <button type="button" class="quiet" data-pl="rmp" data-e="${i}" data-p="${j}" aria-label="${esc(T.removePerson)} ${j + 1}">${esc(T.remove)}</button></div>`;
    }).join("");
    const mails = m.emails.map((x, j) => {
      const q = `${p}.emails.${j}`;
      return `<div class="erow">${fld(`${q}.from`, T.fFrom, inp(`${q}.from`, x.from))}
        ${fld(`${q}.body`, T.fBody, `<textarea data-f="${esc(q)}.body" rows="3" spellcheck="false">${esc(x.body)}</textarea>`)}
        <button type="button" class="quiet" data-pl="rme" data-e="${i}" data-p="${j}">${esc(T.remove)}</button></div>`;
    }).join("");
    return `<section class="card emp" aria-label="${esc(T.employer)} ${i + 1}">
      <h3>${esc(T.employer)}${many ? ` ${i + 1}` : ""}</h3>
      <div class="grid5">
        ${fld(`${p}.name`, T.fName, inp(`${p}.name`, m.name), "c-name")}
        ${fld(`${p}.pays_from`, T.fPays, sel(`${p}.pays_from`, m.pays_from, ORDER.map((c) => [ccyOf(c), ccyOf(c)])))}
        ${fld(`${p}.approval`, T.fApproval, sel(`${p}.approval`, m.approval, T.approvalOpts))}
        ${fld(`${p}.per_line_cap`, T.fLine, inp(`${p}.per_line_cap`, m.per_line_cap, 'inputmode="decimal"'), "c-num")}
        ${fld(`${p}.per_run_cap`, T.fRun, inp(`${p}.per_run_cap`, m.per_run_cap, 'inputmode="decimal"'), "c-num")}
      </div>
      <label class="chk"><input type="checkbox" data-f="${p}.local_only" ${m.local_only ? "checked" : ""}><span>${esc(T.fLocal)}</span></label>
      <h3>${esc(T.people)}</h3>
      <div class="people">${people}</div>
      <span class="err" data-err="${p}.people"></span>
      <p class="small over" data-over="${i}" role="status"></p>
      ${m.people.length < 6 ? `<button type="button" class="link" data-pl="addp" data-e="${i}">+ ${esc(T.addPerson)}</button>` : ""}
      <h3>${esc(T.emailsTitle)}</h3>
      <div class="emails">${mails}</div>
      ${m.emails.length < 2 ? `<button type="button" class="link" data-pl="adde" data-e="${i}">+ ${esc(T.addEmail)}</button>` : ""}
    </section>`;
  }

  function reviewHtml() {
    const oneLine = H.text.replace(/\s+/g, " ").trim().slice(0, 90);
    return `<div class="review">
      <div class="rv-head"><div><h2>${esc(T.understood)}</h2><p class="small muted">${esc(H.src === "csv" ? T.fromTable : T.fromText)}${oneLine ? `: <span class="mono">${esc(oneLine)}</span>` : ""}</p></div>
        <button type="button" data-pl="edit">${esc(T.editText)}</button></div>
      ${H.notes.length ? `<ul class="pl-notes" role="status">${H.notes.map((n) => `<li>${esc(n)}</li>`).join("")}</ul>` : ""}
      ${H.form.employers.map(empHtml).join("")}
      <p class="small muted">${esc(T.bankLine)}</p>
      <p class="small muted">${esc(T.calcNote)}</p>
      <div class="runrow"><span id="pl-seg2">${segHtml()}</span><button type="button" class="primary" id="pl-run" data-pl="run"></button></div>
      <p class="small muted" id="pl-segnote2">${esc(segNote())}</p>
      <p class="small ferr" id="pl-fix" role="status"></p>
      <div class="small ferr" id="pl-rerr" role="alert"></div>
    </div>`;
  }

  /* repaint the live parts of the form: errors, calculated amounts, the run button. Inputs themselves are never replaced. */
  function paint() {
    if (!H.form || !$("#pl-run")) return;
    const errs = { ...validate(H.form), ...H.serr };
    const els = [...root().querySelectorAll("[data-err]")];
    const shown = new Set();
    els.forEach((el) => { const m = errs[el.dataset.err] || ""; el.textContent = m; if (m) shown.add(el.dataset.err); });
    root().querySelectorAll("[data-f]").forEach((el) => { if (errs[el.dataset.f]) el.setAttribute("aria-invalid", "true"); else el.removeAttribute("aria-invalid"); });
    H.form.employers.forEach((m, i) => {
      let over = false;
      m.people.forEach((x, j) => {
        const out = root().querySelector(`[data-amt="employers.${i}.people.${j}"]`);
        const ok = NUM_RE.test(x.hours.trim()) && NUM_RE.test(x.rate.trim());
        const c = ok ? lineCents(x.hours.trim(), x.rate.trim()) : null;
        if (out) out.textContent = c === null ? "" : `${groupC(c)} ${ccyOf(x.country)}`;
        if (c !== null && NUM_RE.test(m.per_line_cap.trim()) && c > cents(m.per_line_cap)) over = true;
      });
      const o = root().querySelector(`[data-over="${i}"]`);
      if (o) o.textContent = over ? T.overLine : "";
    });
    const extra = Object.keys(errs).filter((k) => !els.some((el) => el.dataset.err === k)).map((k) => errs[k]);
    const bad = Object.keys(errs).length;
    $("#pl-fix").textContent = bad ? [T.fixFirst, ...extra].join(" ") : "";
    const run = $("#pl-run");
    run.disabled = bad > 0 || H.starting;
    run.innerHTML = H.starting ? `<span class="dot busy"></span>${esc(T.starting)}` : `${esc(backend() === "live" ? T.runLive : T.runSim)} <kbd>${esc(kbd())}</kbd>`;
  }

  function setPath(path, value) {
    const m = /^employers\.(\d+)\.(.+)$/.exec(path);
    if (!m) return;
    const e = H.form.employers[Number(m[1])];
    const parts = m[2].split(".");
    if (parts.length === 1) e[parts[0]] = value;
    else e[parts[0]][Number(parts[1])][parts[2]] = value;
  }

  async function doRun() {
    if (H.starting || !H.form || Object.keys(validate(H.form)).length) return;
    H.starting = true; H.rerr = null; paint(); $("#pl-rerr").innerHTML = "";
    const spec = toSpec(H.form), be = backend();
    try {
      const w = await api("/api/play/worlds", { spec, backend: be });
      try { sessionStorage.setItem(`rf_spec_${w.wid}`, JSON.stringify(spec)); } catch (_) { /* private mode */ }
      location.hash = `#/try/${w.wid}`;
    } catch (e) {
      H.starting = false;
      if (e.status === 422 && Array.isArray(e.detail)) { H.serr = errMap(e.detail); paint(); return; }
      paint();
      const extra = e.status === 409 && be === "live" ? `<button type="button" data-pl="runfake">${esc(T.useSim)}</button>`
        : e.status === 429 ? `<a href="#/demo">${esc(T.watchDemo)}</a>` : "";
      $("#pl-rerr").innerHTML = `<p>${esc(e.message)}</p>${extra}`;
    }
  }

  /* ---------- run view ---------- */
  const PH = [0, 1, 2, 3];
  function openRun(wid) {
    stopRun();
    let spec = null;
    try { spec = JSON.parse(sessionStorage.getItem(`rf_spec_${wid}`) || "null"); } catch (_) { /* none */ }
    R = { wid, spec, view: null, S: null, TL: [], calls: [], proof: null, proofHead: -1, ended: false, gone: false, es: null, timers: [], last: 0, open: new Set(), seen: new Set(),
      baseline: {}, disp: {}, html: {}, rows: {}, rechecks: {}, started: !!sessionStorage.getItem(`rf_started_${wid}`), pulling: false, lastVer: null, shared: false,
      pending: new Set(), errShown: false, rstate: {} };
    document.title = "Ringfence run";
    root().className = "play run";
    root().innerHTML = `<div class="rv-top" id="rv-top"></div><p class="small muted" id="rv-note" role="status"></p>
      <div class="runcols"><section class="trace" id="rv-trace" aria-label="${esc(T.trace)}"></section>
      <aside class="result" id="rv-result" aria-label="${esc(T.result)}">
        <section id="r-bal"></section><section id="r-act"></section><section id="r-pay"></section><section id="r-next"></section><section id="r-cert"></section></aside></div>`;
    renderHead();
    pollView();
  }
  function stopRun() {
    if (!R) return;
    R.timers.forEach(clearTimeout); clearInterval(R.fallback);
    if (R.es) R.es.close();
    R = null;
  }
  const at = (fn, ms) => { const mine = R; const t = setTimeout(() => { if (R === mine) fn(); }, ms); R.timers.push(t); return t; };
  const base = () => `/play/${R.wid}/api`;

  async function pollView() {
    const mine = R;
    try {
      const v = await api(`/api/play/worlds/${mine.wid}`);
      if (R !== mine) return;
      mine.view = v; mine.viewAt = Date.now();
      if (v.status === "ready") { if (!mine.es) connect(); pull(); at(pollView, 20000); }
      else if (v.status === "expired") { ended(); }
      else if (v.status === "failed") { renderHead(); renderPre(); }
      else { renderHead(); renderPre(); at(pollView, 2000); }
    } catch (e) {
      if (R !== mine) return;
      if (e.status === 410) return ended();
      lost(); at(pollView, 3000);
    }
  }
  function lost() { $("#rv-note").textContent = T.lostContact; }
  function ended() {
    if (!R) return;
    R.ended = true; R.gone = !R.S; clearInterval(R.fallback); if (R.es) { R.es.close(); R.es = null; }
    renderHead(); renderPre(); if (R.S) renderRun();
  }
  function connect() {
    const mine = R;
    const poll = () => { if (R === mine && !mine.ended) schedule(); };
    mine.fallback = setInterval(poll, 4000);
    try {
      const es = new EventSource(`/play/${mine.wid}/events`);
      mine.es = es;
      es.addEventListener("tick", (ev) => { if (ev.data === mine.lastVer) return; mine.lastVer = ev.data; schedule(); });
    } catch (_) { /* polling only */ }
  }
  function schedule() {
    if (!R) return;
    clearTimeout(R.pt);
    R.pt = at(pull, Math.max(0, 2000 - (Date.now() - R.last)));  // never faster than every 2 s
  }
  async function pull() {
    const mine = R;
    if (!mine || mine.pulling || mine.ended) return;
    mine.pulling = true;
    try {
      const after = mine.TL.length ? mine.TL[mine.TL.length - 1].detail.seq : 0;
      const [s, tl, c] = await Promise.all([api(`${base()}/state`), api(`${base()}/timeline?after=${after}`), api(`${base()}/calls`)]);
      if (R !== mine) return;
      mine.S = s;
      mine.TL = s.head < after ? await api(`${base()}/timeline?after=0`) : mine.TL.concat(tl).slice(-300);
      mine.calls = c.calls || [];
      $("#rv-note").textContent = "";
      maybeStart(); await maybeProof();
      if (R === mine) renderRun();
    } catch (e) {
      if (R !== mine) return;
      if (e.status === 410) ended(); else if (e.status !== 409 && e.status !== 503) lost();
    } finally { mine.pulling = false; mine.last = Date.now(); }
  }
  function maybeStart() {
    const s = R.S;
    if (R.started || !s.world || !s.world.ready) return;
    R.started = true;
    if (Object.values(s.lanes).some((l) => l.state)) return;
    try { sessionStorage.setItem(`rf_started_${R.wid}`, "1"); } catch (_) { /* private mode */ }
    api(`${base()}/start`, { user: "operator" }).then(() => schedule()).catch((e) => { R.started = false; $("#rv-note").textContent = e.message; });
  }
  async function maybeProof() {
    const s = R.S, lanes = Object.values(s.lanes);
    if (!lanes.length || !lanes.every((l) => l.state === "DONE") || R.proofHead === s.head) return;
    R.proofHead = s.head;
    try { R.proof = await api(`${base()}/proof`); } catch (_) { R.proofHead = -1; }
  }

  /* header */
  const names = () => (R.S ? Object.values(R.S.employers).map((e) => e.name) : R.spec ? R.spec.employers.map((e) => e.name) : []);
  const slots = () => (R.S ? Object.keys(R.S.lanes) : []);
  function minsLeft() {
    if (!R.view || !R.view.expires_at) return null;
    return Math.ceil((Date.parse(R.view.expires_at) - Date.now()) / 60000);
  }
  function renderHead() {
    const s = R.S, v = R.view, live = (v && v.backend) === "live" || (s && s.backend === "live");
    const chip = live ? `<span class="chip">${esc(T.liveChip)}${s && s.world ? ` <span class="mono">acct_…${esc(s.world.account_suffix)}</span>` : ""}</span>` : `<span class="chip sim">${esc(T.simChip)}</span>`;
    const scripted = s && (s.agent === "offline agent" || s.agent_capped);
    const agent = !s ? "" : `<span class="agent">${s.agent_busy ? '<span class="dot busy"></span>' : ""}${esc(scripted ? T.rulesEngine : `Claude ${modelName(s.model || "")}`)} · ${esc(s.agent_busy ? T.agentWorking : T.agentIdle)}</span>`;
    const n = minsLeft();
    const left = R.ended ? "" : n === null ? "" : n >= 1 ? fmt(T.expiresIn, { n }) : T.expiresSoon;
    const run = s ? `<span class="mono muted">Run ${esc(s.run_id)}</span>` : "";
    const html = `<a class="back" href="#/">← ${esc(T.newRun)}</a>
      <div class="rh-main"><h2>${esc(names().join(" · ") || T.trace)}</h2>${chip}${run}</div>
      <div class="rh-side">${agent}<span class="small muted">${esc(left)}</span>
        <button type="button" class="quiet" data-pl="share">${esc(R.shared ? T.shareCopied : T.share)}</button></div>`;
    setHtml("top", $("#rv-top"), html);
    if (s && s.agent_capped) $("#rv-note").textContent = T.claudeCap;
    if (R.timers.length < 50 && !R.tick) R.tick = setInterval(() => { if (R && !R.ended) renderHead(); }, 15000);
  }
  function setHtml(key, el, html) { if (R.html[key] === html) return false; R.html[key] = html; el.innerHTML = html; return true; }

  /* before the world answers: queue, setup steps, failure, gone */
  function renderPre() {
    const v = R.view, tr = $("#rv-trace");
    root().querySelector(".runcols").hidden = false;
    $("#r-bal").innerHTML = ""; $("#r-act").innerHTML = ""; $("#r-pay").innerHTML = ""; $("#r-next").innerHTML = ""; $("#r-cert").innerHTML = "";
    if (R.gone || (!v && R.ended)) {
      setHtml("trace", tr, `<div class="card state"><p>${esc(T.gone)}</p><a class="btn primary" href="#/">${esc(T.startNew)}</a></div>`);
      return;
    }
    if (!v) return;
    if (v.status === "failed") {
      const spec = R.spec;
      setHtml("trace", tr, `<div class="card state"><p>${esc(v.error || T.gone)}</p>${spec ? `<button type="button" class="primary" data-pl="retryfake">${esc(T.useSim)}</button>` : ""}<a class="btn" href="#/">${esc(T.startNew)}</a></div>`);
      return;
    }
    if (v.status === "queued") {
      const ahead = v.position === 1 ? T.aheadOne : fmt(T.aheadMany, { n: v.position });
      const m = Math.max(1, Math.round((v.eta_s || 0) / 60));
      const eta = !v.eta_s || v.eta_s < 60 ? T.etaLess : m === 1 ? T.etaOne : fmt(T.etaMany, { n: m });
      setHtml("trace", tr, `<div class="card state"><p>${esc(ahead)} ${esc(eta)}</p><p class="muted small">${esc(T.runStarting)}</p></div>`);
      return;
    }
    const calls = (v.calls || []).map((c, i) => callItem(c, i, 0));
    setHtml("trace", tr, `<div class="card state"><p>${esc(T.runStarting)}</p></div>${calls.length ? `<ol class="rows pre">${calls.map((it, i) => rowHtml(it, i)).join("")}</ol>` : ""}`);
  }

  /* ---------- trace ---------- */
  const callPath = (c) => String(c.path || "");
  function callTitle(c) {
    const p = callPath(c), m = c.method;
    if (m === "POST" && /\/transfers\/create/.test(p)) return "Sent a payment";
    if (m === "GET" && /\/transfers\//.test(p)) return "Checked a payment on Airwallex";
    if (/\/beneficiaries\/create/.test(p)) return "Created bank details";
    if (/\/beneficiaries\/validate/.test(p)) return "Checked bank details";
    if (/\/fx\/quotes/.test(p)) return "Asked for an exchange rate";
    if (/\/fx\/conversions/.test(p)) return "Converted currency inside this account";
    if (/\/global_accounts/.test(p)) return m === "GET" ? "Read receiving accounts" : "Opened a receiving account";
    if (/\/simulation\//.test(p)) return `${T.simulated} sandbox step`;
    if (/\/balances/.test(p)) return "Read balances";
    if (/\/deposits/.test(p)) return "Read deposits";
    return `${m} ${p}`;
  }
  function callItem(c, i, ph) {
    if (c.kind === "claude") return { key: `c${i}`, ts: c.ts, type: "claude", c, ph: 1 };
    if (c.kind === "rules_engine") return { key: `c${i}`, ts: c.ts, type: "rules", c, ph: 1 };
    const quote = /\/fx\/quotes/.test(callPath(c));  // the agent prices FX while preparing, before anyone approves
    const act = !quote && /\/(transfers|fx)\b/.test(callPath(c)) && (c.method !== "GET" || /\/transfers\//.test(callPath(c)));
    return { key: `a${c.method}${callPath(c)}${c.method === "GET" ? "" : i}`, ts: c.ts, type: "awx", c, ph: quote ? 1 : act ? 3 : ph };
  }
  const LEDGER_PH = { RUN_CREATED: 1, AGENT_NOTE: 1, PROPOSAL: 1, ALERT: 1, FUNDING_REQUESTED: 2, FUNDING_MATCHED: 2, BENEFICIARY_QUARANTINED: 2, CALLBACK_CONFIRMED: 2,
    APPROVED: 2, GATE_ALLOW: 2, HOLD: 2, FX_CONVERTED: 3, SUBMITTED: 3, UNKNOWN: 3, RECONCILED: 3, STATUS: 3, REOPENED: 3, FEE_CHARGED: 3, FEE_CREDIT: 3 };
  function ledgerPhase(r) {
    if (r.kind === "GATE_DENY") return r.text.startsWith("The agent") ? 1 : 3;
    return LEDGER_PH[r.kind] ?? null;
  }
  function traceItems() {
    const raw = [];
    const gets = new Map();
    R.calls.forEach((c, i) => {
      const hide = c.method === "GET" && c.status < 400 && !/\/transfers\//.test(callPath(c));  // reads of balances and lists are not steps
      if (hide || /authentication/.test(callPath(c))) return;
      if (c.method === "GET") { gets.set(`${c.method}${callPath(c)}`, [c, i]); return; }
      raw.push([c, i]);
    });
    gets.forEach((v) => raw.push(v));
    const calls = raw.sort((a, b) => (a[0].ts < b[0].ts ? -1 : 1));
    const agentTs = [...R.TL.map((r) => r.ts), ...R.calls.filter((c) => c.kind !== "airwallex").map((c) => c.ts)].sort()[0] || "￿";
    const items = [];
    calls.forEach(([c, i]) => items.push(callItem(c, i, c.ts < agentTs ? 0 : null)));
    R.TL.forEach((r) => items.push({ key: `l${r.detail.seq}`, ts: r.ts, type: "ledger", r, ph: ledgerPhase(r) }));
    items.sort((a, b) => (a.ts < b.ts ? -1 : a.ts > b.ts ? 1 : 0));
    const merged = [], seenCall = new Map();  // one row per repeated call (FX quotes), with a count; each payment stays its own row
    items.forEach((it) => {
      const k = it.type === "awx" && it.c.method === "POST" && !/transfers\/create/.test(it.c.path) ? `${it.c.method}${it.c.path}${it.ph}` : null;
      const prev = k && seenCall.get(k);
      if (prev) prev.c = { ...prev.c, n: (prev.c.n || 1) + (it.c.n || 1) };
      else { merged.push(it); if (k) seenCall.set(k, it); }
    });
    items.length = 0; items.push(...merged);
    let last = 0;
    items.forEach((it) => { if (it.ph === null || it.ph === undefined) it.ph = last; last = it.ph; });
    return items;
  }
  const chipHtml = (txt, cls = "") => `<span class="chip mono ${cls}">${esc(txt)}</span>`;
  const verdict = (r) => {
    if (r.kind === "GATE_ALLOW") return `<span class="pill green">${esc(T.allowed)}</span>`;
    if (r.kind === "GATE_DENY") return `<span class="pill red">${esc(T.refused)}</span>${r.detail.code ? `<span class="chip mono rule" tabindex="0" title="${esc(r.text)}">${esc(r.detail.code)}</span>` : ""}`;
    if (r.kind === "BENEFICIARY_QUARANTINED") return `<span class="pill amber">${esc(T.quarantined)}</span>`;
    if (r.kind === "ALERT") return `<span class="pill amber">${esc(T.flagged)}</span>`;
    return "";
  };
  function rowHtml(it, i) {
    const open = R && R.open.has(it.key), enter = R && !R.seen.has(it.key);
    const multi = R && R.S && Object.keys(R.S.lanes).length > 1;
    let title = "", chips = "", raw = "", quote = false;
    if (it.type === "awx") {
      const c = it.c;
      title = callTitle(c);
      chips = `${chipHtml(c.status, c.status >= 400 ? "red" : "")}${c.id ? chipHtml(mid(c.id, 6, 4)) : ""}${c.n > 1 ? chipHtml(`×${c.n}`) : ""}`;
      raw = JSON.stringify(c, null, 1);
    } else if (it.type === "claude") {
      const c = it.c;
      title = `Agent step${c.tools && c.tools.length ? `: ${c.tools.join(", ")}` : ""}`;
      chips = `${chipHtml(modelName(c.model))}${chipHtml(`${c.ms} ms`)}`;
      raw = JSON.stringify(c, null, 1);
    } else if (it.type === "rules") {
      title = "Rules engine step";
      chips = `${chipHtml(T.rulesEngine)}${chipHtml(`${it.c.ms} ms`)}`;
      raw = JSON.stringify(it.c, null, 1);
    } else {
      const r = it.r;
      quote = r.kind === "AGENT_NOTE";
      title = (multi && r.tenant ? `${nm2(r.tenant)}: ` : "") + r.text;
      const id = r.detail.transfer_id || r.detail.request_id;
      chips = `${verdict(r)}${id ? chipHtml(mid(id, 6, 4)) : chipHtml(`#${r.detail.seq}`)}`;
      raw = R.rows[r.detail.seq] ? JSON.stringify(R.rows[r.detail.seq], null, 1) : "…";
    }
    return `<li class="tr ${enter ? "enter" : ""} ${quote ? "quote" : ""}" style="--i:${Math.min(i, 5)}" data-k="${esc(it.key)}">
      <button type="button" class="rowbtn" data-pl="row" data-k="${esc(it.key)}" ${it.r ? `data-seq="${it.r.detail.seq}"` : ""} aria-expanded="${open}">
        <span class="tt">${quote ? `<span class="small muted">${esc(T.agentSays)}</span> ` : ""}${esc(title)}</span><span class="tc">${chips}</span></button>
      ${open ? `<pre class="raw">${esc(raw)}</pre>` : ""}</li>`;
  }
  const nm2 = (t) => (R.S && R.S.employers[t] ? R.S.employers[t].name : t);
  const secs = (items) => (items.length > 1 ? `${((Date.parse(items[items.length - 1].ts) - Date.parse(items[0].ts)) / 1000).toFixed(1)} s` : "");

  function proofRow() {
    const p = R.proof;
    if (!p) return "";
    const certs = Object.values(p.certs), valid = certs.length && certs.every((c) => c.valid && c.result === "PASS");
    const chain = p.report.chain.ok, probes = p.report.probes || [];
    const iso = probes.length ? (probes.every((x) => x.ok) ? T.pass : T.fail) : T.isoOne;
    const open = R.open.has("proof");
    return `<li class="tr"><button type="button" class="rowbtn" data-pl="row" data-k="proof" aria-expanded="${open}"><span class="tt">${esc(valid ? T.certValid : T.certBad)} · ${esc(chain ? T.chainOk : T.chainBad)} · ${esc(T.isoLine)} ${esc(iso)}</span>
      <span class="tc"><span class="pill ${p.report.ok && valid ? "green" : "red"}">${esc(p.report.ok && valid ? T.pass : T.fail)}</span></span></button>
      ${open ? `<pre class="raw">${esc(JSON.stringify({ chain: p.report.chain, probes, certs: Object.fromEntries(Object.entries(p.certs).map(([k, v]) => [k, { valid: v.valid, result: v.result }])) }, null, 1))}</pre>` : ""}</li>`;
  }

  function renderTrace() {
    const items = traceItems(), by = [[], [], [], []];
    items.forEach((it) => by[it.ph].push(it));
    const lanes = Object.entries(R.S.lanes);
    const pending = lanes.filter(([, l]) => l.state === "AWAITING_APPROVAL" && l.diff);
    const approved = lanes.some(([, l]) => ["READY", "RELEASING", "RELEASED", "DONE"].includes(l.state));
    let n = 0;
    const group = (i, title, rows, extra = "") => `<section class="ph"><header><span class="pn">${i + 1}</span><h3>${esc(title)}</h3><span class="pt mono">${esc(secs(rows))}</span></header>
      ${rows.length || extra ? `<ol class="rows">${rows.map((it) => rowHtml(it, n++)).join("")}${extra}</ol>` : `<p class="small muted wait">${esc(T.phWait[i])}</p>`}</section>`;
    const batch = pending.map(([t, l]) => `<li class="tr"><span class="rowbtn static"><span class="tt">${esc(R.S.employers[t].name)}: ${l.lines.length} ${l.lines.length === 1 ? T.people1 : T.peopleN} · ${esc(totalsText(l.diff.totals))}</span><span class="tc"><span class="pill amber">${esc(RUN_LABEL.AWAITING_APPROVAL)}</span></span></span></li>`).join("");
    const unpaid = R.ended && !lanes.every(([, l]) => l.state === "DONE");
    const end = unpaid ? `<p class="small muted wait end">${esc(T.endedUnpaid)}</p>` : "";
    const proof = proofRow();
    const html = `${group(0, T.ph[0], by[0])}${group(1, T.ph[1], by[1])}${group(2, approved && !pending.length ? "Approved" : T.ph[2], by[2], batch)}${group(3, T.ph[3], by[3])}
      <section class="ph"><header><span class="pn">5</span><h3>${esc(T.ph[4])}</h3></header>${proof ? `<ol class="rows">${proof.replace('class="tr"', `class="tr ${R.seen.has("proof") ? "" : "enter"}"`)}</ol>` : `<p class="small muted wait">${esc(R.S.agent_busy || !approved ? T.phWait[4] : T.proofWait)}</p>`}</section>${end}`;
    const changed = setHtml("trace", $("#rv-trace"), html);
    items.forEach((it) => R.seen.add(it.key)); if (proof) R.seen.add("proof");
    return changed;
  }

  /* ---------- result column ---------- */
  const approver = (l) => (R.S.users || []).find((u) => u.role === (l.diff && l.diff.approver_role));
  const tidOf = (ln) => { const r = [...R.TL].reverse().find((x) => x.detail.request_id === ln.request_id && x.detail.transfer_id); return r ? r.detail.transfer_id : null; };

  function renderBalances() {
    const lanes = Object.entries(R.S.lanes), multi = lanes.length > 1;
    const rows = [];
    lanes.forEach(([t, l]) => Object.entries(l.wallet || {}).sort().forEach(([c, a]) => {
      const k = `${t}:${c}`;
      if (!(k in R.baseline)) R.baseline[k] = cents(a);
      const d = R.baseline[k] - cents(a);
      rows.push(`<div class="bal">${multi ? `<span class="small muted">${esc(l.name)}</span>` : "<span></span>"}<span class="ccy">${esc(c)}</span><span class="num" data-bal="${esc(k)}" data-v="${esc(a)}">${esc(groupC(cents(a)))}</span><span class="delta num">${d > 0n ? `↓ ${esc(groupC(d))}` : ""}</span></div>`);
    }));
    const html = `<h3>${esc(T.balances)}</h3>${rows.length ? `<div class="bals">${rows.join("")}</div>` : `<p class="small muted">${esc(T.balancesWait)}</p>`}`;
    if (!setHtml("bal", $("#r-bal"), html)) return;
    root().querySelectorAll("[data-bal]").forEach((el) => {
      const to = cents(el.dataset.v), from = R.disp[el.dataset.bal];
      R.disp[el.dataset.bal] = to;
      if (from === undefined || from === to || reduced()) return;
      const t0 = performance.now(), d = to - from;
      const step = (now) => {
        const p = Math.min(1, (now - t0) / 400), e = 1 - (1 - p) ** 3;
        el.textContent = groupC(from + (d * BigInt(Math.round(e * 1000))) / 1000n);
        if (p < 1 && el.isConnected) requestAnimationFrame(step);
      };
      requestAnimationFrame(step);
    });
  }

  function fundingBlock(f, name) {
    const acct = f.account_number || f.iban || "";
    const rows = [["Pay into", `${name}'s own ${f.currency} account`], ["Account", acct], [(f.routing_type || "Routing").toUpperCase(), f.routing_value || ""], ["Reference", f.reference], [T.fundNeed, fmtMoney(f.currency, f.amount)]];
    return `<div class="funding" aria-label="${esc(T.fundTitle)}">${rows.filter((r) => r[1]).map((r) => `<div class="row"><span>${esc(r[0])}</span><span class="num">${esc(r[1])}${["Account", "Reference"].includes(r[0]) ? ` ${copyBtn(r[1])}` : ""}</span></div>`).join("")}</div>`;
  }

  function renderAct() {
    const lanes = Object.entries(R.S.lanes), multi = lanes.length > 1;
    const html = lanes.map(([t, l]) => {
      const x = l.text, tone = { idle: "grey", amber: "amber", blue: "blue", green: "green", red: "red" }[x.tone] || "grey";
      const head = `<div class="status">${multi ? `<strong>${esc(l.name)}</strong>` : ""}<span class="pill ${tone}">${esc(l.state ? RUN_LABEL[l.state] : T.agentWorking)}</span><span>${esc(x.status)}</span></div><p class="small muted">${esc(x.next)}</p>`;
      let body = "";
      if (!R.ended) {
        if (l.funding) body += `${fundingBlock(l.funding, l.name)}<button type="button" data-pl="topup" data-t="${esc(t)}" ${R.pending.has("topup") ? "disabled" : ""}>${esc(T.topup)}</button>`;
        if (l.state === "AWAITING_APPROVAL" && l.diff) {
          const who = approver(l);
          body += `<h3>${esc(T.whatYouApprove)}</h3>${diffHtml(l.diff)}<div class="diff-row"><strong>${esc(T.lineTotal)}</strong><strong class="num">${esc(totalsText(l.diff.totals))}</strong></div>
            <button type="button" class="primary hold" data-hold="${esc(t)}" ${who ? "" : "disabled"}><span class="fill"></span><span class="lbl">${esc(multi ? `${T.holdToApprove}: ${l.name}` : `${T.holdToApprove} ${T.asFinance}`)}</span></button>
            <p class="small muted">${esc(fmt(T.approverNote, { name: l.name }))}</p>`;
        }
        if (["AWAITING_APPROVAL", "READY", "AWAITING_FUNDS"].includes(l.state)) body += `<button type="button" class="quiet" data-pl="hold" data-t="${esc(t)}">${esc(T.pauseRun)}</button>`;
        else if (l.state === "HELD") body += `<button type="button" class="quiet" data-pl="resume" data-t="${esc(t)}">${esc(T.resumeRun)}</button>`;
      }
      return `<div class="blk" data-t="${esc(t)}">${head}${body}</div>`;
    }).join("");
    if (!setHtml("act", $("#r-act"), html)) return;
    root().querySelectorAll("[data-hold]").forEach((b) => {
      const t = b.dataset.hold, l = R.S.lanes[t], who = approver(l);
      const label = b.querySelector(".lbl").textContent;
      holdToApprove(b, label, async () => {
        b.disabled = true;
        try { await api(`${base()}/approve`, { user: who.id, tenant: t }); } catch (e) { $("#rv-note").textContent = e.message; }
        schedule();
      });
    });
  }

  function renderPay() {
    const lanes = Object.entries(R.S.lanes), multi = lanes.length > 1;
    const out = lanes.map(([t, l]) => l.lines.map((ln) => {
      const tid = tidOf(ln), rc = tid && R.rechecks[tid];
      const rcHtml = !rc ? "" : rc.busy ? `<p class="small muted">${esc(T.rechecking)}</p>` : rc.err ? `<p class="small ferr">${esc(rc.err)}</p>`
        : `<p class="small"><span class="muted">${esc(T.asOf)}</span> <span class="mono">${esc(clockSec(rc.fetched_at))}</span> · <span class="muted">${esc(T.status)}</span> <span class="mono">${esc(rc.status)}</span> <button type="button" class="link" data-pl="raw" data-id="${esc(tid)}">${esc(T.rawJson)}</button></p>${R.open.has(`rc:${tid}`) ? `<pre class="raw">${esc(JSON.stringify(rc.raw, null, 1))}</pre>` : ""}`;
      return `<li><div class="pr"><span class="nm" title="${esc(ln.name)}">${esc(ln.name)}${multi ? ` <span class="small muted">${esc(l.name)}</span>` : ""}</span><span class="num">${money(ln.currency, ln.amount)}</span>${pillHtml(ln.pill)}
        ${tid ? `<button type="button" class="quiet icon" data-pl="recheck" data-id="${esc(tid)}" title="${esc(T.recheck)}" aria-label="${esc(T.recheck)}: ${esc(ln.name)}">⟳</button>` : "<span></span>"}</div>${rcHtml}</li>`;
    }).join("")).join("");
    setHtml("pay", $("#r-pay"), `<h3>${esc(T.payouts)}</h3>${out ? `<ul class="pays">${out}</ul>` : `<p class="small muted">${esc(T.noPayouts)}</p>`}`);
  }

  function evidenceHtml(r, show) {
    const e = r && r.evidence;
    if (!e) return "";
    return `<dl class="ev"><dt>${esc(T.evInput)}</dt><dd>${esc(e.input)}</dd>
      <dt>${esc(T.evDecided)}</dt><dd>${esc(e.decided_by)}${e.rule ? ` <span class="chip mono">${esc(e.rule)}</span>` : ""}<br><span class="muted">${esc(e.decision)}</span></dd>
      <dt>${esc(T.evRecorded)}</dt><dd>${e.seq != null ? `<span class="mono">#${esc(e.seq)} ${esc(e.hash || "")}</span> <button type="button" class="link" ${show || `data-pl="rows" data-seqs="${esc((r.seqs || [e.seq]).slice(0, 20).join(","))}"`}>${esc(T.evShow)}</button>` : ""}</dd></dl>`;
  }

  function renderNext() {
    const S = R.S, lanes = Object.values(S.lanes), multi = lanes.length > 1;
    const offered = Object.fromEntries(S.scenarios.map((s) => [s.id, s]));
    const paid = lanes.some((l) => l.lines.some((ln) => ln.pill === "Paid"));
    const sent = lanes.some((l) => ["READY", "RELEASED", "DONE"].includes(l.state));
    const order = paid ? ["late_return", "double_click", "bank_change_email", "injection"] : sent ? ["double_click", "bank_change_email", "injection"] : ["bank_change_email", "injection", "double_click"];
    if (multi) order.push("cross_tenant_call");
    const fit = (id) => offered[id] && (id !== "late_return" || paid) && (id !== "double_click" || sent);
    const ran = order.filter((id) => offered[id] && offered[id].last);
    const todo = order.filter((id) => fit(id) && !(offered[id].last)).slice(0, 3);
    const item = (id) => {
      const s = offered[id], r = s.last;
      return `<li><button type="button" data-pl="sc" data-id="${esc(id)}" ${R.pending.has(id) || R.ended ? "disabled" : ""}>${esc(T.tn[id] || s.title)}</button>
        ${r ? `<p class="small verdict ${r.ok ? "ok" : "no"}">${esc(r.summary)}</p>${evidenceHtml(r)}` : ""}</li>`;
    };
    const list = [...ran, ...todo];
    setHtml("next", $("#r-next"), list.length ? `<h3>${esc(T.tryNext)}</h3><ul class="nx">${list.map(item).join("")}</ul>` : "");
  }

  function renderCert() {
    const p = R.proof, lanes = Object.entries(R.S.lanes), multi = lanes.length > 1;
    const html = p ? `<div class="certs">${lanes.map(([t, l]) => `<a class="btn" href="${esc(base())}/cert/${esc(t)}" download>${esc(T.cert)}${multi ? `: ${esc(l.name)}` : ""}</a>`).join("")}</div>`
      : `<p class="small muted">${esc(T.certNone)}</p>`;
    setHtml("cert", $("#r-cert"), html);
  }

  function renderRun() {
    renderHead();
    root().querySelector(".runcols").hidden = false;
    const trace = renderTrace();
    renderBalances(); renderAct(); renderPay(); renderNext(); renderCert();
    if (trace && !R.focusing) root().querySelectorAll(".rowbtn[aria-expanded='true']").forEach(() => {});
    document.title = `${names().join(" · ")} · Ringfence`;
  }

  /* ---------- actions ---------- */
  async function act(key, fn) {
    if (R.pending.has(key)) return;
    R.pending.add(key); if (R.S) renderRun();
    try { return await fn(); } catch (e) { $("#rv-note").textContent = e.message; } finally { R.pending.delete(key); schedule(); if (R && R.S) renderRun(); }
  }
  async function loadRow(seq, key) {
    if (R.rows[seq]) return;
    R.rows[seq] = { loading: true };
    try { const [row] = await api(`${base()}/ledger?seqs=${seq}`); R.rows[seq] = row || { missing: true }; } catch (e) { R.rows[seq] = { error: e.message }; }
    if (R && R.S) { R.html.trace = null; renderTrace(); }
  }
  async function showRows(b, seqs) {
    try {
      const rows = await api(`${b}/ledger?seqs=${seqs}`), d = $("#dlg-rows");
      d.innerHTML = `<header><h2 id="rows-title">${esc(T.ledgerRows)}</h2><button type="button" class="quiet" data-close>${esc(T.close)}</button></header><div class="body">${rows.map((r) => `<div><strong>#${r.seq} ${esc(r.kind)}</strong> <span class="detail" style="display:inline" title="${esc(r.hash)}">${esc(mid(r.hash, 8, 6))}</span> ${copyBtn(r.hash)}<pre>${esc(JSON.stringify(r.payload, null, 1))}</pre></div>`).join("") || `<p>${esc(T.noRows)}</p>`}</div>`;
      d.showModal();
    } catch (e) { toast(e.message); }
  }

  document.addEventListener("click", (ev) => {
    const el = ev.target.closest("[data-pl]");
    if (!el || !root().contains(el)) return;
    const a = el.dataset.pl;
    if (a === "be") { H.backend = el.dataset.v; H.touchedBackend = true; paintSeg(); if ($("#pl-run")) paint(); }
    else if (a === "ex") {
      const p = T.presets[Number(el.dataset.i)], ta = $("#pl-text");
      ta.value = p.text; H.text = p.text; H.ferr = ""; $("#pl-ferr").textContent = ""; H.note = []; $("#pl-notes").innerHTML = "";
      if (p.sim) { H.backend = "fake"; H.touchedBackend = true; paintSeg(); }
      paintRead(); $("#pl-read").focus();
    }
    else if (a === "read") doRead();
    else if (a === "edit") { H.phase = "compose"; home(); $("#pl-text").focus(); }
    else if (a === "run") doRun();
    else if (a === "runfake") { H.backend = "fake"; H.touchedBackend = true; paintSeg(); doRun(); }
    else if (a === "addp") { H.form.employers[Number(el.dataset.e)].people.push({ name: "", country: "GB", hours: "", rate: "" }); H.serr = {}; home(); }
    else if (a === "adde") { H.form.employers[Number(el.dataset.e)].emails.push({ from: "", body: "" }); H.serr = {}; home(); }
    else if (a === "rmp") { H.form.employers[Number(el.dataset.e)].people.splice(Number(el.dataset.p), 1); H.serr = {}; home(); }
    else if (a === "rme") { H.form.employers[Number(el.dataset.e)].emails.splice(Number(el.dataset.p), 1); H.serr = {}; home(); }
    else if (!R) return;
    else if (a === "row") {
      const k = el.dataset.k;
      if (R.open.has(k)) R.open.delete(k); else { R.open.add(k); if (el.dataset.seq) loadRow(el.dataset.seq, k); }
      R.html.trace = null; if (R.S) renderTrace(); else renderPre();
    }
    else if (a === "share") { navigator.clipboard.writeText(location.href).then(() => { R.shared = true; renderHead(); setTimeout(() => { if (R) { R.shared = false; renderHead(); } }, 2000); }).catch(() => {}); }
    else if (a === "hold") act("hold", () => api(`${base()}/hold`, { user: "operator", tenant: el.dataset.t }));
    else if (a === "resume") act("resume", () => api(`${base()}/resume`, { user: "operator", tenant: el.dataset.t }));
    else if (a === "topup") act("topup", () => api(`${base()}/scenario/topup?tenant=${encodeURIComponent(el.dataset.t)}`, {}));
    else if (a === "sc") {
      const id = el.dataset.id, t = Object.keys(R.S.lanes)[0];
      act(id, () => api(`${base()}/scenario/${id}${id === "cross_tenant_call" ? "" : `?tenant=${encodeURIComponent(t)}`}`, {}));
    }
    else if (a === "recheck") {
      const id = el.dataset.id;
      R.rechecks[id] = { busy: true }; renderPay();
      api(`${base()}/recheck/${encodeURIComponent(id)}`).then((r) => { R.rechecks[id] = r; }).catch((e) => { R.rechecks[id] = { err: e.message }; }).finally(() => { if (R) renderPay(); });
    }
    else if (a === "raw") { const k = `rc:${el.dataset.id}`; if (R.open.has(k)) R.open.delete(k); else R.open.add(k); renderPay(); }
    else if (a === "rows") showRows(base(), el.dataset.seqs);
    else if (a === "retryfake") {
      api("/api/play/worlds", { spec: R.spec, backend: "fake" }).then((w) => { try { sessionStorage.setItem(`rf_spec_${w.wid}`, JSON.stringify(R.spec)); } catch (_) { /* private mode */ } location.hash = `#/try/${w.wid}`; })
        .catch((e) => { $("#rv-note").textContent = e.message; });
    }
  });

  /* form edits: update the model, repaint only the live parts */
  const onEdit = (e) => {
    const f = e.target.dataset && e.target.dataset.f;
    if (!f || !H.form) return;
    setPath(f, e.target.type === "checkbox" ? e.target.checked : e.target.value);
    delete H.serr[f];
    if (/\.(pays_from)$/.test(f)) paint(); else paint();
  };
  document.addEventListener("input", onEdit);
  document.addEventListener("change", onEdit);

  /* keyboard: Ctrl or Cmd + Enter, j and k between trace rows, ? for the list */
  document.addEventListener("keydown", (e) => {
    if (!root() || root().hidden) return;
    const typing = e.target.closest("input,select,textarea");
    if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
      if ($("#pl-run")) { e.preventDefault(); doRun(); } else if ($("#pl-read")) { e.preventDefault(); doRead(); }
      return;
    }
    if (typing || e.metaKey || e.ctrlKey || e.altKey) return;
    if (e.key === "j" || e.key === "k") {
      const rows = [...root().querySelectorAll(".rowbtn:not(.static)")];
      if (!rows.length) return;
      const i = rows.indexOf(document.activeElement);
      rows[Math.max(0, Math.min(rows.length - 1, i + (e.key === "j" ? 1 : -1)))].focus();
    } else if (e.key === "?") {
      const d = $("#dlg-keys");
      d.innerHTML = `<header><h2 id="keys-title">${esc(T.keysTitle)}</h2><button type="button" class="quiet" data-close>${esc(T.close)}</button></header><div class="body">${T.keys.map(([k, v]) => `<div class="diff-row"><span>${esc(v)}</span><span class="mono">${esc(k)}</span></div>`).join("")}</div>`;
      if (!d.open) d.showModal();
    }
  });

  /* dropping a file anywhere on the page shows the veil over the composer */
  const dragging = (e) => e.dataTransfer && [...(e.dataTransfer.types || [])].includes("Files");
  document.addEventListener("dragenter", (e) => { if (dragging(e) && $("#pl-veil")) { H.drag++; $("#pl-veil").hidden = false; } });
  document.addEventListener("dragover", (e) => { if (dragging(e) && $("#pl-veil")) e.preventDefault(); });
  document.addEventListener("dragleave", (e) => { if (dragging(e) && $("#pl-veil")) { H.drag = Math.max(0, H.drag - 1); if (!H.drag) $("#pl-veil").hidden = true; } });
  document.addEventListener("drop", (e) => {
    if (!dragging(e) || !$("#pl-veil")) return;
    e.preventDefault(); H.drag = 0; $("#pl-veil").hidden = true;
    const f = e.dataTransfer.files[0]; if (f) takeFile(f);
  });

  addEventListener("DOMContentLoaded", () => { $("#problem").innerHTML = `<p>${esc(T.problemStrip)}</p><a href="#/">${esc(T.tryYours)}</a>`; });

  return { route, evidenceHtml, showRows };
})();
