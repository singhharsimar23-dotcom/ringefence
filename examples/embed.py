"""Use the Ringfence engine in your own code, no web app, no keys: a fake Airwallex runs offline.

    uv run python examples/embed.py

The same calls work on the live sandbox: swap `build_backend("fake")` for `build_backend("live")`.
"""
import os
import tempfile
from pathlib import Path

os.environ.setdefault("RF_VAR", tempfile.mkdtemp(prefix="rf-embed-"))  # where the ledger lives

from ringfence import setup_demo, verify
from ringfence.agent.loop import pay_date
from ringfence.awx import build_backend
from ringfence.config import var_dir
from ringfence.ledger import Ledger
from ringfence.orchestrator import Orchestrator, Refused


def main() -> dict:
    awx, _ = build_backend("fake")
    setup_demo.setup(awx)
    o = Orchestrator(awx, Ledger(Path(var_dir()) / "ringfence.db"))
    run = o.create_run("northwind", pay_date())          # priced in Decimal on Northwind's own account
    print("price :", o.diff(run, "northwind")["totals"])
    o.submit(run, "northwind")                           # Northwind's mandate needs a person
    try:
        o.approve(run, "northwind", "maya", "operator")  # the wrong role is refused
    except Refused as e:
        print("refused:", e)
    o.approve(run, "northwind", "priya", "finance:northwind")  # signs this exact batch
    print("state :", o.advance(run, "northwind"))        # sends it; request IDs fixed, bank details inline
    rep = verify.report(o.awx, o.L)
    print("verify: ok =", rep["ok"])
    return rep


if __name__ == "__main__":
    main()
