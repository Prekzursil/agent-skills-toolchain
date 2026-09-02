# Harness lineage reunion, 2026-09-02

Resolves the reconcile direction left open in `harness-lineage-2026-09-01.md`
(section 5, decision 1). Nothing was mashed: every file was classified against a
three-way base, every B-side change was either ported into A **with tests** or
recorded below with the reason it was not carried. A stays authoritative for harness
code; CI stays green.

| | before | after |
|---|---|---|
| **A** `agent-self/harness` (CI, repo layout) | 834 passed, 1 skipped | **926 passed, 1 skipped** |
| **B** live tree, captured verbatim on `live-capture/2026-09-02` at `harness/` (commit `726687ec`) | 1 collection error; with `test_register_gate.py` ignored 19 failed, 767 passed | unchanged (a capture; the deploy below replaces it) |
| `.agents/harness` (deployable mirror of the live folder) | 2026-08-28 capture: 1 collection error + 19 failed, 485 passed | byte-identical to reunited A: **926 passed, 1 skipped** |
| reunited A in a simulated harness-at-root layout with `~/.agents/command-center` deployed | — | 914 passed, 13 skipped, 0 failed |
| `ruff check` / `ruff format --check` (A and mirror) | clean | clean |
| `basedpyright` standard, A source (CI's ephemeral config) | 0 errors | 0 errors |
| branch coverage A (CI's `--cov` invocation, measured not gated) | ~85% | 97% total; adapters 100%, registration 100%, dispatcher 99%, ledger 98%, recall_index 96%, modules 89% |

Reproduce (repo root, py3.12, `pip install pytest pytest-cov pyyaml`):

```bash
python -m pytest agent-self/harness/tests -q          # 926 passed, 1 skipped
python -m pytest .agents/harness/tests -q             # 926 passed, 1 skipped
diff -r -x __pycache__ agent-self/harness .agents/harness && echo IDENTICAL
git archive origin/live-capture/2026-09-02 harness | tar -x -C /tmp/B && \
  (cd /tmp/B && python -m pytest harness/tests -q)   # 1 collection error (B's own tests vs B's own code)
```

## 1. Method

1. **Populations.** A = `agent-self/harness` at `5c6e1bae` (main). B = `harness/` on
   `live-capture/2026-09-02` (`726687ec`). The two git histories share **no merge
   base** (`git merge-base` is empty), so a repo-wide three-way merge was impossible.
2. **Per-file three-way base.** For every diverged file, B's blob was searched in A's
   history (`git log --find-object`) and, where absent, the A revision with the
   smallest line diff against B was taken as the base. Four B files are byte-identical
   to A's 2026-07-18 enshrinement (`58686d3b`) — B never changed them; A moved on. For
   the other seven the bases are named in the table.
3. **Classification** of all 44 paths: identical / A-only / B-only / diverged, from
   sha256 of the file bytes (section 2).
4. **Port.** For every B-only or diverged file: `diff base..B` = what live added,
   `diff base..A` = what the repo added. Each B-side hunk was judged as behaviour or
   not, ported into A (tests first, then code, `ruff format`ed), or recorded in
   section 4 with the reason. B's three live-only suites were adopted; where B's tests
   asserted a variant A had already fixed differently, the test was adapted to A's
   contract and the divergence is recorded.
5. **Mirror.** `.agents/harness` is refreshed to the reunited A, byte for byte (the
   live folder stays harness-at-root; `.agents/` is its deployable mirror). B's
   `dispatcher.py.orig` patch artifact is not mirrored.

## 2. Classification table (44 paths)

`A`/`B` = line counts. `base` = three-way base used (A revision). `.agents/harness`
= the 2026-08-28 capture that was on main before this change.

| path | class | A | B | base | what happened |
|---|---|---:|---:|---|---|
| `.gitignore` | identical | 12 | 12 | — | — |
| `__init__.py` | identical | 5 | 5 | — | — |
| `models.py` | identical | 148 | 148 | — | — |
| `schemas/hook-result.schema.json` | identical | 39 | 39 | — | — |
| `storage.py` | identical | 64 | 64 | — | — |
| `surface_reconciler.py` | identical | 583 | 583 | — | — |
| `README.md` | diverged | 73 | 56 | `58686d3b` (B == base) | B stale; A kept and extended for the ported behaviour |
| `adapters.py` | diverged | 244 | 299 | `fa62d369` | **ported**: `_NO_NATIVE_CONTEXT_EVENTS`, `turn_id`→`prompt_id` fallback, `grok` provider (§3.1) |
| `dispatcher.py` | diverged | 585 | 683 | `fa62d369` | **ported**: fan-out wall-clock budget, degraded quarantine, `_as_int`, `--provider grok`, `bm_vault_digest` priority, `os._exit` (§3.2); B's `input_error` not carried (§4) |
| `dispatcher.py.orig` | B-only | 0 | 562 | — | not carried: `patch(1)` backup artifact, not source |
| `injection_grammar.py` | diverged | 211 | 191 | `58686d3b` (B == base) | B stale; A kept |
| `install.py` | diverged | 1222 | 887 | `58686d3b` (B == base) | B stale (lacks `deploy(skill_surface_roots=)`, the cause of B's 15 `test_surface_reconciler` failures); A kept |
| `ledger.py` | diverged | 1327 | 1542 | `8a61d931` (A == base) | **ported whole** (§3.3); reunited file is byte-identical to B |
| `modules.py` | diverged | 3691 | 3710 | `696ed513` | **ported**: session-cwd path resolution, FIX-N session flags, spool, vault digest (§3.4); A's `RegisterGateModule` kept |
| `recall_index.py` | diverged | 358 | 555 | `58686d3b` | **ported**: digest sidecar builder + `--from-index` (§3.5); A's vault-alias guard kept |
| `redaction.py` | diverged | 74 | 92 | `0cd20c07` (A == base) | not carried: comment-only delta; patterns and `redact_text` verified identical (§4) |
| `registration.py` | diverged | 189 | 221 | `01c9b9a7` (A == base) | **ported**: `build_hooks("grok")` with the deliberate `.*` matcher / no hand-edits (§3.1) |
| `schemas/hook-event.schema.json` | diverged | 63 | 57 | `58686d3b` (B == base) | B stale (lacks `agent.parent_id`); A kept |
| `tests/conftest.py` | diverged | 9 | 19 | — | **ported** autouse `BASIC_MEMORY_VAULT` isolation |
| `tests/test_contract.py` | diverged | 188 | 167 | — | A kept (B lacks the schema/lineage/initializer tests) + B's grok test **ported** |
| `tests/test_cov_dispatcher_adapters.py` | diverged | 484 | 480 | — | A kept (B's variant asserts the not-carried `input_error`) |
| `tests/test_cov_final.py` | identical | 37 | 37 | — | **rewritten** for the OS-level lock (both trees tested the retired O_EXCL lock) |
| `tests/test_cov_install_small.py` | identical | 417 | 417 | — | — (absent from the 2026-08-28 capture; now mirrored) |
| `tests/test_cov_ledger.py` | diverged | 786 | 689 | — | A kept (B is a stale prefix); 4 O_EXCL-lock tests **replaced** by 11 for the new lock |
| `tests/test_cov_modules_a.py` | identical | 778 | 778 | — | — |
| `tests/test_cov_modules_b.py` | identical | 950 | 950 | — | — |
| `tests/test_cov_recall_injection.py` | identical | 279 | 279 | — | — |
| `tests/test_deploy_command_center.py` | A-only | 233 | 0 | — | kept; repo-only probe now skips in the deployed layout |
| `tests/test_dispatcher_and_registration.py` | diverged | 419 | 380 | — | A kept (B lacks the D010 CLI tests) + B's grok `build_hooks` test **ported** + grok wire test added |
| `tests/test_dispatcher_degraded_health.py` | B-only | 0 | 252 | — | **adopted**, theme 3 adapted to A's D010 contract, 5 cases added |
| `tests/test_dispatcher_mixer_breaker.py` | identical | 469 | 469 | — | — |
| `tests/test_fix_n_session_flags.py` | B-only | 0 | 165 | — | **adopted** verbatim |
| `tests/test_injection_grammar.py` | diverged | 123 | 83 | — | B stale prefix; A kept |
| `tests/test_install_deploy.py` | diverged | 355 | 251 | — | B stale prefix; A kept |
| `tests/test_install_reconciler.py` | identical | 735 | 735 | — | — |
| `tests/test_ledger_process_recovery.py` | B-only | 0 | 181 | — | **adopted** verbatim (cross-process lock proof) |
| `tests/test_ledger_receipts_and_taint.py` | diverged | 531 | 661 | — | **adopted** B (a strict superset of A) + 3 edge tests added |
| `tests/test_modules.py` | diverged | 2865 | 3056 | — | A kept + B's 9 additions **ported** (digest ×5, session-cwd ×2, nudge/spool ×2) + 7 added; B's deletions not carried (§4) |
| `tests/test_native_events.py` | diverged | 342 | 507 | — | **adopted** B (host-union replica + 5 tests; a superset of A) |
| `tests/test_recall_index.py` | diverged | 324 | 243 | — | A kept (B lacks the D-wu-34 guard tests) + B's sidecar assertions **ported** + 8 builder tests added |
| `tests/test_register_gate.py` | diverged | 444 | 426 | — | B is A before `cf7d2cfa` (pinned live ids); A kept; real-register fixture now skips outside the repo layout |
| `tests/test_security_regressions.py` | diverged | 381 | 208 | — | B stale prefix; A kept |
| `tests/test_storage_read_status.py` | identical | 113 | 113 | — | — |
| `tests/test_surface_reconciler.py` | identical | 831 | 831 | — | — |

Totals: 15 identical, 24 diverged, 4 B-only, 1 A-only. Of the 24 diverged: 8 are
B-stale (B == an older A), 9 carried B-side behaviour into A, 7 are test files where A
was kept and B's additions were merged in.

## 3. What was ported (behaviour, with the evidence the live tree recorded)

### 3.1 adapters.py / registration.py

- **Host-union-safe injects.** `PostCompact`, `TaskCompleted`, `TaskCreated`,
  `TeammateIdle`, `PermissionDenied` (and `ConfigChange`, already) render an inject as
  `systemMessage`. Live measured 2026-07-27 against claude 2.1.220 that those names have
  no `additionalContext`-bearing member in the host's `hookSpecificOutput` output union:
  the first four fail the union (whole payload degraded to plainText), the fifth's
  member is `{hookEventName, retry?}` so the key is stripped. `test_native_events.py`
  now carries a replica of that union and asserts every rendered output survives it.
- **`turn_id` falls back to `prompt_id`/`promptId`.** The claude base payload names the
  turn `prompt_id`; live measured 112076/112076 claude `tool_result` rows with
  `turn_id == ""` vs 16970/16971 populated for codex — turn scoping was inert on
  claude. Composes with A's `models.evidence_turn_id` (session-derived fallback stays
  for the no-identity case; D-wu-24 tests still pass).
- **`grok` as a runtime provider** (attribution fix; Grok's hooks ran as
  `--provider claude`). Rides the claude `Stop`/`SubagentStop` branch because Grok's
  output vocabulary has no `systemMessage`; `build_hooks("grok")` keeps the broad `.*`
  matcher (the claude matcher hits 1 of 13 Grok tools) and none of the claude
  hand-edits. Runtime only: `install.py` still writes just the claude and codex
  documents.

### 3.2 dispatcher.py

- **Fan-out wall-clock budget.** Modules run on a daemon thread under
  `registration._TIMEOUTS[event] - 0.6s` (floor 0.25s; `HARNESS_DISPATCH_BUDGET_MS`
  overrides, `0` disables). An over-budget module is abandoned and named in
  `failed_modules`; the terminal record is written either way. Live measured on 260k
  terminal records: 2.3% of `UserPromptSubmit` already exceeded the 2s cap and were
  SIGKILLed with no record. `__main__` flushes and `os._exit`s so an abandoned thread
  cannot push finalization past the host deadline.
- **Degraded quarantine.** An enforced breaker skip stamps `FAILED:hook-<event>` and
  names the skipped detector instead of reporting a clean measurement.
- **`_as_int`.** A corrupt `breaker.json` streak raised inside the except handler,
  escaping `dispatch()` and discarding an already-computed block.
- `--provider grok`; `bm_vault_digest` ranks GOAL in the injection mixer.

### 3.3 ledger.py (A was byte-identical to the base, so B's whole delta applies)

- **Receipt authority.** Only an executing tool (`_is_command_tool`: name or MCP leaf
  verb) mints a typed receipt. Before: `classify_receipt("WebSearch", "pytest status",
  "success")` and `("mcp__tasks__create", {"command": "pytest"})` both returned a green
  test receipt. Read-only heads (`echo test`, `cat test.log`), informational flags
  (`pytest --version`, `--collect-only`), exit-code laundering (`|| true`, `| tee`) and
  zero-test runs never pass; prose is a verdict only for `health`.
- **Evidence scoping.** `_receipts` matches the turn strictly (an unattributed receipt
  cannot substantiate another turn); `has_fresh_receipt` uses a cwd-wide mutation floor
  and only the newest receipt per class (a failing rerun revokes an earlier green);
  `_has_legacy_verification` ignores receipt-lane rows.
- **OS-level `_FileLock`** (`fcntl`/`msvcrt`), released by the kernel when the holder
  dies. The O_EXCL lockfile's 30s stale-reclaim window let one killed hook worker stall
  every later append past the 2s host deadline (B's `test_ledger_process_recovery.py`
  proves recovery across real processes). The `msvcrt` branch — the one the live
  estate runs — is exercised on every OS through a fake backend.

### 3.4 modules.py

- **Session-cwd path resolution.** `_under` / `_canonical_tree` /
  `_scaffold_artifact_label` resolve a relative edit target against `event.cwd`, never
  the hook process cwd (live measured 2026-08-07: a bare `pytest` from
  `~/.agents/harness` classified `Write notes.md` as tree `harness`). No base → fail
  closed.
- **FIX-N session-scoped capture nudge.** Facts come from sticky per-session flags
  stamped at `PostToolUse` (`any_mutation`, `canonical_edit`, `bm_write`); the bounded
  ledger window is only a fallback and carriers are never mixed. Live measured over
  271,720 ledger rows: 85% of canonical edits had left the 120-row window by Stop, and
  the project-keyed window let a sibling session's `write_note` mute this one.
  `"unknown"` sessions share no flag directory and keep a once-per-session cooldown.
- **Nudge fires on ANY mutation and spools a session note** (`state/bm-spool/`),
  flushed best-effort through the `basic-memory` CLI (`BASIC_MEMORY_CLI`) and retried
  on `SessionStart`; inert under pytest unless `HARNESS_BM_FLUSH_IN_TEST=1`. This
  inverts A's `silent_without_canonical_edit` expectation on purpose; the
  `GATE_CONTRACTS["basic_memory_nudge"]["fire_rate"]` text follows.
- **Vault digest (owner decision Q3/Q4, `memory-map.md` 2026-08-28).** `RecallModule`
  injects the slim `recall-digest.json` (UNTRUSTED) once on `SessionStart` and once on
  the first `UserPromptSubmit`; never walks the vault, never loads the keyword index for
  it.

### 3.5 recall_index.py

- `build_index` also writes `recall-digest.json` (top 16 by importance/mtime, no
  keyword arrays, cache paths excluded, redacted/bounded fields).
- `build_digest_from_index` / `--from-index [--digest-target]` rebuild the sidecar by
  streaming `notes[]` (64 KiB chunks, keywords popped before retention); fail-open on
  truncated/alien documents. B shipped no tests for the builder; eight were added.

## 4. B-side changes deliberately NOT carried (each with the reason)

| B-side change | reason |
|---|---|
| `dispatcher.py.orig` (562 lines) | `patch(1)` backup artifact, not source |
| `dispatcher.py`: `input_error: bool` + `reason_code="malformed_input"` for unparseable stdin | Same defect A already fixed as D010 `transport_error`, which additionally names the failure class in `failed_modules` (`_transport:malformed_json` / `_transport:non_object_payload`). Kept A's; the adopted degraded-health suite pins the D010 shape so the two cannot drift again |
| `adapters.py`: `_first_present`-based `tool.name/id/input` aliases | A has the equivalent (commit-era fix), with the `is not None` nuance that keeps an intentional empty `tool_input` from falling through to the alias |
| `redaction.py` comment-only delta | Verified: all 16 `_SECRET_PATTERNS` and `redact_text` source identical; the prose is written from the live tree's viewpoint ("this live tree was stale") and would be false in A |
| `modules.py`: deletion of the 3-line "a test existed for exactly this" comment in `SensitiveArtifactModule` | comment only |
| `modules.py` B@08-28 `rglob`-based vault digest | superseded on live itself by the 09-02 sidecar version (owner rule: never `rglob` the vault); the 09-02 version is what was ported |
| `tests/test_modules.py`: removal of `register_gate` from the module-order assertion | B lacked `RegisterGateModule`; A has it |
| `tests/test_modules.py`: removal of `test_sensitive_artifact_ignores_a_reentrant_subagent_stop`, `..._still_reports_a_fresh_subagent_stop`, `..._notice_never_demands_a_forbidden_action` | the behaviour is present in BOTH trees; dropping coverage is not an improvement |
| `tests/test_modules.py`: `PLACEHOLDER` → `EXAMPLE` marker rewording, `vault_root=` on one pre-existing test | cosmetic / unnecessary in the 09-02 design (the module never reads the vault) |
| `tests/test_dispatcher_degraded_health.py` theme 3 assertions (`malformed_input`) | adapted to A's D010 contract (see row 2) |
| B's copies of `install.py`, `injection_grammar.py`, `README.md`, `schemas/hook-event.schema.json`, `test_register_gate.py`, `test_install_deploy.py`, `test_injection_grammar.py`, `test_security_regressions.py`, `test_cov_ledger.py`, `test_cov_dispatcher_adapters.py`, `test_recall_index.py` (guard tests) | B is an older A (strict prefix / pre-`cf7d2cfa`); nothing B-side to carry |

## 5. Follow-ups filed (not built here)

- `cursor-provider-followup-2026-09-02.md` — no Cursor provider exists in the hook
  harness (either lineage); recorded, not built.
- `mcp-cursor-merge-lineage-2026-09-02.md` — `merge_generated_cursor_mcp.py` has
  diverged in BOTH directions between main and live; its surgical deploy is blocked
  until reconciled (found while building the deploy plan below).

## 6. Deploy plan for the owner (Windows box, repo checkout `~/source/ast-integrate`)

Direction: repo → live, the only direction that ends with one tested tree. The live
folder stays **harness-at-root** (`C:\Users\Prekzursil\.agents\harness`). Run
everything from the EDIT checkout named in `CLAUDE.md` (`~/source/ast-integrate`, on
this PR's branch or on main after merge). Never run these from a scratch checkout.

### 6.1 Pre-flight (read-only)

```powershell
cd C:\Users\Prekzursil\source\ast-integrate
git status --short --branch                       # clean, on the reunion branch / main
python -m pytest agent-self\harness\tests -q      # expect 926 passed, 1 skipped
python agent-self\harness\install.py --check      # drift report of the CURRENT live registration; read it, do not act yet
```

### 6.2 Timestamped backup (belt and braces; `--deploy` also backs up on its own)

```powershell
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$bk = "C:\Users\Prekzursil\.agents\backups\harness-reunion-$stamp"
New-Item -ItemType Directory -Force $bk | Out-Null
robocopy C:\Users\Prekzursil\.agents\harness "$bk\harness" /E /XD __pycache__ .pytest_cache backups /XF installed.json /NFL /NDL /NJH /NJS
robocopy C:\Users\Prekzursil\.agents\command-center "$bk\command-center" /E /NFL /NDL /NJH /NJS
Copy-Item C:\Users\Prekzursil\.claude\settings.json "$bk\settings.json"
Copy-Item C:\Users\Prekzursil\.codex\hooks.json     "$bk\codex-hooks.json"
"$bk"   # keep this path; it is the rollback source
```

Rollback = `robocopy "$bk\harness" C:\Users\Prekzursil\.agents\harness /E /PURGE` and
restore the two settings files. `install.py --deploy` ALSO writes its own copy to
`agent-self\harness\backups\deploy-<stamp>\harness` in the repo checkout (gitignored).

### 6.3 Exact file set that changes on live (43 managed files in the reunited tree)

Measured against the 2026-09-02 capture. **NEW (1):** `tests/test_deploy_command_center.py`.
**CHANGED (25):** `README.md`, `adapters.py`, `dispatcher.py`, `injection_grammar.py`,
`install.py`, `modules.py`, `recall_index.py`, `redaction.py`, `registration.py`,
`schemas/hook-event.schema.json`, `tests/conftest.py`, `tests/test_contract.py`,
`tests/test_cov_dispatcher_adapters.py`, `tests/test_cov_final.py`,
`tests/test_cov_ledger.py`, `tests/test_dispatcher_and_registration.py`,
`tests/test_dispatcher_degraded_health.py`, `tests/test_injection_grammar.py`,
`tests/test_install_deploy.py`, `tests/test_ledger_receipts_and_taint.py`,
`tests/test_modules.py`, `tests/test_native_events.py`, `tests/test_recall_index.py`,
`tests/test_register_gate.py`, `tests/test_security_regressions.py`.
**UNCHANGED (17):** `.gitignore`, `__init__.py`, `ledger.py` (reunited == live),
`models.py`, `schemas/hook-result.schema.json`, `storage.py`, `surface_reconciler.py`,
`tests/test_cov_install_small.py`, `tests/test_cov_modules_a.py`,
`tests/test_cov_modules_b.py`, `tests/test_cov_recall_injection.py`,
`tests/test_dispatcher_mixer_breaker.py`, `tests/test_fix_n_session_flags.py`,
`tests/test_install_reconciler.py`, `tests/test_ledger_process_recovery.py`,
`tests/test_storage_read_status.py`, `tests/test_surface_reconciler.py`.
**Live-only, left in place:** `dispatcher.py.orig` (harmless artifact; delete by hand if
wanted — the deployer never removes live files).

### 6.4 Deploy (CAS-lite, staged, atomic per file, parity-checked, receipted)

```powershell
cd C:\Users\Prekzursil\source\ast-integrate
python agent-self\harness\install.py --deploy --target harness          # prints {"status":"deployed", "count":..., "copied":[...], "backup":...}
python agent-self\harness\install.py --deploy --target command-center   # WORK-UNIT-CATALOG.json -> ~/.agents/command-center (the register gate reads it there)
python agent-self\harness\install.py --check                            # registration drift; then, if it reports managed drift:
python agent-self\harness\install.py                                    # rewrites the claude/codex hook documents (backs up first); Codex re-hashes -> review via /hooks in a fresh session
```

Abort conditions the deployer enforces on its own (no writes happen): lock held,
candidate does not compile, live changed between plan and write (CAS), post-write
parity mismatch (restores its backup). If `status` is anything but `deployed`, stop
and read the reason.

### 6.5 Live test commands to re-run (in the deployed harness-at-root layout)

```powershell
cd C:\Users\Prekzursil\.agents
python -m pytest harness\tests -q
```

Expected (measured in a simulated harness-at-root layout with the command-center
deployed beside it): **914 passed, 13 skipped, 0 failed**. The 13 skips are named:
11 `test_register_gate.py` cases that read the REPO register
(`<parent-of-.agents>\command-center\WORK-UNIT-CATALOG.json`), 1
`test_deploy_command_center.py` producibility probe that needs the repo-side source
beside `install.py`, and the pre-existing legacy-capture-hook skip. Any FAILED line is
new information — roll back (6.2) and report it. If `~/.agents/command-center` was not
deployed, 13 `test_register_gate.py` cases fail because the gate finds no catalog; that
is the missing 6.4 step, not a harness defect.

Then rebuild the slim digest once so the first session after deploy has it:

```powershell
python C:\Users\Prekzursil\.agents\harness\recall_index.py --from-index C:\Users\Prekzursil\.agents\state\harness\recall-index.json
```

### 6.6 Surgical deploy of the three `.agents/scripts` files with their tests

Measured by overlaying main's copies onto the live capture's `scripts/` + `tests/` and
running the LIVE test files (`test_mcp_control_plane.py`, `test_mcp_fleet_supervisor.py`;
the one pre-existing live failure `test_cursor_basic_memory_uses_session_proxy_not_raw_url`
probes a Windows-only path and is unrelated):

| file | main vs live | live tests with main's copy | verdict |
|---|---|---|---|
| `mcp_fleet_supervisor.py` + `tests/test_mcp_fleet_supervisor.py` | main adds the fleet-total ceiling (`totalOverBudget`, `39accd83`); live's test file is a strict subset of main's | live suite green; main's 6 fleet tests green against the live tree | **deploy both** |
| `merge_generated_claude_mcp.py` | main adds `type: "http"` so HTTP servers mount (`abe34c52`) | live suite green | **deploy** |
| `merge_generated_cursor_mcp.py` | **diverged both ways**: main = registry-authoritative `CURSOR_ENABLED_SERVERS` + `--check` (`ed867a45`); live = two-phase attachment (`CURSOR_SAFE_DEFAULT_ATTACHED_SERVERS`, `--attach-all-safe`, `--approvals-file` gate) | **26 live tests fail** with main's copy (27 minus the Windows-path probe that fails on Linux anyway); **6 main tests fail** with live's copy | **BLOCKED** — see `mcp-cursor-merge-lineage-2026-09-02.md`; do not copy either way |

Its own test, `tests/test_mcp_control_plane.py`, has also diverged both ways (live
carries ~300 lines of two-phase/approval tests and the owner's 2026-08-28
"never rotate; manifest stays deleted" expectation), so it is NOT part of this deploy;
the fleet-supervisor test is.

```powershell
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$bk = "C:\Users\Prekzursil\.agents\backups\scripts-reunion-$stamp"
New-Item -ItemType Directory -Force "$bk\scripts","$bk\tests" | Out-Null
Copy-Item C:\Users\Prekzursil\.agents\scripts\mcp_fleet_supervisor.py,C:\Users\Prekzursil\.agents\scripts\merge_generated_claude_mcp.py "$bk\scripts\"
Copy-Item C:\Users\Prekzursil\.agents\tests\test_mcp_fleet_supervisor.py "$bk\tests\"

cd C:\Users\Prekzursil\source\ast-integrate
Copy-Item .agents\scripts\mcp_fleet_supervisor.py        C:\Users\Prekzursil\.agents\scripts\
Copy-Item .agents\scripts\merge_generated_claude_mcp.py  C:\Users\Prekzursil\.agents\scripts\
Copy-Item .agents\tests\test_mcp_fleet_supervisor.py     C:\Users\Prekzursil\.agents\tests\

cd C:\Users\Prekzursil\.agents
python -m pytest tests\test_mcp_fleet_supervisor.py tests\test_mcp_control_plane.py -q   # expect: fleet 6 passed; control-plane unchanged from your pre-deploy baseline
python scripts\merge_generated_claude_mcp.py                                             # dry run (no --write): review the rendered .claude.json diff before any --write
```

Note also that live's `mcp_control_plane.py` is AHEAD of main (`REMOTE_REQUIRED_SERVERS`,
https-only for credential-bearing http servers, `ctx7sk-`/`fc-` secret prefixes) — the
repo needs that folded back in a separate change; nothing here touches it.
