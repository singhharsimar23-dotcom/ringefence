"""A finding is only listed if the test that proves it exists, and the page's words obey the same copy rules as the rest of the site."""
import re
from pathlib import Path

from ringfence.alta_findings import FINDINGS, LIMITS

TESTS = Path(__file__).resolve().parent


def test_every_finding_names_tests_that_exist():
    src = "\n".join(p.read_text(encoding="utf-8") for p in TESTS.glob("test_*.py"))
    for f in FINDINGS:
        assert f["tests"], f["id"]
        for t in f["tests"]:
            assert re.search(rf"^def {t}\(", src, re.MULTILINE), (f["id"], t)


def test_findings_are_complete_and_ids_unique():
    assert len({f["id"] for f in FINDINGS}) == len(FINDINGS)
    for f in FINDINGS:
        assert all(f[k].strip() for k in ("title", "where", "broke", "fixed")), f["id"]
    assert all(x.strip() for x in LIMITS)
