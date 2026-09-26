---
title: harness live deploy + hosted-models gem-hunt 2026-09-02
type: decision
permalink: main/decisions/harness-live-deploy-hosted-models-gem-hunt-2026-09-02
tags:
- harness
- deploy
- mcp-control-plane
- basic-memory
- gitleaks
- gem-hunt
- hosted-models
- glm53-space
---

# Harness live deploy + hosted-models gem-hunt (02.09.2026)

## Observations
- [fact] Live deploy done 02.09.2026 from a clean `main` worktree @ 5fa34fd: `install.py --deploy --target harness` (43 files) + `--target command-center` (1); backups at `~/.agents/harness/backups/deploy-20260902-043028/` (harness tree, 3 merge scripts, agents.json before x_cursor, cursor/codex/home mcp targets before sync). #deploy
- [decision] Cursor's basic-memory bridge is now DECLARED in the registry: `agents.json` -> `mcp.servers.basic-memory.x_cursor.stdio_bridge = {command: C:\Python314\python.exe, args: [~/.agents/scripts/bm_cursor_http_session.py, --stdio]}`; the merge renders it plus `--url <registry url>`. Name-based special-casing inside `merge_generated_cursor_mcp.py` is gone (reunited script from #309). #mcp-control-plane #basic-memory
- [fact] After staging the reunited merge scripts: repo suite 43 pass, live suite 60 pass, `merge_generated_cursor_mcp.py --check` drift=0, `sync_shared_state.ps1` all SUCCESS, Codex `config.toml` byte-identical. PR #312 carries the live test lineage (60 tests) into the repo so CI guards both contracts. #deploy
- [fact] NOT deployed: hook registrations (`~/.claude/settings.json`). Live has `WorktreeCreate`/`WorktreeRemove` and lacks `InstructionsLoaded`; `registration.py` would drop live events. Needs reconciliation before any `install.py --bootstrap`. #hooks
- [fact] gate-secrets root cause: `gitleaks git` defaults to `git log --all` and `fetch-depth: 0` fetches every remote branch, so the 802 MB P2 capture on `handoff/cloud-agent-2026-09-02` / `p2/loop-to-green-2026-09-02` turned every PR red (1434 commits / 1.10 GB / 820 leaks vs 0 in the PR range). Fixed by `--log-opts="--full-history HEAD"` (PR #313, merged; main scan = 950 commits, 219 MB, 0 leaks, 17s). Reruns reuse the old merge snapshot; `gh pr update-branch` is what re-gates a PR. #gitleaks #ci
- [fact] Blast radius of the capture (private repo only): 787 gitleaks hits inside `harness/ast-integrate`, mostly captured HTML/research fixtures; 5 `databricks-api-token` hits in three copies of `_USER-PROMPTS.md` (WFA-0141/live, AUD-0074, WFA-0039 fixtures) MATCH a live credential; 6 anthropic-key-shaped and 3 github-pat-shaped strings do not match the live pool. Owner rule: report, never rotate. #secrets
- [fact] `GH_TOKEN` is a fine-grained PAT set in `$PROFILE` + User + Machine env and lacks checks/actions read (gh 403 on check-runs); the keyring account works. #gh
- [fact] Hosted-models gem-hunt: 13 lenses + synthesizer on Fable 1M max (~$120 total, docs only) -> PR #314 (`docs/gem-hunt/2026-09-02-hosted-models/`: 13 lens reports, CONSOLIDATED-GEM-DECISIONS, DECISION-QUEUE D1-D13, BUILD-WAVE-PROPOSAL). Verified surprises: the box HAS an RTX 4050 6 GB; `codex mcp-server` deprecated upstream 2026-08-24. #gem-hunt #hosted-models
- [decision] `glm53-space` is to be DEPRECATED (owner, 02.09.2026) and replaced by a registry-driven model integration layer (models SSOT + per-runtime materializers + one generic inference MCP tool + eval gate) across all installed runtimes; build wave only after the owner steers D1-D13. #glm53-space
- [fact] Cloud lane spend 02.09.2026 (charged): W12 P2 loop-to-green > $674 and rising (~$8/min, 26 commits / 147 files of real G-1 repair on `p2/loop-to-green-2026-09-02`), W11 search ~$350, W10 OOM $244 (PR #311). Soft caps armed by the local monitor: W12 $800, W11 $400, W10 $300. #cost

## Relations
- relates_to [[memory-contract]]
- relates_to [[hosted-model-agents skill]]
- supersedes [[basic-memory transport decision 2026-09-02]]
