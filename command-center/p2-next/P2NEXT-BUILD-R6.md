---
title: P2NEXT-BUILD-R6
type: note
permalink: dqverify-repo-20261013/command-center/p2-next/p2-next-build-r6
---

# P2NEXT — BUILD round 4: the retraction landed in one page, and the gate watching the other one only counts

COVERAGE: every claim below names the probe that produced it. Two things stay unmeasured and say
so inline: full CI (11 of ~25 steps ran locally), and whether the 39 owed units would PASS a Codex
review. One thing I could not recover at all and say so in §0: the round-4 verifier's CONFIRMED
defect list.

## 0. What I was sent back for — and the part I could not recover

My brief's `PRIOR ROUNDS` array carries **round 1 only**, truncated mid-sentence inside its own MF2
(`.agents/sk`). Rounds 2 and 3 and their verifications are absent from it. Two mechanically
different searches for a round-4 verifier artifact — `Glob **/*VERIFY*` under `command-center/`,
and an mtime listing of every file touched in the last 95 minutes — both return **nothing newer
than `P2NEXT-VERIFY-R4.md` (05:57)**, which is the verifier of round *2*. Round 3's build
(`P2NEXT-BUILD-R5.md`; commits `23ed5b1c`, `245a24ec`, `7511c943`) has no verifier artifact on disk.

So I did not have the CONFIRMED list. Instead of guessing at it, I verified round 3's shipped work
myself and fixed what I found by execution. **The finding below is mine, not a verifier's** — weigh
it accordingly. Round 1's two must-fixes (the 449 sentence, the `host.tld:port` anchor) were closed
in rounds 2 and 3 and are not re-litigated here.

### One thing I broke and repaired inside the first minute, recorded rather than hidden

My first action wrote a skeleton to `command-center/p2-next/P2NEXT-BUILD-R4.md` — which **already
existed** as round 2's committed artifact. `git diff --stat` showed `21 insertions, 277 deletions`;
`git checkout --` restored it and `git status` reports it clean. This round's artifact is
`P2NEXT-BUILD-R6.md`. Cost: nothing durable. Cause: I assumed a filename was free instead of
listing the directory first — the same class as every other "assumed, not measured" defect here.

## 1. The defect: two owner-facing pages assert opposite states of the same fact, and CI is green

Round 3 retracted *"the cross-vendor review rail is DOWN"* in `CROSS-VENDOR-RAIL-STATUS.md`. It
left `command-center/E2E-WAVE-STATUS.md:124` — a page `rail_count_gate.py` **already scans as a
citing doc** — asserting it:

> 5. **The cross-vendor review rail is DOWN, and it gates 42 blocked units.** … Three green
> signals, unusable rail.

The gate returned `SUCCESS` on that state for a full round. Not because it skipped the file: it
read it, examined 7 on-topic claims in it, and found **the number correct**. `42` is still the
right count. C2 only reads numbers, so a citing-doc check meant to stop "the citing doc rotting
while the owning doc stays right" returns the identical answer whether or not the two pages
contradict each other. That is a control that cannot distinguish the two hypotheses.

The decision damage is not hypothetical: an owner reading the wave-status page is told the rail is
dead and that 42 units are gated on restoring it — the exact premise round 3 disproved, on the page
most likely to be read for cross-lane status.

## 2. The fix

**a. The citing page** (`E2E-WAVE-STATUS.md`, item 5) now carries the measured state, with the
refuted wording **quoted and marked `[superseded 2026-08-14]` rather than deleted**, since it also
lives in permanent commit messages.

**b. The owning page** declares the verdict once, in the machine-readable block that is already its
contract with CI: `rail_state: up`, `rail_probed: 2026-08-14`.

**c. `rail_count_gate.py` gains C6** — every page in the scanned set must agree with that one
declaration or carry the same dated marker C2 uses. Both fields are REQUIRED, and their shape is
checked (an undated verdict cannot be told apart from a stale one).

**Why C6 reads a FIELD instead of inferring the state from the owning doc's prose:** because I
tried the prose route first and it produced a confident wrong answer. `_k1_premise_scan.py` run 1
reported the owning doc as asserting UP on the strength of *"…whether the rail is up or down. That
is a control that looks the same under both hypotheses"* — a sentence about the **gate** being
state-blind. The conclusion was right and the evidence was fabricated by my regex, which is the
worse failure of the two. The disjunction guard and the declared-field design both come from that
miss.

**What C6 does NOT do, stated in the gate's own header and on the owner-facing page:** it proves
CONSISTENCY, never TRUTH. It makes no network call — `ci-hygiene.md` §2 keeps a live endpoint out
of the per-PR suite — so its silence means the corpus stopped contradicting itself and nothing more.
Only the round-3 probe, with its 401 control, says anything about the rail itself.

## 3. Evidence — commands and their real output

```
python command-center/p2-next/_k1_premise_scan.py
  OWNING command-center/CROSS-VENDOR-RAIL-STATUS.md
    L1     UP    '# The cross-vendor review rail ANSWERS - and 39 blocked units are still owed...'
    L36    UP    '## The rail answers. Two transports, and a control that proves...'
  CITING command-center/E2E-WAVE-STATUS.md
    L124   DOWN  '5. **The cross-vendor review rail is DOWN, and it gates 42 blocked units.**...'
  owning asserts: ['up']      CONTRADICTIONS: [('command-center/E2E-WAVE-STATUS.md', 124, 'down')]
  CONTROL A quote-strip discriminates: True (unstripped DOWN lines [16], stripped [])
  CONTROL B mutation clears it: True (post-mutation contradictions [])
  CONTROL C scanner CAN see the historical assertion (scope is a choice): True (P2NEXT-BUILD-R2.md L99)
  WORKTREE (post-fix): RAIL-STATUS 3 assertion(s) ['up'] | E2E-WAVE 0 | OWNER-DECISION-condition-11 0
  SUCCESS:k1-premise-scan

python command-center/p2-next/rail_count_gate.py     # BEFORE the doc fix, committed basis
  C6 rail verdict: the block declares ? probed ?; 3 rail-state assertion(s) across 2 page(s)...
  C1 RAIL-COUNT block is missing field(s): ['rail_state', 'rail_probed']
  C6 RAIL-COUNT rail_state must be one of ['up', 'down'], got ''
  C6 RAIL-COUNT rail_probed must be an ISO date (YYYY-MM-DD), got ''
  FAILED:rail-count-gate 3 problem(s)                                            exit 1

python command-center/p2-next/_k2_redproof.py
  ok  A post-fix working tree: silent (want SILENCE)
  ok  B pre-fix blob @0c64b983: FIRED (want FIRE) -- C6 E2E-WAVE-STATUS.md line 124: asserts the
        rail is DOWN while the RAIL-COUNT block declares UP, and the line carries no dated marker
  ok  C declaration flipped to down (control): FIRED -- C6 line 1: asserts the rail is UP while
        the RAIL-COUNT block declares DOWN
  ok  D real CLI on a flipped copy: exit 1 (want 1), 3 C6 problem(s)
  SUCCESS:k2-redproof C6 fires on the shipped defect, is silent on the fix, and is wired

python command-center/p2-next/rail_count_gate.py --self-test
  selftest: PASS (50 cases, 27 of them expecting a FIRE, every check in both states)   [was 37/22]

uvx ruff@0.15.17 check / format --check (3 files)   -> All checks passed! / 3 already formatted
```

Post-commit gate sweep is in §7.

## 4. Detector controls, per claim

| claim | control | result |
|---|---|---|
| the citing page contradicts the owning page | **B**: flip `rail is DOWN`→`rail is UP` in memory; the contradiction must vanish | vanishes — the finding is bound to that sentence, not to the file |
| the retraction itself is not the defect | **A**: disable quote-stripping; the owning doc's quoted retracted headline (L16) must reappear | reappears — quote-stripping is what excludes it, not luck |
| the scan set is a CHOICE, not a blind spot | **C**: the same scanner over a historical round artifact finds its DOWN assertion | finds it (`P2NEXT-BUILD-R2.md:99`) — excluded by scope, deliberately |
| C6 is not "the word DOWN is bad" | red-proof **C**: declare `down`, scan the owning doc | fires on the owning doc's own UP title |
| C6 is reachable, not merely importable | red-proof **D**: the real CLI on a flipped copy | exit 1 with 3 C6 problems (`ci-hygiene.md` §1) |
| the before-state is really a before-state | leg B pinned to `0c64b983`, not HEAD; exits 2 if that blob already carries the fix | held — round 1 shipped a HEAD-pinned probe that went red the moment its own fix landed |
| the self-test discriminates | 27 of 50 cases expect a FIRE; a one-sided suite fails | PASS |

## 5. What was NOT done, deliberately

- **No `codex login`.** Credential write, owner-only (AGENTS.md §9). `auth.json` never read.
- **No READY units built.** The lane spec forbids it. Round 2's correction of the false REASON
  (163-164 of 449 name cross-vendor; 285-286 do not) stands and is not re-litigated.
- **No same-vendor review substituted where cross-vendor is demanded.** The 42/10 demand split and
  the 39/3 owed/served split are untouched; I added no unit, moved no verdict.
- **`OWNER-DECISION-condition-11.md` NOT added to the scan set.** Measured first: it carries **0**
  rail-state assertions, so adding it buys coverage of nothing today while exposing its unrelated
  counts to C2. Stated as a choice with its measurement, not skipped silently.
- **Condition 11 untouched** — still the delivery ceiling, and now the whole owner decision.
- **`.github/workflows/**` untouched**, including the shared `quality.yml`. C6 needs no workflow
  change: `p2next-rail-count.yml` already runs this gate on push and PR.
- **The 4 dirty `REVIEW-*.json`** in the worktree are a sibling's CRLF phantoms; not touched.

## 6. Residual — inline, not blocking

1. **C6 is NEGATION-BLIND.** "the rail does not answer" matches as an UP assertion and would pass
   under `rail_state: up`. Measured cost today: **0** — no scanned page contains a negated
   assertion (`K1-PREMISE-SCAN.json`). Settling experiment named in the gate header: add a negation
   window to `STATE_ASSERT` and re-run `_k1_premise_scan.py`, which must still find exactly 3
   assertions in the owning doc and 0 in the citing one.
2. **After this fix, C6 has nothing live to fire on in the citing page** (0 assertions there now).
   Its value is prospective: it turns the next unmarked contradiction from silent into loud. Leg B
   is what proves it fires on real bytes, and leg B reads a pinned historical blob.
3. **C6 cannot see a contradiction in a page outside `SECONDARY_DOCS`** — the set is one document,
   so a page nobody declared can still rot. This was going to ship as a disclosed residual; I ran
   the settling experiment instead (`_k4_tree_survey.py`, AGENTS.md §9b — remediate the whole set,
   not the first symptom). Over **every tracked `.md`** at HEAD, using the gate's own imported
   predicate so the survey cannot drift from what the gate enforces:
   **0 LIVE pages assert the retracted verdict**; 4 hits remain and all 4 are round artifacts whose
   job is to record it (`P2NEXT-BUILD-R2/R5/R6`, `P2NEXT-GROUNDING`), classified by PATH so the
   use-vs-mention call is inspectable. **CONTROL:** the historical bucket is non-empty, so the zero
   is a measurement and not a broken grep — had both buckets been empty the survey would have
   exited 2 rather than reporting clean. The residual that REMAINS is prospective only: a NEW
   owner-facing page could assert it tomorrow and C6 would not scan it.
4. **UNVERIFIED [uncertain, 20-55%]:** whether the 39 owed units would PASS a Codex review. This
   lane has only ever measured what receipts DEMAND and which are already SERVED.
5. **NOT-CHECKED: full CI.** 11 gates ran locally out of roughly 25 steps. A Windows-local green is
   not CI green.
6. **The dual-write blocker is unchanged and NOT implicated** — this round touches no
   `.agents/skills/**` file. Control in §7.

## 7. Gate sweep — measured AFTER the commit (`7ab8a35e`), on the COMMITTED state

`.github/workflows/p2next-rail-count.yml` runs the first four. All green.

| gate | result |
|---|---|
| `rail_count_gate.py --self-test` | PASS — 50 cases, 27 expecting a FIRE, every check in both states |
| `rail_count_gate.py` (committed basis) | SUCCESS — 52 / 42 (39 owed, 3 served) / 10 / 10; catalog 2007, READY 449; **C6: block declares UP probed 2026-08-14, 3 assertions across 2 pages agree** |
| `vendor_satisfiability.py --basis committed` | SUCCESS — artifact drift False |
| `split_review_gate.py --basis committed` | SUCCESS |
| `_j3_redproof.py` (round 3's red-proof — must survive my change) | SUCCESS, 3/3 legs; leg B's missing-field list now also names `rail_state`, confirming the new field is required and did not displace the old ones |
| `_c4_blobcheck_mine.py 7ab8a35e` | 3 python blobs, **0 CRLF**, blob-form `ruff check` and `format --check` rc=0, **CONTROL mangled blob fires rc=1** |
| `ci/check_skill_dual_write.py --strict-parity` on `7ab8a35e` | **OK** — this round touches no `.agents/skills/**` file. **Control:** the same command on `1b1e1e4e` still reports `VIOLATIONS: 1`, so the gate discriminates |
| `ci/gen_skill_index.py --check --fail-on-drift` | INDEX DRIFT: no; canonical NOT declared: 0 |
| `ci/gen_skills_manifest.py --check` | skills_tracked=337 manifest_rows=337 malformed_lines=0 |
| `uvx ruff@0.15.17 check` / `format --check` (4 files) | All checks passed / already formatted |

**A detector failure of mine, in this very sweep.** My first dual-write run reported `OK` on *both*
`7ab8a35e` **and** `1b1e1e4e` — a commit round 1 measured as violating. Two agreeing greens, one of
which had to be wrong. Cause: I omitted `--strict-parity`, so I ran a different check from the one
CI runs and from the one the earlier rounds measured. The control is what exposed it; without a
commit known to fail, I would have reported a green that measured the wrong thing. Both rows above
are the corrected `--strict-parity` runs.

Not run: the node/npm steps, CodeQL, gitleaks, and the hook/workflow gates owned by sibling lanes.

## 8. DoD — re-derived first-hand from committed blobs (`_k3_dod.py`), not cited from a prior round

```
DoD1 rows=52 unique_ids=52 {'RAIL_BLOCKED': 42, 'SATISFIABLE_NOW': 10}
DoD2 non-empty reviewer_requirement 52/52; blocked_on 43/52
DoD3 satisfiable=10 reviewed_PASS_independent=10 notes 1027-2092 chars
DoD4 rail_blocked=42 still_owed=39 already_served=3
CONTROL fulfilment counter separates the populations: True (satisfiable fulfilled=0)
SUCCESS:k3-dod
```

| item | status |
|---|---|
| the population split into cross-vendor-required vs any-independent-reviewer | **PASS** — 42 / 10 of 52. (The brief's "48" is superseded and marked so in-tree; the population is 52.) |
| receipt text quoted per unit | **PASS for `reviewer_requirement` — 52/52 non-empty.** Scoped, per round 1's refuted overclaim: `blocked_on` is non-empty on **43** of 52; the 9 empty ones are faithful, their receipts carrying no `blocked_on` at all. |
| the satisfiable subset reviewed and receipted | **PASS** — 10/10 `verdict=PASS` + `independent=true`, notes 1027-2092 chars, all clearing C5's floor |
| the rail-blocked remainder counted exactly | **PASS** — 42 demanded, **39 still owed**, 3 already served; gate-enforced and partition-checked |

The control on DoD4 is what makes 39/3 a measurement rather than a reader artifact: the same
predicate returns **0** fulfilled across the SATISFIABLE population. A counter that merely detected
"has a reviewer" would have returned 10 there.