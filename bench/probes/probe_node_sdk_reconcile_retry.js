// Offline probe of @airwallex/node-sdk 2.1.0-beta.5. No network: a local fake Airwallex on 127.0.0.1, fake creds.
// Usage: node bench/probes/probe_node_sdk_reconcile_retry.js <node-sdk package dir> [<developer-mcp package dir>]
// (A) The docs say: on an uncertain create outcome, GET the payout by request_id. When THAT GET times out once,
//     the SDK's built-in retry (apiClient.js:157 passes config into the data slot) re-sends the GET with no params
//     and no headers: the request_id filter and x-on-behalf-of are dropped, and an unfiltered page comes back.
// (B) Even with the argument swap fixed, the "safe" POST retry of a create that already landed gets
//     400 duplicate_request_id, which the SDK throws as ValidationError; the MCP error string drops details.id.
"use strict";
const http = require("http");
const path = require("path");
const sdkRoot = path.resolve(process.argv[2] || "");
const { Airwallex } = require(path.join(sdkRoot, "dist", "index.js"));
const { apiClient } = require(path.join(sdkRoot, "dist", "client", "apiClient.js"));

const ledger = [ // the account's real transfers; only rid-ben's line was paid
  { id: "tr_other_1", request_id: "northwind-2026-11-13-cy", beneficiary_id: "ben_cy", status: "PAID" },
  { id: "tr_ben", request_id: "northwind-2026-11-13-ben", beneficiary_id: "ben_ben", status: "SCHEDULED" },
];
const seen = [];
let slowNext = 0; // number of upcoming non-login requests to stall past the client timeout
const srv = http.createServer((req, res) => {
  let raw = "";
  req.on("data", (c) => (raw += c));
  req.on("end", () => {
    const send = (code, obj) => { res.writeHead(code, { "content-type": "application/json" }); res.end(JSON.stringify(obj)); };
    if (req.url.startsWith("/api/v1/authentication/login")) return send(201, { token: "fake", expires_at: "2099-01-01T00:00:00+0000" });
    const u = new URL(req.url, "http://x");
    seen.push({ method: req.method, path: u.pathname, request_id_param: u.searchParams.get("request_id"), obo: req.headers["x-on-behalf-of"] || null, body: raw ? JSON.parse(raw) : null });
    let reply;
    if (req.method === "GET" && u.pathname === "/api/v1/transfers") {
      const rid = u.searchParams.get("request_id");
      reply = () => send(200, { items: rid ? ledger.filter((t) => t.request_id === rid) : ledger });
    } else if (req.method === "POST" && u.pathname === "/api/v1/transfers/create") {
      const body = raw ? JSON.parse(raw) : {};
      const dup = ledger.find((t) => t.request_id === body.request_id);
      if (dup) reply = () => send(400, { code: "duplicate_request_id", message: "The request_id has been used. Please use a different request ID if you wish to create a separate transfer.", details: { id: dup.id } });
      else if (!body.request_id) reply = () => send(400, { code: "validation_failed", message: "request_id must be provided" });
      else { const t = { id: "tr_new_" + ledger.length, request_id: body.request_id, status: "SCHEDULED" }; ledger.push(t); reply = () => send(201, t); } // commit now, answer maybe late
    } else reply = () => send(404, { code: "not_found" });
    if (slowNext > 0) { slowNext--; setTimeout(reply, 900); } else reply();
  });
});

srv.listen(0, "127.0.0.1", async () => {
  const base = "http://127.0.0.1:" + srv.address().port;
  Object.defineProperty(Airwallex.prototype, "basePath", { get: () => base });
  const awx = new Airwallex({ clientId: "c", apiKey: "k", accountId: "acct_NORTHWIND", env: "demo", enableTelemetry: false, timeout: 300, retry: 1, retryDelay: 50 });

  // (A) reconcile Ada's line (never created) by request_id, README style: params + x-on-behalf-of, first attempt times out
  slowNext = 1;
  const r = await awx.get("/api/v1/transfers", { params: { request_id: "northwind-2026-11-13-ada" }, headers: { "x-on-behalf-of": "acct_NORTHWIND" } });
  const [first, retried] = seen.splice(0);
  const items = (r && r.items) || [];
  console.log("[A] first  GET request_id=%s obo=%s", first.request_id_param, first.obo);
  console.log("[A] retry  GET request_id=%s obo=%s", retried.request_id_param, retried.obo);
  console.log("[A] reconcile result for ada: %d item(s): %s", items.length, items.map((t) => t.request_id).join(", "));
  console.log("RESULT retried_get_drops_filter=%s naive_length_check_says_paid=%s", retried.request_id_param === null, items.length > 0);

  // (B) emulate the one-line upstream fix (swap args back on retry), then lose the response of Ben's create
  const orig = apiClient._request.bind(apiClient);
  apiClient._request = (m, url, a, b) => (b && b.request_id && a && "responseType" in a ? orig(m, url, b, a) : orig(m, url, a, b));
  ledger.splice(1, 1); // Ben not yet created
  slowNext = 1; // the create lands, its response is lost; the SDK retries the same body
  let err = null;
  try { await awx.payouts.transfers.createTransfer({ request_id: "northwind-2026-11-13-ben", beneficiary_id: "ben_ben", source_currency: "GBP", transfer_currency: "GBP", transfer_amount: 2, transfer_method: "LOCAL", reason: "wages_salary", reference: "payroll" }); }
  catch (e) { err = e; }
  const creates = seen.filter((s) => s.path === "/api/v1/transfers/create");
  const booked = ledger.filter((t) => t.request_id === "northwind-2026-11-13-ben").length;
  console.log("[B] create attempts=%d booked_at_airwallex=%d caller_sees=%s status=%s", creates.length, booked, err && err.name, err && err.status);
  console.log("[B] SDK error.message: %s", err && err.message);
  // developer-mcp utils/errorHandler.js:16 builds the tool result from status + message only
  const toolText = err ? `Failed to create transfer (${err.status || 500}): ${err.message}` : "ok";
  console.log("[B] MCP tool text: %s", toolText);
  console.log("RESULT landed_create_reported_as=%s original_id_in_tool_text=%s", err && err.name, toolText.includes("tr_new_"));
  srv.close();
});
