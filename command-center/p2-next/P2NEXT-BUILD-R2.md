---
title: P2NEXT-BUILD-R2
type: note
permalink: dqverify-repo-20261013/command-center/p2-next/p2-next-build-r2
---

# P2NEXT — BUILD round 2: fix what the auditor confirmed, and the same defect where it wasn't looked for

**Measured 2026-08-13** against `ast-integrate` (worktree of `agent-skills-toolchain`, `main`).

COVERAGE: §1-§6 MEASURED and executed. Every number below came from a command in §6 run in this
session. §0 names one thing I could NOT recover and what I did instead.

---

## 0. What I was given, and the hole in it

The re-entry brief carried the auditor's verdict (**PARTIAL**) and its **defect 1** in full, plus
the DoD-3 line "*the stated verification METHOD fails re-execution, and it is a worktree number.
See real defects 1 and 3*". The auditor's own confidence block refers to "findings 1-6".
**Defects 2, 4, 5 and 6 were TRUNCATED out of my brief and the audit wrote no report file to disk**
(`command-center/p2-next/` holds its nine `_audit*.py` probes and `_AUDIT-BLOCKED-POP.json`, no
prose). So I did not guess at them. I re-ran the auditor's own probes, re-derived the defects they
were pointed at, and then went looking for the same defect *class* in the places nobody had checked.
That found one more real defect (§3) that is not in any list I was given.

**If a later reader has the full audit text, findings 2/4/5/6 must still be checked against this
document. I am not claiming to have closed them — I am claiming I could not read them.**

---

## 1. DEFECT 1 (CONFIRMED, MEDIUM) — the published command did not reproduce its own number

**What the auditor measured:** `python command-center/p2-next/vendor_satisfiability.py` printed
**47 RAIL_BLOCKED / 4 SATISFIABLE** where the artifact it silently overwrote said 41/10, and
`_b20_final_verify.py` then exited 1 with `rail-blocked count moved to 47`.

**Root cause, re-derived here and now pinned by a test.** Rule D read: *"the requirement names the
producer's own vendor, therefore it is self-defeating, therefore it means the OTHER vendor."* That
premise is only true when the requirement also carries a cross-vendor clause. Round 1's own edits
rewrote `failure.blocked_on` on the six AUD receipts (the review was done, so the field was updated
to name the remaining blocker). That removed the word "Claude", rule A stopped firing, and all six
fell through to rule D — which inverted *"one fresh-context Claude reviewer"* into a demand for an
`openai` reviewer. **A classifier whose answer depends on its own author's later edits is not a
measurement.**

**Fix (the auditor's scoped fix (a)):** rule D only inverts when the requirement carries a
cross-vendor clause; otherwise **D2** — naming the producer's vendor with no such clause means
same-vendor is *what it asks for*, not a substitution for something stricter.

**The fix, applied naively, would have been WORSE than the bug — in the dangerous direction.**
My first draft gated rule D and nothing else. It moved **seven** units, not six: `BLD-0023` too. Its
requirement says "An Anthropic-vendor reviewer…", so D2 called it SATISFIABLE. But its own
`blocked_on` reads *"…plus one **cross-vendor refuter** to re-derive the 1-of-2007 and zero-CI
findings from the raw tree rather than from this receipt"* — a cross-vendor demand that names no
vendor, so `named_vendor()` returns None and rule A never fires. I would have dispatched a
same-vendor reviewer at a unit whose operative field forbids one: **the exact letter-vs-purpose
failure this lane exists to avoid.** Caught by reading the receipt before accepting a verdict move.

**Second fix: rule A2** — an *undirected* cross-vendor clause in `blocked_on` resolves to the other
vendor, ahead of anything the catalog says. 7 units are now decided by A2.

**Third fix (the auditor's scoped fix (b)):** `_b20_final_verify.py` **RE-DERIVES** the split by
importing the resolver and walking the committed receipts. It used to read the count out of
`VENDOR-SATISFIABILITY.json` — the producer's own artifact — so re-running the producer moved the
number the verifier then reported as verified.

**Fourth fix: the write hazard.** Both scripts now default to **CHECK-only** and exit 1 on drift;
`--write` regenerates. An auditor re-running a published command can no longer corrupt the
deliverable.

**Regression test, both states** (`_r2_control_stability.py`):

| state | STABILITY check | satisfiable ids |
|---|---|---|
| shipped ladder | 52 units classified at BOTH `899ff779^` and HEAD, **0 moved** | the same 10 |
| v2 ladder monkeypatched back | **6 moved**, all AUD, each `A` → `D:unconditional-invert` | 4 |

The instrument fires on the known-broken state and is silent on the fixed one, and it reports a
**count of the thing being compared** (52 units classified at both revisions), failing closed below
40 so a shape change is loud instead of reporting parity.

## 2. DEFECT 3 (CONFIRMED) — 41 was a worktree number; the committed tree says 42

`ADV-0041` is `state=BLOCKED` in **every commit since `fb2f477f`**, with
`blocked_on = "cross-vendor Codex refuter + downstream consumer execution"`. In the shared
**worktree** a sibling lane has an **uncommitted** edit making it `state=SUCCESS`,
`reviewer.vendor=openai`, `verdict=PASS`. Round 1 walked the worktree and therefore never saw it.

| basis | blocked | rail-blocked | satisfiable |
|---|---|---|---|
| **committed (HEAD)** | **52** | **42** | 10 |
| worktree | 51 | 41 | 10 |

Both scripts now default to `--basis committed` and print the other number beside it.

**Two errors cancelled, which is why the headline looked stable.** Round 1's 41 = the true rail set
**minus `ADV-0041`** (worktree basis) **plus `BLD-0023`** (which the v2 rule-D bug happened to
classify correctly for the wrong reason). Fixing both moves the composition while leaving the
arithmetic at 41 on the worktree — **41 was right by coincidence, not by derivation.** That is worth
more than the number: an unstable derivation can produce a correct figure and teach you nothing.

**UNRESOLVED, and it is not mine to resolve [uncertain, 20-55%].** The sibling's uncommitted
`ADV-0041` asserts an **`openai` reviewer PASS** while this lane's entire premise is that the
`openai` rail is DOWN. Both cannot be true. I did not touch the file. *Settling experiment:* ask the
owning lane for that review's transcript or `mcp__codex__codex` call id; if it is real, the rail
diagnosis needs revisiting and the price is 41, not 42.

## 3. NOT IN ANY FINDING I WAS GIVEN — the same defect in the lane's other command

The auditor confirmed non-idempotence in `vendor_satisfiability.py`. Nobody checked the *other*
script in the same reproduce block. I did (`_r2_probe_splitgate.py`), by hashing the artifact,
running the command, and hashing again:

```
artifact before run : a09ae9758373 (== HEAD)
run rc=0            : "wrote command-center\p2-next\REVIEW-GATE-SPLIT.json"
artifact after run  : 5ec36ee3ff45  DRIFTED=True
RESTORED            : a09ae9758373  match=True
```

`split_review_gate.py` had **both** halves of the defect — worktree basis and unconditional
overwrite. Same fix applied. Restoration was verified by content hash, not `git status`, which
reports a stale `" M"` on this contended tree.

**And fixing it surfaced a third instrument disagreement.** With `--basis committed` the two lane
scripts returned **41 CROSS_VENDOR** and **42 RAIL_BLOCKED** — my own outputs contradicting each
other, which is a detector failure until resolved from raw text, never by preferring the newer
script. The single differing unit was `BLD-0023` again: `split_review_gate.classify()` read receipt
tags, the catalog requirement and `failure.reason`, but **never `blocked_on`**. Adding it as a
fourth source (the stricter source governs, as that script's own docstring already required) makes
both instruments return 42/10. Its selftest grew two BLD-0023-shaped cases, in both directions: a
cross-vendor clause present **only** in `blocked_on` must classify CROSS_VENDOR, and the same shape
*without* the clause must stay ANY_INDEP — otherwise the new source would just be a blanket upgrade
that proves nothing.

## 4. REFUTED SENTENCE — "137 tag occurrences"

Round 1's residual 6 said `blocker_census.py:185-190` "prints a tag-sum (137 occurrences) directly
under a unit count (51)". Measured:

- The tool prints `tags naming an independent/cross-vendor REVIEW gate: **33**` at the **end** of
  its output, after the histogram — not "directly under" the receipt count at the top.
- **137 is emitted by no instrument in this repo.** It came from `P2NEXT-GROUNDING.md:43`.
- The occurrence sum is a **family** of numbers: **114** (`failure.classification` + top level,
  deduped, committed/52), **113** (auditor, worktree/51 — the difference is `ADV-0041`'s one tag),
  **132** (every `classification` key anywhere, not deduped). The 132-vs-114 gap is **18 nested tags
  inside a single receipt**, `ADV-0009`.

The narrower criticism survives and is the one worth keeping: **an occurrence sum answers a question
nobody asked.** The unit-level number is **31 distinct units carrying a review/refut-naming tag** —
*fewer* than the 42 the ladder resolves, because 11 rail-blocked units carry their cross-vendor
demand only in `blocked_on` prose. Counting the structured field alone **under**-reports this gate.

## 5. Unchanged by this round (do not re-litigate)

The auditor CONFIRMED these independently, including by re-deriving the split from the **pre-edit**
blobs at `899ff779^` (which my round-1 edits could not reach) and by reading the ten receipts from
committed blobs:

- The **satisfiable set is the same 10 ids**, on both bases, before and after the fix.
- **10 of 10 reviewed, receipted, `verdict=PASS`, `independent=true`, `fresh_context=true`**, notes
  1,027-2,092 chars, none claiming SUCCESS, all ADMITTED by `receipt_validate.py`.
- **No same-vendor substitution occurred** where cross-vendor was demanded.
- **Condition 11**, not the reviewer, is the last gate for every unit in the program.

## 6. Reproduce (every command in this document, in order)

```
python command-center/p2-next/vendor_satisfiability.py          # 52/42/10 committed + 51/41/10 worktree; CHECK-only
python command-center/p2-next/split_review_gate.py              # 52 units, 42 CROSS_VENDOR / 10 ANY_INDEP; CHECK-only
python command-center/p2-next/_r2_control_stability.py          # both states: v2 ladder moves 6, fixed moves 0
python command-center/p2-next/_r2_control_b20.py                # both states: verifier red on a wrong expectation
python command-center/p2-next/_r2_reconcile.py                  # both states: 1 disagreement pre-fix, 0 post-fix
python command-center/p2-next/_r2_tagcensus.py                  # 114 / 31 units; refutes 137
python command-center/p2-next/_r2_probe_splitgate.py            # the drift probe (restores what it perturbs)
python command-center/p2-next/_b20_final_verify.py              # the 10 from committed blobs + RE-DERIVED counts
python command-center/p2-next/_r2_blobcheck.py                  # ruff over the COMMITTED blobs (LF), control fires
python command-center/p2-next/_audit7_adv0041.py                # ADV-0041 at worktree/HEAD/3 commits
python command-center/p2-next/_audit8_cause.py                  # pre/post-edit token scan behind defect 1
```

`_r2_blobcheck.py` is a HEAD-basis sibling of `docs/rule-audit/_r2_blobcheck.py`, which another lane
wrote for the *staged index*. Theirs is the better pre-commit tool and was not edited; it simply
fails closed here because this lane's work is already committed, so `--cached` is empty. The two
differ in exactly one line of input. Measured: **10 blobs, 0 CRLF, ruff format + check both rc=0
under the repo's real `ruff.toml`, and a mangled blob makes the same invocation exit 1.**

## 7. Residuals, inline

- **UNRESOLVED [uncertain, 20-55%]** — whether the committed figure to price is **42** or **41**.
  Turns entirely on the legitimacy of the sibling's uncommitted `ADV-0041` `openai`-reviewer PASS
  (§2). *Settling experiment:* that review's transcript or Codex call id.
- **NOT RECOVERABLE HERE** — auditor findings **2, 4, 5, 6**, truncated from my brief and absent
  from disk (§0). *Settling experiment:* re-read the audit output and diff it against this file.
- **UNVERIFIED [likely, 55-80%]** — rule **A2** reads a cross-vendor clause in `blocked_on` as a
  *demand*. A **negated** mention ("no longer needs cross-vendor review") would be misread. Measured
  today: 0 of the 10 satisfiable units contain any such token in `blocked_on`, so no unit is
  currently affected, and the error direction is **safe** (over-counts rail-blocked, over-prices
  `codex login`). *Settling experiment:* a negation-guard case in the selftest plus a scan of all 52
  `blocked_on` fields for negated cross-vendor mentions.
- **UNVERIFIED [uncertain, 20-55%]** — that the 42 would reach DELIVERED after a Codex review.
  Unchanged from round 1: this lane measures what receipts *demand*. Condition 11 bounds the answer
  regardless of vendor.
- **NOT-CHECKED** — whether `codex login` fixes the `agent/register` failure. Owner-only credential
  write; not attempted, `~/.codex/auth.json` not read.
- **HANDED OVER, not patched (outside the declared file scope):** `CROSS-VENDOR-RAIL-STATUS.md:1`
  and `:4` still say **43**; the measured figure is **42 of 52 committed / 41 of 51 worktree**. That
  is the number an owner would act on when pricing `codex login`, and it is now wrong by two
  different mechanisms. `blocker_census.py`'s review line reports an occurrence sum where a unit
  count is the answerable quantity (§4). Both are one-line edits in other lanes' files.
- **NO new reviews were run this round.** The satisfiable set did not change, so DoD item 2 is
  unchanged at 10 of 10. `BLD-0023` briefly looked like an 11th and is not one (§1).