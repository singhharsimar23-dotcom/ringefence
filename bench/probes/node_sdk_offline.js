// Offline probe of @airwallex/node-sdk (official, beta). No network: a local fake Airwallex on 127.0.0.1.
// Usage: node bench/probes/node_sdk_offline.js <path-to-extracted-sdk-package>
// Checks: (1) two Airwallex instances (one per employer via accountId) share one module-level apiClient;
//         (2) the built-in POST retry after a timeout sends the request options as the body and drops custom headers.
const http = require('http');
const path = require('path');
const sdk = require(path.resolve(process.argv[2]));
const { Airwallex } = sdk;
const seen = [];
let slowFirst = false;
const srv = http.createServer((req, res) => {
  let body = '';
  req.on('data', (c) => (body += c));
  req.on('end', () => {
    const acct = req.headers['x-login-as'];
    if (req.url.startsWith('/api/v1/authentication/login')) {
      res.writeHead(201, { 'content-type': 'application/json' });
      return res.end(JSON.stringify({ token: 'tok_for_' + acct, expires_at: '2099-01-01T00:00:00+0000' }));
    }
    // never log real tokens: these are fake, so recording them is the point of the probe
    seen.push({ url: req.url, auth: req.headers['authorization'], obo: req.headers['x-on-behalf-of'] || null, body: body ? JSON.parse(body) : null });
    const respond = () => { res.writeHead(201, { 'content-type': 'application/json' }); res.end(JSON.stringify({ id: 'tr_' + seen.length, status: 'SCHEDULED' })); };
    if (slowFirst) { slowFirst = false; setTimeout(respond, 1500); } else respond();
  });
});
srv.listen(0, '127.0.0.1', async () => {
  const base = 'http://127.0.0.1:' + srv.address().port;
  Object.defineProperty(Airwallex.prototype, 'basePath', { get: () => base });
  const mk = (acct, extra = {}) => new Airwallex({ clientId: 'c', apiKey: 'k', accountId: acct, env: 'demo', enableTelemetry: false, ...extra });
  const transfer = (rid) => ({ request_id: rid, beneficiary_id: 'ben_ada', source_currency: 'GBP', transfer_currency: 'GBP', transfer_amount: 100, transfer_method: 'LOCAL', reference: 'payroll', reason: 'wages_salary' });

  // (1) per-employer clients
  const northwind = mk('acct_NORTHWIND');
  const kestrel = mk('acct_KESTREL');
  await northwind.payouts.transfers.createTransfer(transfer('northwind-2026-11-13-ada'));
  const r1 = seen.pop();
  console.log('[1] northwind client create -> Authorization =', r1.auth);
  const singletonBug = r1.auth !== 'Bearer tok_for_acct_NORTHWIND';

  // (2) retry after timeout, with x-on-behalf-of as the README shows
  const plat = mk('acct_PLATFORM', { timeout: 500, retry: 1, retryDelay: 10 });
  slowFirst = true;
  let outcome;
  try { outcome = await plat.payouts.transfers.createTransfer(transfer('plat-obo-2026-11-13-ada'), { headers: { 'x-on-behalf-of': 'acct_CONNECTED' } }); }
  catch (e) { outcome = e.constructor.name + ': ' + e.message; }
  await new Promise((r) => setTimeout(r, 1700));
  console.log('[2] attempts seen by server:');
  for (const s of seen) console.log('    obo=%s body=%s', s.obo, JSON.stringify(s.body));
  console.log('    caller got:', typeof outcome === 'string' ? outcome : JSON.stringify(outcome));
  const retry = seen[seen.length - 1];
  const retryBug = seen.length >= 2 && (retry.obo === null || !(retry.body && retry.body.request_id));
  console.log('RESULT singleton_shares_last_account=%s retry_drops_body_and_headers=%s', singletonBug, retryBug);
  srv.close();
  process.exit(0);
});
