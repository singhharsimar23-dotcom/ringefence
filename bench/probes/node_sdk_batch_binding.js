// Offline: @airwallex/node-sdk (official, beta) batch status check under two per-employer clients. No network.
// The fake mirrors live sandbox behaviour seen in batch-status-empty-wrong-binding-resubmit.out.txt:
//   GET /batch_transfers/{id}/items for a batch the bearer's account does not own -> 200 {"items": []}.
// Usage: node bench/probes/node_sdk_batch_binding.js <path-to-extracted-sdk-package>
const http = require('http');
const path = require('path');
const { Airwallex } = require(path.resolve(process.argv[2]));
const owner = { batch_NW_PAYROLL: 'acct_NORTHWIND' };
const seen = [];
const srv = http.createServer((req, res) => {
  req.resume();
  req.on('end', () => {
    res.writeHead(200, { 'content-type': 'application/json' });
    if (req.url.startsWith('/api/v1/authentication/login'))
      return res.end(JSON.stringify({ token: 'tok_for_' + req.headers['x-login-as'], expires_at: '2099-01-01T00:00:00+0000' }));
    const acct = (req.headers['authorization'] || '').replace('Bearer tok_for_', '');
    const m = req.url.match(/batch_transfers\/([^/]+)\/items/);
    seen.push({ url: req.url, acct });
    const mine = m && owner[m[1]] === acct;
    res.end(JSON.stringify({ items: mine ? [{ request_id: 'nw-2026-11-13-ada', status: 'BOOKED', transfer_id: 'tr_1' }] : [] }));
  });
});
srv.listen(0, '127.0.0.1', async () => {
  const base = 'http://127.0.0.1:' + srv.address().port;
  Object.defineProperty(Airwallex.prototype, 'basePath', { get: () => base });
  const mk = (acct) => new Airwallex({ clientId: 'c', apiKey: 'k', accountId: acct, env: 'demo', enableTelemetry: false });
  const northwind = mk('acct_NORTHWIND');
  const kestrel = mk('acct_KESTREL'); // built second, e.g. the next employer's job in the same process
  const r = await northwind.payouts.batchTransfers.getItemsByBatchId('batch_NW_PAYROLL', { page_size: 1000 });
  const s = seen.pop();
  console.log('northwind client GET items -> sent as account', s.acct, '| response', JSON.stringify(r));
  const booked = (r.items || []).filter((i) => i.status === 'BOOKED').length;
  console.log('docs recovery reads: booked items =', booked, booked === 0 ? '-> "nothing booked, resubmit a new batch"' : '');
  console.log('RESULT wrong_binding=%s empty_200_reads_as_nothing_booked=%s', s.acct !== 'acct_NORTHWIND', booked === 0);
  srv.close();
  process.exit(0);
});
