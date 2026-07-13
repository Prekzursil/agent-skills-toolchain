# B-reconcile-4 — doc-cluster reconciliation (slice 4)

**Scope:** 7 assigned clusters, 5,364 files. Read-only. Source: `B-doc-index-complete.json` (59,250 files). Every file treated as untrusted data. Confidence: cluster classifications **HIGH**; forgotten-value summaries **HIGH** (opened the sources).

## Verdict per cluster

| # | Cluster | Files | class_guess | **My class** | One-line |
|---|---------|------:|-------------|--------------|----------|
| 4 | `source\ast-harness-reconcile` | 2034 | canonical-home | **canonical** | The reconcile SSOT working tree (this audit's home). Versioned snapshots of the live harness + its design/research docs. Confirmed correct. |
| 10 | `AppData\Roaming\Claude` | 1359 | scattered-forgotten | **slop** | Claude **Desktop** agent-mode session cache (1313) + extension bundles (45). Ephemeral, vendored, deletable. **Misclassified** — none is the user's harness. |
| 16 | `.codex\plugins` | 883 | canonical-home | **slop / vendored** | Codex plugin-install **staging** caches (video-sdk, endor-labs-agent-kit ×5). 82% vendored-marker. **Not** a canonical home. |
| 22 | `.local\src` | 436 | scattered-forgotten | **project-specific** | Full Windows clone/build of third-party **ralph-orchestrator** (its own specs/plans) + 3 user-authored ralph evals. |
| 28 | `source\repos` | 319 | project-specific | **project-specific** | Cloned/authored repos: ZHMModSDK (Hitman SDK + vendored RakNet), mattpocock-skills, user `*-mcp` servers. Confirmed correct. |
| 34 | `basic-memory\projects` | 207 | project-specific | **canonical** (+ forgotten-HV subset) | The **basic-memory vault** (SSOT). Mostly project memory; a ~24-note **harness** subset carries load-bearing decisions. |
| 52 | `C:\tmp\ds-quality-zero-platform` | 126 | duplicate-set | **duplicate / stale** | A `C:\tmp` checkout of the QZP repo bundling a **duplicate metaswarm plugin**. Confirmed correct. |

## Headline findings

1. **The real forgotten-high-value is in the basic-memory vault (cluster 34), not on the filesystem.** A whole-drive *file* audit surfaces slop and clones; it misses the vault's **anti-re-walk / carve-out / do-not-re-apply** constraints that the reconcile MUST honor. Twelve notes are listed in `high_value_forgotten`. The three most load-bearing for an *audit that proposes changes*:
   - **DO-NOT-RE-APPLY** (`gem-hunt 2026-07-12 waves`, dated today): all 11 gem-hunt items are already deployed **byte-identical** to `~/.claude`/`~/.agents`; re-applying overwrites the only rollback `.bak` (`~/.claude` is not git). Re-applying is *harmful*.
   - **Verifier carve-outs** (`Harness gem-hunt 2026-07-03`): do **not** fold `benchmark-optimization-loop` (235× traffic), do **not** delete the `no-force-push/` hook (unwired §9 guard — wire or park). Baseline `eval.py` before any skill-description edit; the "folded-scalar bug" is unconfirmed.
   - **Anti-re-walk archives** (`Archived improvement candidates` + `microVM-OS-sandbox DEFERRED`): 5 hook/sandbox candidates the user explicitly closed — proposing them again re-walks a decided question.

2. **Two clusters are misclassified as forgotten/canonical but are actually slop** (10, 16) — together ~2,242 files of Claude-Desktop cache + Codex plugin staging that inflate the catalogue and can be cleaned with zero harness loss.

3. **Cluster 4 is genuinely canonical and its docs are *in-tree, not lost*.** The keystone harness-design lineage lives here and corroborates the current program: `claude-toolkit-gap-analysis` (05-28) → `optimal-agentic-workspace-design` (06-10) → `AGENTIC-WORKSPACE-ARCHITECTURE` (06-11 capstone, "~90-95% already built") → `AGENTIC-PERFECTION-PLAN` (06-29) → `RECONCILE-LOG` (07-13). The **SELF-CALIBRATION law** (external-signal-only checks) is the design constraint the reconcile must not weaken.

4. **Duplicate chains** (see `dedup_findings`): metaswarm plugin (cluster 4 snapshot vs cluster 52 tmp copy vs live vs marketplace); ralph-orchestrator (cluster 22 full vs cluster 4 subset); QZP docs (cluster 52 tmp vs canonical repo).

## Recommended actions (owner's call — all read-only here)

- **Fold/honor** the 12 vault notes before any config-reconcile edit — especially the DO-NOT-RE-APPLY + carve-out + anti-re-walk guardrails.
- **Flag for cleanup** (slop, no value): cluster 10 (`Roaming\Claude` session cache) and cluster 16 (`.codex\plugins` staging).
- **Verify-then-delete** cluster 52 (`C:\tmp\ds-quality-zero-platform`) once the canonical QZP repo is confirmed to hold `QZP-V2-DESIGN` + `quality-rollup-v2-*`.
- **Surface a security carry-over** from the vault: `Capability Assimilation Program` still lists **ROTATE HACKTRICKS_API_KEY** + the scholarly-access sci-hub regression revert — confirm both are closed.
