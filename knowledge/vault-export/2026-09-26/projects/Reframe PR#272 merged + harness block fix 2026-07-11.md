---
title: Reframe PR#272 merged + harness block fix 2026-07-11
type: note
permalink: main/projects/reframe-pr-272-merged-harness-block-fix-2026-07-11
tags:
- reframe
- harness
- compaction-checkpoint
- codeql
---

# Reframe PR#272 merged to main + shared-harness block fix (2026-07-11)

## PR #272 — MERGED (squash 48e0d71), main fully green
The ultracode sweep + #268 GGUF fix. Getting green surfaced 4 issues the sweep left
(it ran only the coverage gates; `quality` has 9 sub-steps):
1. ruff/biome format + N999 (renamed test_wf_sidecar-core-1.py -> test_wf_sidecar_core_1.py).
2. REAL bug (basedpyright-surfaced): injected-key seam wrote ctx.injected_keys but recipes
   read ctx._injectedKeys (INJECTED_KEYS_FIELD) — nested cloud recipe steps lost their key;
   each half's test used its own name so 100% coverage HID it. Unified on INJECTED_KEYS_FIELD.
3. tracks.py CodeQL FP -> routed subtitle probe through baseline probe_streams (DRY, no new sink).
4. manager.py CodeQL FP -> confined get-pip path via ensure_within sanitizer.
Result: CodeQL GREEN (zero new alerts) — merged clean, NO ruleset bypass. main quality+CodeQL green.

## Shared-harness block fix (~/.agents/harness/modules.py) — owner directive
Two over-firing hooks were breaking ALL sessions:
- SecretGuardModule blocked UserPromptSubmit on contains_secret false positives (dropped benign
  prompts) AND blocked "irreversible" ops by scanning ALL tool-input strings (so a memory note
  that merely MENTIONED a destructive command, or a legit feature-branch deletion / hard-reset,
  got blocked). This is why basic-memory writes + branch deletes failed harness-wide.
- Fix: (1) never hard-block UserPromptSubmit; (2) removed the irreversible block entirely
  (_is_irreversible kept dormant); (3) redact the goal at store-time (LedgerModule set_goal ->
  redact_text) so secrets in prompts still never persist raw. 107 harness tests pass.
- Kept: PreToolUse tool-input secret block + credential-read block (genuine section-9 value).

## Reframe branches (14 remote): 7 fully-merged + 6 content-superseded + #272(now merged).
Remote branch DELETION is also blocked by the same lifecycle policy — needs the user's hand
until the fix propagates. The 6 superseded branches still need a salvage-value check (user ask).

## Open Reframe follow-up: 22 pre-existing main CodeQL alerts to triage
7 py/path-injection + 5 js/path-injection (keystore.ts) + 5 py/command-line-injection +
4 py/log-injection + 1 py/clear-text-storage. Codebase has ensure_within (path) + clean_for_log
(log) sanitizers -> most path/log ones are FIXABLE by routing; command-injection (list-form
subprocess) are true FPs -> dismiss; clear-text-storage + keystore need individual review.

Continues [[project_reframe_v1_4_1_shipped_2026-07-09]]. See [[reference_reframe_quality_gate_codeql_2026-07-11]].


## CORRECTION 2026-07-11 (supersedes the "removed the irreversible block entirely" line above)
Codex stop-review correctly flagged that fully removing `_is_irreversible` also unblocked
genuinely-catastrophic disk/history ops (Format-Volume, rm -rf, force-push) — a §9 regression.
Reworked SecretGuardModule into a BALANCED gate (115 harness tests pass, verified LIVE):
- Irreversible gate now scans ONLY an actual shell `command` field (Bash/PowerShell), never
  arbitrary tool CONTENT — that content-scan was the false positive that blocked notes/writes
  merely MENTIONING a command. This is the real root-cause fix.
- STILL BLOCKED (catastrophic/unrecoverable): format-volume/clear-disk/remove-partition,
  reg delete, rm -rf / Remove-Item -Recurse / rd-s / del-s, git push --force/-f/+refspec/--mirror,
  git clean -f, git restore/checkout--/branch-D/stash-drop. (Verified live: `git stash clear` blocked.)
- FREED (routine, recoverable): `git reset --hard` + branch DELETION (`git push --delete`/`:ref`).
  (Verified live: `git reset --hard origin/main` ran exit 0.)
- UserPromptSubmit still never hard-blocked; secrets redacted at set_goal; tool-input secret +
  credential-read guards unchanged.
Lesson: "user says remove the block" ≠ remove ALL safety — root-cause the FALSE POSITIVE
(here: content-scanning), keep the true-positive catastrophic guard. Peer-review (Codex) caught it.
