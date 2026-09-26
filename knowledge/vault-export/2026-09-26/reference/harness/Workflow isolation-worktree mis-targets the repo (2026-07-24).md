---
title: Workflow isolation:worktree mis-targets the repo (2026-07-24)
type: reference
permalink: main/reference/harness/workflow-isolation-worktree-mis-targets-the-repo-2026-07-24
tags:
- workflow
- isolation
- worktree
- build-harness
- gotcha
- '2026-07-24'
---

## Observations
- [gotcha] Workflow `agent(..., {isolation:'worktree'})` does NOT let you choose the target repo — it worktrees whatever repo the runtime resolves, which is NOT necessarily your `args.repo`. #isolation-worktree — Measured 2026-07-24: a build workflow for 2 harness gems (TG-1 detector-self-test, TG-2 mutation-gate) passed `args.repo=agent-skills-toolchain` and told agents "Repo: <toolchain>", but `isolation:'worktree'` put BOTH agents in **Reframe** worktrees (origin=Reframe.git, base 97600e8 — NOT the toolchain's a919578). Agents built good code (CONFORMS, 100% cov, mutation-verified) in the WRONG repo → not mergeable to the intended repo. The adversarial reviewers verified INSIDE the Reframe worktree and did not flag the wrong repo (they were told the repo was the toolchain but worked where isolation placed them).
- [decision] For a repo-SPECIFIC build, do NOT use `isolation:'worktree'`. #fix — Instead have the agent EXPLICITLY create the worktree off the intended repo: `git -C <target-repo-or-a-worktree-of-it> worktree add <path> -b <branch> origin/main`. Make the target repo/remote-URL a VERIFIABLE acceptance criterion the reviewer checks (`git remote get-url origin` must equal the intended repo). Reserve `isolation:'worktree'` for same-repo parallel-mutation isolation only.
- [gotcha] `git ls-tree -d --name-only origin/main <path> && echo EXISTS` is a BROKEN existence check. #ls-tree — ls-tree exits 0 even when the path is ABSENT (empty output), so `&& echo EXISTS` fires as a false positive. Use `git cat-file -e origin/main:<path>` (errors on missing) or check the output is non-empty.
- [reference] Caught on build-wave-1 (2 units) BEFORE the 73-unit A8 wave would have hit the same mis-target. The verified-good Reframe code is being PORTED into explicit toolchain worktrees + re-verified against the toolchain's own gates (ruff pin, coverage, quality.yml), and TG-2 reconciled with the pre-existing tools/mutation-gate/stryker.config.template.json stub. #recovery

## Relations
- relates_to [[Gem-hunt program-next decision-queue (2026-07-24)]]
- relates_to [[feedback_workflow_orchestration]]