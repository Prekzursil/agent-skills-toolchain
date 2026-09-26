---
title: Reframe branch backlog cleanup 121 to 3 2026-07-11
type: note
permalink: main/projects/reframe-branch-backlog-cleanup-121-to-3-2026-07-11
tags:
- reframe
- branch-cleanup
- audit
- compaction-checkpoint
---

# Reframe remote branch backlog: 121 -> 3 (2026-07-11)

Cleaned the full remote-branch backlog after merging PR #272 (ultracode sweep) + #273
(CodeQL sanitizer fixes). User directive: "aggressive categorized sweep + audit when in
doubt to ensure nothing is lost."

## Method (reconcile-don't-drop)
- `git ls-remote --heads origin` is AUTHORITATIVE — local tracking refs were STALE
  (a restrictive fetch refspec meant `git branch -r` showed only ~14 of the real 121;
  `git branch -r --merged` also lies because of stale refs). Always use ls-remote SHAs.
- `git push origin --delete` is ATOMIC — one stale/nonexistent ref fails the whole push.
  Filter the delete list against ls-remote first; delete in chunks.
- Fully-merged (`git merge-base --is-ancestor <sha> origin/main`) = zero-risk delete.
- Everything else audited by 6 parallel Opus subagents (read-only git forensics:
  log/show/diff/grep/merge-base/ls-tree). Verdict unanimous.

## Outcome: 118 deleted, 1 salvaged, 3 kept
- **DELETE (118 total across the session):** all content-superseded. Two lineages:
  (1) the RECENT media-studio branches (reframe-v1.3/v1.4, fix/reframe-hardening,
  fix/ui-audit-p0-crash = the v1.1/v1.2 lines) fully absorbed into v1.4.1 main; main even
  ADVANCED chatterbox torch to 2.11 vs a branch's 2.10. (2) the ABANDONED pre-pivot SaaS
  monorepo (~60 `*-batch-01` + `apps/`/`services/`/`packages/`/`infra/` branches) — a
  DISJOINT git history (zero merge-base with main) from before the SaaS->local-Electron
  pivot; touches no file main contains.
- **SALVAGE (1):** `chore/dependabot-ignore-torch` -> its torch/torchvision/torchaudio
  Dependabot-ignore stanza (main only ignored semver-major, so minor torch bumps like the
  live 2.6->2.13 slipped through and would break the cu128 pin) -> cherry-picked into PR
  #274 (`.github/dependabot.yml`) before deleting the branch.
- **KEEP (2 + main):** `archive/inspirations-snapshots` (deliberate reference keepsake,
  3319 prior-art files under "Inspirations & Former Attempts/"), `media-studio` (a
  CI-target branch in quality.yml `on.push.branches`).
- Did NOT archive-tag the SaaS lineage (owner pivoted away deliberately; GitHub keeps
  deleted branches recoverable ~90d; the one real value was salvaged). Offer stands.

## Also this session
PR #272+#273 merged, main green, 0 open CodeQL alerts (6 fixed + 16 FP dismissed). Harness
blocks removed (see [[reference_reframe_quality_gate_codeql_2026-07-11]]).
Continues [[project_reframe_v1_4_1_shipped_2026-07-09]].
