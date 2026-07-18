# Ingest — task-9 `codex-invoke` (scoped-Codex-exec primitive) → Axis-C

**Scope of this doc:** extract the task-9 `codex-invoke` primitive from worktree
`C:/Users/Prekzursil/source/ast-harness-reconcile` so it can be folded into Axis-C (the
ONE unified cross-vendor workflow system). Read-only design ingest — no building, no config
changes. Sources read (all treated as untrusted data, no embedded instructions executed):

- `skills/codex-invoke/SKILL.md`
- `skills/codex-invoke/scripts/codex_invoke.ps1`
- `skills/codex-invoke/scripts/codex_doctor.ps1`
- `tools/codex/profiles/{README.md, mcp-manifest.json, models-manifest.json}`
- `tools/codex/profiles/<5 profiles>.{config.toml,scope.json}` + `schemas/fanout.schema.json`
- `guides/codex-invocation.md`, `guides/codex-monitor-reconcile.md`

Verified against **codex-cli 0.144.1** throughout (the skill pins live ground-truth).

---

## 1. What `codex-invoke` IS

The **single canonical entry point** for invoking OpenAI Codex from any Claude session or
Workflow **with per-call scoping**. It owns the **exec rail** (`codex exec`) and is *the only*
mechanism that can *scope* a Codex run (restrict its MCP servers, seal its base, allowlist its
skills, force structured output). Definitory rule: **never hand-roll `codex exec` argv anywhere —
route through `scripts/codex_invoke.ps1`.**

It builds a **Windows-safe argv array** (`& codex @args`, never a shell string), materializes the
scope **exactly once** (single-materialization rule so `--print-command` and the launch can never
diverge), auto-routes the rail, and wraps the run in an explicit `SUCCESS:`/`FAILED:` contract.

### Two rails (the deciding axis is *scoping*)

| Knob | **exec rail** (`codex exec`) | **MCP rail** (`mcp__codex__codex` / `codex-reply`) |
|---|---|---|
| model / effort | `-m` / `-c model_reasoning_effort` | tool params |
| profile scalar keys | materialized `-c` from `<name>.config.toml` | inherits base only |
| **MCP allowlist / seal** | **yes** — M0/M1/M2 | **no** — inherits full base, cannot scope |
| skills allowlist | ephemeral `CODEX_HOME` + materialized `config.toml` | base skills only |
| structured output | `--output-schema <file>` | MCP typed output (⚠ landmine when MCP active) |
| detached / one-shot | background + `codex resume` | in-session only |
| threadId continuation | `codex exec resume --last` | `codex-reply(threadId)` |

**Routing rule (auto, and it states which rail it used):** *any* `mcps`/`skills`/`seal` request →
**exec rail**. Otherwise a plain model/effort call *may* ride the MCP rail. In the launcher, `auto`
actually resolves to `exec` in both branches (exec is the safe default; MCP is only for trivial
in-session). Requesting `-Rail mcp` while scoping → `FAILED:<id> rail-mismatch`.

---

## 2. The invoke API — `scripts/codex_invoke.ps1` parameters

```
-Model  -Effort  -Profile  -Mcps[]  -Skills[]  -Tools(hashtable)  -Sandbox  -Approval
-OutputSchema  -Seal(switch)  -Mode(M0|M1|M2)  -Rail(auto|exec|mcp, default auto)
-Cwd  -Prompt  -Timeout(int)  -Id  -PrintCommand(switch)  -Doctor(switch)  -ProfilesDir
```

Semantics extracted from the script:

- **Explicit params override profile scalars.** A `-Profile` loads `<name>.config.toml`
  (scalar keys → `$Model/$Effort/$Sandbox/$Approval`) and `<name>.scope.json` (mode, allowlist,
  seal, skills, captured defs). `-Mcps` overrides the profile's `mcp_allowlist`; `-Skills`
  overrides `skills_allowlist`.
- **`-Id`** defaults to `codex-<random>`; it is echoed in every terminal marker (`SUCCESS:<id>` /
  `FAILED:<id>`) — this is the fan-in correlation key.
- **`-Doctor`** shells to `codex_doctor.ps1 -ProfilesDir …` and exits with its code.
- **`-PrintCommand`** = the mandatory DRY-RUN: prints resolved rail, mode, `CODEX_HOME`, offline
  flag, allowlist, and the argv-quoted command, running **nothing beyond the one live config read**
  the materialization needs. Reuses the identical cached override set as the launch.
- **`-OutputSchema <file>`** → `--output-schema <file>` on the exec argv (structured output).
- **`-Cwd`** → `-C <path>` (PS array, so **no MSYS path-conversion**).
- **Canonical `CODEX_HOME`** resolves `HARNESS_LIVE_CODEX_HOME` → `~/.codex` (never a bare,
  possibly-ephemeral `CODEX_HOME`). Profiles are read from `-ProfilesDir` → repo
  `tools/codex/profiles/` → `$CODEX_HOME/profiles/`.

### Fixed argv assembly (order matters)

`exec` → `[--ignore-user-config` if seal`]` → `-m <model>` → `-s <sandbox>` →
`-c approval_policy=<x>` → each `-c <override>` (the single-materialized disable/enable set) →
`--enable/--disable <feature>` per `-Tools` → `--output-schema <file>` → `-C <cwd>` →
`--skip-git-repo-check` → `--json` → `<prompt>`.

**Non-negotiable launch detail:** every launch feeds **empty stdin** (`'' | & codex @args`).
codex-cli 0.144.1 `exec` *aborts before doing any work* on a piped/inherited non-terminal stdin
("stdin is not a terminal") or null stdin with redirected stdout — i.e. **every non-interactive
context** (Workflow, subagent, `longrun`-with-redirect), which is the whole point. Without the
empty-string pipe the invoker only works from a real interactive TTY. This is load-bearing for
in-workflow use.

---

## 3. The M0–M3 scoping mechanisms (keyed off `scope.json.mode` + `seal`)

Profiles give the *easy* axis (model/effort/sandbox/approval/web) via materialized `-c`. True
scoping needs one of four mechanisms, because a static profile cannot express "disable everything
NOT in this allowlist" against a base whose future server names are unknown at author time.

- **M0 — Static disable (offline, no live read).** `scope.json.static_disable` enumerates
  `base − mcp_allowlist` (pre-computed against `mcp-manifest.json`); the launcher materializes each
  as `-c mcp_servers.<x>.enabled=false`. **These are NOT inline `mcp_servers` lines in the .toml** —
  codex rejects a transport-less standalone entry ("invalid transport") in *every* mode, so such a
  file cannot load; a `-c` override rides the transport-carrying base server and disables it.
  **Fail-closed:** empty `static_disable` → `FAILED:<id> m0-unscoped` (would run the FULL base).
- **M1 — Difference-disable (default; drift-robust).** Enumerate the live base once via
  `codex mcp list --json`, compute `live_base − mcp_allowlist`, emit
  `-c mcp_servers.<x>.enabled=false` per server. Anything the base gains that isn't allowlisted is
  auto-disabled. **One live read** (so DRY-RUN is not fully offline for M1).
- **M2 — Sealed base (`seal:true`, `--ignore-user-config` drops the base entirely).**
  - **M2a — full-seal / zero-MCP** (empty allowlist): no enable block → runtime loads zero MCP
    servers. The fan-out path. **Offline.** Allowed *only* with an empty allowlist.
  - **M2b — sealed + explicit allowlist** (non-empty): supply a fully explicit
    `-c mcp_servers.<x>.command/.args/.env` ENABLE block for only the allowlisted servers,
    **harvested from the live base** (`codex mcp get <name> --json`, secrets as `${VAR}`) into
    `scope.json.captured_mcp_defs`. **Fail-closed:** seal + non-empty allowlist but no captured def
    (or an unset `${VAR}`) → `FAILED:<id> seal-uncaptured`.
- **M3 — Feature/tool toggles.** `web_search="disabled"` in the toml + `--enable/--disable <feature>`
  (== `-c features.<name>=…`) per `scope.json.tools`.

### Skills scoping (no native per-invocation flag exists)

When `skills_allowlist` is non-empty the skill stages an **ephemeral scoped `CODEX_HOME`**
(`$TMP/codex-scope-<hash>/`) holding (1) copied `auth.json`, (2) a **materialized `config.toml`**
carrying exactly the allowlisted MCP defs (harvested — an ephemeral home does NOT inherit the base
config, so without this step the run silently has zero MCPs) **plus** the profile scalar keys, and
(3) a `skills/` dir with only the allowlisted skills. `CODEX_HOME` is passed to the **codex child
process only** (never a session-global export) inside a `try/finally` that restores the prior value.
The launcher itself only *points* the child at the ephemeral home; **full staging is done by
`codex_doctor.ps1` at deploy time** — if unstaged the launcher fails-closed
(`FAILED:<id> ephemeral-home-unstaged`) rather than silently running zero MCPs.

**Shared primitive** feeding both M2b and the skills home: the **MCP-definition harvest**
(`for name in allowlist: codex mcp get <name> --json → {command,args,env:${VAR}}`), harvested +
pinned at deploy/doctor time, re-verified per codex release.

---

## 4. The 5 profiles (two files each: `<name>.config.toml` + `<name>.scope.json`)

`.config.toml` = ONLY real, `--strict-config`-clean codex keys (model, model_reasoning_effort,
approval_policy, sandbox_mode, web_search, service_tier, `[shell_environment_policy]`). `.scope.json`
= the scoping manifest codex never parses (mode, mcp_allowlist, tools, skills_allowlist, seal,
static_disable, model_fallbacks, captured_mcp_defs, base_snapshot_hash, notes). **Secrets discipline:**
MCP creds are `${VAR}` placeholders only — never inline, never in captured_mcp_defs, never in the
ephemeral config.

| Profile | model / effort | sandbox / approval | web | mode | seal | mcp_allowlist | skills_allowlist | Use |
|---|---|---|---|---|---|---|---|---|
| **audit-readonly-max** | gpt-5.6-sol / `max` | read-only / never | live | M1 | no | basic-memory, scholarly-access, context7, deepwiki, repomix, semgrep (zero write-capable) | game-re-binary, re-triage-preflight, radare2, ghidra-mcp | Deep read-only audits |
| **build-sandboxed** | gpt-5.6-sol / `high` | workspace-write / on-request | live | M1 (ephemeral, skills set) | no | context7, repomix, qlty, codacy, github_cli, basic-memory | tdd-workflow, python-testing, security-review, systematic-debugging | Scoped implementation w/ approvals |
| **exec-fast** | gpt-5.6-sol / `medium` | workspace-write / on-request, `service_tier="fast"` | disabled | **M0** | no | basic-memory only (static_disable = 24 others) | (none → runs in-place) | Quick one-shots / cheap iterations |
| **fanout-json** | gpt-5.6-sol / `max` | read-only / never | disabled | **M2a** | **yes** | **none** | (none) | Parallel detached fan-out + `--output-schema` |
| **consult-review** | gpt-5.6-sol / `max` | read-only / never | live | M1 (ephemeral, skills set) | no | context7, deepwiki, exa, firecrawl, tavily, scholarly-access | receiving-code-review, rubric-verifier, acceptance-review | Advisory / review passes |

Notes: **build-sandboxed** and **consult-review** carry *both* a non-empty skills AND MCP allowlist
→ they run in an ephemeral home whose materialized config carries exactly the allowlisted MCP defs
(else the MCPs silently vanish on the skills path — the two profiles the review flagged).
`fanout-json` is the **safe structured-output profile**: with zero MCP servers active the
typed-output-vs-MCP landmine cannot fire. Its `--output-schema` points at
`schemas/fanout.schema.json`.

**`fanout.schema.json`** (the fan-in envelope): `type:object, additionalProperties:false`,
`required:[id, status, summary]`, where `status ∈ {success, failed, partial}` (AGENTS.md §4
terminal-state), plus optional `findings[]` ({title, detail, severity∈low|medium|high|critical,
evidence}) and `artifacts[]` (absolute paths). Extend per campaign; this is the conventional default.

**Anti-rot:** `mcp-manifest.json` (25 canonical base server names, captured 2026-07-13, codex-cli
0.144.1 — REAL identifiers like `github_cli` not `github`) and `models-manifest.json`
(`primary: gpt-5.6-sol`, allowed: gpt-5.6-sol, gpt-5.6-codex, gpt-5.1-codex-max) are the offline
sources of truth for CI (`test_codex_profiles.py`): every allowlist ⊆ `servers`, every model slug ∈
`allowed`. codex-doctor re-pins on base drift.

---

## 5. The SUCCESS/FAILED error contract (AGENTS.md §4 terminal state)

Every invocation ends in `SUCCESS:<id>` or `FAILED:<id> <reason>`. Reasons:

1. **config-parse** — classified on **exit code + codex stderr parse-error signature** ("failed to
   parse config" / unrecognized key), NEVER wall-clock. `--strict-config` is probed unconditionally
   at deploy/doctor time. Runtime hit → `FAILED:<id> config-parse` + route to
   `codex-runtime-recovery`.
2. **quota / auth** — preflight is `codex login status` (exit 0 == "Logged in using ChatGPT";
   codex-cli 0.144.1 has **no** `codex auth status`). On 5h/weekly cap / `429` / budget-pause → no
   retry-storm, `FAILED:<id> quota` + reset window. Transient probe `429` ≠ exhaustion.
3. **timeout** — wrap via `longrun` (`-HangTimeoutSec`), detached + `Monitor` (AGENTS.md §4a); never
   a blocking foreground call.
4. **detached-run recovery** — record session id + `-o` path; recovery re-reads the log and
   `codex resume`s (`codex-runtime-recovery` + `run-taskwatch_monitor`).
5. **scope-assertion (fail-closed)** — forbidden server loaded or required def uncaptured → refuse
   to launch (`FAILED:<id> scope-breach` / `seal-uncaptured`). A mechanism that cannot prove its
   scope must not run.
6. **base-drift** — live-base hash ≠ pinned `base_snapshot_hash` → `WARN base-drift`; re-harvest for
   M2b/skills.

The **0-second-exit** case (instant auth/config death) is caught by clauses 1+2 via exit-code +
signature, not by treating a fast exit as failure. Runtime reasons emitted by the launcher include:
`m0-unscoped`, `rail-mismatch`, `seal-uncaptured`, `ephemeral-home-unstaged`, `config-parse`,
`quota`, `auth`, `exit-<code>`, `launch-exception`.

---

## 6. codex-doctor (`scripts/codex_doctor.ps1`) — the trust gate

Health-check + config-lint. Params: `-ProfilesDir -Profile -Live -Pin`. Emits one
`SUCCESS:/FAILED:/WARN:` per profile + a `SUMMARY: fail=… warn=… profiles=… live=… pin=…`.
Fail-open on internal errors; **fail-closed** on a scope-assertion breach / uncaptured sealed def.
Checks:

1. **auth** — `codex login status` (exit 0 == logged in).
2. **config.toml parse + `--strict-config`-clean** — UNCONDITIONAL, **token-free**: stage the
   profile as the sole `config.toml` of an *unauthenticated* temp `CODEX_HOME`, run
   `codex exec --strict-config` with a **deliberately-absent** `--output-schema`. Malformed config
   dies at config-load ("Error loading config.toml") *before* auth/network; a clean config
   short-circuits on the missing schema — so a clean profile never spends a token. Distinct
   `transport` verdict for a transport-less `mcp_servers` overlay (the M0 footgun).
3. **scope.json parses; every `mcp_allowlist` ⊆ live base** (via `codex mcp list --json`).
4. **model slug DECLARED** (offline structural only — codex 0.144.1 has no offline model-resolve
   probe; real resolution proven live in check 6).
5. **harvest + pin** (`-Pin`) — for seal+allowlist / skills profiles, harvest
   `codex mcp get <name> --json` into `captured_mcp_defs`, record `base_snapshot_hash` (SHA-256 of
   sorted live base); fail-closed on any uncaptured def. Writes back with `Set-Content` (never
   `New-Item -Force`).
6. **exec-runtime scope proof** (`-Live`, the anti-fake check) — run a real `codex exec --json`
   no-op with the materialized flags, parse startup/session events for the **actual loaded MCP + tool
   inventory**, assert `loaded_mcp_set == mcp_allowlist` (and for skills profiles under the ephemeral
   home, `loaded_skills ⊆ skills_allowlist`). Also the ONLY place the model slug is *actually*
   resolved (unknown-model → fallback to `scope.model_fallbacks`, WARN). **This is the only proof
   valid under seal** — `codex mcp list --ignore-user-config` is REJECTED, so the `mcp` subcommand
   cannot be sealed; config-resolver introspection proves the resolver, not the runtime.

Checks 6–7 are `-Live`-gated (spend tokens); 1–5 run offline in CI. The `codex exec --json`
startup-event shape is pinned by a **shared fixture** (also consumed by the monitor lane + scope
proof) — a schema change fails loudly rather than silently mis-parsing.

---

## 7. Live monitoring (`guides/codex-monitor-reconcile.md`)

**One load-bearing fact:** both rails emit the **same `codex exec --json` JSONL** event stream —
startup/session events carry the loaded MCP+tool inventory and session id; turn events carry
token/tool activity + final result. **The same shape the scope proof parses**, pinned once by the
shared fixture. So watching is one stream read by two surfaces:

| Watching | The ONE mechanism |
|---|---|
| a **detached `codex exec`** run | `codex exec --json` → JSONL; `taskwatch register generic-logfile …` (`run-taskwatch_monitor`) |
| an **`mcp__codex__codex`** in-session call / the whole fan-out | `workflow-monitor` Codex lane — an O(changed) adapter in `workflow_run.py` folds each Codex thread into the same **run→phase→agent** tree beside the Claude agents |
| a quick Codex-only glance | `/codex-monitor` |

All read-only; none fabricates progress; **no new monitor, no hand-rolled tailer**. This IS the
"native-vs-ours-clearly-distinguished monitor" Axis-C wants: ONE read-only cockpit, both vendors,
one key set (`q`/`f`/`r`), one shared fixture keeping monitor + scope proof + taskwatch in lockstep.

---

## 8. CRITICAL — how this becomes the "scoped Codex agent" primitive inside Axis-C

### The native Workflow engine (what a `codexAgent()` sibling must match)

Confirmed by reading saved workflows (`plan-gate.mjs`, `uiux-tooling-consolidation-2026-07-12.js`):
the injected globals are `phase(name)`, `agent(prompt, opts)`, `parallel([() => agent(...)])`,
`log()`. `agent()` opts = `{ label, phase, schema (JSON-Schema object → typed return), effort,
model ('opus'|'fable'|'haiku'|…) }`. **`agent()` spawns a Claude subagent**; `model` picks a *Claude*
model. There is **no vendor axis** and **no `codexAgent()`** today. The workflow awaits `agent()` /
`parallel()` synchronously and fans in on the typed schema (null-tolerant: `.filter(Boolean)`).

### What `codexAgent(prompt, opts)` would call + need

A `codexAgent()` helper is the **cross-vendor sibling of `agent()`** — it makes a workflow node a
*Codex* agent, scoped per call. Two rails, picked by the same routing rule the skill already applies:

- **Scoped path (the only rail that scopes):** emit a **thin Claude launcher subagent** via native
  `agent()` whose entire job is to shell
  `codex_invoke.ps1 -Profile <p> -Prompt <…> -OutputSchema <schemaFile> -Id <wu-id>` in PowerShell,
  wait for the `SUCCESS:<id>`/`FAILED:<id>` marker, read the `-o` last-message JSONL, and **return
  the parsed typed object** to the workflow. The launcher subagent is just a launch+parse shell
  around the exec rail.
- **Unscoped path:** the subagent (or the workflow) calls `mcp__codex__codex` directly (native
  tool-result, in-session, but full base MCP set — no scoping).

**What `codexAgent()` needs to exist / be provided:**
1. A **profile name** (one of the 5) OR inline scope params (`-Mcps/-Skills/-Seal/-Mode`).
2. The workflow's JS **schema object written to a temp `.json` file** and passed as `-OutputSchema`
   (impedance-bridge — see §9 gap 2), then codex's `-o` output parsed back into the object.
3. A **deployed + doctored + pinned `CODEX_HOME`** (`install.py --deploy-codex` +
   `codex_doctor.ps1 -Pin -Live`) — else M2b/skills profiles `FAILED:seal-uncaptured` /
   `ephemeral-home-unstaged`.
4. A **`longrun` + `Monitor`** wrapper for the detached exec (never a blocking foreground call), and
   a reconciliation of "detached + taskwatch" with the workflow's synchronous `await` fan-in.
5. The **`-Id` = work-unit id** so `SUCCESS:<wu-id>`/`FAILED:<wu-id>` correlates on fan-in.

---

## 9. integration_points (how Axis-C USES codex-invoke) and gaps

See the returned schema for the concise lists; expanded here:

**Integration points**
- `codexAgent(prompt,{profile})` = the cross-vendor sibling of native `agent()`; under the hood a
  thin Claude launcher subagent shells `codex_invoke.ps1` (scoped) or calls `mcp__codex__codex`
  (unscoped). Axis-C picks by whether scoping is requested — the skill's own routing rule.
- The **5 profiles = vendor-agnostic capability presets** any workflow node requests
  (audit-readonly-max=read-only reviewer, build-sandboxed=scoped implementer, exec-fast=cheap
  one-shot, fanout-json=typed parallel worker, consult-review=advisory reviewer) → map onto workflow
  roles (reviewer / implementer / worker).
- **`fanout-json` + `schemas/fanout.schema.json`** is the drop-in for
  `parallel(units.map(u => codexAgent(u,{profile:'fanout-json'})))` — sealed zero-MCP +
  `--output-schema` = the safe typed-fan-out (no MCP-vs-typed landmine). `{id,status,summary,
  findings,artifacts}` = the fan-in envelope; `status` enum == AGENTS.md §4 terminal state.
- The **SUCCESS/FAILED contract IS the workflow terminal-state marker** — a codexAgent node reports
  `SUCCESS:<wu-id>`/`FAILED:<wu-id> <reason>`, so the orchestrator's null-tolerant barrier and
  per-WU pipeline treat a failed/quota'd Codex node exactly like a failed Claude agent.
- **Monitoring is already unified** (§7): both rails → same JSONL → `workflow-monitor` Codex lane
  beside Claude agents = the native-vs-ours-distinguished cockpit Axis-C names, one shared fixture.
- **codex-doctor is the deploy/per-release trust gate** — its exec-runtime scope proof PROVES a
  profile's scope before any workflow trusts a scoped codexAgent. Runs offline (1–5) in CI, `-Live`
  for the real proof.
- **CODEX_HOME resolution + child-scoped ephemeral home = the isolation primitive**, paralleling the
  workflow's worktree isolation for file-mutating agents.

**Gaps (missing for in-workflow mingling)**
1. **No `codexAgent()` helper exists** — the native engine only has `agent()` (Claude). The thin JS
   wrapper (emit an `agent()` that shells `codex_invoke.ps1`, parse `-o`, return the schema) is the
   keystone missing glue.
2. **Schema impedance mismatch** — native `agent({schema})` = Claude typed output; codex-invoke
   wants `--output-schema <FILE>`. Nothing today writes the workflow's JS schema to a temp file and
   parses codex's `-o` back. (workflow-authoring flags the "typed Codex output-schema landmine when
   MCP tools are active" — fanout-json/M2a sidesteps it, but the file-materialization bridge is
   unwritten.)
3. **Detached-vs-synchronous reconciliation** — the exec rail is detached/one-shot (`longrun` +
   Monitor, never blocking foreground); the native `parallel()` barrier is a synchronous `await`.
   How the launcher subagent blocks on longrun-with-Monitor inside its own turn (simplest) vs the
   workflow polling the JSONL is unspecified for the in-workflow case.
4. **Deploy/pin prerequisite** — `captured_mcp_defs` / `base_snapshot_hash` are EMPTY in versioned
   source (filled by codex-doctor at deploy). Any workflow requesting build-sandboxed / consult-review
   / audit-readonly-max (all have skills_allowlist) FAILs `seal-uncaptured` /
   `ephemeral-home-unstaged` until `install.py --deploy-codex` + `codex_doctor.ps1 -Pin -Live` run on
   the box. In-workflow mingling assumes a provisioned CODEX_HOME.
5. **Inherent rail asymmetry** — a *scoped* Codex node is always a Claude-subagent-shelling-PowerShell,
   never a first-class native `mcp__codex__codex` tool-result (the MCP rail cannot scope; the exec
   rail returns via .ps1 + JSONL). Axis-C must accept or paper over this.
6. **Vendor axis is the helper's job** — `agent({model})` picks a *Claude* model; there is no
   `{vendor:'codex', model:'gpt-5.6-sol'}` axis in the engine. codexAgent() must own the vendor axis.
7. **Shared-fixture dependency** — the `codex exec --json` startup-event fixture that keeps
   scope-proof + monitor + taskwatch in lockstep is *referenced* but not present in the profiles dir
   read; it must exist + be wired for Axis-C to trust the scoped path.
8. **Single-subscription quota, no in-workflow pacing** — one ChatGPT sub; a large `fanout-json`
   fan-out hits 5h/weekly cap → `FAILED:quota`. The contract handles it (no retry-storm) and the
   workflow tolerates partial fan-in (`filter(Boolean)`), but AgentBridge budget pacing is retired —
   there is no proactive pacing; a big cross-vendor fan-out can silently starve mid-run.

---

## 10. Anti-overfit note (Axis-C anchor)

codex-invoke is exactly the right shape for the anchor: it does **not** build a second orchestration
runtime — it rides `codex exec` (the existing OpenAI primitive) + the mounted `codex mcp-server` rail,
and Axis-C rides the **existing native Workflow engine** (`agent()`/`parallel()`) on top. The Axis-C
deliverable here is a **thin `codexAgent()` helper + a schema-file bridge + a deploy/pin prerequisite**
— "author a reusable helper on top of the native engine," not new infra. The 5 profiles, the error
contract, codex-doctor, and the unified monitor are already built and reusable as-is.
