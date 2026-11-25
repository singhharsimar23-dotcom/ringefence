"""Exhaustive check of the Alta settlement rule against a fully hostile server (no TLA+ tool needed: plain Python, every state).

World: two approved lines, A (payee PA, 2 USDZ) and B (payee PB, 3 USDZ). The server may, in any order and any number of times:
pull any credential it holds to any payee for any amount, and ask for a line to be reopened. The chain refuses a pull that
breaks the credential's payee, per-payment cap, budget, occurrence count, or that is revoked. The device, when it re-signs a
reopened line, revokes the earlier credentials first (config `revoke`) and refuses if one already paid.

Invariants: PaidOnlyApproved (every payment goes to an approved line's payee and is at most its amount: a mandate caps a payment, so
underpaying is possible and alta_verify flags it, overpaying or diverting is not) and NoDoublePay (at most one
payment per line). Configs: ringfence must hold; naive (one broad credential) must violate PaidOnlyApproved; no_revoke (a
reopen that leaves the old credential payable) must violate NoDoublePay, which is the defect A1.

  python formal/alta_model.py"""
from itertools import product

LINES = {"A": ("PA", 2), "B": ("PB", 3)}
PAYEES, AMOUNTS = ("PA", "PB", "MULE"), (1, 2, 3, 4)


def mint(line):
    p, a = LINES[line]
    return (line, p, a, a, 1, 0, 0, False)  # line, payee, cap, budget, occurrences, spent, count, revoked


def broad():
    return ("*", None, max(a for _, a in LINES.values()), sum(a for _, a in LINES.values()), 10**9, 0, 0, False)


def pull(m, payee, amt):
    line, p, cap, budget, occ, spent, n, rev = m
    if rev or (p is not None and payee != p) or amt > cap or n >= occ or spent + amt > budget:
        return None
    return (line, p, cap, budget, occ, spent + amt, n + 1, rev)


def steps(state, mode):
    creds, paid = state
    for i, m in enumerate(creds):
        for payee, amt in product(PAYEES, AMOUNTS):
            if (m2 := pull(m, payee, amt)) is not None:
                yield creds[:i] + (m2,) + creds[i + 1:], paid + ((m[0], payee, amt),)
    if mode != "naive":
        for line in LINES:
            held = [m for m in creds if m[0] == line]
            if mode == "ringfence" and any(m[6] for m in held):
                continue  # the device never re-signs a line whose earlier credential paid
            if len(held) >= 2:
                continue  # bound the search: one reopen per line
            new = tuple((*m[:7], True) if (mode == "ringfence" and m[0] == line) else m for m in creds)
            yield (*new, mint(line)), paid


def violations(paid):
    out = set()
    cap = {p: a for p, a in LINES.values()}
    if any(payee not in cap or amt > cap[payee] for _, payee, amt in paid):  # a mandate caps a payment: less is possible, more never
        out.add("PaidOnlyApproved")
    by_payee: dict = {}
    for _, payee, _amt in paid:
        by_payee[payee] = by_payee.get(payee, 0) + 1
    if any(n > 1 for n in by_payee.values()):
        out.add("NoDoublePay")
    return out


def check(mode):
    start = (tuple(mint(x) for x in LINES) if mode != "naive" else (broad(),), ())
    seen, todo, bad = {start}, [start], set()
    while todo:
        s = todo.pop()
        bad |= violations(s[1])
        for creds, paid in steps(s, mode):
            nxt = (tuple(sorted(creds)), tuple(sorted(paid)))
            if nxt not in seen and len(paid) <= 4:
                seen.add(nxt)
                todo.append(nxt)
    return len(seen), sorted(bad)


if __name__ == "__main__":
    for mode, expect in (("ringfence", []), ("naive", ["PaidOnlyApproved"]), ("no_revoke", ["NoDoublePay"])):
        n, bad = check(mode)
        ok = all(e in bad for e in expect) and (bad == [] if not expect else True)
        print(f"{mode:<10} {n:>7} states  violates {bad or 'nothing'}  {'as expected' if ok else 'UNEXPECTED'}")
