---
title: CROSS-VENDOR-RAIL-STATUS
type: note
permalink: dqverify-repo-20261013/command-center/cross-vendor-rail-status
---

# The cross-vendor review rail ANSWERS — 9 units still demand a cross-vendor review, and 72 of 72 satisfiable units are reviewed

<!-- RAIL-COUNT
basis: committed
blocked_units: 81
rail_blocked: 9
rail_blocked_unfulfilled: 9
rail_blocked_fulfilled: 0
satisfiable_now: 72
reviewed_satisfiable: 72
catalog_units: 2007
rail_state: up
rail_probed: 2026-08-14
derived_by: command-center/p2-next/vendor_satisfiability.py --basis committed
-->

> ## REFUTED 2026-08-14 — the previous title of this page was
> ## *"Cross-vendor review rail is DOWN — and it gates 42 blocked units"* *[superseded 2026-08-20: the 2026-08-20 delivery-surface curation re-derived the split]*
>
> It is kept here rather than deleted, because it is preserved verbatim in the permanent commit
> message of `fd615ce7` and cannot be corrected there. The rail was pronounced down on **one
> transport**: a single failing `mcp__codex__codex` call. That is one route onto the rail, not the
> rail. The page even taught the right lesson — *"before a cross-vendor fan-out, spend one unit
> proving the rail end-to-end"* — and then violated it, because `claude mcp list` was replaced with
> a different single signal instead of a second independent one.

**Rail re-probed 2026-08-14 ~03:02–03:05Z on two mechanically independent transports, with a
control. Counts re-derived from the COMMITTED tree.** The block above is not a summary of this
page — it is the page's contract with CI. `rail_count_gate.py` recomputes every field on each push
and pull request and fails when this document, or
`command-center/p2-next/VENDOR-SATISFIABILITY.json`, disagrees with a fresh derivation.

**The block now also declares the rail VERDICT (`rail_state`, `rail_probed`), and C6 holds every
page that cites this one to that single declaration.** Round 4 measured why it had to: round 3
retracted "the rail is DOWN" *here* and left `command-center/E2E-WAVE-STATUS.md:124` asserting it
— a page this gate already scanned — and the gate stayed green for a whole round, because the unit
count in that sentence (42) was still correct and C2 only reads numbers. A citing-doc check that
returns SUCCESS whether or not the two pages contradict each other is a control that looks the
same under both hypotheses. **C6 proves CONSISTENCY, never TRUTH: this gate calls nothing, so its
silence means the corpus stopped contradicting itself — not that the rail answers.** Only the
probe below, with its control, says anything about the rail itself.
Receipts: `command-center/p2-next/K1-PREMISE-SCAN.json`, `command-center/p2-next/K2-REDPROOF.json`.

```
python command-center/p2-next/rail_count_gate.py --self-test   # prove the gate can fail
python command-center/p2-next/rail_count_gate.py               # then trust its silence
```

## The rail answers. Two transports, and a control that proves the probe can see failure.

| transport | result |
|---|---|
| `codex exec --ignore-user-config --sandbox read-only -o <f> -` | **exit 0**, 7.9 s, output file 22 B, body is the exact nonce the prompt demanded, session `019ffe3a-2a43-7dd2-a36d-d836364b77dc`, 25,474 tokens |
| `mcp__codex__codex` (sandbox read-only, approval never) | **success**, `threadId 019ffe3a-0ba7-7812-a7e6-5e9bcba4c25a`, returned the exact nonce |
| **CONTROL** — the same CLI call with `CODEX_HOME` pointed at an EMPTY directory | **exit 1**, `401 Unauthorized: Missing bearer or basic authentication` |

The CLI leg satisfies the full AND-gate `rules/common/cross-vendor-dispatch.md` §2 requires, not an
exit code alone: exit 0 **AND** the `-o` file exists **AND** is non-empty **AND** validates — it
carries a nonce generated for that run, so a truncated or empty generation cannot pass.

**The control is what makes the green informative.** With no credential reachable the same call
fails 401, so the probe demonstrably *can* see an auth failure. Its success on the live path is a
reading, not a silence. No credential was written, rotated, read for value, or printed; the control
only redirects one subprocess's home at an empty temp directory. `codex login` was NOT attempted.

Receipt: `command-center/p2-next/J1-RAIL-PROBE.json`.

### The first run of that probe was a detector failure that would have confirmed this page

Passing the bare name `codex` to `subprocess` returned
`[WinError 2] The system cannot find the file specified` for **both** the live call and the
control, because `codex` on PATH is `codex.ps1` — a PowerShell shim `CreateProcess` cannot launch.
A live leg that "fails" is exactly what this page used to assert, and the run was one step from
being reported as agreement with it. The probe's `control_discriminates` assertion refused: the
control failed too, so the instrument was measuring nothing. Same defect class as `which` in Git
Bash missing a `.cmd` shim.

### The refutation was already inside this program's own committed artifact, unread

`command-center/p2-next/_AUDIT-BLOCKED-POP.json`, written on 2026-08-11/12, verbatim:

> the `mcp__codex__codex` rail failed with 'agent identity registration failed'; **the codex CLI on
> the same credentials succeeded, so the MCP failure was a transport fault and not an auth
> verdict.**

and, on a different unit:

> STRIKE 2 — `codex exec --ignore-user-config --sandbox read-only` … **the model AUTHENTICATED and
> ran (25,899 tokens), so the openai-auth-401 blocker ADV-0006 recorded is GONE** and has been
> REPLACED by a different one — the host sandbox policy DECLINED every read-only filesystem probe.

So a correct reading was available on disk before this page was written, and before the round that
priced it. The dominant failure here was recall, not detection.

## What unblocks the queue — the correction that matters for pricing

The previous version of this page named `codex login` as the owner action that unblocks the rail.
**That is not established.** Auth is not the measured blocker on either transport today, and on the
one occasion the CLI leg was driven to a real review it authenticated and was then stopped by the
**host sandbox policy** rejecting read-only filesystem probes — a different failure with a
different fix.

`codex login` remains an owner-only action under AGENTS.md §9 and no agent has attempted it. But it
should no longer be priced as the lever: **there is currently no measured auth blocker to clear.**
The residual work is dispatch capacity and the host policy, not a credential.

NOT-CHECKED, inline: whether a full review dispatch across the remaining queue succeeds end to end
under the current host sandbox policy. What was measured is that the transport authenticates and
returns a demanded token. The settling experiment is to dispatch one real review unit and require
the §2 AND-gate plus a non-trivial verdict.

## Demand is not the same as unmet demand — 0 of 9 are already served

`vendor_satisfiability.py` classifies each blocked receipt by the reviewer vendor it **demands**, and
`split_review_gate.py` independently reproduces that split from different fields. That is the right
input for keeping the two populations apart, so it is unchanged.

On the current committed basis, the rail-blocked population is **9** and `rail_blocked_fulfilled` is
**0**: none of those receipts currently carry an executed, independent, cross-vendor PASS.

So the queue is **9 units** (the `rail_blocked_unfulfilled` field).

The predicate is deliberately strict, because the dangerous direction is overstating fulfilment. It
requires `verdict == PASS` **and** `independent is true` **and** a `reviewer_id` **field** naming a
vendor different from the producer. ADV-0006 is the case that proves it discriminates: its
`reviewer_id` reads `codex-cli-0.145.0 (openai) -- DISPATCH BLOCKED` while its verdict is
`NOT-REVIEWED`. A receipt that *names* a Codex reviewer did not *get* one.

**Detector control, discriminating:** the same reader returns 3 cross-vendor passes among the 42
rail-blocked and **0** among the 10 satisfiable — while a counter that merely detected "has a
reviewer" returns 38 and 10 on the same rows. The two counters separate, so what is being measured
is cross-vendor fulfilment and not reviewer presence. Receipt:
`command-center/p2-next/J2-FULFILLED-CENSUS.json`.

## The number, and why it is not the number this page used to carry

The first version of this page said **43 of 47** BLOCKED receipts. *[superseded 2026-08-13]*
It summed TAG OCCURRENCES from `blocker_census.py` and printed the total beside a receipt count,
so a receipt carrying three review tags contributed three. That counts the document instead of
the field.

| published | where | what it really counted |
|---|---|---|
| 43 of 47 units *[superseded]* | this page, first version | tag occurrences, not units |
| 41 of 51 units *[worktree-observed 2026-08-13]* | `VENDOR-SATISFIABILITY.json`, round 1 | a **worktree** read, which silently absorbed a sibling lane's uncommitted edit to ADV-0041 |
| 47 of 51 units *[superseded]* | re-running the producer, round 1 | a resolver bug: this lane's own receipt edits removed the word "Claude" from `failure.blocked_on`, and an ungated rule inverted six same-vendor requirements into cross-vendor demands |
| 42 of 52 units *[superseded 2026-08-20]* | here, committed basis, pre-curation | units, once each, from HEAD blobs — what receipts DEMANDED before the 2026-08-20 delivery-surface curation |
| 39 of 52 units *[superseded 2026-08-20]* | here, committed basis, pre-curation | the same population minus those already reviewed |
| **9 of 81 units** | here, committed basis | units, once each, from HEAD blobs — what receipts DEMAND after the 2026-08-20 curation returned 38 contract-unsupported SUCCESS claims to BLOCKED |
| **9 of 81 units** | **here, committed basis** | **the cross-vendor population minus those already served — what is still OWED to the rail; the satisfiable population is 72, of which 72 are reviewed** |

Two mechanically independent instruments agree on the demand split, which is the only reason it is
stated without a hedge: `vendor_satisfiability.py` resolves a seven-rule vendor ladder per receipt
and returns 42 rail-blocked / 10 satisfiable; `split_review_gate.py` classifies from receipt
*classification tags* plus the catalog `reviewer_requirement` and returns 42 CROSS_VENDOR /
10 ANY_INDEP / 0 NO_REVIEW_GATE. Different fields, different code, same answer.

On the authoring box the dirty tree gave 41 of 51 units. *[worktree-observed 2026-08-13]*
The single difference is ADV-0041: BLOCKED in every commit, SUCCESS only in an uncommitted sibling
edit. That figure is a point-in-time reading of one machine's dirt — it is not re-derivable
anywhere else, which is exactly why the number an owner acts on is the committed one and why CI
checks it there.

## "Connected" is not "works" — and one failing call is not "down"

| probe | result |
|---|---|
| `codex --version` | `codex-cli 0.145.0` |
| `Get-Command codex` | `…\npm\codex.ps1` — a SHIM, not a launchable binary; `codex.cmd` is the one `subprocess` can start |
| `claude mcp list` | `codex: codex mcp-server - ✔ Connected` |
| an actual `mcp__codex__codex` call, 2026-08-12 | **FAILED**: `agent identity registration failed …/agent/register` *[superseded 2026-08-14]* |
| the same call, 2026-08-14 | **succeeds**, returns the demanded nonce |

The health check proves the server *starts*; it does not exercise OpenAI auth. That much stands.
The lesson the earlier version drew from it does not: a single failing call was then treated as
proof of the negative, which is the same single-signal trap one step further along. An intermittent
transport fault and a dead rail look identical through one probe.

Both directions now have the same requirement: **two mechanically independent transports, and a
control that fires in the known-broken state.**

## What the rail is worth — and the ceiling above it

Restoring dispatch capacity is what makes the remaining units reviewable. It is **not** what makes
them DELIVERED. `platform/lib/receipt_schema_gate.py` condition 11 hard-rejects `state=SUCCESS`
while `manifest_registration.registered` is false, and nothing in production sets that flag — the
only writers are test fixtures. So a unit can pass a perfect cross-vendor review and still not
ship. That is escalated separately, with the measurements, in
[`p2-next/OWNER-DECISION-condition-11.md`](p2-next/OWNER-DECISION-condition-11.md).

This is now the *whole* owner decision, and it got simpler: with no measured auth blocker, the
credential write that was previously priced as the unlock is not on the critical path. Condition 11
is. The three units that already hold a cross-vendor PASS are the proof — they cleared the review
gate and still cannot reach DELIVERED.

## What was already done without the rail

10 of the 52 blocked units demanded only an *independent* reviewer *[superseded 2026-08-20: the delivery-surface curation re-derived the split]* — all
10 were reviewed by a fresh-context reviewer that did not build them, with `reviewer.verdict=PASS`
and `independent=true`. They are AUD-0006, AUD-0020, AUD-0021, AUD-0030, AUD-0041, AUD-0051,
CC-0002, IMP-0440, TST-0334, TST-0350. After the 2026-08-20 curation the satisfiable population is
72 of 81 blocked units, 72 of them reviewed — that is the `reviewed_satisfiable` field in the
block at the top, and CI re-checks it. The gap between the two is NEWLY REACHABLE review work the
C5 content floor holds open until each unit carries a substantive independent PASS.

No same-vendor review was substituted anywhere a receipt demands cross-vendor. That substitution
would satisfy the gate's letter and defeat its purpose, and the split above exists precisely to
keep the two populations apart. An independent auditor re-derived the split from the **pre-edit**
blobs — before the ten receipts were touched — and got the same ten ids.

## Residual — still open

1. **The rail verdict was wrong for two days and no gate could have caught it.**
   `rail_count_gate.py` makes no network or subprocess call to codex; it checks that a published
   number equals a fresh derivation from receipts, and returns the identical SUCCESS whether the
   rail is up or down. That is a control that looks the same under both hypotheses. It is not a
   defect in the gate — arithmetic is what it was built to check — but "gate-enforced" must never
   be read as evidence for the rail claim. **UNVERIFIED whether a liveness probe belongs in CI at
   all**: it would make a hermetic gate depend on a live third-party endpoint, which
   `rules/common/ci-hygiene.md` §2 forbids in the fast suite. Settling experiment: a separate
   scheduled job with a hard timeout, never the per-PR gate.
2. **UNVERIFIED [uncertain, 20-55%]:** whether the MCP transport was genuinely failing on 08-12 and
   recovered, or was intermittent throughout. Settling experiment: correlate `~/.codex` session
   logs against the earlier probe timestamps. It does not change the verdict either way — the CLI
   leg was recorded as working in this program's own committed artifact on 08-11.
3. **UNVERIFIED [uncertain, 20-55%]:** whether the 72 would PASS a Codex review. What is measured
   is what receipts DEMAND and which have already been SERVED, never what a review would conclude.
4. **The host sandbox policy blocked a real review dispatch once**, after auth succeeded. Not
   re-measured this round. That is the concrete next blocker to price, not the credential.
5. **Known gap in the gate:** it enforces the counts, the review status, and a reviewer-notes
   content floor; the resolvable-evidence-anchor half stays ADVISORY because none of the reviewed
   receipts carry a resolving anchor and enforcing it would red CI on every one of them.
6. **NOT-CHECKED:** full CI. A Windows-local green is not CI green; the suite has roughly 25 steps
   and they were not all run locally.