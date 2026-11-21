---------------------------- MODULE RingfenceRelease ----------------------------
(* A model of one payroll run's release protocol, for one employer.

   Propose a batch, a person approves a hash of the exact batch, the release re-reads the live payee
   bank details and holds on a mismatch, then each line is sent. A send can succeed, time out after
   the bank booked it, or fail before it booked. The process can crash. A payment can be returned.
   An attacker can edit any payee's bank details at any moment, and any line amount before release.

   Two switches turn the two fixes off:
     PinnedDetails   = FALSE  the approval binds payee IDs only, and the send names the payee by ID,
                              so the bank pays whatever the payee holds at that moment. FINDINGS F1.
     StableRequestId = FALSE  a retry mints a fresh request ID and never looks the payment up. FINDINGS F4.

   Abstracted away: one run, two payees, no clock (approval expiry is not modelled), no funds check,
   no FX. The gate's 25 refusals are not modelled here; they are unit and property tested.            *)
EXTENDS Naturals, FiniteSets

CONSTANTS Payees, Amounts, Banks, Good, OtherGA, PinnedDetails, StableRequestId, MaxAttempt

ASSUME Good \in Banks /\ OtherGA \in Banks /\ Good # OtherGA
ASSUME PinnedDetails \in BOOLEAN /\ StableRequestId \in BOOLEAN /\ MaxAttempt \in Nat \ {0}

VARIABLES
    runSt,     \* NONE | AWAITING | APPROVED | RELEASING | HELD
    bank,      \* the live bank details per payee, which an attacker can edit
    amt,       \* the line amounts of the batch
    approved,  \* has a person approved
    apprHash,  \* what the approval binds
    apprAmt,   \* the amounts the person saw
    line,      \* READY | INTENT | UNKNOWN | PAID | RETURNED
    rid,       \* the stored request ID (an attempt number) per line
    paid       \* payments the bank booked: [p, rid, bank, amt, ret]

vars == <<runSt, bank, amt, approved, apprHash, apprAmt, line, rid, paid>>

Pin == [p \in Payees |-> Good]  \* the approved bank details, pinned when the payee was registered

\* What the approval hash covers. Pinned: the exact bank details. Naive: the payee IDs only.
Hash(b, a) == [b |-> IF PinnedDetails THEN b ELSE "ids", a |-> a]

Booked(p, r) == \E x \in paid : x.p = p /\ x.rid = r

Init == /\ runSt = "NONE"
        /\ bank = Pin
        /\ amt \in [Payees -> Amounts]
        /\ approved = FALSE
        /\ apprHash = "none"
        /\ apprAmt = [p \in Payees |-> CHOOSE a \in Amounts : TRUE]
        /\ line = [p \in Payees |-> "READY"]
        /\ rid = [p \in Payees |-> 1]
        /\ paid = {}

Propose == /\ runSt = "NONE" /\ runSt' = "AWAITING"
           /\ UNCHANGED <<bank, amt, approved, apprHash, apprAmt, line, rid, paid>>

Approve == /\ runSt = "AWAITING" /\ runSt' = "APPROVED"
           /\ approved' = TRUE /\ apprHash' = Hash(Pin, amt) /\ apprAmt' = amt
           /\ UNCHANGED <<bank, amt, line, rid, paid>>

\* The attacker: write access to a saved payee, at any moment, including mid-release.
EditBank(p, b) == /\ bank' = [bank EXCEPT ![p] = b]
                  /\ UNCHANGED <<runSt, amt, approved, apprHash, apprAmt, line, rid, paid>>

\* A line changed after it was proposed. Lines are frozen once release starts.
EditAmount(p, a) == /\ runSt \in {"AWAITING", "APPROVED"} /\ amt' = [amt EXCEPT ![p] = a]
                    /\ UNCHANGED <<runSt, bank, approved, apprHash, apprAmt, line, rid, paid>>

\* The gate: re-read the live details and amounts, recompute the hash, hold on any difference.
Gate == /\ runSt = "APPROVED"
        /\ runSt' = IF Hash(bank, amt) = apprHash THEN "RELEASING" ELSE "HELD"
        /\ UNCHANGED <<bank, amt, approved, apprHash, apprAmt, line, rid, paid>>

\* INTENT is committed, with its request ID, before the HTTP call.
Intend(p) == /\ runSt = "RELEASING" /\ line[p] = "READY"
             /\ line' = [line EXCEPT ![p] = "INTENT"]
             /\ UNCHANGED <<runSt, bank, amt, approved, apprHash, apprAmt, rid, paid>>

Send(p) ==
    /\ runSt = "RELEASING" /\ approved /\ line[p] = "INTENT"
    /\ LET rec == [p |-> p, rid |-> rid[p], ret |-> FALSE, amt |-> amt[p],
                   bank |-> IF PinnedDetails THEN Pin[p] ELSE bank[p]]  \* inline details, or the payee ID
           booked == IF Booked(p, rid[p]) THEN paid ELSE paid \cup {rec}  \* the bank rejects a repeated ID
       IN \/ paid' = booked /\ line' = [line EXCEPT ![p] = "PAID"]      \* success
          \/ paid' = booked /\ line' = [line EXCEPT ![p] = "UNKNOWN"]   \* booked, the reply was lost
          \/ paid' = paid   /\ line' = [line EXCEPT ![p] = "UNKNOWN"]   \* failed before it booked
    /\ UNCHANGED <<runSt, bank, amt, approved, apprHash, apprAmt, rid>>

\* An unknown outcome. Ringfence looks the payment up by its stored ID and adopts it, or puts the line
\* back to READY with the same ID. The naive retry sends again with a fresh ID and never looks.
Resolve(p) ==
    /\ line[p] = "UNKNOWN"
    /\ \/ StableRequestId /\ Booked(p, rid[p])
          /\ line' = [line EXCEPT ![p] = "PAID"] /\ rid' = rid
       \/ StableRequestId /\ ~Booked(p, rid[p])
          /\ line' = [line EXCEPT ![p] = "READY"] /\ rid' = rid
       \/ ~StableRequestId /\ rid[p] < MaxAttempt
          /\ line' = [line EXCEPT ![p] = "READY"] /\ rid' = [rid EXCEPT ![p] = rid[p] + 1]
    /\ UNCHANGED <<runSt, bank, amt, approved, apprHash, apprAmt, paid>>

\* Restart: the lock is released, sends in flight have unknown outcomes, the ledger keeps the rest.
Crash == /\ runSt' = IF runSt = "RELEASING" THEN "APPROVED" ELSE runSt
         /\ line' = [p \in Payees |-> IF line[p] = "INTENT" THEN "UNKNOWN" ELSE line[p]]
         /\ UNCHANGED <<bank, amt, approved, apprHash, apprAmt, rid, paid>>

\* The payee's bank sends the money back. Paying again needs a new round and a new approval, which
\* this model does not do, so RETURNED is final here.
Return(p) == /\ line[p] = "PAID" /\ Booked(p, rid[p])
             /\ paid' = {IF x.p = p /\ x.rid = rid[p] THEN [x EXCEPT !.ret = TRUE] ELSE x : x \in paid}
             /\ line' = [line EXCEPT ![p] = "RETURNED"]
             /\ UNCHANGED <<runSt, bank, amt, approved, apprHash, apprAmt, rid>>

Next == \/ Propose \/ Approve \/ Gate \/ Crash
        \/ \E p \in Payees : Intend(p) \/ Send(p) \/ Resolve(p) \/ Return(p)
        \/ \E p \in Payees, b \in Banks : EditBank(p, b)
        \/ \E p \in Payees, a \in Amounts : EditAmount(p, a)

Spec == Init /\ [][Next]_vars

\* ---- invariants ------------------------------------------------------------------------------

\* A payee is never paid twice for one round, unless the first payment was returned.
NoDoublePay == \A p \in Payees : Cardinality({x \in paid : x.p = p /\ ~x.ret}) <= 1

\* Every payment goes to the pinned account, for exactly the approved amount.
PaidOnlyApproved == \A x \in paid : x.bank = Pin[x.p] /\ x.amt = apprAmt[x.p]

\* No payment lands in another employer's own account.
NoCrossEmployer == \A x \in paid : x.bank # OtherGA

\* Nothing is booked before a person approves. Here that follows from the guard on Send, so it
\* checks the model, not the code. The code's version is invariant I7 in tests/invariants.py.
NoSendWithoutApproval == paid # {} => approved

\* ---- sanity: TLC must violate these, or the model cannot do what it claims -------------------
NeverAllPaid == ~(\A p \in Payees : line[p] = "PAID")
NeverHeldAfterPay == ~(runSt = "HELD" /\ paid # {})
NeverReturned == ~(\E p \in Payees : line[p] = "RETURNED")
=============================================================================
