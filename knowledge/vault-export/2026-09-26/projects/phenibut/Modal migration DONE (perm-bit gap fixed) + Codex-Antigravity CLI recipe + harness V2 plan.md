---
title: Modal migration DONE (perm-bit gap fixed) + Codex/Antigravity CLI recipe +
  harness V2 plan
type: report
permalink: main/projects/phenibut/modal-migration-done-perm-bit-gap-fixed-codex-antigravity-cli-recipe-harness-v2-plan
tags:
- modal
- migration
- codex
- antigravity
- harness
- recipe
- phenibut
---

# Modal migration DONE + Codex/Antigravity CLI recipe + harness V2 plan (2026-06-20)

## Migration florineldanciu4 -> prekzursiltr: COMPLETE
The suite+license+inputs are on prekzursiltr (`/sch/suites2026-2` incl. `licenses/26-2.lic`, `lic_support`, `fep_inputs`). Path used (A, copy installed suite, NOT reinstall): `modal volume get --force` (pre-create dest dir + `--force` to push past the jaguar `macro_pka already exists` symlink choke) -> local 16.51GB/150524 files -> `tar -czf` via **Windows tar.exe** (Git Bash `/d/` mount failed silently; bsdtar works) = 8.73GB -> `modal volume put` to prekzursiltr -> `mig.py --stage unpack` (pigz).
- **GOTCHA (the gap):** the Windows download+tar round-trip **STRIPPED the Unix exec bits** -> `PermissionError [Errno 13]: '/sch/suites2026-2/jsc'` on the first FEP edge. FIX = `mig.py --stage fixperms` (`chmod -R a+rx /sch/suites2026-2`); jsc/run now `-rwxrwxrwx`. **Any Windows->Linux volume copy of a suite MUST chmod +x after.** `mig.py` now has pack/unpack/fixperms stages.
- Use `MODAL_PROFILE=<profile>` env var per-command (florineldanciu4 is SPEND-CAPPED -> data reads only; prekzursiltr has budget). α2δ FEP re-running on prekzursiltr to confirm end-to-end.

## Codex 5.5-xhigh + Antigravity recipe -> `~/.claude/AGENT-CLI-RECIPES.md`
- **Codex:** `~/.codex/config.toml` ALREADY defaults model=gpt-5.5, model_reasoning_effort=xhigh, detailed reasoning, approval=never, sandbox=danger-full-access. So `codex exec "<prompt>"` = 5.5-xhigh. Pipe big context via stdin (`Get-Content x | codex exec "..."`). **Root cause of "timeout":** `codex doctor` shows **1,935 rollout files = 58.77GB scanned EVERY launch** -> ~minutes startup (health otherwise ✓). FIX/recipe = **ALWAYS background, never foreground-block; longrun hang-timeout >=600s**; speedup = prune/archive rollouts (`codex-runtime-recovery` skill). Codex locks `state_5.sqlite` -> never run 2 concurrently.
- **Antigravity:** `agy --print --print-timeout <N>m --dangerously-skip-permissions "<prompt>"`. `--print-timeout` = the anti-timeout knob. Gemini CLI deprecated for this tier (2026-06-18) -> use `agy`. Same heavy startup -> background.
- **Council pattern:** pipe a plan to both codex exec + agy --print (adversarial review prompt), synthesize what survives all 3 lenses.

## Harness V2 plan -> `~/.claude/SOTA-HARNESS-RECOMMENDATIONS-V2.md`
Session-grounded (mined event-ledger 39 dirs/1305 turns + basic-memory + 47.8MB mega-session). P0(2): dark-surface/stub detector at Stop (GREEN-not-LIVE, #1 failure), orphan-commit gate. P1(7): EDIT-UNREAD block, FALSE-STARTED claim-check, anti-thrash PostToolBatch, WRONG-SHELL lint, concurrency-governor, INFRA-vs-CODE triage, DEGEN-READ tweak. Killed 10 hype. Codex+Antigravity council running on the 5 flagged items -> then implement. See [[Harness P0 hooks IMPLEMENTED + Modal account migration (florineldanciu4 spend-capped -> prekzursiltr)]].
