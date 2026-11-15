// node tests/flow_model.js  ->  prints a JSON list of failed checks ([] means every check passed)
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
console.log(JSON.stringify(bad));
