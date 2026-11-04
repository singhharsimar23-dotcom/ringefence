"use strict";
/* First-visit guide and hover tips for /app. Words live in copy.js (T.guide, T.tips).
   One floating card per page (Try, Three employers): it opens on the first visit, points at one control per step,
   and a "How this works" button brings it back. Steps whose control is not on the page (Metal off) are skipped. */
(() => {
  const G = T.guide, $ = (s) => document.querySelector(s);
  const page = () => (location.hash.startsWith("#/demo") ? "demo" : /^#\/(proof|rules)/.test(location.hash) ? null : "try");
  const seen = (p) => { try { return localStorage.getItem(`rf_guide_${p}`) === "1"; } catch (_) { return false; } };
  const remember = (p) => { try { localStorage.setItem(`rf_guide_${p}`, "1"); } catch (_) { /* private mode */ } };
  const shown = (el) => !!el && el.getClientRects().length > 0 && !el.closest("[hidden]");

  const box = document.createElement("aside");
  box.className = "guide"; box.hidden = true; box.setAttribute("aria-label", G.title); box.setAttribute("aria-live", "polite");
  const fab = document.createElement("button");
  fab.type = "button"; fab.className = "guide-fab"; fab.textContent = `? ${G.reopen}`; fab.hidden = true;
  const tip = document.createElement("div");
  tip.className = "tip"; tip.setAttribute("role", "tooltip"); tip.hidden = true;
  document.body.append(box, fab, tip);

  let P = null, steps = [], i = 0, hi = null;
  const unmark = () => { if (hi) hi.classList.remove("guide-hi"); hi = null; };
  const paint = () => {
    unmark();
    const s = steps[i], el = $(s.at);
    if (shown(el)) { hi = el; el.classList.add("guide-hi"); el.scrollIntoView({ block: "nearest", behavior: "smooth" }); }
    box.innerHTML = `<div class="g-head"><span>${esc(G.title)} · ${i + 1}/${steps.length}</span><button type="button" class="g-x" data-g="close" aria-label="${esc(G.close)}">×</button></div>
      <h3>${esc(s.h)}</h3><p>${esc(s.p)}</p>
      <div class="g-dots">${steps.map((_, k) => `<span class="${k === i ? "on" : ""}"></span>`).join("")}</div>
      <div class="g-foot">${i ? `<button type="button" data-g="back">${esc(G.back)}</button>` : "<span></span>"}<button type="button" class="primary" data-g="${i === steps.length - 1 ? "close" : "next"}">${esc(i === steps.length - 1 ? G.done : G.next)}</button></div>`;
  };
  const open = () => {
    steps = (G[P] || []).filter((s) => shown($(s.at)));
    if (!steps.length) return;
    i = 0; box.hidden = false; fab.hidden = true; paint();
    box.querySelector("[data-g=next],[data-g=close].primary").focus({ preventScroll: true });
  };
  const close = () => { box.hidden = true; unmark(); if (P) { remember(P); fab.hidden = false; } };
  box.addEventListener("click", (e) => {
    const g = e.target.closest("[data-g]"); if (!g) return;
    if (g.dataset.g === "close") { close(); return; }
    const cur = steps[i];  // controls can appear after the guide opened (the Metal card waits on /api/play/info)
    steps = (G[P] || []).filter((s) => s === cur || shown($(s.at))); i = steps.indexOf(cur);
    i = Math.max(0, Math.min(steps.length - 1, i + (g.dataset.g === "next" ? 1 : -1))); paint();
    box.querySelector(".g-foot .primary").focus({ preventScroll: true });
  });
  document.addEventListener("keydown", (e) => { if (e.key === "Escape" && !box.hidden) close(); });
  fab.addEventListener("click", open);

  /* the views render after data arrives, so wait until the first step's control exists */
  const start = () => {
    box.hidden = true; unmark(); P = page(); fab.hidden = !P;
    if (!P || seen(P)) return;
    let n = 0;
    const t = setInterval(() => { if (shown($(G[P][0].at)) || ++n > 40) { clearInterval(t); if (page() === P && !seen(P)) open(); } }, 150);
  };
  addEventListener("hashchange", start);
  start();

  /* hover and focus tips */
  const tipFor = (el) => { for (const [sel, text] of Object.entries(T.tips)) { const m = el.closest(sel); if (m) return [m, text]; } return null; };
  const show = (e) => {
    const hit = e.target instanceof Element && tipFor(e.target);
    if (!hit) { tip.hidden = true; return; }
    const r = hit[0].getBoundingClientRect();
    tip.textContent = hit[1]; tip.hidden = false;
    const w = tip.offsetWidth, h = tip.offsetHeight;
    tip.style.left = `${Math.max(8, Math.min(innerWidth - w - 8, r.left + r.width / 2 - w / 2))}px`;
    tip.style.top = `${r.top - h - 8 < 8 ? r.bottom + 8 : r.top - h - 8}px`;
  };
  document.addEventListener("mouseover", show);
  document.addEventListener("focusin", show);
  document.addEventListener("mouseout", (e) => { if (!e.relatedTarget || !tipFor(e.relatedTarget)) tip.hidden = true; });
  document.addEventListener("focusout", () => { tip.hidden = true; });
  addEventListener("scroll", () => { tip.hidden = true; }, { passive: true });
})();
