# Provider-Neutral AI Harness Tier-1 Implementation Plan

> **Status: SUPERSEDED after Plan Review Gate FAIL.** Use
> `2026-08-29-provider-neutral-ai-harness-implementation_v2.md`. This file is
> retained as the audit trail and must not be executed.

> **For Claude:** REQUIRED SUB-SKILL: use the owner-selected execution method
> after this plan passes the mandatory plan-review gate. No implementation may
> begin from this draft.

**Goal:** Deliver one transactional, loss-aware activation path for the
canonical `.agents` control plane and the Claude, Codex, and Cursor consumers.

**Architecture:** Extend the existing `agents.json`, MCP validation, harness
storage/redaction/ledger, and provider mergers. Add a small `control_plane`
package for inventory, grants, transactions, receipts, adapters, and status.
Existing writers become non-writing libraries; `sync_shared_state.ps1` remains
the compatibility entry point and delegates to one controller.

**Tech stack:** Python 3.14 stdlib, pytest, pytest-cov, PowerShell 7, existing
JSON/TOML/YAML parsers and native consumer CLIs. No daemon, database, new memory
engine, new marketplace, or orchestration runtime.

**Design:** `docs/plans/2026-08-29-provider-neutral-ai-harness-design.md`

---

## Scope

### Tier-1 deliverable

- coverage SSOT and tests-first scaffold;
- destructive-sync hard stop;
- canonical topology/baseline/inventory/provenance;
- redacted bounded telemetry;
- deployment lock, CAS, pre-images, immutable receipts, journal/controller;
- extended backward-compatible `agents.json`;
- mediated adapter grants;
- canonical rules bootstrap;
- Claude, Codex, Cursor adapters;
- read-only status/CLI;
- one activation entry point and writer retirement.

### Explicitly deferred

- Hermes installation/canary;
- Grok, Goose, Gemini, Antigravity, OpenCode, Fabric, Aider adapters;
- donor discovery and automatic scheduling;
- dashboard UI;
- hook promotion from advisory to enforcement;
- plugin disablement or capability removal.

Each deferred milestone requires a fresh plan and plan-review gate after the
Tier-1 release receipt is green.

## Measured starting state

- `.agents\rules` contains three files and is ignored by `.agents\.gitignore`.
- `.agents\hooks` does not exist.
- `.agents\skills\DEPLOYED-MANIFEST.json` exists but is incomplete.
- `.agents\harness\reconcile-baseline.json` is absent.
- `.agents\.coverage-thresholds.json` is absent.
- `scripts\sync-skills.ps1` defaults can resolve source and destination to the
  same live vault, then remove the target before copying.
- `mcp_control_plane.py` accepts only `claude` and `codex` targets.
- Cursor is a six-server filtered Claude projection.
- Claude HTTP rendering omits the `type: http` field expected by its test.
- `sync_shared_state.ps1` performs several independent live writes without an
  estate transaction.
- The repository has unrelated dirty/untracked work. Every commit in this plan
  stages exact declared paths only.

## Global implementation rules

1. TDD is mandatory: write one failing test, run it and observe the intended
   failure, add minimum implementation, rerun green, then refactor.
2. No test opens or modifies live consumer config, secrets, sessions, logs, or
   Basic Memory. Use `tmp_path` fixtures.
3. Only the interactive orchestrator commits. Subagents report diffs and
   receipts; background/headless agents never commit.
4. Run one pytest process at a time.
5. Do not start agent workers, native runtime smokes, or apply when free RAM is
   below 8 GiB.
6. Never run more than one `cursor-agent`.
7. No native smoke may log in/out, refresh/revoke/create sessions, rotate keys,
   install plugins, send messages, or mutate remote state.
8. No bulk recursive scan of the home directory, scratch clones, or Basic
   Memory vault.
9. Every status claim needs a disk artifact and executable receipt.
10. Coverage command comes only from `.coverage-thresholds.json`.

## Observational method

**Monitored metrics**

- free RAM before agents/smokes/apply;
- pytest duration/failures and coverage;
- transaction state, rollback result, and active writer count;
- peak control-plane working set;
- capability-delta unexplained-loss count;
- raw synthetic-secret match count.

**Trigger-action responses**

| Trigger | Binding action |
|---|---|
| Free RAM below 8 GiB | Skip agents/smokes/apply; continue read-only or stop |
| Two consecutive subagent aborts | Stop fan-out; continue serially in-session |
| Same hypothesis fails twice | Stop retrying; re-decompose or escalate |
| Any raw synthetic secret reaches output/disk | Halt wave; remove artifact safely; repair redaction |
| Any unexplained capability loss | Block apply; require owner disposition |
| CAS conflict persists past retry budget | Mark deferred; do not overwrite |
| Missing/corrupt rollback pre-image | `FAILED_TO_RUN`; no apply or partial restore |
| Any live session/auth mutation | Roll back immediately and halt |
| New always-on process | Reject change |
| Test exceeds expected runtime by 2× | Stop broader suite; investigate smallest failing scope |

---

## Wave 0 — coverage and scaffold

### Task 0: Establish the coverage SSOT

**Files**

- Create: `.coverage-thresholds.json`
- Create: `control_plane/__init__.py`
- Create: `tests/control_plane/__init__.py`
- Create: `tests/control_plane/conftest.py`
- Create: `tests/control_plane/test_coverage_ssot.py`

**Step 1 — RED**

Write `test_thresholds_file_declares_runnable_enforcement_command`. It parses
the project-root file and requires 100% lines/branches/functions/statements for
the new `control_plane` package plus:

```text
python -m pytest -q tests/control_plane --cov=control_plane --cov-branch --cov-fail-under=100
```

Run:

```powershell
python -m pytest -q tests/control_plane/test_coverage_ssot.py
```

Expected: FAIL because `.coverage-thresholds.json` is absent.

**Step 2 — GREEN**

Create the thresholds file and package scaffold. `conftest.py` adds the project
root and `scripts` to `sys.path` and redirects all state roots to `tmp_path`.

**Step 3 — VERIFY**

Run the same node; expect PASS. Read the enforcement command back from JSON and
run it; expect PASS with an empty package counted correctly.

**Step 4 — COMMIT**

Stage only the five files. Message: `test: establish control-plane coverage gate`.

---

## Wave 1 — freeze unsafe state

Tasks 1, 2, and 4 touch disjoint files and may be authored independently, but
tests run serially. Task 1 lands first because it removes the highest-risk
footgun.

### Task 1: Hard-stop source-equals-destination skill sync

**Files**

- Modify: `scripts/sync-skills.ps1`
- Create: `tests/control_plane/test_sync_skills_guard.py`
- Create: `tests/control_plane/fixtures/skills-same-root/example/SKILL.md`

**RED**

Create a fixture where source and destination resolve to the same skills tree.
Run the script with explicit fixture paths and assert:

- non-zero exit;
- `FAILED:sync-skills source equals destination`;
- fixture file still exists and hash is unchanged.

Run:

```powershell
python -m pytest -q tests/control_plane/test_sync_skills_guard.py
```

Expected: FAIL against current remove-then-copy behavior.

**GREEN**

Resolve all source/destination paths before any write. Refuse equality,
parent/child overlap, and reparse-point aliasing. Add `-AuditOnly`; make
unscoped execution audit-only until the transaction controller replaces it.
Retain the existing `-Skill`/`-Prune` conflict guard.

**VERIFY**

Run the test three times. No invocation may use live defaults.

**COMMIT**

Exact paths only. Message: `fix: block destructive live skill self-sync`.

### Task 2: Correct canonical topology rules

**Files**

- Modify: `.gitignore`
- Create: `tests/control_plane/test_repo_topology.py`

**RED**

Require:

- `rules/` not ignored;
- `staging/`, `state/`, `deploy-backups/` ignored;
- `releases/` and `provenance/` tracked;
- `local.json` ignored;
- canonical rules directory exists.

Expected failure: `rules/` is ignored and `staging/` is missing.

**GREEN**

Remove stale rules-junction ignore text; add `staging/`; document tracked vs
local control-plane paths.

**VERIFY**

```powershell
python -m pytest -q tests/control_plane/test_repo_topology.py
```

**COMMIT**

Message: `chore: define canonical control-plane topology`.

### Task 3: Make missing baselines honest and capture link topology

**Files**

- Create: `control_plane/baseline.py`
- Create: `tests/control_plane/test_baseline.py`
- Modify: `harness/install.py`
- Modify: relevant existing reconciler tests only if expected status changes

**RED**

Tests:

- missing baseline → `FAILED_TO_RUN`, not healthy;
- malformed/shapeless baseline → distinct `FAILED_TO_RUN`;
- expected link chain records link type, target, attributes;
- rules and skills topology are separate records.

**GREEN**

Add tri-state baseline reads and bounded link-topology capture, reusing
`harness.surface_reconciler` reparse detection. Preserve existing nightly
fail-open execution while making its reported state honest.

**VERIFY**

```powershell
python -m pytest -q tests/control_plane/test_baseline.py
python -m pytest -q harness/tests/test_install_reconciler.py
```

**COMMIT**

Message: `fix: surface missing baselines and capture link topology`.

### Task 4: Build redacted bounded inventory and provenance

**Files**

- Create: `control_plane/inventory.py`
- Create: `control_plane/provenance.py`
- Create: `tests/control_plane/test_inventory.py`

**RED**

Tests:

- detector fires on known-present and known-missing fixtures;
- synthetic token never appears in artifact;
- inventory is bounded under 1 MiB;
- unknown origin becomes `unknown-base`;
- generated consumer output is rejected as donor input;
- scratch/secondary worktrees are excluded by default.

**GREEN**

Reuse `harness.redaction` and `surface_reconciler.comparison_hash`. Record
structural keys, counts, hashes, ownership, and provenance—never config bodies
or values.

**VERIFY**

```powershell
python -m pytest -q tests/control_plane/test_inventory.py
```

**COMMIT**

Message: `feat: add redacted control-plane inventory`.

**Wave 1 gate**

```powershell
python -m pytest -q tests/control_plane
python -m pytest -q tests/test_mcp_control_plane.py
```

---

## Wave 2 — safety and transaction core

### Task 5: Add one redacted, locked, rotating telemetry writer

**Files**

- Create: `control_plane/telemetry.py`
- Create: `tests/control_plane/test_telemetry.py`

**RED**

Process-level tests:

- two writers never interleave records;
- synthetic secrets are structurally redacted;
- rotation and retention bound disk use;
- dropped events are counted;
- each hook declares failure class and timeout action.

Run each safety/concurrency case three times.

**GREEN**

Reuse the harness lock/redaction primitives. Do not create a daemon. Emit
bounded schema-allowlisted records only.

**VERIFY**

```powershell
python -m pytest -q tests/control_plane/test_telemetry.py
```

**COMMIT**

Message: `feat: add bounded redacted control-plane telemetry`.

### Task 6: Add deployment-lock ownership and safe stale recovery

**Files**

- Create: `control_plane/locking.py`
- Create: `tests/control_plane/test_locking.py`
- Modify: `harness/install.py`
- Modify: exact existing lock tests whose fixture assumes timestamp-only expiry

**RED**

- old lock with live PID is not stolen;
- dead/recycled PID can be recovered only by journal recovery;
- corrupt lock → `FAILED_TO_RUN`;
- break-lock action records host, PID, process start, transaction, reason.

**GREEN**

Delegate existing install lock behavior to the new helper. Only recovery may
break a stale lock; no general force option.

**VERIFY**

```powershell
python -m pytest -q tests/control_plane/test_locking.py
python -m pytest -q harness/tests/test_install_deploy.py -k "lock"
```

**COMMIT**

Message: `fix: make deployment lock recovery process-aware`.

### Task 7: Add bounded CAS and non-atomic fallback

**Files**

- Create: `control_plane/cas.py`
- Create: `tests/control_plane/test_cas.py`
- Modify: `harness/install.py`

**RED**

- transient conflict succeeds within a fixed retry budget;
- persistent conflict writes nothing and returns deferred;
- same-volume atomic replacement is preferred;
- forced non-atomic fallback verifies temp and target hashes or restores;
- temporary files disappear after abort.

**GREEN**

Extract a bounded optimistic-CAS helper with backoff. Require consumer idle when
continuous external writes prevent progress. Never loop indefinitely.

**VERIFY**

```powershell
python -m pytest -q tests/control_plane/test_cas.py
python -m pytest -q harness/tests/test_install_deploy.py -k "cas"
```

**COMMIT**

Message: `feat: add bounded compare-and-swap deployment`.

### Task 8: Implement protected rollback pre-images

**Files**

- Create: `control_plane/preimage.py`
- Create: `tests/control_plane/test_preimage.py`

**RED**

- missing/truncated/hash-mismatched pre-image → `FAILED_TO_RUN`;
- owner-only ACL requirement is enforced;
- exact file metadata and expected link type/target are captured;
- pre-image bytes never appear in logs/diffs/receipts/model output;
- mixed config rollback applies an inverse managed-subtree patch;
- whole-file restore is allowed only when the live hash still equals the known
  post-apply hash.

**GREEN**

Create a content-addressed, local-only rollback store under
`deploy-backups/<transaction>`. Add bounded retention without deleting the
active/last-known-good transaction.

**VERIFY**

```powershell
python -m pytest -q tests/control_plane/test_preimage.py
```

Run rollback/secret cases three times.

**COMMIT**

Message: `feat: add protected transactional pre-images`.

### Task 9: Implement immutable receipt chains

**Files**

- Create: `control_plane/receipts.py`
- Create: `tests/control_plane/test_receipts.py`

**RED**

- create-once rejects different bytes at same path;
- success requires verification evidence;
- rollback-complete requires restored-state evidence;
- chain reconstruction detects missing/forked/mismatched links;
- receipts contain no config body, secret, session, or secret path.

**GREEN**

Use exclusive create and content hashes for committed, failed,
rollback-started, rollback-completed, and failed-to-run records. Reconstruct
chain head from versioned receipts; local active-head state is only a cache.

**VERIFY**

```powershell
python -m pytest -q tests/control_plane/test_receipts.py
```

**COMMIT**

Message: `feat: add create-once release receipts`.

### Task 10: Implement journal and transaction controller

**Files**

- Create: `control_plane/journal.py`
- Create: `control_plane/controller.py`
- Create: `tests/control_plane/test_controller.py`

**RED**

- illegal state transitions refused;
- new transaction blocked until interrupted journal recovered;
- fault at every state restores all touched targets;
- partial consumer success never becomes estate success;
- stale-lock recovery follows journal;
- controller hash mismatch refuses apply;
- controller rollback uses the prior known-good controller;
- mediated capabilities are required for every side effect.

**GREEN**

Implement the design state machine, serial apply/verify, restore-all behavior,
controller self-integrity check, and known-good recovery launcher. Split journal
and controller into separate commits if controller exceeds ~400 lines.

**VERIFY**

```powershell
python -m pytest -q tests/control_plane/test_controller.py
```

Run fault-injection paths three times.

**COMMIT**

Message: `feat: add transactional control-plane controller`.

---

## Wave 3 — schema, grants, and rules

### Task 11: Extend `agents.json` compatibly

**Files**

- Modify: `agents.json`
- Modify: `scripts/mcp_control_plane.py`
- Modify: `scripts/validate_mcp_control_plane.py`
- Create: `control_plane/schema.py`
- Create: `tests/control_plane/test_schema.py`

**RED**

- Cursor is a first-class consumer;
- every declared consumer is validated and counted;
- current schema keys round-trip unchanged;
- installed `agents status/doctor` accept the extension read-only;
- floating managed dependencies are reported and cannot newly activate;
- `integrations.enabled` remains empty.

**GREEN**

Extend the existing registry in place. If installed `agents` rejects unknown
keys, use one hash-referenced sibling manifest as a compatibility projection
without introducing a second authority.

**VERIFY**

```powershell
python -m pytest -q tests/control_plane/test_schema.py
python -m pytest -q tests/test_mcp_control_plane.py
```

**COMMIT**

Stage registry, schema, validator, and tests together. Message:
`feat: add consumer-aware control-plane schema`.

### Task 12: Add mediated adapter capabilities

**Files**

- Create: `control_plane/adapters/__init__.py`
- Create: `control_plane/adapters/base.py`
- Create: `control_plane/adapters/grants.py`
- Create: `tests/control_plane/test_adapter_contract.py`

**RED**

- all eight adapter operations required;
- raw file/subprocess/socket calls unavailable to adapter implementation;
- mediator refuses unlisted path, argv, host, env name, reparse point, or
  elevation;
- env values never enter inventory;
- required unsupported semantics fail only affected consumer;
- native smoke session mutations are refused.

**GREEN**

Implement controller-owned capability handles and grant dataclasses from the
design tables. Adapters request effects through the mediator only.

**VERIFY**

```powershell
python -m pytest -q tests/control_plane/test_adapter_contract.py
```

**COMMIT**

Message: `feat: mediate provider adapter capabilities`.

### Task 13: Bootstrap canonical rules without copying blindly

**Files**

- Create: `control_plane/rules.py`
- Create: `tests/control_plane/test_rules_bootstrap.py`
- Modify: `scripts/sync-rules.ps1`
- Create/modify: `rules/**` only after owner adjudication

**RED**

- recursive copy is refused;
- normalized duplicates and true conflicts are distinct;
- unique rules are retained;
- rules link topology matches baseline;
- current deploy direction is disabled;
- unresolved conflict produces `ACTION_REQUIRED`.

**GREEN**

Hash-compare the three-file `.agents\rules`, `.claude\rules`, Codex rules, and
tracked repository rules. Generate a decision queue; do not choose by timestamp
or location. Commit tooling first. Commit adjudicated canonical rule content
separately after owner decisions.

**VERIFY**

```powershell
python -m pytest -q tests/control_plane/test_rules_bootstrap.py
```

**COMMIT**

Message 1: `feat: add canonical rules reconciliation`.  
Message 2 after adjudication: `chore: establish canonical shared rules`.

---

## Wave 4 — Tier-1 adapters

Tasks 14–16 have disjoint implementation files and may be authored in parallel,
but tests/native smokes remain serial.

### Task 14: Claude adapter and HTTP renderer repair

**Files**

- Create: `control_plane/adapters/claude.py`
- Create: `tests/control_plane/test_adapter_claude.py`
- Modify: `scripts/merge_generated_claude_mcp.py`
- Modify: exact existing renderer tests if only fixtures need adaptation

**RED**

First run the already-failing:

```powershell
python -m pytest -q tests/test_mcp_control_plane.py::test_claude_http_renderer_declares_http_transport
```

Then tests for managed-subtree-only changes, no unreported `pop`, inverse
rollback, secret exclusion, idempotence, CAS conflict, ACL/encoding
preservation, and session-neutral verification.

**GREEN**

Emit `type: http`; turn the merger into a non-writing render library; implement
Claude adapter through mediator/controller. Never test against live
`.claude.json`.

**VERIFY**

```powershell
python -m pytest -q tests/control_plane/test_adapter_claude.py
python -m pytest -q tests/test_mcp_control_plane.py -k "claude"
```

**COMMIT**

Commit HTTP fix separately, then adapter conversion.

### Task 15: Codex adapter and safety assertions

**Files**

- Create: `control_plane/adapters/codex.py`
- Create: `tests/control_plane/test_adapter_codex.py`
- Modify: `scripts/merge_generated_codex_mcp.py`

**RED**

- marker edit preserves all unmanaged settings/comments/order;
- `git-always-force-push=true` produces owner impact decision, never silent
  preservation or mutation;
- native memories remain isolated caches per approved policy;
- second render zero-diff;
- BOM/encoding preserved;
- session-neutral native probe only.

**GREEN**

Turn merger into a non-writing library. Apply only managed markers and approved
asserted settings via controller.

**VERIFY**

```powershell
python -m pytest -q tests/control_plane/test_adapter_codex.py
python -m pytest -q tests/test_mcp_control_plane.py -k "codex"
```

**COMMIT**

Message: `feat: add transactional Codex adapter`.

### Task 16: Cursor first-class six-MCP policy

**Files**

- Create: `control_plane/adapters/cursor.py`
- Create: `tests/control_plane/test_adapter_cursor.py`
- Modify: `scripts/merge_generated_cursor_mcp.py`
- Modify: `agents.json`

**RED**

- Cursor target used instead of Claude target;
- six-server grant is registry data, not Python constant;
- every parked/denied/plugin-managed exclusion has stable delta/removal reason;
- `${env:NAME}` rendering preserved;
- no more than one session-neutral Cursor process;
- no unreported capability loss.

**GREEN**

Move the locked six-server policy into canonical consumer grants and remove the
hard-coded keep-list in the same commit. Preserve the exact six names.

**VERIFY**

```powershell
python -m pytest -q tests/control_plane/test_adapter_cursor.py
python -m pytest -q tests/test_mcp_control_plane.py -k "cursor"
```

**COMMIT**

Stage adapter, merger, registry, and tests together. Message:
`feat: make Cursor a first-class MCP consumer`.

---

## Wave 5 — status and activation convergence

### Task 17: Build canonical CLI/status projection

**Files**

- Create: `control_plane/status.py`
- Create: `control_plane/cli.py`
- Create: `tests/control_plane/test_status.py`
- Modify/create: only the minimal existing `agents` command shim required to
  expose `agents control-plane`

**RED**

- per-capability freshness turns old pass into `STALE`;
- degraded requires fresh executable compensating path;
- all aggregation precedence cases;
- command-specific exit codes;
- operation status distinct from estate status;
- approval/recovery states and commands;
- output bounded under 1 MiB;
- compatibility aliases return identical envelope/exit code/help intent.

**GREEN**

Implement read-only status over receipts/telemetry first. Add mutation subcommands
only as controller calls with exact approval artifacts.

**VERIFY**

```powershell
python -m pytest -q tests/control_plane/test_status.py
```

**COMMIT**

Message: `feat: expose receipt-backed control-plane status`.

### Task 18: Converge to one activation entry point

**Files**

- Modify: `scripts/sync_shared_state.ps1`
- Modify: three provider merger CLIs
- Modify: `scripts/harness-audit.js`
- Modify/classify: `skills/DEPLOYED-MANIFEST.json`
- Create: `tests/control_plane/test_writer_inventory.py`

**RED**

- exactly one apply-capable entry point;
- writers retired ≥ writers added;
- direct merger `--write` refused;
- link manager journaled/restorable;
- deployed manifest is projection or retired;
- presence score cannot claim runtime acceptance;
- activation count and always-on process count captured before/after.

**GREEN**

Make `sync_shared_state.ps1` delegate to the controller while preserving its
documented compatibility surface. Existing mergers render only. Rename/label
the presence score honestly. Do not touch live configs until a dry-run and
rollback preview both validate.

**VERIFY**

Small:

```powershell
python -m pytest -q tests/control_plane/test_writer_inventory.py
```

Tier-1 gate:

```powershell
python -m pytest -q tests/control_plane harness/tests
python scripts/validate_mcp_control_plane.py --agents-config agents.json
```

Then run the enforcement command from `.coverage-thresholds.json`.

**COMMIT**

One exact-path commit after rollback dry-run. Message:
`refactor: converge harness activation through one controller`.

---

## Tier-1 acceptance

All are blocking:

- coverage command from `.coverage-thresholds.json` passes;
- control-plane and existing harness/MCP suites pass;
- Claude, Codex, Cursor staged native parsers pass;
- synthetic secret raw matches = 0 outside protected pre-image fixtures;
- unexplained capability loss = 0;
- fault injection before/after every activation stage restores pre-images;
- exactly one activation entry point;
- net always-on processes = 0;
- no session/auth mutation;
- no credential rotation;
- peak added working set ≤2 GiB;
- no more than one `cursor-agent`;
- committed, disk-reverified release receipt exists;
- all unrelated pre-existing dirty files remain untouched.

## Follow-on milestones

After Tier 1, create separately gated plans:

1. Hermes canary and graduation evaluation.
2. Secondary consumer adapters, one at a time.
3. Donor discovery/quarantine/reconciliation.
4. Compatibility aliases and canonical governance workflow.
5. Read-only dashboard projection.

## Execution handoff

After the plan-review gate passes, ask the owner to choose:

1. **Metaswarm orchestrated** — per-work-unit implement → validate →
   adversarial review → interactive commit.
2. **Subagent-driven** — fresh subagent per task, interactive review/commit.
3. **Parallel session** — execute the approved plan in a separate session with
   checkpoints.

No execution method is selected automatically.
