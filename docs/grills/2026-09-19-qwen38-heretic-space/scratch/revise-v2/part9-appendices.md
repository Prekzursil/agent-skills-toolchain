---

## Appendix A: judge work-list resolution

Every item from the three judgements, mapped to the section that resolves it or to a one-line reasoned decline. "§" references are into this document. **A.1-A.5 are carried from v1 verbatim** (the judges' reports remain the standard for anything the critic did not mention); where the critic's §4 audit of this table found a v1 closure deficient, the fix is recorded in A.0 and its gap id points into Appendix B.

### A.0 The v2 audit of this work-list (what the reviser re-verified against the critic's audit)

| Audit finding (critic §4) | v2 closure |
|---|---|
| J1 A3-4 closure "half-real" (the F-11/F-10 rows were prose in v1's stage flow) | `checkPlan()` now executes in every stage (C-19: REFUTED-id and manifest checks throw in R0 **and** R1; drive S17/S17b/S17c), and the idiom clearance stays a `taskDone()` condition fed by the gate's `IDIOM_HITS` |
| J1 G13 "real except after HALT" | C-7: `budgetOk(label, exemptFromHalt)` — the synthesizer runs after every HALT (drive S4/S8c) |
| J1 G2 decline "stands, but resume holes remain" | C-8/C-10/C-22: retryable parks auto-retry on resume, a clean gate is re-run before reviewing when the last one is not a pass at head, and every row carries reason + next (drive N5/S7b/N6) |
| J1 G7 "the prose was real, the mechanism dead" (journeys) | C-4: a separate pytest collection, default-deselected, `--journeys` at every merge + clean gate, `needs=` counted by the gate (drive S16/N1) |
| J1 CG9/CG10 "real but contradictory" (floors vs plan) | C-14: the manifest is derived from the cards (`new_modules ∪ required_files`), `worker/penalty.py` conditional on `args.torch_in_venv`; `validateCards` checks plan-vs-manifest coverage |
| J1 CG6 decline "stands" | unchanged (digest equality is the cross-check); not re-litigated |
| J2 A3-1 (journeys branch mismatch) | C-4 mechanics: `taskBranch()` retained and the journeys merge gate carries `--journeys` (drive S1 asserts every merge gate command has it) |
| J2 A3-2 (clean-gate null → revert) | C-11: three-way typing; a null/malformed/contradicted return is `gate-unavailable`, never a revert (drive S6/S6b/N2) |
| J2 A3-4 (R2/R3 `satisfied()` unreachable / promote from failed) | C-6 + C-10: `lastClean` seeded only at the same head, evidence findings through the loop, `ready` false over confirmed critical/high (drive S15/N8) |
| J2 gap 8 (budget throw) | C-7 again: no fan-out of instant throws, but the synthesizer still runs |
| J2 gap 12 (unchecked revert) | C-12: the revert targets the recorded `merge_sha` and its result is checked (drive N3/N4) |
| J2 graft 3 (rankCards) | C-24: the same `(−rank, id)` key orders integration, not just waves (drive S1 asserts wave 2 = [03a, 02] by rank) |
| J2 graft 15 (validateCards) | extended per C-13/C-14/C-21: size classes, manifest coverage, ownership rule, `expected_green_tests`, bootstrap-false |
| J2 graft 6 decline (timing) | stands: returns stay timestamp-free; the orchestrator computes durations from the run record after the run |
| J1 D5/G-15(5) "the §C DoD regex is weak" | noted; the §C greps stay plan-verifier-checked (C-19 re-checks them), and the idiom lint's v2 scoping (C-15: `--lint-base..HEAD`, comments stripped) stops it firing on legitimate lines such as a quoted `continue_final_message` in prose |
| J3 Continue-clar "the blocking idiom fires on legitimate lines" | C-15: comment stripping + range scoping; the blocking regex still fires on real call sites |
| J3/C-Q "the boundary tool was unowned" | C-21: card 01 delivers `tools/make_boundary_fixture.py`; the owner records `persona_boundary_fixture_path` AND its sha256; the gate pins it |
| J3 CG-31 "the `/healthz` sha source was ambiguous pre-CI" | C-34: card 03b ships a placeholder `build_info.json` (`git_sha: "unknown"` — rejected by the canary), CI writes the real one |
| A.5's v1 rows "real but unproven" | each is now drive-checked; A.5 below gains the three defects the v2 drive caught in my own drafts |
| "the v1 drive's 19 assertions are not auditable" | the v2 drive (`drive.mjs`, 37 scenarios, 98 assertions) and its full log live beside the design in the scratch dir and are re-runnable (`node drive.mjs`); Appendix C lists every scenario and every annotation |

### A.1 Judge J1 (red-team)

**Blocking defects in A3 (J1 §2)**

| # | Item | Resolution |
|---|---|---|
| A3-1 | `assertCommon` nulls every worktree agent (`repo_toplevel === R`) | §10.5 / §13 `assertCommon`: prefix test `startsWith(R + '-wt/')` plus `git_common_dir === R/.git` (the store identity, so a worktree of another repo cannot pass); the drive exercises a `-wt/x` toplevel on every return. |
| A3-2 | test-count and skip floors inert or spuriously red (`.gate/base.json` only in the main checkout) | §7.2 `--baseline <path> --baseline-sha256`, mandatory in full mode, fail closed; skip rule became a SET rule vs `baseline.skipped_ids` and `xfail_allowed`; `except: base = {0,0}` deleted. Dry run: tampered baseline → RED. |
| A3-3 | mutants optional | §7.2 `--mutants`: written ≥ 1, all applied, all killed, tree unchanged; §5 condition 6. |
| A3-4 | F-11 and F-10 rows prose | §1.4/§2.1/§13: `pipeline(unverified_finding_ids, verifier mode:'preverify')` before the planner; REFUTED ids refused in JS (v2: `checkPlan()` in every stage, C-19); `IDIOM_HITS` in the ledger + condition 9; `corrected_text` required per cited finding. |
| A3-5 | stale re-drive replays the stale result | §4.4/§13 `redriveLine(k)` on every prompt of a re-driven chain (`buildTask(c, head, merged, 1)`). |
| A3-6 (minor) | external gate copy unpinned; `judged.filter(Boolean)` unlogged; on-disk RUN-REPORT not rewritten; `pgrep -f "python.*$REPO"` inert | CG-1 pin (+ `tools/gate.pin`); §13 `judgeDrops` log line; `synthesizer mode:'fix'` rewrite (F-40); kill scoped to `/proc/<pid>/cwd == $REPO` (CG-2). |

**Adversarial constructions (J1 §3), status now:** (a) ship the f88b120 pattern — the optional-mutant hole is closed (condition 6) and the oracle reset makes the author's suite the one that runs; (b) fix-loop spin — unchanged (cannot spin); the soft spot "a parked fix card keeps `satisfied()` false until max-rounds" is bounded and now also visible in the checkpoint as a parked row with reason + next; (c) leak a secret — closed at the gate and in every structured return (`redact()`, condition 11; v2: the `TESTTOKEN-` dummy convention, C-32); (d) outward action — `HALT` (works inside barriers), `git remote -v` post-checks, owner Hub checks (**O**), and the synthesizer still reports after the HALT (C-7); (e) drop a null — honoured everywhere, including the clean gate (three-way typed, C-11), the veto judge and the evidence reader; (f) stale cache — resume modes + `stale-launch-args` + `redrive:` suffix, and prior rows are detail, never truth (C-8).

**Graft list (J1 §6)**

| # | Graft | Resolution |
|---|---|---|
| G1 | A1 canonical digest + two-execution equality | §7 (digest over the timestamp-free canon; dry-run verified) + §5 condition 3 + confirm-RED equality (C-29). |
| G2 | A1 state probe before consuming any cached sha | **Applied as one live probe per invocation, not two agents per card** (§1.2, §1.4, §2.3, §10.1): a per-card probe replays from the same cache it would check; the setup probe carries `launched_at` in `git` mode, returns live heads/merged ids/remotes, and JS refuses a stale launch sha. |
| G3 | A1 oracle reset diffed against the oracle, not the base; tamper-scan idioms | §7.2 step 4 (`--oracle`) + author-range tamper rules in `--only-tests` + builder-test tamper idioms in step 8. |
| G4 | every acceptance id exit 0 on both sides; mutants exist and all die; negative control red | §5 conditions 6, 7, 8 (`dod_reruns[]`, `--revert-proof`; v2: the test set includes builder-added `tests/unit/*`, C-28). |
| G5 | pre-verifier pipeline over UNVERIFIED findings | §2.1 R0, §13 main (plan stage). |
| G6 | JS keyword raise of `verification_level` | §13 `raiseLevels()` in `validateCards` and on every returned finding/DoD line. |
| G7 | held-out seams H1-H7 as the journeys spec | §4.8; `JOURNEY_NEEDS`; journeys author per seam wave; v2: the separate collection + gate counting (C-4). |
| G8 | A2 `semantic()` extras | §5 conditions 5, 8, 10; receipts logged not nulled (C-23); `veto` needs a reproduction (§6.2; v2: non-zero-exit, C-27). |
| G9 | recorded `--profile bootstrap`, rejected for non-bootstrap cards | §7.2 (`profile` in the ledger and the digest) + condition 4 + `validateCards` (`bootstrap` false on every card). |
| G10 | gate integrity extended with `args.gate_sha256` | CG-1: the gate self-checks; `gate_sha256_observed` compared in `taskDone()`/`mergeOk()`; the integrity step compares the repo copy to the pin and `tools/gate.pin` exists. |
| G11 | `maxAgentsThisRun` slices + chain-level reservation | §2.3, §13 `agentsOk(label, need)` with `RESERVE_PER_CHAIN = 7`; v2: sliced cards are `not_attempted`, auto-retried (C-8). |
| G12 | confirm-RED failure-class recording | §7.2 `--only-tests` records `classes=` in the ledger summary; rc 1/2 only count. |
| G13 | synthesis verifier as a file-rewriting probe | §13 `synthesizer mode:'fix'` when rows differ; `rows_consistent` in the checkpoint; runs after every HALT (C-7). |
| G14 | idiom-warning clearance in JS | condition 9 (`warnings_cleared.length ≥ idiom_hits`), over the v2-scoped lint (C-15). |
| D1 | prefix test / common dir | done (A3-1). |
| D2 | baseline from args, fail closed; distinguish xfails in new files | done (A3-2; `xfail_allowed` per card; set rule). |
| D3 | real `P.revert` | §13 `P.revert(id, head, mergedIds)`; result checked (CG-24); v2: targets the recorded `merge_sha` (C-12). |
| D4 | `attempt` suffix on stale/author re-drives; mutants mandatory | done; v2: the author re-drive carries the red verdict (C-26, drive N11). |
| D5 | log `judged.filter(Boolean)`; clean-gate toolchain check in JS | done (`judgeDrops`; toolchain mismatch → `HALT`, `docs/grills` excluded, C-17). |
| D6 | consider dropping the per-wave journeys author | **Partially taken:** the author runs only for waves in which a seam card merged (≈ 6-8 per R1), not per wave. |

**Common gaps (J1 §7):** CG1 → CG-1; CG2 → CG-2; CG3 → CG-3; CG4 → CG-4; CG5 → CG-5; CG6 → CG-6 (declined as an agent, covered by digest equality); CG7 → CG-7; CG8 → CG-8; CG9 → CG-9; CG10 → CG-10 (v2: the manifest is the plan, C-14); CG11 → CG-11; CG12 → CG-12.

**Per-row ◐ verdicts on A3 (J1 §8) now closed:** F-8 (apicheck also runs on the builder's `apis_used` as the separate `apicheck-extended` entry, every entry needs a `ledger_ref` — condition 12; v2: wheel-SOURCE resolution, C-16); F-13 (condition 10, fail-closed, C-25); F-20 (fixture #1 precondition; mutants mandatory); F-26 (scoped kill); F-37 (`raiseLevels` in JS); F-43 (resume modes; v2: retryable parks auto-retry, C-8); F-47 (journeys branch unified; the 98-assertion drive); D/AP-1 (receipts logged, not nulled, C-23); T/AP-11 (drops counted, `fixcards-unavailable` included).

### A.2 Judge J2 (tool contract)

**Contract-violation table for A3 (J2 §1b), rows that were ◐/✗**

| Row | Resolution |
|---|---|
| schemas: `pattern/maxLength/minLength/minimum/maximum` UNVERIFIED | §9: removed; JS enforcement; CG-17. |
| `log()` silent spots (`dropped_null` chains; journeys merge failure) | §13: both logged with counts/reasons (v2: `fixcards-unavailable` typed and logged, C-3). |
| journeys branch mismatch | §13 `taskBranch()` used by the journeys author and the integrator; v2: `--journeys` on the merge gate (C-4). |
| stale re-drive identical prompts | `redriveLine`. |
| fail-closed on dropped verdict agents (clean-gate null → revert; veto null fail-open; confirm-RED null misattributed to the author) | §4.5/§6.2/§13: `gate-unavailable` without revert (three-way typing, C-11); `veto-unavailable`; a red-verifier null is `agent-null:red`, not an author re-drive — and an author re-drive now carries the red verdict (C-26). |
| R2/R3 `satisfied()` unreachable; `promote-production` emitted with `status:'failed'` | §6.2: `lastClean` seeded from `args.last_clean_gate` only at the same head (C-10); evidence findings routed through the loop with the C-6 stop; §2.2 `promote-production` only from `ready` + F-38 field; drive S15/N8 asserts both. |
| `NEED` incomplete | §13 `NEED_ALL` + `NEED_BY_STAGE`, every interpolated arg listed. |

**Blocking defects (J2 §3, A3 1-5):** 1 journeys → `taskBranch` (+ C-4); 2 clean-gate null → `gate-unavailable` (C-11); 3 veto null → `veto-unavailable`; 4 R2/R3 → §6.2 (+ C-6); 5 stale re-drive + `NEED` → done.

**Graft list (J2 §6)**

| # | Graft | Resolution |
|---|---|---|
| 1 | A2 gate steps 13-15 (`--journeys` with `needs=`, gate integrity, `--self-test` on every clean gate) | §7.2; `P.clean` passes `--clean --self-test --journeys`; v2: `--journeys` also on every merge gate and `needs=` counted by the gate itself (C-4). |
| 2 | `semantic()` + `STAGING_RE` level forcing in JS | conditions 5/8/10; `raiseLevels()`; receipts logged (C-23). |
| 3 | `rankCards` longest-path ordering inside barrier waves | §4.3, §13 `rankCards`/`waves`; v2: the same key orders integration (C-24) and `readyWave()` is recomputed live (C-5). |
| 4 | R0 grounding trio | §2.1 R0, §13 plan stage (`parallel([apiLedger, catalog, pipeline(preverify)])`). |
| 5 | cache-key settling experiment + `maxAgentsThisRun` slicing | §2.0 step 8, §2.3, §10.1. |
| 6 | `t_start`/`t_end` timing + waste ratio | **Declined:** the returns carry no timestamps by design (T-AP-9); the orchestrator computes per-role durations from the run record's `queuedAt/startedAt` after the run (research-2 §1.4) and writes `timing-<nonce>.json` outside the script — same data, no volatile prompt content. |
| 7 | incremental bundles `<prev>..HEAD` | §4.4/§13 `P.merge` (v2: outside the grill tree, C-17). |
| 8 | `fingerprint()` sha normalisation | §13 `fingerprint` (`[0-9a-f]{7,40}` → `SHA`) — v2: never empty (C-18). |
| 9 | A1 digest + condition 4 | done (G1). |
| 10 | locked-oracle reset + tamper idioms | done (G3). |
| 11 | `revert_proof` + `negative_control` | done (G4; every mutant is a negative control; test set includes `tests/unit/*`, C-28). |
| 12 | `probesUsed` to the inversion mandate | §6.2/§13 (`probes_used[]` on review/veto returns; `P.veto(..., probes)`). |
| 13 | fail-closed judging | `veto-unavailable`. |
| 14 | H1-H7 as the journeys spec | §4.8 (v2 mechanics, C-4). |
| 15 | `validateCards` throwing at script start | §13 `validateCards` (ids, steps, DoD shape and flags, size classes C-13, manifest-vs-plan coverage C-14, ownership rule C-21, `bootstrap` false, `corrected_text`, security DoD line, level raise, topo). |

**Drop-or-fix list (J2 §6):** journeys branch name ✓; clean-gate null ✓ (C-11); veto null ✓; R2/R3 `satisfied()` ✓ (C-6/C-10); `attempt` suffix / `dropped_null` log / `NEED` ✓; `P.revert` ✓ (C-12); `withTimeout` kept with timeouts sized from queue depth (`tmo()`) and a replay-divergence marker (`REPLAY_RISK`) ✓.

**Common gaps (J2 §7):** 1 → CG-13; 2 → CG-14; 3 → CG-15; 4 → CG-16; 5 → CG-17; 6 → CG-18; 7 → CG-19; 8 → CG-20; 9 → CG-21; 10 → CG-22; 11 → CG-23; 12 → CG-24 (v2: merge_sha, C-12).

### A.3 Judge J3 (program fit)

**Blocking defects (J3 §3, A3 1-5)**

| # | Item | Resolution |
|---|---|---|
| 1 | F-11 guard only in the matrix | pre-verifier pipeline (G5); v2: re-checked every stage (C-19). |
| 2 | G-15 point (5) missing | §4.0 row G-15+G-24 (verbatim), card 05a DoD line + `tests/test_python_eval_surfaces.py` (protected, in the manifest), seam H4, `validateCards` requires a surface/operator-flag DoD line on every `risk:'security'` card. |
| 3 | Continue via chat template contradicts gpu-lease-3/critic-4 | §4.0 `Continue-clar`; card 08a token-level control record + `prefix_ids` + CPU test; seam H1; `continue_final_message=…(think|reasoning)` is a blocking idiom — v2: scoped so it no longer fires on legitimate prose (C-15); critic-4 is pre-verified in R0. |
| 4 | VLM class never stated | §4.0 `G-16-clar`; cards 08b/08c; R0 `has_visual_tensors`; gate catalog step; `prefill_chunk_size` blocking; C0-4/C1-6 decision; §15 Q7. |
| 5 | G-3 never named; Q4 defers the API lane | §1.3 C-N: Q4 deleted; G-3 in the sheet with `against_recommendation: true`; cards 07/11/12/13a/14 stay in R1. |

**Graft list (J3 §7)**

| # | Graft | Resolution |
|---|---|---|
| 1 | A2 §4a decision sheet in the design with A1's `against_recommendation`/`dq_line` | §4.0; JS asserts the five marks — v2 in every stage (C-19); `verifier mode:'plan'` refutes rows vs the DQ lines. |
| 2 | card table with CORRECTED ids + ship-but-flag list with pin rows | §4.2, §4.6 (v2: the pins are green inside card 01 via the `config.py` skeleton, C-13). |
| 3 | gate steps 14-15 + scan of the gate's own logs | §7.2 (integrity + self-test; v2: `tools/gate.pin`, the gate-written fixture, C-2). |
| 4 | apicheck known-bad list + `STAGING_RE` at return time | §7.2 step 3 reads `plan/api-ledger.json.known_bad[]`; `raiseLevels()`; v2: wheel-SOURCE resolution + `unresolvable-needs-torch` (C-16). |
| 5 | R0 catalog-provenance agent saving raw Hub reads | `verifier mode:'catalog'` (§13), `evidence/catalog/*.json` — v2 also copied into the repo by card 13a (C-34), `unresolved` after 3 tries. |
| 6 | `maxAgentsThisRun` + timing instrumentation | slicing ✓ (v2: sliced cards retryable, C-8); timing computed by the orchestrator from the run record (see J2 graft 6). |
| 7 | timestamp-free digest | done. |
| 8 | H1-H7 as journeys | done (v2: the separate collection, C-4). |
| 9 | pre-verifier | done (C-19). |
| 10 | VLM-class statement + Q6 as a worker-card precondition | done (blocking 4; §15 Q7). |
| 11 | locked-oracle reset + assertion-loss detection | done (G3; builder-added tests with skip/xfail/`except: pass` → RED; revert-proof includes them, C-28). |
| 12 | canary contract with the visibility tripwire | §2.1 (R2/R3 paragraph), §8 `EXPECTED.json` (v2: from `tools/expected.py`, written by CI, C-35), card 14, S-AP-12. |

**Drop-or-repair list (J3 §7):** `P.revert` ✓ (C-12); Q4 deleted (C-N) ✓; G-15 (5) verbatim in card 05a ✓; F-11 code ✓ (C-19); chat-template resume replaced by the token-level control record ✓.

**Common gaps (J3 §8):** 1 → CG-25 (C-O; §15 Q4); 2 → CG-26; 3 → CG-27 (C-S; §15 Q2; v2: wired into MANIFEST_MIN, C-14); 4 → CG-28 (§4.7; v2 re-checked every stage, C-19); 5 → CG-29 (C-Q; v2: C-21); 6 → CG-30 (C-M; v2: field/why/next on the row, C-22); 7 → CG-31 (v2: placeholder build_info.json, C-34); 8 → CG-32 (C-P; §15 Q9); 9 → CG-33; 10 → CG-34 (§15 Q6). J3 §2's shared soft spot (the local row for `backends/worker` is thin): the fake-worker conformance row and seam H1 on the fake worker are the local proof; the queue/`x-ip-token` identity trap under M-2 is a `staging-required` row of card 08b (H2 covers the `/v1` side locally).

### A.4 Declined items (all of them, with the reason)

| Item | Reason |
|---|---|
| J1 G2 / work-list "state probe before/after each card" as agents | A per-card probe is issued with the same prompt on every resume and therefore replays from the cache it is supposed to check; under a positional cache a live probe early in the sequence would also invalidate everything after it. Folded into one live setup probe per invocation + JS checks + `missing-ref` re-drives (§10.1); the resume holes the critic flagged are closed by C-8/C-10/C-22 instead. |
| J1 CG6 "bash ledger reader" probe | It would re-read a file written by the agent under test; the two-execution digest equality (§5 condition 3) is the independent signal. |
| J2/J3 `t_start`/`t_end` in every return + waste ratio inside the script | Timestamps in returns are volatile prompt content (T-AP-9); the same numbers come from the run record after the run, computed by the orchestrator. |
| J1 D6 drop the journeys author entirely | Kept, but only on seam waves (≈ 6-8 per R1); S-AP-4 needs the seams written after the wave. |
| Separate refuter panel, auditor, critic, judge panel, per-wave LLM review, transcript monitor, `mutmut`, hidden branch ACL, `isolation:'worktree'`, plan-critic role, inversion scout, cross-vendor judge (A3 §1.4 cuts) | Unchanged; no judge asked for them back; §1.4 names the covering mechanism for each — and the v2 additions (fixcards, `checkPlan`, the drive) are mechanisms inside the existing six roles and one gate, not new scaffolding. |

### A.5 Defects found by the synthesizer's own checks (not in any judge list)

| Found by | Defect | Fix |
|---|---|---|
| fake drive | `checkpoint.status === 'ready'` while cards were `blocked_on_owner` | `complete` predicate (§2.2). |
| reading the tool contract | an outward-action `throw` inside a `parallel`/`pipeline` thunk resolves to `null` and never aborts | `HALT` flag consulted by `budgetOk()` (§10.5). |
| reading the prompts | cards lived on `plan/<nonce>`, but gates read `plan/cards/<id>.json` from worktrees that did not contain it | setup merges the plan branch into `integration/<nonce>`; `plan/` immutable during a run (gate step 8). |
| fake drive (stage) | the merged set on a fresh invocation came only from a status file | `merged_on_integration` from `git ls-tree` seeds `status`; the file adds detail. |
| gate dry-run design | the self-test's inner run went RED for a missing baseline, making `false_claim_red` vacuous | pins passed to the inner run; the RED must come from the `claim-lint` step (verified from the inner ledger). |
| v2 drive | the gate's protected-ownership rule and `validateCards` disagreed on who may write a protected path (a card with the file in its manifest failed validation) | one ownership rule in both: a protected hit is legal iff the path is in the card's own manifest (`MANIFEST_MIN[id]`) or the card carries `protected_touch` (C-21). |
| v2 drive | the synthesizer was skipped whenever `HALT` was set or the budget was exhausted — the reserve existed but could not be spent on it (C-7/F-45) | `budgetOk(label, exemptFromHalt)`: the exempt caller returns true after the agent-cap check, so the report is always written (drive S4/S8c). |
| v2 drive | a not-ready `promote` run advanced `next_args.stage` to `done` — the C-9 violation in my own first draft | `nextStage`: `(ready ? 'done' : 'promote')` — a stage that did not finish never advances (drive N8/S15). |

---

## Appendix B: Changes in v2 — every critic gap mapped to its resolution (C-1..C-38; 0 declines)

| id | Sev | Gap (critic) | Resolved in |
|---|---|---|---|
| C-1 | blocking | `import-app` RED by construction (card 03b owns `api/app.py`; every earlier card's gate red) | §7.1/§7.3: the step is conditional on `[ -f api/app.py ]`; §4.2 card 03b ships the placeholder `build_info.json` and its own gate command runs both collections; dry-run + drive S1/N2 |
| C-2 | blocking | the self-test's false-claim fixture produced zero claims (vacuous red) | §7.3: the gate writes the fixture itself, its commit message matches the claim-lint regexes, the patch does not change the symbol; `false_claim_red === 'true'` asserted from the inner ledger; dry-run |
| C-3 | blocking | review fix cards were in-memory; `cardRef` named a file nobody wrote; prompts lacked the finding and DoD | §3 (`fixcards` mode), §4.1 (`path`), §4.4, §5/§6 (`toFixCard` → `plan/fixes/`, prompts carry content verbatim); drive S12/N1 |
| C-4 | blocking | journeys collected by the default suite; `needs=` skips RED vs baseline; merge gates lacked `--journeys` | §4.8 (marker conftest + deselect), §7.1/§7.3 (`--journeys` everywhere, `skipped_other`); drive S16/N1 |
| C-5 | blocking | the DAG was asserted only at plan time; dependents of parked roots got built; lenses spent on incomplete trees | §4.3 (`readyWave()` from live status), §6.2 (`tree-incomplete` pre-check); drive S13/N5/N12 |
| C-6 | blocking | R2/R3 emitted `ready`/`promote-production` over confirmed critical/high staging findings | §2.1/§6.2 (`ownerCritical === 0`, `blocked-on-owner:staging-evidence`, rollback on confirmed evidence only); §15 Q10; drive S15/N8 |
| C-7 | major | the synthesizer never ran after HALT | §10.2/§13: `budgetOk(label, exemptFromHalt)`; drive S4/S8c |
| C-8 | major | starvation became permanent parks; rows carried no reasons | §2.3/§10.1 (`starved` → `not_attempted`, `RETRYABLE_RE` auto-retry, `retry_parked_suggested`); §2.2; drive N5/N6 |
| C-9 | major | `next_args.stage` advanced after dry/budget/halt stops | §2.2/§13 nextStage table; drive S7/N7/N8/S8 |
| C-10 | major | no clean-gate re-run when the last was not a pass at head | §6.2 pre-check; §2.1 seeding only at the same head; drive S7b/N3 |
| C-11 | major | malformed clean-gate returns reverted good merges | §4.5/§10.2 three-way typing (incl. exit 0 contradicted by the self-test); drive S6/S6b/N2 |
| C-12 | major | reverts targeted HEAD (wrong after a journeys merge) | §4.4/§4.5: `merge_sha` recorded and targeted, result checked; drive N3/N4 |
| C-13 | major | card 01 could not satisfy its own gate | §4.1/§4.2/§4.6: `expected_green_tests` both ways, `config.py` skeleton, size M, `LEDGER_DIFF_STATS` exclusions; dry-run |
| C-14 | major | `REQUIRED_AFTER` contradicted the plan | §4.1/§13: `MANIFEST_MIN` derived from the cards, conditional on `args.torch_in_venv`; §2.0/§14 |
| C-15 | major | the idiom lint re-scanned all history | §7.1/§7.3: two tiers over `--lint-base..HEAD`, `tests/` excluded, comments stripped |
| C-16 | major | apicheck went RED on symbols it could not resolve without torch | §7.1/§7.3/§8: import-first, else ast of the wheel SOURCE; `unresolvable-needs-torch` never RED; `api_unresolvable[]` |
| C-17 | major | the toolchain-status HALT fired on the owner's grill syncs | §2.0/§2.4/§10.5: exclude `docs/grills`; bundles outside the grill tree |
| C-18 | major | digest equality fragile; fingerprints could be empty | §5/§7.1: gate LAST on the committed tree, `apicheck-extended` separate, `digest_mismatch` with both ledgers, never-empty fingerprint; drive S2/S3 |
| C-19 | major | plan checks ran only in R0 | §2.1/§13: `checkPlan()` every stage, `repair-plan`, REPAIR MODE; drive S17/S17b/S17c |
| C-20 | major | `already-merged` bypassed every check | §4.5: evidence else `already-merged-unproven`; merged + red → revert-now; drive S14/N9 |
| C-21 | major | the persona pipeline was incomplete | §4.2 card 01 (generator), §3/§4.4 (FIXTURE COPY STEP), §7.1 (`--boundary-sha256`), §4.0 (owner sha field), the ownership rule; §14 |
| C-22 | major | checkpoint rows carried no reason or suggested next action | §2.2/§13 `checkpoint()`; drive S1/N6 |
| C-23 | minor | `RECEIPT_RE` dropped a central design phrase | §9 semantic rules: dropped; fragments logged only |
| C-24 | minor | integration order was raw id order | §4.3/§4.5: `(−rank, id)`; drive S1 |
| C-25 | minor | missing `diff_stats` failed open | §5 condition 10 fail-closed; §7.3; the verify schema requires it |
| C-26 | minor | the second author attempt was uninformed | §5: it carries the red verdict (digest_equal false + failures); drive N11 |
| C-27 | minor | reproductions could exit 0 and still confirm | §6.2/§9: non-zero-exit required, else ignored + logged; drive N10 |
| C-28 | minor | `--revert-proof` missed builder-added tests | §7.1/§4.4: `--tests` includes `tests/unit/*` |
| C-29 | minor | the red verifier's digest was only shape-checked | §5/§12 F-12: equality with the author's digest required; drive N11 |
| C-30 | minor | `git worktree add` refuses a checked-out branch for conflict worktrees | §4.4: `worktree add --detach` |
| C-31 | minor | P0 circularity (the setup agent told to create what it must assume) | §2.0 step 2: the venv is CREATED at P0; every prompt asserts existence, never creates |
| C-32 | minor | `SECRET_RE` matched the prompts' own dummy credentials | §10.6/§7.3: the `TESTTOKEN-` convention |
| C-33 | minor | the smoke run executed the full review loop | §2.0 step 8/§6.2: `smoke-skip-review` |
| C-34 | minor | CI/repo path ambiguities (`build_info.json`, evidence/catalog, workflow filenames) | §4.2: placeholder `build_info.json`, `evidence/catalog/README.md` in-repo, the four `.github/workflows` names in card 14's manifest |
| C-35 | minor | `EXPECTED.json` attributed to the wrong writer | §2.1/§8: `tools/expected.py` (card 14) defines the contract; CI writes the file |
| C-36 | minor | `core/engine.py` was delivered by no card | §4.2: in card 03a's manifest |
| C-37 | minor | receipt/label drift (timeout vs `timeout-or-dialog`, revert reasons, self-test exit) | §10.2/§13: `run()` maps receipts; typed revert reasons; the gate computes the self-test exit |
| C-38 | minor | a clean gate ran even when nothing had merged | §4.5/§6.1: skipped when nothing merged and the last clean gate passed at this head; drive S1 |

---

## Appendix C: Drive results v2

**Method.** `drive.mjs` imports `makeScript` from the assembled §13 (`assembled.mjs`, rebuilt from the §9 schemas + the §13 text by `gen.sh`) and drives the WHOLE script from its stage entry to the checkpoint against a fake harness implementing exactly the workflow tool contract: `agent(prompt, {label, phase, schema, effort})`, `parallel` (barrier, throwing thunk → null), `pipeline` (no barrier, stage throw → null), `budget{total, spent, remaining}`, `log`, `phase`. Deterministic shas (`SHA(n)`/`HEX(n)`) make every digest comparison meaningful; the happy path (`happy()`) answers per role+mode with internally consistent digests (`st.seq`/`seqPeek` so a verifier can only reproduce the builder's digest by construction); each scenario overrides one behaviour. Assertions run against the calls (labels, prompts, launch order), the log lines and the checkpoint object — never against an agent's self-report.

**Provenance and result.** The critic's 21 scenarios are all carried (adapted to the v2 mechanisms, with the inversions the critic itself flagged flipped and marked below); 16 new scenarios/sub-variants (N1-N12 + S6b/S7b/S8b/S8c/S17b/S17c/N5b/N8b) aim at the blocking gaps. **37 scenarios, 98 assertions: 98 passed, 0 failed.** Artifacts: `scratch/revise-v2/drive.mjs` + `drive-run.log`; re-run with `node drive.mjs`.

| Scenario | Drives | Asn | The load-bearing assertion |
|---|---|---|---|
| S1 | happy build, 12 cards, wave rule | 12 | wave 1 = [01] alone, wave 2 = [03a, 02] by rank desc; every merge gate carries `--journeys`; no extra review-pre clean gate |
| S2 | schema-valid-but-empty verifier | 3 | 2 builds, parked `no-progress` (never-empty fingerprint, C-18) |
| S3 | verifier pass, different digest | 3 | typed `digest-mismatch` with both ledgers to the fixer; two-strikes at 2 builds |
| S4 | hidden remote at merge | 4 | `HALT remote-added`; nothing after HALT except the synthesizer — which DID run (C-7) |
| S5 | overlapping write sets | 3 | overlapping cards never share a pipeline batch; all still merge |
| S6 / S6b | malformed clean gate; self-test contradicts exit 0 | 3 | no revert; `gate-unavailable`; no lenses on a never-clean tree (C-11/C-10) |
| S7 / S7b | null clean gate every wave, then resume | 6 | no revert, no lenses, stage stays build; resume re-runs a clean gate at head first (C-10), then satisfied |
| S8 / S8b | budget crosses RESERVE mid-wave; resume | 4 | starved cards `not_attempted` (retryable), stage repeats build, synthesizer ran; resume completes without `retry_parked` (C-8) |
| S8c | `agent()` throws budget ceiling | 4 | `HALT budget-exhausted`, synthesizer still ran, no retry fan-out (C-7/CG-20) |
| S9 | stale launch sha | 3 | throws `stale-launch-args`; no card agent launched |
| S10 | secret in builder `output_tail` | 3 | secret reaches no prompt/log/checkpoint; card parked `secret-shaped-output`; no fixer |
| S11 | veto judge null | 3 | stop `veto-unavailable`; not ready; retried once then parked |
| S12 | review finding → fix card | 4 | fixcards wrote `plan/fixes/<id>.json` BEFORE the author ran; the prompt carries the finding text AND the DoD command; `--card plan/fixes/…` (C-3) |
| S13 | root card parked (verify ×3) | 4 | `tree-incomplete`, zero lenses, dependents `not_attempted:dependency-blocked` (C-5) |
| S14 | bogus `already-merged` | 2 | unevidenced claim → `already-merged-unproven`; head unchanged; no revert (C-20) |
| S15 | stage with a failed canary | 3 | NO `promote-production`; stop `blocked-on-owner:staging-evidence`; stage stays stage (C-6/C-9) |
| S16 | seam card merges → journeys | 3 | journeys author launched; the journeys merge gate carries `--journeys`; the author is told the marker + `needs=` rule (C-4) |
| S17 / S17b / S17c | REFUTED citation + missing manifest cards; R1 refusal; repair relaunch | 5 | `repair-plan` (never approve-plan) + `plan_defects` carried; R1 refuses before any author/builder; REPAIR MODE relaunch approves (C-19/C-22) |
| N1 | journey skipped after its card merged | 2 | synthetic finding → refuter → fix card in `plan/fixes/` → built + merged (C-4 + C-3) |
| N2 | one malformed clean gate, healthy later | 2 | no revert; run still ends satisfied + ready (C-11) |
| N3 | clean gate red right after a journeys merge | 3 | exactly one revert, of the JOURNEYS merge, by its merge sha; a passing clean gate at head precedes any lens (C-12/C-10) |
| N4 | merged + gate red | 2 | checked revert of that merge sha; card `reverted`; dependents `dependency-blocked` (C-12) |
| N5 / N5b | resume with prior parked rows | 4 | `agent-null` park auto-retried + merged; `fix-exhausted` stays parked with reason; `retry_parked` re-drives it on demand (C-8/C-22) |
| N6 | verifier drops twice on card 01 | 2 | parked `agent-null:verifier` with `next: retry_parked`; `retry_parked_suggested` exactly [card 01] (C-22) |
| N7 | review loop to max-rounds | 2 | stop `max-rounds(3)`; status blocked; stage stays build (C-9) |
| N8 / N8b | promote with a confirmed critical finding; clean evidence | 2 | `rollback` emitted with the finding id; stage pinned at `promote` (C-6/C-9); clean evidence → satisfied + ready + no rollback |
| N9 | proven `already-merged` | 1 | evidence-checked claim counts as merged; run completes (C-20) |
| N10 | exit-0 reproduction; digest wording in notes | 2 | no fix card for a "holds" whose reproduction exits 0 (C-27); receipt-shaped notes NOT nulled (C-23) |
| N11 | confirm-RED digest differs once | 2 | author attempt 2 carries the verdict (`digest_equal: false`, failures); card then builds + merges (C-26/C-29) |
| N12 | fixture #1 not recorded | 2 | 04 `blocked_on_owner` with next; 05a `dependency-blocked`; independent 08a merged; `record-fixture-1` action; no lenses |

**Annotation taxonomy.** `[flipped: …]` = the critic's assertion encoded a v1 defect (an inverted expectation) and v2 asserts the intended behaviour. `[corrected, not a flip: …]` = my own draft's expectation was wrong and the assertion was rewritten to the correct invariant. `[corrected fixture, assertion unchanged]`, `[strengthened: …]`, `[not carried: …]` as below. Assertions are never edited to make a failing script pass; the three real failures were fixed in `script.js`.

| Assertion | Annotation |
|---|---|
| S1 "checkpoint status ready" | `[flipped: the critic marked its own "blocked" expectation as a mistake]` — with every card merged and the veto clean, `ready` is the correct state |
| S1 wave-2 order | `[corrected, not a flip: my first draft wrote the critic's id order; the rank order is platform-03a (deeper dependents) before platform-02]` |
| S1 rows carry reason + next | `[flipped: v1 rows had neither — C-22]` |
| S2 two-strikes at 2 builds | `[corrected, not a flip: v1 burned all 3 builds only because its fingerprint could be empty, disabling two-strikes; with the never-empty fingerprint the correct expectation is 2 builds + no-progress]` |
| S3 typed digest-mismatch + 2 builds | `[flipped: v1 passed failures: [] and burned 3 builds — C-18/C-26]` |
| S5 trailing refute batch | `[not carried: the critic's S5 asserted a trailing refute batch that only exists in the v1 loop shape; v2 runs refutes inside the review round, and the equivalent behaviour is asserted by S12/N1/N10]` |
| S7 lenses not spent; stage stays build | `[flipped: v1 spent 6 review agents on a never-clean tree — C-5/C-10/C-9]` |
| S8c the synthesizer still ran | `[flipped from FAIL: C-7]` |
| S12 fixcards before author; finding + DoD in the prompt | `[flipped: v1 named a card file nobody wrote — C-3]` |
| S13 tree-incomplete, no lenses | `[flipped from FAIL: C-5]` |
| S15 promote-production not emitted | `[flipped from FAIL: C-6]` |
| S16 merge gate `--journeys` | `[flipped from FAIL: C-4]` |
| S17 repair-plan + plan_defects; R1 refusal; REPAIR MODE | `[flipped from FAIL: C-19/C-22]` |
| N3 re-gate before lens | `[corrected, not a flip: the re-gate is wave 4's clean gate, which is why the literal review-pre label never appears — the invariant is a passing clean gate at head before the first lens (C-10)]` (the hook freezes `st.lastJourneyMerge` at the first journeys merge so the assertion tests the right sha) |
| N7 max-rounds | `[corrected fixture, assertion unchanged: the drive originally fed low-severity findings, which satisfied() correctly tolerates — critical/high are what keep it false]` |
| N8 stage pinned at promote | `[strengthened: C-9 pins the stage at promote, not merely not-done]` |

**The three real defects the drive caught in my own drafts** (fixed in `script.js`, never in the assertions): (1) the gate's protected-ownership rule and `validateCards` disagreed on who may write a protected path — resolved as one ownership rule (`MANIFEST_MIN[id] ∪ protected_touch`) in both (C-21); (2) the synthesizer was blocked by the budget guard after a HALT, violating C-7/F-45 — `budgetOk(label, exemptFromHalt)` now exempts it, because that reserve is what it is FOR; (3) a not-ready promote run advanced `next_args.stage` to `done`, violating C-9 — now `(ready ? 'done' : 'promote')`.

---

*End of design v2. Every section required by the brief is present in the brief's order; all 136 coverage rows are kept and §12.7 adds the v2 mechanism rows; every judge item is mapped in Appendix A (with the v2 audit in A.0); every critic gap C-1..C-38 is resolved with 0 declines and mapped in Appendix B; the gate, the schemas and the script are the exact texts that passed `bash -n` (+ 13 heredocs and 3 one-liners compiled), the schema walk (34 object nodes, 7 roots), `node --check` (both assembly forms), the 22/22 control-path dry run and the 98-assertion fake-harness drive.*
