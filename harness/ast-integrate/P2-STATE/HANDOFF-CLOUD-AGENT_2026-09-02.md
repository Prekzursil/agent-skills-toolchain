# HANDOFF — cloud agent, 02.09.2026 (ast-integrate capture + toolchain reconciliation)

> Status file for the two-stage reconciliation of Miky's agent harness into ONE repo
> (`github.com/Prekzursil/agent-skills-toolchain`, PRIVATE). Written on disk first so the
> orchestrator can pick it up even if the writer is cut off. Sections are appended as work lands;
> every claim carries a provenance tag (`disk-verified` = the writer re-read the artifact,
> `agent-claimed` = asserted only).

## WORKER CLAIM (coordination — read this before touching the repo)

- **Active worker:** `stage1-worker-B` (Cursor subagent, Fable 5.1), started 02.09 03:05 EEST.
- **Claim refreshed:** 02.09 03:50 EEST — holds `scripts/sync-from-live.ps1`, `harness/**`,
  `.gitignore`, `scripts/test_sync_from_live.py` and the `handoff/cloud-agent-2026-09-02` branch
  head until the Stage 1 push lands. Refreshes every step; a claim older than 20 min is stale.
- **Sibling detected:** a second worker with the same mandate is alive on this box. Evidence
  (`disk-verified`): the `handoff/cloud-agent-2026-09-02` branch was created at 03:01 (reflog),
  and an `ast-integrate` `$Map` entry landed in `scripts/sync-from-live.ps1` between 03:12 and
  03:41 that this worker did not write (comment text differs: "84,000 files / 7.9 GB raw").
  That entry is design-identical to this worker's (same keys, same exclusions) and was KEPT.
  This worker added the engine half (`Test-Excluded -Area`, `Test-TooLarge`, reserved device
  names, loop wiring). **Sibling: do not run the sync, `git add`, commit or push on this branch
  while this claim is fresh — re-read this file first. If you have already pushed, say so here
  and this worker will rebase onto your commit instead of re-capturing.**
- Neither worker is registered on agent-mail (`list_window_identities` = 0 on both project keys
  at 03:47), so this file is the coordination channel.

## Stage 0 — recovery (02.09 03:05–03:45, `disk-verified`)

- Branch `handoff/cloud-agent-2026-09-02` exists locally at `fbc70f22` (= `docs/cursor-cli-bridges`),
  NOT on origin (`git ls-remote --heads origin 'handoff/*'` empty).
- No prior handoff doc, no `.agents\backups\archived-trees-20260902\`, no partial script edit at
  03:10 (the `$Map` entry appeared later — see sibling note above).
- 65 pre-existing dirty entries in the toolchain (other sessions' work): 8 tracked modifications
  (`mcp-gui` → `mcp-manager` rename across `commands/`, `agent-self/`, `platform/routing/fixtures`,
  `.github/workflows/quality.yml`, two `ci/tests`, `tools/mcp/README.md`, `tools/mcp-manager/uv.lock`)
  + 57 untracked (51 `skills/microsoft-foundry/**`, `.agents/gem-hunt-2026-08-29/`,
  `tools/mcp/glm53-space/`, `skills-claude-only/azure-validate/references/recipes/README.md`).
- **Live P2 tree is NOT idle:** `_g1_respawn.ps1` (PID 58828) + 2 WSL `_g1_regen_par.py`
  workers (wave `wave-regen-0209`, 6 workers) were still running at 03:15 and appending to
  `ovh-monitor/g1-repair-claude_2026-08-27.log` / `repair-claude/wave-regen-0209.jsonl` and
  copying unit artifacts back into the Windows tree. They were launched by the 02.09
  coordinator at 02:34 (sanctioned by the 02:28 strategy switch) and survived the coordinator.
  NOT killed by this worker (owner-sanctioned, resumable; owner's call) — see Stage 1 note on
  what that means for the "frozen" premise. Kill recipe if the owner wants the freeze to be
  real: `Stop-Process -Id 58828` then `wsl.exe bash -lc 'pkill -f _g1_regen_par.py'`.

## Stage 1 — cloud capture (IN PROGRESS)

_(section is rewritten when the push lands: branch, commit hash, repo path, exclusions summary)_
