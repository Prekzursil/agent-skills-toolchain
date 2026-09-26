---
title: 'webcoder lean-gate: opengrep SAST GREEN; next gate = osv-scanner deps (188
  CVEs) (2026-06-20)'
type: note
permalink: main/projects/reframe/webcoder-lean-gate-opengrep-sast-green-next-gate-osv-scanner-deps-188-cves-2026-06-20
tags:
- webcoder
- lean-quality-gate
- opengrep
- sast
- osv-scanner
- deps
- fleet
---

# webcoder feat/lean-quality-gate — opengrep SAST fixed (2026-06-20)

Branch feat/lean-quality-gate on Prekzursil/WebCoder (PR #85). Worked in fresh Windows temp clone. Pushed HEAD 3c2f30f.

## gate-sast opengrep — FIXED, GREEN in CI (run 27873614532)
The 75 opengrep findings were ALL third-party: 74 in `backend/venv/Lib/site-packages/` (eval/exec/pickle/md5/shell=True inside pytest, django, celery, pip, click...) + 1 REAL first-party finding.

Two fixes (two scoped commits):
1. **d666291 — real XSS fix**: `ProblemDetailPage.tsx` injected `problem.statement_i18n` via `dangerouslySetInnerHTML` with only `\n`->`<br/>` and NO sanitization (opengrep js-dangerously-set-inner-html, CWE-79). Replaced with React text nodes: `problemStatement.split('\n').map(...<React.Fragment><br/ if i>0>{line})` — React escapes text, line-break behavior preserved, sink eliminated. Added test asserting raw `<img onerror>` renders as escaped TEXT (not executed) + `<br>` count. ProblemDetailPage stays 100%.
2. **3c2f30f — venv untrack**: `backend/venv` was COMMITTED (8724 files) despite `.gitignore` having `venv/`. `git rm -r --cached backend/venv` → opengrep scope drops 8818→215 first-party files, 0 findings. Same generated/venv scope exclusion the coverage gate already applies. NOT weakening.

## ⭐ Windows CRLF gotcha (cost a detour)
`core.autocrlf=true` checks out working tree as CRLF but committed blobs are LF. biome (`lineEnding: lf`) flagged 77 "errors" LOCALLY on the pristine branch (false positive). CI passes (LF blobs). FAITHFUL MIRROR = renormalize to LF first: `git -c core.autocrlf=false rm --cached -r . && reset --hard` (WARNING: this reverts uncommitted edits + re-tracks venv — re-apply after). Then biome = 74 files clean. ALWAYS commit with LF blobs; verify `git cat-file -p :file | grep -c $'\r'` == 0.

## Full lean gate verified locally (all GREEN before push)
ruff check+format ✓ | basedpyright 0/0 (clean py3.12, no deps) ✓ | tsc ✓ | oxlint 73f ✓ | biome 74f LF ✓ | python cov 100% (195 tests, 1132 stmts) ✓ | frontend cov 100% (236 tests, 25 suites) ✓ | opengrep 0 findings ✓ | gitleaks 0 ✓.
opengrep local: download `opengrep_windows_x86.exe` from `gh release v1.22.0` (standalone Windows CLI, no core zip needed). Read its --json with encoding='utf-8' (cp1252 chokes).

## REMAINING (honest) — gate-deps osv-scanner, NEW failure surfaced
My fix unblocked the pipeline → next gate failed: **osv-scanner: 188 known vulns / 68 packages / 2 ecosystems (12 Crit, 75 High); 185 fixable**. Scans `backend/requirements.txt` (pinned old Django/celery) + `frontend/webcoder_ui/package-lock.json` (CRA-era npm). This is a SEPARATE multi-day dependency-UPGRADE effort with breakage risk, not the SAST task. Gate policy (.quality/osv-scanner.toml) FORBIDS blanket ignore — only per-CVE genuinely-unfixable/unreachable with dated reason. Do NOT weaken. Charter intent = upgrade where safe.

Downstream after osv: charter-check (last step). osv was never reached before because it was blocked behind sast.
