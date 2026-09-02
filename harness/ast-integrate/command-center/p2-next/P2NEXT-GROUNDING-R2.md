# P2NEXT grounding round 2 — the lane's DoD is already delivered; here is what is actually left

STATUS: COMPLETE. Every claim below was EXECUTED, not read. Commands and real output in §6.

COVERAGE: §1-§6 measured. §7 lists what is NOT done, inline, with a settling experiment each.

## 0. Headline — do not rebuild this lane

The P2NEXT DoD ("split the 48 · review the satisfiable subset · count the remainder exactly")
was **delivered by committed work before this round started**, and is wired into CI. My job was to
stop a build lane re-deriving it. It would have re-derived it, because **the spawn brief is stale
on both of its numbers**.

| the brief says | committed truth | why the brief is wrong |
|---|---|---|
| "48 units are self-declared BLOCKED" | **52** | 48 was round-1 framing; the population was never 48 in any commit I can reach |
| "43 of 47 name an INDEPENDENT CROSS-VENDOR review gate" | **42 of 52** | 43/47 summed *tag occurrences*, so a receipt with three review tags counted three times — it counts the document, not the field |

Both wrong figures are already marked `[superseded]` in `command-center/CROSS-VENDOR-RAIL-STATUS.md`
with the table showing what each actually measured. The brief inherited the pre-correction numbers.

## 1. The split, re-derived by a THIRD independent instrument

I did not trust the two shipped instruments agreeing — they could share an input. I wrote
`_g2_independent.py`, which imports neither, reads committed blobs itself, discovers the population
itself, and classifies with its own predicate.

```
BLOCKED/FAILED population = 52
MY  VERDICT: {'RAIL_BLOCKED': 42, 'SATISFIABLE_NOW': 10}
SHIPPED VERDICT: {'RAIL_BLOCKED': 42, 'SATISFIABLE_NOW': 10}
only in MY population : []      only in SHIPPED: []      per-unit DISAGREEMENTS: 0
```

Zero population difference, zero per-unit disagreement. A fourth mechanism already in the tree
(`_a3_verbatim.py` Part B — a git tree walk that never consults the catalog) independently finds
the same 52 distinct unit ids, with **0 BLOCKED unit ids absent from the catalog**.

**Stability:** HEAD moved under me mid-run (`27da3215` → `e525e063`, a sibling lane committing to
the shared tree). I re-ran everything at the new HEAD: 52 / 42 / 10, unchanged, gate still green.

### The split is a real cross-vendor demand, not a vendor MENTION

The use-vs-mention trap is the obvious way this number goes wrong, and it is already controlled
(`_a3_verbatim.py` Part C):

```
rail-blocked total                       : 42
  cross clause in catalog requirement    : 41
  cross clause in receipt blocked_on     : 20
  in EITHER operative field              : 42
  in NEITHER (vendor-name inference only): 0
```

Every one of the 42 carries an explicit cross-vendor clause in an operative field. **None** is
rail-blocked merely because a vendor name appears somewhere in its text.

### I reproduced the exact failure mode this lane exists to guard against

My first derivation returned **38 / 14**, disagreeing on ADV-0008, ADV-0022, ADV-0028, ADV-0035.
The shipped instrument was right and I was wrong. I had regexed `json.dumps(produced_by)` — which
contains role prose like `"role": "... (catalog assigns openai/gpt-5-codex; executed by
anthropic/opus)"` — so the word `openai` in a *mention* flipped four anthropic-produced units.
Reading the `vendor` FIELD instead gives 42 / 10 and zero disagreements. Counting the document
instead of the field is the same defect that produced the brief's "43 of 47".

My first shape assumption was also wrong: I read `cat["units"]`, which does not exist, so the probe
silently measured the catalog's 10 top-level keys and reported "10 units". The real collection is
`work_units` (2007). Both are now size-asserted so a wrong collection fails closed.

## 2. The satisfiable subset — done, with real content

All **10** (AUD-0006, AUD-0020, AUD-0021, AUD-0030, AUD-0041, AUD-0051, CC-0002, IMP-0440,
TST-0334, TST-0350) carry `reviewer.verdict=PASS`, `independent=true`, `fresh_context=true`, and
substantive notes (1,027–2,092 chars; none empty). No same-vendor review was substituted where a
receipt demands cross-vendor — the two populations are kept apart by construction, and an auditor
re-derived the same ten ids from the **pre-edit** blobs.

## 3. The rail-blocked remainder, priced exactly

**42 units** need `codex login` (owner-only credential write, AGENTS.md §9 — not attempted).

But `codex login` **does not make them DELIVERED**. All 10 already-reviewed units carry
`blocked_on_head: "completion condition 11: manifest_registration.registered is false"`. Condition
11 (`platform/lib/receipt_schema_gate.py:515-527`) hard-rejects `state=SUCCESS` while
`manifest_registration.registered` is false, and **nothing in production sets that flag** — the
only writers are test fixtures. A unit can pass a perfect cross-vendor review and still not ship.

**Price the two decisions together.** `codex login` buys review capacity for 42; condition 11
decides whether anything in that queue can reach DELIVERED. Condition 11 is a genuine contract
collision (`OWNER-DECISION-condition-11.md`), not a missing function — the manifest is a *complete*
producer for a *different* contract, and 80 receipts already point at it.

## 4. The one gap worth building — and I PROVED it rather than repeating it

`CROSS-VENDOR-RAIL-STATUS.md` residual #4 claims "a reviewer PASS with empty reasoning would
satisfy C5". That was an unexecuted assertion. `_g3_c5_content_probe.py` executes it, monkeypatching
only the blob reader so no receipt on disk or in git is touched, in three states:

```
[A control: receipts unmutated]                    rows=10  reviewed=10  problems=0
[B mutation: every reviewer note emptied]          rows=10  reviewed=10  problems=0
[C control2: reviewer verdict flipped to FAIL]     rows=10  reviewed=0   problems=10
```

Control C proves the probe **can** see failure (a silent probe in both states measures nothing).
Control A proves the baseline. **CONFIRMED: C5 is verdict-shaped only** — `rail_count_gate.py:324-327`
reads exactly `verdict == "PASS"` and `independent is True`, nothing else. Emptying every reviewer
note across all ten units changes not one number.

So the review gate currently proves a review *happened*, not that it *said anything*.

## 5. Prior art — the content floor is 80% built already, and it has a live hole

Do not write a new gate. `.agents/skills/claim-verify-gate/scripts/claim_gate.py` (488 lines)
already implements the needed shape: a CONFIRMED/REFUTED/UNVERIFIED vocabulary, `source_probe` vs
`verify_probe` fingerprint comparison (same-probe-rerun detection), a required `file:line`/URL
evidence anchor for CONFIRMED, and a rewrite requirement for REFUTED.

`rules/common/single-signal-verification.md` documents a hole in it. I executed that too
(`_g4_claimgate_hole.py`), again in both states:

```
A full claim passes                 : True (exit 0)
B same-probe rerun is CAUGHT        : True (exit 1)  <- detector is live
C missing source_probe still passes : True (exit 0)
```

**CONFIRMED: the hole is live.** A CONFIRMED verdict with **no `source_probe` at all** returns
`violations: []`, `ok: true`, exit 0 — the gate certifies corroboration for a claim that declares no
producing measurement. Control B proves the detector is not simply inert. Reuse of `claim_gate` as
the C5 floor must close this first or the floor inherits the defect.

Also already in the tree, do not rebuild: `platform/lib/workflows/test_two_signal_corroboration_gate.py`
(230 lines, mutation-tested per check), and the `agent-as-judge` / `rubric-verifier` /
`mutation-check` / `two-tier-verify` skills.

### External SOTA agrees the floor should be DETERMINISTIC, not a judge

2026 work converges on fixed criteria + typed evidence grounding + extractive quote verification +
calibration, and reports explicitly that criteria predicting human preference in conversation **do
not transfer cleanly to code review**. Reliability-without-validity results show judge agreement
metrics can look healthy while validity does not hold. That argues for the structural floor
`claim_gate` already implements — notes length, a resolvable evidence anchor, a named falsification
method — and against adding an LLM judge to the blocking path. The repo's own `agent-as-judge`
skill already self-declares advisory/shadow, never blocking, which is consistent.

- https://arxiv.org/abs/2601.08654 — Rubrics to Reliable Scores: evidence-grounded LLM judges (fetched via search result summary, not full text)
- https://arxiv.org/html/2606.19544v1 — Reliability without Validity (fetched via search result summary, not full text)
- https://arxiv.org/pdf/2603.05399 — Judge Reliability Harness (fetched via search result summary, not full text)

## 6. Commands, re-runnable

```
python command-center/p2-next/rail_count_gate.py --self-test   # 23 cases, both states -> PASS
python command-center/p2-next/rail_count_gate.py               # 52/42/10/10, 2007 catalog, 449 READY
python command-center/p2-next/vendor_satisfiability.py         # 42 RAIL_BLOCKED / 10 SATISFIABLE
python command-center/p2-next/split_review_gate.py             # 42 CROSS_VENDOR / 10 ANY_INDEP
python command-center/p2-next/_g2_independent.py               # third instrument: 52/42/10, 0 disagreements
python command-center/p2-next/_g3_c5_content_probe.py          # C5 content gap CONFIRMED
python command-center/p2-next/_g4_claimgate_hole.py            # claim_gate source_probe hole CONFIRMED
```

CI wiring exists: `.github/workflows/p2next-rail-count.yml` (push + PR + dispatch, `fetch-depth: 0`),
running the self-test first, then the gate, then both producers in CHECK mode.

## 7. What is NOT done — inline, with the settling experiment

1. **NOT-CHECKED: full CI.** I ran ruff check + format on my three new probes (all pass, and I
   reformatted them to match the convention the committed lane probes already satisfy), the gate
   self-test, the gate, and both producers. The suite has ~25 steps; I did not run them all. A
   Windows-local green is not a CI green. Settling experiment: push and read the run.
2. **UNVERIFIED [uncertain, 20-55%]: whether the 42 would PASS a Codex review.** What is measured is
   what the receipts DEMAND, not what a review would conclude — and condition 11 bounds the answer
   regardless of vendor. Settling experiment: run the open-defect and completion-sentinel checks
   across the 42, then re-read condition 11.
3. **NOT-CHECKED: whether `codex login` actually clears `agent/register`.** Owner-only credential
   write; no agent attempted it and `~/.codex/auth.json` was never read for value. Settling
   experiment: the command, then one real `mcp__codex__codex` call.
4. **UNVERIFIED [likely, 55-80%]: that a notes-length floor is the right C5 fix.** I proved the gap
   exists; I did not prove a length floor closes it without false-positives on a terse-but-valid
   review. Settling experiment: apply the floor to the 10 existing receipts and check none regress.
5. **Scope honesty:** I wrote no production code, per the grounding-lane instruction. The three new
   files are probes, matching the `_`-prefixed lane convention. They are uncommitted — a sibling
   lane owns the shared tree and I did not commit into it.
6. **Detector caveat I hit twice:** two of my own probes were wrong before they were right (wrong
   collection; mention-vs-field). Both were caught by asserting shape and by running controls, not
   by re-reading the code. Treat any single number here as provisional until its control is seen.
7. **Expected-red, do not "fix" it:** `rail_count_gate.py --basis worktree` currently FAILS with 14
   problems, reporting 41/51. That is correct behaviour, not a regression. It compares the
   *committed* document against a *worktree* derivation, and the worktree still carries a sibling
   lane's uncommitted edit flipping **ADV-0041** from BLOCKED to SUCCESS — re-measured this round,
   still the sole divergence (`only in committed: ['ADV-0041']`, `only in worktree: []`). The
   committed basis is the default and the one CI runs, and it is green at 52/42/10. Anyone who
   "fixes" the worktree red will be chasing one machine's dirt.
