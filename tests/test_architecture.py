"""T0 exit-gate architecture rules, enforced by scanning source."""
import ast
import re
from pathlib import Path

PKG = Path(__file__).resolve().parents[1] / "ringfence"
MONEY_MODULES = ["money", "gate", "executor", "fx", "funding", "fees"]
NO_SHADOW = ["gate", "executor", "funding", "fx", "fees", "agent"]


def _tree(name):
    f = PKG / f"{name}.py"
    return ast.parse(f.read_text(encoding="utf-8")) if f.exists() else None


def test_no_floats_in_money_logic():
    for name in MONEY_MODULES:
        t = _tree(name)
        if t is None:
            continue
        for n in ast.walk(t):
            assert not (isinstance(n, ast.Constant) and isinstance(n.value, float)), f"{name}:{n.lineno} float literal"
            assert not (isinstance(n, ast.Call) and getattr(n.func, "id", "") == "float"), f"{name}:{n.lineno} float()"  # isinstance(x, float) guards are fine


def test_shadow_not_imported_by_decision_code():
    for name in NO_SHADOW:
        t = _tree(name)
        if t is None:
            continue
        for n in ast.walk(t):
            mods = [n.module or ""] + [a.name for a in n.names] if isinstance(n, ast.ImportFrom) else \
                [a.name for a in n.names] if isinstance(n, ast.Import) else []
            assert not any("shadow" in m for m in mods), f"{name} imports shadow"


def test_on_behalf_of_only_in_probe():
    for f in PKG.glob("*.py"):
        if f.name == "fake_awx.py":
            continue
        src = f.read_text(encoding="utf-8")
        hits = [m.start() for m in re.finditer(r"on-behalf-of", src)]
        if f.name != "awx.py":
            assert not hits, f"{f.name} mentions x-on-behalf-of"
            continue
        for pos in hits:  # in awx.py every use must sit inside probe_cross_tenant or its docstring
            start = src.rfind("def ", 0, pos)
            assert src.startswith("def probe_cross_tenant", start) or src[start:start + 40].startswith("def probe_cross_tenant"), \
                "x-on-behalf-of outside probe_cross_tenant"
