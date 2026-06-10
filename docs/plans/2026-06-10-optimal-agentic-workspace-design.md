# Optimal Agentic Workspace — Design Spec (draft v0, pre-council)

**Date:** 2026-06-10 · **Status:** DRAFT synthesized from 4 deep-research pillars; pending model-council refinement → user approval → Design Review Gate → plan → build.
**Supersedes/subsumes:** the unified-MCP-gateway spec (`2026-06-10-unified-cross-ai-mcp-architecture-design.md`) becomes **Layer 2** here.

## 0. The reframe

User's real goal is not "an MCP gateway" — it's a **workspace where the agent reliably finds and uses the right capability, cheaply (tokens), lightly (RAM), with durable memory, best-practice + inquisitive behavior, and autonomy without degeneration.** Research confirms these are **four orthogonal problems with four different fixes** — solving one (e.g. lazy-load) does NOT solve the others. The design is therefore **4 stacked layers + 1 cross-cutting principle**, each independently adoptable.

> **Central finding (Pillar 1):** "agents fail to use the right skill/MCP" is a *measured* failure mode — selection accuracy degrades past **30-50 tools** (Anthropic) and collapses to **13-20%** at 200-740 tools (RAG-MCP arXiv:2505.03275). The user's ~40 servers = 300-1000+ tools → squarely in the collapse zone. **Fleet size causes the mis-selection.** Token-reduction is necessary but NOT sufficient — *selection* needs discovery + good descriptions; *RAM* needs process management. Three distinct levers.

---

## Layer 1 — Discovery & Selection  (fixes "agent doesn't find/use the right skill/MCP")

| Move | Effect | Effort | Conf |
|---|---|---|---|
| **`ENABLE_TOOL_SEARCH=auto:5`** (or `true`) in Claude Code | selection **49→74 / 79.5→88.1%** + **~85% token cut**; defers schemas, searches on demand | ~0 (env var) | HIGH |
| **Rewrite user-authored skill descriptions** to single-line `trigger + scope-exclusion + output` formula; 4-6 verb synonyms matching natural phrasing | activation **~20%→84%**; multi-line YAML **silently truncates to line 1** (~40% of misfires) | med | HIGH |
| **Disambiguate near-duplicate skills**; `disable-model-invocation: true` for manual-only | stops mis-fires + shrinks match space | med | HIGH |
| **Capability map in CLAUDE.md** ("you can search for tools to do RE / web research / scholarly / chem / social…") | raises whether the agent *thinks to search* | tiny | HIGH |
| **Specialized sub-agents with small curated toolsets** (RE agent → ghidra/IDA/binja only; research agent → web/scholarly only) | keeps each agent **under 30-50** by construction — most robust selection fix | med | HIGH |
| **Rewrite worst MCP *tool* descriptions** (5-pattern: scope / deps / outputs / param-constraints / param-pairing) | +11pts multi-step, −29% degradation at 150+ tools (Trace-Free+ arXiv:2602.20426) | med | HIGH |
| **Metatool/discover proxy for Codex + Antigravity** (no native Tool Search) | same token+discovery win cross-client | med | MED-HIGH |

*Marketplace skills untouched (auto-update); only user-authored skill descriptions are rewritten.*

---

## Layer 2 — Overhead: token + RAM  (the gateway, reframed as 3 tiers)

P0 spike (this session) proved 1mcp & mcp-funnel **eager-spawn** (lazy=schema/token only, never process/RAM). But genuine lazy-spawn supervisors exist on Windows w/o Docker. **Docker is OUT** — its Resource Saver does not reclaim RAM under WSL2 (official docs).

- **Tier A — hot core (eager, shared):** `sparfenyuk/mcp-proxy` as a 127.0.0.1 service hosting ONE copy of ~4-8 hot stateless servers (context7/exa/tavily/basic-memory/github…); all 3 AIs connect via HTTP → kills per-session duplication (measured **172→33 procs, 3GB→~700MB**). Resident: few hundred MB.
- **Tier B — cold tail (lazy-spawn + idle-reap):** `lazy-mcp` (npm/PyPI, **5-min idle reaper**) or MCPJungle stateless (spawn-per-call, ~0 resident) for the ~20 occasional servers (research/social/quality). Spawn on first tool call, die when idle. `mcp-reaper.ps1` = backstop.
- **Tier C — token deferral per client:** Claude = native Tool Search (free); Codex/Antigravity = metatool proxy.
- **LOCAL (never shared):** stateful RE fleet (ida/ghidra/binja/frida/cheatengine/hexstrike), playwright, basic-memory*/postgres/docker (concurrency), codex-bridge. (*basic-memory may move to Tier A if single-writer.)
- **Security:** bind 127.0.0.1; keep credentialed servers off the shared HTTP plane or token-gate; DPAPI for secrets; OWASP "MCP Top 10" memory-poisoning awareness.

Quantified target: hot core few-hundred-MB, tail ~0 until used, tokens ~15k vs ~90k. Cost: few-second cold-start on first tail use + small local-HTTP surface to lock down.

---

## Layer 3 — Memory & Continuity  (fixes the post-compaction echo-chamber)

> **Echo-chamber root cause (Pillar 3):** after compaction the agent **re-acts on the lossy auto-summary as ground truth** and loops on its garbled framing. Compaction keeps *what happened*, destroys *why* (decisions/rationale).

- **THE fix:** post-compaction **`/clear` + reload ONLY the structured checkpoint** — never let the auto-summary blend with the checkpoint. SessionStart(matcher `compact`) re-injects plan + project-context and forces a "current position" restatement **before** acting.
- **Checkpoint upgrade:** PreCompact note becomes structured (User Requests / Files+paths / Tasks / **Decisions+rationale** / Blockers / Next Action) + **monotonic counter + HEAD-commit stamp** → fail-closed against stale reload (same discipline as the BC-verifier monotonic hit-set).
- **4-layer memory** (already present): CLAUDE.md procedural **<300 lines**; basic-memory semantic; checkpoints episodic; window working. Keep CLAUDE.md lean (adherence drops past ~200 lines).
- **Pull-not-push:** JIT identifier-based retrieval (paths/queries/permalinks); body loaded only when a topic surfaces. Don't pre-dump the vault.
- **3-file recovery** (`active-plan.md` / `project-context.md` / `execution-state.md`, already via `.beads/`) read before any work; keystone instruction **"ASSUME INTERRUPTION."**
- **Proactive manual compaction** at logical seams (~60-70% fill) over reactive auto-compaction (rot begins ~70%, auto fires ~83.5%).

---

## Layer 4 — Behavior & Hooks  (best practice + inquisitiveness + anti-degeneration)

**Cardinal rule (Pillar 4):** **BLOCK only the irreversible/dangerous; INJECT (guide) everything else.** Heavy blocking → the model evades (block `Write`→Bash heredoc; block `rm`→`perl unlink`) → thrash + useless agent. Recommended suite (hookify can author most conversationally — already installed):

| Hook | Event | Purpose | Block? |
|---|---|---|---|
| A | `UserPromptSubmit` | **Inquisitiveness:** vague-prompt heuristic → inject "restate understanding + ask 1-3 Qs via AskUserQuestion before editing"; `*` bypass | inject |
| B | `UserPromptSubmit` | **Plan-first:** 3+ files → `/start-task`+plan+confirm (mirrors CLAUDE.md) | inject |
| C | `PreToolUse`/Bash | **Safety:** deny `rm -rf`, force-push, `--no-verify`, prod creds | **DENY** |
| D | `PreToolUse`/Bash (`git commit`) | **No secrets:** `gitleaks protect --staged`, exit 2 on findings | **DENY** |
| E | `PreToolUse`/Edit\|Write | **Skill/MCP nudge + scope discipline** (scoped `git add`, cached-diff before commit — closes worktree-contamination burn); optional TDD-Guard | inject/ask |
| F | `PostToolUse`/Edit\|Write | **Auto-format + lint + secret-scan** (warn via additionalContext) | warn |
| G | `Stop` (prompt/agent) | **Verification gate:** tasks done + tests pass + coverage vs `.coverage-thresholds.json`; **MUST honor `stop_hook_active`** (8-block cap) | **BLOCK** |
| H | `PostToolUse`/`PostToolBatch` | **Anti-degeneration:** fingerprint tool calls; 3× repeat → inject "different approach or ask"; no-progress (<5% change) halt; PostToolBatch may block runaway | inject/rare block |
| I | `PreCompact`+`SessionStart(compact)` | **Compaction survival** (Layer 3) | — |
| J | `InstructionsLoaded` | **Observability** (verify harness stays lean) | — |

Plus **terminal-state tools** (unambiguous SUCCESS/FAILED, no retry-inviting language) — cut tool calls 14→2. Anti-degeneration defaults: debounce window 3 / dup≥2; idempotent cap 2-3.

---

## Cross-cutting principle

The four layers are **orthogonal and stack** — and you must address all four or the pain persists:
- Discovery (L1) fixes token+selection; **lazy-load alone won't fix selection**.
- Overhead tiers (L2) fix RAM; **descriptions/search won't fix RAM**.
- Memory (L3) fixes continuity/echo-chamber; independent of L1/L2.
- Hooks (L4) fix behavior/degeneration; the glue that *enforces* the others (e.g. L4-I implements L3; L4-E nudges L1).

## Adoption order (effort→impact)
1. **L1 instant wins:** `ENABLE_TOOL_SEARCH=auto:5` + CLAUDE.md capability map (minutes; biggest selection+token win).
2. **L4 starter hooks** (A inquisitiveness, C/D safety, G verification) via hookify.
3. **L3 echo-chamber fix** (`/clear`+checkpoint-reload, checkpoint Decisions section + stamp).
4. **L1 skill-description rewrite** (user-authored only) — the "skills don't fire" half.
5. **L2 gateway** (Tier A shared core + Tier B lazy tail) — RAM; reuses WU0 rollback harness already built.
6. Cross-AI metatool (Codex/Antigravity) + remaining hooks (E/F/H) + sub-agent toolset curation.

## Sources (per-pillar, full lists in research transcripts)
- L1: Anthropic Tool Search (platform.claude.com/.../tool-search-tool; code.claude.com/.../tool-search), RAG-MCP (arXiv:2505.03275), MCP-Zero (2506.01056), skill-activation deep-dive, Trace-Free+ (2602.20426).
- L2: shyamverma.com/shared-mcp-servers-claude-code, RaiAnsar/mcp-gateway, MCPJungle, lazy-mcp, Docker Resource-Saver docs (anti-Docker), Anthropic advanced-tool-use.
- L3: Anthropic effective-context-engineering + multi-agent-research-system, dev.to/aws reasoning-loops, claudefa.st context-recovery-hook, orchestrator.dev memory-2026, SpecRA (OpenReview xVO4BqmzVD).
- L4: code.claude.com/docs/en/hooks(+guide), severity1/claude-code-prompt-improver, nizos/tdd-guard, boucle.sh hooks-cannot-enforce, disler/claude-code-hooks-mastery, hookify.
