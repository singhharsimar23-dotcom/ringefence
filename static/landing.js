"use strict";
/* Landing page. Every number comes from this server (/api/state, /api/proof, /api/gauntlet, /api/ledger, /api/timeline);
   when a fetch fails the page says so instead of showing a made-up value. Without JS the HTML is readable as it is.
   Motion never depends on scroll position: content is visible by default and each scene animates once when it enters. */
(() => {
  if (/^#\/(demo|rules|proof|try)/.test(location.hash)) { location.replace(`/app${location.hash}`); return; }

  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => [...r.querySelectorAll(s)];
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const j = (u) => fetch(u).then((r) => (r.ok ? r.json() : Promise.reject(new Error(String(r.status)))));
  const T = { ago: (s) => (s < 90 ? "just now" : s < 5400 ? `${Math.round(s / 60)} min ago` : `${Math.round(s / 3600)} h ago`) };
  const fmt = (s) => { const [i, f = ""] = String(s).split("."); return `${i.replace(/\B(?=(\d{3})+(?!\d))/g, ",")}.${`${f}00`.slice(0, 2)}`; };
  const set = (sel, text) => { const el = $(sel); if (el) el.textContent = text; };

  /* a recorded run on the live sandbox beats an offline one; every figure says which it was */
  const pick = (a) => (a || []).find((x) => x.backend === "live") || (a || [])[0];
  const where = (x) => (x && x.backend === "live" ? "Airwallex sandbox" : "offline test double, not Airwallex");

  const reduce = matchMedia("(prefers-reduced-motion: reduce)").matches;
  const motion = !reduce && !!(window.gsap && window.ScrollTrigger);
  if (motion) {
    document.documentElement.classList.add("js");
    gsap.registerPlugin(ScrollTrigger, window.DrawSVGPlugin);
  }
  const once = (trigger, fn) => { if (motion) ScrollTrigger.create({ trigger, start: "top 80%", once: true, onEnter: fn }); };

  /* ---- data ---- */
  const state = j("/api/state").catch(() => null);
  const proof = j("/api/proof").catch(() => null);
  const gaunt = j("/api/gauntlet").catch(() => null);
  const build = j("/static/build.json").catch(() => null);
  const tline = j("/api/timeline?after=0").catch(() => []);
  const isFake = (s) => !!(s && s.backend && s.backend !== "live");

  /* hero: balances, status strip */
  Promise.all([state, proof]).then(([s, p]) => {
    const bal = (p && p.balances) || {};
    for (const emp of $$(".emp")) {
      for (const b of $$("[data-b]", emp)) {
        const v = (bal[emp.dataset.t] || {})[b.dataset.b];
        if (v == null) { b.textContent = "n/a"; continue; }
        const [whole] = String(v).split("."), end = fmt(v);
        if (motion && Number.isSafeInteger(+whole)) {
          const o = { n: 0 };
          gsap.to(o, { n: +whole, duration: 0.6, ease: "power1.out", onUpdate: () => { b.textContent = fmt(Math.round(o.n)); }, onComplete: () => { b.textContent = end; } });
        } else b.textContent = end;
      }
    }
    const dot = $(".strip .dot");
    const ok = !!(p && p.report && p.report.probes && p.report.probes.length && p.report.probes.every((x) => x.ok));
    set("#st-reach", isFake(s) ? "Offline test double, not Airwallex" : ok ? "Airwallex sandbox reachable" : p ? "Airwallex sandbox: a check failed" : "Airwallex sandbox: no answer yet");
    if (!ok || isFake(s)) dot.classList.add("off");
    set("#st-proof", p && p.at ? `last proof ${T.ago((Date.now() - Date.parse(p.at)) / 1000)}` : "last proof not available");
    const h = p && p.report && p.report.chain && p.report.chain.hash;
    set("#st-head", h ? `ledger head ${h.slice(0, 4)}…` : "ledger head not available");
  });

  /* results band: one tile per Gauntlet test, live runs first */
  Promise.all([gaunt, build]).then(([g, b]) => {
    const r = (g && g.results) || {};
    if (b && b.tests) { set("#b-tests", String(b.tests)); $("#b-tests").closest(".tile").classList.add("pass"); }
    if (!r.date) return;
    set("#b-when", `run ${r.date}${r.commit ? `, commit ${r.commit}` : ""}`);
    const tile = (id, v, sub, pass) => { set(`#${id}`, v); if (sub) set(`#${id}-s`, sub); if (pass) $(`#${id}`).closest(".tile").classList.add("pass"); };
    const h = r.hostile_documents;
    if (h && h.claude && h.evil) {
      const moved = [h.claude.money_moved, h.evil.money_moved].map(Number);
      tile("b-money", String(moved[0] + moved[1]), `Claude fooled ${h.claude.fooled}/${h.claude.expressible}, obedient agent ${h.evil.fooled}/${h.evil.expressible}`, moved.every((x) => x === 0));
    }
    const iso = pick(r.isolation);
    if (iso) tile("b-iso", `${iso.pass ? iso.directions : 0}/${iso.directions}`, `HTTP 401 from the ${where(iso)}`, iso.pass);
    const n = pick(r.network_storm);
    if (n) tile("b-storm", String(Math.max(...n.transfers_per_line)), `${n.parallel_releases} parallel releases, ${n.answers_lost} replies lost (${n.backend === "live" ? "live" : "offline"})`, n.pass);
    if (r.tamper) tile("b-tamper", `${r.tamper.caught_at_the_right_row}/${r.tamper.mutations}`, "caught at the row that was edited", r.tamper.pass);
    if (r.sequences) tile("b-seq", String(r.sequences.sequences), `${r.sequences.steps_run} steps, invariants ${r.sequences.pass ? "held" : "broke"}`, r.sequences.pass);
  });

  /* 01: the email types itself once */
  once("#email", () => {
    const el = $("#mail-text"), mail = el.textContent, o = { n: 0 };
    gsap.timeline()
      .fromTo(o, { n: 0 }, { n: mail.length, duration: 1.6, ease: "none", onUpdate: () => { el.textContent = mail.slice(0, Math.round(o.n)); } })
      .from("#w-call", { opacity: 0, y: 16, duration: 0.4 })
      .from("#w-pay", { opacity: 0, y: 16, duration: 0.4 }, "+=0.2");
  });

  /* 02: the ring draws once, then cycles by itself; hover or focus holds a stage */
  (() => {
    const items = $$("#loop li"), ring = $(".ring");
    const name = $("#ring-name"), sub = $("#ring-sub");
    const lightAll = () => $$(".arc,.node,.rl", ring).forEach((e) => e.classList.add("on"));
    if (reduce) { lightAll(); return; }
    const show = (i) => {
      items.forEach((li) => li.classList.toggle("on", +li.dataset.i === i));
      $$("[data-i]", ring).forEach((e) => e.classList.toggle("on", +e.dataset.i === i));
      const li = items[i - 1];
      name.textContent = $("b", li).textContent; sub.textContent = $("span", li).textContent;
    };
    let i = 0, held = false, timer = null;
    const start = () => { if (!timer) timer = setInterval(() => { if (!held) show((i = (i % 4) + 1)); }, 2200); };
    items.forEach((li) => {
      const hold = () => { held = true; show((i = +li.dataset.i)); };
      li.addEventListener("mouseenter", hold); li.addEventListener("focus", hold);
      li.addEventListener("mouseleave", () => { held = false; }); li.addEventListener("blur", () => { held = false; });
    });
    const go = () => { show((i = 1)); start(); };
    if (motion && window.DrawSVGPlugin) once("#why", () => gsap.from(".ring .arc", { drawSVG: 0, duration: 0.5, stagger: 0.25, ease: "power1.inOut", onComplete: go }));
    else go();
  })();

  /* 03: recorded samples */
  gaunt.then((g) => {
    const list = (g && g.samples) || [];
    const box = $("#samples");
    if (!list.length) { set("#s-note", "No Gauntlet run is recorded on this server yet, so the example above is fixed text."); return; }
    box.innerHTML = list.slice(0, 4).map((s, i) => `<button type="button" class="chip" role="tab" aria-selected="${i === 0}" data-i="${i}">${esc(s.label)}</button>`).join("");
    const show = (i) => {
      const s = list[i];
      $$(".chip", box).forEach((c, k) => c.setAttribute("aria-selected", String(k === i)));
      set("#s-call", `${s.tool}(${JSON.stringify(s.input, null, 2)})`);
      const pill = $("#s-pill");
      pill.textContent = s.ok ? s.decision.split(/[(.,]/)[0].trim().slice(0, 40) : "Stopped by the gate";
      pill.className = `pill ${s.ok ? "hold" : "no"}`;
      set("#s-why", s.decision);
      set("#s-seq", `Ledger #${s.ledger_seq} · ${s.ledger_kind}`);
      set("#s-note", `Recorded from the Gauntlet run on the ${s.source}.`);
    };
    box.addEventListener("click", (e) => { const b = e.target.closest(".chip"); if (b) show(+b.dataset.i); });
    show(0);
  });

  /* 05: isolation matrix, each reply from the Gauntlet's isolation run */
  gaunt.then((g) => {
    const iso = pick(g && g.results && g.results.isolation);
    if (iso) set("#m-src", `Replies recorded from the ${where(iso)}, ${iso.rows.length} cross-account calls.`);
    const out = $("#m-detail");
    const keys = ["northwind", "kestrel", "harbour", "platform"];
    const cells = $$(".matrix .r").slice(1).flatMap((r, i) => $$(".cell", r).map((c, k) => ({ c, from: keys[i], to: keys[k] })));
    for (const { c, from, to } of cells) {
      c.tabIndex = 0;
      const row = iso && iso.rows.find((x) => x.from === from && x.to === to);
      if (from !== to) { c.textContent = row ? String(row.status) : "n/a"; c.classList.toggle("no", !!row && row.status === 401); }
      const say = () => {
        out.textContent = from === to ? `${from} token on its own account: allowed.` : row ? `${from} token on ${to}: HTTP ${row.status} ${row.code}` : `${from} token on ${to}: not recorded on this server.`;
        if (row) set("#m-resp", `login   x-login-as: ${from}\ncall    x-on-behalf-of: ${to}\n\nHTTP ${row.status}  ${row.code}`);
      };
      c.addEventListener("mouseenter", say); c.addEventListener("focus", say);
    }
  });

  /* 06: network storm, drawn from the recorded run: every attempt converges on one transfer per payment */
  gaunt.then((g) => {
    const n = pick(g && g.results && g.results.network_storm);
    if (!n) return;
    set("#storm-bar", `${n.backend === "live" ? "airwallex sandbox" : "offline test double"} / transfers`);
    const single = n.transfers_per_line.every((x) => x === 1);
    set("#storm-count", `${n.parallel_releases} attempts · ${single ? "1 transfer per payment" : `up to ${Math.max(...n.transfers_per_line)} transfers per payment`}`);
    const lost = Number.isInteger(n.answers_lost) ? `${n.answers_lost} replies` : "Replies";
    set("#storm-sub", `${lost} were dropped after the payment had landed. ${n.pass ? `No payment was duplicated across ${n.lines} payments and ${n.parallel_releases} releases` : "A payment was duplicated"} (${where(n)}).`);
    const W = 320, H = 180, k = n.parallel_releases, L = n.lines;
    const sy = (i) => 10 + (i * (H - 20)) / Math.max(1, k - 1), ty = (l) => ((l + 1) * H) / (L + 1);
    const paths = Array.from({ length: k }, (_, i) => {
      const t = ty(i % L), y = sy(i), cls = i < (n.answers_lost || 0) ? ' class="lost"' : "";
      return `<path${cls} d="M14 ${y} C150 ${y} 170 ${t} 280 ${t}"/><circle cx="14" cy="${y}" r="2.5"/>`;
    }).join("");
    const sinks = Array.from({ length: L }, (_, l) => `<circle class="sink" cx="290" cy="${ty(l)}" r="8"/><text x="304" y="${ty(l) + 4}">${n.transfers_per_line[l]}</text>`).join("");
    $("#streams").innerHTML = paths + sinks;
    $("#streams").setAttribute("viewBox", `0 0 ${W} ${H}`);
    $("#storm-ids").innerHTML = (n.transfer_ids || []).map((id, l) => `<li>payment ${l + 1} → ${esc(id)}</li>`).join("");
    if (motion && window.DrawSVGPlugin) once("#storm", () => gsap.from("#streams path", { drawSVG: 0, duration: 0.9, stagger: 0.02, ease: "power1.out" }));
  });

  /* 04: scoreboard */
  const cellsFor = (host, label) => { host.innerHTML = Array.from({ length: 36 }, (_, i) => `<button type="button" data-i="${i}" aria-label="${label} attack ${i + 1}"></button>`).join(""); };
  cellsFor($("#g-claude"), "Claude"); cellsFor($("#g-evil"), "Obedient agent");
  gaunt.then((g) => {
    const h = g && g.results && g.results.hostile_documents;
    const detail = $("#g-detail");
    if (!h) { detail.textContent = "No Gauntlet run is recorded on this server yet."; return; }
    const paint = (key, grid, fooledEl, moneyEl) => {
      const a = h[key]; if (!a) return;
      fooledEl.textContent = `${a.fooled} of ${a.documents}`; moneyEl.textContent = String(a.money_moved);
      a.rows.forEach((r, i) => {
        const b = $$("button", grid)[i]; if (!b) return;
        const cls = r.status === "no_tool" ? "" : r.fooled ? "hold" : "ok";
        if (cls) b.classList.add(cls);
        const out = r.status === "no_tool" ? "no tool can express this" : r.fooled ? `the agent did it. Run ended ${String(r.state || "unknown").toLowerCase()}, ${r.calls_denied} calls denied, ${r.payments} payments, ${r.money_moved} moved wrongly` : "the agent refused";
        const say = () => { detail.textContent = `${g.goals[r.goal] ? g.goals[r.goal].text : r.goal} (${r.framing.replace(/_/g, " ")}): ${out}`; };
        b.addEventListener("mouseenter", say); b.addEventListener("focus", say);
      });
    };
    paint("claude", $("#g-claude"), $("#c-fooled"), $("#c-money"));
    paint("evil", $("#g-evil"), $("#e-fooled"), $("#e-money"));
    const when = [g.results.date, g.results.commit].filter(Boolean).join(", commit ");
    if (when) set("#g-run", `One run per document (${when}). A scripted approver signs whatever the agent leaves waiting, then every payment is compared with the trusted timesheet.`);
    const sq = g.results.sequences, tm = g.results.tamper;
    if (sq) set("#f-seq", `${sq.steps_run} steps in ${sq.sequences} random sequences · invariants ${sq.pass ? "held" : "broke"}`);
    if (tm) set("#f-tamper", `${tm.caught_at_the_right_row}/${tm.mutations} ledger edits caught`);
    if (motion) once("#score", () => gsap.from(".grid button", { opacity: 0, duration: 0.2, stagger: 0.01 }));
  });

  /* 07: the ledger, checked in the browser (static/chain.js, parity-tested against ledger.py) */
  state.then(async (s) => {
    const list = $("#l-rows"), msg = $("#l-msg");
    if (!s || !s.head) { list.innerHTML = '<li class="muted">No ledger rows to show yet.</li>'; return; }
    const seqs = Array.from({ length: Math.min(20, s.head) }, (_, i) => s.head - i).reverse();
    let rows;
    try { rows = await j(`/api/ledger?seqs=${seqs.join(",")}`); } catch (_) { list.innerHTML = '<li class="muted">The ledger did not answer.</li>'; return; }
    rows.sort((a, b) => a.seq - b.seq);
    const orig = rows.map((r) => JSON.stringify(r.payload));
    const recheck = async () => {
      const bad = await RFChain.firstBreak(rows);
      $$("li", list).forEach((li, i) => li.classList.toggle("bad", bad != null && rows[i].seq >= bad));
      msg.className = `small ${bad == null ? "ok" : "no"}`;
      msg.textContent = bad == null ? `All ${rows.length} rows hold. Recomputed in your browser.` : `The chain breaks at row ${bad}, and every row after it.`;
    };
    list.innerHTML = rows.map((r, i) => `<li><span>#${esc(r.seq)}</span><span>${esc(r.kind)}</span><input data-i="${i}" aria-label="Payload of row ${esc(r.seq)}" value="${esc(JSON.stringify(r.payload))}" spellcheck="false"><span class="h" title="${esc(r.hash)}">${esc(String(r.hash || "").slice(0, 12))}</span></li>`).join("");
    list.addEventListener("input", async (e) => {
      const i = +e.target.dataset.i;
      try { rows[i].payload = JSON.parse(e.target.value); } catch (_) { rows[i].payload = { edited: e.target.value }; }
      if (e.target.value === orig[i]) { try { rows[i].payload = JSON.parse(orig[i]); } catch (_) { /* unchanged */ } }
      await recheck();
    });
    await recheck();
  });

  /* 08: follow one payment, the real ledger rows of the newest payout */
  const KEEP = new Set(["RUN_CREATED", "FUNDING_REQUESTED", "FUNDING_MATCHED", "METAL_PULL", "APPROVED", "FX_CONVERTED"]);
  Promise.all([state, tline]).then(([s, rows]) => {
    const hit = [...rows].reverse().find((r) => r.kind === "SUBMITTED" && r.detail && r.detail.transfer_id);
    if (!hit) return;
    const id = hit.detail.transfer_id, rid = hit.detail.request_id, t = hit.tenant, fake = isFake(s);
    const start = [...rows].reverse().find((r) => r.tenant === t && r.kind === "RUN_CREATED" && r.seq <= hit.seq);
    const mine = rows.filter((r) => r.tenant === t && (!start || r.seq >= start.seq)
      && (KEEP.has(r.kind) || (r.detail && (r.detail.transfer_id === id || (rid && r.detail.request_id === rid)))));
    const lbl = (r) => {
      if (r.reality === "ours" || (r.simulated && !r.reality)) return "[SIMULATED]";
      if (r.reality === "chain") return "Metal testnet";
      if (r.reality === "live" || r.reality === "awx_sim") return fake ? "offline double" : r.reality === "live" ? "Airwallex" : "Airwallex simulator";
      return "ledger";
    };
    $("#track").innerHTML = mine.map((r) => `<li class="${r.blocked ? "bad" : "on"}"><b>${esc(r.phase)} · ${esc(r.kind.toLowerCase().replace(/_/g, " "))}<span class="r">${esc(lbl(r))}</span></b><span>${esc(r.text)}</span><span class="mono small">#${esc(r.seq)} · ${esc(String(r.ts).slice(11, 19))} UTC</span></li>`).join("");
    set("#pay-who", hit.text.replace(/^Sent /, "").replace(/'s payment\.$/, ""));
    set("#pay-id", `${t} · ${id}`);
    const btn = $("#recheck"), out = $("#rc-out");
    btn.disabled = false;
    out.textContent = fake ? "[SIMULATED] offline test double: this id does not exist at Airwallex." : "";
    btn.addEventListener("click", async () => {
      btn.disabled = true; out.textContent = "Asking Airwallex";
      try { const d = await j(`/api/recheck/${encodeURIComponent(id)}`); out.textContent = `fetched just now · ${d.status} · ${d.amount} ${d.currency}`; }
      catch (_) { out.textContent = "Airwallex did not answer. Nothing changed."; }
      btn.disabled = false;
    });
    if (motion) once("#follow", () => gsap.from("#track li", { opacity: 0, x: -10, duration: 0.3, stagger: 0.12 }));

    /* what's real: one live transfer id */
    const td = $('[data-real="live"]');
    if (!td) return;
    if (fake) { td.textContent = "[SIMULATED] offline test double: this id does not exist at Airwallex."; return; }
    td.innerHTML = `${esc(id)} <button type="button" class="btn cp">Copy</button>`;
    $(".cp", td).addEventListener("click", async (e) => {
      try { await navigator.clipboard.writeText(id); e.target.textContent = "Copied"; } catch (_) { e.target.textContent = "Copy failed"; }
    });
  });

  /* 09: funding, from Harbour's funding rows */
  tline.then((rows) => {
    const last = (k) => [...rows].reverse().find((r) => r.tenant === "harbour" && r.kind === k);
    const need = last("FUNDING_REQUESTED"), got = last("FUNDING_MATCHED");
    const sent = rows.filter((r) => r.tenant === "harbour" && r.kind === "SUBMITTED" && (!got || r.seq > got.seq)).length;
    const mark = (sel, r, text) => { if (!r) return; set(sel, text); $(sel).closest("li").classList.add("on"); };
    mark("#sh-need", need, need && need.text);
    mark("#sh-dep", got, got && got.text);
    mark("#sh-rel", got && sent ? got : null, `${sent} payment${sent === 1 ? "" : "s"} released after the money landed.`);
  });

  /* 10: Metal, the on-chain rows this server wrote */
  state.then((s) => {
    const m = s && s.metal, ul = $("#sh-metal");
    if (m == null) { set("#mt-state", "off on this server"); ul.innerHTML = '<li class="muted">Metal is switched off on this server. The live demo runs it.</li>'; return; }
    set("#mt-state", m.length ? `${m.length} on chain` : "none since the last reset");
    if (!m.length) { ul.innerHTML = '<li class="muted">No Metal transactions since the last reset. <a href="/app#/demo">Run Pay from crypto wallet</a>.</li>'; return; }
    ul.innerHTML = m.slice(-6).reverse().map((x) => {
      const what = x.kind === "METAL_PULL" ? `paid ${x.usdz} USDZ` : `refused ${x.usdz} USDZ · ${x.flag || x.code || "refused"}`;
      const link = x.explorer_url ? `<a href="${esc(x.explorer_url)}" target="_blank" rel="noopener">${esc(String(x.tx).slice(0, 14))}… <span class="arr" aria-hidden="true">→</span></a>` : '<span class="muted">no tx</span>';
      return `<li><span>#${esc(x.seq)} ${esc(x.kind)} · ${esc(what)}</span>${link}</li>`;
    }).join("");
    const chain = m.find((x) => x.explorer_url), td = $('[data-real="chain"]');
    if (chain && td) td.innerHTML = `<a href="${esc(chain.explorer_url)}" target="_blank" rel="noopener">${esc(String(chain.tx).slice(0, 18))}…</a>`;
  });

  /* 12: composer, examples fill the box, then the text goes to the app's Try tab */
  $("#ex").addEventListener("click", (e) => {
    const b = e.target.closest(".chip"); if (!b) return;
    $$(".chip", $("#ex")).forEach((c) => c.setAttribute("aria-selected", String(c === b)));
    $("#mini-text").value = b.dataset.ex; $("#mini-text").focus();
  });
  const go = (mode) => {
    try { sessionStorage.setItem("rf_prefill", JSON.stringify({ text: $("#mini-text").value.slice(0, 4000), mode })); } catch (_) { /* private mode */ }
    location.href = "/app#/try";
  };
  $("#mini").addEventListener("submit", (e) => { e.preventDefault(); go("read"); });
  $("#mini-red").addEventListener("click", () => go("redteam"));

  /* footer constants */
  build.then((b) => {
    set("#f-tests", b && b.tests ? `${b.tests} tests` : "tests");
    set("#f-sha", b && b.sha ? b.sha : "commit");
    if (b && b.video) $$("[data-video]").forEach((a) => { if (a.tagName === "A") a.href = b.video; a.hidden = false; });
  });

  /* ---- entrance motion: time-based, once per element ---- */
  if (!motion) return;
  try {
    if (window.DrawSVGPlugin) gsap.from(".emp .fence rect", { drawSVG: 0, duration: 1.2, ease: "power2.out", stagger: 0.1 });
    gsap.from(".band .tile", { opacity: 0, y: 14, duration: 0.4, stagger: 0.05, ease: "power1.out", delay: 0.2 });
    ScrollTrigger.batch(".fade", {
      start: "top 92%", once: true, batchMax: 6,
      onEnter: (els) => gsap.to(els, { opacity: 1, y: 0, duration: 0.35, stagger: 0.05, ease: "power1.out", overwrite: true }),
    });
    once("#metal", () => gsap.from(".mflow > *", { opacity: 0, x: -12, duration: 0.3, stagger: 0.08 }));
    /* a page loaded mid-way (anchor link) must not leave anything hidden */
    addEventListener("load", () => ScrollTrigger.refresh());
  } catch (_) { document.documentElement.classList.remove("js"); }
})();
