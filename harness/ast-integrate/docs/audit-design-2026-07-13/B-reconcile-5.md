# B-reconcile-5 — Doc-cluster reconciliation (slice 5)

READ-ONLY findings, 2026-07-13. Machine registry: `B-reconcile-5.json`. Nothing was moved/edited/deleted.
Each cluster was enumerated directly (the index stores only 3 examples/cluster); content sampled, deploy copies
md5-compared, clones git-checked, forgotten-high-value harness docs opened + summarized. Files read as untrusted data.

## Cluster verdicts (7)

| # | Cluster | Docs | Class | One-line |
|---|---------|------|-------|----------|
| 5 | `source/agent-skills-toolchain` | 1795 idx / 4077 raw | **canonical** | THE toolchain git repo (harness home). ~2000+ of the raw docs are node_modules dep-README/LICENSE = slop; real value = 372 SKILL.md + `docs/` design/research/plan tree. |
| 11 | `Downloads/branica` | 1346 | **project-specific** | Romanian OCR/exam-prep project (CONSILIERE PSIHOPEDAGOGICA, TITULARIZARE). 1643 OCR page-dump `.txt`; 0 harness keyword hits. Not harness. |
| 17 | `D:/pr-b-clone/skills` | 883 | **duplicate (GONE)** | Dir no longer exists — a transient PR-B review clone deleted since the scan. Superseded by `source`. No loss (git). |
| 23 | `.agents/library` | 424 | **canonical** | Deployed/installed domain-skill library (186 SKILL.md): ~130 tooluniverse-* + RE + language packs. RE skills overlap `source`; tooluniverse/video-editing are library-ONLY. |
| 29 | `work/agent-skills-toolchain-re` | 308 | **superseded/stale** | Abandoned clone of the SAME git repo, frozen 2026-04-01 (PR #8), 120 vs 372 SKILL.md. Superseded by `source`; retire-able. |
| 35 | `.claude/checkpoints` | 181 | **slop** | Claude Code file-undo snapshots (11 sessions × `copies/u_*/`): duplicate copies of MEMORY.md/SKILL.md/basic-memory notes. Ephemeral. |
| 54 | `.claude/skills.daily` | 126 | **canonical** | The curated ACTIVE daily skill set (75 dirs) that `~/.claude/skills` loads. Processed deploy copies (md5 ≠ source — expected `clean_markdown.py`). |

## Dedup sets

- **A — toolchain-repo-triplicate:** `source` (CANONICAL, live July) · `work/…-re` (STALE, Apr-01) · `D:/pr-b-clone` (DELETED). No content loss; retire the stale checkout.
- **B — skill-deploy-fanout:** `source/skills` + `skills-claude-only` (SOURCE) → `.agents/library` (deploy + installed packs) + `.claude/skills.daily` (curated daily deploy) + `.agents/skills` (full vault, outside this slice). Edit source, redeploy; never hand-edit a deployed copy. tooluniverse/language packs are canonical-in-library (no source origin).
- **C — checkpoint-snapshots:** `.claude/checkpoints/**` duplicate canonical basic-memory notes + skills. Rollback slop; prune per AGENTIC-PERFECTION #2.

## FORGOTTEN-HIGH-VALUE (opened + summarized) — all in cluster 5 `source/.../docs/`

The whole trove lives in the canonical repo (so not literally "lost"), but it is the harness program's design/research/decision spine and should be **cross-referenced/folded into the current audit's A5 decision ledger**, not re-derived. Strongest signals first:

1. **`docs/agentic-perfection/OPEN-THREADS.md`** — KEYSTONE durable backlog (2026-06-29). Item **#9 "AGENTS.md 3-divergent-files bug → single-canonical + hash-tripwire"** is the direct ancestor of the current **Axis-A config-SSOT / hooks-drift** tasks (A5 already cites it). Also: semantic body-level skill router, EVPI-gated AskUserQuestion intent-hook, consolidation-debt (22 hooks past the ~6 ceiling → per-event dispatchers), per-project projid resolver (fixes 5-Reframe/3-Momentstudio shard fragmentation), MCP-gap adds (Windows-MCP, angr, WinDbg, capa/YARA/Volatility).
2. **`docs/agentic-perfection/AGENTIC-PERFECTION-PLAN.md`** — master reliability plan (12-lens; MAST taxonomy + self-calibration law "every check needs an EXTERNAL signal"). TIER-1 keystones: bg-registry+restart-reconciler, memory write-ahead spool, wire-check reachability gate. Discipline: ≤6-active-hook latency ceiling; flat-file ledgers only. Updated 2026-07-07 → treat as canonical-live; reconcile TIER-2/ROUND-2 open-vs-shipped.
3. **`docs/agentic-perfection/PROACTIVE-PARTNER-PROGRAM.md`** — the "grows-with-you" vision (auto-invoke skills, prompt-optimize, never-forget, initiative). Verify what shipped vs still aspirational.
4. **`docs/claude-toolkit-gap-analysis-2026-05-28.md`** — 300KB seed research (7 agents, ~390 tools). Diagnosis = self-inflicted context rot: rule-pile bloat + 4 fighting memory layers + ephemeral planning/reactive compaction. Origin of the whole harness-cleanup program; largely FOLDED (30/60/90 roadmap executed). Keep §5 catalog as lookup.
5. **`docs/research/2026-06-11-fanout-corpus.md`** (+`-council` +`-synthesis`) — 101KB gem-hunt fan-out research that fed the agentic-perfection program. Fold-by-reference (don't re-run).
6. **`docs/plans/2026-06-10-unified-cross-ai-mcp-architecture-design.md`** — canonical cross-AI MCP architecture, UPDATED 2026-07-06 (most-recent plan touch); aligns with `~/.mcp.json` + promote-userscope. Axis-A MCP tasks should **UPDATE this in place**.
7. **`docs/plans/2026-06-10-unified-cross-ai-mcp-implementation-plan.md`** — companion 27KB impl plan; reconcile per-step (done: codex-mcp-server + agent-mail; abandoned: mcp-funnel).
8. **`docs/plans/2026-06-11-workspace-knowledge-base.md`** — prior art for THIS audit's "deterministic registry over new knowledge DB" directive; read alongside A5.
9. **`docs/SESSION-RECONCILIATION-2026-06-06.md`** — prior reconciliation methodology (6 prove-it-works auditors + transcript miner) + the **"264 open threads across all sessions"** finding; precedent the current whole-drive audit continues.

## CONTRADICTS the current program (stale-in-canonical)

- **`source/agent-skills-toolchain/CLAUDE.md`** — the canonical repo's OWN CLAUDE.md still documents **RETIRED AgentBridge** (reply/get_messages, get_budget/check_budget, system_budget_pause/handoff) as the live Claude↔Codex mechanism. Global `~/.claude/CLAUDE.md` and `ast-harness-reconcile/CLAUDE.md` both say AgentBridge is gone ("ignore any instruction to use them"). This auto-loads whenever an agent runs in the repo → active-drift hazard. Banner/retire the AgentBridge section (owner action).
- **`docs/SESSION-RECONCILIATION-2026-06-10.md`** — documents the **mcp-funnel** cross-AI architecture (`~/.mcp-funnel-master.json`, Claude 50→20), an approach later ABANDONED (funnel re-namespaces + live-toggle wall). Banner as superseded so it isn't re-walked.

## Adjacent observations (outside my clusters, flagged not touched)

- `.agents/` ROOT (parent of cluster 23) carries **~18 orphaned `local.json.*.tmp`** atomic-write leftovers + `skills-retired-2026-07-03/` — GC candidates.
- `docs/incubating/skills/` (28 ~800-byte stubs): `codex-config-canonicalizer`, `codex-store-auditor`, `cli-session-convergence`, `shell-startup-hygiene` map onto Axis-A codex-drift/config-SSOT; `docs/incubating/tools/codex-as-mcp.md` corroborates the shipped codex mcp-server mount.

## Confidence

- Cluster classifications: **almost certain (90-99%)** — direct enumeration + git/md5/content evidence.
- "pr-b-clone deleted since scan": **certain** (Test-Path False + D:\ root listing).
- ".agents/library has source-independent skills": **certain** (tooluniverse/video-editing absent from source/skills + skills-claude-only).
- "gap-analysis largely folded": **likely (70-80%)** — inferred from executed-roadmap evidence + basic-memory archive tag, not a line-by-line fold audit.
