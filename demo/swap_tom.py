"""Off-camera swap for the Demo Day shoot: change Tom's bank account on Airwallex for BOTH agents.

    python demo/swap_tom.py 99999901    left Tom (payroll:tom) and the right Tom of the newest Ringfence run
    python demo/swap_tom.py --left 12345601    revert only the left Tom (the right run's world is thrown away anyway)
"""
from __future__ import annotations

import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts.mcp_smoke import set_account, tom_beneficiary  # noqa: E402
from standard_mcp import ACCT, set_tom  # noqa: E402
from awx import env  # noqa: E402

HOST = "https://ringfence-hs23-eu.indiasouthcentral.cloudapp.azure.com"


def main(args: list[str]) -> None:
    left_only = args[:1] == ["--left"]
    number = args[-1] if args else ""
    if not (number.isdigit() and len(number) == 8):
        sys.exit(__doc__)
    set_tom(number)
    print(f"left Tom -> ..{number[-4:]}")
    if left_only:
        return
    r = httpx.get(f"{HOST}/approve/latest", headers={"x-enroll-key": env("RF_ENROLL_KEY")}, timeout=20)
    r.raise_for_status()
    wid = r.json()["run_id"]
    set_account(ACCT, tom_beneficiary(wid, ACCT), number)
    print(f"right Tom (run {wid[:6]}) -> ..{number[-4:]}")


if __name__ == "__main__":
    main(sys.argv[1:])
