"use strict";
const $ = (id) => document.getElementById(id);
const h = (tag, cls, ...kids) => {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  for (const k of kids) e.append(k);
  return e;
};
const link = (text, href) => {
  const a = h("a", "mono small", text);
  a.href = href;
  a.target = "_blank";
  a.rel = "noopener";
  return a;
};
const explorer = "https://testnet.metalntwx.com/tx/";

function cell(row) {
  const c = h("div", "cell");
  if (!row) return h("td", "", "n/a");
  const paid = row.outcome === "paid";
  const pill = h("span", "pill " + (paid ? "no" : "ok"), paid ? "paid the attacker" : row.outcome === "refused" ? "refused on chain" : row.outcome);
  c.append(pill);
  if (row.reason) c.append(h("span", "mono small", row.reason));
  if (row.note) c.append(h("span", "small muted", row.note));
  if (row.tx) c.append(link(row.tx.slice(0, 18) + "…", explorer + row.tx));
  const td = h("td");
  td.append(c);
  return td;
}

function attacks(a) {
  const body = document.querySelector("#atk-t tbody");
  if (!a) {
    $("atk-meta").textContent = "The attack lab has not been run on this server yet.";
    return;
  }
  const by = {};
  for (const r of a.rows) (by[r.attack] ||= {})[r.side] = r;
  const fin = (n) => a.attacks[n];
  for (const n of Object.keys(by).sort()) {
    const tr = h("tr");
    tr.append(h("th", "", fin(n).name), h("td", "small", fin(n).class));
    const sides = by[n];
    const first = Object.values(sides)[0];
    const keys = Object.keys(sides);
    // two columns: the first side is the unprotected one, the second is Ringfence's
    tr.append(cell(sides[keys[0]]), cell(sides[keys[1]]));
    if (keys.length === 1 && first) tr.lastChild.replaceWith(h("td", "small muted", "n/a"));
    body.append(tr);
  }
  $("atk-meta").textContent = `Run ${a.date} on ${a.network}. Principal ${a.principal.slice(0, 10)}…`;
}

function findings(list) {
  const root = $("finds");
  for (const f of list) {
    const d = h("dl");
    for (const [k, t] of [["How it was broken", f.broke], ["The fix", f.fixed]]) d.append(h("dt", "", k), h("dd", "", t));
    const refs = h("div", "ref");
    refs.append(h("span", "pill", f.where));
    for (const t of f.tests) refs.append(h("span", "mono small muted", t));
    root.append(h("article", "card", h("p", "mono small muted", f.id), h("h3", "", f.title), d, refs));
  }
}

function payroll(p) {
  const ul = $("pr-lines");
  ul.replaceChildren();
  if (!p) {
    ul.append(h("li", "muted", "No payroll has been recorded on this server yet."));
    $("pr-state").textContent = "none";
    $("recheck").disabled = true;
    return;
  }
  $("pr-state").textContent = p.cert ? p.cert.body.result : "uncertified";
  const done = Object.fromEntries((p.report?.lines || []).map((l) => [l.contractor_id, l]));
  for (const l of p.export.lines) {
    const r = done[l.contractor_id];
    ul.append(h("li", "", h("span", "", `${l.contractor_id}  USD ${l.amount}  =  ${l.usdz} USDZ`), h("span", "", r ? `${r.state}, ${r.spent_usdz} USDZ paid` : "")));
  }
}

async function recheck() {
  const b = $("recheck"), out = $("rc-out");
  b.disabled = true;
  out.textContent = "Reading the credentials from the chain. This takes a few seconds.";
  try {
    const r = await fetch("/alta/api/recheck", { method: "POST" });
    const j = await r.json();
    if (!r.ok) throw new Error(j.detail || r.status);
    const bad = j.rows.filter((x) => !x.ok);
    out.textContent = j.ok
      ? `Every credential matches what was approved (${j.rows.length - 1} lines, read from the chain just now).`
      : "Mismatch: " + bad.map((x) => `${x.line}: ${x.why}`).join("; ");
  } catch (e) {
    out.textContent = "Could not re-check: " + e.message;
  }
  b.disabled = false;
}

async function price(ev) {
  ev.preventDefault();
  const f = new FormData(ev.target), out = $("price-out");
  out.replaceChildren();
  const r = await fetch("/alta/api/price", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(Object.fromEntries(f)) });
  const j = await r.json();
  if (!r.ok) return out.append(h("li", "muted", j.detail));
  for (const l of j.lines) out.append(h("li", "", h("span", "", `${l.contractor_id}  ${l.hours} h`), h("span", "", `USD ${l.usd}  =  ${l.usdz} USDZ`)));
  out.append(h("li", "muted", `Total ${j.total_usdz} USDZ. ${j.note}.`));
}

(async () => {
  $("mcp-cmd").textContent = `claude mcp add --transport http ringfence-alta ${location.origin}/alta/mcp`;
  $("recheck").addEventListener("click", recheck);
  $("price-f").addEventListener("submit", price);
  try {
    const o = await (await fetch("/alta/api/overview")).json();
    attacks(o.attacks);
    findings(o.findings);
    payroll(o.payroll);
    for (const t of o.limits) $("limits-l").append(h("li", "", t));
  } catch (e) {
    $("atk-meta").textContent = "Could not load the results: " + e.message;
  }
})();
