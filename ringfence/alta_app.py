"""The /alta page, its API and its MCP. A separate process from the main demo: it holds no key that can move money.

It shows what was run on the Alta testnet (the committed attack table and payroll certificate), and it re-reads the chain
live: `recheck` runs the auditor over the recorded payroll's public files and reports what the chain says right now. Nothing
here binds, signs, pulls or revokes."""
from __future__ import annotations

import json
import os
import re
import threading
import time
from decimal import Decimal
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import alta, metal, seed
from .alta_findings import FINDINGS, LIMITS
from .alta_verify import audit
from .awx import AwxError
from .money import price_line

ROOT = Path(__file__).resolve().parent.parent
STATIC, DOCS = ROOT / "static", ROOT / "docs" / "alta"
RECHECKS_PER_HOUR = int(os.environ.get("RF_ALTA_RECHECKS", "30"))


def _latest(pattern: str) -> Path | None:
    found = sorted(DOCS.glob(pattern))
    return found[-1] if found else None


def attacks() -> dict | None:
    p = _latest("attacks-*.json")
    return json.loads(p.read_text(encoding="utf-8")) if p else None


def payroll() -> dict | None:
    d = _latest("payroll-*")
    if d is None or not (d / "export.json").exists():
        return None
    cert = next(iter(sorted(d.glob("alta_*.json"))), None)
    return {"dir": d, "export": json.loads((d / "export.json").read_text(encoding="utf-8")),
            "book": json.loads((d / "book.json").read_text(encoding="utf-8")),
            "cert": json.loads(cert.read_text(encoding="utf-8")) if cert else None,
            "report": json.loads((d / "report.json").read_text(encoding="utf-8")) if (d / "report.json").exists() else None}


def price(hours: dict[str, str], tenant: str = "kestrel") -> dict:
    """What a payroll of these hours costs on Alta, from the registry's rates. Moves nothing and takes no wallet or amount."""
    cs = seed.contractors(tenant)
    out, total = [], Decimal(0)
    for cid, h in hours.items():
        if cid not in cs:
            raise ValueError(f"unknown contractor {cid}")
        ln = price_line(cs[cid], Decimal(str(h)))
        usdz = alta.usd_to_usdz(ln.amount)  # refuses an amount that is not whole cents
        out.append({"contractor_id": cid, "hours": str(ln.hours), "usd": str(ln.amount), "usdz": str(usdz)})
        total += usdz
    return {"tenant": tenant, "lines": out, "total_usdz": str(total), "usd_per_usdz": str(alta.USD_PER_USDZ),
            "note": "1 USDZ = USD 10 on the testnet, a fixed scale; moves nothing"}


class Recheck:
    """Re-reads the recorded payroll from the chain. One at a time, capped per hour: each call costs the chain a few reads."""

    def __init__(self, runner=None):
        self.runner, self.lock, self.times = runner or metal.run_cli, threading.Lock(), []

    def __call__(self) -> dict:
        p = payroll()
        if p is None:
            raise HTTPException(404, "No payroll has been recorded yet.")
        now = time.time()
        self.times = [t for t in self.times if now - t < 3600]
        if len(self.times) >= RECHECKS_PER_HOUR:
            raise HTTPException(429, "Too many re-checks this hour. The recorded result is shown on the page.")
        if not self.lock.acquire(blocking=False):
            raise HTTPException(409, "A re-check is already running.")
        try:
            self.times.append(now)
            rows = audit(p["export"], p["dir"] / "creds", p["book"], self.runner)
        finally:
            self.lock.release()
        return {"checked_at": int(now), "ok": all(r["ok"] for r in rows), "rows": rows,
                "limit": "Reads the chain now for the credentials in the recorded payroll's folder."}


def overview() -> dict:
    p = payroll()
    return {"network": "Alta testnet, chain 63825", "usd_per_usdz": str(alta.USD_PER_USDZ), "findings": FINDINGS, "limits": LIMITS,
            "attacks": attacks(),
            "payroll": None if p is None else {"export": p["export"], "report": p["report"], "cert": p["cert"]},
            "simulated": "Airwallex fees and the employer registry run on an offline fake; the chain is real."}


def create_app(runner=None) -> FastAPI:
    app = FastAPI(title="Ringfence on Alta", docs_url=None, redoc_url=None)
    app.mount("/static", StaticFiles(directory=STATIC), name="static")
    recheck = Recheck(runner)
    asset_v = format(int(max(f.stat().st_mtime for f in STATIC.rglob("*") if f.is_file())), "x")

    @app.get("/alta")
    def page():
        html = (STATIC / "alta.html").read_text(encoding="utf-8")
        return HTMLResponse(re.sub(r'(/static/[\w./-]+\.(?:js|css))"', rf'\1?v={asset_v}"', html))

    @app.get("/alta/healthz")
    def healthz():
        return {"ok": True}

    @app.get("/alta/api/overview")
    def api_overview():
        return JSONResponse(overview())

    @app.post("/alta/api/recheck")
    def api_recheck():
        return recheck()

    @app.post("/alta/api/price")
    def api_price(hours: dict[str, str]):
        try:
            return price(hours)
        except (ValueError, AwxError) as e:
            raise HTTPException(400, str(e)) from None

    @app.get("/alta/api/cert")
    def api_cert():
        p = payroll()
        if p is None or p["cert"] is None:
            raise HTTPException(404, "No certificate yet.")
        return p["cert"]

    @app.get("/alta/api/export")
    def api_export():
        p = payroll()
        if p is None:
            raise HTTPException(404, "No payroll recorded yet.")
        return p["export"]

    @app.get("/alta/payroll.zip")
    def payroll_zip():
        p = payroll()
        if p is None:
            raise HTTPException(404, "No payroll recorded yet.")
        import io
        import zipfile
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
            for f in sorted(p["dir"].rglob("*")):
                if f.is_file() and f.name != "m.key.json":  # never a pull key
                    z.write(f, f.relative_to(p["dir"]).as_posix())
        from fastapi.responses import Response
        return Response(buf.getvalue(), media_type="application/zip",
                        headers={"Content-Disposition": "attachment; filename=alta-payroll-proof.zip"})

    from . import alta_mcp
    alta_mcp.register(app, recheck)
    return app


def main() -> int:
    import uvicorn
    port = int(os.environ.get("RF_ALTA_PORT", "8010"))
    print(f"Ringfence on Alta at http://127.0.0.1:{port}/alta")
    uvicorn.run(create_app(), host="127.0.0.1", port=port, workers=1, log_level="warning")
    return 0


__all__ = ["create_app", "overview", "price"]

if __name__ == "__main__":
    raise SystemExit(main())
