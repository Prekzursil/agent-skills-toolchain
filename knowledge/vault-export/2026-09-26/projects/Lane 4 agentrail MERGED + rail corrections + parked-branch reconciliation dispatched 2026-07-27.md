---
title: Lane 4 agentrail MERGED + rail corrections + parked-branch reconciliation dispatched
  2026-07-27
type: note
permalink: main/projects/lane-4-agentrail-merged-rail-corrections-parked-branch-reconciliation-dispatched-2026-07-27
tags:
- monitor-harness
- wave-2
- compaction-checkpoint
- '2026-07-27'
---

Continues [[main/projects/harness-wave-2-lanes-2-4-5-dispatched-lane-2-scope-correction-2026-07-27]].

## LANE 4 DONE — PR #233 merged, main = 363daa1, `tools/agentrail` 29 files live
Generic config-driven agent rail that CONSUMES agentspec (the lane's named risk — building a rival
dispatch core — did NOT recur; an AST scanner enforces the reuse boundary mechanically, not in prose).
CI 11/11, 241 tests, 100% line+branch over 665 statements / 132 branches, 0 pragmas, charter OK.

**Verified by me, not taken from the repair receipt** (repair receipts have been unreliable all wave):
- **duplication-B1** — `plan.py` re-implemented agentspec's unit-id rule with `.strip()`, weaker than
  `terminal.py:61` (`isprintable()` + no whitespace). `report.judge_result` composed both back-to-back,
  so `--unit-id "wu 7"` passed the local check, ran the rail (`spawned=1`), then died on a bare
  `ValueError` the CLI didn't catch — `stdout_lines=0`, completed work discarded. Re-ran the critic's
  exact repro post-fix: now exits 1 with a full envelope, reason `policy-violation` (a member of
  agentspec's closed taxonomy), root_cause quoting agentspec's real rule, raised PRE-dispatch.
- **security-B1** — the deployed `~/.local/bin/agentrail.cmd` shim was FAIL-OPEN (exit 0 on every
  failure). E2E'd the live shim from outside the worktree with a both-states control:
  failing input -> exit **1** + envelope; `--help` -> exit **0** (proves it isn't just always-nonzero).
- **coverage-B2** — the mutation gate scored a *crashed* row as a *caught* mutation. Fixed + 3 meta-controls.
Deferred (non-blocking, documented): spill-file cleanup, mixed LF/CRLF, part of a redaction layer.

## RAIL GROUND-TRUTH CORRECTIONS (appended to RAIL-PROBE-2026-07-26.md, not edited in place)
1. **`codex exec` DOES accept the prompt on STDIN** — proven executably with a control. Refutes
   `codex.mjs:91` ("Prompt is an argument to avoid stdin edge cases"). The reference rail therefore
   satisfies `PROMPT_TRANSPORTS = ("file","stdin")` natively.
2. **`agy --version` exits 0 at ~20s** — the 15s cap was a DETECTOR FAILURE, not a verdict. Third time
   this estate nearly recorded a timeout as a verdict. Still UNVERIFIED: whether agy supports a
   non-interactive WORK UNIT (different question from `--version` returning).
3. **`gemini` is hard-blocked: `WinError 193`** on its `.ps1` — a real exec failure, not a timeout.
   Any gemini rail must go via `powershell -File`.

**Self-correction:** I refused to widen agentspec's transport enum to admit `argv` on the grounds that
agy (the critic's justification) was headless-UNVERIFIED. Correction #2 weakens THAT premise. The
ruling stands, but on the stronger ground of #1: no shipped rail needs argv, so widening would
reintroduce the measured `os error 206` for zero gain. Recorded rather than quietly re-justified.

## PARKED-BRANCH RECONCILIATION — dispatched, wf_d590e366-09b
Owner lifted the "do NOT touch" hold on `fix/mcp-health-agentmail-fbmessenger` and asked for full
reconciliation -> PR -> merge. Measured shape (merge-base `26b9869`, 2026-07-19; 8 ahead / ~110 behind):
- **292** files in the branch's own commits; **156 already IDENTICAL on main (superseded, no-op)**
- **136 genuinely live**: **88 true 3-way conflicts** + **48 clean adds** (74 `.agents/skills`, 52 `tools/crcp`)
- **41 uncommitted** working-tree files
**Backups proven before any action** (`~/.claude/monitor-harness-ultracode-2026-07-18/parked-backup-20260727-034150/`):
git bundle 25.7 MB (all 8 commits) + tar 83 entries + a TAGGED dangling `git stash create` commit.

### CRITICAL SAFETY FACT — git-crypt is NOT active
`git config filter.git-crypt.clean` returns **`cat`** (pass-through), NOT git-crypt. On origin/main
`tools/mcp/{cloud-hub,search-hub}/accounts.json` are the ENCRYPTED git-crypt blob (GITCRYPT magic
confirmed); the working tree holds DECRYPTED plaintext with live tokens. So **staging those paths
would commit PLAINTEXT**. They are on a hard DENYLIST — never staged; main's blob left untouched.
gitleaks is the backstop, not the primary defense. `.gitattributes` itself IS safe to commit and its
branch change (encrypting `tools/crcp/cookie-store/*.json`) is genuine work worth keeping.

## Workflow-authoring lessons this round (SOTA practice, cost real reruns)
- `pipeline()` silently deletes a lane: a stage that throws drops the item to null and skips its
  remaining stages. That was the root cause of the earlier run's "build:L4 / critic:L4 / both
  recritics never started" with no error surfaced. Every agent call now goes through a `safe()`
  wrapper that catches, logs and returns a sentinel.
- **Never filter the verdict array before mapping it back to the lens list** — `verdicts.filter(...)`
  breaks index alignment with `LENSES[i]` and misattributes findings to the wrong critic. Keep the RAW
  array; filter only for counting.
- A dead critic must NOT count as a pass — require every lens to have RETURNED *and* PASSED to exit
  the verify/repair loop.
- Per-file `git cat-file`/`git diff` loops over ~300 files TIMED OUT at 10 min under concurrent lanes.
  Use batch `git diff --name-only` + `comm` set algebra instead (seconds).
- MSYS footguns hit twice: `tar -czf C:/...` reads `C:` as a REMOTE HOST (use `-C` + relative paths);
  `> NUL` in Git Bash creates a literal 674-byte file (it is not the null device — `/dev/null` is).
