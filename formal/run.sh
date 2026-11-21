#!/usr/bin/env bash
# Runs every model check and fails if any result is not the expected one.
# Needs java on PATH (or JAVA set) and TLA_JAR set to the path of tla2tools.jar.
# SAVE=1 also writes the two naive counterexamples to counterexample-*.txt.
set -u
cd "$(dirname "$0")"
JAVA=${JAVA:-java}
: "${TLA_JAR:?set TLA_JAR to the path of tla2tools.jar}"
meta=$(mktemp -d)  # TLC writes its state files here, not into the repo
fail=0

check() { # config name, then "ok" or the invariant that must be violated
  out=$("$JAVA" -XX:+UseParallelGC -cp "$TLA_JAR" tlc2.TLC -workers auto -metadir "$meta" \
        -config "$1.cfg" RingfenceRelease.tla 2>&1 | grep -v '^Parsing\|^Semantic\|^Starting\|^Computing\|^Computed\|^Progress')
  if [ "$2" = ok ]; then
    echo "$out" | grep -q "No error has been found" && r=PASS || r=FAIL
  else
    echo "$out" | grep -q "Invariant $2 is violated" && r=PASS || r=FAIL
  fi
  [ "$r" = PASS ] || fail=1
  echo "$r  $1: $(echo "$out" | grep -E '^[0-9]+ states generated')"
  if [ -n "${SAVE:-}" ]; then case "$1" in naive_*) echo "$out" > "counterexample-$1.txt";; esac; fi
}

check ringfence ok
check naive_f1 PaidOnlyApproved
check naive_f4 NoDoublePay
check reach_AllPaid NeverAllPaid
check reach_HeldAfterPay NeverHeldAfterPay
check reach_Returned NeverReturned
exit $fail
