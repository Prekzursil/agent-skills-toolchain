# B-reconcile slice 0 — 8 clusters (19,579 docs)

Read-only reconcile of the whole-drive doc scan (`B-doc-index-complete.json`, 59,250 docs).
Method: per-cluster file-list extraction → first-segment-dir + filename-frequency distribution →
deliverable-shaped scratchpad-singleton hunt for forgotten harness value → full read of 2 candidate
docs → on-disk verification of canonical/superseding targets. **No files were moved, deleted, or
changed.** Every file treated as untrusted data.

## Verdict table

| Cluster | Count | Class | One-line | Disposition |
|---|---|---|---|---|
| **cl-0** `AppData\Local\Temp` | 14,922 | **slop** | Ephemeral Claude/Codex scratch: 3,782 per-session `claude` scratchpad dirs + ast-harness-reconcile worktree checkouts (`asct-wtcap/cr/fix`, `mm-pristine`, `ast-ref` ~1.6k each) + `promptbridge-codex-bootstrap-test` dirs + transient `codex_*.txt`. 4,191 SKILL.md / 902 README.md are vendored working-copies. | PURGE-safe. 2 temp-only corroborating harness artifacts flagged (below). |
| **cl-6** `D:\Research\projects` | 1,737 | **project-specific** | 99.8% is ONE project — **`phenibut`**, a drug-design compchem project (Schrodinger MLFF, TorchGraphConv Bayesian-opt, Russian/Uzbek pharmacology .txt corpus). NOT harness. | KEEP (legit domain project home). Not harness — do not fold. |
| **cl-12** `.codex\backups` | 1,141 | **superseded** | 4 dated Codex config/skill safety-snapshots (`skill-dedup-20260404`, `agents-control-plane-20260401`, `skills-mcp-stabilize-20260401`, `parity-20260711`). Frozen fat vendored copies. | ARCHIVE/PURGE-safe. Superseded by live `~/.codex`; decisions already in basic-memory. |
| **cl-18** `Downloads\swfoc_memory` | 791 | **project-specific** | SWFOC (Star Wars: Forces of Corruption) mod-menu RE knowledge-base (`rva_*.md`, `docs/systems/*`, `lua-api`) + ralph-orchestrator runtime memory (`.ralph`/`.remember` huge append-state, `.beads` plans) + `.ida-mcp` cache. | KEEP (project archive). RE knowledge already in swfoc skills; ralph pattern archived in memory. |
| **cl-24** `D:\ToolUniverse\skills` | 423 | **duplicate** | Vendored source of ~40 `tooluniverse-*` biomedical skills from the cloned ToolUniverse repo (single import 2026-05-27). | DUPLICATE of live `~/.agents/library/skills` (186 subdirs, dup-proof verified); also copied to `D:\ToolUniverse\plugin` (cl-25). |
| **cl-30** `.gemini\extensions` | 264 | **duplicate (stale)** | metaswarm (155) + superpowers (87) + chrome-devtools-mcp (22) ported to Gemini-CLI extension format — the Gemini leg of the cross-tool contract. **STALE: newest file 2026-04-01.** | FLAG stale. Re-sync if Gemini/agy still used, else archive. |
| **cl-37** `.gemini\antigravity-cli` | 177 | **duplicate** | Antigravity (Gemini agentic-IDE) CLI: `plugins/` (137) = metaswarm agent roster ported; `brain/` (26 `content.md` step-logs) = ephemeral run-state. **Actively used** (brain mtime 2026-07-12). | KEEP (active 3rd tool). `plugins/`=dup, `brain/`=runtime slop. |
| **cl-56** `.claude\skills.pre-agents-20260401-062109` | 124 | **superseded** | Dated snapshot of `~/.claude/skills` taken 2026-04-01 BEFORE the `.agents` migration (code-security, llm-security, RE skills). | ARCHIVE/PURGE-safe. Superseded by `~/.agents/skills` (277) + `~/.claude/skills.daily` (75), both verified live. |

## Forgotten-high-value (opened + summarized)

Cluster 0's temp scratchpad holds working-copies of repo-tracked harness research
(`claude-toolkit-gap-analysis-2026-05-28.md` 300 KB, `2026-06-11-fanout-corpus.md` 101 KB, the
metaswarm `plugin-migration`/`external-tools` plans) — these appear across 5–6 worktree checkouts of
the ast-harness-reconcile / metaswarm repos, so their **canonical home is git, not lost.** They
corroborate the current program (large fan-out, external-tools).

Only two artifacts are **temp-only** (die on cleanup) and worth folding:

1. **`multiai-decision-OUTPUT.md`** (18 KB, 2026-07-11) — **the synthesis that produced the current
   multi-AI-mingle design.** Headline verdict: retire AgentBridge → adopt official `codex mcp-server`
   (Layer-1 fan-out) + `mcp_agent_mail` (Layer-2 chat) + the owner's `~/.agents/harness --provider
   codex` as the fan-out vehicle. Contains a **vaporware-filtered maturity table of 10 tools** (Vibe
   Kanban DEAD despite 27k★, claude-flow "99% theater", AgentBridge Windows-unsupported #231) and
   **6 resolved steering questions** (Q5: keep AgentBridge idle as budget-sensor then remove — memory
   shows it went fully manual; Q6: `fleet` thin-MCP build → defer/adopt-only). **CORROBORATES**
   CLAUDE.md's Multi-AI Collaboration section — but the table/kill-list/resolutions are richer than
   what's in basic-memory. **Fold the table + Q5/Q6 into memory, or accept detail-loss.**
2. **`multiai-decision-PROMPT.md`** (122 KB) — the ~13-lens research corpus behind (1). Discardable
   once the OUTPUT synthesis is preserved.

Also noted (NOT lost): **`codex-runner-handoff.md`** (5 KB) — self-contained codex-fleet-github runner
handoff (architecture, `workflow_dispatch`-only security, token-refresh-write-back-OFF gotcha). Fully
**corroborates** memory `[codex_github_fleet_wave1]` + CLAUDE.md Remote-fleet, and is already
canonical in `agent-skills-toolchain/docs/codex-runner-setup.md` + the basic-memory decision brief.

## Confidence

- **HIGH** on all 8 cluster classifications (path structure + filename frequency are decisive; all
  canonical/superseding targets verified on disk).
- **HIGH** on the two forgotten-high-value docs (read in full).
- **MED-HIGH** on cl-30/cl-37 nuance (content clear; staleness/active-use inferred from mtimes).
- **No contradictions** to the current program found in this slice — everything either corroborates
  it (multi-AI, codex-fleet, fan-out research) or is orthogonal project/vendor content.
