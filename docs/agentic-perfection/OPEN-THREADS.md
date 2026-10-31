---
title: OPEN-THREADS
type: note
permalink: dqverify-repo-20261013/docs/agentic-perfection/open-threads
---

# OPEN THREADS — durable backlog so nothing postponed is ever forgotten
<!-- The "never-forget" register. A SessionStart/resurface hook should surface the ACTIVE + QUEUED
     items. Update as threads open/close. This exists because the user's #1 stress is: discussed-then-
     postponed ideas vanishing. They do NOT vanish if they live here. Last updated 2026-06-29. -->

## ACTIVE (in flight right now)
- **SOTA MCP/harness expansion — Wave B** building: B1 keystone hooks (mcp-liveness self-heal+ALERT,
  capability-catalog auto-tool-select, edit-checkpoints, truth-verify, persist-nudge) + B2
  (mcp-code-orchestrate 98.7% skill, routing wire searxng/cve, 2 doc-skills, description-rewrites).

## QUEUED — the next program (deep-research + brainstorm + council; user-requested)
1. **PROACTIVE-PARTNER capability (the keystone meta — user's core vision):**
   - Auto-INVOKE the great skills/frameworks when apt (not just MCPs): metaswarm, ECC, ToolUniverse,
     /prompt-optimize, /research-ops, /self-reflect, /continuous-learning-v2, /agent-sort,
     /plan-orchestrate, /frontend-design-direction, /nanoclaw-repl, /claw, /council, /brainstorm.
     (Capability-catalog + router must cover SKILLS+frameworks, ranked, so I reach for them by default.)
   - PROMPT-OPTIMIZE layer: when the user's prompt is sloppy/fatigued, auto-enrich it (/prompt-optimizer)
     or ask the 1-3 essence-questions BEFORE executing — dig the logical intent + desirability, not literal words.
   - NEVER-FORGET: this register + a resurface hook (surface open threads at SessionStart / when relevant).
   - INITIATIVE: proactively suggest improvements, ask clarifying Qs, propose welcome additions ("grows with you").
   - Online tool-SEARCH + suggest-missing: if a needed tool/skill isn't installed, find it / suggest it (don't makeshift).
   - **SOTA ARCHITECTURE (fork deep-research 2026-06-29 — build-ready, one proactive-partner hook layer):**
     * SessionStart injects: capability-catalog (auto-select primer) + USER.md (grows-with-you) + relevant-NOW OPEN-THREADS (REASONED resurface, not flat dump).
     * UserPromptSubmit (a) SEMANTIC BODY-LEVEL skill/tool ROUTER — embed every skill/MCP BODY with nomic-embed-text (on D:) into a local index; embed task -> cosine top-k -> auto-load matched skills+MCPs. REPLACES the lexical router (body is the decisive signal: SkillRouter arXiv 2603.22455; 2603.20313 = 99.6% token-cut/97.1% hit@3/<100ms). (b) DECOUPLED EVPI-gated INTENT-CHECK — separate watcher; on a vague prompt, if underspecified AND EVPI-positive (Query-Ambiguity x Task-Risk x Cognitive-Load) -> inject 1-3 essence-questions OR auto-enrich via /prompt-optimizer BEFORE executing ("Ask or Assume?" arXiv 2603.26233).
     * PreToolUse/Stop: Wave-B verify/checkpoint/liveness hooks already cover safety + the basic-memory-death alert.
     * Background DREAMING: /self-reflect + continuous-learning-v2 + ReasoningBank -> update USER.md, distill strategies, re-rank OPEN-THREADS (Honcho pattern; optional heavy = self-host Honcho in Docker, aligns w/ mem0/Qdrant).
     * BUILD ORDER (highest-leverage first): (1) semantic body-level router, (2) EVPI intent-hook, (3) resurface-hook, (4) USER.md, (5) dreaming.
     * RECONCILE: Wave-B's LEXICAL capability-catalog = solid v1 / SessionStart primer; the SEMANTIC router is the v2 that actually delivers "auto-pick without me invoking."
     * ROUND-2 REFINEMENTS (fork, multi-round): (a) router = SUCCESS-ALIGNED not just semantic — log which suggestions led to success, re-weight (Memento-Skills 2603.18743). (b) intent-hook fires OPTION-BASED AskUserQuestion (recognition>recall, low-fatigue — AskUserQuestion IS the prescribed elicitation tool; Adaptive-Prompt-Elicitation IUI-2026). (c) ADD auto-skill-authoring (novel success -> draft skill -> review-queue, NEVER auto-install; Voyager/AutoSkill/Hermes) + skill-self-repair-on-failure. (d) /council = ADOPT rachittshah/llmcouncil (MCP+CC-skill; vote/debate/critique/red-team/verify; KS-adaptive-stop -94.5% cost; Opus+Perplexity+agy panel; enforces 'consensus != verification').
     * ADOPT-DON'T-BUILD: llmcouncil (council); Honcho (user-model, optional-heavy Docker). Everything else = light glue on existing substrate.
     * BUILD ORDER (highest-leverage): (1) body+success-aligned skill/tool router, (2) EVPI-gated AskUserQuestion intent-hook, (3) USER.md + SessionStart injection (grows-with-you), (4) adopt llmcouncil, (5) auto-skill-authoring + reasoned resurface-hook (background dreaming via /self-reflect+CL-v2+ReasoningBank).
2. **UI/UX QUALITY overhaul** — Reframe, Momentstudio, Webcoder. Bar: NO dead buttons, NO crash-on-edge-click,
   NO confusing/cluttered/overlapping GUI, NO overly-complex/duplicated UI, NO built-but-not-wired, NO
   reimplemented-already-existing, NO absurd dupes (e.g. coupons_v2 with no coupons_v1). Momentstudio = heavy
   declutter (overlapping, misplaced categories, too-many/too-few options). Reframe had similar.
3. **MEDIA/VIDEO editing CONSOLIDATION** — unify cutting + operations (HandBrake + tools), SOTA research
   (deep GitHub analysis + analyze OpusClip-produced shorts). **STEP 1 = watermark removal WITHOUT
   deterioration** (the failing-agent pain; our lesson: ProPainter smears animated bg → LAMA + NCC gate).
4. **Binary Ninja autonomous harness** — same as IDA/Ghidra (re-harness adapter). Low urgency, user said "its fine."
5. **ToolUniverse / Schrödinger expansion** — auto-pick the best of the 2,526 TU tools + the Schrödinger suite.

## DEFERRED from Wave B (fold into next program, NOT dropped)
- osint-extras MCP (key-free community/long-tail/IOC), tor-osint minimal MCP (defensive), abuse.ch IOC MCP.
- new app-skills: opus-clip-to-reels (covered by media program). Serena activate_project verify (likely unused).
- longrun-enforce hook, media-verify Stop hook, per-call mcp-liveness already in B1.

## BC (Battle Cats) LEFTOVERS
- clear_progress save-restore for Sengoku 1385-1389 / Golden 7010 (events now playable; user's call).
- W2 daemon polish: nowType:'double' + gs-relative-admit container (offsets derived+committed; classifier self-wire).
- enemy_db.json regen (cascade risk); enemy cols 105-112 (tbcml-blocked at col 103).

## OTHER RE / PROJECTS named
- Hitman RE, SWFOC RE (the user's RE projects — revisit when relevant).

## AGENTIC-PERFECTION BUILD BACKLOG (2026-06-29 — core LIVE, rest captured here)
LIVE+WIRED: B1 hooks · PP1 semantic auto-router · PB1 durability spine (bg-registry restart-reconciler + memory-spool + heartbeat) · PB2 verification layer (wire-check, tool-result-sentinel, honest-signal, stub-ledger, dup-guard). Plans: AGENTIC-PERFECTION-PLAN.md + PROACTIVE-PARTNER-PROGRAM.md.
REMAINING (priority order):
1. **CONSOLIDATION-DEBT (do FIRST)**: ~22 hooks added this session past the ~6-ceiling -> refactor into per-event DISPATCHERS (one Stop-dispatcher running wire-check+honest-signal+stub-report+truth-verify+claim-guard+persist in ONE process; same for PostToolUse/SessionStart) to reclaim per-turn latency. wire-check ripgrep is the main latency cost.
2. **ANTICIPATORY scheduled-tasks** (background lens, run as ~/scripts/*.ps1 NOT hooks): build the "while you were away" BACKGROUND-DIGEST.md FIRST (Finding 8, the surface) -> then resource-guard, world-watchers (BC-version/upstream-clobber), readiness-refresh (re-embed router index + pre-warm backends), consolidation-GC (tombstone resolved failures, merge battle-cats/battlecats dup, prune 100 checkpoints), ProAct research-prefetch, sleep-time-distill, PASTE pre-exec.
3. **PER-PROJECT intelligence** (per-project lens): unified repo-identity-resolver _shared/projid.py (FIXES the 5-Reframe-shard + 3-Momentstudio-shard ledger fragmentation) -> project-cards (auto-loaded SessionStart) + cross-repo prompt-detection + per-project tool/quality-bar defaults + staleness-gating. Rides existing carriers (capability-catalog inject + UserPromptSubmit), zero new hooks.
4. **AUTONOMY/INTERACTION wave**: graded-autonomy-gatekeeper + auth-ledger (one consolidated PreToolUse), fatigue-adaptive-mode, failure-precondition-matcher, subagent scope-tripwire, parallel-barrier-watchdog.
5. **ROUND-2 REASONING-SPINE**: world-model state ledger (.beads/context/world-model.md), hold-your-ground dissent, code-mode-default for high-volume MCP, backtracking-executor, capability-gap tool-FORGE, empirical variant-archive self-improvement, trust-Brier-ledger, trajectory-quality-gate at subagent handback.
6. **APP-DRIVING skill** "drive-and-verify" (Playwright functional-guards: console/dead-button/dup-id/dead-link/broken-img/blank-route + axe + independent FRESH-CONTEXT vision-critic, taste=advisory/functional=blocking) — for Reframe/Momentstudio/Webcoder UI quality. ~80% primitives exist (playwright/chrome-devtools/claude-in-chrome MCPs + visual-review/webapp-testing/design-system skills).
7. **MCP-GAP adds** (verified native-Win11/no-Docker, lazy): Windows-MCP (app-driving keystone), DBHub/Qdrant/DuckDB, codebase-memory-mcp, WinDbg-MCP, angr-MCP+Unicorn-MCP, mitmproxy-mcp (agent-driven BC MITM), capa/YARA/Volatility (malware-triage).
8. **USER-MODEL/grows-with-you**: USER.md + dreaming pass, adopt llmcouncil (/council), auto-skill-authoring (review-queue), EVPI-gated AskUserQuestion intent-hook (option-elicitation).
9. **AGENTS.md 3-divergent-files bug**: ~/.codex vs ~/.claude vs ~/ stale -> single-canonical + hash-tripwire (NOT symlinks).
10. **fix the workflow StructuredOutput retry-cap**: broad/deep lenses fail the strict schema -> use looser/plain-text schema for deep-research workflows.
11. **GEM-REFINEMENTS**: (a0) memory-spool content-capture -> VERIFY: spool entries observed 0-content (only title captured) during the 2026-06-29 bm-outage; if spool.py stores only the title not the full write_note payload (title+content+tags), a lost note's BODY isn't auto-recoverable (only flagged by title). Fix spool.py to persist the full tool_input so flush can re-write verbatim. (a) stub-ledger false-positives -> ✅ FIXED+VERIFIED (is_test_file exclusion in record+report; `_COMMENT_TAG`/`_WEAK` `(?![-\w])` compound-guard so `stub-ledger`/`stubscan` refs aren't flagged; dispatch.py now 0 hits; real TODOs still caught). (b) PreToolUse-dispatcher-consolidation (ulysses+tms+no-force-push+goal-reinject+edit-checkpoints now co-fire on Bash/Edit/Write) -> PENDING (do AFTER the anticipatory+per-project agents land, to avoid manifest.json write-contention). (c) install 2 forge disciplines -> ✅ DONE+LIVE (no-force-push exit-2 on `--force`; todo-surfacer in Stop dispatcher).
(Plus the non-agentic backlog above: UI/UX overhaul, media/watermark consolidation, BN harness, BC clear_progress restore.)

## KNOWN-ISSUE: radare2 MCP -32000 (CC-side, exhaustively diagnosed 2026-06-29)
The r2_id_shim.js + ~/.mcp.json radare2 entry + r2mcp are VERIFIED CORRECT — do NOT re-diagnose these. Ruled out (all tested green): stale session-spec (persists after full restart), protocol-version (works on 2024-11-05 AND CC's 2025-06-18, returns 32 tools), the r2mcp id-echo bug (shim restores ids — sequential handshake confirmed), stdout banner pollution (stdout is clean JSON), connection-close on init methods (r2mcp survives initialize+initialized+tools/list+resources/list+prompts/list, process stays alive), cached failed-state (0 radare2 mentions in ~/.claude.json). The -32000 is INSIDE Claude Code's MCP client, not reproducible from Bash. NEXT: capture via `claude --mcp-debug` (the real connection error) then fix; OR accept (radare2 SKILL + ida/ghidra/binja/frida cover RE) and disable the entry to kill the noise. GitHub MCP FIXED same day (PAT Bearer header + GITHUB_MCP_PAT env). Perplexity cookie live.

## STANDING USER PREFERENCES (apply always)
- Maintain rigor + prompt-quality HIGH all session; no thin status-tables; research = cite + grade confidence.
- Quality bar: perfect work, no half-built junk, no duplication. Use the proper tool/skill/MCP, not makeshift scripts.
- Repair a broken MCP on the spot; ALERT loudly if a critical tool (basic-memory) dies — never silent loss.
- Honesty / anti-sycophancy; reconcile-don't-drop; remember + research by default; fan out large when apt.