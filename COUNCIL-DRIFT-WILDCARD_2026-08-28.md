# COUNCIL — Drift + Wildcard Architecture (2026-08-28)

Discovery/decision only. No implementation in this document.

## Executive take

- **Issue 6 (silent bridge loss):** Add a *read-only, end-of-run* “Bridge Drift Check” to `sync_shared_state.ps1` that verifies **(a) link/junction invariants**, **(b) per-runtime config presence + minimal semantic sanity**, and **(c) the “silent skip” surfaces** (notably the Claude local bridge file). Emit **high-salience warnings** (banner + `DRIFT:WARN` sentinel), and allow a strict mode to fail builds without changing default behavior.
- **Wildcard:** Stop thinking “sync writes configs” and instead adopt **“health is a first-class artifact”**: a single local health surface (status bar item / statusline / tray toast) driven by a cheap on-demand verifier. Longer-term, **offload always-on daemons (basic-memory + agent-mail) into WSL+systemd** so Windows RAM pressure and process death stop being existential.

---

## (a) Best drift-check design for Issue 6: “Bridge Drift Check”

### What we are defending against

**Silent bridge loss** means: a runtime stops being wired to the shared harness (skills/rules/MCP pointers disappear, or a “skip” path triggers) and the next user/agent experience is “things feel broken” with no immediate, obvious error.

The current `sync_shared_state.ps1` already hard-stops on some invariants (notably `.claude\skills` must remain a link), but it still has **silent/soft failure modes**, the biggest being:

- `sync_local_bridge_mcp.py` prints `skip: bridge MCP file missing: ...` and returns success if the local bridge file is missing — *exactly the kind of loss that can go unnoticed*.

### Design goals

- **Read-only:** no writes to any runtime; only `Test-Path`, `Get-Item`, small file reads, and light parsing.
- **Cheap:** \(O(1)\) file checks, no recursion, no network calls, no process starts.
- **Un-ignorable:** warnings must be hard to miss in terminal output and easy to grep for in logs.
- **Actionable:** each warning includes “what broke”, “why it matters”, and “what to check next”.
- **Compatible:** default mode **does not change exit code** so existing automation isn’t destabilized; strict mode is opt-in.

### Where it runs

Append the drift-check **at the very end** of `sync_shared_state.ps1` (after all merge steps), immediately before printing `SUCCESS:shared-state-sync`.

Rationale: if you check too early, you might warn about a state that the sync is about to repair; checking at the end reports the actual post-sync wiring.

### How warnings become “un-ignorable”

Emit a *single banner* plus per-runtime lines:

- **Banner:** large ASCII box or “==== DRIFT WARNING ====” line in red/yellow (PowerShell `Write-Host` with `-ForegroundColor`).
- **Machine sentinel:** lines prefixed with **`DRIFT:WARN`** (and `DRIFT:OK`) so any log-scraper, grep, or future statusline can key off it.
- **Optional strict mode:** if env var `AGENTS_DRIFT_STRICT=1` is set, then treat warnings as failure (exit non‑zero or throw). Default remains warning-only.
- **Optional toast (still read-only):** if interactive + module available, show a Windows toast for any “critical” drift (local bridge missing, skills link illegal). This is a strong UX lever without writing files.

### What to assert per runtime (concrete)

Below is the best “cheap but high-signal” assertion set given the current harness shape.

#### Global shared harness assertions (always)

- **Vault exists:** `C:\Users\Prekzursil\.agents\skills` exists (already hard-stopped earlier; re-report as `DRIFT:OK`).
- **Registry exists:** `C:\Users\Prekzursil\.agents\agents.json` exists and is valid JSON (light parse).
- **Rules bridge exists (if part of policy):** `C:\Users\Prekzursil\.agents\rules` exists and is a junction/symlink (or at minimum exists). This matters because Grok config can reference `extra_rule_dirs` pointing here.

#### Claude (skills + MCP)

**Skills wiring**

- `.claude\skills` must be a **link** (junction or symlink), **not** a real directory. (Already enforced; drift-check should *restate* it.)
- `.claude\skills.daily` must either:
  - be a junction/symlink whose resolved target is `.agents\skills`, **or**
  - if it’s a real directory fallback, it must contain the **full vault coverage** (the current script already checks this when it detects a real directory; drift-check can summarize “fallback copy mode” as a warning because it’s fragile).

**MCP wiring**

- `.claude.json` exists and contains a top-level `mcpServers` object (JSON parse).
- Sanity keys present for the “shared always-on” servers: at least `basic-memory` and `agent-mail` are present in `mcpServers` *or* are intentionally plugin-provided (documented exceptions).

#### Claude local bridge (critical “silent skip” surface)

The local bridge file is currently at:

- `C:\Users\Prekzursil\.claude-runtime\local-mcp-marketplace\plugins\local-mcp-bridge\.mcp.json`

Assertions:

- **Must exist**. If missing: `DRIFT:WARN [CRITICAL] Claude local bridge missing` (this is the exact silent-loss case).
- Must be valid JSON mapping server names → `{command|url,...}` (light parse).
- Must not be empty (or at least must contain a minimum expected set), otherwise warn “bridge exists but mounts nothing.”

Why critical: the sync step currently *skips* when missing, so this can silently drop a whole class of MCPs for the Claude plugin bridge.

#### Codex

Assertions:

- `.codex\config.toml` exists and is non-empty.
- Contains at least the minimal “shared always-on” servers in `[mcp_servers."basic-memory"]` and `[mcp_servers."agent-mail"]` blocks, or equivalent configured URLs.
  - Cheap check: regex search for `\[mcp_servers\."basic-memory"\]` and `\[mcp_servers\."agent-mail"\]`.
- Optional: ensure **no** stale PromptBridge markers remain (the merge script strips them); drift-check can warn if it finds `promptbridge-codex managed`.

#### Cursor

Cursor’s current policy (from the merge script) is a strict allowlist: only these are emitted to `.cursor\mcp.json`:

- `agent-mail`, `basic-memory`, `chrome-devtools`, `context7`, `firecrawl`, `playwright`.

Assertions:

- `.cursor\mcp.json` exists and contains `mcpServers` object.
- `mcpServers` contains **exactly** the allowlisted keys (warn if missing any; warn if extras appear because they’ll confuse “what is actually supported here”).
- For env substitution: Cursor uses `${env:NAME}` syntax in this file; warn if any `${NAME}` pattern appears (cheap regex), because Cursor will treat it literally (per merge script rationale).

#### Grok (bridge correctness, not tool health)

From `C:\Users\Prekzursil\.grok\config.toml`, the harness expects:

- `paths.extra_skill_dirs` includes `C:\Users\Prekzursil\.agents\skills`
- `paths.extra_rule_dirs` includes `C:\Users\Prekzursil\.agents\rules`
- minimal MCP includes `basic-memory` and `agent-mail` over HTTP.

Assertions (cheap TOML substring checks):

- `.grok\config.toml` exists.
- Contains the two `paths.extra_*_dirs` references to `.agents\skills` and `.agents\rules`.
- Contains the `basic-memory` and `agent-mail` MCP URLs (`127.0.0.1:8765` and `127.0.0.1:8812`).

#### Gemini / Goose / Agy / Fabric (best-effort, avoid false alarms)

We currently don’t have a single authoritative “these files must exist” contract for each runtime in the sync pipeline. The drift-check should therefore:

- **Only assert what is explicitly contracted** by the harness (e.g., known junctions like `.gemini\skills` if policy says it exists).
- Otherwise, emit a **non-blocking info line**: “runtime not under sync contract; no checks performed.”

This avoids the “noisy alarm” problem, which is its own kind of silent failure (people start ignoring alerts).

### Severity model (to keep signal high)

Classify warnings:

- **CRITICAL:** local bridge missing; `.claude\skills` became real directory; vault missing; `agents.json` unreadable.
- **HIGH:** `basic-memory` / `agent-mail` missing from Codex/Claude/Cursor configs.
- **MEDIUM:** Cursor allowlist mismatch; Grok missing extra_skill_dirs; `.claude\skills.daily` fallback copy mode.
- **INFO:** runtime not under contract; optional config absent but not required.

### Output format (example)

```
==== DRIFT WARNING (Bridge Drift Check) ====
DRIFT:WARN [CRITICAL] claude-local-bridge: missing C:\...\local-mcp-bridge\.mcp.json (sync currently SKIPS → silent MCP loss)
DRIFT:WARN [HIGH] codex: mcp_servers."agent-mail" block not found in .codex\config.toml
DRIFT:OK   cursor: mcp.json allowlist ok (6/6)
DRIFT:OK   grok: extra_skill_dirs ok; agent-mail/basic-memory urls ok
==== End Drift Check (warnings=2) ====
```

This is grep-friendly, human-visible, and cheap.

---

## (b) WILDCARD — Fundamentally better architecture options (ranked)

### Ranking criteria

- **Dissolves multiple issues** (1–6) with one move
- **Cheap/low cognitive overhead**
- **Reversible** (can back out without data loss)
- **Doesn’t violate standing decisions** unless the benefit is overwhelming

### Option 1 (Rank #1): “Local Control Plane in WSL + systemd” (thin Windows client)

**What it is**

Move the fragile always-on services (at minimum **basic-memory** and **agent-mail**) into a WSL2 Linux distro and run them under **systemd**, with Windows clients talking to them over `127.0.0.1` (as today) or a stable WSL hostname/port mapping.

**What it dissolves**

- **(1) RAM mass-cancellation:** fewer always-on Python/Node processes competing with the IDE on Windows; WSL can be memory-limited and isolated.
- **(2) dead-but-alive agents:** systemd supervision provides restart + status primitives.
- **(5) basic-memory flapping:** running as a managed service reduces “forgot to start it / it died silently.”
- **(6) silent bridge loss:** health checks can reduce to “is service reachable + correct version/hash.”
- Partial for **(3) safeguard blocks** and **(4) home-as-workspace** (still helpful: fewer moving parts in the main Windows session).

**Cost**

- Medium: WSL setup, service unit files, port discipline, and a small “health check” endpoint/command.

**Risk**

- WSL lifecycle surprises (suspends, networking quirks).

**Reversibility**

- High: clients still point to localhost; you can revert to Windows-hosted daemons.

**Standing decisions challenged?**

- No SaaS, no vector DB, no extra orchestration runtime violated. This is an OS-level containment move.

**Adversarial round verdict**

- **Survived.** Pragmatist accepted because it’s a single, comprehensible move with a strong payoff and uses existing official support for systemd-in-WSL.

**Evidence (selected)**

- WSL systemd support and enablement via `/etc/wsl.conf` `[boot] systemd=true`: Microsoft Learn `wsl-config` + `systemd` docs.  
  - `https://learn.microsoft.com/en-us/windows/wsl/wsl-config`  
  - `https://learn.microsoft.com/en-us/windows/wsl/systemd`

### Option 2 (Rank #2): “Health is a first-class artifact” (one always-visible health surface)

**What it is**

Create a single **local harness health surface** that is always visible:

- VS Code/Cursor status bar item (extension) **or**
- terminal statusline segment **or**
- tray notifier.

It runs (or reads) a **cheap verifier** that emits the drift state: “bridges OK / drift warnings / services unreachable.”

**What it dissolves**

- **(6) silent bridge loss:** becomes impossible to miss; you see red/yellow in your face.
- **(2) dead-but-alive agents:** the health check can include “agent-mail reachable” and “last heartbeat < N minutes.”
- **(5) basic-memory flapping:** same.
- **(3) safeguard blocks:** if blocks are caused by missing MCP wiring or denied servers, the health surface can show “missing/denied” explicitly (reduces “mystery brokenness”).
- Indirectly helps **(1)** by preventing “retry storms” that happen when you don’t know what’s broken.

**Cost**

- Low-to-medium: a small extension or script + a spec for the output contract (the drift-check above provides the contract).

**Risk**

- If too noisy, it becomes ignorable. Must keep it sparse and severity-driven.

**Reversibility**

- High: can disable without affecting runtime state.

**Standing decisions challenged?**

- No: this is local-only observability (not SaaS).

**Adversarial round verdict**

- **Survived.** Skeptic tried to kill it as “yet another moving part,” but it’s explicitly designed as a *thin read-only surface* over the drift-check.

**Evidence (selected)**

- VS Code status bar items are standard extension UI; guidelines include warning/error prominence patterns.  
  - `https://code.visualstudio.com/api/ux-guidelines/status-bar`  
  - `https://code.visualstudio.com/api/extension-capabilities/extending-workbench`
- Cursor can run VS Code extensions (practical evidence: vendors ship “VS Code & Cursor” extensions; community confirms MCP status extensions read `~/.cursor/mcp.json`).  
  - `https://prismatic.io/docs/dev-tools/vscode-extension/`  
  - `https://github.com/ajascha/mcp-status-bar`

### Option 3 (Rank #3): “Supervisor Tree” pattern for local MCP servers (OTP-inspired)

**What it is**

Adopt an Erlang/OTP-inspired supervision model for local MCP servers: one parent supervisor manages child server processes with restart strategies and restart-intensity limits, plus a single health query.

**What it dissolves**

- **(2) dead-but-alive agents** and **(5) flapping** by making process lifecycle explicit.
- **(6) silent bridge loss** by giving a single “truth service” for what’s running and reachable.
- Helps **(1)** by allowing backpressure/circuit breakers: don’t start N heavy servers at once.

**Cost**

- Medium-to-high: you’re building/choosing a supervisor, defining restart strategies, and integrating multiple runtimes.

**Risk**

- Complexity risk (the very thing you’re fighting).

**Reversibility**

- Medium: you can keep current direct-launch as fallback.

**Standing decisions challenged?**

- Possibly **CHALLENGES STANDING DECISION** if it becomes a “second orchestration runtime.” If implemented as a minimal local process manager only, it can fit the spirit.

**Adversarial round verdict**

- **Conditional survive:** Architect/Security liked the explicit lifecycle; Pragmatist warned it could become “yet another orchestrator.” Recommended only if Option 1/2 don’t stabilize.

**Evidence (selected)**

- OTP supervisors define restart strategies (`one_for_one`, `one_for_all`, `rest_for_one`) and restart intensity (`intensity`, `period`).  
  - `https://www.erlang.org/docs/28/system/sup_princ.html`  
  - `https://hexdocs.pm/elixir/1.12/Supervisor.html`

### Option 4 (Rank #4): “Radical simplification / per-project minimal harness”

**What it is**

Treat complexity as the disease: define a minimal “core harness” (e.g., 20 skills + 5 MCP servers) and require explicit opt-in to mount anything else per project, rather than global mounting.

**What it dissolves**

- **(1) RAM mass-cancellation:** fewer mounted/auto-started tools.
- **(3) safeguard blocks:** smaller surface area to trigger tooling constraints.
- **(6) silent bridge loss:** fewer bridges to lose.

**Cost**

- Social + operational: changes habit, requires curation.

**Risk**

- Capability loss / frustration; might slow some workflows.

**Reversibility**

- High: you can re-expand.

**Standing decisions challenged?**

- No; it reinforces the “don’t overfit complexity” doctrine.

**Adversarial round verdict**

- **Survived as a backstop.** Wildcards argued it’s the most reliable path; Chief-of-Staff noted it needs clear defaults so it doesn’t become “death by configuration.”

---

## (c) Ideas we killed (and why)

- **“Observability SaaS / hosted health dashboard”** — killed due to standing “no SaaS” posture and unnecessary risk/complexity for a single workstation.
- **“Full LangGraph / second orchestration runtime for everything”** — killed: violates the anti-overfit guardrail; likely increases RAM pressure and failure modes.
- **“Vector DB for everything”** — killed: adds a heavy always-on component; fights the “small box” constraint.
- **“Cloud micro‑VM for control plane”** (**CHALLENGES STANDING DECISION**) — *bold*, but killed for now: introduces external dependency and auth surface; local WSL offers most of the benefit with fewer new risks.

---

## Council voices — Round 1 (independent takes)

### Architect

The harness is already a control plane. Make it explicit: define **contracts** per runtime (what artifacts prove “wired”), and build a single verifier that all UX surfaces consume. Drift-check is the minimal viable contract.

### Skeptic

Beware alert fatigue. If drift-check warns too often or on ambiguous states, it becomes noise and you’re back to “silent breakage.” Prefer a small set of high-signal checks (bridge file exists, skills link legal, core MCP endpoints present).

### Pragmatist

Fix the actual silent skip: the local bridge script returns success on missing file. Your drift-check must treat that as CRITICAL and visible. Everything else is secondary.

### Critic

Don’t add another layer of complexity unless it reduces net complexity. A drift-check appended to an existing script is cheap; a full supervisor framework is expensive and must earn its keep by eliminating multiple classes of bugs.

### Security

“Health surfaces” must remain read-only and avoid leaking secrets (don’t dump env var values). Also, prefer explicit allowlists (Cursor already has one) to reduce accidental mounting of risky tools.

### Chief-of-Staff

Humans notice what’s **in their face**. Either a status bar item or a terminal banner with a single-word verdict (OK/WARN) is better than long logs.

### Wildcard/Creative Voice #1 — “Immune system”

Treat bridge drift as an infection: the system should *detect early signals* (missing symlink, missing bridge file) and present a visible “fever indicator.” Optional strict mode is an “immune escalation” when drift repeats.

### Wildcard/Creative Voice #2 — “Control theory”

Error budgets aren’t just for SRE teams; they’re for any system with reliability vs velocity tradeoffs. Define an “automation error budget”: when drift warnings exceed threshold, the harness automatically shifts into “safe mode” (minimal MCP, no parallel subagents).

Evidence for error-budget framing:

- Google SRE book explains error budgets as a mechanism balancing reliability with release velocity.  
  - `https://sre.google/sre-book/service-best-practices/`
- Google SRE workbook provides an example error budget policy with “halt changes when budget is spent.”  
  - `https://sre.google/workbook/error-budget-policy/`

---

## Adversarial cross-round (pragmatic kill-attempts vs wild defenses)

### Kill attempt: “WSL+systemd adds another failure domain”

- **Pragmatist:** WSL can suspend; networking can be weird; now you have Windows + Linux.
- **Wildcard defense:** The current state already has multiple failure domains (many runtimes + many MCP processes) *without* supervision. WSL+systemd is fewer domains *in practice* because lifecycle is centralized and observable. Official docs confirm systemd support and how to enable it.
- **Verdict:** survives; risk is real but bounded and reversible.

### Kill attempt: “Status bar health is just one more widget”

- **Skeptic:** Another widget can be ignored.
- **Chief-of-Staff defense:** This is why we use severity colors and a single short verdict. VS Code guidelines explicitly discuss warning/error prominence patterns in the status bar, and it’s a known extension surface.
- **Verdict:** survives if kept minimal and severity-driven.

### Kill attempt: “Supervisor tree will become a second orchestrator runtime”

- **Critic:** Slippery slope; scope creep.
- **Architect defense:** Keep it as a narrow process manager for MCP only, not a general planner/executor. The restart strategy ideas are borrowed from OTP but implementation can be minimal.
- **Verdict:** conditional; not first choice.

---

## Practical “notice me” mechanisms (without SaaS)

These are local-only and compatible with the anti-overfit stance:

- **Terminal:** banners + `DRIFT:WARN` sentinel (immediate).
- **Status bar (VS Code/Cursor):** a tiny extension that calls the verifier and paints warning/error background (guidelines exist).  
  - `https://code.visualstudio.com/api/ux-guidelines/status-bar`
- **Windows service (optional):** if you later choose Windows-native daemons, `New-Service` and `sc.exe create` are standard mechanisms.  
  - `https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.management/new-service`  
  - `https://learn.microsoft.com/en-us/windows-server/administration/windows-commands/sc-create`

---

## Confidence

- **High** on the drift-check design: it targets the real silent skip and uses cheap, concrete invariants already present in the harness.
- **Medium-high** on WSL+systemd offload: strong upside, but WSL lifecycle can surprise; still reversible.
- **Medium** on supervisor-tree approach: conceptually strong (OTP proves the pattern), but implementation scope must be tightly contained to avoid overfitting.

