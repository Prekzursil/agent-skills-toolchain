# Provider-Neutral AI Harness Tier-1 Implementation Plan v2

> **For Claude:** REQUIRED SUB-SKILL: use the owner-selected execution method
> only after this plan passes the mandatory plan-review gate.

**Goal:** Deliver one transactional, loss-aware activation path for the
canonical `.agents` control plane and complete skill/rule/hook/MCP/memory
conformance for Claude, Codex, and Cursor.

**Architecture:** Extend existing validation, storage, redaction, ledger,
install, and merger primitives. Add one `control_plane` Python package and one
estate-owned `agents-cp` CLI. Do not shadow or modify the third-party `agents`
binary. Existing activation writers become read-only renderers or are retired.

**Tech stack:** Python 3.14, pytest, coverage.py/pytest-cov, PowerShell 5/7
compatibility, Windows `icacls.exe`, native consumer CLIs. No daemon, database,
new memory engine, marketplace, or orchestration runtime.

**Design:** `docs/plans/2026-08-29-provider-neutral-ai-harness-design.md`

---

## 0. Scope, authority, and safety

### Tier-1 only

Tier 1 covers `.agents` plus Claude, Codex, and Cursor. Hermes, Grok, Goose,
Gemini, Antigravity, OpenCode, Fabric, Aider, discovery automation, and the
dashboard are follow-on plans.

### Workspace boundary

- All implementation, tests, commits, and activation originate only from the
  primary `C:\Users\Prekzursil\.agents` worktree.
- Do not create, edit, commit, or deploy from `source\agent-skills-toolchain`,
  `source\ast-patch167`, `_wu*`, `_verify*`, Cursor-managed worktrees, or any
  other secondary clone/worktree.
- Secondary roots may be inventoried read-only and classified as donor,
  scratch, archive, linked worktree, or retained independent repository.
- The external `agents` CLI and its commands remain untouched.

### Commit/push boundary

- Subagents and background/headless sessions never commit.
- The interactive orchestrator commits only after explicit owner authorization
  in the execution session and stages exact declared paths.
- Never use `--no-verify`.
- Never force-push.
- Never push unless the owner separately requests it.

### TDD and live-state boundary

1. Write one focused test.
2. Run it and observe the intended RED failure.
3. Add minimum implementation.
4. Run GREEN and the named regression test.
5. Review; only then request/perform an authorized exact-path commit.

Tests use `tmp_path` estates. No test reads or writes live credentials, sessions,
consumer configs, logs, Basic Memory vault, or remote state.

### Resource boundary

- One pytest process at a time.
- No agent worker/native smoke/apply below 8 GiB free RAM.
- No more than one `cursor-agent`.
- Native smokes run serially.
- Peak added control-plane working set ≤2 GiB.
- Existing 6 GiB total idle MCP private-bytes ceiling remains.
- No broad recurring scans; status output ≤1 MiB.

### Monitored triggers

| Trigger | Action |
|---|---|
| Free RAM below 8 GiB | read-only work only; no worker/smoke/apply |
| Two subagent aborts | stop fan-out; continue serially |
| Two failures of one hypothesis | re-decompose; do not retry unchanged |
| Raw synthetic secret outside protected pre-image fixture | halt wave and repair redaction |
| Any unapproved capability removal/expansion | block apply |
| CAS budget exhausted | defer; never overwrite |
| Missing/corrupt pre-image or receipt | `FAILED_TO_RUN` |
| Session/auth mutation | rollback and halt |
| New always-on process | reject |
| Test runtime >2× baseline | stop broad suite; isolate |

---

## Wave A — gates and immediate footguns

### WU-A1: Establish enforceable coverage SSOT

**Files**

- Create: `.coverage-thresholds.json`
- Create: `.coveragerc`
- Create: `scripts/run_control_plane_coverage.py`
- Create: `control_plane/__init__.py`
- Create: `tests/control_plane/__init__.py`
- Create: `tests/control_plane/conftest.py`
- Create: `tests/control_plane/test_coverage_ssot.py`

**RED**

Test that the thresholds file and runner are absent, then require:

- enforceable metrics: lines and branches only;
- 100% for new `control_plane` Python;
- 100% for touched `harness/install.py` and touched MCP renderer/validator
  modules;
- explicit behavior-test exemptions for PowerShell line coverage;
- exact documented exclusions for `install.py`'s package-import fallback and
  module main guard only;
- phase-aware source activation so a wave is not failed by source files that
  no work unit has touched yet;
- one runnable `enforcement.command`.

Run:

```powershell
python -m pytest -q tests/control_plane/test_coverage_ssot.py
```

Expected: FAIL because the SSOT/runner is absent.

**GREEN**

The runner accepts `--phase wave-a|wave-b|wave-c|wave-d|final` and executes:

- `tests/control_plane`;
- `tests/test_mcp_control_plane.py`;
- affected `harness/tests`;
- coverage include filters for `control_plane/**`, `harness/install.py`,
  `scripts/mcp_control_plane.py`, `scripts/validate_mcp_control_plane.py`, and
  three `merge_generated_*_mcp.py` modules.

Only source groups owned by that phase or an earlier phase enter that phase's
coverage denominator. The final phase activates every touched Python module;
an inactive group can never yield final success. It checks line+branch totals
per declared source group. `.coveragerc` excludes only the exact unreachable
dual-import and `if __name__ == "__main__"` patterns, and a test rejects broader
exclusions. PowerShell files list mandatory behavior tests instead of fake line
metrics. Import
`control_plane` in the first test so “no data collected” cannot pass.

**VERIFY**

Run the enforcement command read back from JSON; record pytest, coverage, and
pytest-cov versions.

Wave-A preflight also proves Python 3.14, pytest, coverage.py, pytest-cov,
`pwsh.exe`, and `node` are installed, and records free RAM. Missing tooling is
`FAILED_TO_RUN` before dependent work begins.

**Commit boundary:** exact declared files, owner-authorized.

### WU-A2: Freeze unsafe skill deployment until transaction replacement

**Files**

- Modify: `scripts/sync-skills.ps1`
- Create: `control_plane/guards.py`
- Create: `tests/control_plane/test_sync_skills_guard.py`
- Create: fixture `tests/control_plane/fixtures/skills-sync/**`

**RED**

Fixture tests prove source==destination, parent/child overlap, and reparse
alias refuse before delete and preserve hashes. A separate test proves every
donor/repo→live deployment returns `ACTION_REQUIRED` during the Phase-0 freeze,
writes nothing, and names the transaction-controller replacement. `-Prune`
remains prohibited.

**GREEN**

Add resolved-path guard and an estate command classifier that flags external
donor deploy scripts targeting live `.agents`. Make this script audit/stage
only until WU-E4 activates the controller. Do not edit secondary clones.
Document the temporary impact explicitly: existing live skills continue to
work; new/updated skills cannot activate during the freeze and remain staged.
Document the residual external-script risk in status until clone adjudication.

**VERIFY**

```powershell
python -m pytest -q tests/control_plane/test_sync_skills_guard.py
```

Run fixture cases three times; never invoke live defaults.

**Commit boundary:** exact declared paths.

### WU-A3: Fix topology without breaking Grok projection

**Files**

- Modify: `.gitignore`
- Create: `tests/control_plane/test_repo_topology.py`

**RED**

Require:

- canonical `rules-canonical/` tracked;
- generated Grok `rules/`, `staging/`, `state/`, `deploy-backups/`, `local.json`
  ignored;
- `releases/` and `provenance/` tracked;
- a fixture Grok projection remains under 10,000 chars; `*.bak*` is classified
  scratch and excluded. This test never reads the gitignored live `rules/`
  directory.

**GREEN**

Add `rules-canonical/` and `staging/` policy; retain `rules/` ignore.

**VERIFY**

```powershell
python -m pytest -q tests/control_plane/test_repo_topology.py
```

**Commit boundary:** `.gitignore` + test only.

### WU-A4: Freeze clone and active dependency provenance

**Files**

- Create: `control_plane/provenance.py`
- Create: `tests/control_plane/test_provenance.py`
- Create after owner review: `provenance/*.lock.json`

**RED**

Tests require classification for every discovered relevant clone without
entering secondary worktrees; unknown base → `ACTION_REQUIRED`; floating
`latest`, branch-head, unversioned package/image/plugin stays active but cannot
newly activate through the controller.

**GREEN**

Record origin, classification, immutable revision, digest, publisher/license,
asset class, last-imported upstream hash, current canonical local hash,
supported consumers, capability requirements, maturity status, review
date/update policy, local customization state, and review status. Inventory exact installed
versions/digests for active native/plugin/package/container dependencies.
Capture the initial `git status --porcelain=v2` path/status set and digest as the
baseline used by final “unrelated dirty files unchanged” verification; never
persist file contents.

**VERIFY**

```powershell
python -m pytest -q tests/control_plane/test_provenance.py
```

No secondary file is changed.

**Commit boundary:** tooling/tests first; owner-reviewed lock records separately.

### WU-A5: Prove installed `agents` compatibility before schema work

**Files**

- Create: `tests/control_plane/test_native_agents_compat.py`
- Create: `tests/control_plane/fixtures/agents-registry/**`

**RED**

Record the installed `agents` version and prove a process-isolated
`HOME`/`USERPROFILE` fixture can run native `agents status`, `doctor`,
`sync --check`, and MCP read-only help/list behavior without touching the live
registry. Add a namespaced dummy top-level extension and verify the same
commands still parse. Run every estate-owned script with explicit fixture
`--agents-config`, `--live`, and state-root arguments; add a negative test that
fails if any default absolute live path is opened. Exercise the native
`agents` write/check path available in the installed version and assert the
unknown top-level extension survives byte-semantically; if no isolated write
path exists, record `NOT_TESTED` and block WU-C1.

Expected RED is either missing fixture support or explicit incompatibility—not
a live-file mutation.

**GREEN**

If temporary-home isolation and unknown-key tolerance work, preserve the receipt
for WU-C1. If either cannot be proven, stop as `FAILED_TO_RUN` and amend the
design before schema implementation. No companion registry is invented.

**VERIFY**

```powershell
python -m pytest -q tests/control_plane/test_native_agents_compat.py
```

**Commit boundary:** test/fixture/receipt only; no `agents.json` edit.

---

## Wave B — state, telemetry, and transaction primitives

### WU-B1: Baselines and link topology

**Files**

- Create: `control_plane/baseline.py`
- Create: `control_plane/links.py`
- Create: `tests/control_plane/test_baseline.py`
- Create: `tests/control_plane/test_links.py`
- Modify: `harness/install.py`

**RED**

- missing/malformed/shapeless baseline → distinct `FAILED_TO_RUN`;
- skill and rule links record type, target, attributes;
- link restore recreates expected object and refuses unexpected reparse point;
- current `.claude\skills` chain round-trips in fixture form;
- `.agents\rules`, `.agents\rules-canonical`, `.claude\rules`, and
  `.codex\rules` each record link/reparse type, target, attributes, and active
  file-set hash; backup/scratch files are excluded.

**GREEN**

Reuse public `surface_reconciler.comparison_hash`/`scan_surface`; promote the
minimum reparse helper to a tested public function rather than importing a
private underscore symbol. Link writes occur only through the transaction
mediator and have pre-images.

**VERIFY**

```powershell
python -m pytest -q tests/control_plane/test_baseline.py tests/control_plane/test_links.py
python -m pytest -q harness/tests/test_install_reconciler.py
```

### WU-B2: Hook policy and safe telemetry

**Files**

- Create: `control_plane/hook_policy.py`
- Create: `control_plane/telemetry.py`
- Create: `tests/control_plane/test_hook_policy.py`
- Create: `tests/control_plane/test_telemetry.py`

**RED**

For each declared hook require failure class, timeout, timeout action,
malformed-input action, bypass resistance, recovery instruction, and both-state
tests. Process tests prove lock-safe JSONL, structural redaction, rotation,
retention, dropped-event counter, and explicit test-vs-production source
classification. Safety tests pass^3.

**GREEN**

Use existing lock/redaction primitives; no daemon. Existing live hook scripts
are inventoried but not rewired in this unit. Promotion remains deferred.
Any discovered non-Cursor raw payload sink emits `ACTION_REQUIRED` and blocks
Phase 1 exit until migrated or explicitly scoped by a reviewed amendment.

**VERIFY**

```powershell
python -m pytest -q tests/control_plane/test_hook_policy.py tests/control_plane/test_telemetry.py
```

### WU-B2b: Migrate live Cursor loggers to the safe writer

**Files**

- Create: `scripts/cursor-hooks/write-safe-event.ps1`
- Create: `tests/control_plane/test_cursor_logger_migration.py`
- Modify after reconciling existing dirty diffs:
  `scripts/cursor-hooks/cursor-hook-log.ps1`
- Modify after reconciling existing dirty diffs:
  `scripts/cursor-hooks/shell-guard.ps1`

**RED**

Run synthetic secret-bearing shell/edit/MCP payloads through fixture copies.
Assert no raw secret or full edited content reaches any live-shaped disk sink;
schema allowlist, lock, rotation, retention, source class, and dropped-event
receipt are present. Close-match legitimate commands remain allowed. No live
log is read.

**GREEN**

Route telemetry fields through the safe writer while preserving current deny/
allow output timing and exit behavior. First capture/review existing uncommitted
diffs so this unit does not overwrite another agent's changes. Enforcement mode
remains unchanged.

**VERIFY**

```powershell
python -m pytest -q tests/control_plane/test_cursor_logger_migration.py
```

Run safety cases three times. Phase 1 cannot exit until this passes.

### WU-B3: Journal state model before lock recovery

**Files**

- Create: `control_plane/journal.py`
- Create: `tests/control_plane/test_journal.py`

**RED**

Test every design state transition, resume/rollback table row, abandon only
before `PREPARED`, and six resume-refusal conditions.

**GREEN**

Implement pure state logic and create-once/fsynced journal writes.

**VERIFY**

```powershell
python -m pytest -q tests/control_plane/test_journal.py
```

### WU-B4: Process-aware deployment lock

**Files**

- Create: `control_plane/locking.py`
- Create: `tests/control_plane/test_locking.py`
- Modify: `harness/install.py`

**RED**

Live old PID not stolen; dead/recycled PID recoverable only through journal
recovery; corrupt lock → `FAILED_TO_RUN`; break-lock receipt required.

**GREEN**

Delegate existing install lock to process/start-time/transaction-aware helper.
This intentionally changes the old timestamp-only stale-steal contract: a live
long-running owner is no longer preempted merely because its timestamp aged.
Update the existing stale-lock test to use a dead PID, retain a separately
named legacy-behavior fixture for evidence, and record the availability impact
(recovery now requires journal adjudication).

**VERIFY**

```powershell
python -m pytest -q tests/control_plane/test_locking.py
python -m pytest -q harness/tests/test_install_deploy.py -k "lock"
```

### WU-B5: Bounded CAS and target-idle handling

**Files**

- Create: `control_plane/cas.py`
- Create: `tests/control_plane/test_cas.py`
- Modify: `harness/install.py`

**RED**

Transient conflict within budget succeeds; persistent conflict writes nothing;
same-volume replace preferred; non-atomic fallback verifies every copy/hash;
external continuous writer yields explicit deferred state. After replacement,
ACL/owner, encoding, BOM, line endings, and file attributes equal the captured
target policy/pre-image.

**GREEN**

Bounded retry/backoff; no indefinite loop. Preserve temp cleanup.

**VERIFY**

```powershell
python -m pytest -q tests/control_plane/test_cas.py
python -m pytest -q harness/tests/test_install_deploy.py -k "cas"
```

### WU-B6: Windows-protected byte-exact pre-images

**Files**

- Create: `control_plane/preimage.py`
- Create: `scripts/verify-acl.ps1`
- Create: `tests/control_plane/test_preimage.py`

**RED**

Missing/truncated/hash mismatch → `FAILED_TO_RUN`; exact metadata/link capture;
mixed-file inverse managed-subtree rollback; whole-file restore only when live
hash equals known post-apply hash; secret bytes never escape protected store;
the design's exact one-shot `icacls.exe` argv plus pinned PowerShell SDDL
verifier; owner-plus-local-SYSTEM-only ACL verification.

**GREEN**

Use local content-addressed `deploy-backups/<transaction>`. Apply inheritance
removal and owner+SYSTEM grants in one exact `icacls.exe` invocation, then use
the pinned `verify-acl.ps1` .NET SDDL check. No localized `icacls` text is
parsed. If ACL verification is unavailable, fail to run—never claim protection.
Test the empty parent-root bootstrap before transaction children and verify the
script's pinned hash; a changed verifier cannot protect a transaction.

**VERIFY**

```powershell
python -m pytest -q tests/control_plane/test_preimage.py
```

Safety paths pass^3.

### WU-B7: Immutable release artifacts and receipt chain

**Files**

- Create: `control_plane/receipts.py`
- Create: `tests/control_plane/test_receipts.py`
- Create in fixtures: `releases/<id>/{manifest,capability-delta,verification}.json`

**RED**

Exclusive create; no success before verification; no rollback-complete before
restoration; chain reconstruction from versioned files; missing/forked/mismatch
detected; redaction contract; local active-head treated only as cache.

**GREEN**

Implement create-once committed/failed/rollback/failed-to-run receipts and
versioned layout.

**VERIFY**

```powershell
python -m pytest -q tests/control_plane/test_receipts.py
```

### WU-B8: Machine-readable capability delta

**Files**

- Create: `control_plane/capability_delta.py`
- Create: `tests/control_plane/test_capability_delta.py`

**RED**

Cover skills, MCPs, rules, hooks, plugins, commands, auth/session references,
and native-only capabilities. Additions default-deny; removals need exact owner
approval ID; unknown blocks apply; unreported pop/prune/keep-list drop fails;
required unsupported → consumer `FAILED_TO_RUN`.

**GREEN**

Emit `releases/<id>/capability-delta.json` before `PREPARED`.

**VERIFY**

```powershell
python -m pytest -q tests/control_plane/test_capability_delta.py
```

### WU-B9: Hash-bound approvals

**Files**

- Create: `control_plane/approvals.py`
- Create: `tests/control_plane/test_approvals.py`

**RED**

Seven approval states; per-change partial approval; hash/scope expiry; quarantine
and revoke; `approve-risk` cannot override NEVER-ROTATE, secret export, missing
pre-images, invalid digest/signature, or hard locks; no generic force/yes.

**GREEN**

Create local approval records referenced by transaction receipts.

**VERIFY**

```powershell
python -m pytest -q tests/control_plane/test_approvals.py
```

### WU-B10: Transaction controller

**Files**

- Create: `control_plane/controller.py`
- Create: `tests/control_plane/test_controller.py`

**RED**

Fault-inject at every stage; staged secret/delta scan occurs before `PREPARED`;
partial success never estate success; interrupted journal blocks new work;
mediator required for all effects; controller self-hash checked; prior
known-good controller performs controller rollback.

**GREEN**

Compose B3–B9. Implement serial activation/verification and restore-all.

**VERIFY**

```powershell
python -m pytest -q tests/control_plane/test_controller.py
```

Fault paths pass^3.

**Wave B gate**

Run `python scripts/run_control_plane_coverage.py --thresholds
.coverage-thresholds.json --phase wave-b`, then named existing install/harness
regressions.

---

## Wave C — registry, grants, and memory/rules policy

### WU-C1: Consumer-aware schema without breaking native `agents`

**Files**

- Create: `control_plane/schema.py`
- Create: `tests/control_plane/test_schema.py`
- Modify: `agents.json`
- Modify: `scripts/mcp_control_plane.py`
- Modify: `scripts/validate_mcp_control_plane.py`

**RED**

- all five support classes and all required consumer fields validate;
- Cursor is first-class;
- every consumer count appears;
- existing keys and rendered Claude/Codex/Cursor outputs are unchanged by an
  additive schema extension;
- process-isolated temporary `HOME`/`USERPROFILE` probe checks installed
  `agents status`, `doctor`, `sync --check`, and `mcp` compatibility without
  touching live config;
- one canonical authority invariant holds.

**GREEN**

Use an optional namespaced extension in `agents.json`. WU-A5 is blocking: if
the installed binary rejects the extension, stop and amend the design; do not
create a companion registry or second authority. This unit extends
`VALID_TARGETS` and validator reporting to include `cursor`, but does not switch
the Cursor merger's parity key; WU-D3 owns that switch. Assert all three
provider render outputs are unchanged before/after adding the non-Cursor schema
fields.

**VERIFY**

```powershell
python -m pytest -q tests/control_plane/test_schema.py
python -m pytest -q tests/test_mcp_control_plane.py
```

### WU-C2: Mediated adapter grants

**Files**

- Create: `control_plane/adapters/__init__.py`
- Create: `control_plane/adapters/base.py`
- Create: `control_plane/adapters/grants.py`
- Create: `tests/control_plane/test_adapter_contract.py`

**RED**

All eight operations; default-deny path/argv/env-name/network/elevation; exact
Tier-1 grant matrix; no raw side-effect imports/calls in adapter AST; mediator
negative tests; controller's own exact grant table; session-mutating native
commands refused; known-missing consumer fixture returns `NOT_APPLICABLE` or
`NOT_TESTED`, never false healthy.

**GREEN**

Application-level mediation, explicitly not OS containment. Enforce with AST
lint, exact controller handles, and monkeypatched bypass tests.

**VERIFY**

```powershell
python -m pytest -q tests/control_plane/test_adapter_contract.py
```

### WU-C3: Basic Memory canonical cache policy

**Files**

- Create: `control_plane/memory_policy.py`
- Create: `tests/control_plane/test_memory_policy.py`

**RED**

- only `http://127.0.0.1:8765/mcp`;
- reject stdio/uvx/npx/pip spawn, rebinding/restart/cloud sync;
- semantic search remains on; embeddings off request path;
- durable publication only through `write_note`;
- cache schema includes project, source hash, timestamp, TTL, supersession,
  poison, trust;
- expired/cross-project/poisoned/superseded/provenance-missing not injected;
- outage uses bounded local non-authoritative cache and creates no durable write;
- cache directories use the B6 owner+SYSTEM SDDL verifier, per-project paths,
  bounded size/retention, and no cloud synchronization;
- synthetic `local.json` values never enter canonical, staged, generated,
  diagnostic, or model-facing output.

**GREEN**

Policy/validator only; do not restart or modify Basic Memory.

**VERIFY**

```powershell
python -m pytest -q tests/control_plane/test_memory_policy.py
```

### WU-C4: Canonical rules and budgeted projections

**Files**

- Create: `control_plane/rules.py`
- Create: `tests/control_plane/test_rules_bootstrap.py`
- Modify: `scripts/sync-rules.ps1`
- Create after owner adjudication: `rules-canonical/**`
- Preserve/generated later: `rules/**`

**RED**

No recursive copy; normalized duplicate/conflict distinction; unique retention;
unknown conflict → `ACTION_REQUIRED`; canonical path separate from Grok;
Grok projection ≤10,000 chars; budgeted Claude/Codex/Cursor projections;
fixture behavior proves each consumer loads intended rule.

**GREEN**

Generate decision queue from current three-file Grok projection, Claude, Codex,
and repository donor rules. Tooling lands before owner-adjudicated content.

**VERIFY**

```powershell
python -m pytest -q tests/control_plane/test_rules_bootstrap.py
```

Wave C cannot finish while required rule conflicts remain unresolved.

**Wave C gate:** run
`python scripts/run_control_plane_coverage.py --thresholds .coverage-thresholds.json --phase wave-c`
plus `tests/test_mcp_control_plane.py`.

---

## Wave D — complete Tier-1 consumer adapters

Each adapter covers skills, rules, hooks, MCPs, memory/cache classification,
native-only capability inventory, rollback, and representative session-neutral
journeys—not MCP alone. Authoring may be parallel; tests/smokes are serial.

### WU-D1: Claude adapter

**Files**

- Create: `control_plane/adapters/claude.py`
- Create: `tests/control_plane/test_adapter_claude.py`
- Modify: `scripts/merge_generated_claude_mcp.py`

**RED**

- existing HTTP renderer test;
- semantic managed-subtree preservation on first render and byte-stable second
  render;
- no whole-file reformat/reorder;
- no unapproved pop/prune;
- skill link/rule projection/hook policy/memory cache staged and rollback-safe;
- ACL/owner, encoding, BOM, line endings, and attributes preserved;
- canonical→native→inventory retains all required fields;
- pinned installed Claude version and pre/post `claude mcp list`/read-only
  status show typed HTTP accepted without session mutation.

**GREEN**

Add `type: http`; convert merger to render-only; use controller mediator.

**VERIFY**

```powershell
python -m pytest -q tests/control_plane/test_adapter_claude.py
python -m pytest -q tests/test_mcp_control_plane.py -k claude
```

Native smoke only with ≥8 GiB free RAM and rollback prepared.

### WU-D2: Codex adapter

**Files**

- Create: `control_plane/adapters/codex.py`
- Create: `tests/control_plane/test_adapter_codex.py`
- Modify: `scripts/merge_generated_codex_mcp.py`

**RED**

Existing text-splicer preserves comments/order; asserted force-push conflict
requires owner decision; native memories classified as cache; skills/rules/
hooks/MCP/memory staged and rollback-safe; round-trip and idempotence;
ACL/owner, encoding, BOM, line endings, and attributes preserved;
session-neutral native status only.

**GREEN**

Retain regex marker text splicing; do not TOML reserialize. Render only.

**VERIFY**

```powershell
python -m pytest -q tests/control_plane/test_adapter_codex.py
python -m pytest -q tests/test_mcp_control_plane.py -k codex
```

### WU-D3: Cursor first-class six-MCP adapter

**Files**

- Create: `control_plane/adapters/cursor.py`
- Create: `tests/control_plane/test_adapter_cursor.py`
- Modify: `scripts/merge_generated_cursor_mcp.py`
- Modify: `agents.json`

**RED**

- exact six server records gain `cursor` target;
- plugin/denied/parked reasons move into registry grants;
- rendered six names are identical before/after target migration;
- every exclusion has stable approved delta ID;
- `${env:NAME}` preserved;
- skills/hooks/MCP/memory staged and rollback-safe;
- rules are explicitly `emulated` through the canonical `AGENTS.md` pointer
  with no Cursor rule-file write;
- encoding/BOM/line endings/attributes preserved;
- round-trip, second-render zero-diff, one-process/session-neutral smoke;
- `mcp-cursor-parked-31.json` is migrated to a generated/read-only projection
  or explicitly retired.

**GREEN**

Move all Cursor policy constants into canonical data in the same commit; merger
becomes render-only.

**VERIFY**

```powershell
python -m pytest -q tests/control_plane/test_adapter_cursor.py
python -m pytest -q tests/test_mcp_control_plane.py -k cursor
```

### WU-D4: Serialized native runtime journeys

**Files**

- Create: `control_plane/runtime_verify.py`
- Create: `tests/control_plane/test_runtime_verify.py`
- Create: `tests/control_plane/fixtures/runtime/**`

**RED**

Per-consumer exact argv allowlists; representative MCP/skill/rule/hook/memory
journeys; ≥8 GiB preflight; serial execution; `NOT_TESTED` when no neutral
command; no login/logout/refresh/revoke/session creation; verification receipt.

**GREEN**

Fixture runner first. Live journeys require owner-approved canary transaction
and protected rollback.

**VERIFY**

```powershell
python -m pytest -q tests/control_plane/test_runtime_verify.py
```

**Wave D gate:** run
`python scripts/run_control_plane_coverage.py --thresholds .coverage-thresholds.json --phase wave-d`
plus the full adapter and MCP control-plane suites.

---

## Wave E — status, CLI, end-to-end, and activation

### WU-E1: Status aggregation and freshness

**Files**

- Create: `control_plane/status.py`
- Create: `tests/control_plane/test_status.py`

**RED**

All states/precedence; per-capability SLO; degraded recovery fields; required
unsupported; approvals; operation vs estate status; bounded output; every
nonhealthy field. Assert `status --all` includes canonical hash,
active/staged/last-known-good releases, dirty/drift, pending approvals, separate
support and runtime-health fields, verification age/receipt/next action, state
counts, rollback availability, and interrupted transaction. Alert dedup keys
are consumer+capability+reason+release; novel safety findings never suppress.

**GREEN/VERIFY**

Pure read-only projection over receipts/telemetry.

```powershell
python -m pytest -q tests/control_plane/test_status.py
```

### WU-E2: Owned `agents-cp` CLI, approvals, and recovery commands

**Files**

- Create: `control_plane/cli.py`
- Create: `scripts/agents-cp.ps1`
- Create: `C:\Users\Prekzursil\.local\bin\agents-cp.cmd` through a
  transaction-managed staged target
- Create: `tests/control_plane/test_cli.py`

**RED**

Exact design commands and exit-code classes; review/quarantine/revoke/risk;
transaction resume/rollback/abandon; release list/diff; rollback preview;
noninteractive exact approval; no force/yes; native `agents` command resolution
unchanged; PowerShell 5 and 7 behavior.

**GREEN**

Expose `python -m control_plane` through `.agents\scripts\agents-cp.ps1` and
the exact `.local\bin\agents-cp.cmd` shim. Do not modify PATH or profiles; if
`.local\bin` is not already discoverable, document the full path and report
bare resolution unsupported. Never shadow `agents`.

**VERIFY**

```powershell
python -m pytest -q tests/control_plane/test_cli.py
```

### WU-E3: End-to-end gate and completion AND-gate

**Files**

- Create: `control_plane/completion_gate.py`
- Create: `tests/control_plane/test_e2e_commands.py`
- Create: `tests/control_plane/test_completion_gate.py`

**RED**

Run all design target commands against a temporary estate and assert typed
envelopes/exit codes. AND-gate requires exit, artifact, size, schema, sentinel,
no forbidden path change. Resource tests retain ports 8765/8812/8317 ownership,
6 GiB MCP ceiling, one Cursor process, and measured ≤2 GiB added peak. Peak
working set is measured with a pinned read-only PowerShell `Get-Process`
sampler before, during, and after a fixture transaction; the receipt stores
only PID, process name, and byte counts.

**VERIFY**

```powershell
python -m pytest -q tests/control_plane/test_e2e_commands.py tests/control_plane/test_completion_gate.py
```

### WU-E4: Writer inventory and single activation entry point

**Files**

- Modify: `scripts/sync_shared_state.ps1`
- Modify: provider merger CLIs
- Modify: `scripts/sync-hooks.ps1`
- Classify: `scripts/deploy-skills-daily.py`
- Classify: `scripts/deploy-skills-codex.py`
- Classify: `scripts/sync-from-live.ps1`
- Classify: both `convert_skills_daily_*.ps1`
- Modify: `scripts/harness-audit.js`
- Classify: `skills/DEPLOYED-MANIFEST.json`
- Create: `tests/control_plane/test_writer_inventory.py`

**RED**

Discover writers dynamically; exactly one apply entry point; retired writers ≥
new writers; direct merger writes refuse; link manager transaction-owned;
presence scorer cannot claim runtime acceptance; PowerShell 5 SUCCESS sentinel
preserved.

**GREEN**

`sync_shared_state.ps1` delegates to `agents-cp apply`; existing writers become
render/inventory only. Replace the temporary skill-deployment freeze with the
transaction-owned skill/link path; no independent skill deploy remains.

**VERIFY**

```powershell
python -m pytest -q tests/control_plane/test_writer_inventory.py
python -m pytest -q tests/test_mcp_control_plane.py
python -m pytest -q harness/tests
node --check scripts/harness-audit.js
```

No live apply occurs until `agents-cp rollback <release> --dry-run` and staged
validation pass.

---

## Wave F — acceptance and branch handoff

### WU-F1: Tier-1 acceptance

Run serially:

```powershell
python scripts/run_control_plane_coverage.py --thresholds .coverage-thresholds.json
python scripts/validate_mcp_control_plane.py --agents-config agents.json
agents-cp inventory --all --redacted --output <artifact>
agents-cp plan --all --output <artifact>
agents-cp validate --staging <transaction>
agents-cp rollback <captured-pre-tier1-baseline> --dry-run
agents-cp apply --transaction <approved-transaction>
agents-cp verify --release <release>
agents-cp rollback <release> --dry-run
```

Blocking:

- tests/coverage green;
- unapproved capability additions/removals = 0;
- raw synthetic-secret matches = 0 outside protected fixture pre-images;
- all transaction fault paths restore;
- Claude/Codex/Cursor complete representative journeys;
- one apply entry point; writer count reduced; no new daemon;
- no auth/session mutation or credential rotation;
- resource budgets hold;
- disk-reverified release receipt exists;
- unrelated dirty files unchanged.

If resource or session-neutral constraints leave any required journey
`NOT_TESTED`, the only allowed terminal is
`TIER1-CODE-COMPLETE-NOT-RUNTIME-VERIFIED`; it is not success and cannot
activate the new entry point. `SUCCESS:TIER1` requires all required live
journeys and the release receipt.

### WU-F2: Knowledge capture and finishing boundary

Before any PR/merge/branch-finish:

1. Run `/self-reflect`.
2. Write durable decisions through Basic Memory `write_note` when available;
   if unavailable, emit degraded receipt and do not invent memory success.
3. Commit approved knowledge-base updates only with owner authorization.
4. Run the repository's final coverage/gate command again.
5. Present branch/PR/merge options; do not push without explicit request.

---

## Dependencies and safe parallel authorship

```text
A1
├─ A2
├─ A3 ─ B1 ─┐
├─ A4
├─ A5 ─ C1 ─ C2
├─ B2 ─ B2b
└─ B3 ──────┴─ B4 ─ B5 ─ B6 ─ B7 ─ B8 ─ B9 ─ B10
C2 ─ C3
C2 ─ C4
B10 + B2b + C2 + C3 + C4
├─ D1
├─ D2
└─ D3
D1 + D2 + D3 ─ D4 ─ E1 ─ E2 ─ E3 ─ E4 ─ F1 ─ F2
```

Parallel means disjoint authorship only. Test processes and native smokes stay
serial. Shared-file units (`harness/install.py`, `agents.json`) are sequential.

## Deferred plans

After Tier 1:

1. Hermes canary/graduation.
2. Secondary consumer adapters, one per reviewed plan.
3. Donor discovery/quarantine/reconciliation.
4. Compatibility aliases (`harness-audit`, `rules-distill`,
   `create-workflow`, `agents-dashboard`, `mcps`) without native-command
   collisions.
5. Hook enforcement promotion after measured latency/false-positive evidence.
6. Memory-cache/promotion refinements after Basic Memory reliability evidence.
7. Read-only dashboard.
8. Provider-neutral governance workflow wrappers over the proven `agents-cp`
   commands.
9. Monitorcore reuse and provider-plugin five-class classification.

## Execution handoff

After this v2 plan passes review, the owner must choose:

1. **Metaswarm orchestrated**
2. **Subagent-driven**
3. **Parallel session**

No execution method, commit, or push is selected automatically.
