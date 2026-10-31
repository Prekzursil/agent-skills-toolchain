---
title: WAVE0-recon
type: note
permalink: dqverify-repo-20261013/docs/audit-design-2026-07-13/wave0-recon
---

# Wave-0 Recon — WU-3 back-port list & WU-5 Stop-hook inventory

- **Date:** 2026-07-13
- **Mode:** READ-ONLY recon (no files modified except this report). `ci/harness/` untouched (concurrent editor).
- **Scope:** Task A = skills to back-port into repo canonical; Task B = plugin Stop-hook inventory for the WU-1 re-entrancy guard.

---

## Task A — WU-3 back-port list ("the 22 daily-gem skills")

### Method
- Repo canonical = `C:\Users\Prekzursil\source\ast-harness-reconcile\skills\` — skills counted at two tiers: direct children `skills\<name>\SKILL.md` **and** `skills\external\<name>\SKILL.md`. **277** distinct skill dirs.
- Live daily set = `C:\Users\Prekzursil\.claude\skills.daily\` (flat `<name>\SKILL.md`). **75** skill dirs. `~\.claude\skills\` mirrors `skills.daily` (identical file set — the curated daily symlink/copy), so the two are interchangeable for this diff.
- Back-port set = **daily − repo** (present in daily, absent from repo canonical).

### Result: TRUE COUNT = 22 (exactly matches the "22 gems" claim — no discrepancy)

Ordered back-port list (each = pure-additive; source path under `C:\Users\Prekzursil\.claude\skills.daily\<name>\`):

| # | Skill | Size | What it is (1-line) |
|---|-------|------|---------------------|
| 1 | `agent-as-judge` | 15.7 KB | Advisory, evidence-citing Agent-as-a-Judge — second opinion on whether a completion meets its DoD, AFTER the deterministic gates; shadow, never gates. |
| 2 | `bc-drive-plus` | 104.5 KB | Additive enhancements to the bc-drive Battle Cats canvas driver (bounded one-shot touch-dispatch capture to resolve the stripped NewButton ctor RVA). |
| 3 | `bc-update-survival` | 165.1 KB | Toolpack that RETIRES hardcoded RVAs when a BC update relinks `libnative-lib.so` (AOB wildcard resolver + ghidriff auto-port + update-triage). |
| 4 | `compchem-validators` | 86.9 KB | OUTPUT quality gate for docking/MD/free-energy (PoseBusters pose validity + cheap-tier prefilters before token-gated tiers). |
| 5 | `design-studio-session` | 35.0 KB | Interactive-modify behind `design-studio session`: point at a LIVE element in a running app and iteratively restyle with Claude+Codex. |
| 6 | `diff-blind-test-synth` | 7.4 KB | Independent check that a patch satisfies spec — synth tests from ONLY spec+public API, run vs pre/post-patch trees; shadow. |
| 7 | `execution-grounded-bon` | 37.3 KB | Pick best among several candidate patches WITHOUT an LLM judge — execution-consensus across cross-vendor fan-out; shadow. |
| 8 | `ida-multi-mcp` | 9.3 KB | Analyze several binaries in IDA via one MCP endpoint; re-find a function whose address SHIFTED after a rebuild (BCSD similar_functions). |
| 9 | `llm-decompile-verify` | 10.3 KB | Recover compilable C from a stripped binary with a recompile-verify round-trip gate (anti-faking). |
| 10 | `media-dub` | 8.5 KB | Local DUB of a video (re-voice into another language, keep the speaker's voice) via Chatterbox-Multilingual on the media_studio substrate. |
| 11 | `multi-ai-mingle` | 39.4 KB | Seamless local Claude↔Codex collab — parallel Codex threads via codex mcp-server + live agent-mail chat/file-lease channel. |
| 12 | `orchestration-patterns` | 13.7 KB | Proven cross-vendor multi-agent orchestration patterns for this Windows box (Architect→Editor split, sandbox ladder, repo-map, retry caps). |
| 13 | `packaged-artifact-smoke` | 26.0 KB | Prove a BUILT deliverable works end-to-end via golden journeys against the packaged artifact + deterministic postcondition probes. |
| 14 | `pdf-reader` | 6.6 KB | Read a PDF and ground every claim in a real source span (Anthropic Citations API + pdf-reader MCP). |
| 15 | `qiling-emulation` | 7.0 KB | Emulate/sandbox a native ARM/ARM64 `.so` off-device in Qiling (dynamic-off-device complement to frida). |
| 16 | `re-triage-preflight` | 101.7 KB | Fast hash-cached RE triage preflight on an unknown binary (format/entropy/DIE/FLOSS/capa) before deep analysis. |
| 17 | `refactor-equivalence` | 6.4 KB | External proof a "pure refactor" is behavior-preserving (CrossHair diffbehavior / Hypothesis differential); shadow. |
| 18 | `smallest-check-ladder` | 7.1 KB | Run "the smallest test that could still catch this change" via an L0–L3 ladder (lint→impacted→full→e2e). |
| 19 | `trail-of-bits-re` | 7.0 KB | Trail of Bits security/RE skill packs (differential-review, variant-analysis, yara-authoring) + marketplace map. |
| 20 | `ui-drive` | 44.9 KB | Thin rail-router driver for a LIVE web/Electron app (a11y-ref→CDP css→vision xy); point/actuate + ephemeral restyle loop. |
| 21 | `ui-invariant-walk` | 13.5 KB | Property-based random-walk oracle driving a running app, asserting UI invariants (no dead clicks / no route errors) via fast-check; shadow. |
| 22 | `workflow-authoring` | 11.5 KB | Author/debug saved Claude Code Workflows (the `agent`/`parallel`/`phase` fan-out API + gotchas). |

These 22 are exactly the 2026-07-12 gem-hunt adoptions and all appear in the live available-skills list (confirming they are enabled/loaded in the daily set).

### Collision / additivity check
- **0 collisions.** Every one of the 22 names was verified absent **anywhere** under the repo skills tree (recursive dir-name scan, not just the two canonical tiers). → **The back-port is truly pure-additive.**
- **Caveat — 53 overlapping skills exist in BOTH daily and repo** (intersection). WU-3 must **only ADD the 22** and must **NOT** copy/overwrite these 53 — that would not be pure-additive and could clobber repo-canonical versions. Content drift between the daily and repo copies of the 53 was **not** diffed (out of the additive scope). If a "sync the overlap" is ever wanted, that is a separate, non-additive work-unit requiring a per-skill content diff + review.
  - The 53 (for reference): audio-extract-mix, battlecats-event-unlock, bc-drive, bcsfe-save-roundtrip, binary-ninja, biomedical-paper-triage, caption-burn, cheat-engine-workflow, cheminformatics-rdkit, clarify-requirements, codex-consult, council, deep-research, design-review-loop, design-studio, design-system, figma, firecrawl, fresh-context-verify, frida, game-re-binary, gem-hunt, ghidra-mcp, grill-me-extensive, hacktricks, hexstrike-ai-mcp, ida-pro-mcp, imagegen, mcp-fleet-curation, python-testing, qdx-rush, radare2, re-ensure, reframe, reverse-engineering-toolkit, scholarly-literature-review, schrodinger-maestro-driver, security-review, silence-trim, social-find-post, social-media-toolchain, speech, strategic-compact, structure-based-screening, swfoc-modding, tdd-workflow, tooluniverse, transcribe, transpose-to-figma, ui-audit, ui-ux-pro-max, video-convert, video-watermark-removal.

### Implementation note for WU-3 (target tier)
Repo has two skill tiers (`skills\<name>\` and `skills\external\<name>\`). The daily set is flat, so decide the target tier per skill (most likely top-level `skills\<name>\` to match the daily layout; `skills\external\` if they are to be treated as external adoptions). This is a WU-3 decision, flagged here — not decided by recon. Some candidates ship non-SKILL.md payloads (e.g. `re-triage-preflight` 101.7 KB, `bc-update-survival` 165.1 KB include scripts/references) — copy the whole dir, not just SKILL.md.

---

## Task B — WU-5 plugin Stop-hook inventory

### Settings-level Stop hook (NOT a plugin — this is the guard's HOME)
`~/.claude/settings.json` `hooks.Stop` has **exactly one** entry: the shared harness dispatcher
`python "C:/Users/Prekzursil/.agents/harness/dispatcher.py" --provider claude --event Stop` (timeout 5s).
This is the dispatcher whose **WU-1 re-entrancy guard** must tolerate the plugin Stop hooks below. (Note: the settings dispatcher points at `~/.agents/harness/`, which the repo `ci/harness/` mirrors.)

### Enabled-plugin Stop hooks = 3 (matches the RFC's "3 plugin Stop hooks")

All three plugins are ENABLED in settings.json and all three target scripts EXIST → **none are vestigial**. Each is **dormant-but-wired by default** (fires as a no-op / early-return unless a specific trigger is present).

| # | Plugin | Hook file / target script | Timeout | Behavior (re-entrancy relevance) | Default state |
|---|--------|---------------------------|---------|----------------------------------|---------------|
| 1 | **codex** `@openai-codex` | `plugins\marketplaces\openai-codex\plugins\codex\hooks\hooks.json` → `scripts\stop-review-gate-hook.mjs` (5711 B, 2026-05-20) | **900s (15 min)** | The "codex 900s stop-review-gate". Config-gated: `if (!config.stopReviewGate) return;`. When ON, spawns `codex-companion.mjs task --json` (15-min `spawnSync` timeout) to review the last turn; on non-ALLOW it emits `{"decision":"block", reason}` → **blocks Stop / re-enters**. Session-scoped (filters jobs by `session_id`). | **Dormant** (`stopReviewGate` off by default; the "Optional" gate). Emits only an advisory log-note when a Codex job is still running. |
| 2 | **hookify** `@claude-plugins-official` | `plugins\marketplaces\claude-plugins-official\plugins\hookify\hooks\hooks.json` → `hooks\stop.py` (1403 B, 2026-07-13) | 10s | Loads user rules from `.claude/hookify.*.local.md` (event=stop) and evaluates them; can emit a block/systemMessage. Fail-open (always exit 0; import/other errors → allow). | **Inert** unless the project has `.claude/hookify.*.local.md` stop rules. None are wired into an active project `.claude/` (see stale-state note). |
| 3 | **ralph-loop** `@claude-plugins-official` | `plugins\marketplaces\claude-plugins-official\plugins\ralph-loop\hooks\hooks.json` → `hooks\stop-hook.sh` (7533 B, 2026-07-13) | (none set → CC default) | **The canonical re-entrant blocker.** Reads project-scoped `.claude/ralph-loop.local.md`; if an active loop exists (and not complete / under max_iterations / matching `session_id`), it emits `{"decision":"block","reason":<same prompt>,"systemMessage":"🔄 Ralph iteration N"}` → **blocks Stop and re-injects the SAME prompt**, bumping `iteration`. Already has session isolation (state `session_id` vs hook `session_id`; legacy no-id files fall through). | **Dormant** (no `.claude/ralph-loop.local.md` exists anywhere — see below). |

### Plugins with hooks.json but NO Stop matcher (out of scope for WU-5)
- **claude-reflect** `@claude-reflect-marketplace` — `marketplaces\claude-reflect-marketplace\hooks\hooks.json` (no `Stop`).
- **metaswarm** `@metaswarm-marketplace` — `plugins\metaswarm\hooks\hooks.json` (no `Stop`).
- **remember**, **skill-creator**, **superpowers** (`@claude-plugins-official`) — enabled, but no `hooks.json` and no `hooks` in plugin.json → no Stop hook.

### Stop hooks that exist but are DISABLED (would add Stop hooks if enabled — currently inert)
- **security-guidance** `@claude-plugins-official` — has a Stop hook (`hooks.json` Stop:true) but `enabledPlugins=false`.
- **ecc / everything-claude-code** — has Stop hooks (`hooks\hooks.json` Stop:true) but `enabledPlugins=false`.
- (`marketplaces\claude-plugins-official.bak\...` and `marketplaces\context-mode\...` are inactive marketplace copies — not loaded.)

### "Must-tolerate" list for the WU-1 dispatcher-boundary re-entrancy guard
The guard sits in the harness Stop dispatcher, which fires on **every** Stop — including Stops that another Stop hook BLOCKS to re-enter. It must tolerate:

1. **A plugin Stop hook returning `{"decision":"block"}` that re-enters the turn** (ralph-loop always; codex-gate when `stopReviewGate` on; hookify when a stop rule matches). The dispatcher will then fire AGAIN on the next Stop — the guard must **not** mis-classify the re-entrant Stop as a duplicate/loop-abort and must **not** double-write turn/goal-ledger data per re-entry.
2. **ralph-loop re-injecting the identical prompt each iteration** — the harness repetitive-action / drift detectors must not false-positive on the same prompt recurring across ralph iterations.
3. **A long-running sibling Stop hook (codex up to 900s)** running in parallel with the harness Stop hook (5s). A `block` from any sibling means the session is NOT ending; the guard must not treat its own quick Stop completion as "session ended."
4. **Session-scoped re-entry** — ralph-loop and codex-gate both key on `session_id`; the guard should likewise be session-keyed (consistent with the prior harness session-scoping fix) so concurrent sessions sharing cwd don't cross-trigger.

### Disposition recommendation (recommendation only — NO action taken)
- **codex stop-review-gate — KEEP.** Wired + valuable; dormant by default (opt-in `stopReviewGate`). The guard must tolerate its 900s runtime + block-decision when enabled. No disable.
- **hookify stop — KEEP.** Fail-open, 10s, inert without rule files. Low risk. No disable.
- **ralph-loop stop — KEEP.** The primary re-entrancy source but already session-isolated and dormant (no active state). No disable — WU-1 exists precisely to tolerate it.
- Net: **all 3 KEEP**; none vestigial, none recommended for disable. WU-1's job is tolerance, not removal.

### Stale `ralph-loop` / loop / hookify state files (reported, NOT deleted)
- **No active `.claude/ralph-loop.local.md` anywhere** — both `~/.claude/ralph-loop.local.md` and the repo `.claude/ralph-loop.local.md` are absent, and a recursive scan found none. **The re-entrant ralph loop is dormant; no stale stop-state to clean.**
- Related artifacts found (none are active plugin stop-state — do NOT delete):
  - `C:\Users\Prekzursil\.claude\gem-hunt-2026-07-12\staging\C2-rubric-canon-merge\.design\loop-state.json` (1878 B, 2026-07-12) — a **design-studio loop** state file, a DIFFERENT subsystem (not the ralph-loop Stop hook).
  - `C:\Users\Prekzursil\.claude\harness-meta\instinct_gem_queue\artifacts\hookify__*.local.md` ×3 (2026-07-12) — **staged hookify RULE candidates** in the instinct gem queue, NOT wired into any project `.claude/`. Inert to the hookify Stop hook unless promoted into a project `.claude/hookify.*.local.md`.
  - `C:\Users\Prekzursil\source\ast-harness-reconcile\tools\editor\ralph-orchestrator\vendor\...` — a **vendored ralph-orchestrator tool tree** (Rust crates + docs + its own `.claude/agents/ralph-loop-runner.md`), unrelated to the ralph-loop *plugin* Stop hook. Repo content, not runtime state.
  - Two basic-memory notes mentioning ralph (`ralph_headless_mcp_trust_gate.md`, `reference_ralph_loop_changelog_pointer.md`) — memory, not state.

### Incidental drift observations (not Stop-hook related; flagged, not acted on)
- `C:\Users\Prekzursil\.claude\plugins\cache\` is polluted with **hundreds of `temp_subdir_*.clone`** dirs (marketplace clone leftovers) — cleanup candidate for a hygiene pass, unrelated to Wave-0.
- `marketplaces\claude-plugins-official.bak\` is a stale duplicate of the official marketplace.