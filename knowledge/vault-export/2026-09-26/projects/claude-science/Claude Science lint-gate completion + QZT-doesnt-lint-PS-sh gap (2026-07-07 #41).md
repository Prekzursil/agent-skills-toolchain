---
title: 'Claude Science lint-gate completion + QZT-doesnt-lint-PS/sh gap (2026-07-07
  #41)'
type: report
permalink: main/projects/claude-science/claude-science-lint-gate-completion-qzt-doesnt-lint-ps-sh-gap-2026-07-07-41
tags:
- claude-science
- agent-skills-toolchain
- quality-gates
- powershell
- shellcheck
- lessons
---

# Claude Science lint-gate completion (#41) + the reusable harness gap

**2026-07-07.** Closed the "impeccable / hard quality gates" pass on the Claude Science WSL2 tooling (`scripts/claude-science/` in `agent-skills-toolchain`). Merged **#41** to main (`0350f3d`), normal merge, CI green, independent adversarial review = SHIP.

## ⭐ The reusable lesson (applies to the WHOLE toolchain, not just CS)
The **QZT CI (`quality.yml`) lints Python ONLY — not PowerShell or bash.** So #38 shipped **CI-green while failing its own hard gates**: 9 `.ps1` + 6 `.sh` carried ~50 PSScriptAnalyzer/shellcheck findings, *including `cs.ps1` itself*. **"CI green" ≠ "PS/sh clean."** Any time you touch a `.ps1`/`.sh` in this repo, run PSSA + shellcheck manually. PSScriptAnalyzer 1.25 installs CurrentUser; shellcheck 0.11 is on the host PATH. Pairs with the CRLF lesson (verify `bash -n` in REAL wsl, not Git Bash) and [[feedback_peer_review]] (never trust self-cert).

## What #41 delivered
- **PSSA 0 / shellcheck 0** across the whole `cs` set. `Write-Host`→`Write-Information -InformationAction Continue` (no `-ForegroundColor` in use → zero UX loss; `cs.ps1`'s parsed `SUCCESS/FAILED` markers already use stdout, untouched), non-ASCII→ASCII (clears `PSUseBOMForUnicodeEncodedFile`, no BOM), `SupportsShouldProcess` on `Set-TabExempt`, justified `PSUseUsingScopeModifier` suppression on `Invoke-CSWsl` (args via `-ArgumentList`/`param()` = true false positive), `ls`→`find`/`$CS_EXTRA`→`read -ra` array/`cd||exit`/`find -delete`/intentional SC2016 disable.
- Folded in **WU-A**: 12-field `cs status -Json` contract, `cs open` regfix, `cs-restore --dry-run`+401 verify.
- `cs-maintain.sh` reframe deltas: fixed the wrong "reduces wedge frequency" comment + require non-empty backup (`-size +0c`) before VACUUM.
- README neighbour-RAM levers (LM Studio idle-unload / Docker `.wslconfig memory=8GB` / BOINC suspend).

## Scope discipline (no-more-no-less) — do NOT re-add these
- DROPPED "daily maintenance" + "-AtStartup boot-warm" deltas: the tiny-DB reframe (3.2 MB, already WAL) makes #38's **weekly** correct, and boot-warm contradicts the **fast-ensure-not-resident** decision. #38 was already reframe-aware.
- DROPPED the watchdog "dual-signal" wedge delta: `Test-CSHealth` measures **localhost** 401 latency (no network variance), so a slow localhost 401 already IS a wedged daemon; a second `wsl status` call adds load for no signal.

## Verification (empirical, not self-cert)
PSSA 0 · shellcheck 0 · `bash -n` 0 · AST 0 · live `cs status -Json` (12-field) · live `cs doctor` **10 PASS / 0 FAIL / 0 WARN** · falsify-tested `read -ra` empty-array under `set -u` + advanced `Set-TabExempt` scope · independent Opus reviewer SHIP (all 8 risk points PRESERVES, validated in real WSL 5.2 / PS 5.1).

Prior context: this session also had a recall-first miss (fanned out agents to rebuild what #38 already merged) — WU-A honestly surfaced the stale premise and pivoted to gap-closing instead of a redundant rebuild. Relates to the file-based note `project_claude_science_hardening_2026-07-07`.
