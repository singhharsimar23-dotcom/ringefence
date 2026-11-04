"use strict";
/* The ledger's hash, in the browser. Mirrors ringfence/ledger.py entry_hash and money.canonical_json:
   sorted keys, "," and ":" separators, every character outside space..~ written as a lowercase \uXXXX escape.
   tests/test_chain_parity.py runs this file under Node against a real ledger; the page only uses it if they agree. */
const RFChain = (() => {
  const str = (s) => JSON.stringify(s).replace(/[^\x20-\x7e]/g, (c) => "\\u" + `${c.charCodeAt(0).toString(16).padStart(4, "0")}`);
  function canon(v) {
    if (v === null) return "null";
    if (typeof v === "string") return str(v);
    if (typeof v === "boolean") return v ? "true" : "false";
    if (typeof v === "number") return String(v);
    if (Array.isArray(v)) return `[${v.map(canon).join(",")}]`;
    return `{${Object.keys(v).sort().map((k) => `${str(k)}:${canon(v[k])}`).join(",")}}`;
  }
  async function entryHash(prev, row) {
    const body = canon({ seq: row.seq, ts: row.ts, run_id: row.run_id, tenant: row.tenant, kind: row.kind, payload: row.payload });
    const buf = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(prev + body));
    return [...new Uint8Array(buf)].map((b) => b.toString(16).padStart(2, "0")).join("");
  }
  /* rows oldest first. Returns the seq of the first row that does not hold, or null. A row breaks when its own hash is wrong
     or when it does not point at the hash of the row before it. */
  async function firstBreak(rows) {
    for (let i = 0; i < rows.length; i++) {
      const r = rows[i];
      if (i > 0 && r.prev_hash !== rows[i - 1].hash) return r.seq;
      if ((await entryHash(r.prev_hash, r)) !== r.hash) return r.seq;
    }
    return null;
  }
  return { canon, entryHash, firstBreak };
})();
if (typeof module !== "undefined") module.exports = RFChain;
