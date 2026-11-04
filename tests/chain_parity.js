// node tests/chain_parity.js rows.json  ->  prints the seqs whose hash the browser code recomputes differently, then the first break
const fs = require("fs");
const C = require("../static/chain.js");
(async () => {
  const rows = JSON.parse(fs.readFileSync(process.argv[2], "utf8"));
  const bad = [];
  for (const r of rows) if ((await C.entryHash(r.prev_hash, r)) !== r.hash) bad.push(r.seq);
  console.log(JSON.stringify({ bad, firstBreak: await C.firstBreak(rows) }));
})();
