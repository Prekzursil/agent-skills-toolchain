# Estate coherence audit — 2026-09-25

**Scope:** MCP fleet coherence, scheduled tasks / terminal spam, skills sync, harness version-control topology, across three fronts (VM `OFFLOAD-W2025` / REPO `agent-skills-toolchain` / HOME `desktop-a60s9gp`).
**Method:** 78-agent read-only workflow (69 returned, 9 lost to `[cyber]`), 291 raw findings, 15 material findings **all 15 survived 2-lens adversarial verification**, 8 multi-engine research questions. Gaps left by failed agents were filled in the main loop and are marked *(main-loop)*.
**Posture:** nothing was applied, killed, restarted, edited or re-registered. Patches below are for review.

---

## 0. Corrections to earlier claims (recorded because they were wrong)

| Claim | Status | Truth |
|---|---|---|
| "90 identical npx wrappers from one command line" | **artifact** | `mcp_ram_audit.ps1:22-27` truncates the grouping key to 4 tokens, cutting *before* the package name. Correct: **91 distinct command lines, max multiplicity 6**. |
| "`Priv_MB` metric is broken" | **confirmed, cause found** | `:9` reads `PrivateMemorySize64`, which does not exist on a `Win32_Process` CIM object → `$null` → 0.00. Correct property `PrivatePageCount` (**bytes**). True total **20.51 GB / 333 procs**. |
| "`reframe`/`Reframe` breaks JSON parse" | **half right** | The collision is real but it is **`C:/Users/Prekzursil` vs `C:/Users/prekzursil`** (project keys). Python `json.loads` tolerates it; **PowerShell `ConvertFrom-Json` throws**. `-AsHashtable` silently keeps one of the pair. |
| "Pin subagents to 4.8 to dodge `[cyber]`" | **refuted** | All 9 failures read *"Opus 4.8's safeguards flagged"* — 4.8 trips too. Main-loop calls: **0 trips in ~75**. |

---

## 1. Root cause — the owner thesis, confirmed with the correct mechanism

**It is per-session multiplication, not orphaning.** Measured twice independently (audit + main-loop control run):

- 333 MCP-class processes, **20.51 GB** private, 95 true `npx-cli.js` wrapper hops.
- Ownership rollup: `claude.exe:20856→90`, `:26632→85`, `:10332→74`, `:28800→74`, **DEAD-PARENT→10**.
- So ~97% belong to 4 live sessions. **No MCP server process is shared between sessions.**

**Why the reaper cannot help — by construction:** `reap_orphan_mcp.ps1:34-38` lists `cmd`/`pwsh`/`powershell` in `$hostRootNames`. The chain is `claude.exe → cmd.exe → node npx-cli.js`, so **every wrapper resolves to "live-root" and is permanently unreapable**. That rail is *correctly* fail-closed (a reaper once killed a live TUI) — the error is aiming an **orphan** tool at a **duplication** problem. Four reaper implementations exist with three incompatible safety policies.

**Each `cmd /c npx -y PKG` entry costs 6 OS processes** (`claude → cmd → node(npx-cli) → cmd → node(server)` + conhost); only the last is the server. The VM has **23** such entries.

---

## 2. Symptom-masking, with evidence

- **`basic-memory-supervisor.log`: 647 lines, 2026-08-27 → 2026-09-23, 162 "starting basic-memory…" entries and no root-cause line.** 162 relaunches in ~28 days is a restart loop, not self-healing.
- **`bm-watchdog.ps1` force-kills `pwsh`/`python`/`basic-memory` before relaunch — destroying the evidence needed to diagnose.** Its own header admits the "clean termination with no crash event" was never explained. That is *why* 162 relaunches produced no diagnosis.
- **`RailHealthGuard` reports McpHub 401 every run** because its probe sends an unexpanded `${MCPHUB_TOKEN}` — a red hub may be the guard's blindness, not the service's death.
- **9 of 10 declared loopback endpoints have no listener** (only `basic-memory:18765` up). The config advertises capability the runtime is not providing, so stdio duplicates stay alive to compensate.
- **Duplicate supervisors on HOME:** `MCP-Orphan-Reaper` vs `MCPOrphanReaper`; `MCP-Promote-AtLogon` vs `MCPUserScopePromote`. **40 of 116** home tasks match watchdog/keeper/guard/reaper/supervisor.
- **Terminal spam, concretely:** `ClaudeSessionTaildrop` runs on an **Interactive** token every **PT2M** (VM-only). Home's Startup folder mixes correctly-hidden `cs-watchdog.vbs` with console scripts `biomni-autostart.bat` and `home-link-serve.cmd` — the fix pattern already exists in the same folder.

---

## 3. Cross-tool MCP matrix *(main-loop, filled after agent loss)*

| Tool | Servers |
|---|---|
| Claude VM | **88** |
| Claude HOME | **28** |
| Codex | **13** |
| Cursor | **8** |
| Gemini | **0** (config present, nothing materialized) |

- **HOME ⊂ VM exactly**: 28 shared, **HOME-only = 0**, **VM-only = 60**. Not divergence — accumulation.
- **Transport shape:** VM `20 http / 68 stdio (23 npx)` · HOME `22 http / 6 stdio (0 npx)`.
- **Wiring contradictions = 2**, both the same pattern: `hexstrike-ai` and `semgrep` are **HTTP hub endpoints on HOME** (`:31113`, `:31119`) but **local stdio** on the VM.
- **Claude↔Codex overlap = 8**; Codex-only = 5 (`apify, cve, firecrawl-kit, node_repl, sliver`); Claude-only = 80.
- Plugins re-expose ~38 servers the registry never models, incl. **19 exact-name copies**.
- **Architectural verdict: HOME is the reference implementation; the VM never inherited it.** Do **not** port home's watchdog zoo to the VM — supervision is what home's shared-daemon architecture *requires*; the VM's eager-stdio shape is the anti-pattern.

---

## 4. Discipline layer — worse than "not enforced"

- **Rules are never `@`-imported at all.** `CLAUDE.md` imports only `AGENTS.md` / `AGENTS-RUNTIME.md` / `~/AGENTS.md`. There is no §12. A rule only *loads* when (a) a numbered contract section cites it by path **and** (b) the file exists at `~/.claude/rules/common/<x>.md` (the `sync-rules.ps1` destination). **Neither holds today.**
- **`.agents/.gitignore:26-27` ignores `rules/` on a false premise** — it claims `rules/` is "a junction into ~/.claude/rules, versioned in its own home". Both halves are false: it is a real directory, and `~/.claude` is in **no git repo on either host**. Net: **the rules corpus is version-controlled nowhere.** The three rules authored 2026-09-25 exist on the VM only (they are in home's backup bundle).
- Registry SSOT is unsynced: HOME and VM `agents.json` disagree on **43 enabled flags, 2 transports, 1 server**; the sync pipe is dead.
- `~/.claude/.mcp-disabled-defaults.json` is **inert/stale** — it misrepresents control state rather than enforcing it.
- **Parked-yet-live mechanism:** an **empty** `disabledMcpServers` list on the governing project entry nullifies user-scope curation, and two case-variant project keys (`disable=120` vs `disable=0`) mean which one governs is a **cwd-casing accident**.

---

## 5. Ready patches (NOT APPLIED — review first)

**P1 — fix the instrument before trusting any number** (`REPO .agents/scripts/mcp_ram_audit.ps1`)
- `:9` `PrivateMemorySize64` → `PrivatePageCount` (bytes). Effect: `0.00 MB` → **20.51 GB**.
- `:22-27` group on the **full** `CommandLine`, truncate only for display. Effect: 1 apparent group → **91**.
- `:32` add duplicate-multiplicity + owning-session columns so the audit tool and the reaper stop being blind in identical ways.

**P2 — scope the reaper honestly** (`reap_orphan_mcp.ps1`): record that it is **orphans only** and structurally blind to live duplication; route duplicate-class bloat to `scripts/mcp_reap_duplicates.py`. **Do not loosen `$hostRootNames`.**

**P3 — declare ONE authoritative reaper**, and record `RETIRED / MERGED-INTO / SUPERSEDED-BY` for the other three.

**P4 — give every restarter an attempt ceiling, a terminal latch, and an escalation path.** Reference implementation already on disk: `mcp_agent_mail/supervisor/agentmail_supervisor.ps1` (real `/api/health` probe, exponential backoff capped 60 s, stable-run reset, 240 s grace, mutex). Add pre-restart **evidence capture** to `bm-watchdog.ps1` before its force-kill.

**P5 — un-ignore `rules/`** (`.agents/.gitignore:26-27`); ignore a specific deploy path instead if one ever lands.

**P6 — add a real §12 "Discipline rules (on-demand)"** to `AGENTS-RUNTIME.md` naming every rule path, plus a lint asserting each rule's declared loader token resolves to an existing section AND the cited file exists. Rewrite `mcp-process-hygiene.md` so it **stops prescribing the orphan reaper as the cure**.

**P7 — normalize `~/.claude.json`**: collapse the case-variant project keys; remove the empty `disabledMcpServers` override. All PowerShell consumers must use `ConvertFrom-Json -AsHashtable` (and state that it keeps one of a colliding pair).

**P8 — process-shape:** rewrite the 23 `cmd /c npx` entries to direct-interpreter form (home's shape), or move them behind the gateway. **Sequence hub liveness BEFORE any Tier-1 collapse** — collapsing while 9/10 endpoints are dead removes working capability.

**P9 — SSOT:** make `generated/claude.mcp.json` + generator **tracked**; add a backend-identity `singletonKey` (host:port, or resolved interpreter+entrypoint) to every server so duplicates become visible; fix `breach-intel`'s backspace-corrupted arg; mark the 11 dead-path stdio servers retired; make the generator **fail loud** on an unresolved `${VAR}`.

---

## 6. Open loops

0.04↔0.01 skill-budget A/B · thin-docs diet (~14.7k always-on tokens; `AGENTS-RUNTIME.md` 273 L) · `MEMORY.md` compaction (20.5/24.4 KB) · hub band liveness · 21 `microsoft-foundry` deletions · 2 `entra-*token*.md` docs blocked by the name guard · HOME live-state (run `home-command-pack.ps1`) · whether HOME's tasks actually restart-loop (**UNVERIFIED** — only names readable over rclone).
