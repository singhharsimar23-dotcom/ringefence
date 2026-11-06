// Offline probe: what does @airwallex/node-sdk send when it auto-retries after a timeout?
// The official Developer MCP (@airwallex/developer-mcp 0.3.0-beta.13) calls
//   airwallex.post("/api/v1/transfers/create", body_with_fresh_uuid_request_id, {headers: {"x-on-behalf-of": id}})
// on node-sdk 2.1.0-beta.5. This replays that call against a local fake server (fake creds, no network).
// Usage: node bench/probes/probe_node_sdk_retry.js <path-to-node-sdk/package>
"use strict";
const http = require("http");
const path = require("path");
const sdkRoot = process.argv[2];
if (!sdkRoot) { console.error("usage: node probe_node_sdk_retry.js <node-sdk package dir>"); process.exit(2); }
const { Airwallex } = require(path.join(sdkRoot, "dist", "index.js"));
const { apiClient } = require(path.join(sdkRoot, "dist", "client", "apiClient.js"));
const { HttpClientImpl } = require(path.join(sdkRoot, "dist", "client", "httpClient.js"));

const seen = [];
let creates = 0, lists = 0;
const server = http.createServer((req, res) => {
  let raw = "";
  req.on("data", (c) => (raw += c));
  req.on("end", () => {
    const url = req.url.split("?")[0];
    const reply = (code, obj, delay = 0) => setTimeout(() => {
      res.writeHead(code, { "content-type": "application/json" }); res.end(JSON.stringify(obj));
    }, delay);
    if (url === "/api/v1/authentication/login") return reply(201, { token: "fake", expires_at: "2099-01-01T00:00:00+0000" });
    const rec = { method: req.method, url, on_behalf_of: req.headers["x-on-behalf-of"] || null, body: raw ? JSON.parse(raw) : null };
    seen.push(rec);
    if (url === "/api/v1/transfers/create") {
      creates++;
      // attempt 1 LANDS (201) but answers after the client's timeout; the retry is judged like Airwallex would
      if (creates === 1) return reply(201, { id: "tr_landed", status: "SCHEDULED", request_id: rec.body.request_id }, 900);
      return rec.body && rec.body.request_id ? reply(400, { code: "duplicate_request_id" })
                                             : reply(400, { code: "validation_failed", message: "request_id is required" });
    }
    if (url === "/api/v1/transfers") { lists++; return reply(200, { items: [] }, lists === 1 ? 900 : 0); }
    reply(404, {});
  });
});

server.listen(0, "127.0.0.1", async () => {
  const port = server.address().port;
  const awx = new Airwallex({ clientId: "fake", apiKey: "fake", accountId: "acct_platform", env: "demo",
                              enableTelemetry: false, timeout: 400, retryDelay: 10 });
  apiClient.client = new HttpClientImpl(`http://127.0.0.1:${port}`, awx.config);  // point at the fake
  apiClient.setInterceptors();
  const body = { beneficiary_id: "ben_1", reason: "salary", reference: "payroll", request_id: require("crypto").randomUUID(),
                 source_currency: "GBP", transfer_amount: 2, transfer_currency: "GBP", transfer_method: "LOCAL" };
  let createErr = null, listErr = null;
  try { await awx.post("/api/v1/transfers/create", body, { headers: { "x-on-behalf-of": "acct_employer_b" } }); }
  catch (e) { createErr = `${e.name} ${e.status || ""} ${e.message}`; }
  try { await awx.get("/api/v1/transfers", { headers: { "x-on-behalf-of": "acct_employer_b" } }); }
  catch (e) { listErr = `${e.name} ${e.status || ""} ${e.message}`; }
  await new Promise((r) => setTimeout(r, 1200));
  console.log(JSON.stringify({ requests_seen_by_server: seen, create_error_shown_to_caller: createErr,
                               list_error_shown_to_caller: listErr }, null, 2));
  const retry = seen.filter((s) => s.url === "/api/v1/transfers/create")[1];
  const listRetry = seen.filter((s) => s.url === "/api/v1/transfers")[1];
  // self-check: the bug is present iff the retried POST lost its request_id and its on-behalf-of header
  console.log("RETRY_POST_LOST_BODY:", !!retry && !(retry.body && retry.body.request_id));
  console.log("RETRY_POST_LOST_ON_BEHALF_OF:", !!retry && retry.on_behalf_of === null);
  console.log("RETRY_GET_LOST_ON_BEHALF_OF:", !!listRetry && listRetry.on_behalf_of === null);
  server.close();
});
