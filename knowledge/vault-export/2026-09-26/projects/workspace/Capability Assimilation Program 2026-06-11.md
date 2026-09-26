---
title: Capability Assimilation Program 2026-06-11
type: report
permalink: main/projects/workspace/capability-assimilation-program-2026-06-11
tags:
- capability-assimilation
- skills
- video
- hacktricks
- curation
- handoff
---

Multi-session program to assimilate high-value capabilities the strict/rigid curated way (vet → net-new → no-bloat → cross-tool `~/.agents/skills`). **Full spec: `C:/Users/Prekzursil/.claude/CAPABILITY-ASSIMILATION-PROGRAM.md`** (the handoff). Event-ledger milestone #23 (auto-replays at SessionStart).

## DONE (verified)
- mattpocock/skills `handoff` + `grill-me` vendored into canon `~/source/agent-skills-toolchain/skills` + `~/.agents/skills` (Claude via symlink + Codex/agy), MIT-attributed. `mattpocock-skills` marketplace registered as **directory source, NOT installed** (no 15-skill bloat).
- `caveman` absorbed (canon + `~/.agents/skills`, MIT). Live.
- HackTricks API key validated + stored env `HACKTRICKS_API_KEY` (User+process). RAG quota 50/week, 0 used.

## SECURITY (do first)
- ⚠ ROTATE `HACKTRICKS_API_KEY` — pasted in chat (exposed). Update env var after; reference `$env:HACKTRICKS_API_KEY`, never the literal.
- scholarly-access regression carry-over: `c8bcaf7` re-armed Sci-Hub/LibGen + emptied DENY_SUBSTRINGS, LIVE → revert to `c0a27ba` + verdict-time PDF gate. Never call `mcp__sci-hub__*`.

## Wave plan (post-compact, route via /start-task T-tier; gated builds → design/plan review)
- **Wave 1 (priority):** (a) claude-shorts video pipeline — `AgriciDaniel/claude-shorts`, WSL2 Ubuntu (installed), build BOTH reframe engines [built-in MediaPipe + graft `KazKozDev/auto-vertical-reframe` (verthor, YOLOv11+ByteTrack)] and compare; lighter alt `louisedesadeleer/clipify`; VET setup.sh/preflight.sh/export.sh + pin commit + flag-gate Remotion. (b) HackTricks assimilation — clone open wikis (main/cloud/AI markdown) for unlimited local search + thin MCP/skill wrapping REST `POST /api/v1/rag` + `/api/v1/chat` at `https://ai.hacktricks.wiki` (header `X-API-Key`), with content-hash caching + `GET /api/v1/rag/usage` guard (50/wk limit). `hacktricks-training.com` = paid LMS, skip.
- **Wave 2:** autoresearch core loop (keep/discard-auto-git-revert; `krzysztofdudek/ResearcherSkill` or `uditgoenka` core; wire to `.coverage-thresholds.json`); context-mode sandbox pattern (ctx_execute against basic-memory, NOT its hooks/postinstall); scholarly-access revert (safety).
- **Wave 3:** AutoDream-H6 memory consolidation over basic-memory (Orient→Gather→Consolidate→Prune, diff-before-prune + fresh-context verifier; native AutoDream stays OFF; design-review gated); funclip standalone on D: (only if Mandarin transcript-cut job arises); optional NVD/KEV CVE skill.

## DROP (redundant/bloat/low-trust)
AI-Youtube-Shorts-Generator fork, claude-code-video-toolkit (overlap fal-ai-media); gstack (rewrites CLAUDE.md+browser hijack); reddit-office pack (curl|bash + 136 skills); sensenova (China relay token.sensenova.cn); Veridano security-feed (exfil via closed AWS relay); karpathy-guidelines (already hook-enforced); firecrawl 32-pack.

## Paused
BC 15.4 + bcsfe 3.4.0 grill — topic chosen, checkpoint pulled; resume = build update-resilience offsets-manifest + frida-confirm keystones. Deprioritized behind this program, not abandoned.

## Relations
- relates_to [[Workspace Curation — plugins/MCPs de-bloated (2026-06-11)]]
- relates_to [[BC 15.4 + bcsfe 3.4.0 upgrade checkpoint 2026-06-10]]
- relates_to [[agent-skills-toolchain mechanics]]
