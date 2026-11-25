"""Fill the generated parts of docs/ALTA_SETTLEMENT.md and README.md from the committed results, so no number is typed by hand.

  python scripts/alta_docs.py

docs/ALTA_SETTLEMENT.md is rewritten from docs/ALTA_SETTLEMENT.template.md. README.md: the text between the two alta markers."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from ringfence.alta_findings import FINDINGS, LIMITS

EX = "https://testnet.metalntwx.com/tx/"


def latest(pattern: str) -> Path | None:
    f = sorted((ROOT / "docs" / "alta").glob(pattern))
    return f[-1] if f else None


def cell(r: dict | None) -> str:
    if not r:
        return "n/a"
    what = "paid" if r["outcome"] == "paid" else f"refused, `{r['reason'].split(' ')[0]}`" if r["reason"] else "refused"
    tx = f" [{r['tx'][:10]}…{r['tx'][-4:]}]({EX}{r['tx']})" if r["tx"] else ""
    return what + tx


def attacks_md() -> str:
    p = latest("attacks-*.json")
    if p is None:
        return "Not run yet."
    a = json.loads(p.read_text(encoding="utf-8"))
    by: dict[str, dict] = {}
    for r in a["rows"]:
        by.setdefault(str(r["attack"]), {})[r["side"]] = r
    out = [f"Run {a['date']}, {a['network']}.", "", "| # | Attack | Incident class | Unprotected | Ringfence |", "|---|---|---|---|---|"]
    for n in sorted(by):
        s = list(by[n].values())
        out.append(f"| {n} | {a['attacks'][n]['name']}: {a['attacks'][n]['does']} | {a['attacks'][n]['class']} | {cell(s[0])} | {cell(s[1] if len(s) > 1 else None)} |")
    return "\n".join(out)


def payroll_md() -> str:
    d = latest("payroll-*")
    if d is None or not (d / "report.json").exists():
        return "Not run yet."
    rep = json.loads((d / "report.json").read_text(encoding="utf-8"))
    cert = next(iter(sorted(d.glob("alta_*.json"))), None)
    res = json.loads(cert.read_text(encoding="utf-8"))["body"]["result"] if cert else "no certificate"
    out = [f"Recorded in [{d.name}/]({d.name}/): the approved batch, each credential file (never a pull key), the line report and the signed certificate. "
           + f"Result: **{res}**. The Airwallex fee step ran on the offline fake and is [SIMULATED]; the payments are real testnet payments.", "",
           "| Line | Ledger state | Paid (USDZ) | Checks |", "|---|---|---|---|"]
    for x in rep["lines"]:
        out.append(f"| {x['contractor_id']} | {x['state']} | {x['spent_usdz']} | {'all passed' if x['ok'] else 'FAILED: ' + ', '.join(c['name'] for c in x['checks'] if not c['ok'])} |")
    return "\n".join(out)


def findings_md() -> str:
    out = []
    for f in FINDINGS:
        out += [f"### {f['id']}. {f['title']}", f"*{f['where']}.*", "", f"**What was found.** {f['broke']}", "", f"**The fix.** {f['fixed']}", "",
                "**Tests.** " + ", ".join(f"`{t}`" for t in f["tests"]) + (f". Live: attack {f['attack']}." if f.get("attack") else "."), ""]
    return "\n".join(out)


def readme_md() -> str:
    rows = [f"| {f['id']} | {f['title']} | {f['where']} |" for f in FINDINGS]
    return "\n".join([
        "### Approval-bound settlement (new)",
        "",
        "Live page: `/alta`. MCP: `/alta/mcp`. Full write-up: [docs/ALTA_SETTLEMENT.md](docs/ALTA_SETTLEMENT.md).",
        "",
        "On a bank rail, Ringfence's gate is the only enforcer. On Alta the human's approval is compiled into the payment: an approver's device (a separate process and key) signs one single-use mandate per approved line, with the approved batch hash in its signed description. A compromised Ringfence server can then pay only the approved lines, once each, before the approval expires. The executor is the unchanged, mutation-tested one; only the client underneath it changes ([alta.py](ringfence/alta.py)).",
        "",
        "**First we broke it.** The attacker is the Ringfence server (every pull key, no owner key). Each attack ran live on the testnet against a broad mandate and against Ringfence's per-line mandates:",
        "",
        attacks_md(),
        "",
        "**Then we fixed it.** Defects found while building this, each reproduced first and each with a test:",
        "",
        "| # | Defect | Where |", "|---|---|---|", *rows,
        "",
        "How each was broken and fixed is in [docs/ALTA_SETTLEMENT.md](docs/ALTA_SETTLEMENT.md#defects-found-and-the-fix-for-each).",
        "",
        payroll_md(),
        "",
        "Audit a run without this server: `python scripts/alta_audit.py --export export.json --creds creds/ --book book.json`.",
        "",
        "Limits: " + " ".join(LIMITS),
    ])


def main() -> None:
    t = ROOT / "docs" / "ALTA_SETTLEMENT.template.md"
    if not t.exists():
        (ROOT / "docs" / "ALTA_SETTLEMENT.md").replace(t)
    doc = t.read_text(encoding="utf-8")
    for k, v in (("FINDINGS", findings_md()), ("ATTACKS", attacks_md()), ("PAYROLL", payroll_md()), ("LIMITS", "\n".join(f"- {x}" for x in LIMITS))):
        doc = doc.replace(f"<<{k}>>", v)
    (ROOT / "docs" / "ALTA_SETTLEMENT.md").write_text(doc, encoding="utf-8")
    rd = ROOT / "README.md"
    s = rd.read_text(encoding="utf-8")
    a, b = "<!-- alta:start -->", "<!-- alta:end -->"
    if a in s:
        s = s[:s.index(a) + len(a)] + "\n" + readme_md() + "\n" + s[s.index(b):]
        rd.write_text(s, encoding="utf-8", newline="")
    print("docs written")


if __name__ == "__main__":
    main()
