# SLOP — BUILD lane, round 7

**Headline: round 6 shipped its new gate with the exact defect its own sibling documents.**
`_r6_transcript.py` binds `REPO` to an absolute string literal. The CI-wired
`check_published_commands.py` carries a PORTABILITY paragraph naming that construction as why
another gate "cannot run on a CI runner at all". So this lane wrote the defect class down and
then committed it two rounds later. Measured consequence: a copy of the gate placed in a fresh
clone **re-measured the source worktree and wrote its receipt back into it**.

**Disclosed first, because it changes how this round should be read.** My re-entry brief carried
round **4**'s audit (D1, D2, O1, O2) and said a verifier confirmed defects last round. All four
were already fixed on disk — by rounds 5 and 6, which the brief does not know happened. I checked
that by running the instruments, not by reading the reports. So, as in round 6: **round 6's own
audit never reached me, and a defect it found that I did not independently re-derive is still open
and unknown to me.** Everything below was re-derived.

COVERAGE: DoD-1 is carried forward from round 5's committed receipt and deliberately NOT re-run
(§5). DoD-2 is unchanged and still PARTIAL. The ~84 non-ruff `quality.yml` steps remain
NOT-CHECKED. Nothing here claims main is green — only that the named gates are, at the named revs.

---

## 1. What the brief asked me to fix, and why I did not re-fix it

| # | round-4 audit finding | already fixed by | I verified it by |
|---|---|---|---|
| D1 | the executed deletion targeted a file that was already tracked, so it was in no bucket | round 5 (`f725baf4`) | reading `_r5_bucket_c.out.json` — the cycle now runs on a real bucket-(c) candidate and *reclassified it out of bucket (c)* on a K7 clone-regenerability test round 4 did not have |
| D2 | the DoD-4 control used a pathspec matching 0 tracked files — inert | round 5 | re-running `_r5_frozen.py` myself (§4): hash identity 9/9, live-detector control fires at 5 lines while the frozen dirs read 0 |
| O1 | "all 5 pytest targets ... ALL ARE TRACKED" contradicted its own `"NOWHERE": 1` | round 4/5 | the corrected wording is in place |
| O2 | "23 format + 11 lint" was stale | round 5 re-measured | superseded twice over; not re-litigated |

Re-running any of these would have overwritten committed evidence to produce the answer already
on disk. Round 6 hit the same fork and made the same call.

---

## 2. The defect — three measurements, each with a control that distinguishes

`python command-center/slop-report/_r7_defect.py` → `_r7_defect.out.json`,
verdict **CONFIRMED-NOT-CLONE-VALID**, pinned to pre-fix rev `b2df8f6b`.

**P1 — the root is an absolute literal.** Decided with `ast` over the module body, never a regex
over prose. The gate as shipped binds `REPO = "C:/Users/Prekzursil/source/ast-integrate"`.

The control has to survive the repair, so it runs on two files this round does *not* edit:
`check_published_commands.py` (uses `git rev-parse --show-toplevel`) must come back
**not**-hardcoded, and `_aud3_clone_gate.py` (which really does bind a literal, legitimately — it
clones *from* that path) must come back hardcoded. Both hold, so the detector separates the
hypotheses rather than reporting that a file was readable.

**P2 — a clone-run silently measures the source tree.** The gate was copied into a fresh clone
pinned at `b2df8f6b` and run with `cwd=clone`. Two mechanically independent signals, because the
obvious one is unusable here:

| signal | reading | meaning |
|---|---|---|
| doc COUNT | reported 10; clone holds 9, source holds 10 | it read the **source** |
| write-back | the clone's run mutated `_r6_transcript.out.json` **inside the source worktree** | only a hardcoded root can do that |

The source carries an untracked `SLOP-*.md` that cannot exist in a clone, so the two counts differ
by construction — that is what makes the count able to discriminate at all, and the probe asserts
it before reading the verdict.

**P3 — receipts come from the working tree, so CLEAN meant "on this disk".** Proven in memory, no
file mutated, on a genuinely divergent key — `n_before` in `_r2_bucket_c.out.json`, worktree `73`
against committed `1`:

| a document publishing… | vs worktree receipts | vs committed receipts |
|---|---|---|
| the **worktree** value (73) | AGREE — green | DISAGREE — a clone would fail it |
| the **committed** value (1) | DISAGREE | AGREE |

The first row is the false negative, the dangerous direction. The second row is what makes the
first one mean anything: it proves the two indices genuinely differ and the comparator is live in
both. **My first attempt got only the first row** — the mirror came back AGREE-on-both because the
chosen key was carried by more than one receipt and the gate matches against every receipt holding
it. Requiring the key to be unique to one receipt on both sides fixed the control. Recorded, not
quietly repaired.

---

## 3. The fix, and the proof that it changed what is measured

`python command-center/slop-report/_r7_verify.py` → `_r7_verify.out.json`, verdict **FIX-PROVEN**.

Three changes to `_r6_transcript.py`:

1. **Root resolved from `__file__`**, via `git -C <script dir> rev-parse --show-toplevel` — the
   same mechanism the CI-wired sibling already uses. Anchored on the file rather than cwd on
   purpose: the copy inside a clone has to resolve from where *it* sits.
2. **`--committed` mode** reads docs *and* receipts from HEAD blobs — the question a clone asks.
   It deliberately writes **no** receipt: a second `_*.out.json` beside this one would be indexed
   by the next worktree run, which is the self-indexing false negative round 6 caught as F4.
3. **`dirty_consulted`** is now reported, so a green verdict states its own scope instead of
   implying a repo-wide one.

Both states, in one clone, in one run — the old gate (the committed blob, still carrying the
literal) and the new one, each run twice against the same checkout:

| | reported | measured | wrote into source worktree |
|---|---|---|---|
| OLD (committed at `b2df8f6b`) | 10 docs | the **source** | **yes** |
| NEW (this round) | 9 docs | the **clone** | no |

If both had passed, the check would have been inert and would have proven only that python ran.

**Regression in this tree** — the fix must not change the answer where the answer was already
right: verdict `TRANSCRIPTION-CLEAN` unchanged, `claims_found` 38 unchanged, all 8 controls still
PASS. `docs_scanned` moves 9 → 10 for one reason, stated rather than buried: this round's own
untracked report is now in the corpus.

**And the honest scope, which is smaller than the mechanism.** Running
`python command-center/slop-report/_r6_transcript.py --committed` returns **TRANSCRIPTION-CLEAN
with 0 violations** across 9 committed docs and 82 committed receipts. So the hole was real and is
now closed, but **no published number currently exploits it**. This round fixed a live gap in the
instrument; it did not catch a wrong number. Saying otherwise would be the overclaim this lane has
produced in every round.

**One number it did catch was mine.** Run against this report before commit, the gate went
`TRANSCRIPTION-VIOLATIONS` on §5's quotation of a superseded reading of my own probe — a
use-vs-mention case, resolved with the marker convention rather than by deleting the disclosure,
and counted in `preserved_refutations` so the suppression is visible. That is the round-6
instrument doing exactly the job it was built for, on the round that was repairing it.

---

## 4. DoD status

| DoD item | verdict | evidence |
|---|---|---|
| 1. every candidate classified into four buckets with evidence | **PASS, carried forward** | round 5's committed `_r5_reclassify.out.json`: rows == untracked total, `partition_total: true`, its own 5 controls PASS. Deliberately not re-run — see §5 |
| 2. bucket (b) committed rather than deleted | **PARTIAL — unchanged, and I am not claiming progress** | the dangerous subset is still empty by construction (the CI-wired gate: `0 NEW, 0 stale`). The 179 weak-signal files are other lanes' in-flight evidence, outside my declared scope, and committing them unformatted still reddens `gate-lint-format` for every sibling |
| 3. bucket (c) deletions each backed by a shown regenerating command | **PASS** | 0 bucket-(c) files deleted by this round, so no deletion lacks backing. The delete→absent→regenerate→restore cycle stands from round 5 on a real candidate, `K8_restored: true` |
| 4. frozen-evidence directories untouched | **PASS, re-proven this round** | `python command-center/slop-report/_r5_frozen.py` → `FROZEN-UNTOUCHED-PROVEN`: 9/9 files byte-identical to their HEAD blobs, fail-closed counts 7 + 2, live-detector control returns 5 dirty lines on a known-dirty dir while both frozen dirs return 0, and no untracked file inside either |

---

## 5. Three of my own detectors were wrong. All recorded, none quietly repaired.

1. **I called a confirmed defect INCONCLUSIVE.** P2's first version decided which tree was
   measured by comparing the reported `head` against a HEAD read at probe start. Siblings commit
   under this lane continuously: source `245a24ec`, clone `245a24ec`, reported `c3cfefde` — the
   reported value matched *neither*, and the probe returned INCONCLUSIVE while two other signals
   in the same output already said CONFIRMED. **Equality against a moving value is not an
   invariant.** The check is kept in the receipt as `S1_head_equality_REFUTED_moving_head` and is
   never read for a verdict.
2. **The P3 mirror control passed for the wrong reason** — see §2.
3. **My evidence expired the moment I fixed the thing.** `_r7_defect.py` originally measured the
   live file, so after the repair it reported `DYNAMIC` and INCONCLUSIVE — a receipt that could
   never demonstrate the defect again.
   REFUTED, kept rather than deleted: that run also printed ~~`control_distinguishes: false`~~,
   which was a reading of the already-repaired file; the current receipt says true.
   Both probes now pin to
   the **newest rev whose committed blob is still hardcoded**, discovered rather than hand-pinned
   (`b2df8f6b`), and report the as-shipped and current states side by side. This is the same trap
   round 6 avoided by holding its T1/T2 fixtures inside the gate; I walked into it anyway.

**Why DoD-1 was not re-run.** Re-running `_r5_reclassify.py` regenerates the receipt that round
5's published histogram is compared against. That number was correct *at its rev*; the transcript
gate compares a rev-anchored claim to whatever the receipt says *now*, so regenerating it would
have manufactured a violation in a sibling round's correct sentence. That is a real limitation of
the gate, disclosed here rather than discovered later — **UNVERIFIED whether any other published
claim is already exposed to it. Settling experiment:** re-run each producer in a scratch copy and
diff the receipt against its committed blob, flagging any key a doc cites by name.

---

## 6. Residuals

- **DoD-2, 179 weak-signal bucket-(b) files, unchanged.** Not swept, not silently passed. Settling
  experiment unchanged: each owning lane commits its own, or a per-lane gate requires it at close.
- **Round 6's audit never reached me.** Any finding it raised that I did not re-derive is open.
- **The transcript gate is rev-blind** (§5). It compares today's receipt against a claim anchored
  to an older rev.
- **`_r6_transcript.py` is still not CI-wired.** It is now *portable enough* to be, which it was
  not before, but wiring it is a separate change with its own corpus-cost question.
- Three receipts (`_r2_bucket_c`, `_r3_redproof`, `_r3_twinsurface`) have been dirty for several
  rounds. Inspected: re-run churn — timings, a rev field, a `__pycache__` snapshot. Left alone;
  they belong to the rounds that wrote them.
- NOT-CHECKED: the ~84 non-ruff `quality.yml` steps.
