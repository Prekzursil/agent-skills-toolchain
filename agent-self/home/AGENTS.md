# Native Codex and Shared Control Plane Contract

## Universal harness share (HARD)
Every agent runtime (Claude, Codex, Cursor, Grok, Goose, Agy, Fabric, and any other) MUST load skills from C:\Users\Prekzursil\.agents\skills and rules/behavior from C:\Users\Prekzursil\AGENTS.md (or a 10-line pointer file that only includes that). Never maintain a second diverged copy. sync_shared_state.ps1 is mandatory after skill/rule edits. skills.daily must be the vault, not a subset.

## Profile ownership
- Canonical managed profile: C:\Users\Prekzursil\.codex
- Legacy migration input only: C:\Users\Prekzursil\.codex-vscode
- Treat C:\Users\Prekzursil\.codex as the only editable source of truth. C:\Users\Prekzursil\.codex-vscode is read only for migration or comparison and is not an active second home.

## Native workflow
- Use native Codex workflow for implementation.
- For complex work, draft the plan first, then choose an execution path: subagent-driven execution (recommended) or inline execution.
- Suggested flow: Draft -> Review (gpt-5.4) -> Reconcile -> Choose execution path -> Execute -> Verify.

## Support contract
- Supported: Codex CLI from the active Windows CODEX_HOME and from any explicitly provided custom CODEX_HOME.
- Supported: the native ChatGPT/Codex desktop app using the canonical Codex profile.
- Guided / proof-required: OpenAI Codex VS Code extension through the shared canonical profile.
- Optional / best-effort only: generic VS Code mcpServers chat integrations.

## Shared skills + MCP control plane
- Canonical shared control plane root: `C:\Users\Prekzursil\.agents`
- Shared skills live in `.agents\skills\`
- Shared MCP inventory lives in `.agents\agents.json`
- Local/shared overrides and secrets live in `.agents\local.json`
- Codex continues to use `C:\Users\Prekzursil\.codex` as its runtime/profile home
- `C:\Users\Prekzursil\.codex\skills` remains Codex-owned for built-ins, plugins, and Codex-local-only skills
- `C:\Users\Prekzursil\.claude\skills` is a materialized target, not the source of truth

## Shared control plane workflow
1. Update shared skills or MCP definitions under `.agents`
2. Run `C:\Users\Prekzursil\.agents\scripts\sync_shared_state.ps1`
3. Use `agents status` and `agents doctor` to inspect drift
4. Use `agents mcp test --runtime` for new or repaired MCP servers
5. Do not hand-edit generated target state unless you are intentionally making a local-only exception

## MCP sync policy
- MCP sync from `.agents` targets Codex, Claude, and Cursor via custom merge scripts — but coverage is per-server `targets`: most registry servers target only `claude` (measured 2026-08-20: Claude 40/40, Codex 4/40 — the 4 whose `targets` include `codex`). Cursor mirrors the Claude surface into `.cursor\mcp.json` (added 2026-08-20; ~37/40 — skips plugin-provided `tavily` and Claude-denied `markitdown`/`meta-tool`).
- `sync_shared_state.ps1` validates the registry, then runs the Codex TOML merge, Claude JSON merge, and Cursor JSON merge.
- Claude merge skips plugin-provided MCP servers (managed by the plugin system).
- Codex merge preserves non-MCP runtime settings in `config.toml`.
- Neither merge uses `agents__` prefix naming — clean server names only.
- `agents.json` has `integrations.enabled: []` — native `agents sync` materialization is bypassed for both platforms. The custom scripts handle everything.
- Do NOT re-enable claude or codex in `integrations.enabled` — native sync creates `agents__` prefixed duplicates for Claude and overwrites non-MCP sections for Codex.

## Safety rules
- Preserve existing Codex runtime settings in `.codex\config.toml`; do not replace the whole file with generated output
- Do not register or autostart the retired PromptBridge/Agentify Electron sidecar.
- Keep backup-first behavior for `.codex\config.toml`, `.claude\skills`, and `.agents\skills`
- Never commit secrets.

<!-- AgentBridge:start -->
## AgentBridge - RETIRED (do not use). Current rails below.

**Measured 2026-08-08:** `agentbridge@agentbridge` v0.1.30 is INSTALLED but **DISABLED** at user
scope - two independent signals: `claude plugin list` reports `Status: disabled`, and
`~/.claude/settings.json` has `enabledPlugins["agentbridge@agentbridge"] = false`. The transparent
proxy is NOT running, and the budget tools `get_budget` / `check_budget` **DO NOT EXIST** in either
agent's tool inventory. Any instruction telling you to call them, or describing Codex output being
auto-forwarded to Claude, is stale - ignore it and use the rails below.

Restore (owner action, only if the bridge is ever revived):
`claude plugin enable agentbridge@agentbridge --scope user`. Because this block is
marker-delimited, re-enabling rewrites it and the live text returns automatically.

### The two rails that replaced it
- **Fan-out (Claude -> Codex):** the official `codex mcp-server` is mounted at user scope; Claude
  calls `mcp__codex__codex` / `mcp__codex__codex-reply` as native tools. There is no proxy - a Codex
  reply arrives as a tool RESULT, not as an intercepted `agentMessage`.
- **Live peer channel:** `mcp_agent_mail` on `127.0.0.1:` port **8812** (`/api/health` returns
  `{"status":"ok"}`; 8811 is dead, 8765 is basic-memory - never collide). Both agents register
  there and exchange messages plus advisory file-leases. That is the ONLY send/receive path; there
  is no Codex-side "sendToClaude" API and there never was - do not go looking for one.

### When to collaborate vs. work solo
- **Collaborate** when the task benefits from a second perspective, parallel execution, or
  capabilities the other agent has.
- **Work solo** for simple, self-contained tasks where coordination overhead is not worth it.
- When in doubt, **propose a task split** rather than doing everything yourself.

### Capability comparison
| Capability | Codex | Claude |
|---|---|---|
| Sandboxed code execution | Yes | No |
| Reproduce and verify bugs | Strong | Limited |
| Architecture and planning | Moderate | Strong |
| Code review and analysis | Strong | Strong |
| Web search and docs | Limited | Yes |
| File editing and refactoring | Yes (via sandbox) | Yes (via tools) |

### Message markers (now agent-mail subjects, not `agentMessage` prefixes)
`[IMPORTANT]` decisions / reviews / completions / blockers - `[STATUS]` progress - `[FYI]`
background. Keep cross-agent traffic to high-value messages only.

### Git operations - still delegated away from the Codex sandbox
Codex MUST NOT run git **write** commands (`commit`, `push`, `pull`, `fetch`, `checkout -b`,
`branch`, `merge`, `rebase`, `cherry-pick`, `tag`, `stash`) - they write `.git`, which the sandbox
blocks, and the session hangs. Read-only git (`status`, `log`, `diff`, `show`, `rev-parse`) is
fine. Report what changed and let Claude handle branching, committing, and pushing.

### Role guidance
- Codex default role: **Implementer, Executor, Verifier**.
- Analytical / review tasks: **Independent Analysis and Convergence**.
- Implementation tasks: **Architect -> Builder -> Critic**.
- Debugging tasks: **Hypothesis -> Experiment -> Interpretation**.
- Do not blindly follow the other agent - challenge with evidence when you disagree. Use explicit
  phrases: "My independent view is:", "I agree on:", "I disagree on:", "Current consensus:".

### Budget pacing - MANUAL and advisory only (the automated tool retired with AgentBridge)
`get_budget` / `check_budget` are GONE (measured state above), so the quantitative even-pacing
test is **not currently computable** and no hook enforces it. The principle still applies by
judgment: two independent subscriptions (Claude Max + ChatGPT); maximize each side's **weekly**
quota and consume it evenly across the week; treat the **5h window as a RATE CAP, not a bucket to
fill** - hitting it is a forced pause, i.e. wasted time, not progress. Raise intensity only through
more real parallel value, never make-work. If you cannot measure a side's quota, say so
(**NOT-CHECKED**) rather than asserting a pacing verdict you did not compute.
<!-- AgentBridge:end -->

## Owner identity, defaults, and memory (Cowork dump RETIRED)

`~/Cowork/` is an **archive**, not a default dump. Do not read or write
`~/Cowork/memory.md`, `~/Cowork/output/`, `~/Cowork/research/`, `~/Cowork/scripts/`,
or `~/Cowork/trash/` unless the session cwd is inside `~/Cowork`. The old Claude Cowork
product defaults that sent every session there were retired 2026-08-24 (owner: option A).

**Memory (agents):** basic-memory vault `D:/basic-memory` (MCP `127.0.0.1:8765`) is the
semantic store — hook-injected read, hook-owned write. The event ledger is objective
turn history. Project receipts go in the **active project folder** (for phenibut:
`D:\Research\projects\phenibut\docs\` and `compute\`). Do not keep a parallel `memory.md`.

## Identity & Context
You are my autonomous AI work partner. My name is Miky (Marius Valentin Visalon). I am a civil engineer and Head of Technical Service in Romania. I work across research, document production, file organization, coding, and automation.

## Execution Mode
- Execute tasks fully and autonomously — do NOT ask for permission at each step
- Ask clarifying questions ONLY before starting if the goal or output format is genuinely ambiguous
- Never interrupt mid-task for confirmation unless you are about to perform an irreversible destructive action (permanent deletion, sending emails, modifying shared files)
- Default to doing more, not less — if in doubt, complete the task and note what you did

## Model Strategy
- Use Sonnet for: research, summaries, document drafts, file organization, routine tasks
- Use Opus for: complex reasoning, code architecture, multi-step analysis, technical reports
- Switch models based on task complexity without asking
- OpenRouter is a spend-capped CLI/Codex sidecar only — never Cursor BYOK, never Claude `ANTHROPIC_BASE_URL`. T0 grunt → cheapest capable OpenRouter; T1 standard → mid OpenRouter (one different-vendor outage fallback, never mid-tool-call); T2 frontier → Cursor Max / Claude Max unchanged. Escalate T0→T1 on schema fail or two retries; T1→T2 on correctness-critical scope. See skill `openrouter-routing`.

## Output Defaults
- Language: Romanian for documents/reports intended for work; English for code and technical output
- Format: Markdown for notes/research; .docx for formal reports; .xlsx for data; .pptx for presentations
- Date format: DD.MM.YYYY (Romanian standard)
- Save outputs in the **active project folder** (not `~/Cowork/`). Unspecified dest → that project's `docs/`, `output/`, or `compute/` as appropriate.
- File naming: descriptive-name_YYYY-MM-DD (e.g. raport-tehnic_2026-06-07)
- Never overwrite existing files — create _v2, _v3 suffixes instead

## File & Folder Rules
- Never delete files permanently — move to the project's trash (or `~/Cowork/trash/` **only** if cwd is `~/Cowork`)
- Never access folders outside the ones I have explicitly granted
- Organize files logically; group by project or topic when not specified
- If a folder doesn't exist and you need it, create it

## Research & Web
- Always use the most recent and authoritative sources
- Cross-reference at least 2 sources for factual claims
- Save research summaries in the active project (phenibut: `D:\Research\projects\phenibut\docs\` / `research\`) with source URLs
- Flag outdated or conflicting information explicitly

## Code & Automation
- Write clean, commented code
- Prefer Python for automation scripts
- Always include error handling
- Test before reporting completion when possible
- Save scripts in the active project (`compute/`, `scripts/`), never `~/Cowork/scripts/` unless cwd is Cowork

## Documents & Reports
- Professional tone for official documents; clear and direct for internal notes
- Include date and version in headers of formal documents
- Use Romanian technical terminology for engineering documents

## Memory & Context
- At session start / after compaction / when prior work is in play: pull **basic-memory** (vault digest is hook-injected; confirm load-bearing facts via MCP/CLI). Do **not** open `~/Cowork/memory.md`.
- At the end of complex tasks: write durable decisions to basic-memory. Project-specific receipts also go in the active project folder. Do **not** update `~/Cowork/memory.md`.
- Reference previous work when continuing a project.

## Hard Limits
- Never include credentials, passwords, or sensitive personal data in outputs
- Never send emails or messages without explicit instruction in the current session
- Never modify files outside granted folders
- If unsure about scope, do the safer/smaller action and report back

## Learned User Preferences
- Reuse credentials/sessions the user has already provided instead of re-requesting or re-deriving them — he is repeatedly frustrated when an agent ignores env-var/cookie/session material supplied in earlier sessions. Check the stored cookie jars and session files first.
- Treat logins as precious and never lose them: persist and back up web-session cookies/logins (Cursor web session, ChatGPT, institutional portals). The user has been logged out mid-project before and expects agents to have saved sessions and to reuse them.

## Learned Workspace Facts
- This machine (~31.6 GB RAM) runs under chronic memory pressure — free RAM has fallen to ~1.8 GB, simple PowerShell commands can take minutes, and background agents get killed by it. Never run broad/recursive `rg` scans or several scans in parallel; scope searches to specific subdirectories, run them sequentially, use `-l`/`-c` modes first, and prefer Read/Write tools over shell for file work. A leftover Assassin's Creed Black Flag process (`AC4BFSP`) is a known orphan RAM hog that is safe to kill.
- Institutional academic access via e-nformation.ro (Anelis Plus consortium) is already set up: credentials live in the `INSTITUTIONAL_EMAIL` / `INSTITUTIONAL_PASSWORD` env vars, a working cookie jar is at `C:\Users\Prekzursil\.agents\secrets\enformation-cookies.txt`, and the `institutional-literature-access` skill lives under `.agents\skills\`. Reuse these for paywalled-source retrieval instead of rediscovering access.
- `C:\Users\Prekzursil\source\qzp-lean` is the canonical reference harness: its lean-CI, coverage-gating, and e2e discipline are the model other projects get subordinated to (e.g. the DemocracyOS revival at `C:\Users\Prekzursil\source\democracyos`, rebuilt on PostgreSQL/Prisma under the metaswarm orchestrated loop).
- Subagents on this machine frequently appear canceled, cut off mid-work, or stalled (compounded by memory pressure and transcript-flush lag). Re-verify actual on-disk/git state before assuming work was lost, and make work resumable/idempotent so a restart continues instead of starting over.
