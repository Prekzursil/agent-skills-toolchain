# CI coverage gap: which `hooks/` and `tools/` test suites does CI actually execute?

Lane `r4-ci-coverage-gap` - branch `docs/ci-coverage-gap-report`. Investigation only.
**No workflow file, test file, or gate was edited by this lane.** Section 6 is a PROPOSAL.

Measured against `origin/main` @ `f348634` in a clean worktree.

---

## 0. Verdict

**PREMISE CONFIRMED on the load-bearing claim, with two corrections to how it was stated.**

CONFIRMED (mechanical, section 3): **162 of the 244 real test suites under
`hooks/` and `tools/` are executed by NO CI step at all** - 64 under `hooks/`,
98 under `tools/`, carrying **1691 `def test_*` functions**. There is no
repo-wide pytest autodiscovery: a suite runs if and only if some workflow step names it.

CONFIRMED, specific to the sentinel adversarial review that triggered this lane: neither
`hooks/tool-result-sentinel/test_sentinel.py` nor
`hooks/tool-result-sentinel/test_sentinel_use_vs_mention.py` appears in any selector in any of the
seven workflow files. That review's "unenforced by CI" finding is **correct**.

CORRECTION 1 - the framing *"gate-tests-coverage (python packages) appears scoped to charter
packages"* is **REFUTED as stated**. The `test-python` job is not scoped to charter packages: it
carries an explicit allow-list that already names ~14 NON-package suites outside the four
100%-gated packages, including `hooks/cmd-rewrite/` (`quality.yml:218-222`),
`hooks/_shared/test_manifest_provenance.py` (`quality.yml:256-257`),
`hooks/_shared/test_hookrun.py` (`quality.yml:262-263`),
`hooks/git-hygiene/test_docs_hygiene.py` (`quality.yml:248-253`),
`tools/triage-router/` (`quality.yml:200-202`) and `tools/repomap/` (`quality.yml:285-286`).
The real mechanism is **allow-list, not package-scope** - and the practical consequence is the
same or worse: anything not on the list is invisible to CI. `quality.yml:204-206` says this in
the repo's own words: *"There is no repo-wide test autodiscovery here, so these suites run only
because this step names them; without it they are dead weight that cannot catch a regression."*

CORRECTION 2 - `quality.yml` is **not** the only workflow that runs tests. Two others do, and
between them they cover 4 suites in scope (section 1.5). A claim that the gap is total, or that
`quality.yml` is the sole gate, would be wrong.

---

## 1. Every CI step that runs a test, with working-directory and selector

Enumerated by reading all 7 files in `.github/workflows/`. `autofix-models.yml`,
`dependabot-auto-merge.yml`, `no-runtime-junk.yml` and `codex-runner.yml` contain **no** test
invocation (verified by grep for `pytest|npm test|python .*test|unittest|node --test`).

### 1.1 `quality.yml` job `lint` - runs NO tests
`quality.yml:60`, `:62` ruff; `:66` `bash .quality/charter_check.sh` (grepped: invokes no test);
`:71-75` `diff -r` vendor-drift. No test executes in this job.

### 1.2 `quality.yml` job `types` - runs NO tests
`quality.yml:91-123`, five `basedpyright` steps. Type-check only.

### 1.3 `quality.yml` job `test-node` (`quality.yml:125-144`)

| step | workflow:line | working-directory | selector |
|---|---|---|---|
| `npm ci` + `npm test` | `quality.yml:133-134` | repo root | `npm run test --workspaces --if-present` -> the 3 root workspaces only: `tools/mcp/codex-orchestrator`, `tools/web/promptbridge-talk-lane`, `tools/fanout-schema` (root `package.json`) |
| `gate-tests-coverage agentify-desktop` | `quality.yml:135-139` | `tools/web/agentify-desktop` | `npm test` |
| `gate-tests-coverage hacktricks-mcp-server` | `quality.yml:140-144` | `tools/mcp/hacktricks-mcp-server` | `npm ci; npm test` |

### 1.4 `quality.yml` job `test-python` (`quality.yml:146-333`) - every step

| # | step name | workflow:line | working-directory | selector |
|---|---|---|---|---|
| 1 | `gate-tests-coverage mcp-manager` | `:154-158` | `tools/mcp-manager` | `pytest --cov=. --cov-fail-under=100` (testpaths=`["tests"]`) |
| 2 | `gate-tests-coverage scholarly-access-mcp` | `:159-163` | `tools/scholarly-access-mcp` | `pytest --cov=scholarly_access ...` (addopts `--ignore=tests/test_live.py`) |
| 3 | `gate-tests-coverage taskwatch_monitor` | `:164-168` | `tools/taskwatch_monitor` | `pytest --cov=. --cov-fail-under=100` (testpaths=`["tests"]`) |
| 4 | `gate-tests-coverage monitorcore` | `:169-173` | `tools/monitorcore` | `pytest --cov=monitorcore --cov-fail-under=100` (testpaths=`["tests"]`) |
| 5 | `gate-tests-coverage stdin-server` | `:179-183` | `tools/stdin-server` | `pytest --cov=stdin_server --cov-fail-under=100` |
| 6 | `gate-tests-coverage harness` | `:193-196` | repo root | `python -m pytest agent-self/harness/tests -q --cov=...` (out of lane scope) |
| 7 | `triage-router standalone regression` | `:200-202` | `tools/triage-router` | `python test_triage_router.py` |
| 8 | `gate-tests-coverage cmd-rewrite hooks` | `:218-222` | `hooks/cmd-rewrite` | `python test_msys_pathconv.py` then `python test_hooks.py` |
| 9 | `gate-tests-coverage search-expansion` | `:234-239` | `tools/search-expansion` | `pytest --cov=rank_fusion --cov=searxng_config --cov=query_plan --cov-fail-under=100` |
| 10 | `gate-tests-coverage strict-target hook manifests` | `:241-245` | repo root | `python -m pytest ci/tests/test_emit_hook_manifest.py` (out of lane scope) |
| 11 | `gate-tests-coverage adversarial harness corpus` | `:248-253` | repo root | `python -m pytest ci/tests/test_harness_corpus_wiring.py tools/harness-corpus/test_hook_telemetry.py hooks/git-hygiene/test_docs_hygiene.py -q` |
| 12 | `gate-tests-coverage hook-manifest provenance` | `:256-257` | repo root | `python hooks/_shared/test_manifest_provenance.py` |
| 13 | `gate-tests-coverage bounded hook launcher` | `:262-263` | repo root | `python hooks/_shared/test_hookrun.py` |
| 14 | `gate-tests-coverage closed-batch config editor` | `:273-274` | repo root | `python -m pytest tools/mcp/closed-batch/tests -q` |
| 15 | `gate-tests-coverage repomap grounding pack` | `:285-286` | repo root | `python tools/repomap/test_repo_map.py` |
| 16 | `gate-tests-coverage claim-verify-gate` | `:300-304` | repo root | 3 scripts under `.agents/skills/claim-verify-gate/scripts/` (out of lane scope) |
| 17 | `gate-tests-coverage fanout-schema` | `:307-311` | `tools/fanout-schema` | `npm test` (= `node --test test_fanout_schema.mjs`) + `npm run lint -- ../../workflows` |
| 18 | `gate-tests-coverage hook manifest conformance` | `:316-317` | repo root | `python -m pytest hooks/_dispatch/test_wiring.py -q -k hook_manifest_conformance` - **PARTIAL** |
| 19 | `browser-rail helper tests` | `:324-325` | repo root | `python -m pytest skills/browser-rail/scripts/test_browser_rail.py -q` (out of lane scope) |
| 20 | `gate-tests-coverage codex-databricks-fanout` | `:332-333` | repo root | `python -m pytest skills/codex-databricks-fanout/scripts/tests -q` (out of lane scope) |

Step 18 is the one selector where a named file is only partly run. Measured locally:

```
$ python -m pytest hooks/_dispatch/test_wiring.py --collect-only -q
13 tests collected in 1.59s

$ python -m pytest hooks/_dispatch/test_wiring.py -q -k hook_manifest_conformance --collect-only
hooks/_dispatch/test_wiring.py::test_hook_manifest_conformance_gate_is_adopted
1/13 tests collected (12 deselected) in 1.06s
```

**CI runs 1 of the 13 tests in that file; 12 are deselected.** The matrix below counts the file as
EXECUTED, which is generous - the true unexecuted function count is 12 higher than the headline.

### 1.5 The two OTHER workflows that run tests

| workflow:line | trigger | selector | in-scope suites it covers |
|---|---|---|---|
| `routing-benchmark.yml:50-57` | `push` main, `pull_request` main, weekly cron, dispatch | `python -m pytest hooks/harness-bench/test_bench.py hooks/harness-bench/test_gate.py hooks/semantic-router/test_eval.py ci/tests/test_routing_benchmark_wiring.py -q` | 3 `hooks/` suites |
| `skill-dual-write.yml:60` | **`pull_request` main ONLY** (no `push`) | `python -m pytest ci/tests tools/d001-dual-write/tests -q` | 1 `tools/` suite |

`skill-dual-write.yml:34-36` has no `push` trigger, so `tools/d001-dual-write/tests/` runs on PRs
but **not** on a direct push to `main`. Also note `routing-benchmark.yml:65` marks only the
benchmark step `continue-on-error`; its pytest step at `:50-57` does gate.

### 1.6 Corroboration that no autodiscovery exists (second independent signal)

Signal A is my selector enumeration above. Signal B is the repo's own committed comments, which
state it four times independently: `quality.yml:204-206`, `quality.yml:254-255`,
`quality.yml:258-261`, `quality.yml:278-280`, plus `skill-dual-write.yml:21-23`
(*"There is no repo-wide test autodiscovery in this repository: a check runs only because a step
below invokes it by an explicit path"*). Two mechanically independent signals agree.

---

## 2. Test suites that EXIST under `hooks/` and `tools/`

`git ls-files hooks tools` filtered to `test_*.py` / `*_test.py`:

| bucket | files | `def test_*` |
|---|---|---|
| **all** | **254** | **3486** |
| REAL (the denominator used below) | 244 | 3450 |
| VENDORED (`tools/editor/ralph-orchestrator/vendor/`) | 7 | 32 |
| FIXTURE (mutation-gate sample project, detector-self-test examples) | 3 | 4 |

Vendored and fixture files are excluded from the gap denominator on purpose: the vendored tree is
`extend-exclude`d third-party code, and the `tools/mutation-gate/sample/test_threshold_*.py` +
`tools/detector-self-test/test_examples.py` files are INPUTS to their own gates, not suites that
should pass on their own. Counting them as "unenforced tests" would be an overclaim.

---

## 3. THE MATRIX

### 3.1 Executed set - 82 files

| suite (or selector) | CI step | workflow:line |
|---|---|---|
| 16 file(s) | `gate-tests-coverage mcp-manager` | `quality.yml:154-158` |
| 5 file(s) | `gate-tests-coverage scholarly-access-mcp` | `quality.yml:159-163` |
| 22 file(s) | `gate-tests-coverage taskwatch_monitor` | `quality.yml:164-168` |
| 21 file(s) | `gate-tests-coverage monitorcore` | `quality.yml:169-173` |
| 1 file(s) | `gate-tests-coverage stdin-server` | `quality.yml:179-183` |
| 1 file(s) | `triage-router standalone regression` | `quality.yml:200-202` |
| 2 file(s) | `gate-tests-coverage cmd-rewrite hooks` | `quality.yml:218-222` |
| 3 file(s) | `gate-tests-coverage search-expansion` | `quality.yml:234-239` |
| 2 file(s) | `gate-tests-coverage adversarial harness corpus` | `quality.yml:248-253` |
| 1 file(s) | `gate-tests-coverage hook-manifest provenance` | `quality.yml:256-257` |
| 1 file(s) | `gate-tests-coverage bounded hook launcher` | `quality.yml:262-263` |
| 1 file(s) | `gate-tests-coverage closed-batch config editor` | `quality.yml:273-274` |
| 1 file(s) | `gate-tests-coverage repomap grounding pack` | `quality.yml:285-286` |
| 1 file(s) | `gate-tests-coverage hook manifest conformance (PARTIAL -k)` | `quality.yml:316-317` |
| 3 file(s) | `routing benchmark self-test` | `routing-benchmark.yml:50-57` |
| 1 file(s) | `gate-skill-dual-write self-test (PR-only)` | `skill-dual-write.yml:60` |

Resolution of the six directory-shaped selectors was done by running the identical selector
locally (not inferred):

```
tools/mcp-manager          $ pytest --collect-only -q  ->  324 tests collected  (16 files)
tools/scholarly-access-mcp $ pytest --collect-only -q  ->  145 tests collected  ( 5 files, test_live.py ignored by addopts)
tools/taskwatch_monitor    $ pytest --collect-only -q  ->  407 tests collected  (22 files)
tools/monitorcore          $ pytest --collect-only -q  ->  557 tests collected  (21 files)
tools/search-expansion     $ pytest --collect-only -q  ->  105 tests collected  ( 3 files)
tools/stdin-server         $ pytest --collect-only -q  ->   28 tests collected  ( 1 file)
```

### 3.2 NOT EXECUTED - `hooks/` (64 files, 571 `def test_*`)

| suite | `def test_*` | runner kind |
|---|---|---|
| `hooks/_dispatch/test_manifest_presence.py` | 7 | pytest |
| `hooks/_golden/test_hooks.py` | 0 | neither |
| `hooks/_shared/test_completion.py` | 0 | main-only |
| `hooks/_shared/test_completion_conformance.py` | 0 | main-only |
| `hooks/_shared/test_completion_vendored.py` | 0 | main-only |
| `hooks/_shared/test_failure_taxonomy.py` | 34 | pytest+main |
| `hooks/_shared/test_projid.py` | 0 | main-only |
| `hooks/_shared/test_use_vs_mention.py` | 20 | pytest |
| `hooks/anti-degen/test_fingerprint.py` | 0 | main-only |
| `hooks/background-digest/test_background_digest.py` | 0 | main-only |
| `hooks/bg-registry/test_bg_registry.py` | 0 | main-only |
| `hooks/bg-registry/test_reconcile_requeue.py` | 15 | pytest+main |
| `hooks/calibrated-silence/test_calibrated_silence.py` | 0 | main-only |
| `hooks/calibrated-silence/test_log_reaction.py` | 0 | main-only |
| `hooks/capability-catalog/test_project_card.py` | 0 | main-only |
| `hooks/claim-guard/test_claim_guard.py` | 30 | pytest |
| `hooks/contraindication/test_check.py` | 32 | pytest |
| `hooks/dark-surface/test_dark_surface.py` | 7 | pytest |
| `hooks/dup-guard/test_dup_guard.py` | 0 | main-only |
| `hooks/edit-checkpoints/test_checkpoint.py` | 0 | main-only |
| `hooks/event-ledger/test_concurrent_append.py` | 0 | main-only |
| `hooks/event-ledger/test_ledger.py` | 0 | main-only |
| `hooks/event-ledger/test_prune_oats.py` | 0 | main-only |
| `hooks/file-scope/test_file_scope.py` | 66 | pytest |
| `hooks/git-hygiene/test_coverage.py` | 21 | pytest |
| `hooks/git-hygiene/test_git_hygiene.py` | 31 | pytest+main |
| `hooks/goal-reinject/test_reinject.py` | 0 | main-only |
| `hooks/heartbeat/test_heartbeat.py` | 0 | main-only |
| `hooks/honest-signal/test_honest_signal.py` | 0 | main-only |
| `hooks/iatrogenics/test_gate.py` | 31 | pytest |
| `hooks/inquisitiveness/test_prompt_guard.py` | 0 | main-only |
| `hooks/journey-coverage/test_journey_coverage.py` | 19 | pytest |
| `hooks/loop-recovery/test_handler.py` | 20 | pytest |
| `hooks/mcp-liveness/test_liveness.py` | 0 | main-only |
| `hooks/memory-guard/test_scan.py` | 0 | neither |
| `hooks/memory-spool/test_memory_spool.py` | 0 | main-only |
| `hooks/memory-spool/test_replay.py` | 12 | pytest |
| `hooks/mvt-patch-leaving/test_check.py` | 24 | pytest+main |
| `hooks/no-force-push/test_no_force_push.py` | 0 | main-only |
| `hooks/notify-idle/test_notify.py` | 8 | pytest+main |
| `hooks/open-loops/test_open_loops.py` | 0 | main-only |
| `hooks/per-edit-check/test_check.py` | 23 | pytest |
| `hooks/per-edit-check/test_secrets.py` | 14 | pytest |
| `hooks/persist-nudge/test_nudge.py` | 0 | main-only |
| `hooks/re-autolaunch/test_autolaunch.py` | 0 | main-only |
| `hooks/recall-inject/test_recall_inject.py` | 39 | pytest |
| `hooks/selection-events/test_emitter.py` | 16 | pytest+main |
| `hooks/session-end/test_end.py` | 7 | pytest+main |
| `hooks/skill-router/test_eval_fixture.py` | 3 | pytest |
| `hooks/stub-ledger/test_report_claim_surface.py` | 6 | pytest+main |
| `hooks/stub-ledger/test_stub_ledger.py` | 0 | main-only |
| `hooks/stub-ledger/test_stubscan_context.py` | 6 | pytest+main |
| `hooks/stub-ledger/test_stubscan_falsepositives.py` | 0 | main-only |
| `hooks/stub-ledger/test_stubscan_regression.py` | 0 | main-only |
| `hooks/subagent-lifecycle/test_subagent_lifecycle.py` | 55 | pytest |
| `hooks/test-tamper-guard/test_tamper_guard.py` | 17 | pytest |
| `hooks/tms/test_tms.py` | 7 | pytest+main |
| `hooks/todo-surfacer/test_todo_surfacer.py` | 0 | main-only |
| `hooks/tool-result-sentinel/test_sentinel.py` | 0 | main-only |
| `hooks/tool-result-sentinel/test_sentinel_use_vs_mention.py` | 1 | pytest+main |
| `hooks/truth-verify/test_truth_verify.py` | 0 | main-only |
| `hooks/ulysses/test_ulysses.py` | 0 | main-only |
| `hooks/wire-check/test_wire_check.py` | 0 | main-only |
| `hooks/wire-check/test_wire_check_routes.py` | 0 | main-only |

### 3.3 NOT EXECUTED - `tools/` (98 files, 1120 `def test_*`)

| suite | `def test_*` | runner kind |
|---|---|---|
| `tools/abbyy-finereader-ocr-mcp/tests/test_engines.py` | 35 | pytest |
| `tools/abbyy-finereader-ocr-mcp/tests/test_evaluation.py` | 18 | pytest |
| `tools/abbyy-finereader-ocr-mcp/tests/test_index.py` | 33 | pytest |
| `tools/abbyy-finereader-ocr-mcp/tests/test_smoke.py` | 3 | pytest |
| `tools/crcp/tests/test_auth_cli_wire.py` | 8 | pytest+main |
| `tools/crcp/tests/test_auth_deeplink.py` | 9 | pytest+main |
| `tools/crcp/tests/test_auth_mirror.py` | 7 | pytest+main |
| `tools/crcp/tests/test_auth_sso.py` | 4 | pytest+main |
| `tools/crcp/tests/test_envelope_v11.py` | 6 | pytest+main |
| `tools/crcp/tests/test_event_key_idempotent.py` | 4 | pytest+main |
| `tools/crcp/tests/test_merge_imports.py` | 1 | pytest+main |
| `tools/crcp/tests/test_merge_wiring.py` | 5 | pytest+main |
| `tools/crcp/tests/test_redact.py` | 4 | pytest+main |
| `tools/crcp/tests/test_sse_classify.py` | 7 | pytest+main |
| `tools/detector-self-test/detector_self_test.py` | 0 | main-only |
| `tools/detector-self-test/tests/test_detector_self_test.py` | 34 | pytest |
| `tools/ese-gate/test_ese_gate.py` | 18 | pytest+main |
| `tools/event-ledger/test_ledger.py` | 0 | main-only |
| `tools/gitcrypt-worktree/tests/test_gitcrypt_worktree.py` | 28 | pytest+main |
| `tools/glob-argv-guard/test_glob_argv_guard.py` | 17 | pytest |
| `tools/mcp/cloud-hub/tests/test_accounts.py` | 21 | pytest |
| `tools/mcp/cloud-hub/tests/test_biomni_broker.py` | 8 | pytest |
| `tools/mcp/cloud-hub/tests/test_biomni_refresher.py` | 14 | pytest |
| `tools/mcp/cloud-hub/tests/test_biomni_server.py` | 24 | pytest |
| `tools/mcp/cloud-hub/tests/test_compute.py` | 55 | pytest |
| `tools/mcp/cloud-hub/tests/test_databricks_server.py` | 13 | pytest |
| `tools/mcp/cloud-hub/tests/test_hardening.py` | 31 | pytest |
| `tools/mcp/cloud-hub/tests/test_hub.py` | 6 | pytest |
| `tools/mcp/cloud-hub/tests/test_modal.py` | 57 | pytest |
| `tools/mcp/cloud-hub/tests/test_registry.py` | 7 | pytest |
| `tools/mcp/codex-fleet-github/tests/test_fleet_core.py` | 42 | pytest |
| `tools/mcp/codex-fleet-github/tests/test_server.py` | 2 | pytest |
| `tools/mcp/fb-messenger-mcp/_fb_test.py` | 0 | neither |
| `tools/mcp/fb-messenger-mcp/tests/test_dm_e2ee.py` | 15 | pytest |
| `tools/mcp/fb-messenger-mcp/tests/test_dm_e2ee_proxy.py` | 21 | pytest |
| `tools/mcp/fb-messenger-mcp/tests/test_graph.py` | 26 | pytest |
| `tools/mcp/fb-messenger-mcp/tests/test_messenger_send.py` | 9 | pytest |
| `tools/mcp/fb-messenger-mcp/tests/test_server.py` | 4 | pytest |
| `tools/mcp/linkedin-mcp/tests/test_linkedin_core.py` | 66 | pytest |
| `tools/mcp/linkedin-mcp/tests/test_server.py` | 6 | pytest |
| `tools/mcp/mcp-host-supervisor/tests/test_fleet.py` | 47 | pytest |
| `tools/mcp/mcp-http-host/tests/test_apply_registration.py` | 16 | pytest |
| `tools/mcp/mcp-http-host/tests/test_mcp_http_host.py` | 24 | pytest |
| `tools/mcp/openmm-md-mcp/smoke_test.py` | 0 | main-only |
| `tools/mcp/patent-search-mcp/tests/test_patent_api.py` | 5 | pytest |
| `tools/mcp/patent-search-mcp/tests/test_server.py` | 3 | pytest |
| `tools/mcp/proxy-mcp/tests/test_redaction.py` | 29 | pytest |
| `tools/mcp/qdx-rush-mcp/tests/test_charge_parsers.py` | 14 | pytest |
| `tools/mcp/reverse-engineering-mcp-bundle/tests/test_register_mcp_server.py` | 4 | pytest+main |
| `tools/mcp/schrodinger-mcp/_e2e_test.py` | 0 | main-only |
| `tools/mcp/schrodinger-mcp/_pipeline_test.py` | 0 | main-only |
| `tools/mcp/search-hub/tests/test_accounts_env_for.py` | 5 | pytest |
| `tools/mcp/search-hub/tests/test_hub.py` | 7 | pytest |
| `tools/mcp/search-hub/tests/test_providers.py` | 8 | pytest |
| `tools/mcp/search-hub/tests/test_rotation.py` | 16 | pytest |
| `tools/mcp/search-hub/tests/test_usage.py` | 8 | pytest |
| `tools/mcp/social-hub/tests/test_accounts.py` | 13 | pytest |
| `tools/mcp/social-hub/tests/test_fb_session.py` | 20 | pytest |
| `tools/mcp/social-hub/tests/test_fb_session_mcp.py` | 3 | pytest |
| `tools/mcp/social-hub/tests/test_fb_timeline.py` | 22 | pytest |
| `tools/mcp/social-hub/tests/test_hardening.py` | 6 | pytest |
| `tools/mcp/social-hub/tests/test_hub.py` | 6 | pytest |
| `tools/mcp/social-hub/tests/test_registry.py` | 4 | pytest |
| `tools/mcp/tiktok-mcp/_tt_test.py` | 0 | main-only |
| `tools/mutation-gate/tests/test_mutation_gate.py` | 23 | pytest |
| `tools/mutation-gate/tests/test_mutation_gate_demo.py` | 3 | pytest |
| `tools/omniaudit-mcp/tests/integration/test_mcp_protocol.py` | 7 | pytest |
| `tools/omniaudit-mcp/tests/unit/test_auditlens_wave1.py` | 3 | pytest |
| `tools/omniaudit-mcp/tests/unit/test_confirmation.py` | 2 | pytest |
| `tools/omniaudit-mcp/tests/unit/test_cov_app.py` | 5 | pytest |
| `tools/omniaudit-mcp/tests/unit/test_cov_auditlens.py` | 13 | pytest |
| `tools/omniaudit-mcp/tests/unit/test_cov_github.py` | 11 | pytest |
| `tools/omniaudit-mcp/tests/unit/test_cov_observability.py` | 6 | pytest |
| `tools/omniaudit-mcp/tests/unit/test_cov_releasebutler.py` | 13 | pytest |
| `tools/omniaudit-mcp/tests/unit/test_cov_runtime.py` | 22 | pytest |
| `tools/omniaudit-mcp/tests/unit/test_cov_scanner.py` | 8 | pytest |
| `tools/omniaudit-mcp/tests/unit/test_cov_security.py` | 4 | pytest |
| `tools/omniaudit-mcp/tests/unit/test_cov_sitelint_service.py` | 11 | pytest |
| `tools/omniaudit-mcp/tests/unit/test_cov_storage.py` | 17 | pytest |
| `tools/omniaudit-mcp/tests/unit/test_cov_worker.py` | 6 | pytest |
| `tools/omniaudit-mcp/tests/unit/test_findings_parser.py` | 1 | pytest |
| `tools/omniaudit-mcp/tests/unit/test_jobs.py` | 1 | pytest |
| `tools/omniaudit-mcp/tests/unit/test_object_store_adapters.py` | 2 | pytest |
| `tools/omniaudit-mcp/tests/unit/test_observability.py` | 2 | pytest |
| `tools/omniaudit-mcp/tests/unit/test_policy.py` | 2 | pytest |
| `tools/omniaudit-mcp/tests/unit/test_rate_limit.py` | 2 | pytest |
| `tools/omniaudit-mcp/tests/unit/test_release_checksum.py` | 1 | pytest |
| `tools/omniaudit-mcp/tests/unit/test_releasebutler_hardening.py` | 3 | pytest |
| `tools/omniaudit-mcp/tests/unit/test_releasebutler_wave1.py` | 3 | pytest |
| `tools/omniaudit-mcp/tests/unit/test_settings.py` | 1 | pytest |
| `tools/omniaudit-mcp/tests/unit/test_sitelint_wave1.py` | 2 | pytest |
| `tools/omniaudit-mcp/tests/unit/test_tool_registry.py` | 1 | pytest |
| `tools/re-harness/tests/test_mcp_doc_drift.py` | 17 | pytest |
| `tools/scholarly-access-mcp/tests/test_live.py` | 0 | neither |
| `tools/workspace-hooks/anti-degen/test_fingerprint.py` | 0 | main-only |
| `tools/workspace-hooks/event-ledger-extras/test_prune_oats.py` | 0 | main-only |
| `tools/workspace-hooks/goal-reinject/test_reinject.py` | 0 | main-only |
| `tools/workspace-hooks/inquisitiveness/test_prompt_guard.py` | 0 | main-only |

### 3.4 A concrete, self-documented instance

`quality.yml:260-261` states: *"Measured when A04 landed: `hooks/_shared` holds 7 test suites and
CI invoked exactly ONE of them."* Today `hooks/_shared` holds **8** suites and CI invokes **2**
(`test_manifest_provenance.py` at `:257`, `test_hookrun.py` at `:263`). The other **6** -
`test_completion.py`, `test_completion_conformance.py`, `test_completion_vendored.py`,
`test_failure_taxonomy.py`, `test_projid.py`, `test_use_vs_mention.py` - run nowhere.

---

## 4. Quantification

| measure | value |
|---|---|
| test FILES under `hooks/`+`tools/` (real) | 244 |
| test FILES executed by some CI step | 82 |
| **test FILES executed by NO CI step** | **162** (64 `hooks/`, 98 `tools/`) |
| **`def test_*` FUNCTIONS in the not-executed set** | **1691** (571 `hooks/`, 1120 `tools/`) |
| plus deselected functions in a "covered" file (`test_wiring.py`, 12 of 13) | +12 -> **1703** effective |
| pytest ITEMS collected from the 62 collectable not-executed `hooks/` suites | **589** (measured, section 6.3) |

**Unit disclaimer, stated inline because it changes the number:** `def test_*` counts test
*function definitions* found by AST. pytest reports test *items* after parametrization, so the
item count is higher (589 items from 62 files whose AST function count is lower). Both numbers are
in the same table above with their units named; neither is a coverage percentage and this document
makes no claim about line/branch coverage.

**Second inline disclaimer - the function count UNDERSTATES the gap.** 44 of the
162 not-executed suites are `main-only`: they contain **zero** `def test_*` and instead run
`ok(name, cond)` / `check(name, cond)` assertions from a `main()` under an
`if __name__ == "__main__"` guard. Example: `hooks/tool-result-sentinel/test_sentinel.py` is 310
lines of real regression checks and contributes **0** to the 1691 figure. Runner-kind
breakdown of the not-executed set:

| runner kind | files | consequence |
|---|---|---|
| `main-only` | 44 | NOT pytest-collectible - must be invoked as `python <file>` |
| `neither` | 4 | NOT pytest-collectible - must be invoked as `python <file>` |
| `pytest` | 90 | pytest-collectible |
| `pytest+main` | 24 | pytest-collectible |

---

## 5. Two structural blockers a naive fix hits (measured, not predicted)

These are why the proposal in section 6 is shaped the way it is rather than being one line.

### B1 - module-level `sys.exit()` aborts the ENTIRE pytest run

4 files call `sys.exit()` at module top level, outside any `__main__` guard. pytest imports the
module during collection, the `SystemExit` escapes, and pytest dies with `INTERNALERROR` -
discarding every other test in the run. Measured:

```
$ python -m pytest hooks/ --collect-only -q
INTERNALERROR>   File ".../hooks/_golden/test_hooks.py", line 111, in <module>
INTERNALERROR>     sys.exit(0 if all(results) else 1)
INTERNALERROR> SystemExit: 0
21 tests collected in 7.83s
```

21 of 705 collected before the abort. The 4 files:
- `hooks/_golden/test_hooks.py`
- `hooks/cmd-rewrite/test_hooks.py`
- `hooks/memory-guard/test_scan.py`
- `tools/scholarly-access-mcp/tests/test_live.py`

(`hooks/cmd-rewrite/test_hooks.py` and `tools/scholarly-access-mcp/tests/test_live.py` are already
handled correctly today - the former is invoked as `python test_hooks.py` at `quality.yml:222`, the
latter is excluded by `addopts` in its `pyproject.toml`. They are listed because they constrain any
new directory-shaped selector.)

### B2 - duplicate basenames collide under pytest's default `prepend` import mode

18 basenames are used by 2+ test files, 42 files involved, and none of the `hooks/`
directories involved has an `__init__.py`. (Scoped deliberately: of the 30 directories
holding a duplicated basename, 4 DO have one -- `tools/crcp/tests`,
`tools/mcp-manager/tests`, `tools/monitorcore/tests`, `tools/taskwatch_monitor/tests`.
The claim holds for every `hooks/` directory, which is where the section 6 proposal
applies, so nothing downstream changes.) With the 3 `hooks/` B1 files ignored, the collision is what fails next:

```
$ python -m pytest hooks/ --collect-only -q --ignore=hooks/_golden/test_hooks.py     --ignore=hooks/memory-guard/test_scan.py --ignore=hooks/cmd-rewrite/test_hooks.py
import file mismatch:
imported module 'test_check' has this __file__ attribute:
  .../hooks/contraindication/test_check.py
which is not the same as the test file we want to collect:
  .../hooks/mvt-patch-leaving/test_check.py
ERROR hooks/iatrogenics/test_gate.py
ERROR hooks/mvt-patch-leaving/test_check.py
ERROR hooks/per-edit-check/test_check.py
!!!!!!!!!!!!! Interrupted: 3 errors during collection !!!!!!!!!!!!!
612 tests collected, 3 errors in 7.69s
```

Colliding basenames inside `hooks/` alone: `test_check.py` (x3), `test_gate.py` (x2),
`test_hooks.py` (x2). Across the tree: `test_hub.py` (x3), `test_server.py` (x5), `test_accounts.py`,
`test_hardening.py`, `test_registry.py`, `test_ledger.py`, `test_fingerprint.py`,
`test_prune_oats.py`, `test_reinject.py`, `test_prompt_guard.py`, `test_smoke.py`, `test_policy.py`,
`test_adapters.py`, `test_models.py`, `test_redact.py`.

`--import-mode=importlib` resolves B2 without renaming any file. Measured:

```
$ python -m pytest hooks/ --collect-only -q --import-mode=importlib     --ignore=hooks/_golden/test_hooks.py --ignore=hooks/memory-guard/test_scan.py     --ignore=hooks/cmd-rewrite/test_hooks.py
705 tests collected in 2.94s          # 0 errors
```

---

## 6. PROPOSAL - minimal opt-in for the harness suites (NOT APPLIED)

Design constraints taken from the file's own conventions:
`quality.yml:207-210` and `:279-281` establish that a new harness suite reuses the existing
`gate-tests-coverage` charter slug on purpose, so `.quality/charter_check.sh` stays consistent
**with no `.quality/charter.yml` edit**; and `:322-323` establishes that a step deliberately NOT
named `gate-<slug>` is ignored by the reverse check. The proposal below uses the first form, so it
is a `quality.yml`-only change.

### 6.1 The two steps

Added to the `test-python` job after `quality.yml:333`. pytest is already installed by earlier
steps in the same job.

```yaml
      # hooks/ regression harness -- the ~60 hook suites that no step currently names.
      # Reuses the existing `gate-tests-coverage` charter slug on purpose (see the
      # closed-batch and repomap steps above): not a new gate, so charter_check.sh stays
      # consistent with no charter.yml edit.
      # --import-mode=importlib is REQUIRED, not cosmetic: 18 basenames are duplicated in
      # this tree (test_check.py x3, test_gate.py x2, test_hooks.py x2 inside hooks/ alone)
      # and the default `prepend` mode fails collection with `import file mismatch`.
      # The two --ignore files call sys.exit() at MODULE level, which escapes as
      # SystemExit during collection and aborts the whole run with INTERNALERROR; they are
      # invoked as standalone scripts in the step below instead.
      - name: gate-tests-coverage hooks regression harness
        run: |
          python -m pytest hooks/ -q --import-mode=importlib \
            --ignore=hooks/_golden/test_hooks.py \
            --ignore=hooks/memory-guard/test_scan.py \
            --ignore=hooks/cmd-rewrite/test_hooks.py
      # The two module-level-exit suites that no other step covers, run the way they are
      # designed to run -- the same `python <file>` convention already used for
      # test_manifest_provenance.py (:257), test_hookrun.py (:263) and test_repo_map.py
      # (:286). Each exits non-zero on failure. cmd-rewrite/test_hooks.py is NOT repeated
      # here: it is already invoked at :222.
      - name: gate-tests-coverage hooks standalone suites
        run: |
          python hooks/_golden/test_hooks.py
          python hooks/memory-guard/test_scan.py
```

All **three** `--ignore` flags are load-bearing, including
`hooks/cmd-rewrite/test_hooks.py`. I initially expected `--import-mode=importlib` to make the third
unnecessary (its purpose is the basename collision) and probed the 2-ignore form to check. It
FAILS - that file has an independent B1 module-level exit at line 560:

```
$ python -m pytest hooks/ --collect-only -q --import-mode=importlib \
    --ignore=hooks/_golden/test_hooks.py --ignore=hooks/memory-guard/test_scan.py
INTERNALERROR>   File ".../hooks/cmd-rewrite/test_hooks.py", line 560, in <module>
INTERNALERROR>     sys.exit(0)
INTERNALERROR> SystemExit: 0
136 tests collected in 8.09s
```

Dropping that third `--ignore` costs 569 of the 705 collectable items. Measured, not inferred.

### 6.2 Why this is the minimum

- **2 steps, 1 file changed, 0 charter edits.** Reusing `gate-tests-coverage` avoids the
  three-coordinated-edit cost that `skill-dual-write.yml:16-19` documents for a new gate slug.
- **No test file is renamed** - `--import-mode=importlib` absorbs all 18 basename collisions.
- **No new dependency** - stdlib + the already-installed pytest.
- **No coverage threshold.** Deliberately not a `--cov-fail-under` lane, matching the stated
  rationale for the `harness` step at `quality.yml:188-190` and the `cmd-rewrite` step at
  `:209-210`: these are projections of a live runtime, and a hard 100% bar would misrepresent them
  and pin `main` red.

### 6.3 What is measured and what is NOT - read before applying

**Measured:** collection succeeds. `589` items collect cleanly from exactly the 62 not-executed,
pytest-collectible `hooks/` suites, and `705` from `hooks/` as a whole with the 3-ignore form:

```
$ python _r4_items.py
not-executed hooks/ REAL suites: 64
  minus B1 module-level-exit files: 62
589 tests collected in 12.88s
exit=0
```

**NOT measured - the decisive open question.** I did **not** run these suites to green, and
**not** on a Linux runner. Every probe behind the SECTION 6 numbers is `--collect-only` by
deliberate choice (the section 6.4 cloud-hub ERROR claim is the one exception -- collection
there always succeeds, so that observation necessarily comes from a real run):
these are HARNESS suites that launch hook scripts as subprocesses, and executing ~60 of them on
this machine risks writing to live harness state (`~/.claude`, the event ledger, hook caches).
Collection is side-effect-light; a full run is not. My probes ran on **Windows / CPython
3.14.6**; CI is
**ubuntu-latest / CPython 3.11**. Many hook suites are platform-coupled by construction - the
MSYS-argv fixtures at `quality.yml:211-213` are documented as skipping on Linux, and several
suites shell out to `git`, PowerShell, or absolute Windows paths. **A plausible outcome of
applying section 6.1 as written is a red `main`.** Confidence that the 2-step form runs GREEN on
ubuntu without further per-suite triage: **uncertain, 30-55%** - the evidence is collection-only,
which says nothing about pass/fail.

That is precisely why this lane proposes rather than applies. The recommended sequencing is:

1. Run the section 6.1 commands on an ubuntu runner via `workflow_dispatch` on a scratch branch,
   or locally under WSL, and capture the failure list.
2. Triage each failure into: genuinely-broken (fix), platform-coupled (add a
   `pytest.mark.skipif` with the reason inline, the `cmd-rewrite` precedent), or environment-dep
   (install it).
3. Only then land the steps, so `main` never goes red.

An intermediate landing that carries **zero** red-main risk is to add only the suites protecting
this wave's harness fixes - starting with the 2 sentinel suites and the 6 unrun `hooks/_shared`
suites (section 3.4) - as explicit `python -m pytest <file>` / `python <file>` steps, verified one
at a time. That is a smaller opt-in than section 6.1 but does not close the 64-suite gap.

### 6.4 Out of scope for this proposal

- `tools/` (98 suites, 1120 `def test_*`) is deliberately NOT proposed here. Several trees
  need real third-party installs (`tools/omniaudit-mcp` 26 suites, `tools/crcp` 10) and
  `tools/mcp/cloud-hub/tests/test_hub.py` + `test_hardening.py` ERROR in any fresh worktree because
  `accounts.json` is git-crypt ciphertext there - a pre-existing condition, not a defect this lane
  introduces. Wiring `tools/` is a separate, larger piece of work.
- `tools/mcp/cloud-hub/ovh-mcp/tests/ovh-client.test.ts` is a node suite in no npm workspace and
  named by no CI step. Flagged; not proposed.
- Whether `skill-dual-write.yml` should also trigger on `push: main` (section 1.5) is a real
  finding but a different file, so it is out of this lane's deliverable.

---

## 7. Reproduction

The three probe scripts used to produce every number above are NOT committed (they are scratch).
Regenerate with:

```
git ls-files hooks tools | grep -E '(^|/)(test_[^/]*\.py|[^/]*_test\.py)$'   # the 254-file inventory
python -m pytest <dir> --collect-only -q                                      # resolve a directory selector
python -m pytest hooks/ --collect-only -q                                     # reproduce B1
python -m pytest hooks/ --collect-only -q --import-mode=importlib \
  --ignore=hooks/_golden/test_hooks.py --ignore=hooks/memory-guard/test_scan.py \
  --ignore=hooks/cmd-rewrite/test_hooks.py                                    # 705, 0 errors
```

---

## 8. Corrections applied after adversarial recheck (2026-07-25)

A fresh-context recheck independently re-derived the headline with a **zero set difference**
(244 real suites, 82 executed, 162 not executed, 64 `hooks/` + 98 `tools/`, 1691 `def test_*`;
all 20 `test-python` step citations exact; B1 and B2 reproduced exactly). It also found four
items stated as measured that did not hold. Three are corrected above; the fourth is recorded
here rather than silently fixed.

- **F1 (corrected in section 3.4 and the section 4 totals).**
  `tools/detector-self-test/tests/test_detector_self_test.py` was labelled `pytest+main`. It has
  **no** `__main__` guard: its only two `__main__` occurrences are a **comment** (`:355`) and a
  **string argument** (`:363 runpy.run_path(..., run_name="__main__")`). The runner-kind split is
  therefore `pytest 90 / pytest+main 24`, not `89 / 25`. The load-bearing
  `44 main-only + 4 neither` figure is unaffected. Worth naming: this is the same
  **use-vs-mention** error class the sibling `tool-result-sentinel` lane exists to fix, and it
  occurred inside a file called `detector-self-test`.
- **F2 (corrected in section 5, B2).** The `no __init__.py` claim was universal; it is true of
  every `hooks/` directory but false for 4 `tools/` ones.
- **F3 (corrected in section 6.3).** "Every probe in this document is `--collect-only`" was an
  overstated blanket: the section 6.4 cloud-hub ERROR observation cannot come from a
  collect-only probe, because collection there succeeds. The claim itself was verified true.
- **F4 (NOT corrected - cosmetic, recorded).** Four of seventeen workflow citations start one
  line late: `quality.yml:204-206` (the quoted comment spans 203-205), `:278-280` (277-280),
  `:322-323` (321-323), `:188-190` (187-190). All four land inside the correct comment block, so
  no claim moves; they are listed here so a reader tracing a quote is not misled.

None of F1-F4 widens a headline claim.
