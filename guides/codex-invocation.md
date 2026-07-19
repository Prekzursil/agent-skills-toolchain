# Codex Invocation — the canonical HOW-TO

> **Definitory rule:** *To invoke Codex with per-call scoping from any session or Workflow, use the
> `codex-invoke` skill (exec rail). Never hand-roll `codex exec` argv.*

This is the one place that documents how to run Codex locally with per-call control over model,
effort, sandbox, approvals, MCP servers, skills, and structured output — and how to **watch** a run
live on either rail. It is grounded on `codex-cli 0.144.1` (verified) and the `ast-harness-reconcile`
harness. Sibling doc: [`codex-monitor-reconcile.md`](codex-monitor-reconcile.md) — the ONE documented
way to watch both rails.

---

## 1. Two rails — pick by whether you need scoping

Codex is reachable two ways. They are **not interchangeable**; the axis that decides is *scoping*.

| Knob | `exec` rail (`codex exec …`) | MCP rail (`mcp__codex__codex` / `codex-reply`) |
|---|---|---|
| model / effort | yes — `-m` / `-c model_reasoning_effort` | yes — tool params |
| profile scalar keys | yes — materialized as `-c` from `profiles/<name>.config.toml` | no — inherits base only |
| **MCP allowlist / seal** | **yes** — M0 static / M1 diff-disable / M2 sealed | **no** — inherits the full base, no per-call scoping |
| skills allowlist | yes — ephemeral `CODEX_HOME` + materialized `config.toml` | no — base skills |
| structured output | yes — `--output-schema` | yes — MCP typed output (see landmine below) |
| detached / one-shot | yes — background + `codex resume` | no — in-session only |
| threadId continuation | yes — `codex exec resume --last` | yes — `codex-reply(threadId)` |

**Routing rule (the skill applies this automatically and states which rail it chose):**
> Any request that scopes MCP servers, skills, or asks to seal the base → **`exec` rail** — it is the
> only rail that can scope. Everything else may use either; the MCP rail is the in-session default.

**Workflow landmine:** a typed `--output-schema` on the exec rail while MCP tools are active can
break structured output. The DRY-RUN surfaces this; the `fanout-json` profile (M2a sealed, zero-MCP)
is the safe structured-output path.

---

## 2. The five profiles

Profiles are versioned pairs under `tools/codex/profiles/` (repo source of truth), deployed to the
dedicated subdir `$CODEX_HOME/profiles/` (never the `CODEX_HOME` root, which holds only codex's own
`config.toml` / `auth.json` / state). Each profile is **two files**:

- `<name>.config.toml` — **only real codex keys** (`--strict-config`-clean): `model`,
  `model_reasoning_effort`, `approval_policy`, `sandbox_mode`, `web_search`, `service_tier`,
  `[tools.web_search]`, `[shell_environment_policy]`. The skill **reads this and materializes each
  scalar key as a `-c key=value` override** — it does not use native `-p`. It carries **no inline
  `mcp_servers` table**: a standalone config whose `mcp_servers.<x>` entry has no transport is a HARD
  codex load error ("invalid transport") and cannot load. M0 disables live in the scope sidecar
  (`static_disable`) and are applied as `-c` overrides at launch (see §3, M0).
- `<name>.scope.json` — the scoping manifest codex never parses: `mode` (M0/M1/M2),
  `mcp_allowlist`, `tools`, `skills_allowlist`, `seal`, `model_fallbacks`, `captured_mcp_defs`,
  `base_snapshot_hash`, `notes`. Carries **no secret values** — MCP creds are `${VAR}` placeholders only.

| Profile | model / effort | sandbox / approval | web_search | MCP allowlist | mode | seal | skills | Use |
|---|---|---|---|---|---|---|---|---|
| **audit-readonly-max** | gpt-5.6-sol / `max` | `read-only` / `never` | live | read-only only: `basic-memory, scholarly-access, context7, deepwiki, repomix, semgrep` — zero write-capable MCPs | M1 | no | RE/analysis read set | Deep read-only audits |
| **build-sandboxed** | gpt-5.6-sol / `high` | `workspace-write` / `on-request` | live | `context7, repomix, qlty, codacy, github, basic-memory` | M1 (or ephemeral if skills set) | no | `tdd-workflow, python-testing, security-review, systematic-debugging` | Scoped implementation with approvals |
| **exec-fast** | gpt-5.6-sol / `medium` | `workspace-write` / `on-request`, `service_tier="fast"` | disabled | `basic-memory` only | **M0** (static disable, no live read) | no | none | Quick one-shots / cheap iterations |
| **fanout-json** | gpt-5.6-sol / `max` | `read-only` / `never` | disabled | **none** | **M2a** (seal, empty allowlist, zero-MCP) | **yes** | none | Parallel detached fan-out with `--output-schema` |
| **consult-review** | gpt-5.6-sol / `max` | `read-only` / `never` | live | `context7, deepwiki, exa, firecrawl, tavily, scholarly-access` | M1 (or ephemeral if skills set) | no | `receiving-code-review, rubric-verifier, acceptance-review` | Advisory / review passes |

`build-sandboxed` and `consult-review` carry **both** a non-empty `skills_allowlist` and a non-empty
`mcp_allowlist`; on the skills path they run in an ephemeral home whose materialized `config.toml`
carries exactly the allowlisted MCP defs (see §3), so their MCPs do not silently vanish.

---

## 3. The four scoping mechanisms (M0–M3)

Selected by `<name>.scope.json.mode`. The exec rail is the only rail that can scope (§1).

- **M0 — Static disable (known base, no live read).** The `.scope.json.static_disable` list
  enumerates `base − mcp_allowlist` (pre-computed offline against `mcp-manifest.json`); the skill
  materializes each as a `-c mcp_servers.<name>.enabled=false` **override**. The disables are NOT
  carried as inline `mcp_servers` lines in `.config.toml` — codex rejects a transport-less standalone
  entry ("invalid transport"), whereas a `-c` override rides the transport-carrying base server and
  disables it. Fully offline, deterministic, `--strict-config`-clean. **Fail-closed:** an M0 profile
  with an empty `static_disable` would load the FULL base unscoped, so the invoker refuses to run it
  (`FAILED:<id> m0-unscoped`) and the CI config-lint pins `static_disable == base − allowlist`. Use
  when the base is stable and you accept that a *future* base-added server is not auto-disabled (else
  M1). The simplest correct mechanism.
- **M1 — Difference-disable (default; robust to base drift).** The skill enumerates the live base
  once via `codex mcp list --json`, computes `live_base − mcp_allowlist`, and emits
  `-c mcp_servers.<x>.enabled=false` for each. Anything the base gains that is not allowlisted is
  auto-disabled. Everyday mechanism when the base drifts.
- **M2 — Sealed base (hard isolation; `seal:true`).** `--ignore-user-config` drops the base entirely.
  - **M2a — full-seal / zero-MCP** (empty allowlist): no MCP block supplied → runtime loads zero
    servers. The fan-out profile. Allowed with an **empty** allowlist only.
  - **M2b — sealed + explicit allowlist** (non-empty): the skill supplies a fully explicit
    `-c mcp_servers.<x>.command/.args/.env` ENABLE block for only the allowlisted servers. The defs
    are **harvested from the live base** at deploy/doctor time via `codex mcp get <name> --json`
    (secrets as `${VAR}`) and pinned into `captured_mcp_defs`. **Fail-closed:** sealing with a
    non-empty allowlist but no captured defs (or a `${VAR}` unset in the env) → refuse to deploy and
    refuse to launch (`FAILED:<id> seal-uncaptured`).
- **M3 — Feature/tool toggles.** `web_search="disabled"` in the toml + `--enable/--disable <feature>`
  (== `-c features.<name>=true|false`) per `.scope.json.tools`.

**Skills scoping** (no native per-call flag exists — codex loads skills from `$CODEX_HOME/skills`):
when `skills_allowlist` is non-empty the skill stages an **ephemeral scoped `CODEX_HOME`**
(`$TMP/codex-scope-<hash>/`) containing all three of — (1) copied `auth.json`; (2) a **materialized
`config.toml`** with exactly the allowlisted MCP defs (harvested from the live base) plus the profile
scalar keys, *because an ephemeral home does NOT inherit the base config.toml*; (3) a `skills/` dir
with only the allowlisted skills. The child codex process runs with `CODEX_HOME` pointed there
(child-scoped only — never a session-global export). Empty `skills_allowlist` → run in place.

**Shared primitive** feeding both M2b and the skills ephemeral home: an **MCP-definition harvest** —
`for name in allowlist: codex mcp get <name> --json → {command, args, env with ${VAR}}` — harvested at
deploy/doctor time, pinned, re-verified per codex release.

**Proof of scope (the anti-fake check).** The authoritative proof for *every* profile is the
**exec-runtime** proof: run a real `codex exec --json` no-op with the materialized flags, parse the
startup/session events for the actual loaded MCP + tool inventory, and assert it equals the allowlist.
This is the only proof that works under seal — `codex mcp list` is **rejected** with
`--ignore-user-config` (it is an exec/session-level flag; the `mcp` subcommand cannot be sealed), so
config-resolver introspection cannot verify a sealed profile and, even unsealed, proves the resolver
not the runtime. The cheap `codex mcp list --json <disable-set>` pre-check is advisory (M0/M1 only).

---

## 4. DRY-RUN + error contract

### DRY-RUN (`--print-command`, mandatory)
Emits the **exact** argv — resolved canonical `CODEX_HOME`, the single-materialized `-c`
disable-set / enable-block, `-s`, `--output-schema`, `-C`, `--skip-git-repo-check`. The disable/enable
set is **computed once**, cached, and reused for both the DRY-RUN and the launch, so the printed set is
always the launched set.

**Honesty note:** for M1 / M2b / skills, that single computation performs **one live read**
(`codex mcp list --json` and/or `codex mcp get --json`) — so DRY-RUN is a read-only spawn, **not fully
offline and not side-effect-free** (it reads live config; no state mutation). **M0 and M2a require no
live read and ARE fully offline.**

### Error contract (terminal markers `SUCCESS:<id>` / `FAILED:<id> <reason>`)
1. **Config-parse failure — deterministic, no timing guess.** Classified on **exit code + the codex
   stderr parse-error signature**, never on wall-clock. `--strict-config` is probed **unconditionally
   at deploy/doctor time**, so a malformed profile is caught proactively at deploy, not on a spend. On
   a runtime parse-error signature → `FAILED:<id> config-parse` + route to `codex-runtime-recovery`.
2. **Auth/quota preflight** (`codex login status` — exit 0 == logged in; codex-cli 0.144.1 has **no**
   `codex auth status` subcommand): on 5h rate cap / weekly cap / `429`/budget-pause → no retry-storm;
   `FAILED:<id> quota` + reset window. A transient probe `429` ≠ exhaustion.
3. **Timeout:** wrap via `longrun` (`-HangTimeoutSec`), detached + `Monitor` — never a blocking
   foreground call (AGENTS.md §4a).
4. **Detached-run recovery:** record session id + `-o` path; recovery re-reads the log and
   `codex resume`s (reuse `codex-runtime-recovery` + `run-taskwatch_monitor`).
5. **Scope-assertion failure (fail-closed):** if the exec-runtime scope proof shows a forbidden server
   loaded, or a required def is uncaptured → refuse to launch (`FAILED:<id> scope-breach` /
   `seal-uncaptured`). A scoping mechanism that cannot prove its scope must not run.
6. **Base drift:** live-base hash ≠ pinned `base_snapshot_hash` → `WARN base-drift`; re-harvest for
   M2b/skills before proceeding.

### Windows-safe construction (acceptance criterion)
- Build argv as a **PowerShell array** (`& codex @args`) — never a shell string.
- **Feed empty stdin (`'' | & codex @args`)** on every `codex exec` launch. codex-cli 0.144.1 aborts
  BEFORE doing any work when `exec` sees a piped/inherited non-terminal stdin ("Error: stdin is not a
  terminal") or null stdin with redirected stdout ("Error: stdout is not a terminal") — i.e. every
  non-interactive context (Workflow, subagent, `longrun`-with-redirect), which is the whole point of
  this invoker. The empty-string pipe gives codex an immediate-EOF stdin and lets the run proceed; it
  is the same pattern the doctor's strict-config lint uses. Without it the launcher only works from a
  real interactive TTY.
- **No Git-Bash** for any `codex -C <path>` / device-ish arg (MSYS path-conversion truncation); the
  builder is `.ps1`. If a POSIX arg is unavoidable, set `MSYS_NO_PATHCONV=1`.
- Never `New-Item -Force` on an existing profile file — the deployer uses `Set-Content`/copy.
- The smoke matrix round-trips the real footguns byte-exact through `& codex @args` on PowerShell 7:
  multi-element arrays with spaces, env sub-tables, `${VAR}` placeholders (must survive un-expanded),
  and values containing `$`/`[`/`]`/quotes — each verified against codex's parsed view
  (`codex mcp get x -c … --json`).

---

## 5. Deploy

Profiles deploy from the repo into the dedicated `$CODEX_HOME/profiles/` subdir (idempotent,
backup-first) via the harness installer:

```powershell
python ci/harness/install.py --deploy-codex   # folded into --deploy
```

After deploy, verify a profile copied and that **nothing** was written to the `CODEX_HOME` root:

```powershell
Test-Path "$env:CODEX_HOME\profiles\audit-readonly-max.config.toml"   # expect True
```

`CODEX_HOME` resolves canonically to `HARNESS_LIVE_CODEX_HOME` (pinned at deploy) or `~/.codex`. The
deployer and the edit-guard use the **same** resolver; the skill never exports `CODEX_HOME`
session-globally — an ephemeral skills-home is passed to the codex child only, inside a `try/finally`
that restores the prior value.

---

## 6. Watching a run live — pointer

There is exactly one documented way to watch **both** a detached `codex exec` run **and** an in-session
`mcp__codex__codex` call. It is specified in full in
[`codex-monitor-reconcile.md`](codex-monitor-reconcile.md). The one-line map:

| Watching | The ONE mechanism |
|---|---|
| a **detached `codex exec`** run | `codex exec --json` → JSONL; register via `run-taskwatch_monitor` |
| an **`mcp__codex__codex`** in-session call | `workflow-monitor` — its Codex lane parses the same event stream |
| everything at once (both vendors) | `workflow-monitor` cockpit — one read-only board |

Disambiguation: `/codex-monitor` = Codex-thread dashboard · `run-taskwatch_monitor` = a single
detached exec run · `workflow-monitor` = the whole fan-out (both vendors).

---

## 7. Related skills

- `codex-invoke` — **the** entry point (this doc's subject). Exec + MCP rails, DRY-RUN, error contract.
- `codex-doctor` — health-check + CI config-lint: strict-clean, allowlist ⊆ live base, slug resolves,
  harvest+pin, exec-runtime + ephemeral scope proofs (re-run per codex release).
- `codex-runtime-recovery` — detached-run / fast-exit / `CODEX_HOME`-drift recovery. The error
  contract defers to it.
- `codex-session-reunion`, `format-codex-sessions` — session-store hygiene + transcript render;
  `codex resume` continuation points at reunion for split-store cases.
- `codex-orchestrate`, `codex-consult` — in-session MCP-rail routing; each gains an exec-rail
  **delegation branch** to `codex-invoke` for scoping requests (scoped integration work, each tested).
- `codex-vscode-host-routing` — routes Codex to a VS Code host (IDE transport); an orthogonal axis,
  no overlap with `codex-invoke`. Listed here only to close "is there a 4th overlapping skill?" — no.
- `codex-fleet-github` — remote CI fan-out; shares the skill-allowlist file format.
