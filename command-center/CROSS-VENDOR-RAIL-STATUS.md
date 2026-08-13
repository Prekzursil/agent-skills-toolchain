# Cross-vendor review rail is DOWN — and it gates 42 blocked units

<!-- RAIL-COUNT
basis: committed
blocked_units: 52
rail_blocked: 42
satisfiable_now: 10
reviewed_satisfiable: 10
catalog_units: 2007
derived_by: command-center/p2-next/vendor_satisfiability.py --basis committed
gated_by: command-center/p2-next/rail_count_gate.py
-->

**Rail probed 2026-08-12 ~10:45. Counts re-derived 2026-08-13 from the COMMITTED tree.**
The block above is not a summary of this page — it is the page's contract with CI.
`rail_count_gate.py` recomputes every field on each push and pull request and fails when this
document, or `command-center/p2-next/VENDOR-SATISFIABILITY.json`, disagrees with a fresh
derivation. Re-derive it yourself in about a second:

```
python command-center/p2-next/rail_count_gate.py --self-test   # prove the gate can fail
python command-center/p2-next/rail_count_gate.py               # then trust its silence
```

## The number, and why it is not the number this page used to carry

The first version of this page said **43 of 47** BLOCKED receipts. *[superseded 2026-08-13]*
It summed TAG OCCURRENCES from `blocker_census.py` and printed the total beside a receipt count,
so a receipt carrying three review tags contributed three. That counts the document instead of
the field.

Every published figure the program produced for this one quantity, and what each was actually
measuring:

| published | where | what it really counted |
|---|---|---|
| 43 of 47 units *[superseded]* | this page, first version | tag occurrences, not units |
| 41 of 51 units *[worktree-observed 2026-08-13]* | `VENDOR-SATISFIABILITY.json`, round 1 | a **worktree** read, which silently absorbed a sibling lane's uncommitted edit to ADV-0041 |
| 47 of 51 units *[superseded]* | re-running the producer, round 1 | a resolver bug: this lane's own receipt edits removed the word "Claude" from `failure.blocked_on`, and an ungated rule inverted six same-vendor requirements into cross-vendor demands |
| **42 of 52 units** | **here, committed basis** | **units, once each, from HEAD blobs** |

Two mechanically independent instruments now agree on the split, which is the only reason it is
stated without a hedge: `vendor_satisfiability.py` resolves a seven-rule vendor ladder per receipt
and returns 42 rail-blocked / 10 satisfiable; `split_review_gate.py` classifies from receipt
*classification tags* plus the catalog `reviewer_requirement` and returns 42 CROSS_VENDOR /
10 ANY_INDEP / 0 NO_REVIEW_GATE. Different fields, different code, same answer.

On the authoring box the dirty tree gave 41 of 51 units. *[worktree-observed 2026-08-13]*
The single difference is ADV-0041: BLOCKED in every commit, SUCCESS only in an uncommitted sibling
edit. That figure is a point-in-time reading of one machine's dirt — it is not re-derivable
anywhere else, which is exactly why the number an owner acts on is the committed one and why CI
checks it there. The gate refuses to accept such a number unless the line carrying it says so, and
it prints how many lines used that escape so a document cannot be quietly marked instead of fixed.

## "Connected" is not "works"

| probe | result |
|---|---|
| `codex --version` | `codex-cli 0.145.0` |
| `Get-Command codex` | `…\npm\codex.ps1` — on PATH in both shell views |
| `claude mcp list` | `codex: codex mcp-server - ✔ Connected` (line 37 of 67; 55 servers connected) |
| **an actual `mcp__codex__codex` call** | **FAILS**: `agent identity registration failed for https://auth.openai.com/api/accounts/v1/agent/register` |

Three green signals and the rail is still unusable. The health check proves the server *starts*; it
does not exercise OpenAI auth. This is the single-signal trap in its most expensive form — had the
whole gated queue been dispatched instead of probing one unit first, every dispatch would have
failed, likely after burning wall-clock on each.

That is the reusable lesson: before a cross-vendor fan-out, spend one unit proving the rail
end-to-end. `claude mcp list` is not that proof.

## Read-only diagnosis (no credential action taken)

`~/.codex/auth.json` — 215 bytes, modified **2026-08-11 22:15**:

```
top-level keys: ['auth_mode', 'OPENAI_API_KEY']
```

Key *names* only; no value was read, printed, or logged. What this shows:

- There is **no OAuth token object** — no `tokens`, no `id_token`/`access_token`/`refresh_token`, so
  there is no JWT whose `exp` could be checked. The file is API-key mode only.
- The failing endpoint is `accounts/v1/agent/register` — *agent identity* registration, which is a
  ChatGPT-account-session operation, not an API-key operation.

So the most likely cause (**likely, 55-80%**) is that `codex mcp-server` requires the ChatGPT login
session for agent registration and only the API key is configured. The competing explanation
(**uncertain, 20-55%**) is that the key exists but lacks the agent-registration entitlement. Both
are settled by the same one command, which is why no further probes were spent separating them.

UNVERIFIED, inline: nobody established *what* modified `auth.json` at 22:15 on 2026-08-11, roughly
when that session began. It was not that session — no credential file has been written here.
Settling experiment: check the file's prior version if any backup exists, or correlate against the
other session's activity.

## What unblocks it — OWNER ACTION, not an agent's

```
codex login
```

AGENTS.md §9 reserves credential lifecycle to the owner: never remove, rotate, revoke, regenerate,
unset or otherwise modify any API key or token. `codex login` writes credentials, so it is yours.
Read-only diagnosis — presence, size, key names, whether it authenticates — is expected and is what
was done here.

NOT-CHECKED, inline: whether `codex login` actually clears the `agent/register` failure. It is an
owner-only credential write; no agent attempted it and `~/.codex/auth.json` was never read for
value. Settling experiment is the command itself, followed by one real `mcp__codex__codex` call.

Note also, observed while probing and unrelated to the fix: `claude mcp list` prints
*"claude.ai connectors are disabled because ANTHROPIC_API_KEY or another auth source is set and takes
precedence over your claude.ai login"*. Same shape — an env-set API key shadowing a login session.
Reported, not touched.

## What the rail is worth — and the ceiling above it

Restoring the rail is what makes 42 blocked units reviewable. It is **not** what makes them
DELIVERED. `platform/lib/receipt_schema_gate.py` condition 11 hard-rejects `state=SUCCESS` while
`manifest_registration.registered` is false, and nothing in production sets that flag — the only
writers are test fixtures. So a unit can pass a perfect cross-vendor review and still not ship.
That is escalated separately, with the measurements, in
[`p2-next/OWNER-DECISION-condition-11.md`](p2-next/OWNER-DECISION-condition-11.md).

Price the two decisions together. `codex login` buys review capacity for the rail-blocked queue;
condition 11 decides whether anything in that queue can then reach DELIVERED.

## What was already done without the rail

10 of the 52 blocked units demand only an *independent* reviewer, with no vendor constraint in the
receipt, in `failure.blocked_on`, or in the catalog requirement. All 10 have been reviewed by a
fresh-context reviewer that did not build them, and all 10 carry `reviewer.verdict=PASS` with
`independent=true` — that is the `reviewed_satisfiable` field in the block at the top, and CI
re-checks it. They are AUD-0006, AUD-0020, AUD-0021, AUD-0030, AUD-0041, AUD-0051, CC-0002,
IMP-0440, TST-0334, TST-0350.

No same-vendor review was substituted anywhere a receipt demands cross-vendor. That substitution
would satisfy the gate's letter and defeat its purpose, and the split above exists precisely to
keep the two populations apart. An independent auditor re-derived the split from the **pre-edit**
blobs — before the ten receipts were touched — and got the same ten ids.

## Residual — this lane ended CONTESTED, and here is what is still open

1. **REFUTED and now fixed:** the adversarial refuter proved the published verification command did
   not reproduce its own number — running `vendor_satisfiability.py` printed 47 where the artifact
   said 41, overwrote the committed artifact as a side effect, and turned the lane's own verifier
   red. Fix shipped: rule D only inverts when the requirement carries a cross-vendor clause, rule A2
   catches an undirected cross-vendor demand, `--basis committed` is the default, and the script is
   CHECK-only unless `--write`. The refuter also asked that the count be RE-DERIVED rather than read
   back from stored JSON; that is what `rail_count_gate.py` does, and it is why this page is now
   wired into CI instead of merely being correct today.
2. **Corrected here, inline:** the headline moved 43 → 42 and the population 47 → 52. Both earlier
   figures are marked superseded above rather than deleted, because the next reader will otherwise
   re-derive the same wrong number from the same census line.
3. **UNVERIFIED [uncertain, 20-55%]:** whether the 42 would reach DELIVERED after a Codex review.
   What was measured is what the receipts DEMAND, not whether a review would PASS — and condition 11
   bounds that answer regardless of vendor. Settling experiment: run the open-defect and
   completion-sentinel checks across the 42, then re-read condition 11.
4. **Known gap in the gate:** it enforces the counts and the review status; it does not verify the
   *content* of any review. A reviewer PASS with empty reasoning would satisfy C5. Settling
   experiment: extend C5 to assert a reviewer-notes floor and a falsification method per receipt.
5. **NOT-CHECKED:** full CI. The gates touching this change were run (ruff check and format, the
   gate's own self-test, `vendor_satisfiability.py`, `split_review_gate.py`, `charter_check.sh`);
   the suite has roughly 25 steps and they were not all run locally.
