// node tests/flow_model.js  ->  prints a JSON list of failed checks ([] means every check passed)
require("vm").runInThisContext(require("fs").readFileSync(require("path").join(__dirname, "../static/copy.js"), "utf8"));  // T and esc, as in the page
const Flow = require("../static/flow.js");
const bad = [];
const states = (o) => Flow.model(o).map((n) => n.state).join(",");
const eq = (name, got, want) => { if (got !== want) bad.push(`${name}: got ${got}, want ${want}`); };
const line = (pill) => ({ pill, name: "A", amount: "1.00", currency: "GBP" });
const lane = (state, extra = {}) => ({ state, lines: [line("Planned")], funding: null, ...extra });

eq("fresh world", states({ lane: null }), "idle,idle,idle,idle,idle,idle,idle");
eq("agent reading", states({ lane: null, busy: true, rows: [{ kind: "RUN_CREATED" }] }), "done,run,idle,idle,idle,idle,idle");
eq("proposed, awaiting approval", states({ lane: lane("AWAITING_APPROVAL"), rows: [{ kind: "AGENT_NOTE" }], dec: [{ tone: "ok" }] }), "done,done,done,done,you,idle,idle");
eq("short on funds", states({ lane: lane("AWAITING_FUNDS", { funding: { currency: "AUD" } }), rows: [{ kind: "AGENT_NOTE" }], dec: [{ tone: "ok" }] }), "done,done,done,you,idle,idle,idle");
eq("held", states({ lane: lane("HELD"), rows: [{ kind: "AGENT_NOTE" }], dec: [{ tone: "ok" }] }), "done,done,done,done,you,idle,idle");
eq("paying", states({ lane: lane("RELEASED", { lines: [line("On its way")] }), rows: [{ kind: "APPROVED" }, { kind: "SUBMITTED" }], dec: [{ tone: "ok" }] }), "done,done,done,done,done,run,idle");
eq("a payment came back", states({ lane: lane("RELEASED", { lines: [line("Returned")] }), rows: [{ kind: "APPROVED" }, { kind: "SUBMITTED" }], dec: [{ tone: "ok" }] }), "done,done,done,done,done,blocked,idle");
eq("done, proof pending", states({ lane: lane("DONE", { lines: [line("Paid")] }), rows: [{ kind: "APPROVED" }], dec: [{ tone: "ok" }] }), "done,done,done,done,done,done,run");
eq("done with proof", states({ lane: lane("DONE", { lines: [line("Paid")] }), rows: [{ kind: "APPROVED" }], dec: [{ tone: "ok" }], proof: { ok: true } }), "done,done,done,done,done,done,done");

const m = Flow.model({ lane: lane("AWAITING_APPROVAL"), dec: [{ tone: "ok" }, { tone: "ok" }, { tone: "refused" }], rows: [{ kind: "AGENT_NOTE" }] });
eq("rules metric", m[2].metric, "2");
eq("rules refused", String(m[2].refused), "1");
eq("active: needs you", Flow.active(m), "approve");
eq("active: running", Flow.active(Flow.model({ lane: null, busy: true, rows: [{ kind: "RUN_CREATED" }] })), "agent");
eq("active: fresh", Flow.active(Flow.model({ lane: null })), "inbox");
eq("active: all done", Flow.active(Flow.model({ lane: lane("DONE", { lines: [line("Paid")] }), rows: [{ kind: "APPROVED" }], dec: [{ tone: "ok" }], proof: {} })), "proof");

// replay: every step up to the furthest row reached, the refused branch once a refusal is reached
const r = Flow.reach([{ kind: "RUN_CREATED" }, { kind: "AGENT_NOTE" }, { kind: "GATE_DENY" }], { kind: "GATE_DENY" });
eq("reach ids", [...r.ids].join(","), "inbox,agent,rules,refused");
eq("reach cur", r.cur, "rules");
eq("reach payees", Flow.reach([{ kind: "SUBMITTED" }]).ids.has("payees"), true);

// graph: one box per employer, every payee drawn, names escaped, no edge between two employers' boxes
const lanes = ["Acme <b>", "Kite"].map((name) => ({ t: name, name, sub: "own account", nodes: m, docs: [{ label: "Timesheet", sub: "csv" }, { label: "Email", sub: "x", flag: true }],
  payees: [{ name: "Ann", amount: "GBP 1", pill: "Paid" }, { name: "Bo", amount: "GBP 2", pill: "Returned" }], replay: null }));
const g = Flow.graph(lanes, "rules", new Set(["rules"]));
eq("graph boxes", (g.html.match(/class="gbd"/g) || []).length, 2);
eq("graph payees", (g.html.match(/class="gn gp /g) || []).length, 4);
eq("graph escaped", g.html.includes("Acme <b>"), false);
eq("graph edges", (g.html.match(/<path class=/g) || []).length, 2 * (2 + 4 + 2 + 2));
eq("graph flag", g.html.includes("gd flag"), true);
eq("graph size", g.w > 1000 && g.h > 300, true);
console.log(JSON.stringify(bad));
