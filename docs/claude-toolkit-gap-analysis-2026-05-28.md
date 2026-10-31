---
title: claude-toolkit-gap-analysis-2026-05-28
type: note
permalink: dqverify-repo-20261013/docs/claude-toolkit-gap-analysis-2026-05-28
---

# Claude Code Toolkit — Tailored Gap Analysis & Power-User Playbook
*Generated 2026-05-28 · 7 parallel research agents · ~390 tools cataloged · deduped against your installed stack · Confidence: High (star counts verified live via `gh api`, claims cited)*

## 0. How to read this (you said you're overwhelmed — start here)

This report has **three tiers, smallest first**. Do not read it linearly.

1. **§1 Diagnosis + §2 Playbook** — *why your flow breaks and the 21 habits that fix it.* This is the actual answer to "I lose context / prompt badly / the flow breaks." **Read this fully.** It's the highest-value part and needs zero installs.
2. **§3 Top ~40 gamechangers for YOU** — curated from 56 finalist picks, grouped, each with a one-line "why it matters for *your* stack" + how to adopt + status. Skim, star what resonates.
3. **§4 30/60/90 roadmap** — the un-overwhelm: do *five* things week 1, not forty.
4. **§5 Full catalog (~390, by domain)** — the reference dump. Search it when you have a specific need; don't read it cover to cover.

**Status legend:** ✅ HAVE · 🟡 PARTIAL (overlaps something you own; adopt selectively) · 🔴 NET-NEW-GAP (genuinely missing).

**The single most important finding:** Your problem is **not** a missing tool. You already own more than almost anyone. Your problem is (a) prompting before exploring/planning *to a file*, and (b) **self-inflicted context rot** — your global `~/.claude/CLAUDE.md` + 17 `rules/*.md` files + project CLAUDE.md + a big `MEMORY.md` load on *every* turn, and you run *four* overlapping memory-capture layers that fight each other. You are manufacturing the context loss you're fighting. §1–§2 fix that.

---

## 1. THE DIAGNOSIS — why "the good flow breaks and everything seems lost"

Three mechanisms, all fixable this week:

- **Rule-pile bloat.** Anthropic's adherence target is **<200 lines per CLAUDE.md** ([memory docs](https://code.claude.com/docs/en/memory)). You load multiple KB of rules before every prompt. That fragments the prompt cache and dilutes attention every turn — the literal "flow degrades" symptom. *(Fix: Playbook #11.)*
- **Memory-layer collision.** You run auto-memory **+** `remember` **+** `claude-reflect` **+** official `memory` MCP. They hook the same lifecycle events, duplicate observations, and inject conflicting context at session start. More capture ≠ better recall. *(Fix: Playbook #10.)*
- **Ephemeral planning + reactive compaction.** Plans made in chat/plan-mode die at the next compaction; compacting reactively at 90% collapses your cache hit-rate (~80%→<20%) and compresses already-degraded context. *(Fix: Playbook #2, #3, #4, #21.)*

> **One-liner:** Trim the rules, pick one memory layer, persist plans to disk, compact proactively *with steering*, and re-anchor after every compaction. Everything else in this report is optional upside on top of that.

---

## 2. THE PLAYBOOK — 21 habits to fix prompting, context loss & workflow

*Ordered by impact. Full citations for each are in §5 → `06-prompting-context-memory.md`.*

**Workflow discipline**
1. **Explore → Plan → Code → Verify, every time. Never let Claude code first.** Prompt: "Read @files, understand X, **do not write code yet**" → Plan mode (Shift+Tab ×2) → implement one step → verify.
2. **Make the plan a FILE, not a chat turn.** Plan-mode plans vanish at compaction. Persist to `.beads/plans/active-plan.md` (metaswarm already does — *trust the file, not the history*).
3. **`/compact` proactively at 40–60% WITH steering** — `/compact focus on the auth refactor, drop the file dumps`. Never react at 90%.
4. **After ANY compaction, re-anchor:** first message = "Re-read `active-plan.md` + CLAUDE.md, confirm what we're building and where we are." Don't trust auto-rehydration.
5. **Know microcompact vs full compact.** Tool outputs vanish but thread coherent = microcompact (keep going). History replaced by summary = full compact (re-anchor). Don't panic-compact.

**Context hygiene**
6. **One session = one repo.** Cross-repo → orchestrator + Explore subagents, or `--add-dir ../shared`.
7. **Delegate exploration to subagents** ("use a subagent to investigate how X works") — only the summary returns; main context stays clean. You own `dispatching-parallel-agents` — make it the default.
8. **Cap autonomous loops** with a hard turn-limit + verifiable done-condition (the documented 47-iteration spiral makes the agent *dumber*, not just costlier). Native `/goal` bakes in the escape condition.
9. **External memory = STATE/index only, ≤200 lines** (only the first 200 lines of `MEMORY.md` load at start). Pointers + decisions + current position; push detail to on-demand topic files. **Prune your MEMORY.md.**
10. **Pick ONE automatic-capture layer.** ⚠️ You run four. Keep built-in auto-memory (zero overhead) *or* replace it with one better tool — disable the rest; keep `memory` MCP only for explicit typed facts.
11. **AUDIT YOUR RULES PILE — highest-leverage fix.** ⚠️ Enable the `InstructionsLoaded` hook to *see* what loads; move non-every-session rules into `.claude/rules/*.md` with `paths:` frontmatter (web rules load only on `*.tsx/*.css`); run `claude-md-improver`; delete rules that never fire.

**Prompting**
12. **Pin 2–3 non-negotiables to the system prompt, not CLAUDE.md** — `claude --append-system-prompt "TDD mandatory. Never --no-verify. Stay in file scope."` (CLAUDE.md gets summarized in compaction; system prompt is durable). For hard rules, use a PreToolUse hook.
13. **Front-load: ask Claude what it needs BEFORE it acts.** "Before doing anything, ask me the questions you'd need to do this well." (`AskUserQuestion` renders a form.) 4 questions up front beats a 20-min wrong-direction detour.
14. **Write prompts a confused colleague could follow** — paste-ready commands (`npx jest path/to/test`, not "run tests"), and state what *not* to touch ("Do NOT change auth; if you think it needs it, stop and ask").
15. **Structure reusable prompts with XML + examples** — `<task>/<context>/<constraints>/<example>`. Run slash-command and subagent prompts through the Console **Prompt Improver** once; commit the result.
16. **Calibrate effort, don't prompt around shallow reasoning.** Opus 4.7: raise `high`/`xhigh` for multi-file architecture/debugging; lower it + one targeted line for latency-sensitive edits. At max effort, set output budget ≥64k.
17. **Pack unfamiliar code with `repomix`; reference with `@file`; don't let Claude blind-Read** dozens of files (bloats context, breaks cache).

**Verification & recovery**
18. **Verify with evidence; never self-certify.** End tasks with "run `npx jest --coverage` and show the result" / "show the diff." (Your `verification-before-completion` skill + `.coverage-thresholds.json`.) Matches your own "always peer-review" rule.
19. **`/rewind` (esc esc) to recover, not re-explanation.** Claude looping or editing wrong files → rewind to the last clean checkpoint instead of fighting forward through polluted context.
20. **Resume the RIGHT session; `/clear` only with a distilled brief.** `claude --continue` / `--resume` / `--from-pr <url>`. Don't start fresh to "escape the mess."
21. **Add a SessionStart+PreCompact survival hook** to your worst long-running projects (BC RE, etc.): `PreCompact` snapshots `.beads/context/execution-state.md`; `SessionStart` re-injects it via `hookSpecificOutput.additionalContext`. Nothing in your default stack re-injects on the `source=compact` signal — your `.beads/` layout is 90% there; two hooks close the loop. *This is the automated version of #4.*

---

## 3. TOP ~40 GAMECHANGERS FOR YOU

*Curated and deduped from all 7 agents' finalist picks. Each: what it is · why it matters for **your** stack · adopt · status. Full entries with sources in §5.*

### 3.1 Measurement & visibility — your biggest blind spot (you have NONE of this)
You run Ralph loops, councils, and ~40 MCPs with **zero cost/context telemetry**. This category is the cheapest, highest-clarity win.
1. **ccusage** (⭐15k) — token/cost CLI across Claude Code + Codex + Gemini. `npx ccusage@latest`. 🔴
2. **ccstatusline** (⭐9.9k) — always-on statusline: context %, cost, model, quota. Windows-hardened. `npx ccstatusline` → set in `/statusline`. 🔴
3. **Claude-Code-Usage-Monitor** (⭐8k) — real-time "will I hit my Max cap" ML prediction. 🔴
4. **claude-code-history-viewer** (⭐1.4k, Tauri desktop) — offline search over Claude+Codex+Gemini+Antigravity history. 🔴
5. **cc-otel** — Claude Code's native OTLP telemetry → Grafana traces/logs/cost; ideal for auditing what your Ralph loops actually burn. 🔴
6. **Native `/usage`** — built-in quota/usage view you've likely never opened. ✅ (use it)

### 3.2 Context & memory survival — directly serves §1
7. **SessionStart+PreCompact survival hook** (DIY, ~30 lines) — the #1 fix for "Claude forgot mid-session." 🔴 *(Playbook #21)*
8. **`InstructionsLoaded` hook** — logs exactly which instruction files load each turn; the diagnostic that proves your rule-pile tax. 🔴
9. **`--append-system-prompt`** — pin non-negotiables above compaction via a shell alias. 🔴
10. **`claude-md-improver` / `/init` (`CLAUDE_CODE_NEW_INIT=1`)** — you HAVE the plugin; run it on your fat global + project CLAUDE.md, target <200 lines. ✅→apply
11. **Consolidate to ONE memory layer** — evaluate **Basic Memory** (human-readable Markdown, Obsidian-friendly, hybrid search) or **claude-mem** (⭐72k, semantic) as a *replacement* for `remember`+`claude-reflect`, not an addition. 🟡
12. **repomix at task start** — you HAVE it; use it to pack unfamiliar subtrees instead of dozens of Reads. ✅→habit

### 3.3 Native Claude Code features you're underusing
13. **`/effort` + `xhigh` (Opus 4.7)** — your MEMORY literally says "keep effort HIGH"; this is the native dial. 🔴
14. **Sandboxed Bash (`/sandbox`, WSL2) + Auto mode** — run autonomous loops safely **without** `--dangerously-skip-permissions` (which your own rules forbid); OS-enforced. 🔴
15. **`/goal` + Agent View (2.1.142+)** — native bounded autonomous loop + a live dashboard of all sessions with state preserved on detach/resume (you built agent-monitor for exactly this). 🟡
16. **Full hook event matrix** — you're PreToolUse-centric; `SubagentStop`, `PreCompact`, `SessionStart(source=compact)`, prompt/HTTP hooks are unused and high-value. 🔴
17. **Ultrareview (`/code-review ultra`) + Ultraplan** — managed multi-agent *cloud* review with verified findings; a stronger backstop than hand-spun councils. 🟡
18. **Agent SDK tool-search + session storage** — lazy MCP schema loading attacks your ~40-server token bloat; native session storage vs hand-rolled `.beads/`. 🔴
19. **`/rewind`, `--from-pr`, `--add-dir`** — recovery + PR-resume + clean multi-repo, all built-in and forgotten. 🔴

### 3.4 Workflow & harness additions *beyond* metaswarm/Ralph
20. **github/spec-kit** (⭐107k) — don't install on top of metaswarm; **steal the disk-artifact discipline** (`docs/specs/*.md` survive compaction). 🟡
21. **anthropics/claude-code-action** (⭐7.8k, official) — the missing **server-side/CI** agent layer (PR review, triage, scheduled runs); your whole stack is local-only. 🔴
22. **claude-code-router** (⭐34k) — proxy-layer per-scenario model routing → big cost lever on heavy loops. 🔴
23. **claude-squad** (⭐7.7k) — multi-session parallel agent cockpit (complements Ralph's single loop). 🟡 *(tmux/WSL-gated on Windows)*
24. **claude-review-loop** (hamelsmu) — a **Stop-hook that blocks exit until cross-model review passes** — structural enforcement of your "never self-certify" rule. 🔴
25. **dagger/container-use** (⭐3.8k) — container-level (not just worktree) isolation for risky parallel experiments. 🔴

### 3.5 MCP gaps that actually matter for you
26. **sequential-thinking** (official) — cheapest reasoning upgrade; your council's Codex/Antigravity seats lack Claude-native thinking. 🔴
27. **filesystem** (official) — safe file primitive for your model-council/agentchattr clients. 🔴
28. **time** (official) — Ralph loops + cron agents constantly trip on timezone/now. 🔴
29. **awslabs/mcp** (⭐9.1k) — biggest cloud gap; you have the aws-serverless *plugin* but no AWS MCP server. 🔴
30. **n8n-mcp** (⭐17k) — Claude authors/manages n8n workflows with full ~1,400-node knowledge; your biggest *automation* unlock. 🔴
31. **DesktopCommanderMCP** (⭐6k) — terminal + live interactive process control (SSH/DB/REPL); Windows-native, no token cost. 🔴
32. **motherduck/mcp-server-motherduck** — DuckDB over MCP: query Parquet/CSV/S3/local files in-process; pairs with your data work. 🔴
33. **grafana** (⭐3k) / **atlassian** (⭐5.3k) — complete observability (metrics/logs) / Jira-Confluence (zero coverage today). 🔴

### 3.6 Niche power for your domains (RE / security / data)
34. **Arkana** — "malware lab behind one prompt": angr + capa + FLOSS + Qiling, 260 tools — adds **symbolic execution** your IDA/Ghidra set lacks. 🔴
35. **Tengu** — safety-first pentest copilot (80 tools, human-in-the-loop, audit, auto-reports). 🔴
36. **Crawl4AI `crawl-mcp`** — anti-bot scraping + Office/PDF/YouTube extraction + 88% token-reduction summaries. 🔴
37. **mcp-financex** — markets + options Greeks + SEC filings + DCF, no API keys (entire new domain). 🔴

### 3.7 Skills & skill sources worth adding (you have ~350 — these are net-new)
38. **wshobson/agents** (155 skills, multi-harness) + **officialskills.sh/VoltAgent** (1,424 *vendor* skills) — the two collections to subscribe to. 🔴
39. **superpowers problem-solving skills** (`when-stuck`, `simplification-cascades`) — directly counter your "BC RE: don't overcomplicate / stalled for weeks" pattern. 🔴
40. **Skill_Seekers** (⭐13.8k) auto-converts docs/repos → skills (feeds your constant Frida/IDA/BC authoring) · **Office docx/pptx/xlsx** (round-trip w/ tracked changes — you have generic pdf/slides only) · **using-tmux-for-interactive-commands** (drive gdb/radare2/REPL TUIs) · **windows-vm** (isolated APK/RE sandbox). 🔴

---

## 4. The un-overwhelm: 30 / 60 / 90 adoption roadmap

You cannot adopt 40 things. Do these, in order. Stop if it stops helping.

**Week 1 — fix the pain (no new tools except telemetry):**
- [ ] Run `claude-md-improver` on global + project CLAUDE.md → <200 lines each (Playbook #11).
- [ ] Move web/language rules into `.claude/rules/*.md` with `paths:` frontmatter; enable `InstructionsLoaded` hook to verify the drop.
- [ ] Disable 2 of your 4 memory layers; keep auto-memory + `memory` MCP (Playbook #10).
- [ ] Install **ccusage** + **ccstatusline** (you'll finally see context%/cost live).
- [ ] Adopt the habit: plan to `.beads/plans/active-plan.md`, `/compact` proactively with steering (Playbook #2,#3).

**Weeks 2–4 — durability + measurement:**
- [ ] Wire the **PreCompact+SessionStart survival hook** into your BC RE / long projects (Playbook #21).
- [ ] Add `--append-system-prompt` alias with your 3 non-negotiables (#12).
- [ ] Add MCP gaps: **sequential-thinking, filesystem, time** (5-min wins), then **n8n-mcp** if automation interests you.
- [ ] Try **claude-code-router** to cut loop costs; measure with ccusage before/after.

**Months 2–3 — depth where it pays:**
- [ ] Evaluate **Basic Memory vs claude-mem** head-to-head; consolidate to the winner.
- [ ] Add **claude-code-action** for server-side CI review on your repos.
- [ ] Domain depth: **Arkana** (RE symbolic exec), **cc-otel→Grafana** (loop observability).
- [ ] Subscribe to **wshobson/agents** + harvest superpowers problem-solving skills.

---

## 5. Full catalog (~390 tools, by domain)

*Each domain below is a complete deduped catalog from one research agent, in your-words descriptions with sources, star counts, adopt steps, and ✅/🟡/🔴 status. Search for what you need.*

---

## 5.1 — Official Claude Code core capabilities


> Research agent #1 of 7. Domain: **official** Claude Code / Anthropic features only (no third-party).
> Audience: a Claude Code power user on Windows 11 / PowerShell who already runs ECC, metaswarm, Ralph, superpowers, ToolUniverse, agentchattr, model-council, ~350 skills, ~40 MCP servers.
> Thesis: this user has built elaborate *third-party* replacements for things Claude Code now ships *natively*. The biggest wins are first-party features that **obsolete or augment** their custom stack, plus 2026 net-new features they likely haven't seen.
> Status legend: ✅ HAVE · 🟡 PARTIAL · 🔴 NET-NEW-GAP. All claims cite official docs (code.claude.com / docs.claude.com / github.com/anthropics).

---

### A. Autonomous-loop & orchestration features (vs Ralph / metaswarm / model-council / agentchattr)

#### `/goal` — session-scoped completion-condition loop
- **Source:** https://code.claude.com/docs/en/goal
- **Category:** Autonomous execution (native loop)
- **What it is:** You set a verifiable end-state (`/goal all tests in test/auth pass and lint is clean`) and Claude keeps starting new turns by itself until a separate fast model (Haiku) confirms the condition holds, then auto-clears. It is a built-in wrapper around a session-scoped prompt-based Stop hook.
- **Why it's a gamechanger:** This is a native, zero-setup version of the Ralph "keep-going-until-done" loop, with an *independent evaluator* deciding completion rather than the worker self-certifying — exactly the discipline your CLAUDE.md and MEMORY ("never self-certify", "always peer review") demand. Condition can be up to 4000 chars and survives `--resume`.
- **Adopt:** `/goal <condition, e.g. "npm test exits 0 and git status is clean, or stop after 20 turns">` ; non-interactive: `claude -p "/goal CHANGELOG.md has an entry for every PR merged this week"` ; requires v2.1.139+.
- **Status:** 🔴 NET-NEW-GAP (you reimplemented this as Ralph phase-controller + enforced FSM; `/goal` is the lightweight native primitive for the common case)

#### `/loop` — interval / self-paced re-run of a prompt or command
- **Source:** https://code.claude.com/docs/en/scheduled-tasks
- **Category:** Autonomous execution (polling loop)
- **What it is:** Re-runs a prompt on a fixed cron-derived interval (`/loop 5m check the deploy`), at a Claude-chosen dynamic interval (omit the interval), or runs a built-in maintenance prompt (bare `/loop`) that babysits the branch's PR — review comments, failing CI, merge conflicts. You can loop another slash command: `/loop 20m /review-pr 1234`.
- **Why it's a gamechanger:** Native PR-babysitter and deploy-poller without writing a Ralph harness. The dynamic mode self-ends when work is provably done. Customizable via `.claude/loop.md` (project) or `~/.claude/loop.md` (user).
- **Adopt:** `/loop` (maintenance), `/loop 15m <prompt>`, or drop a `.claude/loop.md`. Requires v2.1.72+. Disable globally with `CLAUDE_CODE_DISABLE_CRON=1`.
- **Status:** 🟡 PARTIAL (you have `loop`/`ralph-loop` skills; the *native* `/loop` + `loop.md` maintenance default and command-looping are likely underused)

#### Stop / StopFailure hooks for deterministic loop control
- **Source:** https://code.claude.com/docs/en/hooks ; https://code.claude.com/docs/en/goal (comparison table)
- **Category:** Hooks (turn-cadence)
- **What it is:** A `Stop` hook fires after every turn and can run a *script* (deterministic check) or a *prompt* (model-evaluated) to decide whether Claude keeps working — the same machinery `/goal` wraps, but settings-scoped so it applies to every session. `StopFailure` fires when a turn ends in failure.
- **Why it's a gamechanger:** Lets you encode metaswarm-style "don't stop until coverage gate passes" as a persistent settings rule instead of orchestrator code. Deterministic script Stop hooks are more reliable than prompting the model to re-check.
- **Adopt:** add a `Stop` hook in `~/.claude/settings.json` that runs e.g. `jest --coverage` and exits non-zero (with feedback) until thresholds pass.
- **Status:** 🟡 PARTIAL (your CLAUDE.md references Stop hooks conceptually; verify you actually have script-based Stop gates wired, not just orchestrator logic)

#### Agent view (`claude agents`) — dispatch & monitor background sessions
- **Source:** https://code.claude.com/docs/en/agent-view ; https://code.claude.com/docs/en/agents
- **Category:** Multi-agent orchestration (native)
- **What it is:** One screen (`claude agents`) listing every background Claude session — what's running, what needs input, what's done — with state icons, peek/reply, and attach-to-conversation. Each background session is a full conversation that keeps running with no terminal attached, and **auto-moves into its own worktree** when it needs to edit files.
- **Why it's a gamechanger:** This is a native equivalent of your `agent-monitor` tool (D:\agent-monitor) and a big chunk of agentchattr's value — built in, with automatic worktree isolation so parallel agents don't collide. Dispatch a bug-fix, a PR review, and a flaky-test hunt as three rows and check back.
- **Adopt:** `claude agents` (v2.1.139+). From a session, `/tasks` shows background work; `/agents` shows in-session subagents.
- **Status:** 🔴 NET-NEW-GAP (you built agent-monitor for this; the native surface is more integrated)

#### Agent teams (`CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS`) — lead + messaging teammates
- **Source:** https://code.claude.com/docs/en/agent-teams ; https://code.claude.com/docs/en/agents
- **Category:** Multi-agent orchestration (native, experimental)
- **What it is:** Multiple full Claude Code instances coordinated by a *lead*, sharing a task list and **messaging each other directly** (unlike subagents, which only report back to their spawner). You can talk to individual teammates without going through the lead.
- **Why it's a gamechanger:** Native inter-agent messaging is exactly what agentchattr and model-council provide via custom infra. metaswarm's CLAUDE.md already references `TeamCreate`/`SendMessage` "Team Mode" — this is the underlying official capability.
- **Adopt:** set `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS` in settings.json/env (v2.1.32+). Known limits around resumption/shutdown — experimental.
- **Status:** 🟡 PARTIAL (metaswarm references Team Mode; confirm you've actually enabled the native flag vs only using your custom coordinators)

#### `/batch` — split one large change into 5–30 worktree-isolated subagents, each opens a PR
- **Source:** https://code.claude.com/docs/en/agents
- **Category:** Multi-agent orchestration (native)
- **What it is:** A planned fan-out: describe a repo-wide migration or mechanical refactor in one instruction and Claude splits it into 5–30 subagents, each in its own worktree, each opening a separate pull request.
- **Why it's a gamechanger:** Native large-scale parallel refactor that maps onto your "parallel agents for independent operations" rule — without orchestrating it yourself. Ideal for codemod-style changes across many files.
- **Adopt:** `/batch <one-instruction repo-wide change>`.
- **Status:** 🔴 NET-NEW-GAP

#### Channels — push external events into a running session (Telegram/Discord/iMessage)
- **Source:** https://code.claude.com/docs/en/channels ; https://code.claude.com/docs/en/channels-reference
- **Category:** Event-driven I/O (research preview)
- **What it is:** An MCP server that **pushes** events into your already-open session (CI results, chat messages, monitoring alerts) so Claude reacts while you're away — and can be two-way, replying back through the same channel like a chat bridge. Telegram, Discord, iMessage ship in the preview; installed as a plugin with your own creds.
- **Why it's a gamechanger:** This is the official "talk to your agent from your phone / pipe CI failures in live" capability — overlaps heavily with agentchattr's chat-coordinator concept but is first-party and event-pushed (not polled). Pairs with `/goal` or a background session for an always-on assistant.
- **Adopt:** install a channel plugin (v2.1.80+, claude.ai/Console auth; Team/Enterprise must enable). Demo locally with the `fakechat` channel.
- **Status:** 🔴 NET-NEW-GAP

#### Monitor tool — stream a background script's output into the conversation
- **Source:** https://code.claude.com/docs/en/whats-new/index (Week 15) ; https://code.claude.com/docs/en/scheduled-tasks
- **Category:** Background execution (native tool)
- **What it is:** Runs a background script and streams each stdout line back into the conversation as it appears, so Claude can tail logs and react live instead of re-polling. `/loop` will use it automatically in dynamic mode because it's more token-efficient than re-running a prompt.
- **Why it's a gamechanger:** Native log-tailing / "watch this build and tell me when it breaks" without a polling loop burning tokens. Directly relevant to your long-running RE/build workflows.
- **Adopt:** ask Claude to "use the Monitor tool to tail <script>" (it's in your deferred-tools list as `Monitor`).
- **Status:** 🟡 PARTIAL (tool is available to you; likely underused vs sleeping/polling)

---

### B. Cloud-offload features (vs metaswarm review gates / your own review councils)

#### Ultraplan (`/ultraplan`) — draft a plan in the cloud, review in browser, execute anywhere
- **Source:** https://code.claude.com/docs/en/ultraplan
- **Category:** Planning (research preview, cloud)
- **What it is:** Hands a planning task to a Claude Code-on-the-web session running in plan mode. Claude drafts remotely while your terminal stays free; you open the plan in a browser to leave **inline comments on specific sections**, iterate, then choose to execute on the web (opens a PR) or "teleport back to terminal."
- **Why it's a gamechanger:** A richer review surface than your terminal-bound metaswarm plan-review gate — section-level commenting and emoji reactions — and it offloads drafting so you keep working. Complements (doesn't replace) your adversarial plan-review gates.
- **Adopt:** `/ultraplan migrate the auth service from sessions to JWTs`, or just include the word "ultraplan" in a prompt (v2.1.91+, needs Claude Code on the web + GitHub repo).
- **Status:** 🔴 NET-NEW-GAP

#### Ultrareview (`/code-review ultra`) — multi-agent cloud bug-hunt with verified findings
- **Source:** https://code.claude.com/docs/en/ultrareview
- **Category:** Code review (research preview, cloud)
- **What it is:** Launches a *fleet* of reviewer agents in a remote sandbox to find bugs in your branch or PR. **Every finding is independently reproduced and verified**, so results are real bugs not style nits. Runs in background (~5–10 min); findings come back to your CLI. Has a CI subcommand `claude ultrareview [PR#]`.
- **Why it's a gamechanger:** Independent verification + broad parallel coverage is exactly the rigor your "always peer-review, cross-model, scale to council" memory calls for — but as a managed cloud service instead of you spinning up codex-review + Claude reviewers by hand. 3 free runs on Pro/Max, then ~$5–20/run via usage credits.
- **Adopt:** `/code-review ultra` (branch) or `/code-review ultra 1234` (PR). CI: `claude ultrareview --json`. v2.1.86+; requires Claude.ai auth + usage credits on.
- **Status:** 🔴 NET-NEW-GAP (you orchestrate review councils manually; this is the native deep version)

#### Routines — cron / GitHub-event / API-triggered cloud agents
- **Source:** https://code.claude.com/docs/en/routines ; https://code.claude.com/docs/en/whats-new/index (Week 16)
- **Category:** Scheduling (Anthropic-managed cloud)
- **What it is:** Templated Claude Code agents that run on **Anthropic's infrastructure** on a schedule, on a GitHub event, or on an API call — they run even when your machine is off. Configured at claude.ai/code/routines (or `/schedule` in the CLI).
- **Why it's a gamechanger:** Durable, machine-independent automation (nightly dependency audits, morning PR triage) that your session-scoped Ralph loops and `/loop` can't provide because they need a machine on. Replaces self-hosted cron + a running session.
- **Adopt:** create at https://claude.ai/code/routines or via `/schedule`. Minimum interval 1 hour.
- **Status:** 🔴 NET-NEW-GAP

#### Remote Control — drive a local session from claude.ai/code on any device
- **Source:** https://code.claude.com/docs/en/remote-control
- **Category:** Remote access
- **What it is:** Connect the claude.ai/code web interface to a session running on *your own machine*, so you can continue a local session (with full local file/tool access) from your phone or another computer.
- **Why it's a gamechanger:** Check on / steer your long-running local RE and build sessions from anywhere without exposing your box. (Note: mutually exclusive with ultraplan — both occupy the claude.ai/code interface.)
- **Adopt:** see the Remote Control doc to connect; pairs with mobile push notifications (below).
- **Status:** 🔴 NET-NEW-GAP

#### Mobile push notifications + `/usage`
- **Source:** https://code.claude.com/docs/en/whats-new/index (Week 16)
- **Category:** Notifications / cost visibility
- **What it is:** Push notifications ping your phone when a long task finishes or Claude needs you. `/usage` shows what's driving your rate limits; `/usage-credits` toggles credit billing.
- **Why it's a gamechanger:** Stop babysitting long autonomous runs — get pinged instead. `/usage` is the official way to diagnose the rate-limit/401 churn noted in your memory (you run many concurrent instances).
- **Adopt:** `/usage` in any session; enable push in the mobile app.
- **Status:** 🟡 PARTIAL (likely never run `/usage` despite concurrent-instance cost concerns)

---

### C. Context & state management (vs strategic-compact / save-session / your auto-memory)

#### Checkpointing & `/rewind` — restore code/conversation to any prior prompt
- **Source:** https://code.claude.com/docs/en/checkpointing
- **Category:** Session state (native)
- **What it is:** Claude Code auto-captures code state before each edit; every user prompt is a checkpoint, persisted across sessions (30-day retention). `/rewind` (or double-`Esc` on empty input) opens a menu to **Restore code and conversation / Restore code only / Restore conversation only** at any past prompt. *Caveat:* does NOT track files changed by bash commands — only direct file-edit tools.
- **Why it's a gamechanger:** Native "local undo" for ambitious refactors — try an approach, `/rewind` if it goes wrong, without git gymnastics. Independent of your save-session/checkpoint skills. The bash-not-tracked caveat matters for your script-heavy RE work (rely on git there).
- **Adopt:** `/rewind` or Esc-Esc. Retention configurable.
- **Status:** 🟡 PARTIAL (you have a `checkpoint`/`save-session` skill; the native `/rewind` granular restore is likely underused)

#### `/rewind` Summarize (targeted compaction) + `--fork-session`
- **Source:** https://code.claude.com/docs/en/checkpointing
- **Category:** Context management (native)
- **What it is:** Two summarize actions in the rewind menu: **Summarize up to here** (compress early setup, keep recent work full-detail) and **Summarize from here** (discard a side-discussion, keep early context). Unlike `/compact` (whole conversation), you choose which side to compress. To branch instead of compress: `claude --continue --fork-session`.
- **Why it's a gamechanger:** Surgical context recovery — kill a verbose debugging tangent while preserving your original instructions, the exact failure mode your "strategic-compact" skill targets, but native and targeted. `--fork-session` lets you explore an alternative without destroying the original session.
- **Adopt:** `/rewind` → Summarize up to/from here; `claude --continue --fork-session`.
- **Status:** 🟡 PARTIAL

#### Microcompact / auto-compact behavior
- **Source:** https://code.claude.com/docs/en/context-window ; https://code.claude.com/docs/en/best-practices
- **Category:** Context management (native)
- **What it is:** Claude Code auto-compacts as the context window fills; `/compact [instructions]` triggers it manually with optional focus instructions. Microcompact trims stale tool results automatically to extend a session before a full compaction is needed.
- **Why it's a gamechanger:** Understanding the native compaction ladder (microcompact → auto-compact → manual `/compact` → `/rewind` summarize) lets you stop fighting the context window manually. Your performance.md rule "avoid last 20% of context" is partly handled for you now.
- **Adopt:** `/compact focus on the auth refactor decisions`; let microcompact run; read context-window.md.
- **Status:** 🟡 PARTIAL

#### Auto memory (Claude-written, per-repo, shared across worktrees)
- **Source:** https://code.claude.com/docs/en/memory
- **Category:** Persistent memory (native)
- **What it is:** Two complementary systems load at session start: **CLAUDE.md** (you write rules) and **auto memory** (Claude writes learnings/build-commands/debugging insights from your corrections, per-repository, shared across worktrees, loaded first 200 lines/25KB).
- **Why it's a gamechanger:** You already lean on the user-level auto-memory (MEMORY.md). The doc clarifies auto memory is *per-repo* and *worktree-shared* — distinct from your global notes — so project-specific learnings (e.g. BC RE recipes) belong in repo auto-memory, not your global file.
- **Adopt:** let Claude take notes; review repo `.claude` memory; keep CLAUDE.md for rules, auto memory for discovered facts.
- **Status:** ✅ HAVE (global) / 🟡 PARTIAL (per-repo auto memory likely underused)

#### `.claude/rules/` — scope rules to file types (path-matched memory)
- **Source:** https://code.claude.com/docs/en/memory
- **Category:** Persistent memory (native)
- **What it is:** Rule files under `.claude/rules/` can be scoped so they only load when relevant file types are in play, instead of bloating every session's context.
- **Why it's a gamechanger:** Your `~/.claude/rules/common`, `/web` etc. are huge and load globally. Path-scoped rules cut token cost — load Python rules only on Python work.
- **Adopt:** organize `.claude/rules/<scope>.md` with path-matching frontmatter.
- **Status:** 🟡 PARTIAL (you have a rules/ tree; verify it uses native path-scoping vs always-on loading)

---

### D. Hooks — the full event & type matrix (vs your PreToolUse-centric pattern)

#### Full hook event set (12 events across 3 cadences)
- **Source:** https://code.claude.com/docs/en/hooks ; https://code.claude.com/docs/en/hooks-guide
- **Category:** Hooks (lifecycle)
- **What it is:** Events fire at: **once/session** — `SessionStart`, `SessionEnd`, `Setup` (for `--init`/`--init-only`/`--maintenance` in CI); **once/turn** — `UserPromptSubmit`, `Stop`, `StopFailure`; **every tool call** — `PreToolUse`, `PostToolUse`, `PermissionRequest`; plus `Notification`, `SubagentStop`, `PreCompact`.
- **Why it's a gamechanger:** Your global hooks.md only documents PreToolUse/PostToolUse/Stop. You're missing: `SessionStart` (auto-prime context), `UserPromptSubmit` (inject/validate every prompt), `PermissionRequest` (custom approval logic), `SubagentStop` (gate subagent output — directly serves "never self-certify"), `PreCompact` (preserve state before compaction — aligns with your `.beads/` context-recovery design), `Setup` (CI one-time prep).
- **Adopt:** add hooks per event in settings.json; e.g. `SubagentStop` to run a reviewer, `PreCompact` to dump state to `.beads/`.
- **Status:** 🟡 PARTIAL (heavy PreToolUse user; most of the event matrix unused)

#### HTTP hooks & prompt hooks (beyond shell-command hooks)
- **Source:** https://code.claude.com/docs/en/hooks
- **Category:** Hooks (handler types)
- **What it is:** A hook handler can be a **shell command** (stdin JSON), an **HTTP endpoint** (POST body JSON), or an **LLM prompt** (model-evaluated decision). Hooks can also be **async**, and conditional via `if` expressions (Week 13). Hooks see the active effort level via `effort.level` / `$CLAUDE_EFFORT` (Week 19).
- **Why it's a gamechanger:** Prompt hooks = model-judged gates without writing a script (this is what `/goal` uses internally). HTTP hooks = route lifecycle events to your existing services (model-council, agentchattr) instead of shelling out. `if` hooks reduce noise.
- **Adopt:** in a hook definition use `"type": "http"` with a URL, or a prompt hook with a condition; gate by `$CLAUDE_EFFORT`.
- **Status:** 🔴 NET-NEW-GAP (you almost certainly only use command hooks)

#### `disableAllHooks` / `allowManagedHooksOnly` / managed hooks
- **Source:** https://code.claude.com/docs/en/hooks ; https://code.claude.com/docs/en/goal (requirements)
- **Category:** Hooks (governance)
- **What it is:** Settings that disable all hooks or restrict to managed hooks only; note `/goal` is unavailable when these are set. Hooks require the workspace trust dialog to be accepted.
- **Why it's a gamechanger:** Relevant to your Ralph headless trust-gate finding (loop agents run `--setting-sources project,local` + `--dangerously-skip-permissions`) — understand exactly which hooks survive in headless/managed contexts so your gates actually fire.
- **Adopt:** audit hook settings across user/project/managed scopes for your headless loops.
- **Status:** 🟡 PARTIAL

---

### E. Permissions, sandboxing & autonomy (vs `--dangerously-skip-permissions` habit)

#### Auto mode — classifier-gated permissions (the middle ground)
- **Source:** https://code.claude.com/docs/en/auto-mode-config ; https://code.claude.com/docs/en/whats-new/index (Week 13)
- **Category:** Permissions (research preview)
- **What it is:** A classifier reviews each tool call and auto-approves safe actions while blocking risky ones — the middle ground between approving everything and `--dangerously-skip-permissions`. Supports **hard deny rules** that block unconditionally regardless of allow exceptions (Week 19).
- **Why it's a gamechanger:** Your CLAUDE.md and global rules forbid `--dangerously-skip-permissions`, yet your Ralph loops use it out of necessity. Auto mode gives autonomous execution *with* a safety classifier — a far better default for unattended loops than skip-all.
- **Adopt:** enable auto mode (see auto-mode-config.md); add hard-deny rules for destructive ops.
- **Status:** 🔴 NET-NEW-GAP

#### Sandboxed Bash tool (`/sandbox`) — OS-level filesystem + network isolation
- **Source:** https://code.claude.com/docs/en/sandboxing ; https://code.claude.com/docs/en/sandbox-environments
- **Category:** Security / autonomy
- **What it is:** OS-enforced isolation (macOS Seatbelt; Linux/WSL2 bubblewrap+socat) so Claude runs most bash without prompting, bounded by a filesystem/network allowlist you define. Auto-allow mode runs sandboxed commands unattended; an escape hatch (`dangerouslyDisableSandbox`) falls back to the permission flow. **Native Windows is NOT supported — must run inside WSL2.**
- **Why it's a gamechanger:** Lets autonomous loops run safely without `--dangerously-skip-permissions` — the OS, not the model, enforces the boundary, so it holds even if an allowed command misbehaves. Big for your RE/cleanup loops.
- **Adopt:** **on Windows you must use WSL2.** `sudo apt-get install bubblewrap socat`, then `/sandbox`, pick auto-allow; set `sandbox.enabled: true` in `~/.claude/settings.json`; restrict creds via `sandbox.filesystem.denyRead: ["~/.aws","~/.ssh"]`.
- **Status:** 🔴 NET-NEW-GAP (Windows-native blocked; WSL2 path is the unlock — your disk-cleanup memory shows you already run WSL)

#### Permission modes (`plan`, `acceptEdits`, `bypassPermissions`, default) + `Shift+Tab`
- **Source:** https://code.claude.com/docs/en/permission-modes ; https://code.claude.com/docs/en/permissions
- **Category:** Permissions (native)
- **What it is:** Four modes selectable per-session via `--permission-mode` or by cycling with `Shift+Tab`: default (prompt), `acceptEdits` (auto-accept file edits), `plan` (read-only, propose plan, no disk writes), `bypassPermissions`. Permission rules use allow/ask/deny with path/tool matchers.
- **Why it's a gamechanger:** `Shift+Tab` into plan mode mid-session is the lightweight native alternative to your metaswarm `/start-task` for quick read-only investigation; `acceptEdits` speeds trusted refactors. Your CLAUDE.md says "use /start-task instead of EnterPlanMode" for gated work — but native plan mode is right for ungated quick reads.
- **Adopt:** `Shift+Tab` to cycle; `claude --permission-mode plan`; tune allow/deny in settings.json.
- **Status:** 🟡 PARTIAL

#### `fewer-permission-prompts` / settings allowlist tuning
- **Source:** https://code.claude.com/docs/en/permissions (allow rules) ; built-in `/fewer-permission-prompts` skill (in your skill list)
- **Category:** Permissions (ergonomics)
- **What it is:** Scans your transcripts for common read-only Bash/MCP calls and writes a prioritized allowlist into `.claude/settings.json` to cut prompts.
- **Why it's a gamechanger:** Given ~40 MCP servers and constant tool calls, an auto-generated allowlist drastically reduces friction without blanket-skipping permissions.
- **Adopt:** run `/fewer-permission-prompts`.
- **Status:** 🟡 PARTIAL (skill present; likely not run)

---

### F. Model & speed controls (2026)

#### Fast mode (`/fast`) — 2.5× faster Opus
- **Source:** https://code.claude.com/docs/en/fast-mode
- **Category:** Model config (research preview)
- **What it is:** Same Opus model/quality, a high-speed API config that's **2.5× faster at higher cost** ($30/$150 per MTok flat across the 1M window). Toggle with `/fast` (Tab) or `"fastMode": true`. Billed via usage credits only, separate rate-limit pool, auto-falls-back to standard on cooldown.
- **Why it's a gamechanger:** For live debugging / rapid iteration the latency win is large. You're already on Opus 4.7 [1m]; `/fast` is the latency lever you probably haven't flipped. (Enable at session start — switching mid-conversation charges the whole context at fast rates.)
- **Adopt:** `/fast` (v2.1.36+; usage credits must be on). Combine with lower effort for max speed on simple tasks.
- **Status:** 🔴 NET-NEW-GAP

#### `/effort` slider + `xhigh` effort level (Opus 4.7)
- **Source:** https://code.claude.com/docs/en/whats-new/index (Week 16) ; https://code.claude.com/docs/en/model-config
- **Category:** Model config (2026)
- **What it is:** Opus 4.7 added an `xhigh` effort level (the recommended setting for most coding work) and an interactive `/effort` slider to dial reasoning depth up/down per session. Hooks can read it via `$CLAUDE_EFFORT`.
- **Why it's a gamechanger:** Your MEMORY explicitly flags "maintain full rigor / keep effort HIGH across the whole session." `/effort` is the *native control* for that — set `xhigh` for deep RE/architecture, dial down for mechanical work. Directly actionable on your stated quality concern.
- **Adopt:** `/effort` to open the slider; set `xhigh` for complex work.
- **Status:** 🔴 NET-NEW-GAP (your rigor concern has a literal native dial you're not naming)

---

### G. UI / ergonomics (largely untouched by this user)

#### Output styles (`/config` → Output style; custom Markdown styles)
- **Source:** https://code.claude.com/docs/en/output-styles
- **Category:** Personalization (native)
- **What it is:** Modify the system prompt's role/tone/format. Built-ins: **Proactive** (executes immediately, makes reasonable assumptions — stronger autonomous guidance than auto mode, without changing permission mode), **Explanatory** (educational "Insights"), **Learning** (adds `TODO(human)` markers for you to fill in). Custom styles are Markdown in `~/.claude/output-styles` with `keep-coding-instructions` frontmatter.
- **Why it's a gamechanger:** The **Proactive** style is a one-line way to get more autonomous, less-asking behavior — relevant if you find agents too tentative. Custom styles (e.g. "always lead with a Mermaid diagram") standardize output without re-prompting. Plugins can ship styles with `force-for-plugin`.
- **Adopt:** `/config` → Output style → Proactive; or create `~/.claude/output-styles/<name>.md`. (Standalone `/output-style` was removed v2.1.91 — use `/config` or the `outputStyle` setting.)
- **Status:** 🔴 NET-NEW-GAP (not in your inventory; Proactive style especially underused)

#### Status line (`statusLine` in settings)
- **Source:** https://code.claude.com/docs/en/statusline
- **Category:** Personalization (native)
- **What it is:** A customizable bottom status bar driven by a script you provide, showing model, context usage, git branch, cost, effort level, etc. Configured via `statusLine` in settings.json (or `/statusline`).
- **Why it's a gamechanger:** Live context-window % and cost in-view directly supports your performance.md "avoid last 20% of context" rule and your concurrent-instance cost concerns — no more guessing when to compact.
- **Adopt:** `/statusline` or set `statusLine` in settings.json with a script emitting context/cost/branch.
- **Status:** 🔴 NET-NEW-GAP

#### Custom themes (`/theme`) + flicker-free alt-screen rendering
- **Source:** https://code.claude.com/docs/en/whats-new/index (Week 17, Week 14)
- **Category:** Personalization (2026)
- **What it is:** Build and ship color palettes from `/theme` or a plugin (Week 17). Alt-screen rendering removed flicker (Week 14) and `/fullscreen` gives full-screen rendering.
- **Why it's a gamechanger:** Minor but quality-of-life; themes are shippable via plugins so you could standardize across your many sessions.
- **Adopt:** `/theme`; `/fullscreen`.
- **Status:** 🔴 NET-NEW-GAP

#### Voice dictation
- **Source:** https://code.claude.com/docs/en/voice-dictation
- **Category:** Input (native)
- **What it is:** Dictate prompts by voice in supported surfaces.
- **Why it's a gamechanger:** Faster prompt entry for long instructions; useful on desktop.
- **Adopt:** see voice-dictation.md for the binding.
- **Status:** 🔴 NET-NEW-GAP

#### `/powerup` — interactive lessons with animated demos
- **Source:** https://code.claude.com/docs/en/common-workflows ; https://code.claude.com/docs/en/whats-new/index (Week 14)
- **Category:** Discovery (native)
- **What it is:** Built-in interactive lessons that demo Claude Code features with animations.
- **Why it's a gamechanger:** The fastest official way to discover features you're underusing — exactly this gap-analysis exercise, built in.
- **Adopt:** `/powerup`.
- **Status:** 🔴 NET-NEW-GAP

#### Deep links (`claude-cli://open?repo=…&q=…`)
- **Source:** https://code.claude.com/docs/en/deep-links
- **Category:** Session launching (native)
- **What it is:** A registered `claude-cli://` URL scheme that opens a new terminal session in a chosen repo/cwd with a prompt pre-filled (not auto-sent). Embed in runbooks, dashboards, CI alerts. On Windows the handler writes to `HKCU\Software\Classes\claude-cli` and prefers Windows Terminal.
- **Why it's a gamechanger:** One-click "open Claude in the right repo with the right prompt" for your RE runbooks and incident playbooks — turns your MEMORY recipes into clickable launchers. `repo=owner/name` resolves to your most-recent local clone.
- **Adopt:** build `claude-cli://open?repo=acme/x&q=<url-encoded prompt>`; PowerShell: `Start-Process "claude-cli://open?..."` (v2.1.91+).
- **Status:** 🔴 NET-NEW-GAP

#### Session recap + transcript search (`/`)
- **Source:** https://code.claude.com/docs/en/whats-new/index (Week 17, Week 13)
- **Category:** Sessions (2026)
- **What it is:** Session recap summarizes what happened while a terminal was unfocused; `/` does transcript search within a session.
- **Why it's a gamechanger:** Reorient instantly after stepping away from a long autonomous run; search a sprawling transcript instead of scrolling.
- **Adopt:** `/` to search; recap appears on refocus.
- **Status:** 🟡 PARTIAL

---

### H. Sessions, headless & SDK (vs your save-session / sessions skills)

#### `--resume` / `--continue` / `--fork-session` / `--from-pr` + named/branched sessions
- **Source:** https://code.claude.com/docs/en/sessions ; https://code.claude.com/docs/en/common-workflows
- **Category:** Sessions (native)
- **What it is:** `claude --continue` resumes the latest session in the cwd; `claude --resume` shows a picker; `/resume` from inside a session; `--fork-session` branches; `claude --from-pr <n>` (or pasting a PR URL into the picker) reopens the session that created a PR. Sessions can be named and branched.
- **Why it's a gamechanger:** `--from-pr` and PR-URL-in-picker close the loop on your PR-shepherd workflows; `--fork-session` enables safe what-if exploration. Native, no save-session skill needed for the common cases.
- **Adopt:** `claude --continue`, `claude --resume`, `claude --from-pr 1234`, `claude --continue --fork-session`.
- **Status:** 🟡 PARTIAL (you have sessions/save-session skills; native `--from-pr`/`--fork-session` likely underused)

#### `--worktree` + `.worktreeinclude` + `worktree.baseRef`
- **Source:** https://code.claude.com/docs/en/worktrees ; https://code.claude.com/docs/en/common-workflows ; https://code.claude.com/docs/en/whats-new/index (Week 19)
- **Category:** Parallelism (native)
- **What it is:** `claude --worktree feature-auth` starts an isolated checkout on its own branch for parallel sessions that won't collide. `.worktreeinclude` copies in untracked files (env, build artifacts); `worktree.baseRef` chooses remote-default vs local `HEAD` as the branch point. Non-git VCS supported.
- **Why it's a gamechanger:** Native parallel-session isolation underpins agent view and `/batch`. Your `using-git-worktrees`/`worktree-development` skills wrap this — but `.worktreeinclude` (for your env/build files) and `worktree.baseRef` are config you may not be using.
- **Adopt:** `claude --worktree <name>`; add `.worktreeinclude`; set `worktree.baseRef`.
- **Status:** 🟡 PARTIAL

#### Headless / print mode (`-p`, `--output-format stream-json`, `--input-format`)
- **Source:** https://code.claude.com/docs/en/headless ; https://code.claude.com/docs/en/common-workflows
- **Category:** Programmatic (native)
- **What it is:** `claude -p "prompt"` runs non-interactively for CI/scripts/pre-commit; stdin/stdout pipe like a Unix tool (`git log | claude -p "summarize"`). Output formats include `text`, `json`, `stream-json`; supports fan-out/batch patterns and permission flags.
- **Why it's a gamechanger:** The backbone of scripted automation — your Ralph loops already use headless, but `stream-json` output + fan-out patterns enable cleaner programmatic pipelines than parsing text.
- **Adopt:** `claude -p "/goal …" --output-format stream-json`; pipe stdin.
- **Status:** ✅ HAVE (Ralph uses it) / 🟡 PARTIAL (stream-json + fan-out patterns)

#### Claude Agent SDK — file-checkpointing, session-storage, tool-search, structured outputs, subagents
- **Source:** https://code.claude.com/docs/en/agent-sdk/overview ; .../file-checkpointing ; .../session-storage ; .../tool-search ; .../structured-outputs ; .../subagents
- **Category:** SDK (Python/TypeScript)
- **What it is:** The official SDK to build agents on the same engine as Claude Code, exposing **file checkpointing** (programmatic rewind), **external session storage** (persist sessions to your DB), **tool search** (scale to many tools by searching schemas on demand — same mechanism gating tools in this very session), **structured outputs**, custom tools, hooks, and subagents.
- **Why it's a gamechanger:** Your model-council/agentchattr/Ralph are custom Python harnesses — much of that is now first-party SDK. **Tool search** directly addresses your ~40-MCP-server token bloat (the MCP-reduction initiative in your memory): expose many tools, load schemas lazily. Session-storage enables durable multi-agent state you currently hand-roll in `.beads/`.
- **Adopt:** `pip install claude-agent-sdk` (or npm); use tool-search for many-tool setups; session-storage for durable state.
- **Status:** 🟡 PARTIAL (you have `agent-sdk-dev`/`claude-api` skills; tool-search + session-storage likely underexploited given your scale)

---

### I. Plugins, marketplaces & commands (you have many — verify depth)

#### Plugin loading from `.zip` and URL (`--plugin-dir`, `--plugin-url`)
- **Source:** https://code.claude.com/docs/en/whats-new/index (Week 19) ; https://code.claude.com/docs/en/plugins
- **Category:** Plugins (2026)
- **What it is:** `--plugin-dir` now accepts `.zip` archives and `--plugin-url` fetches a plugin archive for the current session — no marketplace install needed.
- **Why it's a gamechanger:** Try a plugin (or your own superpowers.zip — already in your inventory!) without permanent install; share plugins as a URL. Faster iteration on your own plugin dev.
- **Adopt:** `claude --plugin-dir ./my-plugin.zip` or `--plugin-url https://…`.
- **Status:** 🟡 PARTIAL (you have superpowers.zip; native zip/url loading flags likely unused)

#### Plugin dependencies & plugin hints
- **Source:** https://code.claude.com/docs/en/plugin-dependencies ; https://code.claude.com/docs/en/plugin-hints
- **Category:** Plugins (governance/discovery)
- **What it is:** `plugin-dependencies` constrains plugin dependency versions; `plugin-hints` lets a plugin recommend itself from your CLI.
- **Why it's a gamechanger:** With your large plugin set, version-constraining avoids drift; hints improve discoverability of your own ECC/metaswarm plugins.
- **Adopt:** declare dependency constraints in plugin manifest; add CLI hints.
- **Status:** 🟡 PARTIAL

#### Custom slash commands (`.claude/commands/*.md`, args, frontmatter)
- **Source:** https://code.claude.com/docs/en/commands ; https://code.claude.com/docs/en/agent-sdk/slash-commands
- **Category:** Commands (native)
- **What it is:** Markdown files in `.claude/commands/` (project) or `~/.claude/commands/` (user) become `/commands`, with argument substitution and frontmatter (allowed tools, model, description). Plugins ship commands too.
- **Why it's a gamechanger:** You have hundreds of plugin commands; the native per-project `.claude/commands/` is the lightweight way to codify *your own* repeatable prompts (e.g. your BC RE recipes) without authoring a full plugin.
- **Adopt:** create `.claude/commands/<name>.md` with `$ARGUMENTS`.
- **Status:** ✅ HAVE (via plugins) / 🟡 PARTIAL (hand-rolled project commands)

---

### J. Official Skills you likely DON'T have (anthropics/skills repo)

> Install: `/plugin marketplace add anthropics/skills` then `/plugin install document-skills@anthropic-agent-skills` and `/plugin install example-skills@anthropic-agent-skills`.
> Dedup note: you HAVE `pdf` ✅, `webapp-testing` ✅, `claude-api` ✅, `skill-creator` ✅ (plugin); you have `slides`/`spreadsheet`/`doc` which overlap `pptx`/`xlsx`/`docx` (verify same vs different).

#### web-artifacts-builder
- **Source:** https://github.com/anthropics/skills (skills/web-artifacts-builder)
- **Category:** Official skill (frontend)
- **What it is:** Tools for building elaborate multi-component claude.ai HTML artifacts with React, Tailwind, shadcn/ui — for complex artifacts needing state/routing/components.
- **Why it's a gamechanger:** Production-grade artifact scaffolding; complements your frontend-patterns/liquid-glass-design skills with the official shadcn pipeline.
- **Adopt:** install example-skills; invoke when building rich artifacts.
- **Status:** 🔴 NET-NEW-GAP

#### frontend-design
- **Source:** https://github.com/anthropics/skills (skills/frontend-design)
- **Category:** Official skill (frontend)
- **What it is:** Creates distinctive, production-grade frontend UIs that avoid generic AI aesthetics — for components, pages, dashboards, landing pages.
- **Why it's a gamechanger:** Directly serves your global web/design-quality.md "anti-template policy." This is Anthropic's official take on the exact rule you wrote.
- **Adopt:** install example-skills.
- **Status:** 🔴 NET-NEW-GAP (overlaps your design rules but is the official skill; you have `ui-ux-pro-max` not this)

#### canvas-design / algorithmic-art / theme-factory
- **Source:** https://github.com/anthropics/skills (skills/canvas-design, /algorithmic-art, /theme-factory)
- **Category:** Official skills (visual)
- **What it is:** `canvas-design` makes PNG/PDF posters & visual art via design philosophy; `algorithmic-art` does generative art (p5.js, flow fields, particle systems, seeded randomness); `theme-factory` applies 10 preset (or on-the-fly) color/font themes to slides/docs/HTML/reports.
- **Why it's a gamechanger:** `theme-factory` standardizes styling across your slides/docs output; `canvas-design`/`algorithmic-art` are net-new creative capabilities not in your stack.
- **Adopt:** install example-skills.
- **Status:** 🔴 NET-NEW-GAP

#### mcp-builder (official)
- **Source:** https://github.com/anthropics/skills (skills/mcp-builder)
- **Category:** Official skill (MCP)
- **What it is:** Anthropic's guide for building high-quality MCP servers in Python (FastMCP) or Node/TS (MCP SDK) with well-designed tools.
- **Why it's a gamechanger:** You have `mcp-server-dev`/`mcp-server-patterns` (third-party); the official mcp-builder is the canonical reference — worth diffing against your versions given you author many MCP servers.
- **Adopt:** install example-skills; compare to your mcp-server-patterns.
- **Status:** 🟡 PARTIAL (you have equivalents; official one is the authoritative source)

#### doc-coauthoring / internal-comms / brand-guidelines / slack-gif-creator
- **Source:** https://github.com/anthropics/skills (skills/doc-coauthoring, /internal-comms, /brand-guidelines, /slack-gif-creator)
- **Category:** Official skills (comms/docs)
- **What it is:** `doc-coauthoring` = structured workflow for co-writing specs/proposals/decision-docs; `internal-comms` = status reports/leadership updates/incident reports in company formats; `brand-guidelines` = applies Anthropic brand colors/typography; `slack-gif-creator` = animated GIFs for Slack.
- **Why it's a gamechanger:** `doc-coauthoring` is a rigorous spec/proposal workflow you don't have an official equivalent of; `internal-comms` covers incident reports (relevant to your runbook/deep-link ideas).
- **Adopt:** install example-skills.
- **Status:** 🔴 NET-NEW-GAP (doc-coauthoring, internal-comms, slack-gif-creator); brand-guidelines 🟡 (Anthropic-specific)

#### Skills as a system: model-invoked, `--skill`, Agent SDK skills, API Skills
- **Source:** https://code.claude.com/docs/en/skills ; https://code.claude.com/docs/en/agent-sdk/skills ; https://docs.claude.com/en/api/skills-guide
- **Category:** Skills (native mechanism)
- **What it is:** Skills are auto-loaded when relevant (model-invoked) or run explicitly; they exist at user/project/plugin scope, work in the Agent SDK, and via the **Claude API Skills** feature (create/version skills server-side). You can also publish skills through plugin marketplaces.
- **Why it's a gamechanger:** You manage ~350 skills via a hand-maintained manifest (per your memory). The **API Skills** path + SDK skills let you version and serve skills programmatically rather than file-copying to `~/.agents/skills` — directly relevant to your agent-skills-toolchain pain (5 stale dupes!).
- **Adopt:** read skills-guide.md; consider API-managed skills for the toolchain.
- **Status:** 🟡 PARTIAL (you operate skills heavily; API/SDK skill management likely underused)

---

### K. API features relevant to Claude Code (you have `claude-api` skill — verify depth)

#### Prompt caching (how Claude Code uses it)
- **Source:** https://code.claude.com/docs/en/prompt-caching ; https://docs.claude.com/en/docs/build-with-claude/prompt-caching
- **Category:** API / cost (native)
- **What it is:** Claude Code caches the system prompt, CLAUDE.md, tools, and conversation prefix; cache hits cut input cost dramatically. Output-style changes, tool changes, and big CLAUDE.md edits invalidate the cache (which is why those take effect after `/clear`).
- **Why it's a gamechanger:** Your enormous global CLAUDE.md + rules + ~40 MCP tool schemas are re-cached on every invalidation. Understanding cache breakpoints tells you why startup is slow/expensive across your many sessions — and that trimming/scoping CLAUDE.md and using tool-search pays off on cache, not just context.
- **Adopt:** minimize CLAUDE.md churn mid-session; scope rules; read prompt-caching.md. Your `claude-api` skill mandates caching — apply the same lens to CC config.
- **Status:** 🟡 PARTIAL (you know API caching; the CC-config implications are the gap)

#### Files API / Citations / Batch (Messages API features behind CC capabilities)
- **Source:** https://docs.claude.com/en/docs/build-with-claude/files ; .../citations ; .../batch-processing
- **Category:** API (native)
- **What it is:** Files API (upload/reuse documents across calls), Citations (grounded answers with source spans), Message Batches (50% cheaper async bulk processing).
- **Why it's a gamechanger:** Batch API is the cost-optimal path for your large fan-out/eval workloads (vs many live calls); Citations enforces the "cite sources + grade confidence" rigor your MEMORY demands; Files API avoids re-uploading the same RE artifacts.
- **Adopt:** use the Batch API for bulk/eval jobs; Citations for research outputs; via the SDK or your `claude-api` skill.
- **Status:** 🟡 PARTIAL (in `claude-api`/`openai-docs` skills; Batch for your eval harnesses likely underused)

---

### L. Misc native features worth a look

#### Computer use in the CLI (`/`-driven GUI control)
- **Source:** https://code.claude.com/docs/en/computer-use ; https://code.claude.com/docs/en/whats-new/index (Week 14)
- **Category:** GUI automation (research preview)
- **What it is:** Claude opens native apps, clicks through UI, and verifies changes from your terminal — for closing the loop on things only a GUI can verify. Runs on your real desktop (per-app permission prompts), not sandboxed.
- **Why it's a gamechanger:** Native GUI verification overlaps your Playwright/claude-in-chrome/cheat-engine GUI workflows — useful for verifying BlueStacks/Battle Cats UI state without a separate automation stack.
- **Adopt:** see computer-use.md (CLI); pairs with your RE work.
- **Status:** 🟡 PARTIAL (you have browser MCPs; native desktop computer-use is distinct)

#### `/team-onboarding` + `/autofix-pr`
- **Source:** https://code.claude.com/docs/en/whats-new/index (Week 15)
- **Category:** Workflow (2026)
- **What it is:** `/team-onboarding` packages your setup into a replayable guide; `/autofix-pr` turns on PR auto-fix from your terminal (Claude fixes review comments automatically).
- **Why it's a gamechanger:** `/team-onboarding` could capture your elaborate ECC/metaswarm setup as a shareable artifact; `/autofix-pr` automates the PR-comment loop your `handle-pr-comments`/`gh-address-comments` skills do manually.
- **Adopt:** `/team-onboarding`, `/autofix-pr`.
- **Status:** 🔴 NET-NEW-GAP

#### `claude project purge` + `.claude` directory hygiene
- **Source:** https://code.claude.com/docs/en/whats-new/index (Week 18) ; https://code.claude.com/docs/en/claude-directory
- **Category:** Maintenance (native)
- **What it is:** `claude project purge` cleans up local project state; the claude-directory doc maps everything under `.claude/`.
- **Why it's a gamechanger:** Your disk-cleanup memory flags Claude/codex session bloat on C:. `claude project purge` is the official cleanup; knowing the `.claude` layout helps you prune safely.
- **Adopt:** `claude project purge`; review claude-directory.md before deleting.
- **Status:** 🔴 NET-NEW-GAP (directly relevant to your documented C: drive bloat)

#### `claude --debug` / `/doctor` / debug-your-config
- **Source:** https://code.claude.com/docs/en/debug-your-config ; https://code.claude.com/docs/en/troubleshooting
- **Category:** Diagnostics (native)
- **What it is:** Tools to diagnose why settings/hooks/output-styles/MCP aren't taking effect, including settings-precedence resolution.
- **Why it's a gamechanger:** With your layered settings (user/project/local/managed) + ~40 MCP servers + many plugins, a precedence bug is likely. `debug-your-config` resolves "why isn't my hook firing / MCP connecting."
- **Adopt:** `claude --debug`; read debug-your-config.md; relevant to your Ralph headless `--setting-sources` finding.
- **Status:** 🟡 PARTIAL

---

### Summary: TOP 8 most likely underused by THIS power user

1. **`/effort` slider + `xhigh` (Opus 4.7)** — your MEMORY literally says "keep effort HIGH all session"; this is the native dial for that, and you've never named it. 🔴
2. **Sandboxed Bash (`/sandbox`) via WSL2 + Auto mode** — run autonomous Ralph loops safely *without* `--dangerously-skip-permissions` (which your own rules forbid); OS-enforced, not model-trusted. 🔴
3. **`/goal` (native completion-condition loop) + script Stop hooks** — the lightweight native Ralph, with an independent evaluator (no self-certifying). 🔴
4. **Agent view (`claude agents`) + `/batch`** — native background-session dashboard (you built agent-monitor for this) and 5–30-way worktree-isolated PR fan-out. 🔴
5. **Ultrareview (`/code-review ultra`) + Ultraplan** — managed multi-agent cloud review with *verified* findings and section-commentable cloud plans; replaces hand-spun review councils. 🔴
6. **Full hook event matrix + HTTP/prompt/`if` hooks** — you're PreToolUse-only; `SubagentStop` (gate self-certifying subagents), `PreCompact` (feed your `.beads/` recovery), `SessionStart`/`UserPromptSubmit`, and prompt/HTTP handler types are all unused. 🟡→🔴
7. **Agent SDK tool-search + session-storage** — directly attacks your ~40-MCP token bloat (lazy schema loading) and `.beads/` hand-rolled durable state; much of model-council/agentchattr is now first-party. 🟡
8. **Output styles (Proactive) + status line + `/usage`** — zero-config autonomy boost, live context/cost visibility for your "avoid last 20%" rule and concurrent-instance cost churn. 🔴

**Honorable mentions:** Channels (phone↔agent bridge vs agentchattr), Routines (machine-off cloud cron vs Ralph), `claude project purge` (your documented C: bloat), Deep links (your RE runbooks → clickable), `/powerup` (built-in feature discovery), official `frontend-design`/`doc-coauthoring`/`web-artifacts-builder` skills.

---

## 5.2 — Popular / essential MCP servers


> Research agent #2 of 7. Domain: the **popular/essential tier** of MCP servers (highest stars, most-used).
> Star counts are real, pulled via `gh api repos/OWNER/REPO --jq .stargazers_count` on **2026-05-28**.
> Status legend: ✅ HAVE · 🟡 PARTIAL (skill/plugin wrapper or related, not the canonical MCP server) · 🔴 NET-NEW-GAP.

### Dedup basis

User's registered MCP servers (INVENTORY.md line 13): `apify, binary-ninja-mcp, browserstack, cheatengine, chrome-devtools, codacy, codecov, codex_consult, context7, deepsource, digitalocean, docker, env, excel, figma, firecrawl, frida-mcp, ghidra-mcp, github, github_cli, hexstrike-ai, huggingface, ida-pro-mcp, instructions, integrations, linear, markitdown, mcp, mcp-graphql, memory, meta-tool, notion, options, pdf-reader, playwright, postgres, qlty, ralph-orchestrator, repomix, scrapegraph, semgrep, sentry, servers, sonarqube, tavily, vscode, workspace, x_codex`.

I grepped `~/.claude.json` and `~/.agents/agents.json` for slack, sequential/thinking, time, filesystem, brave, fetch, atlassian, jira, gmail, gdrive, vercel, azure, cloudflare, redis, mongo, neon, supabase, clickhouse, obsidian, stripe, grafana, datadog, perplexity — **none matched** (the lone "time" hit was `startup_timeout_sec`, not the time server). The cryptic names `env / instructions / integrations / mcp / options / servers / workspace` are internal config aliases and are **not** credited as covering any canonical popular server. Per task guidance, over-flagging gaps is the safer error.

> **Ecosystem note:** The `modelcontextprotocol/servers` monorepo (⭐86,394) was pruned in 2025. Its *active* reference set is now ~7 (filesystem, fetch, git, memory, sequential-thinking, time, everything). Older reference servers (Slack, brave-search, gdrive, sqlite, puppeteer, postgres, github, etc.) were moved to `modelcontextprotocol/servers-archived` (⭐266, **archived**) — for those, the live option is a vendor-official or community fork, noted per entry.

---

### A. Official core reference servers (`modelcontextprotocol/servers`, ⭐86,394)

These ship in the official monorepo and share its star count. They are the bedrock of almost every MCP setup. Source: https://github.com/modelcontextprotocol/servers

#### Filesystem (official)
- **Repo:** https://github.com/modelcontextprotocol/servers/tree/main/src/filesystem (part of ⭐86,394 monorepo)
- **Category:** dev / files
- **What it does:** Secure, sandboxed read/write/list/search/move operations over directories you explicitly allow-list, with configurable access controls.
- **Why it's a gamechanger:** The single most-installed MCP server. Gives any MCP client (Claude Desktop, Cursor, other agents) controlled file access without granting blanket shell — the canonical safe-file primitive. Claude Code already has native file tools, but other clients/agents in your fleet (model-council, agentchattr, Codex) benefit.
- **Adopt:** `claude mcp add filesystem -s user -- npx -y @modelcontextprotocol/server-filesystem "C:\Users\Prekzursil\source"`
- **Status:** 🔴 (not named in inventory; Claude Code has native files, but no MCP filesystem server registered for other clients)

#### Fetch (official)
- **Repo:** https://github.com/modelcontextprotocol/servers/tree/main/src/fetch (part of ⭐86,394 monorepo)
- **Category:** web / fetch
- **What it does:** Fetches a URL and converts the HTML to clean markdown for LLM consumption, with chunked reads for long pages.
- **Why it's a gamechanger:** The lightweight, dependency-free "read this page" primitive. You have firecrawl/tavily/scrapegraph for heavy scraping, but `fetch` is the zero-config baseline every client expects and is far cheaper for single-page reads.
- **Adopt:** `claude mcp add fetch -s user -- uvx mcp-server-fetch`
- **Status:** 🟡 (firecrawl/tavily/scrapegraph cover scraping; the canonical lightweight `fetch` server itself is not registered)

#### Git (official)
- **Repo:** https://github.com/modelcontextprotocol/servers/tree/main/src/git (part of ⭐86,394 monorepo)
- **Category:** dev / vcs
- **What it does:** Read, search, and manipulate a local Git repository (status, diff, log, commit, branch) as structured MCP tools.
- **Why it's a gamechanger:** Lets non-Claude-Code agents in your fleet do Git operations without a shell. Complements `github`/`github_cli` (which are remote/API) with **local repo** introspection.
- **Adopt:** `claude mcp add git -s user -- uvx mcp-server-git --repository "C:\Users\Prekzursil\source"`
- **Status:** 🟡 (you have github + github_cli for remote; local-git MCP server not registered — Claude Code uses native Bash git)

#### Sequential Thinking (official)
- **Repo:** https://github.com/modelcontextprotocol/servers/tree/main/src/sequentialthinking (part of ⭐86,394 monorepo)
- **Category:** reasoning / meta
- **What it does:** Exposes a structured "think in steps, revise, branch" scratchpad tool that lets the model decompose hard problems into explicit revisable thoughts.
- **Why it's a gamechanger:** One of the most popular servers overall; materially improves multi-step planning/debugging quality for clients without native extended-thinking. Useful inside your model-council/agentchattr seats (Codex/Antigravity) that lack Claude's thinking.
- **Adopt:** `claude mcp add sequential-thinking -s user -- npx -y @modelcontextprotocol/server-sequential-thinking`
- **Status:** 🔴 (not in inventory)

#### Time (official)
- **Repo:** https://github.com/modelcontextprotocol/servers/tree/main/src/time (part of ⭐86,394 monorepo)
- **Category:** utility / time
- **What it does:** Current time in any IANA timezone plus timezone conversion.
- **Why it's a gamechanger:** Cheap fix for the classic "LLM doesn't know what time it is / botches timezone math" failure. Tiny footprint, high utility for scheduling/cron/loop reasoning (you run Ralph loops + cron agents).
- **Adopt:** `claude mcp add time -s user -- uvx mcp-server-time --local-timezone "Europe/Bucharest"`
- **Status:** 🔴 (the "time" inventory hit was `startup_timeout_sec`, not this server)

#### Memory (official, knowledge-graph)
- **Repo:** https://github.com/modelcontextprotocol/servers/tree/main/src/memory (part of ⭐86,394 monorepo)
- **Category:** memory / knowledge
- **What it does:** Persistent knowledge-graph memory (entities, relations, observations) the model can read/write across sessions.
- **Why it's a gamechanger:** Cross-session recall without bespoke plumbing.
- **Adopt:** `claude mcp add memory -s user -- npx -y @modelcontextprotocol/server-memory`
- **Status:** ✅ (`memory` registered)

#### Everything (official, reference/test)
- **Repo:** https://github.com/modelcontextprotocol/servers/tree/main/src/everything (part of ⭐86,394 monorepo)
- **Category:** dev / reference
- **What it does:** A demo server exercising every MCP feature (prompts, tools, resources, sampling) — the canonical test target for MCP clients.
- **Why it's a gamechanger:** Not for daily use, but invaluable when you build/debug MCP clients (you run mcp-funnel, meta-tool, custom bridges). Pair with the Inspector below.
- **Adopt:** `claude mcp add everything -s user -- npx -y @modelcontextprotocol/server-everything`
- **Status:** 🔴 (dev-only; not registered)

---

### B. Browser / web automation

#### Microsoft Playwright MCP
- **Repo:** https://github.com/microsoft/playwright-mcp (⭐33,152)
- **Category:** browser
- **What it does:** Official Microsoft Playwright MCP — drives Chromium/Firefox/WebKit via the accessibility tree (no screenshots needed), with deterministic, fast browser control.
- **Why it's a gamechanger:** The de-facto standard browser server; a11y-tree approach is faster and more reliable than vision-based clicking.
- **Adopt:** `claude mcp add playwright -- npx -y @playwright/mcp@latest`
- **Status:** ✅ (`playwright` registered; you also have the playwright skill + plugin)

#### Chrome DevTools MCP
- **Repo:** https://github.com/ChromeDevTools/chrome-devtools-mcp (⭐42,106)
- **Category:** browser / debugging
- **What it does:** Google's official server exposing Chrome DevTools Protocol — performance traces, network/console inspection, Lighthouse, DOM, memory snapshots.
- **Why it's a gamechanger:** The go-to for performance/CWV debugging and network inspection inside an agent loop.
- **Adopt:** `claude mcp add chrome-devtools -- npx -y chrome-devtools-mcp@latest`
- **Status:** ✅ (`chrome-devtools` registered; plugin also present)

#### ExecuteAutomation Playwright MCP
- **Repo:** https://github.com/executeautomation/mcp-playwright (⭐5,534)
- **Category:** browser / testing
- **What it does:** Popular community Playwright server adding test-codegen, screenshots, and broader scripted-automation helpers beyond the MS baseline.
- **Why it's a gamechanger:** Useful when you want generated test scaffolding rather than just live driving; complementary to the MS server.
- **Adopt:** `claude mcp add playwright-ea -- npx -y @executeautomation/playwright-mcp-server`
- **Status:** 🟡 (MS Playwright + browserstack already cover browser; this specific community variant not registered)

#### Browserbase MCP (Stagehand)
- **Repo:** https://github.com/browserbase/mcp-server-browserbase (⭐3,359)
- **Category:** browser / cloud
- **What it does:** Drives **cloud** headless browsers via Browserbase + the Stagehand AI-automation framework (natural-language actions, session recording, stealth).
- **Why it's a gamechanger:** Offloads browser automation to managed cloud infra — no local Chromium, better for parallel/headless scraping at scale and bot-detected sites.
- **Adopt:** `claude mcp add browserbase -- npx -y @browserbasehq/mcp` (needs `BROWSERBASE_API_KEY`)
- **Status:** 🔴 (browserstack ≠ Browserbase; cloud-browser-via-MCP not registered)

#### AgentDesk Browser Tools MCP
- **Repo:** https://github.com/AgentDeskAI/browser-tools-mcp (⭐7,219)
- **Category:** browser / debugging
- **What it does:** Reads live browser logs (console, network, errors) and runs audits via a companion Chrome extension — feeds real browser state back to the agent.
- **Why it's a gamechanger:** Tight "agent watches my actual browser tab" loop for debugging running web apps; popular with Cursor users.
- **Adopt:** `claude mcp add browser-tools -- npx -y @agentdeskai/browser-tools-mcp@latest` (+ install the Chrome extension)
- **Status:** 🟡 (chrome-devtools covers most of this; this specific extension-based server not registered)

---

### C. Search / research

#### Exa MCP
- **Repo:** https://github.com/exa-labs/exa-mcp-server (⭐4,492)
- **Category:** search
- **What it does:** Official Exa server for neural/semantic web search, content crawling, and "find similar" — built for LLM-quality retrieval.
- **Why it's a gamechanger:** Best-in-class semantic search results vs keyword engines; great for deep-research agents.
- **Adopt:** `claude mcp add exa -- npx -y exa-mcp-server` (needs `EXA_API_KEY`)
- **Status:** 🟡 (you have the `exa-search` skill + ECC exa plugin tools, but **no standalone `exa` MCP server** in the registered list)

#### Firecrawl MCP
- **Repo:** https://github.com/mendableai/firecrawl-mcp-server (⭐6,413)
- **Category:** search / scraping
- **What it does:** Official Firecrawl server — scrape, crawl, map, and structured-extract entire sites into clean markdown/JSON.
- **Why it's a gamechanger:** Industrial-strength site crawling + extraction; handles JS, pagination, and schema extraction.
- **Adopt:** `claude mcp add firecrawl -- npx -y firecrawl-mcp` (needs `FIRECRAWL_API_KEY`)
- **Status:** ✅ (`firecrawl` registered; plugin + skills present)

#### Tavily MCP
- **Repo:** https://github.com/tavily-ai/tavily-mcp (⭐2,034)
- **Category:** search
- **What it does:** Production search server with real-time search, extract, map, and crawl tuned for agentic RAG.
- **Why it's a gamechanger:** Fast, citation-friendly search API purpose-built for agents.
- **Adopt:** `claude mcp add tavily -- npx -y tavily-mcp@latest` (needs `TAVILY_API_KEY`)
- **Status:** ✅ (`tavily` registered)

#### Perplexity Ask MCP
- **Repo:** https://github.com/ppl-ai/modelcontextprotocol (⭐2,241)
- **Category:** search / answer-engine
- **What it does:** Official Perplexity server (`perplexity-ask`) — sends queries to Sonar models and returns synthesized, web-grounded answers with citations.
- **Why it's a gamechanger:** Gives a second, independent web-grounded "answer engine" — strong for cross-checking research and getting cited summaries in one call.
- **Adopt:** `claude mcp add perplexity -- npx -y server-perplexity-ask` (needs `PERPLEXITY_API_KEY`)
- **Status:** 🔴 (not registered)

#### Brave Search MCP (official)
- **Repo:** https://github.com/brave/brave-search-mcp-server (⭐1,096)
- **Category:** search / privacy
- **What it does:** Brave's official server for independent web/news/image/local search via the Brave Search API (own index, privacy-respecting). Replaces the archived reference brave-search server.
- **Why it's a gamechanger:** Independent index (not Google/Bing reselling); generous free tier; good privacy posture for a default web-search primitive.
- **Adopt:** `claude mcp add brave-search -- npx -y @brave/brave-search-mcp-server` (needs `BRAVE_API_KEY`)
- **Status:** 🔴 (not registered)

---

### D. Databases / data

#### PostgreSQL
- **Repo:** https://github.com/modelcontextprotocol/servers-archived/tree/main/src/postgres (reference archived) / many community forks
- **Category:** database
- **What it does:** Query Postgres with schema introspection; modern forks (e.g. `@henkey/postgres-mcp-server`, crystaldba `postgres-mcp`) add health checks and safe write modes.
- **Why it's a gamechanger:** Direct DB Q&A and schema-aware querying from the agent.
- **Adopt:** `claude mcp add postgres -- npx -y @henkey/postgres-mcp-server --connection-string "$DATABASE_URL"`
- **Status:** ✅ (`postgres` registered)

#### MongoDB MCP (official)
- **Repo:** https://github.com/mongodb-js/mongodb-mcp-server (⭐1,038)
- **Category:** database / NoSQL
- **What it does:** Official MongoDB server — query/aggregate collections and run Atlas admin operations via natural language.
- **Why it's a gamechanger:** First-party NoSQL coverage with Atlas management; the standard for document-DB work.
- **Adopt:** `claude mcp add mongodb -- npx -y mongodb-mcp-server --connectionString "$MDB_URI"`
- **Status:** 🔴 (no NoSQL DB server registered)

#### Redis MCP (official)
- **Repo:** https://github.com/redis/mcp-redis (⭐515)
- **Category:** database / cache
- **What it does:** Official Redis server — natural-language interface to keys, hashes, streams, pub/sub, and vector search.
- **Why it's a gamechanger:** Inspect/operate caches and queues live; handy for debugging app state and rate-limit/session stores.
- **Adopt:** `claude mcp add redis -- uvx --from redis-mcp-server@latest redis-mcp-server --url redis://localhost:6379`
- **Status:** 🔴 (not registered)

#### Supabase MCP (official)
- **Repo:** https://github.com/supabase-community/supabase-mcp (⭐2,709)
- **Category:** database / BaaS
- **What it does:** Manage Supabase projects — run SQL, manage tables/migrations, branches, edge functions, and config from the agent.
- **Why it's a gamechanger:** Full Postgres-backed BaaS control loop; great for full-stack app work.
- **Adopt:** `claude mcp add supabase -- npx -y @supabase/mcp-server-supabase@latest --access-token "$SUPABASE_PAT"`
- **Status:** 🟡 (you have the **supabase plugin/skill**, but not the Supabase MCP server registered)

#### Neon MCP (official)
- **Repo:** https://github.com/neondatabase-labs/mcp-server-neon (⭐603)
- **Category:** database / serverless-postgres
- **What it does:** Manage Neon serverless Postgres — create projects/branches, run SQL, and do schema migrations via natural language.
- **Why it's a gamechanger:** Instant DB branching for preview/test environments controlled by the agent.
- **Adopt:** `claude mcp add neon -- npx -y @neondatabase/mcp-server-neon start "$NEON_API_KEY"`
- **Status:** 🔴 (not registered)

#### MCP Toolbox for Databases (Google, genai-toolbox)
- **Repo:** https://github.com/googleapis/genai-toolbox (⭐15,377)
- **Category:** database / multi-DB gateway
- **What it does:** Google's open-source MCP server fronting many databases (Postgres, MySQL, BigQuery, Spanner, AlloyDB, SQLite, etc.) with connection pooling, auth, and observability.
- **Why it's a gamechanger:** One battle-tested server for *all* your SQL backends instead of one server per DB — production-grade (pooling/authz), high-star, Google-backed.
- **Adopt:** Download the `toolbox` binary, write a `tools.yaml`, then `claude mcp add toolbox -- ./toolbox --tools-file tools.yaml --stdio`
- **Status:** 🔴 (not registered — strong single-server replacement for multiple DB gaps)

#### ClickHouse MCP (official)
- **Repo:** https://github.com/ClickHouse/mcp-clickhouse (⭐789)
- **Category:** database / OLAP
- **What it does:** Official ClickHouse server — run analytical SQL and explore schemas on ClickHouse / chDB.
- **Why it's a gamechanger:** You already have the `clickhouse-io` skill — the MCP server closes the loop for live OLAP querying.
- **Adopt:** `claude mcp add clickhouse -- uvx mcp-clickhouse` (env: `CLICKHOUSE_HOST/USER/PASSWORD`)
- **Status:** 🟡 (clickhouse-io **skill** present; no ClickHouse MCP server registered)

#### Elasticsearch MCP (official)
- **Repo:** https://github.com/elastic/mcp-server-elasticsearch (⭐666)
- **Category:** database / search
- **What it does:** Official Elastic server — query indices and explore mappings in Elasticsearch/ES|QL via natural language.
- **Why it's a gamechanger:** Live log/search-cluster querying from the agent — pairs well with observability work.
- **Adopt:** `claude mcp add elasticsearch -- npx -y @elastic/mcp-server-elasticsearch` (env: `ES_URL`, `ES_API_KEY`)
- **Status:** 🔴 (not registered)

---

### E. Productivity / collaboration

#### Notion MCP (official)
- **Repo:** https://github.com/makenotion/notion-mcp-server (⭐4,367)
- **Category:** productivity / docs
- **What it does:** Official Notion server — search, read, create, and update Notion pages/databases.
- **Why it's a gamechanger:** Two-way Notion automation from the agent.
- **Adopt:** `claude mcp add notion -- npx -y @notionhq/notion-mcp-server` (env: `NOTION_TOKEN`)
- **Status:** ✅ (`notion` registered; Notion plugin + 3 notion skills present)

#### Linear MCP (official, remote)
- **Repo:** https://linear.app/docs/mcp (official remote server) — community ref: https://github.com/jerhadf/linear-mcp-server
- **Category:** productivity / issues
- **What it does:** Manage Linear issues, projects, and cycles; the official server is a hosted remote MCP endpoint.
- **Why it's a gamechanger:** Issue-tracker automation inside the agent loop.
- **Adopt:** `claude mcp add --transport http linear https://mcp.linear.app/mcp`
- **Status:** ✅ (`linear` registered; linear skill present)

#### Atlassian MCP (Jira + Confluence) — community `mcp-atlassian`
- **Repo:** https://github.com/sooperset/mcp-atlassian (⭐5,287)
- **Category:** productivity / issues + wiki
- **What it does:** Most-popular community Atlassian server — Jira issue CRUD/JQL search + Confluence page read/write, supporting both Cloud and Server/Data Center.
- **Why it's a gamechanger:** No supported standalone Jira/Confluence MCP in your inventory; this is the highest-star option and covers DC (the official Atlassian Rovo remote MCP is Cloud-only).
- **Adopt:** `claude mcp add atlassian -- uvx mcp-atlassian` (env: `JIRA_URL`, `JIRA_API_TOKEN`, `CONFLUENCE_URL`, …) — or official Cloud remote: `claude mcp add --transport sse atlassian https://mcp.atlassian.com/v1/sse`
- **Status:** 🔴 (no Jira/Confluence server registered)

#### Slack MCP — community `slack-mcp-server`
- **Repo:** https://github.com/korotovsky/slack-mcp-server (⭐1,632)
- **Category:** productivity / chat
- **What it does:** Powerful Slack server — read channels/threads/DMs, post messages, search — with a no-admin-permissions stealth mode (works without installing a workspace app).
- **Why it's a gamechanger:** The original reference Slack server was archived; this is the leading live replacement. Lets agents triage and post to Slack.
- **Adopt:** `claude mcp add slack -- npx -y slack-mcp-server@latest` (env: `SLACK_MCP_XOXP_TOKEN` or browser tokens)
- **Status:** 🔴 (no Slack server registered — also flagged in task seed list)

#### Gmail MCP — community (Google Workspace)
- **Repo:** https://github.com/GongRzhe/Gmail-MCP-Server (⭐1,125, **archived**) → maintained alt: https://github.com/taylorwilsdon/google_workspace_mcp
- **Category:** productivity / email
- **What it does:** Send/search/read/label Gmail (and with the Workspace alt: Calendar, Drive, Docs) via OAuth.
- **Why it's a gamechanger:** Email + calendar automation; the Workspace alt is a single server covering Gmail/Calendar/Drive/Docs/Sheets — high leverage.
- **Adopt:** `claude mcp add google-workspace -- uvx workspace-mcp` (OAuth flow on first use)
- **Status:** 🔴 (no Gmail/Google-Workspace server registered)

#### Asana MCP (official remote)
- **Repo:** https://github.com/Asana/mcp (official remote endpoint) — community ref: https://github.com/roychri/mcp-server-asana (⭐139)
- **Category:** productivity / project-mgmt
- **What it does:** Manage Asana tasks, projects, and workspaces from the agent.
- **Why it's a gamechanger:** Project-management automation; official remote server needs no local install.
- **Adopt:** `claude mcp add --transport sse asana https://mcp.asana.com/sse`
- **Status:** 🔴 (not registered)

#### Discord MCP — community
- **Repo:** https://github.com/v-3/discordmcp (⭐204) / popular alt: https://github.com/SaseQ/discord-mcp
- **Category:** productivity / chat
- **What it does:** Read and send Discord messages, manage channels via a bot token.
- **Why it's a gamechanger:** Bridges agents into Discord communities (relevant given your multi-agent chat coordinator agentchattr).
- **Adopt:** `claude mcp add discord -- npx -y mcp-discord` (env: `DISCORD_TOKEN`)
- **Status:** 🔴 (not registered)

---

### F. Cloud / infra / deploy

#### AWS Labs MCP (official suite)
- **Repo:** https://github.com/awslabs/mcp (⭐9,145)
- **Category:** cloud / AWS
- **What it does:** Official AWS monorepo of 50+ MCP servers — Core, CDK, Terraform, Lambda, S3, DynamoDB, Cost Explorer, Bedrock KB, CloudWatch, docs, and more.
- **Why it's a gamechanger:** The authoritative way to operate/build on AWS from an agent; you have the `aws-serverless` + `deploy-on-aws` plugins but no AWS MCP server registered.
- **Adopt:** `claude mcp add aws-core -- uvx awslabs.core-mcp-server@latest` (add individual sub-servers as needed)
- **Status:** 🔴 (aws-serverless/deploy-on-aws are **plugins/skills**; AWS MCP servers not registered)

#### Cloudflare MCP (official suite)
- **Repo:** https://github.com/cloudflare/mcp-server-cloudflare (⭐3,790)
- **Category:** cloud / edge
- **What it does:** Official Cloudflare remote MCP servers — Workers, Pages, R2, KV, D1, DNS, Radar, observability, and bindings, deployed as hosted SSE endpoints.
- **Why it's a gamechanger:** Manage your entire Cloudflare edge stack conversationally; remote-hosted (no local install) with OAuth.
- **Adopt:** `claude mcp add --transport sse cloudflare-workers https://docs.mcp.cloudflare.com/sse` (and other CF endpoints)
- **Status:** 🔴 (you have the `cloudflare-deploy` skill; no Cloudflare MCP server registered)

#### Vercel MCP (official, remote)
- **Repo:** https://vercel.com/docs/mcp/vercel-mcp (official hosted) — announced 2025
- **Category:** cloud / deploy
- **What it does:** Official Vercel remote MCP — manage projects/deployments, inspect logs, and query Vercel docs from the agent.
- **Why it's a gamechanger:** Closes the deploy loop for Next.js/frontend work; OAuth, no local install.
- **Adopt:** `claude mcp add --transport http vercel https://mcp.vercel.com`
- **Status:** 🟡 (you have the `vercel-deploy` skill; no Vercel MCP server registered)

#### Azure MCP (official)
- **Repo:** https://github.com/Azure/azure-mcp (⭐1,214) — catalog: https://github.com/microsoft/mcp (⭐3,219)
- **Category:** cloud / Azure
- **What it does:** Official Azure server — operate Azure resources (Storage, Cosmos DB, Monitor/Log Analytics, AKS, Key Vault, RBAC) via natural language; wraps `az` CLI semantics.
- **Why it's a gamechanger:** You have a deep Azure skill set (azure-observability/postgres/rbac/storage/validate) — the MCP server gives live resource operations to match.
- **Adopt:** `claude mcp add azure -- npx -y @azure/mcp@latest server start` (uses your `az login` creds)
- **Status:** 🔴 (rich Azure **skills** present; no Azure MCP server registered)

#### DigitalOcean MCP (official)
- **Repo:** https://github.com/digitalocean/digitalocean-mcp (official) — also `doctl mcp`
- **Category:** cloud / VPS
- **What it does:** Manage DigitalOcean droplets, App Platform, databases, and Spaces from the agent.
- **Why it's a gamechanger:** Conversational control of your DO infra.
- **Adopt:** `claude mcp add digitalocean -- npx -y @digitalocean/mcp` (env: `DIGITALOCEAN_API_TOKEN`)
- **Status:** ✅ (`digitalocean` registered; doctl skill present)

#### Terraform MCP (official, HashiCorp)
- **Repo:** https://github.com/hashicorp/terraform-mcp-server (⭐1,384)
- **Category:** cloud / IaC
- **What it does:** Official HashiCorp server — search the Terraform Registry for providers/modules and surface usage/docs to the agent while authoring IaC.
- **Why it's a gamechanger:** Eliminates guesswork on provider resource args/versions when writing Terraform; authoritative registry data.
- **Adopt:** `claude mcp add terraform -- docker run -i --rm hashicorp/terraform-mcp-server`
- **Status:** 🔴 (not registered)

#### Docker MCP (Docker Hub / containers)
- **Repo:** https://github.com/docker/mcp-servers (Docker MCP Catalog & Toolkit) / community `mcp-server-docker`
- **Category:** cloud / containers
- **What it does:** Manage containers, images, volumes, and compose stacks; Docker's official MCP Toolkit also acts as a gateway/catalog for other servers.
- **Why it's a gamechanger:** Conversational container ops + a one-stop secure gateway to run many MCP servers in isolation.
- **Adopt:** `claude mcp add docker -- uvx docker-mcp` (or enable Docker Desktop's MCP Toolkit)
- **Status:** ✅ (`docker` registered; docker-cli + docker-patterns skills present)

---

### G. Observability / quality / security

#### Sentry MCP (official)
- **Repo:** https://github.com/getsentry/sentry-mcp (⭐706)
- **Category:** observability / errors
- **What it does:** Official Sentry server (remote + stdio) — query issues/events, inspect stack traces, and trigger Seer AI root-cause analysis.
- **Why it's a gamechanger:** Pull production error context straight into the debugging loop.
- **Adopt:** `claude mcp add --transport http sentry https://mcp.sentry.dev/mcp`
- **Status:** ✅ (`sentry` registered; sentry plugin present)

#### Grafana MCP (official)
- **Repo:** https://github.com/grafana/mcp-grafana (⭐3,063)
- **Category:** observability / dashboards
- **What it does:** Official Grafana server — query dashboards, Prometheus/Loki data, alerts, and incidents; can render panels.
- **Why it's a gamechanger:** Lets the agent read metrics/logs and reason over live observability data — strong complement to Sentry (errors) for full-stack diagnosis.
- **Adopt:** `claude mcp add grafana -- npx -y @grafana/mcp-grafana` (env: `GRAFANA_URL`, `GRAFANA_API_KEY`)
- **Status:** 🔴 (not registered)

#### Snyk MCP (official security)
- **Repo:** https://github.com/snyk/snyk-ls (⭐80; ships the MCP server) — docs: https://docs.snyk.io
- **Category:** security / SCA
- **What it does:** Official Snyk server — run SCA/SAST/container/IaC scans and surface vulnerability + license findings to the agent.
- **Why it's a gamechanger:** Adds dependency/vuln scanning to your quality stack (you already have semgrep/codacy/sonarqube/deepsource for SAST, but no SCA/dependency-vuln MCP).
- **Adopt:** `claude mcp add snyk -- snyk mcp -t stdio` (requires Snyk CLI + `snyk auth`)
- **Status:** 🔴 (SAST covered; no SCA/dependency-vuln MCP server registered)

---

### H. Knowledge / docs / files / utility

#### Context7 (Upstash)
- **Repo:** https://github.com/upstash/context7 (⭐56,289)
- **Category:** docs / knowledge
- **What it does:** Fetches version-accurate, up-to-date library/framework documentation and code examples on demand.
- **Why it's a gamechanger:** Kills hallucinated/outdated API usage — one of the highest-star MCP projects.
- **Adopt:** `claude mcp add context7 -- npx -y @upstash/context7-mcp`
- **Status:** ✅ (`context7` registered; plugin present)

#### MarkItDown MCP (Microsoft)
- **Repo:** https://github.com/microsoft/markitdown (tree/main/packages/markitdown-mcp) — MarkItDown ⭐ large (Microsoft)
- **Category:** files / conversion
- **What it does:** Converts PDF/Office/HTML/images/audio into clean markdown for LLMs.
- **Why it's a gamechanger:** Universal "turn any document into LLM-readable text" primitive.
- **Adopt:** `claude mcp add markitdown -- uvx markitdown-mcp`
- **Status:** ✅ (`markitdown` registered)

#### Markdownify MCP
- **Repo:** https://github.com/zcaceres/markdownify-mcp (⭐2,703)
- **Category:** files / conversion
- **What it does:** Community server converting many file types and web content (incl. YouTube transcripts, Bing results) to markdown.
- **Why it's a gamechanger:** Overlaps MarkItDown but adds web/media-to-markdown paths (e.g. transcripts).
- **Adopt:** `claude mcp add markdownify -- npx -y @zcaceres/markdownify-mcp`
- **Status:** 🟡 (markitdown covers core conversion; this adds extra sources — optional)

#### Obsidian MCP — community `mcp-obsidian`
- **Repo:** https://github.com/MarkusPfundstein/mcp-obsidian (⭐3,796)
- **Category:** knowledge / notes
- **What it does:** Read/search/append to an Obsidian vault via the Local REST API plugin.
- **Why it's a gamechanger:** Lets the agent treat your personal knowledge vault as a read/write knowledge base — strong fit for your heavy auto-memory + knowledge-capture workflows.
- **Adopt:** `claude mcp add obsidian -- npx -y obsidian-mcp` (requires Obsidian Local REST API plugin + key)
- **Status:** 🔴 (not registered)

#### Stripe MCP (Agent Toolkit)
- **Repo:** https://github.com/stripe/agent-toolkit (⭐1,575)
- **Category:** payments / business
- **What it does:** Official Stripe server — create/manage customers, products, prices, payment links, invoices, and search docs.
- **Why it's a gamechanger:** Programmatic payments/billing ops from the agent — the standard for monetization workflows.
- **Adopt:** `claude mcp add stripe -- npx -y @stripe/mcp --tools=all` (env: `STRIPE_SECRET_KEY`)
- **Status:** 🔴 (not registered)

#### Apify MCP
- **Repo:** https://github.com/apify/actors-mcp-server (⭐1,283)
- **Category:** scraping / automation
- **What it does:** Run any of 6,000+ Apify Actors (scrapers/automations) and retrieve dataset results via MCP.
- **Why it's a gamechanger:** Massive prebuilt-scraper marketplace behind one server.
- **Adopt:** `claude mcp add apify -- npx -y @apify/actors-mcp-server` (env: `APIFY_TOKEN`)
- **Status:** ✅ (`apify` registered)

#### Repomix MCP
- **Repo:** https://github.com/yamadashy/repomix (ships MCP) — Repomix ⭐ large
- **Category:** dev / context-packing
- **What it does:** Packs an entire repo (or remote repo) into a single AI-friendly, token-counted file for whole-codebase reasoning.
- **Why it's a gamechanger:** "Give the model the whole repo at once" in one call.
- **Adopt:** `claude mcp add repomix -- npx -y repomix --mcp`
- **Status:** ✅ (`repomix` registered; repomix skill present)

#### HuggingFace MCP (official)
- **Repo:** https://github.com/evalstate/hf-mcp-server (official HF Hub server) — hub: huggingface.co/mcp
- **Category:** ML / models
- **What it does:** Search models/datasets/spaces, read model cards, and run Gradio-app tools from the HF Hub.
- **Why it's a gamechanger:** Direct pipeline into the open-model ecosystem.
- **Adopt:** `claude mcp add --transport http huggingface https://huggingface.co/mcp` (HF token for private)
- **Status:** ✅ (`huggingface` registered; huggingface-skills plugin present)

---

### I. Visualization / design / dev-tooling

#### Figma Context MCP (Framelink)
- **Repo:** https://github.com/GLips/Figma-Context-MCP (⭐14,899)
- **Category:** design / dev
- **What it does:** Feeds Figma layout/design data to coding agents for accurate design-to-code generation.
- **Why it's a gamechanger:** Most-popular Figma server; dramatically improves UI-from-design fidelity vs screenshots.
- **Adopt:** `claude mcp add figma -- npx -y figma-developer-mcp --stdio` (env: `FIGMA_API_KEY`)
- **Status:** ✅ (`figma` registered; figma plugin present — note: you may have Figma's official Dev Mode server; Framelink is the high-star community alt)

#### AntV MCP Server Chart
- **Repo:** https://github.com/antvis/mcp-server-chart (⭐4,108)
- **Category:** visualization
- **What it does:** Generates 25+ chart types (line, bar, sankey, mind-map, fishbone, flowchart, etc.) as images/specs from data.
- **Why it's a gamechanger:** Turns the agent's analysis into real charts/diagrams without a frontend — great for reports and dashboards.
- **Adopt:** `claude mcp add antv-chart -- npx -y @antv/mcp-server-chart`
- **Status:** 🔴 (not registered)

#### MCP Inspector (official dev tool)
- **Repo:** https://github.com/modelcontextprotocol/inspector (⭐9,903)
- **Category:** dev / MCP tooling
- **What it does:** Visual GUI + CLI to connect to, test, and debug any MCP server (list tools/resources/prompts, invoke them, inspect transport).
- **Why it's a gamechanger:** Essential when you build/maintain MCP servers and bridges (mcp-funnel, meta-tool, prekzursil-local-mcp). Not a "server" you register but the standard companion tool.
- **Adopt:** `npx -y @modelcontextprotocol/inspector` (run on demand; not added via `claude mcp add`)
- **Status:** 🔴 (dev tooling; worth having for your MCP-authoring work)

#### Excel MCP
- **Repo:** https://github.com/haris-musa/excel-mcp-server (popular) / community variants
- **Category:** files / spreadsheets
- **What it does:** Read/write/format Excel workbooks (formulas, charts, pivot tables) without Excel installed.
- **Why it's a gamechanger:** Full spreadsheet manipulation from the agent.
- **Adopt:** `claude mcp add excel -- uvx excel-mcp-server stdio`
- **Status:** ✅ (`excel` registered; spreadsheet skill present)

#### Code-quality servers (Codacy / SonarQube / DeepSource / Semgrep)
- **Repos:** Codacy https://github.com/codacy/codacy-mcp-server · SonarQube https://github.com/SonarSource/sonarqube-mcp-server · DeepSource (MCP) · Semgrep https://github.com/semgrep/mcp
- **Category:** quality / SAST
- **What they do:** Surface static-analysis findings, security hotspots, and metrics from each platform into the agent.
- **Why it's a gamechanger:** Closes the "scan → read findings → fix" loop across four platforms; you cross-reference them via a code-quality-auditor subagent.
- **Adopt:** already registered.
- **Status:** ✅ (`codacy`, `sonarqube`, `deepsource`, `semgrep`, `qlty`, `codecov` all registered)

---

### Coverage summary

- **✅ HAVE:** memory, playwright, chrome-devtools, firecrawl, tavily, postgres, notion, linear, digitalocean, docker, sentry, context7, markitdown, apify, repomix, huggingface, figma, excel, codacy, sonarqube, deepsource, semgrep, qlty, codecov, github, github_cli, browserstack, scrapegraph + RE stack (binary-ninja, cheatengine, frida, ghidra, hexstrike, ida-pro).
- **🟡 PARTIAL (skill/plugin only, or related variant — no canonical MCP server):** fetch, git, exa, supabase, clickhouse, vercel, markdownify, playwright-ea, browser-tools.
- **🔴 NET-NEW GAP:** filesystem, sequential-thinking, time, everything, browserbase, perplexity, brave-search, mongodb, redis, neon, genai-toolbox (multi-DB), elasticsearch, atlassian (Jira/Confluence), slack, gmail/google-workspace, asana, discord, awslabs, cloudflare, azure, terraform, grafana, snyk, obsidian, stripe, antv-chart, mcp-inspector.

Total servers covered: **~58**.

---

## 5.3 — Niche / specialized MCP servers + directories


Research agent #3 of 7. Domain: niche/specialized/hidden-gem MCP servers and the best discovery directories. Generated 2026-05-28. Year context: 2026.

**Dedup baseline** (from INVENTORY.md — already owned, excluded or flagged): frida, ghidra-mcp, ida-pro-mcp, binary-ninja-mcp, hexstrike-ai, cheatengine, semgrep, codacy, sonarqube, deepsource, qlty, apify, scrapegraph, firecrawl, tavily, playwright, chrome-devtools, browserstack, context7, repomix, markitdown, pdf-reader, excel, memory (basic KG), postgres, mcp-graphql, github, linear, notion, sentry, huggingface, docker, digitalocean, codecov. They also run **mcp-funnel** as a gateway/proxy (load-bearing for token reduction) — so gateway picks below are PARTIAL overlaps, listed as alternatives only.

Status legend: ✅ HAVE-equivalent · 🟡 PARTIAL (overlaps something owned) · 🔴 NET-NEW-GAP.

Verification: every entry below was returned by live search with a real GitHub/registry URL. Star counts (⭐) shown where the search surfaced them. Items marked ⚠️ unverified had thin signals (0–2 stars, single-author, very recent) — real repos, but maturity is uncertain; treat as "evaluate before adopting."

---

### Best MCP directories to browse (start here)

Sourced from 2026 comparison guides (truefoundry, automationswitch, studiomeyer, dibi8, dynomapper).

#### Glama — glama.ai/mcp/servers
**URL** https://glama.ai/mcp/servers · **Category** Directory (largest + security-scanned)
**What it does** ~26,000 servers (largest volume), every server maintainer-verified, continuously rebuilt, scored for quality + safety. Has an in-browser inspector, **tool-level search** (search across all servers' tools, not just server names), and an API gateway with call logging + per-tool access control.
**Why gamechanger** The tool-level search is the killer feature for a power user — find a specific capability across 184k indexed tools. Security scoring helps vet before install.
**Adopt** Primary browse target. Use tool-search for capability hunts. **Status** 🔴

#### PulseMCP — pulsemcp.com
**URL** https://www.pulsemcp.com · **Category** Directory (hand-reviewed, freshest)
**What it does** ~11,800+ servers, hand-reviewed daily by the founder since MCP launch week. One-click install for Claude Desktop/Cursor/VS Code. Co-maintainer of the official registry.
**Why gamechanger** Highest signal-to-noise; human curation means less spam than auto-indexed dirs. Best for "what's actually good and new this week."
**Adopt** Weekly skim for new releases. **Status** 🔴

#### Smithery — smithery.ai
**URL** https://smithery.ai · **Category** Registry + hosted runtime + CLI installer
**What it does** ~7,000 servers with an app-store UX, strong search, `smithery` CLI to install/manage without editing JSON, and hosted remote-server option.
**Why gamechanger** The CLI removes config-file friction; hosted runtime lets you try servers without local installs.
**Adopt** Use the CLI for fast install/trial. **Status** 🔴

#### MCP.so — mcp.so
**URL** https://mcp.so · **Category** Directory (largest raw count, third-party heavy)
**What it does** ~20,000+ community-submitted servers; best coverage of unofficial/third-party/regional servers others miss.
**Why gamechanger** Catches long-tail and non-English servers absent from curated lists.
**Adopt** Exhaustive search when curated dirs come up empty. **Status** 🔴

#### Official MCP Registry — registry.modelcontextprotocol.io
**URL** https://registry.modelcontextprotocol.io · **Category** Metaregistry (machine-readable)
**What it does** Canonical metadata index backed by Anthropic + GitHub + PulseMCP + Microsoft. Metadata only (code lives on npm/PyPI/Docker). REST API + OpenAPI spec. Still preview.
**Why gamechanger** The programmatic source of truth — good for scripting discovery or building your own gallery, not casual browsing.
**Adopt** Wire into automation/agent discovery flows. **Status** 🔴

#### punkpeye/awesome-mcp-servers
**URL** https://github.com/punkpeye/awesome-mcp-servers · **Category** Curated GitHub list (⭐ ~87k)
**What it does** The de-facto community catalog, ~40 categories, maintainer-ordered (not star-ordered). Ctrl-F your domain.
**Why gamechanger** Fastest "known-good things to copy into config" reference.
**Adopt** Bookmark; grep by domain. **Status** 🔴

#### rdmgator12/awesome-claude-connectors  *(your task-specified dir — verified)*
**URL** https://github.com/rdmgator12/awesome-claude-connectors (⭐ 20, updated 2026-05-26) · **Category** Curated list (official Anthropic Connectors mirror)
**What it does** Directory of all **343 verified** integrations in Anthropic's official Claude Connectors Directory, organized by category with use cases.
**Why gamechanger** These are the "blessed" connectors — first-party-vetted, work in Claude.ai/Desktop connectors UI out of the box.
**Adopt** Cross-check here for any commercial SaaS connector before hunting GitHub. **Status** 🔴

---

### Reverse Engineering / Binary Analysis (multi-tool labs — beyond your single-tool wrappers)

You own individual IDA/Ghidra/BinaryNinja/CheatEngine/HexStrike wrappers. The gap is **all-in-one RE/malware labs** and **symbolic-execution/CTF** orchestration.

#### Arkana
**Repo** https://github.com/JameZUK/Arkana (⭐ 18) · **Category** RE / malware lab
**What it does** Single MCP server exposing ~260 analysis tools: angr symbolic execution + decompilation, interactive step-debugging, Binary Refinery's 200+ data transforms, YARA/capa/FLOSS/PEiD signatures, Qiling/Speakeasy emulation, .NET/Go/Rust analysis + .NET deobfuscation, Frida script gen, cross-binary function similarity, VirusTotal, MITRE ATT&CK mapping, IOC extraction, real-time web dashboard. PE/ELF/Mach-O/.NET/Go/Rust/shellcode.
**Why gamechanger** This is "an entire malware lab behind one prompt" — adds angr/Qiling/capa/FLOSS/Binary-Refinery that your IDA-MCP set lacks, with answer caching. Built explicitly for Claude Code.
**Adopt** Add for malware triage + symbolic execution; complements (doesn't replace) IDA. **Status** 🔴

#### rbinmcp (Rogue Binary MCP)
**Repo** https://github.com/kirkderp/rbinmcp · **Category** RE / triage (Docker)
**What it does** Docker-packaged lab bundling radare2, Ghidra, ILSpy, binutils + Rust-backed views behind one server. Compact "cheap-first, heavy-on-demand" responses; cache-backed Ghidra imports/r2 sessions; bounded outputs for long results. Native PE/ELF/Mach-O/firmware/diffs + managed .NET.
**Why gamechanger** Solves the #1 RE-MCP pain: dumping whole projects into context. Token-economical triage→drill-down flow — directly aligned with your token-reduction harness. .NET (ILSpy) coverage you don't have.
**Adopt** Strong default for "unknown binary" triage. **Status** 🔴 ⚠️ unverified (recent, low stars)

#### Reversecore_MCP
**Repo** https://github.com/sjkim1127/Reversecore_MCP (⭐ 54) · **Category** RE / security (Docker)
**What it does** Security-first server orchestrating Ghidra + Radare2 + YARA for automated RE/binary analysis via natural language. Docker, MIT, 39 releases (actively maintained), Win/macOS/Linux configs.
**Why gamechanger** Most-maintained of the multi-tool RE servers; YARA integration + security sandboxing. Good middle ground if Arkana is too heavy.
**Adopt** Evaluate vs rbinmcp; pick one as the "RE lab." **Status** 🔴

#### binary-mcp (Ghidra + x64dbg + WinDbg)
**Repo** https://github.com/Sarks0/binary-mcp · **Category** RE / debugging (Windows-strong)
**What it does** Static (Ghidra + ILSpyCmd for .NET) + user-mode debugging (x64dbg: breakpoints/tracing/memory) + **kernel debugging (WinDbg/KD via Pybag COM)** for driver/IOCTL/crash-dump analysis. SHA256 caching (30–120x), session persistence, 100+ Windows API + crypto-constant patterns.
**Why gamechanger** WinDbg kernel debugging over MCP is rare and Windows-native — pairs with your windbg-command-cookbook skill. You have an x64dbg *skill* but not an MCP server.
**Adopt** Add for Windows driver/kernel RE. **Status** 🔴

#### x64dbg_mcp
**Repo** https://github.com/bromoket/x64dbg_mcp (⭐ 38) · **Category** Dynamic RE (x64dbg)
**What it does** C++ plugin inside x64dbg exposing 151 REST endpoints (stepping, breakpoints, memory, disasm, tracing, **anti-debug bypasses**, CFG analysis, PE dumping) via 23 Zod-validated mega-tools over a TS MCP server.
**Why gamechanger** Turns your x64dbg into a fully AI-drivable debugger with anti-debug bypass — fills the dynamic-analysis gap (your CheatEngine MCP is memory-scan focused).
**Adopt** Add if you do x64dbg work regularly. **Status** 🔴

#### KadeMCP (CTF solver)
**Repo** https://github.com/orgito1015/KadeMCP · **Category** CTF / security all-rounder
**What it does** Turns Claude into a hands-on CTF solver: disassemble, checksec, run pwntools exploits, crack hashes, XOR brute-force, frequency analysis, web fuzzing (SQLi/LFI), steganography (steghide/zsteg/outguess), binwalk, pcap analysis (tshark), EXIF/metadata carving.
**Why gamechanger** One server covering pwn+crypto+web+forensics+stego — the breadth a CTF player wants without juggling tools. Nothing in your inventory targets CTF.
**Adopt** Add for CTF / quick forensic triage. **Status** 🔴 ⚠️ unverified (recent)

#### pwn-mcp
**Repo** https://github.com/polarisxb/pwn-mcp · **Category** CTF pwn (safety-first)
**What it does** Guides CTF pwn workflows: binary protections (NX/PIE/RELRO/Canary), PLT/GOT, controlled crashes w/ GDB, cyclic-pattern offset calc, pwntools template generation (TODO scaffolds, not weaponized), session persistence. Clean hexagonal arch (rizin/gdb adapters).
**Why gamechanger** Educational, structured pwn scaffolding — generates exploit templates you finish, lower-risk than auto-exploit tools.
**Adopt** Pair with KadeMCP for binary-exploitation practice. **Status** 🔴

#### jtsylve/ida-mcp (idalib headless)
**Repo** https://github.com/jtsylve/ida-mcp · **Category** RE (IDA, headless)
**What it does** Headless IDA Pro 9+ MCP via **idalib** (no GUI needed), supervisor/worker arch for **multiple simultaneous databases**. List/decompile/search/read-bytes.
**Why gamechanger** Your ida-pro-mcp likely drives the GUI; this runs IDA as a library headlessly + multi-DB — better for batch/automation/CI RE. 🟡 overlaps ida-pro-mcp but different (headless multi-DB).
**Adopt** Consider for automated/batch IDA pipelines. **Status** 🟡

---

### OSINT / Pentest / Recon (NET-NEW domain — you have none)

#### Tengu
**Repo** https://github.com/whatthefinemanual/tengu · **Category** Pentest copilot
**What it does** Orchestrates ~80 security tools (Nmap, Metasploit, SQLMap, Nuclei, Hydra, ZAP) with safety controls: allowlist, rate limiting, audit logs, human-in-the-loop for destructive actions. 35 pre-built workflows (full pentest, web app, AD, cloud), 20 resources (OWASP Top 10, MITRE ATT&CK, PTES checklists), auto MD/HTML/PDF reports, optional Tor/SOCKS5 stealth layer.
**Why gamechanger** The safety architecture (allowlist + HITL + audit) makes it the responsible choice for an AI pentest copilot. Auto-reporting + methodology resources = consultant-grade.
**Adopt** Top pentest pick if you do authorized security testing. **Status** 🔴

#### badchars/osint-mcp
**Repo** https://github.com/badchars/osint-mcp · **Category** OSINT (passive, correlation)
**What it does** 37 tools across 12 sources (Shodan, VirusTotal, Censys, SecurityTrails, crt.sh, BGP, Wayback, GeoIP, DNS, WHOIS). Agent queries all sources **in parallel**, correlates, scores risk. 21 tools free, 16 more with optional keys.
**Why gamechanger** The reasoning-across-sources model ("this Shodan IP also appears in Censys with an expired cert") is what separates it from single-source tools. Mostly passive = safer.
**Adopt** Best pure-OSINT pick for attack-surface mapping. **Status** 🔴

#### pentest-osint-mcp-server (Kali Docker)
**Repo** https://github.com/Hackerobi/pentest-osint-mcp-server · **Category** OSINT/recon (Docker)
**What it does** 25+ OSINT tools on Kali Docker: Sherlock, Maigret, Holehe, theHarvester, SpiderFoot, recon-ng, Nmap, Shodan, VirusTotal, dnstwist, subfinder. One-command chains ("full passive recon on target.com").
**Why gamechanger** Username/email enumeration (Sherlock/Maigret/Holehe) + breach checks that badchars lacks; one-command recon chains.
**Adopt** Add for people/identity OSINT. **Status** 🔴

#### shodan-mcp (Vorota AI)
**Repo** https://github.com/Vorota-ai/shodan-mcp · **Category** OSINT (focused, Shodan)
**What it does** 20 Shodan tools: IP recon, device search, CVE/CPE intel, DNS, honeypot detection. 4 tools work with no API key. Structured Pydantic output. (Sister: Vorota-ai/nmap-mcp.)
**Why gamechanger** Clean focused Shodan integration if you don't want a whole Kali container; honeypot scoring is a nice touch.
**Adopt** Lightweight alternative to the big suites. **Status** 🔴

---

### DFIR / Malware / Forensics (NET-NEW; you have Volatility *skill* only)

#### mulder
**Repo** https://github.com/calebevans/mulder · **Category** DFIR (case management)
**What it does** 80+ forensic tools (Volatility 3, Sleuthkit, Plaso, Hayabusa, YARA, network capture, mobile) as MCP calls. Creates investigation **cases**, indexes evidence into per-case SQLite with FTS5 search, provenance-tracked findings, audit log, parallel extraction, generates reports (narrative + IOCs + MITRE ATT&CK). Apache-2.0.
**Why gamechanger** Case + provenance + audit structure turns ad-hoc forensics into a repeatable, defensible workflow. You have a Volatility skill but no case-management/timeline/evidence-indexing layer.
**Adopt** Strong DFIR pick. **Status** 🔴

#### mem_forensics-mcp
**Repo** https://github.com/x746b/mem_forensics-mcp (⭐ 4) · **Category** Memory forensics (tiered)
**What it does** 3-tier engine: Tier-1 Rust (fast pslist/malfind/netscan), Tier-2 Python analyzers (DKOM/anomaly/C2/credentials/YARA/VT), Tier-3 full Volatility3 (any plugin). `memory_full_triage` does end-to-end auto investigation.
**Why gamechanger** Rust speed for common ops + Vol3 completeness for the rest = fast triage without losing coverage. Pairs with your volatility-3 skill.
**Adopt** Add for memory-dump analysis. **Status** 🔴 ⚠️ unverified (low stars)

#### Volatility_MCP (timeout-proof)
**Repo** https://github.com/raviesheth2608/Volatility_MCP · **Category** Memory forensics (Windows)
**What it does** Vol3 MCP with a **background job engine** so 30–60 min scans don't hit Claude's tool timeout. All major Vol3 plugins (malfind, netscan, autoruns, rootkit, YARA). Windows-native.
**Why gamechanger** The timeout-proofing is the specific thing that breaks naive Vol3 servers on big dumps — and it's Windows-tested (your platform).
**Adopt** Use if running long Vol3 scans on Windows. **Status** 🔴 ⚠️ unverified

#### Malware-Analysis-MCP-Server
**Repo** https://github.com/SaeidSec/Malware-Analysis-MCP-Server · **Category** Threat intel / malware
**What it does** MalwareBazaar + VirusTotal + Telegram threat intel; IOC extraction with defang/refang; YARA template generation; bulk hash checks; path-traversal-guarded local file hashing.
**Why gamechanger** Defensive threat-intel + safe IOC sharing (defang) — complements RE labs with the "is this known-bad?" lookup layer.
**Adopt** Add alongside an RE lab. **Status** 🔴 ⚠️ unverified

#### forensics-utils-mcp-server
**Repo** https://github.com/jus1-c/forensics-utils-mcp-server · **Category** Forensics (browser artifacts)
**What it does** Deep Chromium + Firefox artifact parsing (history, cookies, logins+decryption, IndexedDB, cache, extensions), VirusTotal v3, Detect-It-Easy, Binwalk firmware extraction, EXIF/strings/hashing.
**Why gamechanger** Browser-artifact + login-decryption parsing is uniquely useful and absent from the memory-focused tools.
**Adopt** Niche; add for browser-forensics cases. **Status** 🔴 ⚠️ unverified

---

### Knowledge & Memory Graphs (your `memory` MCP is the basic Anthropic KG — these are richer)

#### obsidian-mcp (yanxue06 — graph-aware)
**Repo** https://github.com/yanxue06/obsidian-mcp · **Category** Knowledge graph (Obsidian)
**What it does** 25 typed tools treating an Obsidian vault as a real graph: `get_note` returns content+backlinks+forward-links+tags+frontmatter in one call; `traverse_graph` walks N hops; `query_dataview` passes DQL through; `move_note` renames **and rewrites every incoming wikilink**; batch `create_notes`. ~2k LOC, 3 deps, local stdio.
**Why gamechanger** Most servers expose only read/write_file and blow context on multi-hop questions. This exposes the graph itself — "what connects these two ideas?" in one call. Safe rename unblocks "reorganize my vault."
**Adopt** Top KG pick if you use Obsidian. **Status** 🔴

#### knowledge-keeper-mcp
**Repo** https://github.com/zsc-glitch/knowledge-keeper-mcp · **Category** Agent long-term memory (zero-infra)
**What it does** 32 tools, **zero API keys / zero infra**, local-first Markdown. Hybrid search (BM25 R@5=95% + TF-IDF + RRF fusion), entity-detection knowledge graph w/ Mermaid viz, Obsidian read/write, **SHA256 audit trail + version history (diff & rollback)**, spaced repetition. npm.
**Why gamechanger** The only option (per its own comparison) that combines zero-keys + human-readable Markdown + audit + versioning. Audit/version history is rare and valuable. Directly upgrades your basic `memory` KG.
**Adopt** Strong drop-in memory upgrade; no infra to run. **Status** 🔴

#### precis-mcp
**Repo** https://github.com/retospect/precis-mcp · **Category** Memory + research (pgvector, token-optimized)
**What it does** 7-verb uniform API over papers, documents, personal state, code, patents, and **cached** web/Wolfram/YouTube/Perplexity tool calls. pgvector storage, progressive disclosure, spaced repetition, token-optimization. Designed for small (7B) models.
**Why gamechanger** Unifies memory + literature + cached external tools behind one tiny API with explicit token-optimization — aligned with your token-reduction harness. Caching of Wolfram/Perplexity calls saves repeated spend.
**Adopt** Evaluate if you want memory+research+tool-cache in one. **Status** 🔴

#### MegaMem
**Repo** https://github.com/C-Bjorn/MegaMem · **Category** Temporal knowledge graph (Obsidian + Graphiti)
**What it does** Obsidian plugin syncing notes into a **temporal** knowledge graph (Graphiti → Neo4j/FalkorDB) exposed via MCP. AI-extracted entities/relations, every fact timestamped (history preserved), multiple named graph DBs, content-hash incremental sync in SQLite.
**Why gamechanger** Temporal graph = "what did I believe about X, and when" — the time dimension your flat KG lacks. Multi-DB + Neo4j for serious graph queries.
**Adopt** Heavier (needs Neo4j/FalkorDB); add if you want temporal/graph-DB memory. **Status** 🔴

#### zettelkasten-mcp (entanglr)
**Repo** https://github.com/entanglr/zettelkasten-mcp (⭐ 143) · **Category** Knowledge graph (Zettelkasten)
**What it does** Full Zettelkasten methodology over MCP: atomic notes w/ timestamp IDs, bidirectional links, **semantic link types** (multi-dimensional graph), tags, markdown, dual-storage. Most-starred of the KG servers.
**Why gamechanger** Mature, methodology-pure, semantic link types give richer structure than plain wikilinks.
**Adopt** Pick if you practice Zettelkasten specifically. **Status** 🔴

---

### Vector DBs / RAG (you have pinecone *plugin*; these are self-host/multi-provider)

#### qdrant/mcp-server-qdrant (official)
**Repo** https://github.com/qdrant/mcp-server-qdrant (⭐ 1,414) · **Category** Vector DB / semantic memory (official)
**What it does** Official Qdrant server acting as a semantic memory layer: store/find with fastembed local embeddings (no OpenAI key needed), read-only mode, local-path or server. Apache-2.0, actively maintained.
**Why gamechanger** Official + local embeddings = private, self-hosted semantic memory with no API spend. The canonical "give my agent a vector memory" server.
**Adopt** Top vector pick if self-hosting Qdrant. **Status** 🔴

#### vector-mcp (Knuckles-Team)
**Repo** https://github.com/Knuckles-Team/vector-mcp (⭐ 11) · **Category** Vector DB (multi-provider)
**What it does** One server for ChromaDB, Couchbase, MongoDB, Qdrant, PGVector. **Action-routed consolidated tools** (minimizes token overhead / tool bloat), OIDC + Eunomia policy security, OpenTelemetry, built-in Pydantic-AI agent. 75 releases (very active).
**Why gamechanger** Provider-agnostic + token-aware tool consolidation (matches your harness) + enterprise security. Switch backends without switching servers.
**Adopt** Pick if you want one server across multiple vector DBs. **Status** 🔴

#### weave-mcp
**Repo** https://github.com/maximilien/weave-mcp · **Category** Vector DB (universal CLI, 11 DBs)
**What it does** Go server over weave-cli supporting **11** vector DBs (Weaviate, Supabase, Milvus, Chroma, Qdrant, Neo4j, Pinecone, OpenSearch, Elasticsearch, MongoDB, Mock). View/list/create/delete/query collections + docs; operation-specific timeouts.
**Why gamechanger** Broadest DB coverage; built for dev/test/debug (inspect collections quickly). Includes your Pinecone + adds 10 more.
**Adopt** Use as a universal vector-DB inspector/admin. **Status** 🔴

---

### Scientific / Academic Research (you have ToolUniverse biomed; these are general-papers)

#### paper-search-mcp (openags)
**Repo** https://github.com/openags/paper-search-mcp · **Category** Academic papers (broadest sources)
**What it does** Search/download/extract-text across **20+** sources: arXiv, PubMed, bioRxiv, medRxiv, Google Scholar, Semantic Scholar, Crossref, OpenAlex, PMC, CORE, Europe PMC, dblp, OpenAIRE, Zenodo, HAL, SSRN, Unpaywall, DOAJ, BASE (+ optional Sci-Hub). MCP **and** Claude Code skill w/ CLI. Free-first.
**Why gamechanger** Widest free-source coverage with actual PDF download + text extraction (not just metadata). General-science, complementing your biomed ToolUniverse.
**Adopt** Top general academic pick. **Status** 🔴

#### scholar-mcp (pvliesdonk)
**Repo** https://github.com/pvliesdonk/scholar-mcp · **Category** Scholarly (papers + patents + books + standards)
**What it does** Unified search across **papers, patents (EPO OPS), books (Open Library), and standards (NIST/IETF/W3C/ETSI)**. Citation graph BFS, shortest-path bridge discovery, recommendations, BibTeX/CSL-JSON/RIS, OpenAlex enrichment, optional docling PDF conversion.
**Why gamechanger** Patents + standards + books in one prior-art surface — uniquely broad for IP/RE/security research (find a standard or patent, not just a paper).
**Adopt** Add for prior-art / standards lookups. **Status** 🔴

#### paperplain-mcp
**Repo** https://github.com/sulmatajb/paperplain-mcp · **Category** Academic papers (zero-key, auto-route)
**What it does** 200M+ papers from PubMed + arXiv + Semantic Scholar, **no API key**. Auto-routes by topic (health→PubMed+S2, CS/AI→arXiv+S2), auto-falls-back on rate limits, `source_status` field tells the agent if a DB was down. Returns DOI + citation counts.
**Why gamechanger** Zero-config + smart routing + graceful 429 handling = the lowest-friction paper search. Verifiable structured output (no black-box summaries).
**Adopt** Lightweight default for quick lit lookups. **Status** 🔴 ⚠️ unverified (recent)

#### precis-mcp — *(see Knowledge & Memory above; also covers papers/patents/Wolfram)*

---

### Data Engineering / ETL / Analytics

#### motherduck/mcp-server-motherduck (DuckDB)
**Repo** https://github.com/motherduckdb/mcp-server-motherduck · **Category** Data / analytics (DuckDB)
**What it does** Official MotherDuck/DuckDB server — run SQL against a local DuckDB file **or** MotherDuck cloud. DuckDB reads Parquet/CSV/JSON/S3 in-process, so it's a "Swiss-army knife" for ad-hoc analytics across diverse file formats.
**Why gamechanger** DuckDB-over-MCP lets the agent DESCRIBE schemas then query Parquet/S3/local files directly — huge for data wrangling without standing up a warehouse. Complements your postgres MCP for analytical/file workloads.
**Adopt** Top data pick; pairs with your data-engineering skills. **Status** 🔴

#### dbt-labs/dbt-mcp (official)
**Repo** https://github.com/dbt-labs/dbt-mcp (⭐ 556) · **Category** Data / transformation (dbt)
**What it does** Official dbt server for dbt Core/Fusion/Platform: `execute_sql`, `text_to_sql` (NL→SQL w/ project context), Semantic Layer (`list_metrics`, `query_metrics`, `get_entities`), dbt CLI (build/compile/clone in DAG order). 50 contributors, very active.
**Why gamechanger** If you touch dbt, this gives the agent full project context + semantic-layer metric queries — official and well-maintained.
**Adopt** Add for any dbt-based stack. **Status** 🔴

---

### Creative Media — 3D / Image / Audio / Video (you have fal-ai, imagegen, sora *skills*; no MCP for local media tooling)

#### artificer-mcp
**Repo** https://github.com/bthurlow/artificer-mcp · **Category** Creative media (gen + local processing)
**What it does** Full creative pipeline in one server: image gen (Gemini Imagen/Nano Banana), video (Veo), speech (Gemini TTS), music (Lyria), **57 ImageMagick tools** (resize/composite/social-cards/app-icons), **25 FFmpeg tools** (concat/trim/transitions/overlays/subtitles/loudness-norm/sidechain ducking). URI-first I/O, pluggable providers.
**Why gamechanger** Consolidates the fragmented ImageMagick+FFmpeg+gen ecosystem into one coherent server with URI inputs (no local-path-only quirks). Your media skills are gen-focused; this adds *local processing* (resize/encode/composite) the skills lack.
**Adopt** Top creative-media pick. (Focused alt: imagemagick-mcp.) **Status** 🔴

#### mcp-blender (RFingAdam)
**Repo** https://github.com/RFingAdam/mcp-blender · **Category** 3D (Blender, comprehensive)
**What it does** 218 Blender tools across modeling/materials/sculpting/animation. Multi-backend **AI 3D generation** (Hyper3D Rodin, Meshy, Tripo, TripoSR, Stable-Fast-3D, Hunyuan3D, ComfyUI) text/image→3D w/ auto cleanup. **Self-refinement loop**: render_multi_angle → analyze_viewport → refine. Blender 4.x. (Active; also dwgx/blender-copilot has 308 tools + VRChat pipeline.)
**Why gamechanger** The render→analyze→refine vision loop lets Claude iterate on 3D visually. AI text-to-3D backends turn prompts into meshes. Nothing in your inventory does 3D.
**Adopt** Add if you do any 3D/Blender work. **Status** 🔴

#### ffmpeg-mcp (dubnium0)
**Repo** https://github.com/dubnium0/ffmpeg-mcp · **Category** Video/audio (focused FFmpeg)
**What it does** 40+ FFmpeg tools: trim/merge/resize/speed/crop/rotate, stabilize (vidstab), denoise, deinterlace, framerate interpolation, PiP, side-by-side, mosaic, reverse; audio normalize (EBU R128)/mix/fade, waveform + spectrogram gen. (Lighter alt: kevinwatt/ffmpeg-mcp-lite ⭐21.)
**Why gamechanger** Focused, deep FFmpeg if you don't want artificer's gen dependencies. Spectrogram/waveform + stabilize are nice extras.
**Adopt** Use if you only need local video/audio editing. **Status** 🔴

---

### Web Scraping / Browser (specialized — beyond your firecrawl/apify/scrapegraph/playwright)

#### crawl-mcp (Crawl4AI wrapper)
**Repo** https://github.com/walksoda/crawl-mcp · **Category** Scraping (Crawl4AI + multi-format)
**What it does** Wraps Crawl4AI (⭐66k lib): JS-rendered crawling, deep site mapping, entity extraction, **universal extraction** (web + PDF + Word/Excel/PowerPoint + ZIP), **YouTube transcripts (no API key)**, AI summarization with **up to 88.5% token reduction**. 19 tools.
**Why gamechanger** Crawl4AI's anti-bot (v0.8.5 added 3-tier proxy-escalation) + the token-reduction summarization layer = scraping that fits your harness. Office-doc + YouTube extraction your current scrapers lack.
**Adopt** Add for JS-heavy/anti-bot scraping + doc/YouTube extraction. **Status** 🔴

#### Ghost_Browser_MCP
**Repo** https://github.com/BU3NO77XL/Ghost_Browser_MCP · **Category** Stealth browser (nodriver + CDP)
**What it does** 225 tools driving a **real stealth browser** (nodriver + Chrome DevTools Protocol): bypass Cloudflare/Queue-It/antibot, network interception + AI-generated hook functions that modify traffic live, **pixel-accurate page cloning** (DOM+CSS+computed-layout+assets), full page intelligence (console/storage/cookies/event-listeners).
**Why gamechanger** Antibot bypass + live network-hook injection + page cloning go well beyond your Playwright/chrome-devtools — useful for RE of web apps and scraping protected sites. Overlaps your CloakBrowser awareness but as an MCP server.
**Adopt** Add for protected-site automation / web-app RE. **Status** 🔴 ⚠️ unverified

---

### Finance (NET-NEW domain — you have none)

#### mcp-financex
**Repo** https://github.com/xerktech/mcp-financex · **Category** Finance (markets + SEC + options)
**What it does** Real-time stocks/crypto quotes, OHLCV history, technicals (RSI/MACD/SMA/EMA/Bollinger/Stochastic), news; **options chains + Black-Scholes Greeks + strategy analysis**; SEC filings — insider (Forms 3/4/5), 13F institutional, 13D/G ownership, 8-K events; financial statements + DCF valuation. **No API keys** (Yahoo + SEC EDGAR).
**Why gamechanger** Markets + options Greeks + full SEC filing analysis + DCF in one no-key server — broadest finance coverage found.
**Adopt** Top finance pick. **Status** 🔴

#### sec-edgar-mcp (stefanoamorelli)
**Repo** https://github.com/stefanoamorelli/sec-edgar-mcp (⭐ 270) · **Category** Finance (SEC, precision)
**What it does** SEC EDGAR filings with **exact numeric precision** (XBRL-parsed financials), 10-K/10-Q/8-K retrieval + section extraction, insider Form 3/4/5, every response includes SEC URLs for verification. Built on edgartools. 20 contributors, maintained.
**Why gamechanger** Most-starred + precision-focused: financial figures parsed from XBRL (no hallucinated numbers) with verifiable source links. The trustworthy choice for filing analysis.
**Adopt** Pick if your focus is fundamentals/filings over live trading. **Status** 🔴

#### triplom/financial-mcp-server
**Repo** https://github.com/triplom/financial-mcp-server · **Category** Finance (multi-source aggregator)
**What it does** Unifies yfinance + FRED (800k+ macro series) + SEC EDGAR + CoinGecko + forex + commodities + technicals. Equities/SEC/macro/crypto/forex/commodities in one interface.
**Why gamechanger** Adds **macroeconomics (FRED)** + commodities + forex that the markets-only servers lack — full economic picture.
**Adopt** Pick if you want macro + multi-asset coverage. **Status** 🔴 ⚠️ unverified

---

### Automation Platforms (NET-NEW — n8n/Make/Zapier control)

#### czlonkowski/n8n-mcp
**Repo** https://github.com/czlonkowski/n8n-mcp (⭐ 17,262!) · **Category** Automation (n8n)
**What it does** Gives Claude deep knowledge of n8n's ~1,400 nodes (properties 99% coverage, 263 AI-tool variants, 2,352 workflow templates) so it can **build and manage n8n workflows for you**. Free remote endpoint (100 calls/day) or self-host. 176 releases, 30 contributors. The de-facto n8n-MCP.
**Why gamechanger** By far the most-starred niche server found — turns Claude into an n8n workflow author with full node knowledge + a template library. n8n is the privacy-friendly, self-hostable automation hub (400+ integrations) for a power user.
**Adopt** Top automation pick if you self-host n8n. **Status** 🔴

#### makafeli/n8n-workflow-builder
**Repo** https://github.com/makafeli/n8n-workflow-builder · **Category** Automation (n8n CRUD/exec)
**What it does** Full CRUD + execute + lifecycle (activate/deactivate/monitor) of n8n workflows via your n8n API. Zero-config NPX, TypeScript.
**Why gamechanger** Where czlonkowski focuses on *knowledge/building*, this focuses on *operating* an existing n8n instance (run/monitor/manage). Complementary.
**Adopt** Pair with czlonkowski for build+operate. **Status** 🔴

---

### Terminal / DevOps / Remote (you have docker/digitalocean; these are remote-exec + multi-protocol)

#### DesktopCommanderMCP
**Repo** https://github.com/wonderwhy-er/DesktopCommanderMCP (⭐ 6,069) · **Category** Terminal / filesystem
**What it does** Terminal control + filesystem search + diff-based file editing in one. Long-running commands with output streaming, background execution, **interactive process control** (drive SSH sessions/databases/dev servers), process mgmt, session mgmt. macOS + Windows. Uses host client subscription (no API token cost).
**Why gamechanger** Most-starred terminal MCP; the interactive-process control (talk to a live SSH/DB/REPL session) is genuinely powerful for an automation-heavy user. Cross-platform incl. Windows.
**Adopt** Strong general terminal/automation pick. **Status** 🔴

#### mcp-ssh-bridge (muchiny, Rust)
**Repo** https://github.com/muchiny/mcp-ssh-bridge · **Category** Remote mgmt (multi-protocol)
**What it does** Rust server, **337 tools across 74 groups**, routing through **14 protocol adapters**: SSH, WinRM, Telnet, NETCONF, gRPC, K8s-Exec, Serial, SNMP, AWS-SSM, Azure, GCP, ZeroMQ, NATS, MQTT. Linux/Windows/Docker/K8s/Podman/LDAP/network-gear. Built-in security controls; air-gapped friendly; `.dxt` for Claude Desktop.
**Why gamechanger** One server reaches *everything* — Linux + Windows (WinRM) + network equipment (NETCONF/SNMP) + cloud (SSM/Azure/GCP) + message buses. Rust = single binary, no Node/Python on targets.
**Adopt** Add for homelab/infra fleet management. **Status** 🔴 ⚠️ unverified (low stars, but broad + Rust)

#### containers/kubernetes-mcp-server
**Repo** https://github.com/containers/kubernetes-mcp-server (⭐ 1,587) · **Category** DevOps (K8s/OpenShift, native)
**What it does** Go-native K8s/OpenShift server that talks **directly to the API** (NOT a kubectl/helm wrapper) — no external deps, multi-cluster, single binary (Linux/macOS/Windows), npm/PyPI/Docker also. Red Hat backed (60 contributors).
**Why gamechanger** Direct-API (low latency, no kubectl needed) + multi-cluster + truly cross-platform. The serious K8s pick.
**Adopt** Add if you run Kubernetes. **Status** 🔴

#### macos-automator-mcp — *(macOS only; skip — you're on Windows 11)* ⚪

---

### Observability / Time-Series (you have sentry; these are metrics/logs/traces)

#### grafana/mcp-grafana (official)
**Repo** https://github.com/grafana/mcp-grafana (⭐ 3,043) · **Category** Observability (Grafana, official)
**What it does** Official Grafana server: query Prometheus/Loki/ClickHouse/CloudWatch/Elasticsearch/OpenSearch/Snowflake/Athena datasources, fetch dashboard panel queries, run panel queries directly. Go, 90 contributors, very active.
**Why gamechanger** Official + one server fronts ~8 datasource types. Pull a dashboard panel's exact query and run it — fast path from "what does this show?" to data. Pairs with your clickhouse-io skill.
**Adopt** Top observability pick if you run Grafana. **Status** 🔴

#### observability-mcp (ThoTischner)
**Repo** https://github.com/ThoTischner/observability-mcp (⭐ 4) · **Category** Observability (unified gateway)
**What it does** Unified gateway: pluggable connectors to Prometheus/Loki/any backend, **normalizes** data, adds cross-signal anomaly detection + web UI. Benchmark shows normalized tools beat generic ones for blast-radius accuracy (0/10 → much higher). Updated this week.
**Why gamechanger** Normalization across backends means the agent asks one question instead of juggling N query languages — and the benchmark shows it measurably improves agent accuracy.
**Adopt** Consider if multi-backend observability. **Status** 🔴 ⚠️ unverified (low stars but active)

---

### MCP Gateways / Aggregators (PARTIAL — you already run mcp-funnel; alternatives only)

#### metamcp (metatool-ai)
**Repo** https://github.com/metatool-ai/metamcp (⭐ 2,205) · **Category** Gateway / aggregator
**What it does** Dockerized MCP proxy: aggregate N servers into namespaces, host as meta-MCPs with public SSE/HTTP endpoints + auth, pick only the tools you need when remixing, pluggable middleware. Is itself an MCP server → plugs into any client.
**Why gamechanger** Mature, namespace+auth+endpoint hosting + tool-cherry-picking. 🟡 overlaps your mcp-funnel, but namespaces/public-endpoints/middleware may exceed funnel's features.
**Adopt** Evaluate vs mcp-funnel only if you need hosted endpoints/namespaces. **Status** 🟡

#### mentu-ai/metamcp ("power strip")
**Repo** https://github.com/mentu-ai/metamcp · **Category** Gateway (token-collapse)
**What it does** Collapses N child servers into **6 tools (~1,300 tokens, constant whether 3 or 30 servers)** via 4 management + 2 advisory tools. Built-in gallery (122 servers), `mcp_provision` (describe a capability → resolves/installs the right server, incl. npm), connection pooling, schema caching, **skill-awareness** (`mcp_skill_discover` checks SKILL.md readiness).
**Why gamechanger** Aggressive token-collapse + on-demand provisioning + skill-readiness checks = squarely your token-reduction + skills-harness use case. The constant-token property is exactly your goal.
**Adopt** Strong comparison target for mcp-funnel; the skill-awareness is unique. **Status** 🟡

#### stacklok/toolhive
**Repo** https://github.com/stacklok/toolhive · **Category** Gateway (enterprise/security)
**What it does** Enterprise platform: runs every MCP server in an **isolated container** with a permission file (no plaintext creds), semantic tool filtering, gateway + registry + Kubernetes operator + portal, IdP/OIDC SSO, provenance + signing, audit.
**Why gamechanger** Strongest security/isolation story — per-server containers + signed provenance + RBAC. If you ever expose your ~40 servers beyond localhost, this is the hardened option.
**Adopt** Overkill for solo localhost, but the container-isolation model is worth knowing. **Status** 🟡

---

### Summary / TOP 8 hidden-gem NET-NEW picks

Ranked by impact for this user (RE/security + automation + data + token-economy, Windows):

1. **czlonkowski/n8n-mcp** (⭐17k) — Claude authors/manages n8n workflows w/ full node knowledge. Massive automation unlock.
2. **Arkana** — "entire malware lab behind one prompt": angr + capa + FLOSS + Qiling + 260 tools. Adds symbolic exec your IDA set lacks.
3. **DesktopCommanderMCP** (⭐6k) — terminal + interactive process control (drive live SSH/DB/REPL); Windows; no token cost.
4. **knowledge-keeper-mcp** — zero-key, local Markdown agent memory w/ hybrid search + audit trail + version history. Upgrades your basic `memory` KG.
5. **mcp-financex** — full finance (markets + options Greeks + SEC filings + DCF), no API keys. Whole new domain.
6. **crawl-mcp** (Crawl4AI) — anti-bot scraping + Office/PDF/YouTube extraction + 88% token-reduction summarization. Fits your harness.
7. **Tengu** — safety-first pentest copilot (80 tools, HITL, audit, auto-reports). Responsible AI pentesting.
8. **motherduck/mcp-server-motherduck** — DuckDB over MCP: query Parquet/CSV/S3/local files in-process. Data-wrangling powerhouse.

Honorable mentions: mulder (DFIR cases), obsidian-mcp graph-aware (if Obsidian), qdrant/mcp-server-qdrant (self-host vector memory), grafana/mcp-grafana (observability), mcp-blender (3D), paper-search-mcp (20+ paper sources), mcp-ssh-bridge (homelab fleet, 14 protocols), mentu-ai/metamcp (token-collapse gateway vs mcp-funnel).

**Counts:** ~46 servers + 7 directories = **53 entries**. ~11 flagged ⚠️ unverified (real repos, low-maturity signals). 3 gateway picks are 🟡 (overlap mcp-funnel). 1 (macos-automator) excluded as macOS-only.

---

## 5.4 — Skills & skill marketplaces


> Research agent #4 of 7. Focus: **net-new** Claude Code skills the user does NOT already have.
> User already owns ~350 skills (superpowers, ECC, ToolUniverse 200+ bio, full RE/security/cloud/lang stacks).
> Year: 2026. Stars/recency verified via `gh api` on 2026-05-28.
> Legend: 🔴 NET-NEW-GAP · 🟡 PARTIAL (have something similar, this adds value) · ✅ HAVE (listed only to justify skipping)

---

### Best skill marketplaces / collections to subscribe to

These are the *sources* worth wiring in so new skills flow in over time. Ranked by net-new value to THIS user.
**Note on aggregators:** the user already has `affaan-m/everything-claude-code` (ECC, ~153k⭐) — the biggest aggregator — so the marketplaces below are chosen to add what ECC + their ToolUniverse/superpowers stack does NOT cover.

| Marketplace | ⭐ | Last push | Why subscribe | Adopt |
|---|---|---|---|---|
| **wshobson/agents** | 36.1k | 2026-05-26 | 155 skills / 83 plugins / 191 agents, multi-harness (CC+Codex+Cursor+Gemini+Copilot from one source). Massive coverage of k8s/service-mesh/data-eng/payments/web3/observability the user lacks. Granular per-plugin install = no bloat. **Single highest-value subscription.** | `/plugin marketplace add wshobson/agents` |
| **VoltAgent/awesome-agent-skills** | 23.4k | 2026-05-27 | 1,424+ **official vendor** skills (Stripe, GSAP, Remotion, Neon, Better Auth, Resend, MongoDB, Apollo, Datadog, DuckDB, Tinybird, ClickHouse, Vercel, fal.ai…) — "hand-picked, not AI-slop." Browse + 1-click install at officialskills.sh. The best directory of *first-party* skills. | Browse https://officialskills.sh/ ; install per-vendor |
| **ComposioHQ/awesome-claude-skills** | 62.3k | 2026-05-22 | 1,000+ skills across Document/Dev/Data/Marketing/Creative/Productivity/Security + App-Automation-via-Composio (Gmail, Slack, Jira, etc. through one connector). Broadest community catalog. | https://github.com/ComposioHQ/awesome-claude-skills |
| **sickn33/antigravity-awesome-skills** | 39.0k | 2026-05-28 | 1,400+ **installable** agentic skills with a GitHub Pages browser + install scripts. Cross-harness (CC/Codex/Antigravity). Daily updates. | https://sickn33.github.io/antigravity-awesome-skills/ |
| **K-Dense-AI/claude-scientific-skills** | 26.4k | 2026-05-27 | 140 science skills + 100+ databases (chem/physics/materials/medicine). 🟡 overlaps user's ToolUniverse on biomed, but adds non-bio science + a different DB set. | `/plugin marketplace add K-Dense-AI/claude-scientific-skills` |
| **gsd-build/get-shit-done** | 63.8k | 2026-05-27 | "GSD" lightweight meta-prompting + spec-driven dev by TÂCHES. 🟡 alternative philosophy to metaswarm/superpowers — worth studying for context-engineering ideas. | `/plugin marketplace add gsd-build/get-shit-done` |
| **trailofbits/skills** | 5.4k | 2026-05-27 | Pro security firm: CodeQL/Semgrep variant analysis, audit workflows, vuln detection. User has semgrep/RE skills but not ToB's audit *methodology*. | `/plugin marketplace add trailofbits/skills` |
| **vercel-labs/agent-skills** | 27.2k | 2026-05-27 | Vercel's official skills: Web Interface Guidelines (100+ a11y/UX rules), React Best Practices (57 perf rules), Composition Patterns. 🟡 vs user's frontend-patterns/ui-ux-pro-max — but these are battle-tested rule sets, not generic guidance. | `/plugin marketplace add vercel-labs/agent-skills` |
| **expo/skills** | 2.0k | 2026-05-27 | Official Expo team skills for React Native / EAS. User has Swift/Compose but no cross-platform RN/Expo. | `/plugin marketplace add expo/skills` |
| **JimLiu/baoyu-skills** | 19.8k | 2026-05-28 | Baoyu's 22-skill content-creation pipeline (covers, infographics, slide decks, diagrams, XHS cards, multi-platform publishing, YT transcripts). 285k+ installs. The reference content-engine. | `/plugin marketplace add JimLiu/baoyu-skills` or `npx skills add jimliu/baoyu-skills` |
| **obra/superpowers-skills** + **obra/superpowers-lab** | community / 324 | active | Community-editable + experimental superpowers — net-new skills (windows-vm, tmux-control, duplicate-function finder) land here before core. | via `superpowers-marketplace` plugin |
| **FridrichMethod/awesome-skills** | 5 (new) | 2026-05-28 | Niche but clever: auto-syncs 1,800+ vetted skills from **15 upstream collections** weekly into one curl-installable bundle, filtering LFS/oversized junk. A "set-and-forget" meta-aggregator. | https://github.com/FridrichMethod/awesome-skills |

---

### NET-NEW individual skills

> Ordered roughly by impact for this user. Marketplace-bundled skills note their parent marketplace under **Adopt**.

#### Platform / workflow (highest fit for a Windows power user + RE workflows)

#### windows-vm
**Source repo** obra/superpowers-lab (324⭐, pushed 2026-03-23)
**Category** DevOps / platform
**What it does** Spins up a headless Windows 11 VM in Docker (KVM-accelerated, SSH-only, no RDP) and manages its full lifecycle, auto-installing OpenSSH + Node + Claude Code inside.
**Why gamechanger** User is on Windows 11 but does heavy RE/cross-platform work — an isolated, scriptable Windows sandbox for testing patched APKs/binaries or risky tooling without touching the host. Pairs with their BlueStacks/Frida RE stack.
**Adopt** `superpowers-marketplace` → superpowers-lab plugin
**Status** 🔴 NET-NEW

#### using-tmux-for-interactive-commands
**Source repo** obra/superpowers-lab (324⭐)
**Category** Platform / agent-capability
**What it does** Lets Claude drive *interactive* CLI tools (vim, `git rebase -i`, menuconfig, REPLs, `git add -p`) via detached tmux sessions — sending keystrokes and capturing output.
**Why gamechanger** Closes a hard gap: the agent normally can't operate TUIs/REPLs. Huge for the user's debugger/RE sessions (x64dbg scripting is GUI, but radare2/gdb/python REPLs become automatable) and interactive git surgery.
**Adopt** `superpowers-marketplace` → superpowers-lab
**Status** 🔴 NET-NEW (note: tmux is Linux/macOS/WSL — use under WSL on Windows)

#### mcp-cli
**Source repo** obra/superpowers-lab (324⭐)
**Category** MCP / context management
**What it does** Invoke MCP servers on-demand through an `mcp` CLI instead of pre-loading them into context — discover/list/call tools without permanent registration.
**Why gamechanger** Directly serves the user's documented MCP-token-reduction initiative (45% connection cut). One-off RE/quality tool calls without bloating every session's tool list.
**Adopt** `superpowers-marketplace` → superpowers-lab
**Status** 🔴 NET-NEW (complements their mcp-funnel approach)

#### finding-duplicate-functions
**Source repo** obra/superpowers-lab (324⭐)
**Category** Code quality / refactor
**What it does** Detects *semantic* (not syntactic) duplicate functions in LLM-generated code via classical extraction + Haiku domain-clustering + Opus intent analysis. Complements jscpd.
**Why gamechanger** The user runs autonomous loops (Ralph/metaswarm) that generate lots of code — semantic-dupe detection catches the "reimplemented the same util 4 times" drift that copy-paste detectors miss.
**Adopt** `superpowers-marketplace` → superpowers-lab
**Status** 🔴 NET-NEW

#### ios-simulator-skill
**Source repo** conorluddy/ios-simulator-skill (1.0k⭐, pushed 2026-05-25)
**Category** Mobile dev / iOS
**What it does** Wraps `xcodebuild` + simulator control so Claude can build, boot, navigate, and UI-test iOS apps while saving context (it's primarily a context-efficient xcodebuild wrapper).
**Why gamechanger** User has Swift/SwiftUI skills but nothing that actually *drives* the simulator. Turns "write SwiftUI" into "write + build + run + screenshot the result."
**Adopt** clone to `~/.claude/skills/` or `/plugin add`
**Status** 🔴 NET-NEW

#### Andrej Karpathy's Coding Guidelines
**Source repo** via officialskills.sh / VoltAgent (community)
**Category** Coding methodology
**What it does** Encodes Karpathy's four LLM-coding rules: think before coding, simplicity first, surgical changes, goal-driven execution — as an always-available behavioral skill.
**Why gamechanger** A concise, widely-praised counterweight to over-engineering. Sits alongside the user's coding-standards/superpowers without the weight of a full framework. Frequently cited as the single best "make the agent behave" skill of 2026.
**Adopt** Browse officialskills.sh → "Andrej Karpathy's Guidelines"
**Status** 🔴 NET-NEW

#### Skill_Seekers (docs→skill converter)
**Source repo** yusufkaraaslan/Skill_Seekers (13.8k⭐, pushed 2026-05-25)
**Category** Skill authoring / tooling
**What it does** Converts documentation websites, GitHub repos, and PDFs into Claude skills automatically, with conflict detection.
**Why gamechanger** User constantly works with niche APIs (Frida, IDA, tbcml, BCSFE, game-data formats). Auto-generating a skill from a docs site or a repo's README means their RE/game-modding knowledge becomes a reusable skill in minutes — feeds their own skill-creation pipeline.
**Adopt** `git clone https://github.com/yusufkaraaslan/Skill_Seekers`
**Status** 🔴 NET-NEW (better than hand-rolling vs their existing `writing-skills`/`skill-creator` — this is the *ingestion* front-end)

#### supermemory (skill)
**Source repo** supermemoryai/supermemory (22.7k⭐, pushed 2026-05-28)
**Category** Memory / persistence
**What it does** Fast scalable memory engine + skill that stores/recalls style guides, brand voice, and project rules across sessions via a Memory API.
**Why gamechanger** 🟡 user already has the `memory` MCP + `remember` plugin + auto-memory, but supermemory's API-backed store scales past flat-file memory and is purpose-built for cross-project recall — worth evaluating as an upgrade, not a duplicate.
**Adopt** see supermemory docs / officialskills.sh
**Status** 🟡 PARTIAL (potential upgrade)

#### Document & office formats (the user has generic pdf/slides/spreadsheet, NOT the official Anthropic file-format skills)

#### docx / pptx / xlsx (official Anthropic)
**Source repo** anthropics/skills (142k⭐, pushed 2026-05-19)
**Category** Document processing
**What it does** First-class Word/PowerPoint/Excel manipulation: tracked changes & comments (docx), layouts/templates/charts (pptx), formulas/data-analysis/viz (xlsx) — preserving native formatting.
**Why gamechanger** User's inventory has `pdf`, `slides`, `spreadsheet` (generic) but **not** the Anthropic docx/pptx/xlsx skills that round-trip real Office files with comments and tracked changes. Essential for any client/report deliverable.
**Adopt** `/plugin marketplace add anthropics/skills` then install docx, pptx, xlsx
**Status** 🔴 NET-NEW (the generic ones they have don't cover Office round-trip)

#### doc-coauthoring
**Source repo** anthropics/skills (142k⭐)
**Category** Writing / docs
**What it does** Official skill for collaborative long-form document authoring (structure, drafting, revision passes) — newer than the format skills.
**Why gamechanger** User has `doc`/`article-writing` but this is Anthropic's purpose-built co-authoring loop; pairs with docx for client-facing writing.
**Adopt** `/plugin marketplace add anthropics/skills` → doc-coauthoring
**Status** 🔴 NET-NEW

#### theme-factory
**Source repo** anthropics/skills (142k⭐)
**Category** Design / theming
**What it does** Official skill for generating cohesive visual themes (color systems, typography, tokens) for artifacts/UIs.
**Why gamechanger** Complements the user's `liquid-glass-design`/`ui-ux-pro-max` with Anthropic's own token-system generator — good for kicking off a design system fast.
**Adopt** `/plugin marketplace add anthropics/skills` → theme-factory
**Status** 🔴 NET-NEW

#### internal-comms
**Source repo** anthropics/skills (142k⭐, 5.3k installs)
**Category** Productivity / communication
**What it does** Writes status reports, newsletters, FAQs, and internal updates in a structured, professional voice.
**Why gamechanger** Fills a non-code productivity gap — turning the user's project/PR activity into shippable status updates and changelogs.
**Adopt** `/plugin marketplace add anthropics/skills` → internal-comms
**Status** 🔴 NET-NEW

#### Frontend / design (beyond what they have)

#### frontend-design (official anti-"AI-slop")
**Source repo** anthropics/skills (142k⭐)
**Category** Frontend / design
**What it does** Steers Claude away from generic AI aesthetics toward bold, intentional, production-grade UI (tuned for React + Tailwind).
**Why gamechanger** 🟡 user has `frontend-patterns` + `ui-ux-pro-max`, but this is Anthropic's official anti-slop skill that aligns *exactly* with the user's own web/design-quality rules ("Anti-Template Policy"). Different lever: behavioral nudge vs reference library.
**Adopt** `/plugin marketplace add anthropics/skills` → frontend-design
**Status** 🟡 PARTIAL (philosophy match — worth having alongside)

#### Vercel Web Interface Guidelines
**Source repo** vercel-labs/agent-skills (27.2k⭐) / vercel-labs/web-interface-guidelines (647⭐)
**Category** Frontend / accessibility
**What it does** `/web-interface-guidelines` reviews UI code against 100+ rules covering accessibility, keyboard support, form behavior, animation, and performance.
**Why gamechanger** Concrete, auditable rule set (not vibes) — directly satisfies the user's web/testing.md a11y requirements and web/performance.md CWV targets. Auditing existing components against a checklist is something their current skills don't do.
**Adopt** `curl -fsSL https://vercel.com/design/guidelines/install | bash` or `/plugin marketplace add vercel-labs/agent-skills`
**Status** 🔴 NET-NEW

#### Vercel React Best Practices + Composition Patterns
**Source repo** vercel-labs/agent-skills (27.2k⭐)
**Category** Frontend / React
**What it does** Applies 57 performance rules to React/Next.js; replaces boolean-prop sprawl with compound-component composition patterns.
**Why gamechanger** Codifies the exact "compound components over prop drilling" pattern in the user's own web/patterns.md — but as an enforced skill. Net-new perf-rule coverage for React specifically.
**Adopt** `/plugin marketplace add vercel-labs/agent-skills`
**Status** 🔴 NET-NEW

#### shadcn/ui skill
**Source repo** ui.shadcn.com/docs/skills (official)
**Category** Frontend / component library
**What it does** Gives Claude live context on shadcn/ui components plus pattern enforcement when scaffolding UI.
**Why gamechanger** If any project uses shadcn (the de-facto React component kit), this prevents the agent from hallucinating component APIs. Net-new — no shadcn skill in inventory.
**Adopt** see https://ui.shadcn.com/docs/skills
**Status** 🔴 NET-NEW

#### claude-d3js-skill
**Source repo** chrisvoncsefalvay/claude-d3js-skill (183⭐, pushed 2025-10)
**Category** Data viz / frontend
**What it does** Expert guidance for building d3.js visualizations.
**Why gamechanger** User has generic charting via spreadsheet/notebook but no dedicated d3 skill — d3 is the power tool for custom, interactive viz that chart libs can't do. ⚠️ maintenance: untouched since Oct 2025.
**Adopt** clone to `~/.claude/skills/`
**Status** 🔴 NET-NEW (verify still current before relying)

#### web-asset-generator
**Source repo** alonw0/web-asset-generator (398⭐, pushed 2026-01)
**Category** Frontend / assets
**What it does** Generates favicons, app icons, and social-media/OG images from logos, text, or emojis — with validation and framework auto-integration.
**Why gamechanger** Tedious-but-required deploy step the user has no skill for. Pairs with their vercel/cloudflare/netlify deploy skills to ship a polished site (favicons + OG cards) in one pass.
**Adopt** clone to `~/.claude/skills/`
**Status** 🔴 NET-NEW

#### Creative media (user has video-editing/videodb/imagegen/sora/fal-ai — these fill specific gaps)

#### remotion-best-practices
**Source repo** remotion-dev/skills (3.3k⭐, pushed 2026-05-07)
**Category** Creative / programmatic video
**What it does** Deep, official knowledge for building **deterministic** videos in React → MP4 (animated charts, data viz, pixel-perfect motion graphics).
**Why gamechanger** User's `video-editing`/`videodb` are edit/asset tools; Remotion is *programmatic* video — the only reliable way to render data-driven, reproducible animations (e.g., visualizing RE/benchmark data as MP4). Distinct capability.
**Adopt** `remotion-dev/skills` via officialskills.sh or clone
**Status** 🔴 NET-NEW

#### smart-illustrator
**Source repo** axtonliu/smart-illustrator (476⭐, pushed 2026-02)
**Category** Creative / content
**What it does** Tri-engine article illustration: auto-picks Gemini (creative), Excalidraw (hand-drawn), or Mermaid (structured) per content type; detects optimal illustration points; YouTube-thumbnail/cover mode with CTR best practices.
**Why gamechanger** Net-new content-creator capability — turns the user's articles/docs into illustrated pieces and generates high-CTR thumbnails. Mermaid/Excalidraw auto-selection is genuinely clever.
**Adopt** clone to `~/.claude/skills/`
**Status** 🔴 NET-NEW

#### claude-code-video-toolkit
**Source repo** digitalsamba/claude-code-video-toolkit (1.3k⭐, pushed 2026-05-20)
**Category** Creative / video (self-hosted)
**What it does** AI-native video workspace: open-source models for voiceover (Qwen3-TTS), image gen (FLUX.2), music (ACE-Step), plus FFmpeg/moviepy/Remotion editing — deployed to your own cloud GPU (Modal/RunPod) at cost.
**Why gamechanger** 🟡 user has `video-editing` but this is a *self-hosted, no-vendor-lock-in* full pipeline (voice+image+music+edit) — appealing given the user's preference for local/self-hosted tooling and cost control.
**Adopt** `git clone https://github.com/digitalsamba/claude-code-video-toolkit`
**Status** 🟡 PARTIAL (broader + self-hosted than current video skill)

#### slack-gif-creator
**Source repo** anthropics/skills (142k⭐)
**Category** Creative / fun
**What it does** Creates animated GIFs optimized for Slack's size constraints.
**Why gamechanger** Small but genuinely net-new; no GIF skill in inventory. Handy for team comms.
**Adopt** `/plugin marketplace add anthropics/skills` → slack-gif-creator
**Status** 🔴 NET-NEW

#### algorithmic-art / canvas-design
**Source repo** anthropics/skills (142k⭐)
**Category** Creative / generative
**What it does** algorithmic-art: generative art via p5.js (flow fields, particle systems, seeded randomness). canvas-design: composed visual art exported to PNG/PDF using design philosophies.
**Why gamechanger** User has `imagegen`/`sora` (model-driven) but no *code-driven* generative art or layout-design skill. Distinct creative axis (deterministic, parametric).
**Adopt** `/plugin marketplace add anthropics/skills`
**Status** 🔴 NET-NEW

#### Security (user is RE/security-heavy — these add methodology, not duplicate tooling)

#### Trail of Bits security skills
**Source repo** trailofbits/skills (5.4k⭐, pushed 2026-05-27)
**Category** Security / audit
**What it does** Professional audit workflows: CodeQL + Semgrep variant analysis, structured code auditing, vulnerability detection authored by Trail of Bits.
**Why gamechanger** User has `semgrep`/`security-review`/RE skills but not a top-firm's *audit methodology* (variant analysis = "find all other instances of this bug class"). Elevates ad-hoc scanning to systematic audits.
**Adopt** `/plugin marketplace add trailofbits/skills`
**Status** 🔴 NET-NEW

#### ffuf-web-fuzzing
**Source repo** jthack/ffuf_claude_skill (181⭐, pushed 2025-10)
**Category** Security / pentest
**What it does** Expert guidance for `ffuf` web fuzzing: authenticated fuzzing with raw requests, auto-calibration, result analysis.
**Why gamechanger** User's security stack is mostly static/RE; this adds *dynamic* web-app fuzzing. Net-new offensive-web capability. ⚠️ untouched since Oct 2025 (ffuf itself is stable, so low risk).
**Adopt** clone to `~/.claude/skills/`
**Status** 🔴 NET-NEW

#### wshobson security-scanning bundle (STRIDE / attack-trees)
**Source repo** wshobson/agents (36.1k⭐) — security-scanning plugin
**Category** Security / threat modeling
**What it does** 5 skills: SAST configuration, STRIDE analysis, attack-tree construction, security-requirement extraction, threat-mitigation mapping.
**Why gamechanger** 🟡 user has `security-threat-model`, but this is a structured STRIDE + attack-tree toolkit — more rigorous threat-modeling artifacts than a single skill. Worth it for the attack-tree generation alone.
**Adopt** `/plugin marketplace add wshobson/agents` → `/plugin install security-scanning`
**Status** 🟡 PARTIAL (deeper than current threat-model skill)

#### DevOps / infra / data (large genuine gaps — almost none of this in inventory)

#### Kubernetes operations bundle
**Source repo** wshobson/agents (36.1k⭐) — kubernetes-operations plugin
**Category** DevOps / k8s
**What it does** 4 skills: k8s-manifest-generator, helm-chart-scaffolding, gitops-workflow (ArgoCD/Flux), k8s-security-policies (NetworkPolicy/PSP/RBAC).
**Why gamechanger** Inventory has Docker but **zero Kubernetes/Helm/GitOps**. This is a complete, production-grade k8s onramp — a major missing layer for anyone deploying containers.
**Adopt** `/plugin marketplace add wshobson/agents` → `/plugin install kubernetes-operations`
**Status** 🔴 NET-NEW

#### Observability & monitoring bundle
**Source repo** wshobson/agents (36.1k⭐) — observability-monitoring plugin
**Category** DevOps / observability
**What it does** Prometheus configuration, Grafana dashboards, distributed tracing (Jaeger/Tempo), SLO/SLI + error budgets.
**Why gamechanger** User has app-level skills but no telemetry/observability skills. Prometheus+Grafana+tracing+SLOs is the standard production-monitoring stack — entirely absent today.
**Adopt** `/plugin marketplace add wshobson/agents` → `/plugin install observability-monitoring`
**Status** 🔴 NET-NEW

#### Service-mesh bundle (Istio / Linkerd / mTLS)
**Source repo** wshobson/agents (36.1k⭐) — cloud-infrastructure plugin
**Category** DevOps / networking
**What it does** Istio traffic management, Linkerd patterns, zero-trust mTLS configuration, service-mesh observability.
**Why gamechanger** Net-new advanced networking layer. Relevant given the user's homelab/network skills (VLAN/WireGuard/BGP) — extends that into cloud-native service mesh.
**Adopt** `/plugin marketplace add wshobson/agents` → `/plugin install cloud-infrastructure`
**Status** 🔴 NET-NEW

#### Data-engineering bundle (Spark / dbt / Airflow / Great Expectations)
**Source repo** wshobson/agents (36.1k⭐) — data-engineering plugin
**Category** Data / pipelines
**What it does** Spark optimization, dbt transformation patterns, Airflow DAG patterns, data-quality frameworks (Great Expectations).
**Why gamechanger** 🟡 user has the astronomer-data plugin (Airflow/dbt/cosmos), so Airflow/dbt overlap — but Spark-optimization + Great-Expectations data-quality are net-new. Cherry-pick.
**Adopt** `/plugin marketplace add wshobson/agents` → `/plugin install data-engineering`
**Status** 🟡 PARTIAL (Spark + data-quality are net-new)

#### Monorepo / build bundle (Turborepo / Nx / Bazel)
**Source repo** wshobson/agents (36.1k⭐) — developer-essentials plugin
**Category** Dev tooling / build
**What it does** monorepo-management, nx-workspace-patterns, turborepo-caching, bazel-build-optimization (+ git-advanced-workflows, sql-optimization, debugging-strategies).
**Why gamechanger** No monorepo/Turborepo/Nx/Bazel skills in inventory. Essential for scaling multi-package JS/TS repos with computation caching.
**Adopt** `/plugin marketplace add wshobson/agents` → `/plugin install developer-essentials`
**Status** 🔴 NET-NEW

#### Backend event-sourcing bundle (CQRS / Saga / Temporal)
**Source repo** wshobson/agents (36.1k⭐) — backend-development plugin
**Category** Backend / distributed systems
**What it does** event-store-design, cqrs-implementation, projection-patterns, saga-orchestration, workflow-orchestration-patterns (Temporal) + temporal-python-testing.
**Why gamechanger** User has `backend-patterns` but nothing on event-sourcing/CQRS/Saga/Temporal — the patterns for durable, distributed workflows. Net-new architectural depth.
**Adopt** `/plugin marketplace add wshobson/agents` → `/plugin install backend-development`
**Status** 🔴 NET-NEW

#### Accessibility-compliance bundle (WCAG / screen readers)
**Source repo** wshobson/agents (36.1k⭐) — accessibility-compliance plugin
**Category** Frontend / a11y
**What it does** wcag-audit-patterns (WCAG 2.2, automated + manual), screen-reader-testing (NVDA/JAWS/VoiceOver).
**Why gamechanger** User's web/testing.md *requires* a11y checks but they have no a11y skill. WCAG 2.2 audit + screen-reader testing closes that compliance gap.
**Adopt** `/plugin marketplace add wshobson/agents` → `/plugin install accessibility-compliance`
**Status** 🔴 NET-NEW

#### Payment processing (Stripe / PayPal / PCI)

#### stripe/agent-toolkit + Stripe official skill
**Source repo** stripe/agent-toolkit (1.6k⭐, pushed 2026-05-28) + wshobson payment-processing
**Category** Payments / fintech
**What it does** Stripe-built toolkit for agents to create products, checkout, subscriptions, and webhooks; wshobson adds paypal-integration, pci-compliance, billing-automation.
**Why gamechanger** Zero payments coverage in inventory. If the user ever monetizes a project (their investor-materials/investor-outreach skills suggest they might), first-party Stripe integration is the fastest path. PCI-compliance skill keeps it safe.
**Adopt** Stripe via officialskills.sh; `/plugin install payment-processing` from wshobson/agents
**Status** 🔴 NET-NEW

#### Blockchain / web3 bundle (Solidity security / DeFi / NFT)
**Source repo** wshobson/agents (36.1k⭐) — blockchain-web3 plugin
**Category** Web3 / smart contracts
**What it does** solidity-security, defi-protocol-templates, nft-standards (ERC-721/1155), web3-testing (Hardhat/Foundry, mainnet forking).
**Why gamechanger** Inventory has scattered web3 ECC skills (defi-amm-security, evm-token-decimals) but no cohesive Solidity-security + Foundry-testing bundle. ⚠️ only adopt if web3 is a real interest.
**Adopt** `/plugin marketplace add wshobson/agents` → `/plugin install blockchain-web3`
**Status** 🟡 PARTIAL (some ECC web3 skills exist; this is more complete)

#### LLM-app development bundle (RAG / LangChain / vector tuning)
**Source repo** wshobson/agents (36.1k⭐) — llm-application-development plugin
**Category** AI / LLM engineering
**What it does** 8 skills: langchain-architecture, rag-implementation, llm-evaluation, embedding-strategies, similarity-search, vector-index-tuning (HNSW/IVF), hybrid-search.
**Why gamechanger** 🟡 user has `cost-aware-llm-pipeline`/`eval-harness`/`iterative-retrieval` but no dedicated RAG/vector-index-tuning skills. The HNSW/IVF tuning + hybrid-search skills are net-new and directly useful for their pinecone MCP work.
**Adopt** `/plugin marketplace add wshobson/agents` → `/plugin install llm-application-development`
**Status** 🟡 PARTIAL (vector tuning + hybrid search are net-new)

#### Vendor / SaaS official skills (via officialskills.sh — almost all net-new)

#### GSAP (official)
**Source repo** officialskills.sh / GSAP team
**Category** Frontend / animation
**What it does** Official GreenSock animation skill — timelines, ScrollTrigger, performant compositor-friendly motion.
**Why gamechanger** User's web/coding-style.md explicitly recommends GSAP ("`import('gsap')`") but they have no GSAP skill. First-party animation expertise = no more hallucinated GSAP APIs.
**Adopt** browse officialskills.sh → GSAP
**Status** 🔴 NET-NEW

#### Neon / Better Auth / Resend / Apollo GraphQL / MongoDB / DuckDB / Tinybird (official)
**Source repo** officialskills.sh (VoltAgent directory)
**Category** Backend / data / SaaS
**What it does** First-party skills: Neon (serverless Postgres branching), Better Auth (modern auth), Resend (transactional email), Apollo (GraphQL), MongoDB, DuckDB (in-process analytics), Tinybird (real-time analytics APIs).
**Why gamechanger** User has Postgres/Supabase but not Neon's branch-per-PR workflow; has `mcp-graphql` but not Apollo's skill; has clickhouse-io but not DuckDB/Tinybird for embedded/real-time analytics; **no email or modern-auth skill at all**. Each is a clean net-new integration.
**Adopt** browse https://officialskills.sh/ and install per-vendor
**Status** 🔴 NET-NEW (several distinct skills)

#### Datadog Labs (official)
**Source repo** officialskills.sh / Datadog Labs
**Category** Observability / SaaS
**What it does** Official Datadog skill for instrumentation, dashboards, monitors, and APM queries.
**Why gamechanger** Complements the open-source Prometheus/Grafana bundle with the leading commercial APM — net-new, no Datadog skill in inventory.
**Adopt** browse officialskills.sh → Datadog
**Status** 🔴 NET-NEW

#### Autonomous / multi-agent (user has Ralph/metaswarm — these are alternatives to study)

#### loki-mode
**Source repo** asklokesh/claudeskill-loki-mode (947⭐, pushed 2026-05-28)
**Category** Multi-agent / autonomous SDLC
**What it does** Spec→deployed-app autonomous framework: PRD/issue/OpenAPI/one-liner input, 5 AI providers, 11 quality gates, orchestrates many agents across swarms.
**Why gamechanger** 🟡 user has metaswarm (9-phase) + Ralph — but loki-mode's 5-provider + 11-gate design is a different point in the design space worth mining for ideas (esp. multi-provider routing, which aligns with their model-council). Not a replacement.
**Adopt** clone / `/plugin add`
**Status** 🟡 PARTIAL (study, don't duplicate)

#### get-shit-done (GSD)
**Source repo** gsd-build/get-shit-done (63.8k⭐, pushed 2026-05-27)
**Category** Spec-driven dev / context engineering
**What it does** Lightweight meta-prompting + spec-driven development system by TÂCHES — emphasizes context engineering over heavyweight orchestration.
**Why gamechanger** 🟡 the most-starred spec-driven system; a leaner counterpoint to metaswarm/superpowers. Worth installing to compare the philosophy even if not adopted wholesale.
**Adopt** `/plugin marketplace add gsd-build/get-shit-done`
**Status** 🟡 PARTIAL (alternative methodology)

#### Expanded superpowers skills (the user has CORE superpowers, NOT these community/lab additions)

#### Problem-solving thinking skills
**Source repo** obra/superpowers-skills (community)
**Category** Reasoning / meta
**What it does** A suite of structured-thinking skills the user doesn't have: collision-zone-thinking, inversion-exercise, scale-game, simplification-cascades, meta-pattern-recognition, when-stuck.
**Why gamechanger** User has core superpowers (brainstorming/plans/TDD) but **not** these lateral-thinking skills. `when-stuck` and `simplification-cascades` directly counter the user's documented "don't overcomplicate / BC RE stalled for weeks" failure mode.
**Adopt** `superpowers-marketplace` → superpowers-skills
**Status** 🔴 NET-NEW

#### Debugging depth skills (root-cause-tracing / defense-in-depth)
**Source repo** obra/superpowers-skills (community)
**Category** Debugging
**What it does** root-cause-tracing (trace a bug to its origin, not the symptom), defense-in-depth (layered safeguards), condition-based-waiting (deterministic waits vs sleeps), testing-anti-patterns.
**Why gamechanger** User has `systematic-debugging` but not these. `condition-based-waiting` solves their documented anti-pattern of sleep-based waits in automation/verifiers; `root-cause-tracing` deepens debugging beyond their current skill.
**Adopt** `superpowers-marketplace` → superpowers-skills
**Status** 🔴 NET-NEW

#### remembering-conversations / tracing-knowledge-lineages
**Source repo** obra/superpowers-skills (community)
**Category** Memory / research
**What it does** remembering-conversations (recall prior session context), tracing-knowledge-lineages (track how a conclusion was reached across sources).
**Why gamechanger** Complements the user's auto-memory/remember setup with superpowers-native recall, and tracing-knowledge-lineages fits their research-with-citations rigor preference.
**Adopt** `superpowers-marketplace` → superpowers-skills
**Status** 🔴 NET-NEW

#### Niche / domain

#### claude-scientific-skills (K-Dense) — non-bio subset
**Source repo** K-Dense-AI/claude-scientific-skills (26.4k⭐, pushed 2026-05-27)
**Category** Science / research
**What it does** 140 science skills + 100+ databases. The chemistry, physics, materials-science, and general-statistics skills sit outside the user's ToolUniverse (which is biomedical-focused).
**Why gamechanger** 🟡 heavy overlap with ToolUniverse on biology/medicine, but the non-bio science skills + alternate database coverage are net-new. Adopt selectively.
**Adopt** `/plugin marketplace add K-Dense-AI/claude-scientific-skills`
**Status** 🟡 PARTIAL (non-bio skills are net-new)

#### Expo / EAS skills
**Source repo** expo/skills (2.0k⭐, pushed 2026-05-27)
**Category** Mobile / React Native
**What it does** Official Expo skills for building Expo apps and using Expo Application Services (builds, OTA updates, submissions).
**Why gamechanger** User has native iOS/Android (Swift/Compose) but no cross-platform RN/Expo path. Expo is the fastest way to ship one codebase to both stores. ⚠️ only if RN is of interest.
**Adopt** `/plugin marketplace add expo/skills`
**Status** 🔴 NET-NEW

#### HeyGen / Higgsfield (AI avatar & character video)
**Source repo** heygen-com/skills (253⭐) / higgsfield-ai/skills (322⭐)
**Category** Creative / AI video
**What it does** HeyGen: AI avatar/talking-head video in 175+ languages with best-in-class lip-sync. Higgsfield: character-consistent video series via persistent "Soul ID" faces.
**Why gamechanger** Net-new generative-video niches beyond the user's sora/fal-ai. Relevant if they produce talking-head explainers or character content. ⚠️ both require vendor API keys.
**Adopt** `heygen-com/skills` / `higgsfield-ai/skills` via officialskills.sh
**Status** 🔴 NET-NEW (niche)

---

### Explicitly SKIPPED (already HAVE — listed so the gap analysis is auditable)

| Skill / collection | Why skipped |
|---|---|
| superpowers (core: brainstorming, writing-plans, executing-plans, TDD, systematic-debugging, subagent-driven-development, find-skills, writing-skills, etc.) | ✅ HAVE (bundled) |
| webapp-testing, playwright, playwright-interactive | ✅ HAVE |
| frontend-slides, slides, frontend-patterns | ✅ HAVE |
| pdf, spreadsheet, doc, article-writing | ✅ HAVE (generic — but Office docx/xlsx/pptx are net-new, see above) |
| mcp-builder (Anthropic) | ✅ HAVE equivalents: `mcp-server-patterns`, `mcp-server-dev:build-mcp-server`, `mcp-server-dev:build-mcp-app` |
| skill-creator | ✅ HAVE |
| imagegen, sora, fal-ai-media, videodb, video-editing, transcribe, speech | ✅ HAVE (creative-media basics) |
| affaan-m/everything-claude-code (ECC) | ✅ HAVE (already the user's primary harness) |
| repomix, codecov-cli, digitalocean-cli, graphql-cli | ✅ HAVE |
| huggingface, figma, sentry, notion, supabase, railway, netlify, firecrawl, aws-serverless, astronomer-data plugins | ✅ HAVE (marketplace plugins installed) |
| semgrep, security-review, security-scan, security-threat-model, llm-security, code-security | ✅ HAVE (ToB adds *methodology* on top) |
| Full RE stack (ida/ghidra/binary-ninja/frida/radare2/x64dbg/volatility/imhex/angr/etc.) | ✅ HAVE (extensive) |
| ToolUniverse 200+ biomedical skills | ✅ HAVE (K-Dense overlaps on bio) |

---

### Maintenance / verification notes
- Stars and push dates verified via `gh api repos/<owner>/<repo>` on **2026-05-28**.
- ⚠️ flags mark repos to re-check before relying: claude-d3js-skill (Oct 2025), ffuf_claude_skill (Oct 2025), AgriciDaniel/claude-video (10⭐, thin) — excluded from top picks in favor of digitalsamba's toolkit.
- "officialskills.sh" (VoltAgent) and "antigravity-awesome-skills" are *directories* — install individual skills from them rather than the whole catalog (context bloat).
- Install hygiene (per baoyu/wshobson docs + user's own MCP-reduction work): install skills **individually**, not whole marketplaces, to keep the always-loaded metadata footprint small.

---

## 5.5 — Workflows, plugins & agent harnesses


Research agent #5 of 7. Domain: whole frameworks AND copyable workflow patterns. Generated 2026-05-28.

**Dedup baseline:** User already runs metaswarm (9-phase orchestration), Ralph/ralph-orchestrator (autonomous loops), superpowers (TDD/brainstorm/plan/subagent/worktree skills), ECC (everything-claude-code), model-council, agentchattr, codex_consult, plus marketplace plugins (coderabbit, pr-review-toolkit, sentry, semgrep, plugin-dev, claude-md-management, skill-creator, codex, notion). Those are marked ✅ HAVE and given one line. Focus is on what is genuinely **additive**.

**Star-count note:** Counts are live `gh api .stargazers_count` as of 2026-05-28, cross-checked against exa fetch and (for superpowers) the live GitHub page. The Claude-Code ecosystem star counts exploded in early 2026 — superpowers really is ~211K now, not the "20K" that older awesome-lists still cite. Where a repo is suspiciously popular vs. substance, it is flagged.

Legend: ✅ HAVE / 🟡 PARTIAL (have something adjacent) / 🔴 NET-NEW-GAP

---

### A. Spec-Driven Development Frameworks (the biggest additive category)

#### github/spec-kit
**Source** https://github.com/github/spec-kit (⭐106,696; pushed 2026-05-26; very active, 200 contributors, 149 releases)
**Category** framework
**What it is** GitHub's official spec-driven-development toolkit. A `specify` CLI installs slash commands `/speckit.constitution` → `/speckit.specify` → `/speckit.clarify` → `/speckit.plan` → `/speckit.tasks` → `/speckit.analyze` → `/speckit.implement`. Specs are treated as the executable source of truth; a project "constitution" governs all downstream phases. Has an extensions+presets layering system (project-local > preset > extension > core) and works across 30+ agents.
**Why gamechanger** This is the canonical, vendor-backed discipline for turning a vague idea into a constitution + spec + plan + dependency-ordered task list with `[P]` parallel markers — before any code. The `/speckit.clarify` (structured coverage-based questioning) and `/speckit.analyze` (cross-artifact consistency check) gates are more rigorous than metaswarm's brainstorm→design flow at the *spec* layer. The "checklist = unit tests for English" idea is novel.
**Adopt** `uv tool install specify-cli`. Even if you keep metaswarm for execution, steal `/speckit.clarify` + `/speckit.analyze` + the constitution.md pattern as a front-end. Presets can enforce TDD task-ordering and mandatory security-review gates — composes with your existing gates.
**Status** 🟡 PARTIAL — you have notion-spec-to-implementation + metaswarm planning, but NOT spec-kit's constitution/clarify/analyze discipline or the executable-spec philosophy. High-value front-end.

#### bmad-code-org/BMAD-METHOD
**Source** https://github.com/bmad-code-org/BMAD-METHOD (⭐48,197; pushed 2026-05-26; very active)
**Category** framework
**What it is** "Breakthrough Method of Agile AI-Driven Development." A two-phase system: (1) Agentic Planning — dedicated Analyst/PM/Architect agents produce detailed, consistent PRDs and architecture docs through human-in-the-loop refinement; (2) Context-Engineered Development — a Scrum-Master agent transforms those plans into hyper-detailed "story files" embedding full context + implementation guidance so the Dev agent never loses the thread. Domain-agnostic "expansion packs" extend it beyond software.
**Why gamechanger** Its signature contribution is **eliminating planning-inconsistency and context-loss** — the story file carries everything the dev agent needs, which is a different solution to drift than metaswarm's per-unit re-prime. The Agile-ceremony framing (epics → stories → SM hand-off) is a mature alternative mental model. Massive community.
**Adopt** Study the story-file format and the SM→Dev hand-off. Port the "every story embeds full architectural context" idea into your metaswarm work-unit prompts to reduce re-priming cost.
**Status** 🔴 NET-NEW-GAP — distinct methodology; the story-file context-engineering pattern is genuinely additive.

#### automazeio/ccpm
**Source** https://github.com/automazeio/ccpm (⭐8,156; pushed 2026-03-18)
**Category** framework / harness
**What it is** Claude Code Project Management. Spec-driven workflow built **on GitHub Issues as the database**: PRD → epic → tasks become GitHub Issues, and multiple Claude agents work them in parallel git worktrees, each posting progress as issue comments so humans (and other agents) have a full audit trail. Five-phase flow with explicit "no vibe coding" guardrails.
**Why gamechanger** Uses GitHub Issues as durable, shareable, multi-agent task state — your team/PM gets visibility without a custom dashboard, and agents coordinate through issue comments rather than a private file. This is a cleaner persistence layer than `.beads/` for *team* settings, and the worktree-per-issue parallelism is concrete.
**Adopt** Even if you keep metaswarm, copy the "task = GitHub Issue + agent posts comments as a receipt trail" pattern for auditability. Pairs with claude-code-action for the CI half.
**Status** 🔴 NET-NEW-GAP — GitHub-Issues-as-agent-state is not in your stack.

#### shinpr/claude-code-workflows
**Source** https://github.com/shinpr/claude-code-workflows (⭐392; pushed 2026-05-21; active, 89 releases)
**Category** plugin-suite
**What it is** A polished plugin marketplace (`dev-workflows`, `-frontend`, `-fullstack`, `dev-skills`) where a `requirement-analyzer` **routes by task size** (1-2 files = direct; 3-5 = codebase-analyze; 6+ = full PRD→design→test→plan), each phase runs in a **fresh agent context**, and there's a dedicated **diagnosis recipe** (investigator → verifier with path-coverage loop → solver) plus a **reverse-engineering recipe** that auto-generates PRDs/Design-Docs from existing code.
**Why gamechanger** Three patterns worth stealing wholesale: (1) **complexity-based routing** so small tasks skip the heavy pipeline (metaswarm tends to apply full process broadly); (2) the **diagnosis loop** (investigator/verifier "Devil's Advocate" coverage check before proposing a fix) is a structured systematic-debugging upgrade; (3) **reverse-engineer-to-docs** for legacy code. Also a `metronome` add-on that *detects shortcut-taking behavior* and nudges step-by-step.
**Adopt** Read the `recipe-diagnose` and `recipe-reverse-engineer` skill prompts. Add a size-router in front of metaswarm. `codex-workflows` is the same author's Codex port.
**Status** 🔴 NET-NEW-GAP — complexity routing + diagnosis-coverage loop + reverse-eng docs are all additive.

#### Pimzino/claude-code-spec-workflow
**Source** https://github.com/Pimzino/claude-code-spec-workflow (⭐3,748; pushed 2025-09-07 — ~8 months stale)
**Category** framework
**What it is** Requirements → Design → Tasks → Implementation spec workflow with a bundled dashboard and steering documents. Auto-generates the spec scaffolding and tracks task completion.
**Why gamechanger** A lighter, dashboard-equipped alternative to spec-kit for solo work. The steering-document concept overlaps spec-kit's constitution.
**Adopt** Mine for the dashboard idea only; spec-kit is the stronger, maintained choice.
**Status** 🟡 PARTIAL / aging — spec-kit supersedes it; flagged stale.

#### gmickel/gmickel-claude-marketplace (Flow-Next)
**Source** https://github.com/gmickel/gmickel-claude-marketplace (⭐564; pushed 2026-04-08; active, 77 releases)
**Category** plugin-suite / framework
**What it is** "Flow-Next" — a **plan-first** AI workflow plugin with **zero external dependencies** for task tracking, worker subagents, a **Ralph autonomous mode** for overnight coding, **cross-model review gates**, **re-anchoring to prevent drift**, and **receipt-based gating**. Works across Claude Code, OpenAI Codex, and Factory Droid.
**Why gamechanger** This single repo bundles four patterns the task flagged as gamechangers: **re-anchoring/drift-prevention** (periodically re-inject the charter/plan so long runs don't wander), **receipt-based gating** (a step can't proceed without a verifiable receipt from the prior step), plan-first execution, and cross-model review — all with no infra. Its Ralph mode overlaps your ralph-orchestrator, but the *re-anchoring + receipt-gating* mechanics are concrete, copyable, and directly relevant to your autonomous-loop work.
**Adopt** Read the flow-next plugin's re-anchoring and receipt-gating implementation; port the re-anchor cadence into your Ralph/metaswarm loops to fight drift on long runs. Zero-dep design makes it easy to study.
**Status** 🟡 PARTIAL — Ralph mode overlaps installed ralph-orchestrator; the re-anchoring + receipt-based-gating patterns are NET-NEW and additive.

#### marcusgoll/Spec-Flow
**Source** https://github.com/marcusgoll/Spec-Flow (⭐85; pushed 2026-04-23)
**Category** framework
**What it is** Spec-driven workflow emphasizing quality gates, **token budgets**, and auditable artifacts from idea → launch.
**Why gamechanger** The explicit token-budget-per-phase idea is the one differentiator vs. spec-kit.
**Adopt** Steal the token-budget gating concept; low adoption otherwise.
**Status** 🟡 PARTIAL — niche; token-budget idea is the takeaway.

---

### B. Virtual Engineering Team / Whole-Org Plugin Suites

#### garrytan/gstack
**Source** https://github.com/garrytan/gstack (⭐~104K per gh api; pushed 2026-05-27; very active)
**Category** plugin-suite
**What it is** "Virtual engineering team as a startup org" — ~25 skills modeling CEO review → design review → eng review → QA → ship → canary deploy, with **freeze/guard/unfreeze file-protection PreToolUse hooks** and Playwright browser-based QA. `/autoplan` auto-chains the review phases; `/ship`→`/land-and-deploy`→`/canary` chains the deploy pipeline.
**Why gamechanger** Two additive pieces beyond metaswarm: (1) the **ship→deploy→canary→monitor→rollback** pipeline as skills (metaswarm stops at PR); (2) **freeze/guard file-locking hooks** that hard-block edits to protected files. The CEO/business-review layer above eng review is a perspective metaswarm lacks.
**Adopt** Port the canary-deploy monitoring loop and the freeze/guard hooks. (Caveat from the source: guard enforcement only works in Claude Code, not Codex.)
**Status** 🔴 NET-NEW-GAP for the deploy/canary/freeze pieces; review-gate overlaps metaswarm.

#### affaan-m/everything-claude-code (ECC)
**Source** https://github.com/affaan-m/everything-claude-code (⭐~197K per gh api; very active)
**Category** plugin-suite
**What it is** 28 agents, 59 commands, 116 skills, hooks across 7 event groups, 13-language rules, autonomous loop mgmt.
**Status** ✅ HAVE — this is your installed ECC. No action.

#### obra/superpowers
**Source** https://github.com/obra/superpowers (⭐~211K live; very active)
**Category** plugin-suite
**What it is** Auto-triggering skills for TDD, brainstorming, plan-then-execute, subagent-driven dev, parallel dispatch, worktrees, code-review loops.
**Status** ✅ HAVE — installed. No action.

#### sangrokjung/claude-forge
**Source** https://github.com/sangrokjung/claude-forge (⭐715; pushed 2026-05-20)
**Category** plugin-suite
**What it is** "oh-my-zsh for Claude Code" — 11 agents, 36 commands, 15 skills, and a **6-layer security hook system**.
**Why gamechanger** The 6-layer security-hook stack is the differentiator — a defense-in-depth PreToolUse pattern more layered than typical single-guard hooks.
**Adopt** Mine the security-hook layering; the rest overlaps ECC/superpowers.
**Status** 🟡 PARTIAL — security-hook layers additive; framework overlaps.

#### wshobson/agents
**Source** https://github.com/wshobson/agents (⭐36,075; pushed 2026-05-26; very active)
**Category** plugin-suite
**What it is** One of the largest curated **subagent + multi-agent-orchestration** collections — specialized role agents with coordinated task execution and (companion repo `commands`) orchestration slash-commands.
**Why gamechanger** A huge, maintained library of battle-tested agent definitions you can cherry-pick. Even with ECC's 28 agents, wshobson's catalog covers roles/domains you may lack and is a reference for agent-prompt quality.
**Adopt** Cherry-pick individual agent .md files into your `~/.claude/agents/`.
**Status** 🟡 PARTIAL — you have many agents; this is a parts bin for gaps.

#### pcatattacks/solopreneur-plugin
**Source** https://github.com/pcatattacks/solopreneur-plugin (⭐12 — very low adoption)
**Category** plugin-suite
**What it is** "Virtual company": 6 agents, 16 skills, full discover→spec→backlog→design→build→review→ship lifecycle with a **decision journal** and an **observer protocol**, plus agent "kickoff meetings" where agents debate approach.
**Why gamechanger** The decision-journal + observer-protocol + agents-debate-before-building ideas are interesting patterns.
**Adopt** Pattern-mine only (decision journal, kickoff debate). **Flag:** 12 stars — treat as idea source, not a dependency.
**Status** 🟡 PARTIAL / low-signal — patterns additive, adoption negligible.

#### TheWayWithin/BOS-AI & cloudrepo-io/founder-os
**Source** https://github.com/TheWayWithin/BOS-AI (⭐4) ; https://github.com/cloudrepo-io/founder-os (⭐11)
**Category** framework (business-OS)
**What it is** Markdown-as-OS "run a business with Claude" systems. Founder-OS is queue-based (`/queue:add`→`/queue:work`→`/founder:review`) with goal-backward verification; BOS-AI has 42 agents/183 "missions."
**Why gamechanger** The **queue-based autonomous task pickup with blocked_by dependency ordering** (founder-os) is the one reusable harness idea.
**Adopt** Steal the markdown task-queue + goal-backward verification pattern. **Flag:** both near-zero stars despite "Codex-verified counts" in awesome-lists — low-signal, do not adopt wholesale.
**Status** 🟡 PARTIAL / low-signal.

---

### C. CI/CD & PR-Automation Harnesses

#### anthropics/claude-code-action
**Source** https://github.com/anthropics/claude-code-action (⭐7,773; pushed 2026-05-23; very active, official, 197 releases)
**Category** harness (GitHub Actions)
**What it is** Official GitHub Action that runs Claude Code inside CI. Auto-detects mode from context (@claude mentions, issue assignment, or explicit automation prompts), runs on your own runner, supports Anthropic/Bedrock/Vertex/Foundry auth, emits structured JSON outputs that become Action outputs, and has a Solutions Guide of ready patterns (auto PR review, path-specific reviews, external-contributor handling, scheduled maintenance, issue triage, docs-sync, security review).
**Why gamechanger** Your entire stack (metaswarm/Ralph/ECC) is **local-only**. This moves agents server-side and event-driven: PR opened → auto review; issue labeled → auto triage; cron → repo health. `/install-github-app` sets it up in minutes. This is the missing CI surface.
**Adopt** Run `/install-github-app`, then copy the Solutions-Guide workflow YAMLs for auto-PR-review + security-review. Compose with your local gates (local pre-PR, CI post-PR).
**Status** 🔴 NET-NEW-GAP — no server-side/event-driven agent layer in your inventory.

#### OneRedOak/claude-code-workflows
**Source** https://github.com/OneRedOak/claude-code-workflows (⭐3,808; pushed 2025-09-14 — ~8 months stale)
**Category** workflow-pattern collection
**What it is** Three battle-tested workflows from an AI-native startup: **Code Review** (dual-loop: slash command + GitHub Action auto-reviews PRs for syntax/completeness/style/bugs), **Security Review** (OWASP-aligned, severity-classified findings + GH Action), and **Design Review** (Playwright-MCP browser automation + specialized agents checking UI/UX consistency, accessibility, visual diffs before prod).
**Why gamechanger** The **automated Design Review gate using Playwright MCP** (open real pages, screenshot, validate against design standards) is the standout — a *visual/UX* review gate, distinct from metaswarm's text-based design-review-gate. This is the origin of the now-widespread "design-review subagent" pattern.
**Adopt** Port the design-review agent + Playwright flow into your frontend work (you have the playwright plugin already). Mine the dual-loop code-review structure.
**Status** 🟡 PARTIAL — code/security review overlaps your coderabbit/pr-review-toolkit; the **visual design-review gate is NET-NEW**. Flagged stale but patterns are timeless.

#### hamelsmu/claude-review-loop
**Source** https://github.com/hamelsmu/claude-review-loop (⭐677; pushed 2026-03-15)
**Category** workflow-pattern / plugin
**What it is** A **Stop-hook that blocks Claude's exit** until an independent Codex review runs. On `/review-loop`, Claude implements, then the Stop hook prepares a Codex runner and refuses to let the session end; Claude runs Codex (up to 4 parallel sub-agents: diff/holistic/Next.js/UX), Codex consolidates findings to `reviews/review-*.md`, Claude addresses them, then exits.
**Why gamechanger** The **Stop-hook-as-gate** mechanic is the reusable gem: it *forces* a cross-model review before completion at the harness level, not by convention. You have codex_consult, but this wires it as an inescapable exit gate. Inspired by Ralph-Wiggum + Ryan Carson's "compound engineering loop."
**Adopt** Copy the Stop-hook pattern to enforce your codex-review before any task is allowed to finish. ~5 files of shell.
**Status** 🔴 NET-NEW-GAP — Stop-hook-blocks-exit-until-cross-model-review is a harness pattern you don't have.

#### gh-fix-ci / pr-review-toolkit / coderabbit (installed)
**Source** ECC skills + marketplace plugins
**Status** ✅ HAVE — `gh-fix-ci`, `gh-address-comments`, `handle-pr-comments`, coderabbit, pr-review-toolkit already cover CI-fix and PR-comment handling. One line.

---

### D. Parallel / Worktree / Isolation Harnesses

#### dagger/container-use
**Source** https://github.com/dagger/container-use (⭐3,804; pushed 2026-02-23 — ~3 months, Dagger-backed, early-dev)
**Category** harness
**What it is** MCP server giving each agent a **fresh isolated container** on its own git branch (powered by Dagger). Multiple agents run truly in parallel without conflicts; you get full command history/logs of what the agent *actually did* (not what it claims), can drop into any agent's terminal, and review via plain `git checkout`. Works with any MCP agent.
**Why gamechanger** Worktrees (which you have via superpowers) isolate the *filesystem*; container-use isolates the *entire runtime* — different deps, safe destructive experiments, instant discard. The "see what the agent actually ran" log is a trust/verification upgrade over receipts.
**Adopt** Windows: `curl -fsSL https://raw.githubusercontent.com/dagger/container-use/main/install.sh | bash` (WSL/Git-Bash) or grab the release binary; then `claude mcp add container-use -- container-use stdio`. Use for risky parallel experiments where worktrees aren't enough isolation.
**Status** 🔴 NET-NEW-GAP — container-level (not just worktree) isolation. Flagged: early-dev, last release Aug 2025.

#### smtg-ai/claude-squad
**Source** https://github.com/smtg-ai/claude-squad (⭐7,650; pushed 2026-05-18; active)
**Category** harness (TUI)
**What it is** A tmux+git-worktrees TUI (`cs`) to manage **many** background agents (Claude/Codex/Gemini/Aider) at once — each in its own isolated worktree, with yolo/auto-accept, per-session diff review, and commit/push/checkout controls from one terminal.
**Why gamechanger** A purpose-built cockpit for *running N agents overnight in parallel* and triaging their diffs the next morning. Complements Ralph (single autonomous loop) with breadth (many concurrent tasks). Your agentchattr coordinates chat; claude-squad coordinates parallel *coding sessions*.
**Adopt** Windows: `curl -fsSL https://raw.githubusercontent.com/smtg-ai/claude-squad/main/install.sh | bash` (WSL/Git-Bash) or scoop/manual binary install (it's a Go binary `cs`); requires tmux + gh. Use to fan out independent tasks across worktrees and review diffs in one place.
**Status** 🔴 NET-NEW-GAP — multi-session parallel cockpit; distinct from Ralph and agentchattr.

#### Dicklesworthstone/claude_code_agent_farm
**Source** https://github.com/Dicklesworthstone/claude_code_agent_farm (⭐838; pushed 2026-04-06)
**Category** harness
**What it is** Runs a "farm" of many Claude Code agents in parallel via tmux, each chewing through a shared work list (bug-fixing or coverage campaigns), with orchestration scripts and a settings template.
**Why gamechanger** A concrete recipe for **swarm work on a backlog** (e.g., "fix all lint errors across the monorepo") — many agents, one queue. Lighter than container-use, more batch-oriented than claude-squad.
**Adopt** Mine the tmux orchestration script + work-list-chunking approach for large mechanical campaigns.
**Status** 🟡 PARTIAL — overlaps Ralph/squad conceptually; the backlog-swarm script is the additive bit.

#### superpowers worktrees / using-git-worktrees / dispatching-parallel-agents (installed)
**Status** ✅ HAVE — you have worktree + parallel-dispatch skills. claude-squad/container-use are the *tooling* layer above them.

---

### E. Multi-Agent Orchestration & Cross-Model

#### ruvnet/claude-flow (now "ruflo")
**Source** https://github.com/ruvnet/claude-flow → redirects to ruvnet/ruflo (⭐56,011; pushed 2026-05-28; very active, 1,495 releases)
**Category** framework
**What it is** Heavily-marketed multi-agent "swarm intelligence" orchestration: hive-mind topologies, RAG, self-learning swarms, MCP server, claims 84.8% SWE-bench + "352x WASM speedup" + 75% cost savings.
**Why gamechanger** Conceptually it pushes swarm topologies (mesh/hierarchical) further than metaswarm.
**Adopt** **CAUTION — flagged inflated.** The project's *own* Issue #653 ("85% of MCP Tools Are Mock/Stub Implementations") documents that most tools return fake success without doing work; the SWE-bench numbers are self-reported and unverified vs. the real 2026 leaderboard (Opus 4.7 ~87.6%). 56K stars + 1,495 releases signal churn/marketing more than reliability. Read the topology *ideas*; do not adopt as a dependency.
**Status** 🟡 PARTIAL / ⚠️ INFLATED — topology concepts only; substance questionable. You already have metaswarm + model-council for real orchestration.

#### catlog22/Claude-Code-Workflow
**Source** https://github.com/catlog22/Claude-Code-Workflow (⭐2,051; pushed 2026-05-14; active)
**Category** framework
**What it is** JSON-driven multi-agent "cadence-team" framework with CLI orchestration across **Gemini/Qwen/Codex** and a context-first architecture.
**Why gamechanger** JSON-defined cadence (vs. metaswarm's prompt-driven phases) is a different declarative-orchestration approach; multi-CLI delegation overlaps your codex_consult/model-council.
**Adopt** Mine the JSON workflow-definition schema if you want declarative pipelines.
**Status** 🟡 PARTIAL — overlaps model-council/codex_consult; declarative-JSON angle is the new bit.

#### team-attention/agent-council
**Source** https://github.com/team-attention/agent-council (⭐136; pushed 2025-12-24 — stale)
**Category** plugin
**What it is** Orchestrates Claude + Codex CLI + Gemini CLI to give diverse perspectives on the same task.
**Status** ✅ HAVE (equivalent) — your model-council (D:\model-council, 7 strategies) + codex_consult already do cross-model councils. Flagged stale. No action.

#### kingbootoshi/codex-orchestrator
**Source** https://github.com/kingbootoshi/codex-orchestrator (⭐299; pushed 2026-05-28; active)
**Category** harness
**What it is** Delegates tasks to OpenAI Codex agents via tmux sessions, designed to be driven by Claude Code as orchestrator.
**Status** ✅ HAVE (equivalent) — codex_consult / Agent Lanes / agentchattr cover Claude→Codex delegation. One line.

#### yohey-w/multi-agent-shogun
**Source** https://github.com/yohey-w/multi-agent-shogun (⭐1,312; pushed 2026-05-23; active)
**Category** harness
**What it is** tmux-based hierarchical multi-agent system with a shogun→karo→ashigaru (general→officer→soldier) command tree for parallel task farming.
**Why gamechanger** The explicit **3-tier command hierarchy** (one planner, several managers, many workers) is a clean tmux orchestration topology.
**Adopt** Mine the hierarchy + tmux wiring if you want a structured worker pyramid.
**Status** 🟡 PARTIAL — topology idea additive; overlaps Ralph/squad tooling.

---

### F. Context / Memory / Drift-Prevention Harnesses

#### thedotmack/claude-mem
**Source** https://github.com/thedotmack/claude-mem (⭐79,337; pushed 2026-05-28; very active)
**Category** plugin (memory)
**What it is** Auto-captures everything Claude does, compresses it via the Agent SDK, and **injects relevant context back into future sessions** — persistent cross-session memory with zero manual curation.
**Why gamechanger** Your auto-memory (MEMORY.md) + remember plugin are *hand/heuristic* curated; claude-mem does **automatic AI compression + relevance-ranked re-injection** at scale across all sessions. Big adoption.
**Adopt** Trial alongside your existing memory; compare its auto-compression to your manual MEMORY.md. Watch for overlap/conflict with the remember plugin.
**Status** 🟡 PARTIAL — you have memory systems, but not automatic compress-and-reinject of full session history.

#### parcadei/Continuous-Claude-v3
**Source** https://github.com/parcadei/Continuous-Claude-v3 (⭐3,792; pushed 2026-01-26 — ~4 months)
**Category** harness (context engineering)
**What it is** Hook-based context management that maintains state across sessions via **ledgers and handoffs**, runs MCP execution **without polluting context**, and gives each agent an isolated context window.
**Why gamechanger** The **ledger + handoff** pattern (structured state doc that survives compaction and hands off to the next session) is exactly a drift/continuity solution — adjacent to your `.beads/` recovery but more formalized as a continuous-session protocol.
**Adopt** Compare its ledger/handoff schema to your `.beads/context/execution-state.md`; adopt whichever is more robust for surviving compaction.
**Status** 🟡 PARTIAL — overlaps `.beads/` recovery; the formal handoff protocol may improve it.

#### peterkrueck/Claude-Code-Development-Kit
**Source** https://github.com/peterkrueck/Claude-Code-Development-Kit (⭐1,354; pushed 2026-05-18; active)
**Category** framework
**What it is** "Handle context at scale" kit combining hooks + MCP + sub-agents working together, with a documented 3-tier docs architecture (foundational → component → feature CLAUDE.md files) so large codebases stay navigable.
**Why gamechanger** The **tiered CLAUDE.md / docs architecture** for big repos is a concrete context-engineering pattern that scales better than one flat CLAUDE.md.
**Adopt** Adopt the 3-tier CLAUDE.md layout for any large project.
**Status** 🟡 PARTIAL — tiered-docs pattern is additive context engineering.

#### kingbootoshi/cartographer
**Source** https://github.com/kingbootoshi/cartographer (⭐584; pushed 2026-05-13; active)
**Category** plugin
**What it is** Maps and documents codebases of any size using **parallel AI subagents** — produces a navigable map/docs of an unfamiliar repo.
**Why gamechanger** Onboarding-to-a-new-codebase via parallel mapping subagents — a focused workflow you don't have a dedicated tool for (ECC has search-first but not a mapper).
**Adopt** Run on unfamiliar repos before starting work.
**Status** 🔴 NET-NEW-GAP — dedicated parallel codebase-mapping tool.

---

### G. Model Routing, Cost & Observability Harnesses

#### musistudio/claude-code-router
**Source** https://github.com/musistudio/claude-code-router (⭐34,467; pushed 2026-03-04; active)
**Category** harness (proxy)
**What it is** A local proxy (`ccr code`) that routes Claude Code requests to **different models per scenario** — `default`/`background`/`think`/`longContext`/`webSearch` each map to a chosen provider/model (OpenRouter, DeepSeek, Ollama, Gemini, GLM, Qwen…). Supports request/response transformers, custom-router JS, per-subagent model override (`<CCR-SUBAGENT-MODEL>`), and GitHub Actions integration for off-peak cost runs.
**Why gamechanger** Different axis from your model-council/model-route: this routes at the **proxy/request layer** to send cheap/background work to local or budget models while keeping Anthropic for the hard stuff — a major cost lever. The `longContextThreshold` auto-switch and per-subagent model pinning are powerful.
**Adopt** `npm i -g @musistudio/claude-code-router`; map `background`→Ollama/DeepSeek, keep `default`/`think`→Claude. Pairs with cost-aware-llm-pipeline skill.
**Status** 🔴 NET-NEW-GAP — proxy-layer per-scenario model routing for cost is not in your stack (model-council is orchestration-layer, not request-routing).

#### ryoppippi/ccusage
**Source** https://github.com/ryoppippi/ccusage (⭐14,975; pushed 2026-05-27; very active)
**Category** harness (observability)
**What it is** CLI that parses local Claude Code JSONL logs into token/cost reports — daily/monthly/session/blocks breakdowns, model split, live monitoring. Zero-setup `npx ccusage`.
**Why gamechanger** Direct cost/usage visibility across all your heavy automation (Ralph loops, metaswarm, parallel agents burn tokens). Essential telemetry for a power user running autonomous loops.
**Adopt** `npx ccusage@latest` for instant cost reports; add to a daily habit.
**Status** 🔴 NET-NEW-GAP — no token/cost reporting tool in inventory.

#### jarrodwatts/claude-hud
**Source** https://github.com/jarrodwatts/claude-hud (⭐23,936; pushed 2026-05-28; very active)
**Category** plugin (observability)
**What it is** Real-time dashboard overlay showing context usage, active tools, running agents, and todo progress.
**Why gamechanger** Live situational awareness while orchestrating many agents — see context fill and running subagents at a glance. Complements your agent-monitor tool (D:\agent-monitor) but as an in-session HUD.
**Adopt** Install as a plugin; compare to your agent-monitor.
**Status** 🟡 PARTIAL — you built agent-monitor; this is an in-session HUD variant.

#### luongnv89/cc-context-stats
**Source** https://github.com/luongnv89/cc-context-stats (⭐106; pushed 2026-04-28)
**Category** harness (status line)
**What it is** Status-bar "Model Intelligence (MI)" score calibrated from Anthropic's MRCR benchmark per model, with color-coded zones telling you **when to plan, when to code-only, and when to start fresh** as context grows.
**Why gamechanger** Turns context-degradation into an actionable signal — directly relevant to your strategic-compact / context-budget concerns on long sessions.
**Adopt** Add to status line for a "context health" gauge; pairs with strategic-compact skill.
**Status** 🔴 NET-NEW-GAP — MRCR-calibrated context-health signal is novel.

#### starbaser/ccproxy
**Source** https://github.com/starbaser/ccproxy (⭐349; pushed 2026-05-25; active)
**Category** harness (proxy)
**What it is** Proxy that hooks Claude Code requests for model routing, request/response modification, and **LangFuse tracing**.
**Why gamechanger** The LangFuse observability integration (full traced requests) is the differentiator vs. claude-code-router.
**Adopt** Use if you want LangFuse traces of agent runs; otherwise claude-code-router covers routing.
**Status** 🟡 PARTIAL — routing overlaps ccr; LangFuse tracing is the additive bit.

---

### H. Comprehensive Reference Configs & Showcases (parts bins)

#### diet103/claude-code-infrastructure-showcase
**Source** https://github.com/diet103/claude-code-infrastructure-showcase (⭐9,671; pushed 2026-04-17)
**Category** plugin-suite (reference)
**What it is** Full reference of skill auto-activation + hooks + agents working as one integrated system.
**Why gamechanger** A worked example of the *integration* glue (how hooks trigger skills trigger agents) — useful to compare against your ECC wiring.
**Adopt** Read for hook→skill→agent wiring patterns.
**Status** 🟡 PARTIAL — reference; overlaps ECC.

#### ChrisWiles/claude-code-showcase
**Source** https://github.com/ChrisWiles/claude-code-showcase (⭐5,929; pushed 2026-01-06 — ~4 months)
**Category** reference config
**What it is** Project config combining hooks, skills, agents, commands, **and GitHub Actions workflows** in one repo.
**Why gamechanger** Shows local-config + CI-workflows together (the bridge between your local stack and claude-code-action).
**Adopt** Mine the GitHub Actions + local-config integration.
**Status** 🟡 PARTIAL — integration reference.

#### anthropics/claude-cookbook
**Source** https://github.com/anthropics/claude-cookbook (⭐44,511; pushed 2026-05-28; official, very active)
**Category** reference (patterns)
**What it is** Anthropic's official cookbook of recipes/patterns for building with Claude (agents, tool use, RAG, evals, etc.).
**Why gamechanger** Authoritative source for canonical agent/tool-use/eval patterns — the ground truth your custom harnesses should align with.
**Adopt** Reference for eval-harness and agent-design patterns.
**Status** 🟡 PARTIAL — reference, not a workflow; high authority.

#### centminmod/my-claude-code-setup
**Source** https://github.com/centminmod/my-claude-code-setup (⭐2,366; pushed 2026-05-24; active)
**Category** reference config
**What it is** A heavily-documented personal Claude Code setup (hooks, commands, memory bank, statusline) shared as a template.
**Adopt** Compare hook/statusline choices to yours.
**Status** 🟡 PARTIAL — personal-config parts bin.

#### disler/claude-code-hooks-mastery
**Source** https://github.com/disler/claude-code-hooks-mastery (⭐3,717; pushed 2026-03-04)
**Category** workflow-pattern (hooks)
**What it is** Reference implementation covering all 8 Claude Code hook event types with working examples (security guards, TTS notifications, sub-agent control).
**Why gamechanger** The definitive hooks tutorial — directly upgrades your hook game (you use hooks via hookify/ECC but this covers all event types end-to-end).
**Adopt** Read to fill gaps in your hook coverage (e.g., SubagentStop, PreCompact, Notification).
**Status** 🟡 PARTIAL — you have hookify; this is the comprehensive hook reference.

---

### I. High-Value WORKFLOW PATTERNS (copy the technique, no install)

#### Spec → Clarify → Analyze → Tasks cascade
**Source** spec-kit
**Category** workflow-pattern
**What it is** Front-load a constitution + spec, run a **structured clarify** (coverage-based Q&A recorded in the spec), then a **cross-artifact analyze** (consistency/coverage check) BEFORE tasks/implement.
**Why gamechanger** Catches under-specification and spec/plan/task drift before code — cheaper than metaswarm's later review gates.
**Adopt** Add `/clarify` + `/analyze` steps in front of metaswarm planning.
**Status** 🔴 NET-NEW-GAP.

#### Stop-hook-as-completion-gate
**Source** hamelsmu/claude-review-loop; gstack freeze hooks
**Category** workflow-pattern
**What it is** Use a Stop hook to **block session exit** until a required check (cross-model review, coverage, lint) passes — enforcement at the harness level, not by convention.
**Why gamechanger** Makes "no task finishes without independent review" structurally unavoidable. Your CLAUDE.md *asks* for codex review; this *forces* it.
**Adopt** Wire a Stop hook that runs codex_consult and blocks until findings are addressed.
**Status** 🔴 NET-NEW-GAP.

#### Complexity-based pipeline routing
**Source** shinpr/claude-code-workflows
**Category** workflow-pattern
**What it is** A `requirement-analyzer` classifies task size (1-2 / 3-5 / 6+ files) and routes to direct-impl vs. full PRD→design→plan, so small tasks skip heavy process.
**Why gamechanger** Saves tokens/time; metaswarm tends to apply broad process. Adds a cheap fast-path.
**Adopt** Add a size-classifier gate before `/start-task` chooses depth.
**Status** 🔴 NET-NEW-GAP.

#### Diagnosis loop (investigator → verifier coverage → solver)
**Source** shinpr `recipe-diagnose`
**Category** workflow-pattern
**What it is** Bug-fix flow that maps execution paths (investigator), checks **path-coverage with a Devil's-Advocate verifier** (re-investigates if insufficient), then solver does tradeoff analysis before any fix.
**Why gamechanger** A structured upgrade to systematic-debugging that *proves* coverage before proposing fixes.
**Adopt** Layer the verifier-coverage step into your systematic-debugging skill.
**Status** 🔴 NET-NEW-GAP.

#### Visual design-review gate (Playwright MCP)
**Source** OneRedOak design-review; gstack QA
**Category** workflow-pattern
**What it is** A subagent opens real pages via Playwright MCP, screenshots key breakpoints, and validates UI/UX/accessibility against design standards before merge.
**Why gamechanger** A *visual* gate (metaswarm's design-review is text-based). Catches layout/a11y regressions automatically.
**Adopt** You have playwright + frontend rules — add a design-review agent that screenshots + grades.
**Status** 🔴 NET-NEW-GAP (the visual half).

#### Reverse-engineer-to-docs
**Source** shinpr `recipe-reverse-engineer`; cartographer
**Category** workflow-pattern
**What it is** Point agents at undocumented/legacy code; they discover scope, generate PRDs + Design Docs verified against the actual code, making the codebase "AI-friendly."
**Why gamechanger** Onboarding + legacy modernization workflow you lack a dedicated recipe for.
**Adopt** Run before working in any unfamiliar repo.
**Status** 🔴 NET-NEW-GAP.

#### Per-scenario model routing for cost
**Source** claude-code-router
**Category** workflow-pattern
**What it is** Route `background`/`longContext`/`think` to cheap/local/specialist models, keep Claude for hard reasoning; auto-switch on context-length threshold.
**Why gamechanger** Direct token-cost reduction on your heavy autonomous loops.
**Adopt** Configure ccr Router map; pair with cost-aware-llm-pipeline.
**Status** 🔴 NET-NEW-GAP.

#### Ledger + handoff for session continuity
**Source** Continuous-Claude-v3; BMAD story-files
**Category** workflow-pattern
**What it is** Maintain a structured ledger/handoff doc that survives compaction and hands full context to the next session/agent (BMAD's variant embeds full context in each story file).
**Why gamechanger** Drift/continuity solution complementary to `.beads/` recovery.
**Adopt** Harden your `.beads/context/execution-state.md` with explicit handoff sections.
**Status** 🟡 PARTIAL — improves existing recovery.

#### GitHub-Issues-as-agent-state + receipt comments
**Source** ccpm
**Category** workflow-pattern
**What it is** Tasks live as GitHub Issues; agents post progress as issue comments (a public receipt trail); worktree-per-issue for parallelism.
**Why gamechanger** Durable, shareable, auditable multi-agent state for team settings — receipt-based gating in the open.
**Adopt** Mirror metaswarm work-units to GitHub Issues with agent-comment receipts.
**Status** 🔴 NET-NEW-GAP.

#### Queue-based autonomous task pickup
**Source** founder-os; claude_code_agent_farm
**Category** workflow-pattern
**What it is** A markdown/issue queue with `blocked_by` ordering; agents autonomously pick the next unblocked item, work it, mark done, repeat — for backlog swarms.
**Why gamechanger** Scales "fix everything in this list" across many agents without manual dispatch.
**Adopt** Add a queue file + pickup loop for mechanical campaigns (lint, coverage, migrations).
**Status** 🟡 PARTIAL — Ralph does single-goal loops; queue-pickup is the multi-item variant.

#### Off-peak / scheduled autonomous runs
**Source** claude-code-action (scheduled maintenance) + claude-code-router (off-peak cost)
**Category** workflow-pattern
**What it is** Cron-triggered CI agents for repo health/maintenance + routing those runs to cheap models during off-peak hours.
**Why gamechanger** Overnight autonomous coding at lower cost, server-side.
**Adopt** Combine GH Action `schedule:` triggers with ccr cheap-model routing.
**Status** 🔴 NET-NEW-GAP (the scheduled-CI half).

---

### Summary of the strongest NET-NEW additions for this user

Beyond metaswarm/Ralph/superpowers/ECC/model-council, the genuinely additive items, ranked:

1. **github/spec-kit** (⭐107K) — constitution + `/clarify` + `/analyze` spec discipline as a front-end to metaswarm.
2. **anthropics/claude-code-action** (⭐7.8K, official) — the missing server-side/event-driven CI agent layer (PR review, triage, scheduled maintenance).
3. **musistudio/claude-code-router** (⭐34K) — proxy-layer per-scenario model routing → big cost lever on heavy loops.
4. **smtg-ai/claude-squad** (⭐7.7K) — multi-session parallel agent cockpit (overnight fan-out + diff triage), complements Ralph's single loop.
5. **ryoppippi/ccusage** (⭐15K) — token/cost telemetry for all the autonomous burn (you have none).
6. **hamelsmu/claude-review-loop pattern** (⭐677) — Stop-hook-blocks-exit-until-cross-model-review (forces your codex review structurally).
7. **shinpr/claude-code-workflows patterns** (⭐392) — complexity routing + diagnosis-coverage loop + reverse-engineer-to-docs.
8. **dagger/container-use** (⭐3.8K) — container-level (not just worktree) isolation for risky parallel experiments.

**Honorable mentions:** OneRedOak's visual design-review gate (Playwright MCP), BMAD-METHOD story-file context engineering, ccpm's GitHub-Issues-as-agent-state, cc-context-stats MRCR context-health signal, claude-mem auto-compress memory.

**Flagged as inflated/low-signal:** ruvnet/claude-flow (⭐56K but Issue #653 = ~85% mock tools, unverified SWE-bench claims); BOS-AI (⭐4), founder-os (⭐11), solopreneur-plugin (⭐12) — featured in awesome-lists but near-zero adoption, mine for patterns only. Stale-but-valuable: OneRedOak (pushed 2025-09), claudia (2025-10), Pimzino spec-workflow (2025-09).

---

## 5.6 — Prompting, context engineering & memory (full playbook w/ citations)


> Research agent #6. Target reader: a Claude Code power user (Windows 11) who already runs ECC, metaswarm, superpowers, Ralph, model-council, auto-memory, the `remember` plugin, `claude-reflect`, the official `memory` MCP, and skills like `strategic-compact` / `context-budget` / `prompt-optimizer`. Stated pain: *"I'm having problems even prompting correctly, or maintaining a proper workflow, without Claude failing to remember or losing context and the good flow then breaks and everything seems lost."*
>
> **Diagnosis (read this first).** The pain is NOT a missing tool. It is (a) workflow discipline — ad-hoc prompting instead of Explore→Plan→Code→Verify, and (b) **self-inflicted context rot**: this user's global `~/.claude/CLAUDE.md` + `rules/common/*.md` (9 files) + `rules/web/*.md` (8 files) + project `CLAUDE.md` + a large `MEMORY.md` are ALL loaded before any prompt. Anthropic's own guidance is **<200 lines per CLAUDE.md for adherence** ([memory docs](https://code.claude.com/docs/en/memory)). Loading many KB of rules every turn fragments the prompt cache and dilutes attention — the exact "flow breaks / everything lost" symptom. **The PLAYBOOK below is the deliverable; the tools are secondary.** Several "memory tools" are deliberately flagged 🟡/conflict because this user already triple-captures memory and adding more capture layers makes it worse, not better.

Status legend: ✅ HAVE (already installed/used) · 🟡 PARTIAL (overlaps existing; adopt selectively) · 🔴 NET-NEW-GAP (genuinely missing, worth adopting).

---

### TOOLS

#### Anthropic Prompt Engineering Guide ("Prompting best practices")
- **Source:** https://docs.claude.com/en/docs/build-with-claude/prompt-engineering · https://docs.anthropic.com/claude/docs/chain-prompts (the living "Prompting best practices" page, updated for Opus 4.7)
- **Category:** Prompting / reference
- **What:** The single canonical reference for Claude prompting — clarity, examples (multishot), XML structuring, role prompting, chain-of-thought, prompt chaining, plus Opus-4.7-specific notes (effort calibration `high`/`xhigh`, tool-use triggering, output-token budgets ≥64k at max effort).
- **Why:** Authoritative source of truth for *how to phrase* requests. The 4.7 section directly addresses "shallow reasoning" (raise effort, don't prompt around it) and over/under-thinking.
- **Adopt:** Bookmark; skim the 4.7 section once. Pull its rules into a *short* `~/.claude/rules/prompting.md` (not a fat CLAUDE.md block).
- **Status:** 🟡 (has `prompt-optimizer` + `openai-docs` skills; this is the primary-source upgrade, Anthropic-specific)

#### Anthropic "Context engineering" cookbook (compaction / clearing / memory)
- **Source:** https://platform.claude.com/cookbook/tool-use-context-engineering-context-engineering-tools · notebook: https://github.com/anthropics/claude-cookbooks (tool_use/context_engineering)
- **Category:** Context engineering / reference
- **What:** Official deep-dive on the THREE first-party primitives — **compaction** (high-fidelity summary), **tool-result clearing** (drop re-fetchable old tool output), **memory** (structured external notes) — and how to combine them, plus replacing the default compaction prompt.
- **Why:** Names exactly which mechanism fixes which failure. Distinguishing them is the conceptual fix for "context loss."
- **Adopt:** Read once; map each primitive to a habit in the Playbook (compaction→PLAYBOOK#5, clearing→#7, memory→#9).
- **Status:** 🔴 (concept gap — they have the *tools* but not the *mental model*)

#### "Using Claude Code: session management and 1M context" (official blog)
- **Source:** https://claude.com/blog/using-claude-code-session-management-and-1m-context
- **Category:** Context engineering / official
- **What:** Defines context rot, the five shed-context levers (Continue / `/rewind` / `/clear` / Compact / Subagents), and 1M-token context behavior.
- **Why:** Clearest official statement of *when to compact vs clear vs subagent*. The 1M window does NOT remove context rot — bigger window = more dilution if you don't curate.
- **Adopt:** Treat as the decision tree behind PLAYBOOK #5–#8.
- **Status:** 🔴 (net-new framing)

#### Claude Code Memory docs — CLAUDE.md + auto-memory + `.claude/rules/`
- **Source:** https://code.claude.com/docs/en/memory
- **Category:** Memory / CLAUDE.md hygiene
- **What:** Full spec: load order, **<200 lines target**, path-scoped `.claude/rules/*.md` with `paths:` frontmatter (load only when matching files are touched), `claudeMdExcludes`, auto-memory storage at `~/.claude/projects/<proj>/memory/`, **"project-root CLAUDE.md survives `/compact`; nested ones do not."**
- **Why:** This is the user's #1 lever. Migrating fat global rules → path-scoped rules cuts per-turn token load and stabilizes the cache prefix.
- **Adopt:** See PLAYBOOK #11 — audit the rules pile this week.
- **Status:** ✅ mechanism / 🔴 *application* (they own the bloat)

#### Console Prompt Improver + Prompt Generator
- **Source:** https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-tools · https://claude.com/blog/prompt-improver
- **Category:** Prompting / tool
- **What:** In the Anthropic Console: *Generator* drafts a structured prompt from a task description; *Improver* takes an existing prompt and adds CoT + XML sections + standardized examples in 4 steps.
- **Why:** For reusable prompts (slash-command bodies, subagent system prompts, eval prompts) this mechanizes best practice. The user authors many agent/skill prompts — run them through Improver once.
- **Adopt:** Paste your `~/.agents/subagent-profiles.md` system prompts and skill SKILL.md bodies into the Improver; commit the refined versions.
- **Status:** 🔴 (free, underused by most CC users)

#### Plan Mode (`--permission-mode plan` / Shift+Tab×2)
- **Source:** https://code.claude.com/docs/en/common-workflows (Plan before editing)
- **Category:** Workflow / built-in
- **What:** Read-and-propose mode; no edits touch disk until you approve. Toggle mid-session with Shift+Tab Shift+Tab.
- **Why:** Forces the Plan step. BUT — **plan-mode plans are ephemeral** (live in one chat turn, lost to compaction). Use it as the *gate*, then persist the plan to a file (see spec-driven tools).
- **Adopt:** Enter plan mode for anything touching 3+ files; have Claude **write the approved plan to `.beads/plans/active-plan.md`** before exiting.
- **Status:** ✅ built-in / 🟡 (must pair with a disk artifact)

#### `/rewind` + checkpoints (esc esc)
- **Source:** https://claude.com/blog/using-claude-code-session-management-and-1m-context
- **Category:** Recovery / built-in
- **What:** Jump back to a previous message and retry from there — undoes both conversation and file edits to a prior checkpoint.
- **Why:** When a session goes sideways (the "everything seems lost" moment), `/rewind` recovers a good state instead of fighting forward through polluted context.
- **Adopt:** Reflex: when Claude starts looping or contradicting itself, `/rewind` to the last clean point rather than re-explaining.
- **Status:** 🔴 (built-in, easy to forget exists)

#### `claude --continue` / `--resume` / `--from-pr` / `/resume`
- **Source:** https://code.claude.com/docs/en/common-workflows (Resume previous conversations) · https://code.claude.com/docs/en/... (Manage sessions)
- **Category:** Session continuity / built-in
- **What:** `--continue` reopens the most recent session in the cwd; `--resume` shows a picker; `claude --from-pr <url>` reopens the session linked to a PR (auto-linked when you ran `gh pr create`).
- **Why:** Multi-sitting tasks resume with full history instead of a cold start. `--from-pr` is the clean way back into PR-shepherding work.
- **Adopt:** Stop starting fresh sessions to "clear the mess" — resume the right one; use `/clear` only with a distilled brief.
- **Status:** 🔴 (built-in, underused)

#### SessionStart + PreCompact hooks — compaction-survival loop
- **Source:** https://github.com/anthropics/claude-code/issues/25999 (`.mind/` survival loop) · https://medium.com/@porter.nicholas/claude-code-post-compaction-hooks-for-context-renewal-7b616dcaa204
- **Category:** Context persistence / hooks (DIY)
- **What:** Pattern: `PreCompact` hook writes a checkpoint (state, in-flight work, rules) to disk; `SessionStart` hook fires again after compaction with `source=compact` and re-injects the briefing via `hookSpecificOutput.additionalContext`. Result: Claude resumes exactly where it was, no "what were we doing?".
- **Why:** **This is the single most direct fix for "Claude fails to remember after a long session."** None of the user's existing capture tools (remember/claude-reflect/auto-memory) re-inject on the `source=compact` signal.
- **Adopt:** Wire a tiny project hook that snapshots `.beads/context/execution-state.md` on `PreCompact` and re-injects it on `SessionStart`. Their metaswarm `.beads/` layout is already 90% of this — just add the two hooks.
- **Status:** 🔴 (true gap — highest-value DIY)

#### Microcompact awareness (no tool — a fact)
- **Source:** https://gist.github.com/sam-saffron-jarvis/9d8e291c4e696ac7948702d6c4884448 (CC compaction deep-dive v2.1.68)
- **Category:** Context engineering / knowledge
- **What:** CC has 5 distinct mechanisms: auto full compact (LLM), manual `/compact` (LLM, full or partial-from-index), sub-agent compact (LLM), **microcompact (non-LLM, clears old tool results only at the warning threshold)**, session-memory compact (non-LLM).
- **Why:** Microcompact silently dropping old tool results ≠ full compaction. Knowing the difference stops you panicking / over-compacting.
- **Adopt:** Recognize a microcompact (tool outputs vanish, reasoning intact) vs a full compact (history summarized).
- **Status:** 🔴 (knowledge gap)

#### `/goal` + Agent View (CC 2.1.142+)
- **Source:** https://dev.to/akaranjkar08/claude-code-21-agent-view-goal-autonomous-dev-guide-2026-31hk
- **Category:** Autonomous loop / built-in
- **What:** `/goal` sets a completion condition; Claude loops (write→test→inspect→revise) across turns until met, with a live overlay (turns, tokens, elapsed). Agent View = single live dashboard of all sessions (running/blocked/done), background + auto-restart, preserved session state (model, effort, MCP, perm-mode) on detach/resume.
- **Why:** Native, lighter alternative to Ralph for bounded autonomous tasks; the state-preservation fix (2.1.142) directly stops the "resume reverts to defaults" drift.
- **Adopt:** Use `/goal` for "make tests pass" style loops; use Agent View instead of juggling terminal tabs.
- **Status:** 🟡 (overlaps Ralph/`continuous-agent-loop`; native is simpler for small loops)

#### Subagent delegation for exploration (built-in Agent/Task)
- **Source:** https://code.claude.com/docs/en/common-workflows (Delegate research to subagents)
- **Category:** Context isolation / built-in
- **What:** "use a subagent to investigate X" — the subagent reads files in its OWN context window and returns only a summary, keeping the main thread clean.
- **Why:** Exploration is the #1 cause of main-context bloat (Glob/Read pile-up). Isolating it is the cheapest context win.
- **Adopt:** They have `dispatching-parallel-agents` + `subagent-driven-development` skills — make subagent-for-exploration the default for any "where/how does X work?" question.
- **Status:** ✅ (have the skills; enforce the habit)

#### `--add-dir` + `CLAUDE_CODE_ADDITIONAL_DIRECTORIES_CLAUDE_MD=1`
- **Source:** https://code.claude.com/docs/en/memory (Load from additional directories)
- **Category:** Multi-repo context / built-in
- **What:** `--add-dir ../shared` grants access to extra dirs; the env var also loads their `CLAUDE.md`/rules.
- **Why:** Clean cross-repo work without one giant session that mixes two codebases.
- **Adopt:** For shared-lib + app work, `--add-dir` instead of `cd`-hopping in one session.
- **Status:** 🔴 (built-in, niche, useful for their multi-repo setup)

#### GitHub Spec Kit (`/speckit.*`)
- **Source:** https://github.com/github/spec-kit · https://github.blog/ai-and-ml/generative-ai/spec-driven-development-with-ai-get-started-with-a-new-open-source-toolkit/
- **Category:** Spec-driven workflow
- **What:** `/speckit.constitution → .specify → .plan → .tasks → .implement`. Persists spec + plan + tasks as **files on disk**, gated, one task at a time with human review between phases.
- **Why:** The persisted-artifact discipline is exactly what prevents "we drifted from the original intent." Plan-mode plans vanish; spec files don't.
- **Adopt:** Overlaps metaswarm/superpowers heavily — **do NOT install on top**; instead steal the *artifact discipline* (commit `docs/specs/*.md` + `docs/stories/*.md`). If you wanted ONE external SDD toolkit, this is the reference.
- **Status:** 🟡 (metaswarm already does gated SDD; adopt the disk-artifact habit, not the tool)

#### Spec-Flow / BMAD-METHOD
- **Source:** https://github.com/marcusgoll/spec-flow · https://github.com/jcfischer/specflow-bundle · https://dev.to/bspann/bmad-method-claude-code-how-i-actually-ship-projects-with-spec-driven-ai-development-1eei
- **Category:** Spec-driven workflow (alternatives)
- **What:** Spec-Flow = `spec→plan→tasks→implement→optimize→ship` with token budgets + `NOTES.md` decision log; BMAD = PM/Architect/Scrum-Master/Dev agents producing PRD + per-story files under `docs/`.
- **Why:** Both solve context-drift by making the **spec do the remembering**. BMAD users report multi-session features finishing in one session once specs anchor the work.
- **Adopt:** Evaluate only if metaswarm feels too heavy; otherwise harvest the `NOTES.md`/per-story-file pattern. BMAD note: its agent configs can *conflict* with a CLAUDE.md — don't double-instruct.
- **Status:** 🟡 (alternatives to metaswarm; harvest patterns, avoid stacking)

#### claude-mem (thedotmack)
- **Source:** https://github.com/thedotmack/claude-mem · https://docs.claude-mem.ai/introduction
- **Category:** Cross-session memory (automatic capture)
- **What:** 5 lifecycle hooks (SessionStart/UserPromptSubmit/PostToolUse/Stop/SessionEnd) → captures every tool use as observations → Bun worker (HTTP API, port `37700+uid%100`) → SQLite (FTS5) + optional Chroma vectors → injects relevant context at next SessionStart. MCP/skill search tools + web viewer.
- **Why:** Genuinely works and is the most popular (72–77k★). BUT it is a **5-always-on-hook + worker + DB** capture layer.
- **Adopt:** ⚠️ **CONFLICT** — the user ALREADY runs auto-memory + `remember` + `claude-reflect` + official `memory` MCP. Adding claude-mem means 4–5 capture layers fighting, doubled hook overhead (50-tool session = 50–100 child processes), ~80–150 MB RAM. **Pick ONE automatic-capture layer.** If you want a *better* one than the built-ins, claude-mem is the candidate to *replace* `remember`/`claude-reflect` — not to add. Evaluate head-to-head, then consolidate.
- **Status:** 🟡 (capable but redundant; replacement candidate, NOT an addition)

#### Official Memory MCP (`@modelcontextprotocol/server-memory`)
- **Source:** https://github.com/modelcontextprotocol/servers-archived/tree/main/src/memory · review: https://chatforest.com/guides/best-memory-mcp-servers/ (3.5/5)
- **Category:** Memory (knowledge graph)
- **What:** Entities + relations + observations in a JSONL file; 9 tools; **text-match search only** (no semantic).
- **Why:** Reference impl, dead simple, local. Text-match recall is its ceiling.
- **Adopt:** They already have it registered. Keep for explicit typed facts (decisions, entities); don't expect fuzzy recall.
- **Status:** ✅ (installed — use for structured facts, not session capture)

#### mem0 / OpenMemory
- **Source:** https://github.com/mem0ai/mem0 · https://github.com/tensakulabs/mem0-mcp (self-hosted Qdrant+Neo4j+Ollama)
- **Category:** Memory (semantic/vector + graph)
- **What:** Extracts conversations into "facts," stores in vector DB; cloud (API key) or self-host. Cross-client (Claude Code AM + Cursor PM share memory).
- **Why:** Semantic recall + multi-tool memory ownership — the one thing local files don't give you.
- **Adopt:** Only if you want ONE memory shared across Claude Code + Codex + Antigravity. Self-host variant fits their privacy posture. Otherwise skip — adds a service.
- **Status:** 🟡 (alternative; only worth it for cross-client shared memory)

#### Basic Memory
- **Source:** https://chatforest.com/guides/best-memory-mcp-servers/ · github.com/basicmachines-co/basic-memory
- **Category:** Memory (human-readable local Markdown)
- **What:** 15+ tools, hybrid FTS+vector search, stores memory as **local Markdown notes** you can read/edit (Obsidian-friendly).
- **Why:** Human-auditable memory — you can diff/edit what the agent "knows." Aligns with the user's existing Markdown-everything approach (MEMORY.md, .beads).
- **Adopt:** Strong fit IF replacing the JSONL official server; pairs with an Obsidian vault. Evaluate vs claude-mem as the "one capture layer."
- **Status:** 🟡 (NET-NEW option; best human-readable alternative)

#### Zep / Graphiti Knowledge-Graph MCP
- **Source:** https://www.getzep.com/product/knowledge-graph-mcp/ · https://nexo-brain.com/blog/mcp-memory-tools-compared-2026/
- **Category:** Memory (temporal knowledge graph)
- **What:** Local Graphiti graph — entities, relationships, **time edges**; tracks how facts change over time; runs locally.
- **Why:** Temporal/provenance memory beats vector-only when facts contradict, age, or need "when did this change?" — relevant to the user's long-running RE projects where addresses/recipes evolve.
- **Adopt:** Heavier (graph DB). Consider only for the persistent-knowledge layer of multi-month projects (e.g., Battle Cats RE). Overkill for daily coding.
- **Status:** 🟡 (alternative; temporal-recall niche)

#### `claude-md-management` plugin / `/init` (`CLAUDE_CODE_NEW_INIT=1`)
- **Source:** https://code.claude.com/docs/en/memory (Set up a project CLAUDE.md) · their installed `claude-md-management` plugin
- **Category:** CLAUDE.md hygiene / built-in
- **What:** `/init` generates/improves a project CLAUDE.md from the codebase; `CLAUDE_CODE_NEW_INIT=1` enables an interactive multi-phase flow (subagent explores, asks gaps, presents a reviewable proposal). The plugin adds `revise-claude-md` / `claude-md-improver`.
- **Why:** Mechanizes keeping CLAUDE.md lean and accurate — directly counters the bloat problem.
- **Adopt:** Run `claude-md-improver` on the global `~/.claude/CLAUDE.md` and the project one; target <200 lines each.
- **Status:** ✅ (have the plugin — actually run it)

#### `InstructionsLoaded` hook (debug what's loaded)
- **Source:** https://code.claude.com/docs/en/memory (troubleshooting)
- **Category:** CLAUDE.md hygiene / diagnostics
- **What:** A hook that logs exactly which instruction files load, when, and why.
- **Why:** Lets the user SEE the per-turn rules tax they're paying — the first step to trimming it.
- **Adopt:** Enable once; read the log; delete/scope rules that load but never fire.
- **Status:** 🔴 (diagnostic gap)

#### `--append-system-prompt` (pin rules above compaction)
- **Source:** https://code.claude.com/docs/en/memory ("instructions you want at the system-prompt level")
- **Category:** Prompt persistence / built-in
- **What:** Injects text at the **system-prompt level** (CLAUDE.md is a *user* message after the system prompt and gets summarized in compaction; system prompt is more durable). Must be passed every invocation → best for scripts/aliases.
- **Why:** For the 2–3 rules that must NEVER be lost (e.g., "TDD mandatory," "never `--no-verify`"), pinning beats CLAUDE.md.
- **Adopt:** Add a shell alias `claude --append-system-prompt "<the 3 non-negotiables>"`.
- **Status:** 🔴 (built-in, power-user move)

#### `repomix` (pack repo into one context-efficient file)
- **Source:** https://github.com/yamadashy/repomix · their installed `repomix` skill + MCP
- **Category:** Context efficiency
- **What:** Packs a repo (or subset) into a single AI-optimized file with token counts.
- **Why:** For onboarding a new repo, one curated packed file beats dozens of ad-hoc Reads (which bloat context and break the cache).
- **Adopt:** `repomix` the relevant subtree, hand Claude the packed file, work from it.
- **Status:** ✅ (have it — use at task start on unfamiliar code)

---

### PLAYBOOK — habits to fix prompting & context loss

> These are the deliverable. Each rule = the habit + WHY it preserves flow + how to do it in Claude Code specifically. Ordered by impact. The user's words were "the good flow then breaks and everything seems lost" — every rule is a flow-preserving guardrail.

**1. Run the Explore → Plan → Code → Verify loop on every non-trivial task. Never let Claude code first.**
This is Anthropic's own internal workflow and the single highest-impact habit ([r/ClaudeAI synthesis](https://dawid.ai/i-spent-40-hours-mining-reddit-for-the-techniques-that-actually-work/)). WHY: jumping straight to code is what produces the sprawling, off-intent diffs you then have to unwind — the moment flow dies. HOW in CC: (1) prompt "Read @<files> and the relevant code. Understand how X works. **Do not write any code yet.**" (2) Shift+Tab Shift+Tab into Plan mode; have it write the plan to `.beads/plans/active-plan.md`. (3) "Implement the plan in `active-plan.md`, one step at a time." (4) Verify (rule #18). Costs ~2 min, kills the rewrite-in-wrong-style problem.

**2. Make the spec/plan a FILE on disk, not a chat turn. Plan mode alone is ephemeral.**
WHY: plan-mode plans and any reasoning you do in chat are summarized/lost at the next compaction — "everything seems lost" is literally this. A committed `spec.md` / `active-plan.md` survives compaction, session restarts, and `/clear` ([DataCamp SDD](https://www.datacamp.com/tutorial/spec-driven-development-with-claude-code), [Towards AI](https://pub.towardsai.net/claude-code-spec-driven-development-why-your-ai-coding-sessions-fall-apart-at-hour-three-e7145128bfc0)). HOW: their metaswarm already writes `.beads/plans/active-plan.md` + `.beads/context/execution-state.md` — **trust those files, not the chat history**. For ad-hoc work outside metaswarm, ask Claude to "write the agreed approach to `docs/specs/<feature>.md` and update it as we learn."

**3. `/compact` PROACTIVELY at 40–60% context, with steering — never reactively at 90%.**
WHY: compaction is lossy; if you wait until quality degrades you're compressing already-degraded context, and a compaction collapses your prompt-cache hit rate (observed 80%→<20%, doubling cost/latency) ([StackNotice](https://stacknotice.com/blog/claude-code-context-management-guide-2026), [Claude Lab](https://claudelab.net/en/articles/claude-code/claude-code-context-budget-optimization-guide)). HOW: when you finish a phase (explore→implement) and you're ~40–60% full, run `/compact focus on the auth refactor and the failing tests, drop the file dumps`. Steering the summary is the difference between keeping decisions and losing them. The user's `strategic-compact` / `context-budget` skills should fire HERE.

**4. After ANY compaction, re-anchor in your next message — don't trust auto-rehydration.**
WHY: compaction preserves the *code/immediate task* but compresses *project conventions and the full scope* — the rules that prevent bugs get summarized to mush, and Claude may even disown in-flight files as "another session's" ([Nick Porter](https://medium.com/@porter.nicholas/claude-code-post-compaction-hooks-for-context-renewal-7b616dcaa204)). HOW: first post-compact message = "Re-read `.beads/plans/active-plan.md` and `CLAUDE.md`. Confirm what we're building and where we are." Project-root CLAUDE.md *is* re-injected after compaction, but nested ones are NOT until a file in that dir is read — so explicitly re-read them.

**5. Learn the difference between microcompact and full compaction — don't panic-compact.**
WHY: CC has 5 mechanisms; **microcompact** (non-LLM) just clears old tool results when the warning threshold hits — your reasoning is intact ([compaction deep-dive](https://gist.github.com/sam-saffron-jarvis/9d8e291c4e696ac7948702d6c4884448)). Mistaking it for a full compact and over-reacting (extra `/compact`, new session) throws away good context. HOW: tool outputs vanishing but the thread coherent = microcompact, keep going. History replaced by a summary = full compact, re-anchor (rule #4).

**6. One session = one repo. Use an orchestrator + Explore subagents for cross-repo work.**
WHY: mixing two codebases in one thread is the fastest route to confusion and contradictory edits ([ClaudeGuide multi-repo](https://dev.to/claudeguide/running-claude-code-across-multiple-repos-without-losing-context-2k83)). HOW: one `claude` per repo (their `model-council`/`agentchattr` can coordinate). For a cross-repo refactor, open a neutral session, dispatch Explore subagents into each repo, collect findings, then hand off to per-repo sessions for implementation. Or `--add-dir ../shared-lib` for a controlled second dir.

**7. Delegate exploration to subagents to keep the main context clean.**
WHY: open-ended "where/how does X work?" fills the main window with Glob/Read output you never need again — reasoning dilution then makes patches overreach ([Claude Lab](https://claudelab.net/en/articles/claude-code/claude-code-context-budget-optimization-guide)). HOW: "use a subagent to investigate how token refresh works" → only the summary returns. The user owns `dispatching-parallel-agents` + `subagent-driven-development` — make subagent-for-exploration the *default*, not the exception.

**8. Cap autonomous/subagent loops with a hard turn limit and an escape condition.**
WHY: a runaway loop (documented: 47 iterations "fixing" one thing) doesn't just waste tokens — it actively makes the agent dumber for the rest of the session by piling on distractors ([Anatomy of a Coding Agent](https://dev.to/pacheco/anatomy-of-a-coding-agent-what-i-learned-building-my-own-155f)). HOW: with Ralph / `continuous-agent-loop`, set explicit max-iterations + a verifiable done-condition. With native `/goal`, the completion condition IS the escape hatch — use it instead of "keep trying."

**9. Use external memory for STATE, not for everything — and write the index yourself.**
WHY: structured note-taking to disk is what lets session 2 resume session 1 — but only if the notes are a *concise typed index*, not a dump ([Anthropic context-engineering cookbook](https://platform.claude.com/cookbook/tool-use-context-engineering-context-engineering-tools)). HOW: keep `MEMORY.md` (and metaswarm's `.beads/context/`) as **pointers + decisions + current position**, ≤200 lines / 25KB (only the first 200 lines of MEMORY.md load at session start). Push detail into topic files Claude reads on demand. This user's MEMORY.md is already large — prune it to an index.

**10. Pick ONE automatic-capture layer. You currently run four; they fight each other.**
WHY: auto-memory + `remember` + `claude-reflect` + official `memory` MCP (+ if you add claude-mem, five) all hook the same lifecycle events — duplicated observations, multiplied hook overhead, and conflicting injected context at SessionStart. More capture ≠ better recall; it's noise. HOW: choose one — built-in **auto-memory** (zero overhead, ✅ already on) for daily work, OR replace it with **claude-mem**/**Basic Memory** if you want semantic search. Disable the rest. Keep the official `memory` MCP only for explicit typed facts.

**11. AUDIT YOUR OWN RULES PILE — this is your highest-leverage fix.** ⚠️
WHY: your global `~/.claude/CLAUDE.md` + 9 `rules/common/*.md` + 8 `rules/web/*.md` + project CLAUDE.md all load *before every prompt*. Anthropic's target is <200 lines per file for adherence; a multi-KB rules tax fragments the cache and dilutes attention on every turn — you are manufacturing the context rot you're fighting ([memory docs](https://code.claude.com/docs/en/memory), [techtaek context discipline](https://techtaek.com/claude-code-context-discipline-memory-mcp-subagents-2026/)). HOW: (a) enable the `InstructionsLoaded` hook to SEE what loads; (b) move anything not true *every session* into `.claude/rules/*.md` with `paths:` frontmatter so it loads only when relevant files are touched (e.g. web rules only on `**/*.{ts,tsx,css}`); (c) run `claude-md-improver` on each CLAUDE.md; (d) delete rules that have never fired.

**12. Pin your 2–3 non-negotiables to the system prompt, not CLAUDE.md.**
WHY: CLAUDE.md is delivered as a *user* message after the system prompt and gets summarized during compaction; the system prompt is far more durable ([memory docs troubleshooting](https://code.claude.com/docs/en/memory)). The rules you'd be furious to lose mid-session (TDD mandatory; never `--no-verify`; stay in file scope) belong there. HOW: alias `claude --append-system-prompt "TDD mandatory. Never use --no-verify. Stay within declared file scope."` For "must run at a fixed point" rules, use a PreToolUse **hook** instead of any prose — hooks enforce regardless of what Claude decides.

**13. Front-load the prompt: ask Claude what it needs to know BEFORE it acts (Socratic / `AskUserQuestion`).**
WHY: Claude (and Opus 4.7 especially) tends to jump in fast; the highest-leverage prompting shift is surfacing hidden assumptions first ([AI-corner power guide](https://www.the-ai-corner.com/p/claude-best-practices-power-user-guide-2026)). HOW: "I want to <task> so that <success criteria>. Before you do anything, ask me the questions you'd need answered to do this well." The `AskUserQuestion` tool renders a structured form. Answering 4 questions up front prevents the 20-minute wrong-direction detour.

**14. Write prompts a confused colleague could follow — concrete, with NOT-to-do and alternatives.**
WHY: the golden test from r/ClaudeAI — if a human with minimal context would be confused, so is Claude ([dawid.ai](https://dawid.ai/i-spent-40-hours-mining-reddit-for-the-techniques-that-actually-work/)). Vague prompts produce vague, drifting work. HOW: copy-paste-ready commands (not "run the tests" → `npx jest path/to/test`), and state constraints as "Do NOT touch the auth module; if you think it needs changing, stop and ask." Saying what *not* to do is as load-bearing as what to do.

**15. Structure complex prompts with XML tags and examples.**
WHY: XML tags give the prompt a "spine" Claude parses reliably; examples (multishot) are the most effective lever for exact output format ([prompting best practices](https://docs.claude.com/en/docs/build-with-claude/prompt-engineering), [prompt generator](http://anthropic.com/news/prompt-generator)). HOW: for any prompt you'll reuse (slash commands, subagent prompts), wrap sections: `<task>…</task> <context>…</context> <constraints>…</constraints> <example>…</example>`. Run reusable prompts through the Console **Prompt Improver** once and commit the result.

**16. Calibrate effort instead of prompting around shallow reasoning.**
WHY: on Opus 4.7, if reasoning is shallow the fix is raising the effort param (`high`/`xhigh`), not adding more prose — and over-large system prompts can trigger *too much* thinking ([prompting best practices, 4.7 section](https://docs.anthropic.com/claude/docs/chain-prompts)). HOW: for architecture/debugging spanning many files, run at `high`+; for latency-sensitive single edits, drop effort and add one line of targeted guidance. At `max`/`xhigh`, set a large output budget (start 64k) so it has room to act.

**17. Pack unfamiliar code with `repomix`; reference files with `@`; don't let Claude blind-Read.**
WHY: dozens of ad-hoc Reads bloat context and break the cache prefix; one curated packed file or precise `@file` references load exactly what the turn needs ([common workflows](https://code.claude.com/docs/en/common-workflows), [Claude Lab](https://claudelab.net/en/articles/claude-code/claude-code-context-budget-optimization-guide)). HOW: new repo → `repomix` the relevant subtree first. Known files → `@src/auth/handler.ts` (also auto-loads that dir's CLAUDE.md). The principle: load what *this turn* needs, nothing else.

**18. Verify before declaring done — demand evidence (tests/diff/output), never self-certify.**
WHY: "tests pass" without proof is how regressions and half-done work slip through; verification is the non-negotiable last step of context discipline ([techtaek](https://techtaek.com/claude-code-context-discipline-memory-mcp-subagents-2026/)). HOW: their `verification-before-completion` skill + project `.coverage-thresholds.json` gate. End every task with "run `npx jest --coverage` and show the result" / "show the diff." Aligns with their MEMORY note *"always peer-review, never self-certify."*

**19. Use `/rewind` (esc esc) to recover, not re-explanation, when a session goes sideways.**
WHY: once a thread is polluted (loops, contradictions, off-intent edits), pushing forward with corrections just adds more distractor context — the "everything seems lost" spiral ([session-management blog](https://claude.com/blog/using-claude-code-session-management-and-1m-context)). HOW: reflex — Claude proposing the same failed fix twice, or editing the wrong files → `/rewind` to the last clean checkpoint and retry from there. Recovers both conversation and file state.

**20. Resume the RIGHT session; only `/clear` with a distilled brief.**
WHY: starting a brand-new session to "escape the mess" throws away durable history you'll have to rebuild; resuming keeps it ([common workflows](https://code.claude.com/docs/en/common-workflows)). HOW: `claude --continue` (most recent in cwd), `claude --resume` (picker), `claude --from-pr <url>` (PR-linked work). When you DO want a clean slate, `/clear` then paste a 3-line brief distilled from what you just learned — fresh context, but anchored.

**21. (Bonus) Add the SessionStart+PreCompact survival-hook to your worst long-running projects.**
WHY: even with auto-memory, nothing in the default stack re-injects state on the `source=compact` signal — so deep RE/feature sessions still hit "what were we doing?" ([CC issue #25999](https://github.com/anthropics/claude-code/issues/25999)). HOW: a small hook writes `.beads/context/execution-state.md` on `PreCompact` and re-injects it via `hookSpecificOutput.additionalContext` on `SessionStart`. The user's `.beads/` layout is already 90% there — two hooks close the loop. This is the durable, automated version of rule #4.

---

#### One-line summary for the user
Your flow breaks for two reasons you can fix today: **(a)** you prompt before exploring/planning to a *file* (rules #1–#2), and **(b)** your own multi-KB global rules pile + four overlapping memory layers manufacture the context rot you're fighting (rules #10–#11). Trim the rules, pick one memory layer, persist plans to disk, compact proactively with steering, and re-anchor after every compaction.

---

## 5.7 — Community hidden gems & power-user tooling


> Research agent #7 of 7. Domain: power-user utilities & hidden gems around Claude Code that the big awesome-lists under-cover — the stuff experienced users rave about on Reddit/HN/X.
> Generated 2026-05-28. Stars & recency verified via `gh api` (live). Year context: 2026.
> **Platform lens:** user is on **Windows 11 / PowerShell**. Every item carries an explicit Platform line. tmux-based multiplexers require **WSL** and are flagged + NOT headlined.

### Reviewer / dedup notes (read first)

- The user already runs a massive orchestration stack: **superpowers** (TDD/brainstorm/plan/subagent), **metaswarm** (9-phase), **ralph** (autonomous loops), **model-council**, **agentchattr**, **codex_consult / Agent Lanes (PromptBridge)**, **ECC**, **claude-reflect**, **hookify**, **claude-md-management**, **repomix**, **skill-creator**. So: orchestration frameworks, CLAUDE.md generators, slash-command packs, and model-routing are mostly 🟡 PARTIAL (overlap), not net-new.
- The genuine **net-new gaps** for this user are the *observability/measurement* layer (statusline, usage/cost dashboards, session viewers, OTel) and the *Windows quality-of-life* layer (clipboard/screenshot paste fix, notifiers) — none of which their existing stack provides.
- "Hidden gem" intentionally includes low-star (0–25⭐) tools where they are recently maintained (pushed 2026) and solve a real Windows pain. Stars marked honestly.

---

### CATEGORY A — Status lines & TUI

#### ccstatusline
- **Source** https://github.com/sirmalloc/ccstatusline (⭐ 9,909 — verified, pushed 2026-05-25, MIT)
- **Category** Status line / TUI
- **What it does** The dominant statusline formatter for Claude Code. TUI config wizard, powerline + themes, widgets for model, git branch/status, context-window %, token counts, session/weekly/Opus-Sonnet usage bars, burn rate, thinking-effort, vim mode, voice status, even a Claude-account-email widget.
- **Why gamechanger** Claude Code's native status line is bare. This is the community-standard upgrade — 70 contributors, weekly releases, and it explicitly handles Windows (sets `windowsHide` on helper processes, `CCSTATUSLINE_WIDTH` override). The single highest-signal cosmetic+functional upgrade you can install.
- **Adopt** `npx ccstatusline@latest` → TUI wizard writes the `statusLine` block into `~/.claude/settings.json`. Pin the global install (now default) so CC keeps a stable version.
- **Platform** Windows-friendly (Node; Windows-specific fixes shipped). ✅
- **Status** 🔴 NET-NEW-GAP

#### ccbar
- **Source** https://github.com/Narcooo/ccbar (⭐ 24 — verified, pushed 2026-03-31)
- **Category** Status line — per-project cost/quota
- **What it does** Zero-dependency native CC plugin statusline focused on **per-project, cross-session** cost + quota: today/week/month token+cost broken down per project, 5h/7d quota bars with countdown, projection-to-EOD, cache hit %, $/h burn. Per-model pricing (correctly prices Opus ~19x Haiku), streaming dedup by `message.id`.
- **Why gamechanger** Most statuslines show *session* cost which resets on restart; ccbar scans all JSONL to show your real rolling bill, attributed per project. The accuracy story (per-model + cache separation + dedup) is what power users on Reddit call out as the differentiator vs flat-rate estimators.
- **Adopt** Install as a CC plugin (Node/TS, no PyPI bootstrap, no daemon). Alternative with similar angle: **cc-costline** (⭐24, https://github.com/Ventuss-OvO/cc-costline — adds a ccclub leaderboard rank).
- **Platform** Windows-friendly (Node, zero-dep). ✅
- **Status** 🔴 NET-NEW-GAP

#### claude-code-statusline (ilia-pluzhnikov)
- **Source** https://github.com/ilia-pluzhnikov/claude-code-statusline (⭐ low; pushed 2026-04-25)
- **Category** Status line — dependency-free single file
- **What it does** Single-file, **no-dependency, no-build** Node statusline. Notable for an explicit "works on macOS, Linux, **and Windows**" claim, a strong **prompt-cache hit/write** widget (`cache 87% ↓75k +360`), context burn, and an Anthropic peak-hours indicator.
- **Why gamechanger** The "drop one .js file, wire it, done" install is the lowest-friction path if you don't want ccstatusline's TUI/global-install model. The cache-hit widget is genuinely rare and directly actionable for cost.
- **Adopt** Drop `statusline.js` into `~/.claude/hooks/`, point `statusLine.command` at it (use forward slashes on Windows: `node "C:/Users/you/.claude/hooks/statusline.js"`).
- **Platform** Windows-friendly (explicit). ✅
- **Status** 🔴 NET-NEW-GAP

#### cc-statusline (NYCU-Chung) — statusline-as-dashboard
- **Source** https://github.com/NYCU-Chung/cc-statusline (⭐ low; pushed 2026-04-12)
- **Category** Status line — full dashboard
- **What it does** A "see everything at a glance, no slash commands" statusline: session info, quota bars, **agent tracker** (subagent activity), **MCP health** (`✘ failed` / `△ needs auth` per server via `claude mcp list`), message history. Installs as a plugin that auto-registers its hooks.
- **Why gamechanger** The MCP-health and subagent-tracker segments are unusual and useful for a heavy-MCP, heavy-subagent user like you — you'd see at a glance which of your ~50 MCP servers are down/unauthed without running diagnostics. (README even calls out the PowerShell `~`-expansion gotcha — Windows-aware author.)
- **Adopt** `claude plugin marketplace add NYCU-Chung/cc-statusline` then add the `statusLine` block manually (CC won't let plugins set it).
- **Platform** Windows-friendly (Node; PowerShell install notes provided). ✅
- **Status** 🟡 PARTIAL (overlaps ccstatusline; pick one — this one if you want MCP-health visibility)

---

### CATEGORY B — Usage & cost tracking

#### ccusage
- **Source** https://github.com/ryoppippi/ccusage (⭐ 14,975 — verified, pushed 2026-05-27, MIT)
- **Category** Usage / cost analyzer (CLI)
- **What it does** The de-facto cost tool. Reads local JSONL and produces daily/weekly/monthly/session reports + **5-hour billing blocks** + per-model breakdown + cache-token accounting + JSON export + offline pricing. Now multi-agent: also parses Codex, Gemini CLI, Copilot CLI, OpenCode, Amp, Qwen, Kimi, etc. Has an MCP server (`@ccusage/mcp`) and a `statusline` subcommand.
- **Why gamechanger** This is *the* viral Claude Code utility ("cost scorecard that went viral"). For a Max user it's the only reliable way to see what your sessions would actually cost, where tokens go, and whether you're cache-efficient. Multi-agent support means it also covers your Codex/Gemini usage in one report.
- **Adopt** `bunx ccusage` (or `npx ccusage@latest`) — no install needed. Add `@ccusage/mcp` if you want CC to query its own usage; or use the statusline integration.
- **Platform** Windows-friendly (npx/bunx). ✅
- **Status** 🔴 NET-NEW-GAP — *highest-priority measurement tool you're missing*

#### Claude-Code-Usage-Monitor (claude-monitor)
- **Source** https://github.com/Maciek-roboblog/Claude-Code-Usage-Monitor (⭐ 8,091 — verified, pushed 2025-09; HN Show: 245 pts)
- **Category** Usage monitor — real-time terminal w/ predictions
- **What it does** A live (0.1–20 Hz) Rich-UI terminal monitor: color progress bars for token+time, **ML/P90 predictions** of when you'll hit the cap, multi-level warnings, auto-detect plan, per-model cost. Default "Custom plan" learns your limits from the last 192h.
- **Why gamechanger** ccusage tells you *what you spent*; this tells you *will I get cut off mid-session* — the #1 Max-plan pain. Runs 100% locally. Explicitly cross-platform (Windows/macOS/Linux) per its DEVELOPMENT.md.
- **Adopt** `uv tool install claude-monitor` → run `claude-monitor` (also `cmonitor` / `ccm`). Auto-installs ccusage if missing.
- **Platform** Windows-friendly (PyPI; cross-platform stated). ✅
- **Status** 🔴 NET-NEW-GAP
- **Caveat** Last push 2025-09 — slower cadence than ccusage but stable and still the most-loved monitor.

#### cccost
- **Source** https://github.com/badlogic/cccost (`@mariozechner/cccost`; pushed 2025-08)
- **Category** Cost tracking — accurate via fetch() interception
- **What it does** A wrapper: run `cccost` instead of `claude`. It spawns CC and hooks NodeJS `fetch()` to intercept *every* request to Anthropic, writing accurate per-model token/cost to `…sessionid.usage.json` — including resumed sessions.
- **Why gamechanger** Solves a real correctness bug the author documents: the **session transcript does NOT contain all requests** CC issues, and `/cost` is hidden for Pro/Max + had a bug. cccost is the only approach that captures ground-truth usage for resumed sessions, which you can then feed any statusline.
- **Adopt** `npm i -g @mariozechner/cccost`; launch via `cccost --model sonnet …`.
- **Platform** Windows-friendly (Node wrapper). ✅
- **Status** 🔴 NET-NEW-GAP (niche but the accuracy purist's pick)

#### bonkey/claude-counter-statusbar
- **Source** https://github.com/bonkey/claude-counter-statusbar (pushed 2026)
- **Category** Statusline + cost backfill
- **What it does** Statusline showing token bar, estimated API cost (cache discounts: reads 10%, writes 125%), 5h+7d **real rate-limit utilization** with reset countdowns, and a billing-period total that resets on a configurable billing day. `claude-counter --sync` backfills historical cost from transcripts and pulls latest pricing from LiteLLM.
- **Why gamechanger** The billing-cycle total + LiteLLM-sourced live pricing is a nice middle-ground between ccusage and a statusline.
- **Adopt** Install, run `--sync` once to backfill, wire as statusline.
- **Platform** Windows-friendly (reads `~/.claude/projects/*.jsonl`). ✅
- **Status** 🟡 PARTIAL (overlaps ccbar/cc-costline — pick one cost statusline)

---

### CATEGORY C — Session / transcript viewers (NET-NEW measurement layer)

#### claude-code-history-viewer
- **Source** https://github.com/jhlee0409/claude-code-history-viewer (⭐ 1,419 — verified, pushed 2026-05-25, MIT; v1.11.0)
- **Category** Session viewer — desktop app (Tauri)
- **What it does** Desktop app (TypeScript + Rust/Tauri) to browse/search/analyze conversation history across **seven** assistants: Claude Code, Gemini CLI, Codex CLI, Cline, Cursor, Aider, OpenCode. Full tool-use/thinking/cost rendering, cross-provider token comparison, 100% offline. Headless server mode too.
- **Why gamechanger** The most-starred, most-maintained viewer, and multi-tool — it'd surface your Claude + Codex + Gemini history in one offline desktop UI. 30 contributors, 24 releases.
- **Adopt** Download the Windows build from releases (Tauri ships Windows installers), or run headless.
- **Platform** Windows-friendly (Tauri Windows builds). ✅
- **Status** 🔴 NET-NEW-GAP

#### kmizzi/claude-code-sessions
- **Source** https://github.com/kmizzi/claude-code-sessions (⭐ low; pushed 2026-05-05)
- **Category** Session viewer — local web dashboard + AI chat
- **What it does** Local dashboard: global session list across every project (project/branch/gist/last-prompt/context%/model/time columns), virtualized for 10k+ sessions, filters, chat-style **replay**, export to Markdown, **resume/fork → copies the CLI command to clipboard** (with `--dangerously-skip-permissions`/`--fork` flags). Plus a built-in chat panel that answers "what did I work on today / which project burns the most tokens" by querying your indexed sessions (needs your own API key).
- **Why gamechanger** Solves CC's biggest history gap: `--resume` is per-directory; this searches across ALL projects at once and lets you replay/fork. The "ask my own history in natural language" angle is unique.
- **Adopt** Clone + run the local server; bring an API key only for the chat panel.
- **Platform** Windows-friendly (local web; Node). ✅ (verify Node steps)
- **Status** 🔴 NET-NEW-GAP

#### apappascs/claude-code-sessions (plugin: 11 skills + dashboard)
- **Source** https://github.com/apappascs/claude-code-sessions (⭐ low; pushed 2026-05-15)
- **Category** Session intelligence — CC plugin (in-session)
- **What it does** A *plugin* (not external app): adds 11 slash commands — `/session-search`, `/session-stats`, `/session-diff`, `/session-timeline`, `/session-resume` (generates a context-recovery prompt), `/session-tasks` (find orphaned/pending todos across sessions), `/session-export`, `/session-cleanup` — plus a web dashboard.
- **Why gamechanger** Because it's in-session, it fits your workflow without leaving the terminal. `/session-tasks` (orphaned-todo detection) and `/session-resume` (context recovery) pair perfectly with your ralph/metaswarm recovery patterns.
- **Adopt** Install as a CC plugin from the repo.
- **Platform** Windows-friendly (plugin; reads JSONL). ✅
- **Status** 🟡 PARTIAL (overlaps your `.beads` recovery + claude-reflect, but adds cross-session search/diff)

#### agent-session-viewer (dhruv-anand-aintech)
- **Source** https://github.com/dhruv-anand-aintech/agent-session-viewer (⭐ low; pushed 2026-05-27 — very active)
- **Category** Session viewer — live multi-platform
- **What it does** Live (SSE-streaming) unified viewer across Claude Code, Codex, Cursor, OpenCode, Hermes, Antigravity, and "claw" bots (nanoclaw/openclaw/picoclaw). Pretty mode (markdown, thinking pills, tool-call cards), **sub-agent runs visually distinguished** (`⤷ sub-agent` indent), fuzzy thread search.
- **Why gamechanger** Directly relevant: you run nanoclaw/openclaw and Antigravity. This is the one viewer that natively renders those + Claude + Codex live in one UI, and it visualizes subagents.
- **Adopt** Clone + run; auto-detects all platforms.
- **Platform** Likely Windows-friendly (web; verify — Cursor path is macOS-specific but Claude/Codex JSONL are cross-platform). ⚠️ verify
- **Status** 🔴 NET-NEW-GAP (best fit for your multi-agent zoo)

#### Honorable mentions (session viewers)
- **law5/claude-log-viewer** (⭐0, 2026-05) — clean chat-UI viewer with **playback animation**, full-text search, quote mode. Windows-friendly local web.
- **d-kimuson/claude-code-viewer** (⭐ 1,202, pushed 2026-05-10) — full web client; note: as of Apr 2026 chat-send features are opt-in due to ToS, but **read-only viewing/history/live-tail remain fully available**. Windows-friendly.
- **dotneet/agent-session-view** (2026) — web **and TUI**, exports HTML/text, Claude+Codex. TUI is handy on Windows Terminal.
- **lucemia/claude-session-analyzer** (CC plugin) — quantitative analysis (thinking depth, Read:Edit ratio, behavioral regressions, sentiment, cost) replicating anthropics/claude-code#42796 methodology. Great for self-auditing agent behavior.
- **Status** 🟡 PARTIAL/optional

---

### CATEGORY D — Observability / OpenTelemetry

> CC emits native OTLP metrics/logs/traces when `CLAUDE_CODE_ENABLE_TELEMETRY=1`. These projects are pre-built Grafana stacks around that. All run via **Docker Desktop on Windows** — Windows-friendly.

#### cc-otel
- **Source** https://github.com/nadersoliman/cc-otel (⭐ 2; pushed 2026-03-19)
- **Category** Observability — full Grafana LGTM stack
- **What it does** 6-container local stack (OTel Collector → Prometheus/Loki/Tempo + Grafana + Pyroscope) with pre-built dashboards: Log Explorer, Traces (via an OTel trace hook), API Requests/Errors, Tool Usage, Collector health. Drop-in `env` block for `~/.claude/settings.json`.
- **Why gamechanger** Turns your CC usage into a real Grafana observability plane — traces of tool calls, log explorer over prompts, per-session cost — the enterprise-grade view. For someone running autonomous ralph loops, traces of what agents did over time are gold.
- **Adopt** `docker compose up`, paste the env block, set endpoint `http://localhost:4321`.
- **Platform** Windows-friendly via Docker Desktop. ✅ (low stars; it's a config-stack, value is the dashboards)
- **Status** 🔴 NET-NEW-GAP

#### claude-mon / cc-analytics / claude-code-metrics-prometheus
- **Source** https://github.com/halyph/claude-mon (⭐0) · https://github.com/aarogyarijal/cc-analytics (OTel→SQLite→React) · https://github.com/rockdarko/claude-code-metrics-prometheus (Grafana dashboard for existing Prom/VictoriaMetrics/Mimir/Thanos)
- **Category** Observability — lighter alternatives
- **What it does** claude-mon = Prometheus+Loki+Grafana (metrics+logs dashboards). cc-analytics = personal React dashboard backed by SQLite with a live SSE feed (cost/lines/typing-time-vs-active-time/cache-hit/success-rate). metrics-prometheus = just the Grafana dashboard JSON if you already run a Prom-family backend.
- **Why gamechanger** Pick by appetite: cc-analytics if you want a lightweight personal dashboard (SQLite, no full LGTM); metrics-prometheus if you already have Prometheus infra.
- **Adopt** Docker compose (claude-mon) / Node+SQLite (cc-analytics) / import JSON (metrics-prometheus).
- **Platform** Windows-friendly via Docker/Node. ✅
- **Status** 🟡 PARTIAL (choose one OTel stack; cc-otel is the most complete)

---

### CATEGORY E — Notifications (Windows-friendly QoL)

#### claude-notify (hecspc) — Rust multi-channel
- **Source** https://github.com/hecspc/claude-notify (⭐ 0; pushed 2026-05-12, Rust)
- **Category** Notifications — hooks-based, multi-backend
- **What it does** Rust CLI hooking CC events → notifies via Desktop, Telegram, Slack, Discord, ntfy, Pushbullet, Teams, Webhook, Email, WhatsApp. Switch backends on the fly, mute per-session, all driven by `/claude-notify:*` slash commands.
- **Why gamechanger** Most complete channel matrix of the notifiers, and the per-session mute + slash-command control is the polished UX. Fires on permission prompts, questions, idle, and task completion — so you can walk away from a long ralph run and get pinged on your phone.
- **Adopt** Install the plugin; `/claude-notify:setup-desktop` (zero-config) or `…setup-ntfy <topic>` for phone. Switch with `/claude-notify:use desktop,ntfy`.
- **Platform** Windows-friendly (Rust binary; desktop backend cross-platform). ✅ (0 stars — true hidden gem; verify Windows desktop backend)
- **Status** 🔴 NET-NEW-GAP

#### claude-notifier (felipeelias) — single static binary
- **Source** https://github.com/felipeelias/claude-notifier (⭐ 2; pushed 2026-04-16, Go)
- **Category** Notifications — fan-out dispatcher
- **What it does** Single static Go binary, TOML config, compiled-in plugins. Reads CC hook JSON from stdin, **fans out to all channels concurrently** (ntfy, desktop, Slack…), per-event priorities, **always exits 0** so it never breaks your hook. Same binary+config across Linux/macOS/**Windows**.
- **Why gamechanger** The "one binary, same config everywhere, never breaks the hook" design is the cleanest for a cross-machine setup. Go templates expose `{{.Message}}/{{.Project}}/{{.SessionID}}/{{.TranscriptPath}}`.
- **Adopt** `claude-notifier init`, edit TOML, point a Notification/Stop hook at it.
- **Platform** Windows-friendly (explicit). ✅
- **Status** 🔴 NET-NEW-GAP

#### ddaikodaiko/claude-notify — summary-on-finish
- **Source** https://github.com/ddaikodaiko/claude-notify (pushed 2026-04-05)
- **Category** Notifications — Stop-hook summary
- **What it does** Adds a `Stop` hook that reads the session transcript and sends a **summary** (not just "done") to desktop (macOS/Linux/**Windows**), ntfy, or webhooks (Slack/Discord).
- **Why gamechanger** Getting the actual task summary on your phone (vs a generic "completed") is the nicer signal when babysitting multiple sessions. Frozies/claude-notify is a similar Windows-toast option (PowerShell/BurntToast).
- **Adopt** `claude-notify` install; `set channels.ntfy.topic …`.
- **Platform** Windows-friendly (explicit Windows desktop). ✅
- **Status** 🟡 PARTIAL (overlaps the above — pick one notifier)

#### ChanMeng666/claude-code-audio-hooks (echook)
- **Source** https://github.com/ChanMeng666/claude-code-audio-hooks (⭐ 66 — verified, pushed 2026-05-05)
- **Category** Notifications — audio + TTS, AI-operated
- **What it does** Audio notification system: 26 hook events, chime themes + ElevenLabs voice, **TTS that speaks Claude's actual final message** (not just a beep), rate-limit alerts at 80/95%, NDJSON logs. "AI-operated": after one `/reload-plugins`, you control everything in natural language ("snooze for an hour", "switch to chimes").
- **Why gamechanger** Most-loved audio notifier (66★, active). TTS-speaks-the-reply + rate-limit alerts is a step beyond plain sound. On Windows it uses PowerShell for playback (volume via system volume).
- **Adopt** `claude plugin marketplace add ChanMeng666/claude-code-audio-hooks` → install → `/reload-plugins`.
- **Platform** Windows-friendly (PowerShell audio; volume control is macOS/Linux only). ✅
- **Status** 🔴 NET-NEW-GAP (audio niche)
- **Note** `juuni26/claude-notif-sound` is a simpler Windows-friendly sound-only alternative (web GUI at localhost:6998).

---

### CATEGORY F — Windows clipboard / screenshot paste (real Windows pain, unsolved by your stack)

> CC on Windows can't paste raw clipboard images reliably (Snipping Tool → CC paste is broken; native paste is Alt+V and finicky). These fix the screenshot→terminal workflow. **This is a category your superpowers/ECC/metaswarm stack does not address at all.**

#### ClipPath
- **Source** https://github.com/BiteCraft/ClipPath (⭐ 22; pushed 2026-02-14)
- **Category** QoL — clipboard image → file path (Windows/WSL)
- **What it does** Single portable `.exe`. Copy any image, press a hotkey → the saved file path is **typed into your active window**, with automatic **WSL vs Windows path detection** (`/mnt/c/...` vs `C:\...`). Monitors clipboard via Win32 `AddClipboardFormatListener`, saves timestamped BMP, types via `SendInput`. Zero deps.
- **Why gamechanger** Purpose-built for exactly your setup (Claude Code on Windows/WSL). Eliminates the save→navigate→copy-path→paste dance every time you want to show CC a screenshot. The WSL auto-detection is the killer feature if you ever run CC under WSL.
- **Adopt** Download the `.exe`, set a hotkey, screenshot → hotkey → path appears in CC.
- **Platform** Windows-native (built for Windows + WSL). ✅✅
- **Status** 🔴 NET-NEW-GAP

#### TerminalCopyPaste (TCP)
- **Source** https://github.com/CodeWarrior4Life/TerminalCopyPaste (⭐ 0; pushed 2026-04-24)
- **Category** QoL — smart Ctrl+V for terminals (Windows)
- **What it does** Makes **Ctrl+V smart**: image in clipboard + terminal focused → pastes the file path; file(s) in clipboard → pastes path(s); anywhere else → normal paste untouched. Alt+V forces image-path paste anywhere. Auto-detects your screenshot folder; extracts attachments from Telegram/WhatsApp/Outlook to `%TEMP%\tcp\`.
- **Why gamechanger** The zero-learning-curve version of ClipPath — you keep using Ctrl+V and it Just Works, only intervening in terminals. Pastes via clipboard+Ctrl+V (instant) rather than char-by-char typing.
- **Adopt** Run the background app; use Ctrl+V as normal.
- **Platform** Windows-native. ✅✅
- **Status** 🔴 NET-NEW-GAP (0 stars but solves the exact pain; pick this OR ClipPath)

#### claude-screenshot-mcp (raphaelbgr)
- **Source** https://github.com/raphaelbgr/claude-screenshot-mcp (search-surfaced; **repo not found via `gh api` 2026-05-28 — may be renamed/private, VERIFY**)
- **Category** QoL — hotkey region capture → clipboard + MCP
- **What it does** Hotkey (`Ctrl+Shift+Q`) drag-region screenshot → file path on clipboard ready to paste; recapture hotkey; multi-monitor; also exposes MCP tools so CC can trigger captures itself (`screenshot_capture_region`).
- **Why gamechanger** Region-select + CC-can-request-a-capture is a level up from plain paste. The MCP angle means Claude can ask for a screenshot mid-task.
- **Adopt** ⚠️ Confirm the repo exists first (404'd on verification). If gone, use **Grips001/snapview** (Electron, `/snapview` overlay + Claude-requested captures via Stop hook; Windows-friendly) or **marco-jardim/mcp-windows-clipboard** (⭐0, MCP server: `read_clipboard_image` returns a saved path — reliable Windows clipboard bridge).
- **Platform** Windows-friendly (per README) — but repo unverified. ⚠️
- **Status** 🟡 PARTIAL — prefer snapview / mcp-windows-clipboard until verified

#### davestanyer/clipboard-screenshot-saver (`img`)
- **Source** https://github.com/davestanyer/clipboard-screenshot-saver (pushed 2025-07)
- **Category** QoL — PowerShell screenshot saver
- **What it does** Pure **PowerShell**: `img` saves the clipboard image into the project's `imgs/` folder with smart numbering and puts the path back on your clipboard. Context prefixes: `img -UI`, `img -Bug`, `img -Before/-After`.
- **Why gamechanger** Native PowerShell (no .exe, no daemon) — fits your shell exactly. The `-Bug`/`-UI` naming convention keeps screenshots organized inside the repo.
- **Adopt** Dot-source the script into your PowerShell profile; type `img` after screenshotting.
- **Platform** Windows-native PowerShell. ✅✅
- **Status** 🔴 NET-NEW-GAP (the no-install PowerShell purist option)

---

### CATEGORY G — Session / multiplexing & parallel work (mostly WSL-gated — NOT headlined)

> ⚠️ **Windows reality:** the popular multiplexers all require **tmux**, i.e. you'd run them inside **WSL**, not native PowerShell. You already have strong parallel-work coverage via superpowers (subagent/worktree skills), metaswarm, ralph, and native CC worktrees/agent-teams. Included for completeness; do not treat as must-installs.

#### claude-squad
- **Source** https://github.com/smtg-ai/claude-squad (⭐ 7,650 — verified, pushed 2026-05-18)
- **Category** Multiplexer — multiple agents in isolated workspaces
- **What it does** Terminal app managing multiple Claude Code / Codex / Gemini / Aider instances, each in its own **isolated git workspace**. Background tasks (incl. yolo/auto-accept), review-before-apply, commit+push per session.
- **Why gamechanger** The flagship parallel-agent TUI (7.6k★). Genuinely loved for running 4–6 agents on separate tasks with no merge conflicts.
- **Adopt** Inside WSL: install binary; requires **tmux + gh**. `cs` to launch.
- **Platform** ⚠️ **WSL only** (tmux dependency) — not native Windows/PowerShell.
- **Status** 🟡 PARTIAL (covered conceptually by your superpowers/metaswarm; only adopt if you want a dedicated multi-agent TUI and live in WSL)

#### crmux
- **Source** https://github.com/maedana/crmux (⭐ 24; pushed 2026-05-15)
- **Category** Multiplexer — tmux sidebar for CC sessions
- **What it does** A single tmux sidebar showing every CC session's live status/permission-mode/repo/branch/worktree with alerts for approval requests & completions; send prompts to idle sessions by repo name via RPC.
- **Why gamechanger** Lightweight "just a tmux pane" approach — nothing changes about your shells/tools. The RPC send-by-repo-name is elegant.
- **Adopt** WSL + tmux; run `crmux` inside a tmux session.
- **Platform** ⚠️ **WSL only** (tmux). 
- **Status** 🟡 PARTIAL

#### cwt (Rust worktree manager)
- **Source** https://github.com/0dragosh/cwt (⭐ 2; pushed 2026-04-23)
- **Category** Multiplexer — worktree-first TUI (Rust)
- **What it does** Rust TUI treating **git worktrees as the first-class unit of work**; sessions attach to worktrees. Prefers zellij, falls back to tmux. Auto-snapshots + one-key PR shipping. Works with Claude/Codex/Pi.
- **Why gamechanger** The "worktree is primitive" model is the cleanest mental model for parallel agent work; zellij support is slightly more Windows-tolerable than pure tmux.
- **Adopt** Needs zellij or tmux on PATH (so still WSL on Windows). Nix flake for Linux/macOS.
- **Platform** ⚠️ **WSL only** (needs zellij/tmux). 
- **Status** 🟡 PARTIAL

#### tmux-orchestrator / bouquet / cc-tmux-worktree-orchestration / cc-orchestrator
- **Source** twaldin/tmux-orchestrator (⭐2) · promptromp/bouquet · zc277584121/cc-tmux-worktree-orchestration · altsang/cc-orchestrator
- **Category** Multiplexer — multi-agent team orchestration in tmux
- **What it does** Spawn agent teams in tmux windows with worktree isolation, task queues/backlogs auto-delegated, two-way send-keys messaging, auto-approval of stuck prompts. cc-orchestrator adds a FastAPI+React web dashboard (up to 10 instances).
- **Why gamechanger** These overlap heavily with what your **metaswarm + ralph + agentchattr** already do (orchestration, task queues, agent coordination). Mention only.
- **Adopt** All require tmux → WSL.
- **Platform** ⚠️ **WSL only**. 
- **Status** 🟡 PARTIAL (redundant with your existing orchestration stack)

#### Crystal — ⚠️ DEPRECATED
- **Source** https://github.com/stravu/crystal (⭐ 3,072; pushed 2026-02-26) → **replaced by Nimbalyst (https://nimbalyst.com), deprecated Feb 2026**
- **Category** Multiplexer — desktop app (Electron) for parallel worktree sessions
- **What it does (was)** Electron desktop app to run multiple Codex/Claude sessions in parallel git worktrees, compare approaches. (Desktop → would have been Windows-friendly, unlike the tmux tools.)
- **Why noted** It's still all over older awesome-lists and Reddit threads — flagging so you don't chase a dead tool. Use **Nimbalyst** if you want the successor.
- **Platform** Electron (Windows-capable) — but discontinued.
- **Status** 🔴 ABANDONED (use Nimbalyst instead, or claude-squad-in-WSL)

---

### CATEGORY H — Model routing / cost-saver proxies

> 🟡 You already have **Agent Lanes / PromptBridge / codex_consult** and **model-council** for multi-model work. These proxies are a *different* axis (route CC's own traffic to cheaper/free/local models). Included because they're the most-starred CC tools in existence and you may not have a transparent CC→GLM/local router.

#### claude-code-router (ccr)
- **Source** https://github.com/musistudio/claude-code-router (⭐ 34,467 — verified, pushed 2026-03-04)
- **Category** Proxy — route CC requests to any model
- **What it does** The dominant router. Routes CC's Anthropic-API traffic per-tier (background/think/long-context) to OpenRouter, DeepSeek, Ollama, Gemini, Volcengine, SiliconFlow, etc. In-session `/model` switching, `ccr model` CLI, transformer plugin system, GitHub Actions integration.
- **Why gamechanger** #1 way to slash CC cost by sending cheap work to GLM/DeepSeek/local while keeping the CC interface. 34k★ — the single most-starred CC ecosystem tool.
- **Adopt** `npm i -g @musistudio/claude-code-router`; set `ANTHROPIC_BASE_URL` to the proxy; pick providers in config.
- **Platform** Windows-friendly (Node). ✅
- **Status** 🟡 PARTIAL — net-new *capability* (transparent CC→other-model) but conceptually adjacent to your Agent Lanes; adopt only if you want cheap/local routing inside CC itself.

#### 9router
- **Source** https://github.com/decolua/9router (⭐ 14,841 — verified, pushed 2026-05-26, MIT)
- **Category** Proxy — free/cheap auto-fallback gateway
- **What it does** Connects CC/Codex/Cursor/Cline/Copilot/Antigravity to 40+ providers, 100+ models. **Auto-fallback** Subscription → Cheap (GLM/MiniMax) → Free (Kiro/OpenCode/Vertex credits), multi-account round-robin, and **RTK token-saver** (auto-compresses tool_result, −20–40% tokens).
- **Why gamechanger** "Never hit limits" — when your Max quota exhausts mid-session it transparently falls back to cheap then free providers. The RTK token compression is a real, measurable saving. Extremely active (release v0.4.63, 2026-05-26).
- **Adopt** Run the gateway (localhost:201x), point CC at it.
- **Platform** Windows-friendly (JS; ships PowerShell). ✅
- **Status** 🟡 PARTIAL (overlaps router space; the auto-fallback + token-saver angle is distinct)

#### claudish
- **Source** https://github.com/MadAppGang/claudish (⭐ 889 — verified, pushed 2026-05-13)
- **Category** Proxy — use existing subscriptions with CC
- **What it does** Run CC against any model via `claudish --model glm@GLM-4.7` / `oai@gpt-5.3-codex` / `g@gemini-3-pro` / local `ollama@…`. 580+ models via OpenRouter; uses subscriptions/keys you already have; mid-session switching.
- **Why gamechanger** The `provider@model` syntax is the cleanest ergonomics, and "use subs you already pay for" matches your multi-subscription setup (you have Codex/Antigravity/GLM access via wrappers already).
- **Adopt** `npx claudish --model …` per session.
- **Platform** Windows-friendly (Node). ✅
- **Status** 🟡 PARTIAL (you already proxy Codex/Antigravity via model-council/agentchattr wrappers)

---

### CATEGORY I — Quality-of-life: voice, CLAUDE.md, command packs

#### Native `/voice` dictation (built-in) + external alternatives
- **Source** Native: https://code.claude.com/docs/en/voice-dictation (shipped **March 3, 2026**, CC ≥ v2.1.69; tap mode ≥ v2.1.116)
- **Category** QoL — voice input
- **What it does** **CC now has built-in voice dictation** — run `/voice`, hold Space (push-to-talk) or tap mode, speech transcribes live into the prompt, mix voice+typing. Uses Anthropic's STT (counts against `/usage`; requires an anthropic.ai account).
- **Why gamechanger** Zero-setup voice is already in your CLI — most people don't know it shipped. Try this **first** before any external tool.
- **External alternatives** (only if you need higher accuracy / offline / system-wide):
  - **Wispr Flow** (https://wisprflow.ai) — system-wide dictation, **native Windows app**, "Vibe Coding mode" recognizes variable/file names, 179 WPM. Most-recommended external pick for Windows.
  - **Superwhisper** (https://superwhisper.com) — AI voice-to-text, **Windows + macOS + iOS**, offline models.
  - ⚠️ `superultrainc/superwhisper-claude-code` plugin and `nardovibecoding/claudecode-voice` are **macOS-only** (deeplinks / `say` TTS / afplay) — skip on Windows.
- **Platform** Native `/voice`: ✅ all platforms. Wispr Flow / Superwhisper: ✅ Windows.
- **Status** ✅ HAVE (native) / 🟡 external optional

#### awesome-claude-md (curated examples + generator)
- **Source** https://github.com/Anuar-boop/awesome-claude-md (⭐ 0; pushed 2026-03-04)
- **Category** QoL — CLAUDE.md examples + `npx` generator
- **What it does** Curated real-world CLAUDE.md examples per stack + an intelligent generator (`npx awesome-claude-md`) that scans runtime/frameworks/test-runner/package-manager/build commands and emits a tailored CLAUDE.md with git standards.
- **Why gamechanger** Good reference library even if you don't use the generator.
- **Platform** Windows-friendly (npx). ✅
- **Status** 🟡 PARTIAL — you already have the **claude-md-management** plugin + skill-creator. Use this for *example patterns*, not as a replacement.

#### repo-scaffold (RepoScaffold)
- **Source** https://github.com/AnantKumar17/repo-scaffold (⭐ 2; pushed 2026-04-27)
- **Category** QoL — CC plugin: CLAUDE.md + AGENTS.md + skills generator
- **What it does** `/scaffold` analyzes a repo and generates CLAUDE.md, **AGENTS.md** (subagent defs), and **project-specific skills** in `.claude/skills/` (test-writer, security-scanner, component-generator, api-route-generator — conditionally on detected stack). Flags: `--dry-run`, `--skills-only`, `--claude-md-only`.
- **Why gamechanger** Auto-generating *project-scoped skills* (not just docs) is the differentiator over plain CLAUDE.md generators.
- **Platform** Windows-friendly (plugin). ✅
- **Status** 🟡 PARTIAL (overlaps claude-md-management + skill-creator; the AGENTS.md + skills generation is the new bit)

#### Claude-Command-Suite
- **Source** https://github.com/qdhenry/Claude-Command-Suite (⭐ 1,260 — verified, pushed 2026-03-01)
- **Category** QoL — slash-command pack
- **What it does** 216+ namespaced slash commands (`/dev:code-review`, `/test:generate-test-cases`, `/deploy:prepare-release`), 12 skills, 54 agents, GitHub↔Linear sync, media processing, WebMCP.
- **Why gamechanger** The largest well-maintained command pack (1.26k★). Useful as a *menu to cherry-pick from*.
- **Platform** Windows-friendly (markdown commands). ✅
- **Status** 🟡 PARTIAL — heavy overlap with ECC's command suite + your gstack/wshobson skills; mine it for individual commands you lack, don't bulk-install.

#### claude-mods
- **Source** https://github.com/0xDarkMatter/claude-mods (pushed 2025-11)
- **Category** QoL — agents + skills + output-styles + session CLI
- **What it does** 23 agents, 66 skills, **5 output styles** (Vesper/Spartan/Mentor/Executive), 4 hooks (pre-commit lint, post-edit format, dangerous-command warnings), and a zero-dependency **cc-session** CLI (15 commands, `--json`, cross-project search).
- **Why gamechanger** The **output-style pack** and the standalone cc-session analyzer are the interesting hidden bits.
- **Platform** Windows-friendly. ✅
- **Status** 🟡 PARTIAL (output-styles + cc-session are net-new; agents/skills overlap your stack)

#### `/output-style` & `/output-style:new` (built-in, under-used)
- **Source** Built-in CC feature (documented 2026); see Tatsuru Okada, Medium "7 Claude Code Hacks" (2026-04-08)
- **Category** QoL — system-prompt personas (free, built-in)
- **What it does** `/output-style` swaps CC's system prompt (default/explanatory/learning out of the box). `/output-style:new <description>` *generates* a custom style markdown into `~/.claude/output-styles/`. Styles needn't be about coding — turn CC into a business analyst, copy editor, journaling partner; set `keep-coding-instructions: true` to retain tool abilities.
- **Why gamechanger** A power-user lever most people ignore: reuse the tool you already pay for for non-code knowledge work, or tune explanation depth per task. Pairs with claude-mods' style pack.
- **Platform** ✅ built-in, all platforms.
- **Status** ✅ HAVE (built-in) — flagged because it's under-used, not missing.

---

### TOP 8 hidden-gem picks for THIS user (Windows-native, genuinely net-new)

Ranked by value given your existing stack (which already covers orchestration, multi-model, knowledge capture):

1. **ccusage** (⭐15k) — the measurement gap. One `bunx ccusage` and you finally see real cost/token/cache data across CC + Codex + Gemini. ✅ Windows.
2. **ccstatusline** (⭐9.9k) — always-on context%/cost/quota/model in your prompt; explicitly Windows-hardened. ✅
3. **Claude-Code-Usage-Monitor** (⭐8k) — real-time "will I get cut off" predictions for your Max plan; cross-platform. ✅
4. **ClipPath** *or* **TerminalCopyPaste** *or* PowerShell **`img`** — fixes the broken Windows screenshot→CC paste; a pain nothing in your stack addresses. ✅✅ Windows-native.
5. **claude-code-history-viewer** (⭐1.4k, Tauri) — offline desktop browser/search over your Claude+Codex+Gemini+Antigravity history. ✅ Windows builds.
6. **cc-otel** (Docker) — turns CC's native OTLP telemetry into a Grafana traces/logs/cost plane; gold for auditing your ralph autonomous loops. ✅ via Docker Desktop.
7. **claude-notifier** (felipeelias) *or* **claude-notify** (hecspc) — phone/desktop ping (with task summary) when long runs finish or need input; single-binary, same config cross-machine. ✅ Windows.
8. **agent-session-viewer** (dhruv-anand) — live unified viewer that natively renders your nanoclaw/openclaw/**Antigravity**/Codex/Claude sessions with subagent visualization. ✅ (verify Windows web).

**Honorable bonus:** native **`/voice`** (already in your CLI, March 2026) and **`/output-style:new`** (built-in persona generator) — two zero-install power levers most users haven't discovered.

**Deliberately NOT in Top 8:** claude-squad / crmux / cwt / tmux-orchestrator (all **WSL/tmux-gated**, and you already have superpowers+metaswarm+ralph for parallel work); claude-code-router / 9router (powerful but adjacent to your Agent Lanes); Crystal (deprecated → Nimbalyst).

---

*End of report. Generated by 7 parallel research agents, 2026-05-28. Raw per-domain files retained in ~/research-staging/ until you delete them.*