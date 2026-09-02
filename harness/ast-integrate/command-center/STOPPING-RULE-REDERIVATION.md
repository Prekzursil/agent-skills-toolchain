# STOPPING-RULE RE-DERIVATION — Lane C2, independent check on the Phase-14 scorecard

**Unit:** lane C2. **Output file:** this file, mine alone. Investigation only — nothing committed,
no catalog edit, no branch.
**Input under review:** `command-center/PROGRAM-STOPPING-SCORECARD.json`
(`program-stopping-scorecard/v1`, `generated_at: 2026-08-10`, tree_anchor `04e4736c`).
**My tree anchor:** `ef6e2c4b` on `main`; `git rev-list --left-right --count origin/main...HEAD` =
`0 0`; tracked tree CLEAN (`git status --short | grep -v '^??'` is empty); 120 untracked entries.
**Delta since the scorecard's anchor:** `git rev-list --count 04e4736c..HEAD` = **25 commits**.

> If it still reads this way, the unit died before investigating anything and no verdict here may be
> cited.

**RESULT: Phase 14 scored 2 TRUE / 19 FALSE. I score 3 TRUE / 18 FALSE. Exactly one verdict flips:
condition 4, FALSE → TRUE.** Twenty of twenty-one agree with Phase 14. Nine of the twenty agreements
rest on a *different* sub-failure than Phase 14 cited, because Phase 14's stated sub-failure was
since closed — those are recorded as "same verdict, changed reason", which is a materially different
claim from "unchanged".

**COVERAGE — MEASURED:** 20 of 21 conditions re-derived from probes I executed at `ef6e2c4b`.
**1 of 21 (condition 9) I did NOT re-measure** — re-running Phase 11's 26 claim probes was out of
budget, so I default to agreeing with Phase 14 and label it `NOT-CHECKED-BY-ME` rather than
laundering its receipt as my own measurement. Condition 20 is scored with an explicit
self-certification refusal (see its row).

---

## 1. The table

`CHANGED?` = did the **verdict** change. `reason changed` = the verdict stands but Phase 14's
stated basis no longer holds and a different one carries it.

| id | condition (abbrev) | P14 | mine | CHANGED? | confidence |
|----|--------------------|-----|------|----------|-----------|
| 1 | selected options implemented / superseded / rejected | FALSE | FALSE | no | almost-certain |
| 2 | contracted artifacts exist + pass schema/manifest | FALSE | FALSE | no · **reason changed** | almost-certain |
| 3 | all P0/P1 defects closed or proven blocked | FALSE | FALSE | no · **reason changed** | almost-certain |
| 4 | no required test is red | FALSE | **TRUE** | **YES — FLIPPED** | likely (see §3) |
| 5 | mutation + negative-control coverage shows detector validity | FALSE | FALSE | no · **reason changed** | likely |
| 6 | clean install / update / rollback / uninstall pass | FALSE | FALSE | no | almost-certain |
| 7 | cross-platform + cross-client matrices meet the support contract | FALSE | FALSE | no | almost-certain |
| 8 | benchmark shows the intended improvement, no material regression | FALSE | FALSE | no · **reason changed** | likely |
| 9 | independent confirmers pass | FALSE | FALSE (`NOT-CHECKED-BY-ME`) | no | uncertain |
| 10 | adversarial refuters cannot produce an unresolved counterexample | FALSE | FALSE | no | almost-certain |
| 11 | security / privacy / legal / supply-chain gates pass | FALSE | FALSE | no · **reason changed** | almost-certain |
| 12 | docs and code agree | FALSE | FALSE | no · **reason changed** | almost-certain |
| 13 | release / canary succeeds | FALSE | FALSE | no · **reason changed** | almost-certain |
| 14 | rollback is tested | TRUE | TRUE | no (now 2 signals, not 1) | almost-certain |
| 15 | every residual unknown has a settling experiment + impact | FALSE | FALSE | no | almost-certain |
| 16 | ≥160 workflow candidates with provenance + license | TRUE | TRUE | no | almost-certain |
| 17 | ≥96 materially distinct blueprints **executable** | FALSE | FALSE | no | almost-certain |
| 18 | scout/forge + merge maps + tournament + lineage tests pass | FALSE | FALSE | no | almost-certain |
| 19 | council runtime + 48 protocols + 64 presets + controls | FALSE | FALSE | no | almost-certain |
| 20 | the final synthesis has been meta-reviewed | FALSE | FALSE | no | almost-certain |
| 21 | the shared completion predicate returns true for the program | FALSE | FALSE | no | almost-certain |

Tally — mine: **3 TRUE / 18 FALSE / 0 NOT-CHECKED** (condition 9 scored FALSE by deference, flagged).

---

## 2. The one flip — condition 4, FALSE → TRUE

Phase 14 gave three grounds for FALSE. **All three are measurably closed at `ef6e2c4b`:**

1. *"a REQUIRED CI gate is red: `python tools/command-center/render.py --check` exits 1."*
   **REFUTED at HEAD.** `python tools/command-center/render.py --check` →
   `SUCCESS:cc-render no drift`, exit **0**. Root cause was fixed by
   `67b37e22 fix(command-center): render regenerates the graph, and does it BEFORE hashing the manifest`.
   Independent corroboration, not a re-run of the same gate: I hashed all 14
   `ARTIFACT-MANIFEST.json` entries against disk myself — 13 of 14 match byte-for-byte, and the
   14th is the manifest's own entry carrying the sentinel `"sha256": "(self)"`, not a mismatch. My
   first pass mis-scored that sentinel as a failure; correcting my own detector is what turned
   "1 of 14 mismatches" into 0.
2. *"the same suite on Ubuntu 24.04 gives 24 failed, 3875 passed, exit 1, 22 of the 24 in
   platform/routing."* **REFUTED at HEAD, by two mechanically independent signals.**
   (a) GitHub's own run 31416913927 @ `ef6e2c4b`: job `gate-tests-coverage (platform)` = `success`,
   on `ubuntu-latest`. (b) I executed the exact two packages locally:
   `python -m pytest platform/routing platform/coordination -q` → **352 passed, 1 skipped in
   570.45s**. The hermeticity fix is `58143878 fix(routing): make the Phase 8 lane hermetic` plus a
   **581-file committed fixture home** (`git ls-files platform/routing/fixtures/home | wc -l` = 581)
   bound by `platform/routing/conftest.py:99,113`.
3. *"'required' is undefined for this tree: platform/ appears 0 times in all 7 workflow files, so
   the 3,922-test suite is required by nobody."* **REFUTED.**
   `grep -rn "platform" .github/workflows/*.yml` returns 22 hits; the job is
   `.github/workflows/quality.yml:1367` `test-platform`, named `gate-tests-coverage (platform)`,
   added by `783116be ci: add the platform/ test lane - 3,946 tests that CI has never once run`.

Full CI state at `ef6e2c4b`: `quality` **success** (8 of 8 jobs green — node workspaces, opengrep
SAST, osv-scanner deps, **platform**, gitleaks, ruff, basedpyright, python packages),
`no-runtime-junk` **success**, `routing-benchmark` **success**, `autofix-models` **skipped**.

### The caveat that must travel with this TRUE — it is partly vacuous

`gh api repos/Prekzursil/agent-skills-toolchain/branches/main/protection` returns
**`{"message":"Branch not protected"}`** with an **admin** token
(`gh api repos/… --jq .permissions` → `{"admin":true,…}`), and `…/rulesets` returns `404`. So the
detector is not permission-blind: **`main` enforces no required status checks at all.** Under the
strict reading of "required", the required set is EMPTY and condition 4 is *vacuously* satisfiable —
the same self-certification shape Phase 14 correctly identified in condition 21. I score TRUE on
**Phase 14's own reading** (the gates that run on push/PR), because that is the reading under which
it scored FALSE and all three of its grounds are now closed; but a reader must not upgrade this to
"the program's tests are protected". UNVERIFIED: whether the owner intends `main` to be protected —
that is an owner decision, not a measurement, and I did not change any setting.

Residual, disclosed inline: **no Windows CI arm exists** (14 of 14 jobs are `runs-on: ubuntu-latest`,
zero `strategy:`/`matrix:` in any of the 7 workflows), so a Windows-only regression is red in nobody's
gate. That is condition **7**'s failure, not condition 4's, and I have kept it there.

---

## 3. Same verdict, changed reason — the nine rows worth reading

**Condition 2 (FALSE).** Phase 14's four sub-failures: (a) manifest check red → **CLOSED** (§2).
(b) `tools/marketplace/` + `.claude-plugin/marketplace.schema.json` absent → **STILL ABSENT**
(`ls` on both → "No such file or directory"). My own catalog scan confirms Phase 14's count
*exactly*: 61 units reference `tools/marketplace`, yielding **18 distinct absent
`tools/marketplace/schema/*.schema.json` tokens** plus a 19th absent
`.claude-plugin/marketplace.schema.json`. (c) delivery reconciliation → **4** of 2,007 units now have
an artifact at their declared `output_path` (Phase 14 measured 2): `receipts/BLD-0023.json`,
`receipts/TST-0334.json`, `receipts/TST-0350.json`, `wfa/schema/wfa-schema-pack.json`. 4/2007 = 0.20%.
(d) fresh clone → **CLOSED**: I cloned `ef6e2c4b` to a temp dir and ran
`python tools/measure-guard/suitefloor.py --suite platform` →
`OK platform: collected 3946 >= floor 3900 (+6 package floors)`, exit 0. **(b) alone carries FALSE.**

**Condition 3 (FALSE).** Of Phase 14's four live P1s: (1) forged-receipt predicate → **STILL LIVE**,
re-executed. (2) mutation battery 0/12 → **CLOSED**. (3) `tools/marketplace/schema` → **STILL
ABSENT**. (4) render-ordering defect → **CLOSED**. **2 of 4 closed; 2 live.**

**Condition 5 (FALSE).** Phase 14's headline sub-failure is gone:
`python platform/lib/_mutation_selfcheck.py` → **`SUCCESS:predicate-mutation-selfcheck 12/12 mutants
killed`, exit 0**, on a tracked tree with **zero modifications** — so this is committed HEAD, not an
uncommitted orphan (fixed by `3b7a94a1 fix(platform/lib): the mutation battery on main reports 12
survivors it never actually ran`). Two reasons FALSE survives: the tool is still in **no** CI file
(`grep -rn "mutation.selfcheck" .github/workflows/ ci/` → 0 hits), and
`UNKNOWNS-REGISTER.md:15` U-4 still records that only **7 of 46** named failure classes are
demonstrably seeded. Coverage, not one battery, is what the condition asks for.

**Condition 8 (FALSE).** Phase 14's sub-failure (a) — "NOT PORTABLE, the corpus is discovered from
the operator's LIVE `~/.claude` tree" — is **CLOSED**: the 581-file fixture home is committed,
`conftest.py` binds `ROUTING_HOME` to it, and `.github/workflows/routing-benchmark.yml` now runs the
lane on CI (green). Sub-failures (b) abstention does not generalise, (c) the k=10 rung buys zero
recall at pure context cost, and (d) **no baseline-vs-after benchmark artifact for the platform as a
whole** all survive — `BASELINE-SNAPSHOT.md` is a Phase-0 *harness* freeze, not a routing before/after.

**Condition 11 (FALSE).** A **third**, previously unreported revocation defect was found AND fixed
since the anchor: `a8d84652 fix(marketplace): a security-response revocation could brick the whole
registry` — revoking one package made every package uninstallable while `mkt revoke` printed
`SUCCESS`. Phase 14's two named escapes are not in that commit. Independent of all three: **no SBOM
instance** (only `platform/marketplace/mkt/sbom.py` + `schema/sbom.schema.json`), **no license
inventory**, **no vuln-scan artifact**, **no `CHANGELOG.md`**, and no STRIDE *deliverable* — `STRIDE`
appears only in catalog declarations and review prose. FALSE stands on the missing artifacts alone.

**Condition 12 (FALSE).** Re-measured all five. (1) the manifest hash mismatch is **gone**, but the
structural defect is not: `tools/command-center/render.py:276` writes `"verified_on_disk": True`
**unconditionally**, so the flag is still not gated on the check — Phase 14's own settling experiment
is unimplemented. (2) the predicate's "self-certifying" docstring
(`completion_predicate.py:32`) vs conditions 7/8/9/10/12 → **STILL LIVE**, and I re-executed the
refuter that proves it. (3) `RELEASE-CHECKLIST.md:15` **still** says to verify "against the **LF
blob** (`git archive`)" → **STILL WRONG**; lane C1 measured that exact file at HEAD as 3,220 B /
52 CRLF via `git archive` against 3,168 B / 0 CRLF via `git cat-file -p`, and 3,168 is the byte count
`ARTIFACT-MANIFEST.json` itself records. (4) the `routing/index.py:446-450` comment: I verified
`find platform/workflows -name "*TOURNAMENT-WINNER*"` = **0 files**, so the comment does describe a
removed state — but it now reads as a rationale for the dedupe rather than an assertion that the
double-write happens, so I downgrade this from "stale claim" to "wording worth tightening", not a
load-bearing mismatch. (5) `17-DECISION-LOG.md` **does not exist in this repo** (`find` at depth 6
from `/` returns nothing) — so I can neither confirm nor refute it here; `NOT-CHECKED`, and Phase 14
should not have cited an out-of-repo path without its access method.

**Condition 13 (FALSE).** OQ-3 is now **ANSWERED = PR-ONLY** (`OWNER-DECISIONS.md:32` table row +
`:41-45` decision-of-record), which retires Phase 14's own settling experiment and its
`condition_13_reading` caveat. FALSE survives on stronger ground: **0 of the 43 Phase-15/16 units
exist at their declared `output_path`** (lane C1, detector-controlled), `RELEASE-CHECKLIST.md` covers
**0 of the 20** Phase-15 spec deliverables, 17 of 43 units are gated by 6 dangling bucket tokens, and
`REL-0003` — *"owner ruling that makes stop condition 13 satisfiable under PR-ONLY"* — is
**OWNER-GATED and is not what OQ-3 supplied.** Also unchanged: no open PR, HEAD == `origin/main`.

**Condition 6 (FALSE) — the cleanest mechanical answer in the set.**
`git diff --name-only 04e4736c..HEAD | grep -c "^platform/plugin/"` = **0**. Not one line of
`platform/plugin/` changed since the scorecard was written, so both PARTIALs (hard-kill leaves a
blocking lock; health check verifies existence not integrity, control not wired to the exit code) are
unchanged *by construction* — no probe needed and none can disagree.

**Condition 20 (FALSE) — and I refuse to score my own document as the fix.** There is still exactly
ONE Phase-14 synthesis (`PHASE14-SYNTHESIS.md` + `PROGRAM-STOPPING-SCORECARD.json`, same unit,
`ls -la` both `Aug 10 16:15`). This file is an independent *re-derivation of the scorecard*, which is
step 1 of Phase 14's own settling experiment — but it is **not** a second full synthesis, and citing
it as the meta-review would be precisely the self-certification the scorecard's condition 21
identifies. A third agent must review both. **Anyone citing THIS file should note it too is
un-reviewed single-agent output.**

---

## 4. Verdicts I confirmed unchanged, with the detector control that makes the zero real

- **17 — no executor.** `grep -rlnE "def execute|def run_workflow|class WorkflowExecutor|def _execute_stage"`
  over `platform/lib/wfdsl/ platform/workflows/ platform/lib/*.py` → **0 files**. **Control:** the
  same grep style for `def validate|def resolve` over the same roots → **6 files**
  (`wfdsl/capabilities.py`, `wfdsl/resolve.py`, `wfdsl/validate.py`, `receipt_schema_gate.py`,
  `schema_resolver.py`, `vendor_identity.py`). The zero is a measurement.
- **18 — no merge/compatibility map.** `find platform -iname '*compat*'` → **0 hits**. **Control:**
  `find platform -iname '*tournament*'` → 2 files, and `grep -rl tournament platform --include=*.json`
  → 4 files. The only `*merge*` hits are two council presets and a PR-shepherd workflow/test.
- **19 — no council runtime, floors MET.**
  `grep -rlE "class CouncilRuntime|def run_council|class CouncilCompiler|def compile_council|def deliberate" platform/`
  → **0 files**; `platform/lib/councilspec/` is `expression.py registry.py semantics.py validate.py
  make_negatives.py` — a validator. On-disk floors: **52** protocol JSONs (floor 48), **77** preset
  JSONs (floor 64). Specified and validated; nothing deliberates.
- **16 — TRUE, reproduced from scratch.** My own scan of
  `platform/registry/workflow-candidates-[1-5].json`: **164 rows, 164 distinct ids, 1 `_manifest`
  row → 163 kept; 0 missing `provenance`; 0 missing `license`.** 163 ≥ 160. Note file 2 is a dict and
  the rest are lists — a counter that assumes one shape silently returns 132.
- **10 — FALSE, re-executed.** `python platform/lib/_p12_refute_predicate.py` →
  `SUCCESS:p12-refute-predicate REFUTED forgery=COMPLETE control=fires`. The forged receipt still
  reaches `COMPLETE`, and the tool's own control still fires.
- **21 — FALSE, re-measured with a control** (`command-center/_c2_c21_probe.py`, mine — **note its
  access method: that path is gitignored by `.gitignore:70` (`command-center/_*.py`), so it exists in
  my working tree only and a fresh clone will NOT have it; the numbers below are the reproducible
  claim, the file is only the recipe**):
  2,007 work units, all with a non-empty `output_path`, **2,007 distinct**; intersection with the
  14-entry `ARTIFACT-MANIFEST.json` = **0**. **Control:** injecting `command-center/STATUS.md` into
  the declared set yields exactly **1** match, so the matcher does find an overlap when one exists.
- **14 — TRUE, now on two signals.** Phase 14 had one (a sibling receipt it read but did not
  re-execute). I added a second, mechanically different one: `python -m pytest platform/plugin -q -k
  rollback` → **2 passed, 250 deselected**, in `platform/plugin/test_lifecycle.py`.
- **15 — FALSE.** `UNKNOWNS-REGISTER.md` still holds exactly **13** rows (U-1…U-13), **0** containing
  "retired" (`grep -ci retired` → 0), and none of the Wave-4/Wave-5 residuals added.
- **1 — FALSE.** OQ-1 (option selection) and OQ-2 (overrides/priority) are still **OPEN**
  (`OWNER-DECISIONS.md:30-31`), so the predicate still has no subject. Phase 14's evidence sentence
  *"27 of 27 owner questions OPEN, zero answered"* is now **stale**: my parse of the table gives
  **27 rows = 25 OPEN + 2 ANSWERED** (OQ-3, OQ-4). The verdict is unaffected; the sentence needs
  narrowing.
- **7 — FALSE.** `grep -rn "runs-on:" .github/workflows/*.yml` → **14 × `ubuntu-latest`, nothing
  else**; **zero** `strategy:` or `matrix:` in any of the 7 workflows. No macOS, no Windows, no
  per-client install test. Phase 14's "13 CI jobs" is now 14, and its "platform/ appears 0 times" is
  refuted (§2) — neither moves the verdict.
- **9 — FALSE by deference, `NOT-CHECKED-BY-ME`.** I did not re-run Phase 11's 26 claim probes.
  Nothing in the 25 commits re-runs them, so the 18 CONFIRMED / 5 PARTIAL / 3 REFUTED split and its
  tripped escalation threshold stand unrefreshed. Confidence **uncertain** — this is deference, not
  measurement, and it is the one row a reader should not cite as re-derived.

---

## 5. PROPOSALS

`id | current state | what I MEASURED | proposed disposition | evidence anchor | confidence`

| id | current | measured | disposition | anchor | conf |
|----|---------|----------|-------------|--------|------|
| 1 | FALSE | OQ-1/OQ-2 OPEN; 25 OPEN + 2 ANSWERED of 27 | **STAYS-OPEN** (OWNER-GATED on OQ-1) | `command-center/OWNER-DECISIONS.md:30-31` | almost-certain |
| 2 | FALSE | 18 `tools/marketplace/schema/*` + 1 `.claude-plugin/marketplace.schema.json` absent; 4/2007 delivered | **STAYS-OPEN** | `command-center/_c2_c21_probe.py` output | almost-certain |
| 3 | FALSE | 2 of 4 P1s closed, 2 live | **STAYS-OPEN** | rows 5 + 10 below | almost-certain |
| 4 | FALSE | all 3 grounds refuted; every push/PR gate green at HEAD | **CLOSE** (evidence already on disk; disclose the branch-unprotected vacuity) | quality run 31416913927 @ `ef6e2c4b`; `.github/workflows/quality.yml:1367` | likely |
| 5 | FALSE | 12/12 killed at committed HEAD, but 0 CI hits and U-4 7/46 | **STAYS-OPEN** | `command-center/UNKNOWNS-REGISTER.md:15` | likely |
| 6 | FALSE | `platform/plugin/` = 0 files changed since `04e4736c` | **STAYS-OPEN** | `git diff --name-only 04e4736c..HEAD` | almost-certain |
| 7 | FALSE | 14/14 jobs `ubuntu-latest`, 0 matrix | **STAYS-OPEN** | `.github/workflows/*.yml` | almost-certain |
| 8 | FALSE | portability CLOSED; (b)(c)(d) live | **STAYS-OPEN** | `platform/routing/conftest.py:99,113` | likely |
| 9 | FALSE | not re-measured | **STAYS-OPEN** (`NOT-CHECKED-BY-ME`) | `command-center/P11-CONFIRMATION.md` | uncertain |
| 10 | FALSE | forgery still `COMPLETE`, control fires | **STAYS-OPEN** | `platform/lib/_p12_refute_predicate.py` | almost-certain |
| 11 | FALSE | 3rd revocation defect fixed; no SBOM/license/vuln/CHANGELOG/STRIDE instance | **STAYS-OPEN** | commit `a8d84652`; `find . -iname '*sbom*'` | almost-certain |
| 12 | FALSE | 2 of 5 live, 1 resolved-in-fact-not-in-structure, 1 downgraded, 1 unverifiable | **STAYS-OPEN** | `tools/command-center/render.py:276`; `command-center/RELEASE-CHECKLIST.md:15` | almost-certain |
| 13 | FALSE | OQ-3 = PR-ONLY; 0/43 P15 units exist; `REL-0003` owner-gated | **OWNER-GATED** on `REL-0003`, then STAYS-OPEN | `command-center/PHASE15-16-STATUS.md` §1-2 | almost-certain |
| 14 | TRUE | 2 rollback tests pass + sibling receipt | **CLOSE** (evidence on disk; scope = the package verbs only) | `platform/plugin/test_lifecycle.py` | almost-certain |
| 15 | FALSE | 13 rows, 0 retired, Wave-4/5 residuals absent | **STAYS-OPEN** | `command-center/UNKNOWNS-REGISTER.md` | almost-certain |
| 16 | TRUE | 163 kept rows, 0 missing provenance/license | **CLOSE** (floor MET under both counting rules) | `platform/registry/workflow-candidates-[1-5].json` | almost-certain |
| 17 | FALSE | 0 executor files, control = 6 | **STAYS-OPEN** | `platform/lib/wfdsl/` listing | almost-certain |
| 18 | FALSE | 0 `*compat*`, control fires | **STAYS-OPEN** | `find platform -iname '*compat*'` | almost-certain |
| 19 | FALSE | floors 52/77 MET, 0 runtime files | **STAYS-OPEN** | `platform/lib/councilspec/` listing | almost-certain |
| 20 | FALSE | one synthesis, un-reviewed; I cannot score my own file | **STAYS-OPEN** | `ls -la command-center/PHASE14-SYNTHESIS.md` | almost-certain |
| 21 | FALSE | manifest intersection 0 (control = 1); 4/2007 exist; 19 schemas absent | **STAYS-OPEN** | `command-center/_c2_c21_probe.py` output | almost-certain |

**Only conditions 4, 14 and 16 have a CLOSE proposal, and each names evidence already on disk.** No
other row is closeable today; three rows (1, 13, and 11's 239/261 `mcp__` authorization gap) are
OWNER-GATED and I have not invented an answer for any of them.

---

## 6. Corrections Phase 14's own text needs (verdicts unaffected)

1. cond 1 — *"27 of 27 owner questions OPEN, zero answered"* → **25 OPEN / 2 ANSWERED**.
2. cond 2(a), 3(4), 12(1) — *`render.py --check` exits 1* → **exits 0** since `67b37e22`.
3. cond 2(d), 4 — *a fresh clone dies* → a fresh clone **collects 3,946**.
4. cond 4, 7 — *"platform/ appears 0 times in all 7 workflow files"* → **22 hits**; *"13 CI jobs"* → **14**.
5. cond 5 — *0/12 at committed HEAD, repair is an uncommitted orphan* → **12/12 at committed HEAD**.
6. cond 8 — the routing figures were a property of one box → the lane is now **hermetic** on a
   581-file committed fixture.
7. cond 13 — PR-ONLY was an unrecorded executor assumption → **OQ-3 ANSWERED**.
8. cond 2(c), 21 — *"2 of 2,007"* → **4 of 2,007**.
9. cond 12(5) — `17-DECISION-LOG.md` is cited with no access method and **is not in this repo**;
   per the path-carries-its-access-method rule that citation is unusable as written.

## 7. Condition 11 of the *predicate* (not scorecard row 11) — the retracted claim, honoured

I read `command-center/STRUCTURAL-CONDITION-11.md` and
`command-center/P10-REREVIEW-AND-C11-REFUTATION.md` and I do **not** repeat the retracted headline.
The retracted sentence was *"condition 11 is unsatisfiable for EVERY work unit, so no unit can ever
reach SUCCESS"*; it was REFUTED by execution — a purpose-built manifest naming the artifact + sha256
returns **SATISFIED**, with a negative control (empty `artifacts` array) still returning UNSATISFIED.
**Condition 11 IS satisfiable; it is unsatisfied for all 2,007 units under the current convention.**
I independently reproduced the mechanism that makes that true — declared-`output_path` ∩ manifest = 0
with a control that fires (§4) — so my scorecard-row-21 reasoning rests on the *surviving* narrow
finding, not the retracted one. The real defect it exposes is a **definite-article spec
(`_USER-PROMPTS.md:10643`, "*the* artifact manifest") against a free-string implementation**
(`manifest_path` typed `{"type":"string","minLength":1,"maxLength":1024}`, no enum/const/pattern),
which lets a future reader satisfy condition 11 by naming any file at all. That is an owner choice
(per-unit manifest vs extending `CONTRACTED_ARTIFACTS`), plus tightening the field either way.

## 8. Limits of THIS unit

- Condition 9 is deference, not measurement (labelled in every table).
- Conditions 6 and 14 rest partly on sibling receipts I read; for 6 the `git diff` makes re-execution
  unnecessary, for 14 I added a local executable signal but did not drive the packaged CLI myself.
- I could not run the full `pytest platform` suite (forbidden, and CI-gated already), so my Windows
  evidence is the two subpackages Phase 14 measured red on Linux, not the whole 3,946.
- `main` has no branch protection, so "required" has no formal definition in this repo; §2 states
  both readings rather than picking the flattering one.
- This file is un-reviewed single-agent output. It is not the condition-20 meta-review.
