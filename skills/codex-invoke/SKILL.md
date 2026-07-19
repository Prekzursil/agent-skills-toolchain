---
name: codex-invoke
description: The ONE canonical entry point for invoking OpenAI Codex from any Claude session or Workflow with per-call scoping. Use whenever you need to run `codex exec` (or drive the `mcp__codex__codex` / `codex-reply` rail) with a specific model, reasoning effort, sandbox/approval policy, an MCP-server allowlist or seal, a skills allowlist, or structured `--output-schema` output — and you want it built Windows-safe, DRY-RUN-previewable, and guarded by an explicit SUCCESS/FAILED error contract. Triggers include "run this with Codex scoped to read-only", "fan out a sealed zero-MCP Codex job", "invoke Codex with the audit profile", "give me the exact codex argv (dry run)", "Codex one-shot with only these MCPs/skills", "structured-output Codex call". Picks the rail automatically (any scoping request forces the exec rail — the only rail that can scope) and states which it used. NEVER hand-roll `codex exec` argv — route through here. Ships a `codex-doctor` health-check (auth / config-parse / MCP-reach / model-slug resolve-or-fallback / exec-runtime scope proof). NOT for in-session intent routing of the MCP rail (use codex-orchestrate), the PromptBridge consult/curate/review lanes (use codex-consult), VS Code host transport (use codex-vscode-host-routing), or split-store recovery (use codex-runtime-recovery).
license: MIT
---

# Codex Invoke

The single, definitory way to invoke Codex with **per-call scoping**. Every other
codex skill either routes intent on the always-full MCP rail (`codex-orchestrate`,
`codex-consult`) or handles a different axis (transport, recovery, session hygiene).
**This skill owns the exec rail and is the only one that can scope a Codex run**
(restrict its MCP servers, seal its base, or allowlist its skills).

**Definitory rule: never hand-roll `codex exec` argv anywhere. Route through
`scripts/codex_invoke.ps1`.** It builds a Windows-safe argv array, materializes the
scope exactly once, previews it with `--print-command`, and wraps the run in the
error contract below.

Verified live against **codex-cli 0.144.1** (flags, `mcp get/list --json -c`, and the
`mcp … --ignore-user-config` rejection — see Ground Truth).

---

## Canonical docs

The full HOW-TO (rail decision table, the 5 profiles, M0–M3, DRY-RUN honesty, error
contract, deploy) lives in **[`guides/codex-invocation.md`](../../guides/codex-invocation.md)**.
Watching a run live on **either** rail is specified in
**[`guides/codex-monitor-reconcile.md`](../../guides/codex-monitor-reconcile.md)** — the ONE
documented way: `run-taskwatch_monitor` for one detached `codex exec`, the `workflow-monitor`
Codex lane for an in-session `mcp__codex__codex` call / the whole fan-out.

---

## Rails — which knob each supports

The skill auto-picks the rail and **states which one it used** in its output.

| Knob | `exec` rail (`codex exec`) | MCP rail (`mcp__codex__codex` / `codex-reply`) |
|---|---|---|
| model / effort | `-m` / `-c model_reasoning_effort` | tool params |
| profile scalar keys | materialized `-c` from `<name>.config.toml` | inherits base only |
| **MCP allowlist / seal** | M0 static / M1 diff-disable / M2 sealed | inherits full base — no per-call scoping |
| skills allowlist | ephemeral CODEX_HOME + materialized `config.toml` | base skills only |
| structured output | `--output-schema <file>` | MCP typed output (⚠ landmine below) |
| detached / one-shot | background + `codex resume` | in-session only |
| threadId continuation | `codex exec resume --last` | `codex-reply(threadId)` |

**Routing rule:** *any* `mcps` / `skills` / `seal` request → **exec rail** (the only
rail that can scope). Otherwise a plain model/effort call may ride the MCP rail.

⚠ **Workflow landmine:** a typed `--output-schema` on the exec rail while MCP tools
are active can break (see `workflow-authoring`). The DRY-RUN surfaces this; the
`fanout-json` profile (sealed, zero-MCP) is the safe structured-output path.

---

## Scoping mechanisms (keyed off `<name>.scope.json.mode`)

Profiles give the *easy* axis (model/effort/sandbox/approval/web_search) via
materialized `-c`. True scoping needs one of four mechanisms — because a static
profile cannot express "disable everything NOT in this allowlist" against a base
whose future server names are unknown at author time.

- **M0 — Static disable (known base, no live read).** `.config.toml` carries
  explicit `mcp_servers.<name>.enabled=false` lines; materialized as `-c`. Fully
  offline, deterministic, `--strict-config`-clean. Use when the base set is stable.
- **M1 — Difference-disable (default; drift-robust).** Enumerate the live base once
  via `codex mcp list --json`, compute `live_base − mcp_allowlist`, emit
  `-c mcp_servers.<x>.enabled=false` for each. Anything the base gains that isn't
  allowlisted is auto-disabled.
- **M2 — Sealed base (`seal:true`).** Two strictly-separated sub-modes:
  - **M2a — Full-seal / zero-MCP (empty allowlist).** `--ignore-user-config` drops the
    base entirely; no enable-block supplied → runtime loads zero MCP servers. The
    fan-out path. **Allowed only with an empty allowlist.**
  - **M2b — Sealed + explicit allowlist (non-empty).** `--ignore-user-config` drops the
    base, then supply a fully explicit `-c mcp_servers.<x>.command/.args/.env` ENABLE
    block for only the allowlisted servers. **Definitions are harvested from the live
    base** (`codex mcp get <name> --json`, secrets as `${VAR}`) into
    `.scope.json.captured_mcp_defs` — never invented. **Fail-closed:** seal + non-empty
    allowlist but no captured def (or an unset `${VAR}`) → refuse
    (`FAILED:<id> seal-uncaptured`).
- **M3 — Feature/tool toggles.** `web_search="disabled"` in the toml +
  `--enable/--disable <feature>` per `.scope.json.tools`.

**Skills scoping** (no native per-invocation flag exists): when `skills_allowlist` is
non-empty the skill stages an **ephemeral CODEX_HOME** (`$TMP/codex-scope-<hash>/`)
holding (1) copied `auth.json`, (2) a **materialized `config.toml`** carrying exactly
the allowlisted MCP defs (harvested — an ephemeral home does NOT inherit the base
config, so without this step the run would silently have zero MCPs) **plus** the
profile scalar keys, and (3) a `skills/` dir with only the allowlisted skills. The
ephemeral home is passed to the **codex child process only** (never a session-global
`CODEX_HOME` export) inside a `try/finally` that restores the prior value.

---

## DRY-RUN / `--print-command` (mandatory)

`codex_invoke.ps1 -PrintCommand` emits the **exact** argv it will run — resolved
canonical CODEX_HOME, the single-materialized `-c` disable-set / enable-block, `-s`,
`--output-schema`, `-C`, `--skip-git-repo-check`, chosen rail — and runs nothing
**beyond the one live config read** the materialization requires. The launch reuses
the identical cached set (single-materialization rule), so `--print-command` can
never print a set the launch won't use.

**Honesty note:** M1/M2b/skills perform **one live read** (`codex mcp list --json`
and/or `codex mcp get --json`, read-only, no state mutation) to compute the set — so
DRY-RUN is *not* fully offline for those modes. **M0 and M2a require no live read and
ARE offline.** Base drift between print and launch is *detected* via
`base_snapshot_hash`, not silently divergent.

---

## ERROR CONTRACT (explicit — AGENTS.md §4)

Every invocation ends in a terminal marker: `SUCCESS:<id>` or `FAILED:<id> <reason>`.

1. **Malformed-config (deterministic, no timing guess).** Classified on **exit code +
   the codex stderr parse-error signature** ("failed to parse config" / unrecognized
   key), NEVER wall-clock — a legit fast one-shot yields an empty `-o` in <2s, and a
   malformed config can hang. `--strict-config` is also probed **unconditionally at
   deploy/doctor time**, so parse failures are caught proactively. Runtime signature →
   `FAILED:<id> config-parse` + route to **`codex-runtime-recovery`**.
2. **Auth/quota preflight.** `codex login status` first (exit 0 == "Logged in using
   ChatGPT" — codex-cli 0.144.1 has **no** `codex auth status` subcommand); on 5h rate
   cap / weekly cap / `429` / budget-pause → no retry-storm; `FAILED:<id> quota` + reset
   window. A transient probe `429` ≠ exhaustion (fall back to cached status).
3. **Timeout.** Wrap via `longrun` (`-HangTimeoutSec`), detached + `Monitor`
   (AGENTS.md §4a) — never a blocking foreground call.
4. **Detached-run recovery.** Record session id + `-o` path; recovery re-reads the log
   and `codex resume`s (reuse **`codex-runtime-recovery`** + **`run-taskwatch_monitor`**).
5. **Scope-assertion (fail-closed).** If the exec-runtime scope proof shows a forbidden
   server loaded, or a required def is uncaptured → refuse to launch,
   `FAILED:<id> scope-breach` / `seal-uncaptured`. A scoping mechanism that can't prove
   its scope must not run.
6. **Base drift.** Live-base hash ≠ pinned `base_snapshot_hash` → `WARN base-drift`;
   re-harvest for M2b/skills before proceeding.

The **0-second-exit** case (auth/config failure that dies instantly) is caught by
clauses 1+2 via exit-code+signature, not by treating a fast exit as failure.

---

## Windows-safe command construction (ACCEPTANCE CRITERION)

- Build argv as a **PowerShell array** (`& codex @args`) — never a shell string.
- **No Git-Bash** for any `codex -C <path>` or device-ish arg (MSYS path-conversion
  truncation, windows-shell.md §1). The builder is `.ps1`; if a POSIX arg is
  unavoidable, `MSYS_NO_PATHCONV=1`.
- Never `New-Item -Force` on an existing profile file (windows-shell.md §4); the
  deployer uses `Set-Content`/copy.
- The smoke matrix round-trips the **real** footguns byte-exact through `& codex @args`
  on PowerShell 7 (not just a generic argv): (1) multi-element array with spaces
  `-c 'mcp_servers.x.args=["a b","c d"]'`; (2) env sub-table
  `-c 'mcp_servers.x.env={API_KEY="${API_KEY}",REGION="eu west"}'`; (3) `${VAR}`
  placeholders survive un-expanded; (4) values containing `$`/`[`/`]`/quotes/spaces.
  Each asserts the string codex *receives* (`codex mcp get x -c … --json`) equals the
  intent. This is the acceptance gate for the M2b/skills materialization path.

---

## codex-doctor (health-check + config-lint)

`scripts/codex_doctor.ps1` (canonical CODEX_HOME). Runs proactively at deploy and per
codex release:

1. `codex login status` → authed? (exit 0 == logged in; `codex auth status` does not exist).
2. Each `<name>.config.toml` parses **and is `--strict-config`-clean** (unconditional,
   **token-free**). The profile is staged as the sole `config.toml` of an *unauthenticated*
   temp `CODEX_HOME` and run under `codex exec --strict-config` with a deliberately-absent
   `--output-schema`: a malformed config dies at config-load ("Error loading config.toml"),
   a clean config short-circuits on the missing schema — **before any auth or network**, so
   a clean profile never spends a token. Verdict keys on the parse-error signature.
3. Each `.scope.json` parses; every `mcp_allowlist` name exists in the live base.
4. **Model slug declared** (offline structural check only — codex 0.144.1 has no offline
   model-resolve probe, so there is no `--print-command`). The slug's **real resolution** is
   proven live in check 6 (`-Live`): an `unknown model` in the exec-runtime run →
   resolve-or-fallback to `.scope.json.model_fallbacks`, warn on fallback.
5. **Harvest + pin:** for seal+allowlist or skills profiles, harvest
   `codex mcp get <name> --json` into `captured_mcp_defs` (`${VAR}` secrets), record
   `base_snapshot_hash`; fail-closed on any uncaptured def (`seal-uncaptured`).
6. **Exec-runtime scope proof (the anti-fake check):** materialize each profile's
   flags, run a real `codex exec --json` no-op, parse the startup/session events for the
   **actual loaded MCP + tool inventory**, assert `loaded_mcp_set == mcp_allowlist`
   (and, for skills profiles run with `CODEX_HOME=<ephemeral>`, `loaded_skills ⊆
   skills_allowlist`). This is the ONLY proof valid under seal — `codex mcp list` cannot
   be sealed (G3) and proves the resolver, not the runtime. Re-run per release.

The doctor pins the `codex exec --json` startup-event shape via a shared fixture (also
consumed by the monitor lane); if the event schema changes it **fails loudly** rather
than trusting a stale parse.

---

## Parameters (`scripts/codex_invoke.ps1`)

`-Model -Effort -Profile -Mcps[] -Skills[] -Tools -Sandbox -Approval -OutputSchema
-Seal -Mode(M0|M1|M2) -Rail(auto|exec|mcp) -Cwd -Prompt -Timeout -Id -PrintCommand
-Doctor -ProfilesDir`.

- `-Mcps` overrides the profile allowlist; `-Rail auto` (default) applies the routing
  rule; `-Doctor` shells to `codex_doctor.ps1`.
- Profiles are read from `-ProfilesDir` (default: repo `tools/codex/profiles/`, then
  `$CODEX_HOME/profiles/`). CODEX_HOME resolves via `HARNESS_LIVE_CODEX_HOME` →
  `~/.codex` (never a possibly-ephemeral bare `CODEX_HOME`).

## The 5 recommended profiles

| Profile | model / effort | sandbox / approval | web | mcp_allowlist | mode | seal | skills |
|---|---|---|---|---|---|---|---|
| **audit-readonly-max** | gpt-5.6-sol / max | read-only / never | live | read-only: basic-memory, scholarly-access, context7, deepwiki, repomix, semgrep | M1 | no | RE/analysis read set |
| **build-sandboxed** | gpt-5.6-sol / high | workspace-write / on-request | live | context7, repomix, qlty, codacy, github, basic-memory | M1 / ephemeral if skills | no | tdd-workflow, python-testing, security-review, systematic-debugging |
| **exec-fast** | gpt-5.6-sol / medium | workspace-write / on-request (fast tier) | disabled | basic-memory only | M0 | no | none |
| **fanout-json** | gpt-5.6-sol / max | read-only / never | disabled | none | M2a | yes | none |
| **consult-review** | gpt-5.6-sol / max | read-only / never | live | context7, deepwiki, exa, firecrawl, tavily, scholarly-access | M1 / ephemeral if skills | no | receiving-code-review, rubric-verifier, acceptance-review |

`build-sandboxed` and `consult-review` carry both a non-empty skills AND MCP allowlist
→ they run in an ephemeral home whose materialized `config.toml` carries exactly the
allowlisted MCP defs (else the MCPs silently vanish on the skills path).

**Secrets discipline:** MCP creds are `env_vars=["NAME"]` / `${VAR}` only — never inline,
in the base, in `captured_mcp_defs`, or in any materialized ephemeral config.
`.scope.json` carries names + `${VAR}` placeholders, never secret values.

---

## Reconciliation — how this skill relates to the others

**NEW skill (the canonical exec-rail entry point). It does not overlap the existing
three** — `codex-orchestrate` (MCP-rail intent routing), `codex-consult` (PromptBridge
lanes), and `codex-vscode-host-routing` (IDE transport) are orthogonal axes; there is
no 4th overlapping skill.

- **Leverages (cites, does not rebuild):** `codex-runtime-recovery` (fast-exit /
  detached-run / CODEX_HOME-drift recovery), `run-taskwatch_monitor` (detached-exec
  JSONL adapter), `workflow-monitor` (the cross-vendor cockpit's Codex lane),
  `codex-fleet-github` (shares the skill-allowlist file format).
- **Session hygiene continuation:** `codex-session-reunion` / `format-codex-sessions`.
- **Integration owed by the design (scoped work, not a free cross-link):**
  `codex-orchestrate` and `codex-consult` each gain an **exec-rail delegation branch**
  that fires on any scoping request and delegates to this skill, each with its own test.
  Until those edits ship they remain MCP/PromptBridge-only.

## Ground Truth (verified live, codex-cli 0.144.1)

- `codex exec` exposes `-c/--config`, `--strict-config`, `-m`, `-s`, `-C`,
  `--output-schema`, `--output-last-message`, `--ignore-user-config`,
  `--enable`/`--disable`, `--skip-git-repo-check`, `--json`, `--profile`. **PRESENT.**
- `codex mcp get --json -c` and `codex mcp list --json -c` — **PRESENT** (harvest +
  config-resolver surfaces).
- `codex mcp list --ignore-user-config` → **REJECTED** ("unexpected argument") — the
  `mcp` subcommand cannot be sealed, so a sealed profile's only valid scope proof is the
  **exec-runtime** `codex exec --json` startup-event inventory (G3).
- **`codex auth status` and `codex exec --print-command` do NOT exist** in 0.144.1. The
  auth probe is **`codex login status`** (exit 0 == "Logged in using ChatGPT"). There is
  **no** flag that prints the resolved argv or dry-resolves a model, and `-c
  config_path=<file>` is **not** an external-config loader (it just sets an unknown key).
  Strict-config lint therefore loads the profile as a staged temp-`CODEX_HOME`
  `config.toml` under `codex exec --strict-config` and keys on the `Error loading
  config.toml` parse signature (token-free — a missing `--output-schema` short-circuits a
  clean config before any auth/network). `--strict-config` is honored **only** by `codex
  exec` (rejected by `codex mcp` / `codex features`).
