"""Mutation testing for the pure core (gate.py, mandate.py, money.py). Runs on Windows and Linux.

Each mutant is one small AST change (a flipped comparison, and/or swapped, a check forced to True or False, an
off-by-one constant, a swapped refusal code, ...). It is written into a private copy of the package and the
tests run against that copy, so the repo is never touched. Stage 1 runs the fast unit and property tests and
stops at the first failure. Only mutants that survive stage 1 run the whole offline suite.

  uv run python scripts/mutate.py                      all three files
  uv run python scripts/mutate.py --files gate --limit 20
  uv run python scripts/mutate.py --out mutation.json --min-score 90

Mutants a human has judged equivalent (no observable change) are listed in scripts/mutation_equivalent.json."""
from __future__ import annotations

import argparse
import ast
import copy
import json
import os
import queue
import shutil
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PKG = ROOT / "ringfence"
TARGETS = {"gate": "gate.py", "mandate": "mandate.py", "money": "money.py"}
STAGE1 = ["tests/test_gate.py", "tests/test_money.py", "tests/test_properties.py"]
STAGE2 = ["tests", "-m", "not live and not live_llm"]
EQUIV = ROOT / "scripts" / "mutation_equivalent.json"

CMP = {ast.Eq: [ast.NotEq], ast.NotEq: [ast.Eq], ast.Lt: [ast.LtE], ast.LtE: [ast.Lt], ast.Gt: [ast.GtE],
       ast.GtE: [ast.Gt], ast.In: [ast.NotIn], ast.NotIn: [ast.In], ast.Is: [ast.IsNot], ast.IsNot: [ast.Is]}
ARITH = {ast.Add: ast.Sub, ast.Sub: ast.Add, ast.Mult: ast.Div, ast.Div: ast.Mult}
SWAP = {"max": "min", "min": "max", "any": "all", "all": "any"}
ROUNDING = ("ROUND_HALF_EVEN", "ROUND_DOWN")


def reason_codes() -> tuple[str, ...]:
    for n in ast.parse((PKG / "gate.py").read_text(encoding="utf-8")).body:
        if isinstance(n, ast.Assign) and getattr(n.targets[0], "id", "") == "REASON_CODES":
            return tuple(e.value for e in n.value.elts)
    return ()


CODES = reason_codes()


class Mutator(ast.NodeTransformer):
    """Counts candidates when target < 0, applies the target-th one otherwise. Same traversal both times."""

    def __init__(self, target: int, is_gate: bool):
        self.target, self.is_gate, self.n, self.found, self.quiet = target, is_gate, 0, None, 0

    def hit(self, node, desc: str) -> bool:
        i, self.n = self.n, self.n + 1
        if i == self.target:
            self.found = (getattr(node, "lineno", 0), desc)
        return i == self.target

    # annotations are not behaviour
    def visit_arg(self, node):
        return node

    def visit_AnnAssign(self, node):
        if node.value is not None:
            node.value = self.visit(node.value)
        return node

    def visit_ClassDef(self, node):  # decorators like @dataclass(frozen=True) are not logic
        node.body = [self.visit(s) for s in node.body]
        return node

    def visit_FunctionDef(self, node):
        node.args = self.visit(node.args)
        node.body = [self.visit(s) for s in node.body]
        return node

    def visit_Expr(self, node):  # docstrings
        return node if isinstance(node.value, ast.Constant) else self.generic_visit(node)

    def visit_JoinedStr(self, node):  # f-string text is a message
        return node

    def visit_Compare(self, node):
        self.generic_visit(node)
        for i, op in enumerate(node.ops):
            for new in CMP.get(type(op), []):
                if self.hit(node, f"{type(op).__name__} -> {new.__name__}"):
                    node.ops[i] = new()
                    return node
        return node

    def visit_BoolOp(self, node):
        self.generic_visit(node)
        new = ast.Or if isinstance(node.op, ast.And) else ast.And
        if self.hit(node, f"{type(node.op).__name__} -> {new.__name__}"):
            node.op = new()
        return node

    def visit_UnaryOp(self, node):
        self.generic_visit(node)
        if isinstance(node.op, ast.Not) and self.hit(node, "remove not"):
            return node.operand
        return node

    def visit_BinOp(self, node):
        self.generic_visit(node)
        new = ARITH.get(type(node.op))
        if new and self.hit(node, f"{type(node.op).__name__} -> {new.__name__}"):
            node.op = new()
        return node

    def visit_Constant(self, node):
        if isinstance(node.value, bool):
            if self.hit(node, f"{node.value} -> {not node.value}"):
                return ast.copy_location(ast.Constant(not node.value), node)
        elif isinstance(node.value, int):
            if self.hit(node, f"{node.value} -> {node.value + 1}"):
                return ast.copy_location(ast.Constant(node.value + 1), node)
        elif isinstance(node.value, str) and not self.quiet and 0 < len(node.value) <= 12:
            if self.hit(node, f"{node.value!r} -> 'XX{node.value}XX'"):
                return ast.copy_location(ast.Constant(f"XX{node.value}XX"), node)
        return node

    def visit_Name(self, node):
        if node.id == "ROUND_HALF_UP" and isinstance(node.ctx, ast.Load):
            for r in ROUNDING:
                if self.hit(node, f"ROUND_HALF_UP -> {r}"):
                    return ast.copy_location(ast.Constant(r), node)
        return node

    def visit_Call(self, node):
        name = node.func.id if isinstance(node.func, ast.Name) else None
        quiet = name in ("Deny", "MoneyError", "TypeError")  # messages and details are text, not behaviour
        self.quiet += quiet
        self.generic_visit(node)
        self.quiet -= quiet
        if name in SWAP and self.hit(node, f"{name} -> {SWAP[name]}"):
            node.func = ast.copy_location(ast.Name(SWAP[name], ast.Load()), node.func)
        elif name == "abs" and len(node.args) == 1 and self.hit(node, "remove abs"):
            return node.args[0]
        elif name == "Deny" and node.args and isinstance(node.args[0], ast.Constant) \
                and node.args[0].value in CODES:
            i = CODES.index(node.args[0].value)
            if self.hit(node, f"code {CODES[i]} -> {CODES[(i + 1) % len(CODES)]}"):
                node.args[0] = ast.copy_location(ast.Constant(CODES[(i + 1) % len(CODES)]), node.args[0])
        elif name == "Decimal" and node.args and isinstance(node.args[0], ast.Constant) \
                and isinstance(node.args[0].value, str):
            try:
                from decimal import Decimal
                bumped = str(Decimal(node.args[0].value) + 1)
            except Exception:
                return node
            if self.hit(node, f"Decimal({node.args[0].value!r}) -> {bumped!r}"):
                node.args[0] = ast.copy_location(ast.Constant(bumped), node.args[0])
        return node

    def visit_Return(self, node):
        self.generic_visit(node)
        if not self.is_gate or node.value is None:
            return node
        v = node.value
        if isinstance(v, ast.Call) and getattr(v.func, "id", "") == "Deny":
            if self.hit(node, "Deny -> Allow"):
                node.value = ast.copy_location(ast.parse("Allow()", mode="eval").body, v)
        elif isinstance(v, ast.Call) and getattr(v.func, "id", "") == "Allow":
            if self.hit(node, "Allow -> Deny"):
                node.value = ast.copy_location(ast.parse("Deny('MUTANT')", mode="eval").body, v)
        elif isinstance(v, ast.Constant) and v.value is None:
            if self.hit(node, "None -> Deny"):
                node.value = ast.copy_location(ast.parse("Deny('MUTANT')", mode="eval").body, v)
        return node

    def _test(self, node, kind):
        self.generic_visit(node)
        for val in (False, True):
            if self.hit(node, f"{kind} test -> {val}"):
                node.test = ast.copy_location(ast.Constant(val), node.test)
                return node
        return node

    def visit_If(self, node):
        return self._test(node, "if")

    def visit_IfExp(self, node):
        return self._test(node, "if-expression")

    def visit_While(self, node):
        return self._test(node, "while")


def mutants(path: Path):
    """Yields (index, line, description, mutated source) for every distinct mutant of one file."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    base = ast.unparse(tree)
    total = Mutator(-1, path.name == "gate.py")
    total.visit(copy.deepcopy(tree))
    seen = {base}
    for i in range(total.n):
        m = Mutator(i, path.name == "gate.py")
        t = ast.fix_missing_locations(m.visit(copy.deepcopy(tree)))
        src = ast.unparse(t)
        if src in seen:
            continue
        seen.add(src)
        yield i, m.found[0], m.found[1], src


def run(cmd, cwd, env, timeout):
    try:
        p = subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return "timeout", ""
    return p.returncode, p.stdout[-400:]


def pytest_cmd(args):
    return [sys.executable, "-m", "pytest", "-q", "-x", "--no-header", "-p", "no:cacheprovider", "-p", "no:randomly",
            *[str(ROOT / a) if a.startswith("tests") else a for a in args]]


def judge(code) -> str:
    return {0: "survived", 1: "killed", "timeout": "timeout"}.get(code, "crashed")  # 2, 3, 4: import or collection error


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--files", nargs="+", default=list(TARGETS), choices=list(TARGETS))
    ap.add_argument("--workers", type=int, default=min(6, os.cpu_count() or 2))
    ap.add_argument("--limit", type=int, default=0, help="first N mutants per file, for a smoke run")
    ap.add_argument("--out", default="")
    ap.add_argument("--min-score", type=float, default=0.0, help="exit 1 below this percent (equivalents excluded)")
    args = ap.parse_args()

    equiv = {(e["file"], e["line_text"], e["desc"]): e["why"] for e in json.loads(EQUIV.read_text())} \
        if EQUIV.exists() else {}
    work = Path(tempfile.mkdtemp(prefix="rf_mut_"))
    dirs: queue.Queue = queue.Queue()
    for w in range(args.workers):  # one private copy of the package per worker
        shutil.copytree(PKG, work / str(w) / "ringfence", ignore=shutil.ignore_patterns("__pycache__"))
        dirs.put(work / str(w))
    env_base = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}  # a stale .pyc must never hide a mutant

    def env_for(d):
        return {**env_base, "PYTHONPATH": str(d)}

    d = dirs.get()
    code, out = run(pytest_cmd(STAGE1), d, env_for(d), 600)  # the harness itself must pass on unmutated code
    dirs.put(d)
    if code != 0:
        print("unmutated copy fails stage 1, fix that first:\n", out)
        return 2

    jobs = []
    for key in args.files:
        path = PKG / TARGETS[key]
        lines = path.read_text(encoding="utf-8").splitlines()
        items = list(mutants(path))
        for i, line, desc, src in (items[:args.limit] if args.limit else items):
            jobs.append((TARGETS[key], line, lines[line - 1].strip() if line else "", desc, src))
    print(f"{len(jobs)} mutants, {args.workers} workers", flush=True)

    def work_one(job):
        fname, line, text, desc, src = job
        d = dirs.get()
        target = d / "ringfence" / fname
        try:
            target.write_text(src, encoding="utf-8")
            code, _ = run(pytest_cmd(STAGE1), d, env_for(d), 600)
            stage = 1
            if code == 0:
                code, _ = run(pytest_cmd(STAGE2), d, env_for(d), 1500)
                stage = 2
        finally:
            shutil.copyfile(PKG / fname, target)
            dirs.put(d)
        r = {"file": fname, "line": line, "line_text": text, "desc": desc, "result": judge(code), "stage": stage}
        if r["result"] == "survived":
            r["equivalent"] = equiv.get((fname, text, desc))
        print(f"{r['result']:9} {fname}:{line} {desc}", flush=True)
        return r

    t0 = time.time()
    with ThreadPoolExecutor(args.workers) as ex:
        results = list(ex.map(work_one, jobs))
    secs = time.time() - t0
    shutil.rmtree(work, ignore_errors=True)

    count = lambda r: sum(1 for x in results if x["result"] == r)  # noqa: E731
    survivors = [x for x in results if x["result"] == "survived"]
    judged_equiv = [x for x in survivors if x["equivalent"]]
    killed = len(results) - len(survivors)
    real = [x for x in survivors if not x["equivalent"]]
    score = 100 * killed / max(1, len(results) - len(judged_equiv))
    summary = {"mutants": len(results), "killed": killed, "killed_by_test_failure": count("killed"),
               "killed_by_crash": count("crashed"), "killed_by_timeout": count("timeout"),
               "killed_in_stage_2": sum(1 for x in results if x["stage"] == 2 and x["result"] != "survived"),
               "survived": len(survivors), "judged_equivalent": len(judged_equiv), "survived_unexplained": len(real),
               "raw_score_percent": round(100 * killed / max(1, len(results)), 1),
               "score_excluding_equivalents_percent": round(score, 1), "seconds": round(secs), "workers": args.workers,
               "per_file": {f: {"mutants": sum(1 for x in results if x["file"] == f),
                                "survived": sum(1 for x in survivors if x["file"] == f)} for f in sorted({x["file"] for x in results})}}
    print(json.dumps(summary, indent=2))
    for x in real:
        print("SURVIVED", f"{x['file']}:{x['line']}", x["desc"], "|", x["line_text"])
    if args.out:
        Path(args.out).write_text(json.dumps({"summary": summary, "survivors": survivors}, indent=2))
    return 1 if score < args.min_score else 0


if __name__ == "__main__":
    sys.exit(main())
