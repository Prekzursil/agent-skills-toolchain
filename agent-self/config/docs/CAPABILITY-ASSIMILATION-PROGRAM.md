---
title: CAPABILITY-ASSIMILATION-PROGRAM
type: note
permalink: dqverify-repo-20261013/agent-self/config/docs/capability-assimilation-program
---

# Capability Assimilation Program — Handoff (2026-06-11)

Fresh-agent handoff for a multi-session program: assimilate high-value capabilities into the
workspace the **strict/rigid curated way** (vet → net-new value → no-bloat → cross-tool via
`~/.agents/skills`). Continuity lives in basic-memory + MEMORY.md + event-ledger (more durable
than OS-temp), so this doc is saved durably under `~/.claude/`.

## DONE this session (verified)
- **mattpocock/skills**: `handoff` + `grill-me` vendored into canon `~/source/agent-skills-toolchain/skills`
  + mirrored to `~/.agents/skills` (Claude via symlink + Codex/agy), MIT-attributed. Marketplace
  `mattpocock-skills` registered as a **directory source** (NOT installed → no 15-skill bloat).
- **caveman** absorbed (canon + `~/.agents/skills`, MIT). Live — ~75% output-token cut on trigger.
- **HackTricks API key** validated (RAG `remaining:50/50`); stored as env var `HACKTRICKS_API_KEY`
  (User + process). REST only — no official MCP.

## ⚠ SECURITY — do first
- **Rotate `HACKTRICKS_API_KEY`** at the HackTricks account portal — it was pasted in chat (exposed
  in this transcript). After rotating, update the User env var. Never commit the literal; always
  reference `$env:HACKTRICKS_API_KEY`.
- **scholarly-access MCP regression (carry-over):** `c8bcaf7` "unrestricted mode" re-armed
  Sci-Hub/LibGen + emptied `DENY_SUBSTRINGS` and is LIVE. Revert to `c0a27ba` + add a verdict-time
  PDF-body gate. ⛔ never call `mcp__sci-hub__*`.

## The program — by domain

### 1. Video editing / shorts / reframe  ★ STATED PRIORITY
- **claude-shorts** (`AgriciDaniel/claude-shorts`) — **DO**. Canon-absorb as a `reframe`/`shorts`
  skill. Substrate = **WSL2 Ubuntu** (confirmed installed; default distro, v2). User chose
  **build BOTH reframe engines and compare** ("build 1 and 2 and lets see"):
  - (a) built-in **MediaPipe** center-crop reframe (simpler/faster);
  - (b) graft **verthor** (`KazKozDev/auto-vertical-reframe`, YOLOv11-seg + ByteTrack scene-aware
    camera path, presets talking_head/sports/pets/cars) in place of its reframe step.
  - Lighter alternative if claude-shorts is too heavy: **clipify** (`louisedesadeleer/clipify`).
  - **VET FIRST (gate):** read `setup.sh` / `preflight.sh` / `export.sh`, pin a commit. Gate
    Remotion caption rendering behind a flag (heavy node/Chrome) so the reframe-only path stays light.
  - Deps (~GB): faster-whisper, mediapipe, opencv, torch (CPU or CUDA), ffmpeg, node/Remotion.
  - First step post-compact: `wsl -- bash -lc "command -v ffmpeg python3 node"` to confirm toolchain.
  - Route: T3–T4 (gated build). Acceptance = one horizontal sample → 9:16 subject-tracked clip, both
    engines, side-by-side.
- **funclip** (`{{USER}}/FunClip`) — **KEEP** (user does Mandarin). Standalone app on D: (FunASR +
  torch). Only for Mandarin transcript-cut; not a CC skill, not on the critical path.
- **DROP:** `{{USER}}/AI-Youtube-Shorts-Generator` (faceless generator, overlaps fal-ai-media),
  `digitalsamba/claude-code-video-toolkit` (generation, overlaps fal-ai-media).

### 2. Research — academic / general / deep
- **Keep (already strong):** `deep-research`, `exa-search`/`exa:search`, `research-ops`,
  `consensus-tooluniverse-research`, `tooluniverse` MCP, `scholarly-access` MCP (after the revert above).
- **autoresearch core loop** — **DO (build lean)**. Lift `krzysztofdudek/ResearcherSkill` (single
  SKILL.md) OR `uditgoenka` `commands/autoresearch.md` core: the keep/discard-with-auto-git-revert
  optimization loop, wired to `.coverage-thresholds.json`. Drop its learn/improve/reason/security
  commands (already covered). Canon-absorb. Route: T2–T3.

### 3. RE + general security  (incl. HackTricks corpus)
- **HackTricks assimilation** — **DO (build, 2 layers)**:
  - **SCOPE (user, 2026-06-11): assimilate the FULL wiki as a GENERAL knowledge base — NOT RE-scoped.**
    HackTricks covers far more than pentest/RE (networking, crypto, forensics, web, cloud, AI, dev, OS
    internals, protocols…). Index ALL of it; the `hacktricks` skill is a general reference surfaced for
    ANY domain/use-case, not gated to RE/security workflows. "All info, all cases." The skill
    description must be domain-neutral so it triggers broadly.
  - (a) **LOCAL corpus (unlimited, no rate limit):** the wikis are open markdown on GitHub — clone
    HackTricks main + cloud + AI books → local full-text / vector index → a `hacktricks` search
    skill (or thin MCP). This is the bulk "assimilate".
  - (b) **AI API (curated, RATE-LIMITED 50 RAG/week):** thin MCP/skill wrapping
    `POST /api/v1/rag` + `POST /api/v1/chat` at `https://ai.hacktricks.wiki`, header
    `X-API-Key: $env:HACKTRICKS_API_KEY`, with **response caching** (use `content-hash-cache-pattern`)
    and a **usage guard** (`GET /api/v1/rag/usage` before spend). Reserve API calls for when local
    search is insufficient.
  - `hacktricks-training.com` = paid LMS/labs (account-based) — **not assimilable knowledge; skip.**
  - Build as a canon skill + optional local MCP (`mcp-server-patterns`). Route: T3. Security: key
    env-var only; never log the literal.
- **Keep (already strong):** `reverse-engineering-toolkit`, IDA/Ghidra/Binary-Ninja/Frida MCPs,
  `hexstrike-ai`, `security-review`/`security-bounty-hunter`/`security-scan`, semgrep/bandit/trivy/gitleaks.
- **DROP from triage:** Veridano security-feed (routes threat-queries through a closed AWS relay =
  exfil; NVD/CISA data is free direct), `sensenova` (China relay `token.sensenova.cn`, not CC-format).
  Optional: a tiny canon skill hitting NVD 2.0 + CISA KEV JSON direct if you want a CVE feed.

### 4. Memory / cognition
- **AutoDream-H6** — **DO (build, GATED)**. On-demand consolidation pass over basic-memory
  (Orient → Gather → Consolidate → Prune) **with diff-before-prune + a fresh-context verifier**
  (per SELF-CALIBRATION law: intrinsic self-correction fails, needs an external signal). Native
  AutoDream stays **OFF** (it auto-prunes the hand-curated `MEMORY.md` and is blind to
  basic-memory/event-ledger). Touches memory + possibly a scheduled hook → **design-review gate**.
  Route: T3.
- **context-mode sandbox pattern** — **DO (build lean)**. Re-implement `ctx_execute` /
  `ctx_fetch_and_index` against basic-memory; do **NOT** take its 5 hooks or settings.json-mutating
  postinstall. Route: T2.

## DROP list (one-line reasons)
- `gstack` (medium-8) — rewrites CLAUDE.md + browser hijack. `reddit-office` pack — `curl|bash`
  installer + 136 skills, overlaps document-skills/nutrient. `karpathy-guidelines` — 4 rules already
  hook-enforced harder in canon. `firecrawl` 32-pack — bloat-magnet (only caveman was worth it; done).
  `medium-8` — 7/8 already owned. Native AutoDream — auto-prune doctrine violation.

## Wave plan (post-compact, each routed via `/start-task` T-tier; gated builds → design/plan review)
- **Wave 1 (priority):** (a) claude-shorts video pipeline — vet → build both engines → sample
  compare; (b) HackTricks assimilation — local corpus + cached API skill.
- **Wave 2:** autoresearch core loop; context-mode sandbox; scholarly-access revert (safety).
- **Wave 3:** AutoDream-H6 (design-review gated); funclip standalone (only if a Mandarin job arises);
  optional NVD/KEV CVE skill.

## Paused
- **BC 15.4 + bcsfe 3.4.0 grill** — topic chosen, checkpoint pulled (see basic-memory
  `checkpoints/bc-15.4-bcsfe-3.4.0-upgrade-checkpoint-2026-06-10`). Resume point = build the
  **update-resilience offsets-manifest** (auto-rematch + version canary); frida-confirm keystones
  live (getGlobal first, load→hold→detach, no per-frame hook). Not abandoned — deprioritized behind
  this program.

## Suggested skills for the next session
- `simplest-probe-first` (probe before heavy paths), `fresh-context-verify` (AutoDream + RE anchors),
  `security-review` (vet claude-shorts/verthor scripts before running), `content-hash-cache-pattern`
  (HackTricks RAG cache), `mcp-server-patterns` (HackTricks MCP), `using-git-worktrees` (parallel
  builds), `council` / `design-review-gate` (AutoDream-H6 gate), `writing-skills` (canon skill authoring).

## Canon mechanics reminder
Add a skill = put it in `~/source/agent-skills-toolchain/skills/<name>/` → it appears in
`~/.agents/skills` (Claude reads via the `~/.claude/skills` symlink; Codex/agy read the dir directly).
Validator: `~/source/agent-skills-toolchain/scripts/validate-all-skills.ps1`. Rule: no angle-brackets
in `description`. Commit the canon repo to make the source-of-truth durable (not yet committed).