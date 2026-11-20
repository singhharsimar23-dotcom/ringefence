"""Fuzz target: a hostile timesheet either parses into valid hours or raises TimesheetError, nothing else.

Run on Linux: `uv run --with atheris python fuzz/fuzz_timesheet.py -max_total_time=60`.
tests/test_fuzz_timesheet.py checks the same property under Hypothesis on every CI run.
"""
from __future__ import annotations

import sys
from decimal import Decimal


def check(text: str) -> None:
    from ringfence import inbox, seed

    try:
        hours = inbox.parse_timesheet("kestrel", text)
    except inbox.TimesheetError:
        return
    known = seed.contractors("kestrel")
    assert hours, "an accepted timesheet has rows"
    for cid, h in hours.items():
        assert cid in known, f"unknown contractor accepted: {cid!r}"
        assert 0 < h <= 80 and h == h.quantize(Decimal("0.01")), f"hours out of range: {h}"


def main() -> None:
    import atheris

    with atheris.instrument_imports():
        from ringfence import inbox, seed  # noqa: F401

    def one_input(data: bytes) -> None:
        check(atheris.FuzzedDataProvider(data).ConsumeUnicodeNoSurrogates(len(data)))

    atheris.Setup(sys.argv, one_input)
    atheris.Fuzz()


if __name__ == "__main__":
    main()
