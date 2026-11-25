"use strict";
/* The arena on /alta: replays the recorded live attacks, one animated lane per side. It uses $, h, link and explorer from alta.js
   at call time. Nothing here talks to the chain; every cell is a row the attack lab wrote when it ran on the testnet. */
const arena = { rows: {}, sel: null, busy: false, lost: [0, 0] };
const usd = (n) => "USD " + (Math.round(n * 100) / 100).toFixed(2);
const wait = (ms) => new Promise((r) => setTimeout(r, ms));
const order = () => Object.keys(arena.rows).sort();

function setupArena(a) {
  if (!a) {
    $("run").disabled = $("runall").disabled = true;
    $("stage-note").textContent = "The attack lab has not been run on this server yet.";
    return;
  }
  for (const r of a.rows) (arena.rows[r.attack] ||= []).push(r);
  for (const n of order()) {
    const b = h("button", "pick", h("span", "mono small muted", "attack " + n), h("span", "", a.attacks[n].name));
    b.type = "button";
    b.setAttribute("role", "radio");
    b.addEventListener("click", () => choose(n));
    $("picks").append(b);
  }
  choose(order()[0]);
  $("run").addEventListener("click", () => play(arena.sel));
  new IntersectionObserver((es, io) => { if (es[0].isIntersecting) { io.disconnect(); play(order()[0]); } }, { threshold: 0.5 }).observe($("stage"));
  $("runall").addEventListener("click", async () => {
    for (const n of order()) { await play(n); await wait(450); }
  });
}

function choose(n) {
  if (arena.busy) return;
  arena.sel = n;
  [...$("picks").children].forEach((b, i) => b.setAttribute("aria-checked", String(order()[i] === n)));
  const rows = arena.rows[n];
  for (const [i, k] of ["a", "b"].entries()) {
    const row = rows[i];
    $("lane-" + k).className = "lane";
    $("lane-" + k).querySelector(".k").textContent = row ? row.side : "n/a";
    $("v-" + k).textContent = row ? "ready" : "";
    $("n-" + k).textContent = "";
    $("dest-" + k).textContent = row ? row.to.slice(0, 8) + "…" + row.to.slice(-4) : "wallet";
  }
}

async function runLane(k, row, delay) {
  const el = $("lane-" + k);
  await wait(delay);
  el.classList.add("go");
  $("v-" + k).textContent = "pulling " + row.usdz + " USDZ…";
  await wait(1100);
  const paid = row.outcome === "paid";
  el.classList.add(paid ? "paid" : "refused");
  const why = row.reason.length > 34 ? "the chain rejected the bind" : row.reason;
  $("v-" + k).textContent = paid ? "PAID, " + usd(Number(row.usd_lost)) + " gone" : "REFUSED, " + why;
  const n = $("n-" + k);
  n.replaceChildren(row.note ? row.note + ". " : "");
  if (row.tx) n.append(link(row.tx.slice(0, 14) + "…", explorer + row.tx));
  arena.lost[k === "a" ? 0 : 1] += Number(row.usd_lost);
}

async function play(n) {
  if (arena.busy || !n) return;
  choose(n);
  arena.busy = true;
  $("run").disabled = $("runall").disabled = true;
  const [first, second] = arena.rows[n];
  await Promise.all([runLane("a", first, 0), second ? runLane("b", second, 450) : Promise.resolve()]);
  $("s-a").textContent = usd(arena.lost[0]);
  $("s-b").textContent = usd(arena.lost[1]);
  arena.busy = false;
  $("run").disabled = $("runall").disabled = false;
}

function stats(a, nfind) {
  if (!a) return;
  const by = (side) => a.rows.filter((r) => r.outcome === "paid" && r.side === side).length;
  const unprot = a.rows.filter((r) => r.outcome === "paid").length;
  const items = [[order().length, "attacks run live on the testnet"], [unprot, "paid out on the unprotected side"],
    [a.rows.length - unprot, "refused on chain, each with a transaction"], [nfind, "defects found and fixed, each with a test"]];
  const root = $("stats");
  for (const [n, label] of items) {
    const b = h("b", "", "0");
    root.append(h("div", "", b, h("span", "small muted", label)));
    let t = 0;
    const step = () => { t += 1; b.textContent = String(Math.round((n * Math.min(t, 24)) / 24)); if (t < 24) setTimeout(step, 40); };
    setTimeout(step, 300);
  }
}

function reveal() {
  const io = new IntersectionObserver((es) => es.forEach((e) => e.isIntersecting && (e.target.classList.add("seen"), io.unobserve(e.target))), { threshold: 0.12 });
  document.querySelectorAll(".scene:not(.hero), .mnode").forEach((el) => { el.classList.add("rv"); io.observe(el); });
}
