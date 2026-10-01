# design-v2-final — final verification critique (critic-v2)

- **Critic:** critic-v2, Claude Fable 5.1, 2026-09-19. Fresh context; wrote none of v1, v2 or the revision. Read-only except this file and `scratch/critic-v2/`; nothing under `/workspaces/agent-skills-toolchain` modified; no `*.hf.space` URL called; no token sought; no MCP connector used.
- **Read in order:** `design-v2-final.md` in full (2,515 lines: every section, the coverage matrix, `gate.sh`, every schema, every JS block, Appendices A-C), `design-v1-critique.md` (the C-1..C-38 checklist), `WORKFLOW_TOOL_REFERENCE.md`, `DECISION-QUEUE.md` "Resolved decisions", and the judges' reports (`judge-J1-red-team.md`, `judge-J2-tool-contract.md`, `judge-J3-program-fit.md`) spot-checked where Appendix A maps items. The reviser's artifacts under `scratch/revise-v2/` were treated as claims and re-verified.
- **Standard applied:** a C-gap counts closed only when the mechanism in the gate text or the JS handles the critic's failure input without opening a new hole, and only when the document's own description of that mechanism matches the code. Everything I could execute, I executed (§2, §3). Default verdict is `revise` unless nothing blocking or major remains.

## 0. Verdict

**`revise`.** 0 blocking, 3 major, 9 minor. The revision is real: all 38 first-critic gaps have live mechanisms, the reviser's artifacts are byte-identical to the document (§2.1), their 98/98 drive claim reproduces, and my own independent gate execution and 28-scenario fake-harness drive confirm every blocking closure (C-1..C-6) behaves as claimed. What keeps this from being the build standard is that three of v2's own descriptions of its mechanisms are false or under-specified — the exact "resolved as sentences" failure mode this revision was supposed to eliminate — and one sub-mechanism has two naive dead-end implementations. None of the three majors makes the run fail or lie at runtime (all fail conservative); all three are cheap, surgical fixes.

---

## 1. Independent mechanical verification (extraction from the DOCUMENT, not the reviser's copies)

| Check | Result |
|---|---|
| `gate.sh` extracted from doc lines 444-934 (491 lines) → `bash -n` | **OK** |
| All embedded Python: 13 `<<'PYEOF'` heredoc bodies → `ast.parse` | **13/13 OK** |
| All `"$PY" -c '…'` one-liners → `ast.parse` | **3/3 OK** (matches the doc's "13 heredocs + 3 one-liners") |
| §9 schemas extracted (doc lines 976-1145, 170 lines) → walk: root objects, `required ⊆ properties`, non-empty unique enums, keyword set ⊆ {type, enum, required, properties, items, minItems, description}, arrays have items | **clean, no violations**; 7 agent-facing roots; 34 `type:'object'` nodes under the reviser's counting convention (my first count of 40 double-walked CARD/FINDING as separate roots — reconciled, no discrepancy) |
| §13 body (doc lines 1430-2172, 743 lines) + §9 spliced at the marker → `node --check` | **OK in the ESM-factory form and in the async-IIFE wrap** (the plain body has top-level `return`, by design) |
| `grep Date.now\|Math.random\|new Date()\|isolation` over the assembled script | clean (only the words "session isolation" inside the H6 prompt string) |
| `meta.phases` titles vs `phase()` calls; `model:` overrides | all six titles called (Setup/Plan/Build/Integrate/Review/Synthesize); **zero** `model` overrides |
| **Document-vs-artifacts diff** (my extractions vs `scratch/revise-v2/`): `gate.sh`, `schemas.js`, `script.js` | **byte-identical** (diff rc 0 on all three); `assembled.mjs` differs only in the wrapper shape (harness-object factory + inner IIFE vs my parameter factory) — semantically equivalent, both `node --check` clean |
| Reviser's `check_gate.py` / `check_schemas.mjs` re-run | 13/13 + 3/3 parse; schema walk "no problems", 34 nodes / 7 roots — their counts are real |
| Reviser's `drive.mjs` re-run | **98 passed, 0 failed, 37 scenarios** — the headline claim reproduces |

### 1.1 Real gate execution (my own extracted `gate-doc.sh`, throwaway repo, scratch venv; `scratch/critic-v2/mydryrun.sh`) — 10/10

| # | Check | Result |
|---|---|---|
| T1 | wrong `--gate-sha256` | exit **66** (fail-closed self-integrity) |
| T2 | tampered baseline sha | RED at the pre-step `baseline` step |
| T3 | `--clean --self-test --journeys` on a good tree, detached worktree | exit 0; `broken_red: true`; **`false_claim_red: "true"`** — the C-2 fixture commit message really reds the inner `claim-lint` step (v1's C-2 reproduced zero claims; v2's yields `_resolve_image_urls`, `TOK_PER_SEC`, `9.2` — verified standalone against the §7.2 regexes first) |
| T3d | journeys `needs=` skip counted | `skipped_needs: ["platform-08a-worker-pure"]`, `ok: true` |
| T3e | `import-app` conditional | step present, exit 0, **non-blocking** with `api/app.py` absent (C-1) |
| T4 | digest equality | two independent executions → **identical `LEDGER_DIGEST`**, different `LEDGER_SHA256` |
| T5 | a non-needs journey skip | `skipped_other: 1` → journeys step RED (C-4 the other way) |
| — | `--clean` on a non-detached checkout | correctly refused (`clean-checkout` RED) — the design's own precondition |

Getting to 10/10 required implementing the journeys marker correctly (see V-2) and delivering the card-01 fixture pair — both discovery events are themselves findings (V-2, V-4).

## 2. My own adversarial drive (`scratch/critic-v2/mydrive.mjs`; fresh fakes, fresh assertions, driven against my own `assembled-factory-doc.mjs`)

**28 scenarios, 51 assertions: 50 passed, 1 failed.** The 1 failure is a real defect (V-3). Two additional "OBSERVED" probes document behaviour without pass/fail labels. Full log: `scratch/critic-v2/mydrive-run.log`.

| Scenario | Drives | Assertion(s) | Result |
|---|---|---|---|
| M1 | happy build, 12 cards (plan covering the script's own `MANIFEST_MIN` — my first 6- and 11-card plans were **refused by `checkPlan`**, proving C-14 has teeth) | all merged, satisfied, ready; every merge gate carries `--journeys`; merge gates carry `--boundary-sha256`; verify prompt never contains the builder digest; `rows_consistent` | PASS ×5 |
| M2 | verifier `strongest_disagreement` = "will report back when the run ends" (a phrase still in `RECEIPT_RE`) | CODE: return nulled → card parks `agent-null:verifier`; card not merged | PASS ×2 — **empirical proof of the V-1 prose/code contradiction** |
| M3 | rubber-stamp verifier (schema-valid-but-empty: no hunks, mutants {0,0}, revert-proof green, dod rerun fails) | parked after exactly 2 builds `no-progress`; dependents `dependency-blocked`; no lenses; `tree-incomplete`; next stage build | PASS ×3 |
| M4 | implementer adds a remote at merge | `HALT remote-added`; checkpoint `failed`; **synthesizer ran**; no lenses after HALT | PASS ×4 |
| M5 | overlapping write sets | never one batch; all merge | PASS |
| M6/M6b | budget crosses `RESERVE` mid-wave; then resume | starved cards `not_attempted` (retryable); stage stays build; synth ran; **resume rebuilds without `retry_parked`** | PASS ×3 |
| M7 | resume with changed launch sha | `stale-launch-args`; no card agent; synth ran | PASS |
| M8 | `hf_…` secret in builder `output_tail` | secret in no prompt/log/checkpoint; card blocked `secret-shaped-output`; no fixer | PASS ×2 |
| M9 | final judge returns null twice | `veto-unavailable`; not ready; exactly 2 veto calls | PASS |
| M10 | review finding holds → fix card | `fixcards` wrote `plan/fixes/<id>.json` **before** the author; prompt carries the finding text AND the DoD command; gate uses `--card plan/fixes/…`; fix card merges; final stop satisfied | PASS ×5 |
| M11 | root card parked (verify fails) | dependents `not_attempted:dependency-blocked`; no lenses; `tree-incomplete`; blocked; stage build | PASS ×2 |
| M12 | stage run, confirmed **critical** staging finding (failed canary), `production_space_head` recorded | NO `promote-production`; stop `blocked-on-owner:staging-evidence`; not ready; stage stays stage | PASS ×2 |
| M12b | promote run with the same finding | `rollback` emitted with the finding id; stage pinned at `promote` | PASS |
| M12c | accepted **medium** finding (`owner_approvals.accepted_findings`) | deferred, not blocking; `ready` reachable | PASS |
| M13/M13b | `already-merged` without / with evidence | unevidenced → `integration:already-merged-unproven`, head never jumps; evidenced → `merged`, `already-merged(proven)` | PASS ×2 |
| M14 | verifier digest differs once | fixer prompt carries `digest_mismatch` with `builder_steps`, `verifier_steps`, `steps_only_in_*`; two-strikes at 2 builds | PASS ×2 |
| M15 | journey still skipped after its card merged | synthetic finding logged + queued through refute; fix card on `plan/fixes/` | PASS ×2 |
| M16 | R0 plan cites a REFUTED id | `repair-plan` (never `approve-plan`); `plan_defects` carried; next stage `plan` | PASS |
| M16b | R1 launched with that plan | throws `plan-needs-repair` before any author/builder | PASS — **but the next_args assertion FAILED → V-3** |
| M17/M17b | non-owner card writes a protected path / owner-manifest card does | plan refused (`repair-plan`, defect names the ownership rule); owner-manifest passes | PASS ×2 |
| M18 | `agent()` throws budget ceiling | `HALT budget-exhausted`; synthesizer still ran; no retry fan-out | PASS |
| M19 | smoke mode | one card only; `smoke-skip-review`; not ready | PASS |
| M20 | clean gate red + revert fails | `revert-failed` typed; integration dirty; status `failed`; **probe:** `not_attempted:integration-dirty` matches `RETRYABLE_RE` although its `next` says owner-inspect (V-8) | PASS ×2 |
| M21 | venv missing at setup | run fails loudly; no author launched; synth ran; setup prompt says "NEVER create it" | PASS ×2 |
| M22 | h6 timeout receipt | typed `timeout-or-dialog`; retry once; `next_args.resume_mode = 'git'` | PASS |

## 3. Gaps table

Severity: **blocking** = the run fails or lies as written · **major** = a realistic path produces a wrong outcome, an unrecoverable state, an owner who cannot act, or the document misdescribes a load-bearing mechanism (the authorability equivalent) · **minor** = robustness/cost/cosmetic.

| id | sev | Gap | Evidence (design-v2-final.md) | Concrete fix |
|---|---|---|---|---|
| V-1 | **major** | **The RECEIPT_RE closure is described falsely in three places.** §9 ("v1's `RECEIPT_RE` rule is dropped in v2 (C-23) … a receipt-shaped fragment is now **only logged**"), §12.2 AP-1 ("RECEIPT_RE is dropped … logged only") and §12.7 V-22 say the rule is gone; the §13 code still **nulls** any return whose `notes`/`strongest_disagreement` matches a remaining alternative (`started in the background\|Check /codex:status\|as a follow-up task\|will report back when`). My drive M2 proves it: a verifier writing "will report back when the run ends" parks its card `agent-null:verifier`. The first critic's C-23 fix demanded only "drop that alternative … log the matched fragment" — that was done — but v2's coverage matrix now claims a mechanism that does not exist, and the reviser's drive N10 ("receipt-shaped notes NOT nulled") tests only the removed alternative, so it passes vacuously. A script author following the prose deletes the null; following the code keeps it. | lines 1148, 1284, 1421 (prose) vs lines 1479 + 1627-1628 (code); reviser drive N10 | Decide the behaviour and make prose and code say the same thing. Either (a) keep the null and rewrite the three prose sites to "the offending alternative was dropped; the remaining receipt phrases still null, with the fragment logged", or (b) actually drop the null (keep the log line). Then add a drive assertion for whichever is chosen, tested against a remaining phrase, not the removed one. |
| V-2 | **major** | **The journeys marker mechanism is a name-only spec with two naive dead-end implementations.** §4.8: "`tests/journeys/conftest.py`, which marks everything under `tests/journeys/` with the `journey` marker" — card 01's row says only "(the `journey` marker, C-4)". The two obvious implementations both break gates: (a) `pytestmark = pytest.mark.journey` in a conftest is **inert** (pytestmark is read only from test modules) → `--journeys` collects 0, rc 5 → every merge/clean gate RED once the first journey lands — C-4's failure mode returning through a side door; (b) an unscoped `pytest_collection_modifyitems` in a subdirectory conftest marks **every item in the session** (verified empirically) → `-m "not journey"` deselects the whole default suite → exit 5 → pytest-x2 RED from card 01 onward. Both fail closed but are discovered late (first journeys merge / every card gate) and expensively (revert cycles, parked cards), and S-AP-4 (hollow seams) is back until diagnosed. I only reached 10/10 in my gate dry-run after implementing the correct path-scoped hook. This violates the design's own D-19 ("write the algorithm") for its newest blocking closure. | lines 210, 325, 946, 1732; my dry-run iterations (§1.1) | Pin the exact conftest content in card 01's spec: `def pytest_collection_modifyitems(items):\n for it in items:\n  if it.path.is_relative_to(pathlib.Path(__file__).parent): it.add_marker(pytest.mark.journey)` (or equivalent), plus registering `journey` in `pytest.ini` `markers` (my run also shows a PytestUnknownMarkWarning). Add a card-01 DoD line that runs BOTH collections (`--journeys` over a one-file smoke journey) so an inert or over-scoped marker is caught at card 01, not at the first seam wave. |
| V-3 | **major** | **The R1 plan-repair relaunch is not wired into `next_args`.** When `checkPlan` throws in R1, `stop_reason` = "FAILED:plan-needs-repair: … — relaunch stage=plan with args.plan_defects (C-19)" (correct), but `nextStage` yields `'build'` (not ready) and `next_args.plan_defects` is `[]` (it is populated only for `stage === 'plan'`). The machine-readable contract — the thing §2.2 tells the owner to feed the next launch — contradicts the stop message: an owner following `next_args` relaunches `stage=build` and loops on the same throw, burning setup+index agents per loop. The repair data (the defect list) is also dropped from the args the owner would pass to the REPAIR MODE planner. | lines 2069-2071 (`nextStage`, `plan_defects` gate), 2139-2140 (the throw); my drive M16b | One line each: in `nextStage`, `stop` starting with `FAILED:plan-needs-repair` → `'plan'`; and populate `next_args.plan_defects` whenever `planDefects.length > 0`, regardless of stage. Drive-assert the R1-failure checkpoint's `next_args`. |
| V-4 | minor | **The false-claim fixture delivery is misdescribed.** §2.0 step 3 and §7.3 say the fixture "ships inside gate.sh itself (written to a temp dir by the `--self-test` step)" and V-2 says "the gate writes the fixture itself (patch + target into a temp dir)". The code reads the patch+target from the **repo** (`tests/fixtures/gate/false-claim.patch`, delivered by card 01); only the temp worktree and the crafted commit message are gate-created. Consequence as written: before card 01 delivers the pair, a full-profile `--self-test` reports `fixture-missing` and goes RED (only the bootstrap profile tolerates it) — so "the false-claim red-proof exists before card 01 delivers anything" is false; P0 works only because it runs `--profile bootstrap`. | lines 79, 951, 1401 vs gate lines 905-924 (doc 905-924) | Rewrite the three sentences to "the fixture pair is delivered by card 01; the gate crafts the commit message and the temp worktree; P0's bootstrap-profile run proves `broken_red` live and tolerates `fixture-not-yet-delivered`". No code change needed. |
| V-5 | minor | **The two protected-path lists diverge, so "checked identically in `validateCards` and in the gate" (§7.3) is false at the list level.** JS `PROTECTED` (line 1485) vs the §14 `tests/protected.txt` checklist (line 2213) differ in both directions: only the txt has `tests/fixtures/gate/*`, `tests/fixtures/persona_boundary.json`, root `conftest.py`; only the JS has `tests/protected.txt`, `tools/gate.pin`, `tools/baseline.json`, `tools/baseline.pin`, `.gitignore`, and the two gate-fixture files explicitly. A planner slip that puts a txt-only protected path in a non-owner card's write set passes `validateCards` and surfaces only as a gate RED after a burned chain. Fail-closed, but the "identical" claim is wrong and the failure is late. | lines 1485 vs 2213 | Derive both from one source: define the protected list once (e.g. the JS constant writes `tests/protected.txt` content expectations into the card-01 spec, or the checklist copies the JS array verbatim) and add a §14 item asserting the two are equal. |
| V-6 | minor | **`TIMEOUT` has no `tests` key.** `run('author', 'tests', …)` looks up `TIMEOUT['tests']` → falls back to 30 min, while §10.4/§11 say the author gets 25. The timeout table is role-named ("author 25 min") while the map is mode-keyed; every other mode key exists. | line 1475 vs lines 1174, 1197 | Add `tests: 1500000` to `TIMEOUT` (or key the map by role). Harmless direction (longer timeout), but the doc's numbers should match the code. |
| V-7 | minor | **§2.3's admission claim overstates `agentsOk`.** "a wave is admitted only if every chain in it can finish inside this invocation" — the reservation is 7 agents/chain, but a worst-case chain is ≈ 20 `agent()` calls (2 authors + 2 reds + 3 builds + 3 verifies, each retryable once). Mid-chain starvation degrades correctly (C-8: `not_attempted`, retryable), so nothing is lost but the promise. | lines 119, 1645-1649 | Either raise `RESERVE_PER_CHAIN` to the honest worst case (and re-derive the slice math) or soften the sentence to "a wave is admitted only when 7 agents/chain remain; overrun degrades to typed, retryable starvation". |
| V-8 | minor | **`not_attempted:integration-dirty` is auto-retryable while its `next` says "owner inspects".** The reason matches `RETRYABLE_RE` (`^(not_attempted|starved):`), so resume re-drives automatically — over the `next` text's instruction to inspect a branch whose revert failed. Recoverable (git re-seeds state live), but the reason string and the next-action disagree. | lines 1481, 1900-1902 | Use a reason outside `RETRYABLE_RE` for the dirty case (e.g. `blocked:integration-dirty`) or change `next` to match the auto-retry; keep them consistent. |
| V-9 | minor | **v2's UNVERIFIED list dropped v1's budget-throw-message item.** The no-fan-out HALT still keys on the guessed regex `/budget\|ceiling\|spend/i` over the harness's throw text; if the real message differs, the HALT never fires (degrades to typed starvation — bounded, safe, but the assumption is load-bearing and v1 flagged it; v2's §-header UNVERIFIED list omits it). | line 1664 vs v1-critique §8.18; v2 line 8 | Re-add to the UNVERIFIED list with the noted fallback (per-call `budget.remaining()` guard already bounds it). |
| V-10 | minor | **Cost arithmetic is ~10-15 % optimistic.** Per-card 5.7 agents assumes a lighter fix mix than the design's own numbers imply (5 base + 0.4×2 + 0.15×4 + 0.1×2 + 0.05×1 ≈ 6.65) → R1 ≈ 296 vs "≈ 275", total ≈ 335-350 vs "310-325". Per-wave ≈ 80 min at cap 2 is ≈ 95-100 on the same inputs (serial merges + clean gate + seam-wave journeys). Both fit every cap that matters (`max_agents_this_run` 110 enforced in `budgetOk`; git-mode invocations are separate workflows under the 1000 lifetime cap; §11's own range 240-330 nearly covers it) and §11 marks them UNVERIFIED — but the headline should move to ≈ 335-350 / ≈ 28-29 h at cap 2 so the owner's invocation count (4-6) does not silently become 5-7. | lines 1208-1218 | Re-derive §11 with the honest mix (or state the assumed fix mix explicitly so the reader can re-derive it); keep the caps analysis unchanged. |
| V-11 | minor | **The journeys author's gate result is never JS-verified** (no digest equality on that chain — acceptance is `status === 'SUCCESS' && isSha(tests_head)`), so a journeys author that reports SUCCESS over a RED `journeys-only-tests` step is caught only at the merge gate (one wasted merge+revert). Same class as the C-18 builder-side fix; small because journeys are composition tests behind the merge gate. | line 1925 | Require the journeys author to return the gate's exit code and digest and have JS refuse a nonzero `journeys-only-tests` (cheap; consistent with confirm-RED). |

No document-vs-artifact divergence found (§1) — that check is clean and is recorded as a positive result, not a gap.

## 4. Closure audit (C-1..C-38 → verdict)

Legend: **closed** = mechanism present, exercised by me or provably equivalent, no new hole · **closed\*** = mechanism present and working, but with a V-gap attached (prose contradiction, unspecified sub-mechanism, or residual wiring).

| C-id | v1 severity | Verdict | Basis |
|---|---|---|---|
| C-1 | blocking | **closed** | gate code conditional on `[ -f api/app.py ]` with a non-blocking "not yet a composition root" record — **executed** in my dry-run T3e; card 03b's gate command runs both collections (prompt text §4.2). |
| C-2 | blocking | **closed\*** (V-4) | **executed**: `false_claim_red === "true"` from the inner ledger's `claim-lint` step (dry-run T3c); the fixture message yields 3 claims under the §7.2 regexes (standalone probe). The delivery mechanism is misdescribed in prose (V-4). |
| C-3 | blocking | **closed** | my M10: `fixcards` writes `plan/fixes/<id>.json` before the author; prompt carries the finding text + DoD command; gate invoked with `--card plan/fixes/…`; the fix chain runs through the same inner loop and merges. |
| C-4 | blocking | **closed\*** (V-2) | gate side **executed** (T3d `needs=` counted; T5 non-needs skip RED); marker conftest + `pytest.ini` deselect + `--journeys` on every merge/clean gate (M1) + synthetic blocking finding (M15). The marker's implementation is unspecified with two dead ends (V-2). |
| C-5 | blocking | **closed** | my M3/M11: `readyWave` recomputed from live status; dependents `not_attempted:dependency-blocked`; `tree-incomplete` stops the loop with zero lenses. |
| C-6 | blocking | **closed** | my M12/M12b/M12c: no `promote-production` over a confirmed critical/high finding; stop `blocked-on-owner:staging-evidence`; `rollback` only on confirmed evidence; accepted medium/low carve behaves as §15 Q10 states; `ready` false throughout. |
| C-7 | major | **closed** | my M4/M18: synthesizer ran after `HALT remote-added` and after `budget-exhausted` (`budgetOk(label, exemptFromHalt)`); no retry fan-out. |
| C-8 | major | **closed** | my M6/M6b: starvation → `not_attempted` with a retryable reason; resume auto-retries without `retry_parked`; `retry_parked_suggested` computed in the checkpoint. |
| C-9 | major | **closed** | my M3/M6/M11/M12b: the nextStage table holds (`build→build`, `stage→stage`, `promote→promote`) on every non-satisfied stop. |
| C-10 | major | **closed** | code lines 1975-1980 (review pre-check re-runs one clean gate when the last is not a pass at head) + reviser S7b; consistent with `lastClean` seeding only at the same head (line 2104). |
| C-11 | major | **closed** | three-way typing in `cleanGate` (lines 1861-1869): null / malformed / wrong head / exit-0-contradicted-by-self-test → `gate-unavailable`, never a revert; reviser S6/S6b agree with my code read. |
| C-12 | major | **closed** | `mergeLog` records every merge sha (journeys included); `checkedRevert` targets it and checks the result; `INTEG_DIRTY` on failure (my M20 typed `revert-failed`). |
| C-13 | major | **closed** | `expected_green_tests` enforced both ways in the confirm-red verdict heredoc (an extra green new test is RED, a listed-not-green one is RED); `est_lines` vs size class throws; card 01 is M; `LEDGER_DIFF_STATS` excludes `tools/gate.sh` and `tests/fixtures/` (gate code verified). |
| C-14 | major | **closed** | `MANIFEST_MIN` derived from the cards, `worker/penalty.py` conditional on `args.torch_in_venv`; **my own drive's plans were refused until they covered the manifest** — the check demonstrably has teeth; the four CI filenames are pinned in card 14's manifest. |
| C-15 | major | **closed** | two-tier idiom lint scoped `--lint-base..HEAD`, `tests/` excluded, comments stripped (gate code); `Claim-Waiver` counted per `Card:` trailer. |
| C-16 | major | **closed** | apicheck import-first, ast-parse of wheel source under `--libsrc`, `unresolvable` recorded (surfaced as `api_unresolvable[]`), never RED (gate code lines 670-733). |
| C-17 | major | **closed** | `TOOLCHAIN_STATUS_CMD` excludes `docs/grills` (line 1482); bundles under `/workspaces/space-build-bundles/` with only the manifest in the grill tree. |
| C-18 | major | **closed** | my M14: `digest_mismatch` carries both ledgers' steps and `steps_only_in_*`; the fingerprint is never empty (`\|cond:` suffix) — M3 two-strikes at 2 builds. |
| C-19 | major | **closed\*** (V-3) | my M16/M16b: R0 emits `repair-plan` with `plan_defects`, R1 throws before any author/builder; REPAIR MODE relaunch exists from R0. The R1-failure next_args wiring is V-3. |
| C-20 | major | **closed** | my M13/M13b: unevidenced `already-merged` → `integration:already-merged-unproven`, head never moves; evidenced → `already-merged(proven)`; merged+red → checked revert-now. |
| C-21 | major | **closed** | my M17/M17b (ownership rule both ways at plan time) + M1 (`--boundary-sha256` in every merged-args gate command) + the FIXTURE COPY STEP in the author prompt + card 01 delivering `tools/make_boundary_fixture.py` (in `MANIFEST_MIN`). |
| C-22 | major | **closed** | every row and parked entry in every scenario of my drive carries `reason` + `next`; `blocked_on_owner` rows carry field/why/next/severity. |
| C-23 | minor | **closed\*** (V-1) | the offending alternative was dropped and the fragment is logged — the letter of the demanded fix — but three prose sites claim the whole rule is gone while the code still nulls (V-1). |
| C-24 | minor | **closed** | `byRank` orders both scheduling and integration (line 1912); my M1's wave-2 order matches the reviser's S1 expectation. |
| C-25 | minor | **closed** | ok[10] fails closed on missing `diff_stats` (line 1758); M3 confirms the park path. |
| C-26 | minor | **closed** | `redInfo` carries the verdict, `digest_equal`, failures and checks into the second author attempt (line 1791); reviser N11. |
| C-27 | minor | **closed** | `confirmed` requires `reproduction.exit_code !== 0`; shapeless holds are logged and ignored (lines 1999-2000). |
| C-28 | minor | **closed** | the revert-proof test list includes builder-added `tests/unit/*` from `changed_files` (line 1723). |
| C-29 | minor | **closed** | confirm-RED acceptance requires `red.gate_digest === a.gate_digest` (line 1789). |
| C-30 | minor | **closed** | `P.conflict` says `worktree add --detach` (line 1727). |
| C-31 | minor | **closed** | my M21: the setup prompt asserts the venv EXISTS / NEVER create; the venv is created at P0 only. |
| C-32 | minor | **closed** | the `TESTTOKEN-` dummy-credential convention is in `PREAMBLE` (line 1512). |
| C-33 | minor | **closed** | my M19: smoke → one card, `smoke-skip-review`, not ready. |
| C-34 | minor | **closed** | placeholder `build_info.json` in 03b's manifest; `evidence/catalog/README.md` in 13a's; the four CI filenames in card 14's `MANIFEST_MIN` (verified in the script constants). |
| C-35 | minor | **closed** | `tools/expected.py` in card 14's manifest; §2.1/§8 say CI writes `EXPECTED.json`. |
| C-36 | minor | **closed** | `core/engine.py` in 03a's `MANIFEST_MIN`. |
| C-37 | minor | **closed** | my M22: timeout → `timeout-or-dialog`, one retry, `REPLAY_RISK` forces git; revert reasons typed; the self-test computes its own `st_rc`. |
| C-38 | minor | **closed** | my M18 log shows the skip line; code line 1928 (nothing merged + last clean pass at head → skip, logged). |

**Tally: 38/38 closed in mechanism (0 declines, 0 partials); 4 carry an attached V-gap (C-2→V-4, C-4→V-2, C-19→V-3, C-23→V-1).**

## 5. Loop and termination audit

| Loop | Exit set | Bound | Spin / early-exit / mislabel? |
|---|---|---|---|
| `run()` attempts | ok · `null:budget\|halt\|agent-slice` · drop→1 narrower retry→`agent-null` · assertCommon nulls (wrong-repo, wrong-store, outward→HALT, installs, receipt-shaped) | 2 | No spin. The receipt-shaped null (V-1) is conservative, parks retryable. |
| Author loop | pass(+digest equality) · starved · `agent-null:*` · `author-no-commit` · `tests-not-red` | 2 | Bounded; the second attempt is informed (C-26). |
| Build/fix loop | built · starved · `agent-null:builder` · `no-commits` · `secret-shaped-output` · `no-progress` · `oscillation` · `fix-exhausted` | 3 | Bounded; two-strikes has teeth (fingerprint never empty — M3/M14). |
| Wave loop | plan exhausted · `integration-dirty` · halt · agent-slice/budget | ≤ cards | Every wave card receives a status each iteration (starved/built/parked/dropped or stale→re-drive once→status), so `readyWave` strictly shrinks — **cannot spin**; verified across 28 scenarios. |
| Review loop | `satisfied` · `halt:*` · `integration-dirty` · `max-rounds(3)` · `dry(2)` · `budget-or-agent-cap` · `veto-unavailable` · `clean-gate-red/unavailable` (pre-check) · `tree-incomplete` (pre-check) · `blocked-on-owner:staging-evidence` | 3 rounds | Bounded. `satisfied` is checked BEFORE `dry`, so a dry counter never mislabels a satisfiable tree. A confirmed high/critical local finding whose fix card parks keeps `satisfied()` false (openBlocking) → ends `max-rounds`/`dry`, visible as a parked row — bounded and reported (unchanged soft spot, acceptable). |
| Plan stage | `plan-verified` · `plan-needs-repair` · throw | 1 | No spin; the repair relaunch from R1 is V-3. |
| Invocation chain | C-9 nextStage table | owner | Never advances past an unfinished stage (M3/M6/M11/M12/M12b). |
| Gate internals | for-loops only; the self-test's inner call runs with `CLAIM_ONLY=1` and finishes before the self-test block | — | No recursion beyond one level. |

No loop exits with a success label after a typed failure in any scenario I ran or constructed.

## 6. Authorability

Could the script author implement v2 without guessing? Mostly yes — the §13 text is the exact script and the artifacts match it byte-for-byte. The guessing points that remain:

1. **V-1** — does "RECEIPT_RE dropped, only logged" mean delete the null or keep it? The code and the prose disagree.
2. **V-2** — the journeys conftest: no algorithm given, and the two natural readings are both wrong (inert `pytestmark`; over-scoped hook).
3. **V-3** — an R1 `plan-needs-repair` checkpoint whose `next_args` contradicts its own `stop_reason`.
4. **V-4** — "the fixture ships inside gate.sh" vs code that reads it from the repo: which is intended?
5. **V-5** — two protected lists that differ; which one is law?
6. **V-6** — author timeout 25 (prose) vs 30 (code fallback).
7. **V-7** — "every chain can finish inside this invocation" vs a 7-agent reservation.
8. **V-9** — the budget-throw-message regex is a guess that v2's UNVERIFIED list no longer records.

UNVERIFIED facts without fallback: none new — every remaining UNVERIFIED item (timers, cache key, schema keywords already removed, replays-vs-cap assumed counting, wall-clock, idle timeouts, permission-prompt surfacing, Q2/Q3/C-16 wheel layout) carries either a mechanism that does not depend on it or a typed degradation, except V-9's regex, which degrades safely but silently.

## 7. Cost realism

- Re-derived per-card ≈ 6.65 agents (5 base + the design's own fix mix) vs the stated 5.7 → R1 ≈ 296, total ≈ 335-350 vs the stated 310-325 (V-10). Inside every hard limit that matters.
- Per-invocation ≤ 110: enforced in code (`budgetOk`'s `Math.min(AGENT_SOFT_CAP, MAX_AGENTS_RUN)` check applies to everything, synthesizer included — only the HALT/reserve branches are exempt). At 110/invocation the total implies 3-4 build invocations, plus owner stops — consistent with §11's 4-6.
- Lifetime 1000: git-mode invocations are separate workflow runs; even cache-mode replays counted, 4-5 × 110 ≪ 1000. Holds.
- Wall-clock: cap 2 ≈ 28-29 h on my re-derivation (wave ≈ 95-100 min, not 80) — still marked UNVERIFIED by the design itself; the owner-visible consequence is one extra invocation at cap 2 (V-10).
- Resume plan hold: `stale-launch-args` (M7), git-seeded merged set, retryable-park auto-retry (M6b), `last_clean_gate` seeded only at the same head — all verified.

## 8. What v2 gets right (for the record)

All six v1 blocking defects are genuinely dead: I executed the conditional `import-app` (C-1), executed a real `false_claim_red=true` (C-2), drove the fix-card chain end to end with file, content and gate wiring (C-3), counted `needs=` skips and red'd a non-needs skip in a real gate run (C-4), watched a parked root starve its dependents and stop the lenses (C-5), and watched a confirmed critical staging finding suppress `promote-production` and flip R3 to `rollback` while pinning the stage (C-6). The synthesizer-after-HALT exemption, the starvation/retryable-park split, the `already-merged` evidence rule, the merge-sha revert discipline, the ownership rule at plan time, the manifest-as-plan check (it refused my own stub plans), the digest-mismatch fixer payload and the twelve-condition `taskDone` all behave as described in my independent drive. The document-vs-artifacts identity is exact, and the reviser's 98/98 claim reproduces.

## 9. Final verdict

**`revise`** — 0 blocking, 3 major (V-1, V-2, V-3), 9 minor. All three majors are documentation/wiring defects, each fixable in under ten lines without touching the architecture: make the RECEIPT_RE prose match the code (or vice versa) and test a remaining phrase; pin the journeys-marker conftest content and add a card-01 both-collections DoD line; wire the R1 plan-repair relaunch into `next_args`. With those three applied (and ideally V-4/V-5's sentences), v2 is ready to be the build standard.

*Scratch artifacts: `scratch/critic-v2/{gate-doc.sh, schemas-doc.js, script-body-doc.js, assembled-factory-doc.mjs, assembled-iife-doc.js, schemas-mod.mjs, mydrive.mjs, mydrive-run.log, mydryrun.sh, myvenv/, myrealvenv/}` — every number in this critique is re-derivable from them.*
