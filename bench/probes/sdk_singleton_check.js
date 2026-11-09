// Offline proof of the node-sdk process-global singleton. NO network, NO money.
// Run from the scratch install dir:  node <path-to-this-file>
// (cwd must be the dir whose node_modules has @airwallex/node-sdk@2.1.0-beta.5)
const path = require('path');
const base = path.join(process.cwd(), 'node_modules', '@airwallex', 'node-sdk');
const sdk = require(base);
const apiMod = require(path.join(base, 'dist', 'client', 'apiClient'));
const Airwallex = sdk.Airwallex;

const A = new Airwallex({ clientId: 'cid_A', apiKey: 'key_A', accountId: 'acct_AAAA', env: 'demo' });
const B = new Airwallex({ clientId: 'cid_B', apiKey: 'key_B', accountId: 'acct_BBBB', env: 'demo' });

// give each instance a distinct sentinel token (bypasses the network login entirely)
A._token = 'TOKEN_FROM_A';
B._token = 'TOKEN_FROM_B';

const singletonBoundTo = apiMod.apiClient.getAirwallex();
console.log('Constructed A (acct_AAAA) then B (acct_BBBB).');
console.log('module singleton apiClient.getAirwallex().config.accountId =', singletonBoundTo.config.accountId);
console.log('module singleton would send token =', singletonBoundTo._token);

// Prove A's API namespace routes through that same module singleton, not through A.
// Stub the singleton's post so nothing leaves the process; capture that A's call lands here.
let captured = null;
const realPost = apiMod.apiClient.post.bind(apiMod.apiClient);
apiMod.apiClient.post = (url, cfg, data) => { captured = { url, tokenThatWouldBeUsed: apiMod.apiClient.getAirwallex()._token }; return Promise.resolve({ stubbed: true }); };

Promise.resolve(A.payouts.transfers.createTransfer({
  request_id: 'probe-singleton-0001', beneficiary_id: 'ben_x',
  transfer_amount: 1, transfer_currency: 'GBP', transfer_method: 'LOCAL', reason: 'test', reference: 'test',
})).catch(() => {}).finally(() => {
  apiMod.apiClient.post = realPost;
  console.log('\nCalled A.payouts.transfers.createTransfer(...)');
  console.log('  request routed through module singleton?', captured !== null);
  console.log('  token the SDK would attach =', captured && captured.tokenThatWouldBeUsed);
  const bug = captured && captured.tokenThatWouldBeUsed === 'TOKEN_FROM_B';
  console.log('\nRESULT:', bug
    ? "CONFIRMED: a call on instance A goes out with B's token (B is the last-constructed instance). The SDK is a process-global singleton."
    : "NOT reproduced: A's call used A's token. Singleton claim does not hold as described.");
  process.exit(bug ? 0 : 2);
});
