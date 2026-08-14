# LANE DOCS — BUILD round 8 (re-entry after a CONFIRMED refutation of round 7)

COVERAGE: every row in §2 is backed by a command I executed this round. NOT measured here, and
said so rather than folded into a pass: a real CI run, a Linux run, the full `ci/tests` sweep, and
`validate-all-skills.ps1` over 337 skills. See §6.

> If this document still reads `UNKNOWN - not yet measured`, the unit died before measuring
> anything and no verdict here may be cited.

---

## 0. What round 8 is for

Round 7 shipped an anchor-ratchet gate and corrected round 6's reasoning. Everything it
*measured* re-measured true this round (§2 R8-2), so none of it is being undone.

Two things were open:

1. **Round 7 disclosed a weakness in its own gate that it had never measured.** Residual 5 said a
   replaced anchor would go undetected. Round 7's control only ever *stripped* an anchor. Round 8
   ran the replacement.
2. **Round 5 scoped 13 fenced command-doc invocations out — "out of scope by design".** Nobody
   ever checked whether they resolve *anywhere*. From inside the repo, "correctly resolved at
   runtime" and "a published command tells you to run a file that exists nowhere" look identical,
   and the second is this lane's charter defect class.

Round 8 measured both. The first was an **overclaim in the pessimistic direction** — the gate is
stronger than its own doc said. The second found **two genuine dead promises** among nine raw
tokens, and the seven non-defects are the reason the raw number must never be reported.

---

## 1. Starting state (executed, not assumed)

```
HEAD at entry     f0d111ad 2026-08-14   ->  a4594b69 mid-round (siblings committed; 283 -> 284
branch            main                      dirty paths, none of them this lane's)
3 docs suites     48 passed, exit 0         py -3.11, the interpreter CI uses
gate suite        23 passed, exit 0         ci/tests/test_command_doc_promises.py
```

---

## 2. The doc-vs-reality table for round 8

Verdict = what I measured. Resolution = fix-doc / fix-code / route / no-action, with the reason.

| # | claim under test | probe (executed by me this round) | verdict | resolution + reason |
|---|---|---|---|---|
| **R8-1** | `_LANE-DOCS-BUILD-R7.md` §6.5: *"A future edit could replace `67137879` with a different valid-looking SHA and the arm would stay green"* | `docs/_lane_docs_r8_anchor_mutation.py` — replaces each anchor with `0badc0de` in each carrier and runs the SHIPPED pytest test. **4 mutations, 4 fired.** C1 asserts the SHA is in the region first (else the red proves nothing); C2 asserts the fixed state is green (else red-in-both-states); C3 restores and verifies by sha256 | **REFUTED — the gate is STRONGER than its own doc claimed.** `_missing_anchors` compares against exact SHAs in a non-carrier module, so a replacement is detected, not only a removal | **FIX DOC.** Round 7's wording kept verbatim and marked REFUTED; replaced with the measured behaviour plus the residual that IS real (the arm cannot verify the anchored commit *produces* the counts — that needs history). An overclaim in the pessimistic direction is still an overclaim. |
| **R8-2** | round 7's own load-bearing numbers | re-ran `_lane_docs_r6_pinned_counts.py` (**`pre_fix=20/16 post_fix=19/15`**, C1/C2/C3 ok); `git rev-parse 5d573583^` → **`67137879`**; `grep` for the suite in `quality.yml` → **line 1503**; `fetch-depth: 0` as a YAML *field* → **6 workflows** (autofix-models, hook-audit, mcp-audit, p2next-rail-count, quality, skill-dual-write) | **ALL REPRODUCE** | **no action.** Re-reporting them as new findings would be false. |
| **R8-3** | round 5: *"the 13 code-block invocations are out of scope by design, not overlooked"* | `docs/_lane_docs_r8_dead_invocations.py` (4-state control) over 72 top-level command docs: **9 tokens / 15 occurrences** unresolved at the repo root → **1 SHORTHAND, 4 RUNTIME, 4 DEAD-by-resolution** | **HALF-CONFIRMED.** Right for 5 of 9 — they resolve under `~/.claude/…` or elsewhere in the repo. Wrong as a blanket: 4 resolve nowhere | **split by row below.** A single verdict on all 13 was the error; each token needed reading. |
| **R8-4** | `commands/claw.md:12` — `node scripts/claw.js`, plus `:18` *"Or via npm: `npm run claw`"* | two independent signals: `git ls-files` basename search → **NONE tracked**; recursive search of `~/.claude`, `~/.agents`, `~/.codex` → **NONE live**. Root `package.json` (tracked, 11,075 files) has scripts `test` and `validate:skills` only → **no `claw` script**. `skills/nanoclaw-repl/SKILL.md:9` points at the same missing file | **CONFIRMED DEAD — both documented ways to start NanoClaw v2 fail**, and a third artifact (the skill) points at the same absent file | **ROUTE, not fix-doc.** Writing a REPL with branching/compaction/metrics is not a docs lane's call, and weakening the doc would make the document true and the estate no more capable. Same implement-or-retire shape as G1 (`/context-budget`) and G3 (rollback). Gated against growth by R8-6. |
| **R8-5** | `commands/harness-audit.md:17` — `node scripts/harness-audit.js <scope> --format …`, followed by *"This script is the source of truth for scoring and checks"* | same two signals → **NONE tracked, NONE live**. `git ls-files` for `harness-audit` returns **only the 3 command-doc copies** — no skill, no script | **CONFIRMED DEAD, and the strongest instance in the corpus** — the doc names the missing artifact as its source of truth | **ROUTE**, as R8-4. |
| **R8-6** | is anything stopping a *new* dead invocation from being added? | `git grep` — the round-5 prose arm explicitly excludes fenced code, and nothing else reads it. Confirmed by construction: the two dead promises above have sat unflagged | **CONFIRMED GAP** | **FIX CODE.** New ratchet arm in `ci/tests/test_command_doc_promises.py` (+8 tests, 23 → 31): a command doc may not invoke a `scripts/…` file that resolves under neither its own root nor the repo root, unless the token is in a classified baseline. Green on arrival; the baseline may only shrink. No workflow edit — already wired at `quality.yml:1503`. |
| **R8-7** | my own first resolver called `scripts/beads-fetch-pr-comments.ts` a dead promise | basename search → the file is **tracked at 3 paths** under the vendored metaswarm plugin, and the doc that names it sits at `tools/editor/metaswarm/.claude/commands/`, so the reference is correct *relative to that plugin's root* | **MY PROBE WAS WRONG** — root-anchoring error, the same shape as round 5's substring overclaim | **FIX MY CODE, twice.** The gate resolves against the doc's own root **and** the repo root (`_doc_root`, `_resolves_for_doc`), with a control that one token gives different verdicts for the vendored and top-level copies. The probe gained a SHORTHAND bucket and a C4 control. Reporting the raw number would have been a **4.5x** overclaim (9 raw → 2 genuine). |
| **R8-8** | the other two DEAD-by-resolution tokens | read each occurrence in context: `scripts/commands` is the English phrase *"Extract all scripts/commands with their descriptions"* (`update-docs.md:18`); `scripts/hooks/lib` sits inside a fenced block of **sample audit output** (`harness-audit.md:69`, *"Increase automated test coverage across scripts/hooks/lib. (tests/)"*) | **NOT DEFECTS — use-vs-mention.** Independently reproduces round 5's classification of `scripts/commands` | **no action.** Both are extension-less, so the shipped regex already excludes them; the gate's judgment and the reading agree. |

---

## 3. What changed

### 3.1 `ci/tests/test_command_doc_promises.py` — +8 tests (23 → 31)

One ratchet gate, one currency check on its own baseline, and six controls. Deliberately
repo-only: classifying a token as RUNTIME needs `~/.claude`, which does not exist on the CI
runner, so a live-root check would answer a different question on every machine. That
classification stays in the on-demand probe.

`KNOWN_UNRESOLVED_INVOCATIONS` carries seven tokens, each tagged RUNTIME / SHORTHAND / DEAD with
the measurement behind it. `test_the_unresolved_invocation_baseline_carries_no_paid_debt` fails
if an entry starts resolving — a stale debt list read as current is this lane's own defect class,
so the baseline is held to it.

### 3.2 `docs/_LANE-DOCS-BUILD-R7.md` — residual 5 rewritten

Refuted wording quoted verbatim and labelled, not deleted; replaced with the measured behaviour
and the correctly-scoped residual.

### 3.3 Three probes, all with controls

`_lane_docs_r8_anchor_mutation.py` (replacement mutation, 3 controls),
`_lane_docs_r8_dead_invocations.py` (4-state classifier, 5 controls),
`_lane_docs_r8_bothstates.py` (real-file mutation against the shipped gate, 3 controls).

### 3.4 Scope, stated up front

This round edits `ci/tests/**`, outside the lane's declared scope of `docs/**`, `README.md`,
`AGENTS.md`, `CLAUDE.md`. Stated rather than left implicit, because an undisclosed widening is
what an audit faulted in round 5. Precedent: rounds 3 §7.6, 5 §8.5 and 7 §3.4 record this lane
owning `ci/tests/` for its own gate. **No workflow file touched** — `quality.yml` is the named
shared hazard and already runs this suite. `AGENTS.md`, `CLAUDE.md`, `README.md` and every
`commands/**` file are **not** touched; the two dead promises are routed, not papered over.

---

## 4. Detector controls (each distinguishes two hypotheses)

| control | H1 | H2 | result |
|---|---|---|---|
| **anchor replacement** (`r8_anchor_mutation`) | arm compares exact SHAs → RED | arm accepts any SHA-shaped token → GREEN | **PASS** 4/4 fired |
| **fixed-state precondition** | green before mutating | red in both states = measures nothing | **PASS** rc=0 |
| **anchor present before mutation** | mutation changes the region | region never had it | **PASS** |
| **real-file both-states** (`r8_bothstates`) | gate reads bytes on disk → RED | gate short-circuits → GREEN | **PASS** fixed=0 broken=1 |
| **doc-root resolver** (in-suite) | resolution is per-doc-root → vendored resolves, top-level does not | repo-root only → both unresolved, false dead promise | **PASS**, different verdicts for one token |
| **4-state classifier** | REPO/SHORTHAND/RUNTIME/DEAD separate | resolver broken → all one bucket | **PASS** 4 buckets, 4 distinct |
| **ratchet fires on a new missing script** | reads the corpus | reads something else | **PASS** |
| **ratchet silent on a resolving script** | not always-red | always-red | **PASS** (`scripts/longrun.ps1`) |
| **root-qualified reference exempt** | `${CLAUDE_PLUGIN_ROOT}/scripts/x.js` names its own root | substring slice → false bare claim | **PASS** — the round-5 16x overclaim shape |
| **extraction floor** ≥7 tokens | extractor alive | collapsed → vacuous green | **PASS** |
| **EOL agnosticism** | verdict independent of line endings | CRLF vs LF disagree | **PASS** |
| **corpus non-empty** | 72 docs | 0 → "nothing found" reads as clean | **PASS** |

---

## 5. Evidence (executed; commands and their real output)

```
start           48 passed exit 0 (3 docs suites) ; 23 passed exit 0 (gate suite)   py -3.11
anchor mutation SUCCESS:docs-r8-anchor fixed_state_rc=0 mutations=4 fired=4
                verdict=H1-exact-sha restored=True
                  test_command_doc_promises.py 67137879 -> 0badc0de  rc=1 FIRES
                  test_command_doc_promises.py 5d573583 -> 0badc0de  rc=1 FIRES
                  _LANE-DOCS-BUILD-R5.md       67137879 -> 0badc0de  rc=1 FIRES
                  _LANE-DOCS-BUILD-R5.md       5d573583 -> 0badc0de  rc=1 FIRES
pinned counts   SUCCESS:docs-r6-pinned controls=C1,C2,C3-ok pre_fix=20/16 post_fix=19/15
                head_moving=19/15         (re-derived, not quoted)
anchor parent   git rev-parse 5d573583^ -> 67137879   ; both objects are commits ;
                merge-base --is-ancestor 5d573583 HEAD -> 0
classifier      SUCCESS:docs-r8-dead controls=4-state-ok command_docs=72 tokens=9
                occurrences=15 shorthand=1 runtime=4 dead=4
                  DEAD    scripts/claw.js            commands/claw.md:12          fenced
                  DEAD    scripts/harness-audit.js   commands/harness-audit.md:17 fenced
                  DEAD    scripts/commands           update-docs.md:18   English phrase
                  DEAD    scripts/hooks/lib          harness-audit.md:69 sample output
                  SHORT   scripts/beads-fetch-pr-comments.ts  -> 3 tracked paths
                  RUNTIME 4 tokens -> ~/.claude/scripts/...
two signals     git ls-files basename: claw.js NONE, harness-audit.js NONE,
                beads-fetch-pr-comments.ts 3 paths
                recursive live search: claw.js NONE, harness-audit.js NONE
package.json    tracked=True ; scripts = {test, validate:skills} ; has_claw=False
both-states     SUCCESS:docs-r8-bothstates fixed_rc=0 broken_rc=1 arms_differ=True
                target=commands/prime.md eol=CRLF restored=True
gate suite      31 passed, exit 0        (23 before this round's +8)
3 docs suites   56 passed, exit 0
3 siblings      49 passed, exit 0
ruff 0.15.17    check "All checks passed!" exit 0 ; format --check exit 0
                exit codes captured BEFORE any pipe
CI wiring       quality.yml:1503 runs this suite ; fetch-depth: 0 set in 6 workflows
```

---

## 6. Residual, disclosed inline rather than in a footnote

1. **No real CI run, no Linux run, and this lane does not push.** Everything is local on the CI
   interpreter (3.11.9). Settling experiment: push and read `gate-lint-format (ruff)` and the
   `gate-tests-coverage` step.
2. **The two dead promises are ROUTED, not fixed.** `/claw` and `/harness-audit` remain published
   commands whose implementations exist nowhere. That is an implement-or-retire decision for the
   owner, exactly like G1 and G3. The ratchet stops the class growing; it does not pay the debt.
3. **The ratchet gates ADDITION, not correctness.** A doc could still reference a script that
   exists but does the wrong thing, and the baseline's RUNTIME/SHORTHAND tags are a snapshot: they
   were measured on this box, and `~/.claude` is not reproducible in CI. Settling experiment: the
   on-demand classifier, re-run on the target machine.
4. **The corpus split is real and worth knowing.** The classifier reads 72 top-level
   `commands/*.md`; the gate reads every tracked `**/commands/*.md` (a wider set, including
   vendored plugins and mirrors). The gate found a token the classifier's narrower corpus missed
   (`beads-fetch-conversation-history.ts`) — which is how R8-7 was caught. Two instruments with
   different corpora is a feature here, but their numbers are NOT interchangeable.
5. **TWO self-inflicted failures this round, both caught by a second probe rather than by
   inspection, both disclosed:**
   - **I clobbered a committed artifact.** My first action wrote a skeleton over
     `docs/_LANE-DOCS-BUILD-R6.md` (17,748-byte committed file → 1,334-byte stub) because I
     assumed round 6 had not happened. Restored with `git restore --source=HEAD`; `git status`
     clean and all four lane artifacts byte-identical to HEAD. The two-hypothesis control I ran
     on the dirty count was **confounded** by concurrent sibling writes (283 → 284 while HEAD
     moved `f0d111ad` → `a4594b69` and six sibling files were written), so the clean conclusion
     rests on `git status` being empty for the path, not on the count. The real lesson is the
     ground floor's: **recall before writing** — `git log -- <path>` would have cost one command.
   - **My classifier shipped a false DEAD** (R8-7), and would have reported a real, ordinary
     reference as a dead promise. Caught only because I ran a mechanically different second probe
     (basename search) before writing the finding down.
6. **A report-only sensitive-artifact notice fired twice** on edits to the test file:
   `sha256:6c638490d83a`. Surfaced per AGENTS.md §9. No credential was inspected, printed, or
   modified; almost certainly the `GITHUB_TOKEN=$(gh auth token)` example text and
   `${CLAUDE_PLUGIN_ROOT}` patterns quoted in the corpus tripping a heuristic.
7. **Full `ci/tests` sweep NOT-CHECKED.** Prior rounds measured 4 Windows-only failures at parent
   `96362031` that are not this lane's. I ran the 6 suites touching what I changed.
8. **Carried, not mine:** `skill-dual-write.yml` still has no `push:` trigger (INTEGRATE §6.1);
   R5-1 half 2 (fresh-install plugin wiring) remains UNVERIFIED [likely 55-80%], routed to
   hook-audit; G3 (rollback edit-checkpoints) still awaits the owner with a reviewed plan at
   `docs/hook-audit/ROLLBACK-DEPLOY-PLAN.md`.
