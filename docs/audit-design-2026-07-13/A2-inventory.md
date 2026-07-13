# A2 — Multi-Provider Inventory + Source-to-Runtime Provenance (Phase 2, 2026-07-13)

**Workflow A / Phase 2 (EVIDENCE).** Read-only audit-design. **ACTIVE-WORK FREEZE honored** —
nothing built, committed, deployed, restarted, or modified; the only writes are this file and
`A2-inventory.json` in `docs/audit-design-2026-07-13/`. Machine-readable inventory =
[`A2-inventory.json`](./A2-inventory.json); this note is the narrative provenance + the
reconciliation deltas against prior art.

**Method.** Reconciled — not re-discovered — from four inputs: the Codex control-plane inventory
(`Documents/Codex/2026-07-13/…/outputs/harness-current-state-inventory-2026-07-13.json`, cited
`Codex-inv:<line>`), the Axis-A converged audit + `inventory-{0..3}.md`, and **direct live
disk/config/git verification this session** (cited by exact path + line/key). Every load-bearing
claim carries a confidence band. Presence was never used to infer liveness; hook wiring and code
presence were content-verified by grep.

---

## 1. Headline — the critical live-wiring note is CONFIRMED and EXTENDED to THREE hook subsystems

The prompt asked to verify: *the `~/.agents/harness` dispatcher (settings.json matcher `.*`) is the
real hook loader and does NOT read the toolchain `hooks/_dispatch/manifest.json` (repo-vs-live
split).* **Confirmed (~95%)** — and the split is richer than a single repo-vs-live pair. There are
**three overlapping hook subsystems on disk; exactly one is wired through `settings.json`:**

| # | Subsystem | Loader path | Wired? | Evidence |
|---|---|---|---|---|
| **A** | **Shared harness dispatcher** (the real loader) | `settings.json:79-331` → `python ~/.agents/harness/dispatcher.py --provider claude --event <E>` for **17 events**; `dispatcher.py:15-19` imports `harness.modules.build_default_modules` (a Python **module mixer**, not a manifest) | **YES** | Read `settings.json`; grep `dispatcher.py` |
| **B** | **Manifest dispatcher** `hooks/_dispatch/` | `dispatch.py` *docstring* claims Claude calls `python ~/.claude/hooks/_dispatch/dispatch.py <event>` and reads `manifest.json` to run ~13 check scripts in-process | **NO** — zero reference in current `settings.json`; live `modules.py` has zero reference to it (grep: only a comment `@684`) | Read toolchain `hooks/_dispatch/dispatch.py:1-46` + `manifest.json`; exists live too (`~/.claude/hooks/_dispatch/`) |
| **C** | **ECC plugin `hooks.json`** | `~/.claude/hooks/hooks.json` — `${CLAUDE_PLUGIN_ROOT}/scripts/hooks/*.js` (block-no-verify, continuous-learning, cost-tracker…) | **NO** — `ecc@everything-claude-code=false` (`settings.json:410`) | Read `~/.claude/hooks/hooks.json` |

Subsystem **A** (module mixer in `~/.agents/harness/modules.py`) is the live control-plane.
Subsystem **B** (the toolchain `_dispatch/manifest.json` design) is present in **both** the repo and
live (`~/.claude/hooks/_dispatch/`) but **is not wired** — it is the repo-vs-live split the prompt
flagged. Subsystem **C** belongs to a **disabled** plugin, hence dormant. On top of B, **65 hook
script dirs** live under `~/.claude/hooks/` whose capability names (goal-reinject, semantic-router,
mcp-canonical-sync, wire-check, stub-ledger, …) **overlap the harness modules** — strong evidence
the module mixer **consolidated/reimplemented** them; only **2 of 65** (`local-tui-reminder`,
`workflow-monitor-autolaunch`) are individually wired in `settings.json`. Whether the remaining ~63
still fire (via the unwired dispatcher) is **UNRESOLVED** — a live-vs-live split needing a runtime
firing check (medium ~65%). This nuance qualifies the memory claim *"61/61 hooks fire"*
(`reference_harness_health_verdict_2026-07-04`): under the current wiring, the harness **modules**
fire; the 65 standalone **script dirs** are not individually wired.

**Cross-provider:** Codex wires the **same** shared engine — `~/.codex/hooks.json` routes 10 events
to `~/.agents/harness/dispatcher.py --provider codex` (trusted by sha256 in `config.toml:336-367`).
**Gemini and Antigravity wire ZERO harness hooks** (no `hooks` key in either `settings.json`) → for
hook enforcement the "all three first-class" goal is **currently Claude+Codex-only** (R6).

---

## 2. Source-to-runtime provenance — the four providers

| Provider | Version | Model / reasoning | Versioned source | Live/loader path | Hooks | Runtime |
|---|---|---|---|---|---|---|
| **Claude Code** | 2.1.207 | `opus[1m]` · xhigh · fallback sonnet-5 | harness `install.py build_hooks` | `~/.claude/settings.json` (+ `settings.local.json`) | **17 events → harness** | 2 procs |
| **Codex CLI** | 0.144.1 | `gpt-5.6-sol` · medium (plan=ultra) · approval=never · sandbox=danger-full-access | `ast-harness-reconcile/tools/codex/profiles` | `~/.codex/config.toml` | **10 events → same harness** | 5 procs |
| **Gemini CLI** | 0.45.2 | `gemini-3.1-pro-preview` · auto_edit | `release/platforms/windows/gemini-settings.json` | `~/.gemini/settings.json` | **none** | 0 procs |
| **Antigravity** | 1.1.1 | `Claude Opus 4.6 (Thinking)` · always-proceed · G1 credits | unresolved | `~/.gemini/antigravity-cli/` (shares `.gemini`) | **none** | 0 procs |

*Evidence: `settings.json:75,487`; `config.toml:1-18`; `gemini/settings.json:328`;
`gemini/antigravity-cli/settings.json:10`; versions `Codex-inv:26-29`; procs `Codex-inv:304-307`.*

**Antigravity provenance (R5, weakest-documented, now resolved):** `~/.antigravitycli/` is a **0-byte
stub** (one empty json). The real footprint is `~/.gemini/antigravity-cli/` (bin/brain/knowledge/mcp/
conversations + `settings.json` + `history.jsonl` 156 KB + `conversation_summaries.db`). Its
`mcp_config.json` is a **SYMLINK** (PowerShell `LinkType=SymbolicLink`) → `~/.gemini/config/
mcp_config.json`, which registers **2 servers, both `disabled:true`** (`agentchattr` :8200,
`chrome-devtools`). Antigravity is a Gemini-family CLI running a **Claude** model on GCP project
`webcoder-462916`.

---

## 3. Harness engine provenance + the R1 re-deploy finding

`~/.agents/harness/` is the live engine (`dispatcher.py`, `modules.py` 108 KB, `install.py`,
`ledger.py`, `registration.py`, `adapters.py`, …). It is **not a git repo** — edited in place; its
enshrined mirror is `ast-harness-reconcile/ci/harness`. `installed.json` is the deployment receipt
(`deployed_at 2026-07-13T05:14:32+00:00`, **`source_commit: null`** — no git provenance on the
receipt, a residual gap).

**R1 — the prior audits' headline is now STALE (high, ~90%).** The Codex inventory (06:30) and the
converged audit (07:51) both said the task-8 enforcement layer was **committed but inert/undeployed
on live**. Verified this session: live `modules.py` mtime **08:12:01** / **108,296 B** (the converged
audit saw **96,769 B** at 07:51), and grep confirms the enforcement is **now live**:
`_canonical_config_edit_guard` `@673`, `basic_memory_nudge` `@1883`, `_config_drift` `@700`,
`_live_trees`/`_canonical_tree` `@402/@426`; live `install.py` has `def deploy@700` + `--deploy@831`
(CAS-lite + single-writer lock + parity). `installed.json deployed_at` (05:14:32 UTC = **08:14
EEST**) places the deploy at ~08:12-08:14 today — **after both prior audits**. **Caveats:** the gates
ship on `TIER_HEURISTIC` → **SHADOW** (`modules.py:1921`, observe-only, not enforcing); full live↔repo
tree-parity is **not** verified (the `install.py --check` thread-9 gap the audit named). So: **task-8
code is now deployed but shadow-mode; the "inert" claim is falsified, the "not enforcing" claim
still holds.** (Do not infer this was done by me — freeze honored; it was a concurrent owner/session
deploy, consistent with the converged audit's Wave-0 runbook.)

---

## 4. MCP registration provenance — a TRIPLE canonical split (R3)

| Store | Path | Count | Role / provenance |
|---|---|---|---|
| Claude canonical (live) | `~/.mcp.json` | **42** | hand-curated; read by promote script + per-tree walk-up; **includes** angr/search-hub/agent-mail/biomni-hub (verified) |
| Claude user (live-loaded) | `~/.claude.json` mcpServers | **63** | actual session load; drift **+22/−1** vs canonical; clobbered on exit |
| Claude project:home | `~/.mcp.json` as project | 42 (12 active) | `settings.local.json enabledMcpjsonServers`=12, `enableAllProjectMcpServers=false` (verified) |
| Claude project:research | `D:/Research/.mcp.json` | 40 | stale frozen mirror (pre-reconcile bugs) |
| Codex | `~/.codex/config.toml [mcp_servers.*]` | ~24 (~14 on) | inline TOML; `codacy` enabled `@460`; `github_cli` off `@467`; `github` block removed `@398` |
| Gemini | `~/.gemini/settings.json mcpServers` | **33** | carries cloud-quality family + `playwright-mcp`; `ralph-orchestrator` via WSL |
| Antigravity | `~/.gemini/config/mcp_config.json` | **2** | both disabled; symlinked from `antigravity-cli/` |
| Repo canonical A | `agent-skills-toolchain/tools/mcp/canonical-mcp-servers.json` | **44** | sha `f406d9` |
| Repo canonical B | `ast-harness-reconcile/tools/mcp/canonical-mcp-servers.json` | **43** | sha `8d2bc7` |

**The MCP authority conflict is TRIPLE, not the double the Codex audit framed (AUTH-MCP-001):**
`42` (live `~/.mcp.json`) vs `43` (reconcile repo) vs `44` (toolchain repo). The resurfacing of the
`codacy/deepsource/sonarqube/codecov/deepscan` cloud-quality family rides the **plugin bridge at user
scope** (`plugin:local-mcp-bridge:*` in `~/.claude.json`), a surface the drift gate does not watch
(inventory-1 §2, inventory-3 thread-1). *(Counts cross-verified: this session + `Codex-inv:33-49`.)*

---

## 5. Skills / commands / agents / memory (provenance highlights)

- **Skills — three-lane fan with drift:** VCS `agent-skills-toolchain/skills` **192** → runtime vault
  `~/.agents/skills` **278** (COPIED not symlinked; semantic-router indexes it) → session view
  `~/.claude/skills → skills.daily` **75**. The vault holds **86** skills absent from VCS
  (un-enshrined) — copy-not-symlink → silent divergence (inventory-2 §C). Codex + Gemini keep separate
  copies.
- **Commands:** `~/.claude/commands` = **70** `.md` (+ plugin commands). **Agents:** `~/.claude/agents`
  = **17** (agent-as-judge, architect, chief-of-staff, code-reviewer, harness-optimizer,
  intent-drift-sentinel, planner, security-reviewer, tdd-guide, … ; verified list) + metaswarm's 18 via
  plugin. Codex `[agents] max_threads=8 max_depth=1` (`config.toml:72-74`).
- **Model/reasoning profiles:** Codex ships **three preset overlays** — `max.config.toml`
  (ultra/danger-full/fast), `strict.config.toml` (high/read-only/flex), `balanced.config.toml`
  (high/workspace-write/fast) — 182-184 B each, applied via `codex-profiles.ps1` over the base
  `config.toml`.
- **Memory (R4):** shared `basic-memory` HTTP `:8765` (LIVE). Codex's real memory is **sqlite**
  (`memories_1.sqlite` 413 KB, `goals_1.sqlite`, `state_5.sqlite` 8.3 MB, `logs_2.sqlite` **331 MB**) +
  `[memories] use_memories=true`; the prompt-named **`~/.codex/memory.jsonl` is 0 bytes / vestigial** —
  do not treat it as the Codex store. Gemini uses a `memory` MCP → `~/.gemini/memory.jsonl`.

---

## 6. Gaps, conflicts, and confidence

- **HIGH confidence** (direct read this session): all provider config paths/keys, the 3-subsystem hook
  finding, the R1 task-8 re-deploy, the triple MCP canonical split, the antigravity symlink, the empty
  codex `memory.jsonl`, Gemini/Antigravity hook-gap.
- **MEDIUM** (needs a runtime check, out of scope for read-only): whether the ~63 unwired
  `~/.claude/hooks/*` script dirs still fire; whether `hookify` (enabled) loads the ECC `hooks.json`;
  full live↔repo-HEAD harness tree-parity (the `--check` gap); Codex/Gemini skill + agent counts.
- **Observed, not to fix here (per prompt):** `agent-mail :8812` DOWN; MCP connections broadly unstable
  this session (R7).
- **Owner-facing conflicts already logged** (do not silently resolve): triple MCP canonical (R3);
  `~/.agents/harness` un-versioned vs `ci/harness` (source-of-truth choice = Codex-inv OWNER-2);
  `source_commit: null` on the deploy receipt.

*All findings are PROPOSED evidence for Workflow A. Nothing here authorizes a change; any
emergency item is recorded as a finding, never applied.*
