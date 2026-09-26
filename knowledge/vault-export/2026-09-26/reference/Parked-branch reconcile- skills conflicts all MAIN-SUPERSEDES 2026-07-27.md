---
title: 'Parked-branch reconcile: skills conflicts all MAIN-SUPERSEDES 2026-07-27'
type: note
permalink: main/reference/parked-branch-reconcile-skills-conflicts-all-main-supersedes-2026-07-27
tags:
- agent-skills-toolchain
- reconcile
- d-001
- skills
- git
---

# Parked-branch reconcile — `.agents/skills/` true-conflicts verdict

Branch `fix/mcp-health-agentmail-fbmessenger` (tip 6434091) vs `origin/main` (3beea1a),
merge-base `26b9869`. 26 of the 88 true-conflict paths are `.agents/skills/`.

## Verdict: ALL 26 = MAIN-SUPERSEDES. Zero BRANCH-UNIQUE. Zero lost work.

## Root cause (the reusable lesson)
The branch's 8 commits populated `.agents/skills/` with a **mechanically DEGRADED copy** of
`skills/`. Main later did the same migration correctly. Three degradation signatures:

1. **Case-insensitive `Claude`→`Codex` sed** mangled real paths: `.claude` → `.Codex`
   (`~/.Codex/event-ledger`, `~/.Codex/learnings-queue.json`, `~/.Codex/workflows`,
   `HOME / ".Codex" / "hooks"`). On Windows `.Codex` silently resolves to Codex CLI's
   `.codex` dir; on Linux CI it is simply missing. Hit `agent-as-judge` + `workflow-authoring`.
2. **Spurious f-string prefixes** — `print("x")` → `print(f"x")` with no placeholder
   (ruff F541). 22 in `instinct-cli.py`, 6 in `python_implementation.py`.
3. **Pre-format / pre-lint snapshots** — collapsed long lines, unused imports added
   (`Callable`, `sys`, `mock`, `json`), and `snapshot_ring.py` DROPPED
   `usedforsecurity=False` from `hashlib.md5(...)`.

## Method that settled it deterministically
- **AST equality** (`ast.dump`) per python file: 4 AST-identical to main (pure reformat);
  8 showed `MAIN==BASELINE_AST:True` while `BR==BASELINE_AST:False` → main preserved
  semantics, the branch mutated them. **Zero branch-only defs/classes across all 13 files.**
- **Frontmatter-stripped body-line set diff** per markdown: 9 of 13 had ZERO branch-unique
  body lines (main's change was only PR #167 "repair unparseable SKILL.md frontmatter +
  cap descriptions" — quote the YAML, ASCII-ise em-dashes, reflow `>-` folded blocks).

## Two false-alarm supersede traps
`media-dub` and `packaged-artifact-smoke` looked like "main deleted 18 lines". They are
folded-YAML (`>-`) descriptions reflowed to one capped line. Body untouched. **Always strip
frontmatter before calling a markdown deletion "lost work".**

## One real supersede trap
`workflow-authoring` §13 (inline Databricks fan-out) — main **deliberately** replaced it with
a cross-reference: "the large parallel-agent-on-Databricks fan-out lives in
`../codex-databricks-fanout/SKILL.md`". Re-adding §13 re-introduces duplication main removed.
Same for `orchestration-patterns` "Pattern 6" and `cloud-infra-toolchain`'s Databricks
section — main's canonical `codex-databricks-fanout` skill carries every fact with more
detail plus executable `scripts/harness/contract.py`.

## D-001 implication
`ci/check_skill_dual_write.py` is a **DIFF guard, not a tree-parity guard** — `--strict-parity`
only compares paths the PR CHANGED. Since the verdict is "touch none of the 26", D-001 never
fires. Main carries 1822 `.agents/skills/` vs 1656 `skills/` files (known backlog).
**Landmine:** 3 paths already drift on main — `orchestration-patterns/SKILL.md` and
`execution-grounded-bon/SKILL.md` (the same Claude→Codex bug leaked into main's `.agents`
copy) and `bc-drive-plus/snapshot_ring.py`. Touching any of them forces a mirror repair.

## Tooling gotcha reproduced (3rd time)
`git rev-parse <rev>:.agents/...` returns ABSENT under Git-Bash/MSYS — the leading-dot path is
mangled. `git ls-tree <rev> -- <path>` is correct. This nearly produced an all-ABSENT table
and a completely wrong classification. **Use `ls-tree`, never `rev-parse <rev>:<path>`, for
dot-prefixed paths on this box.**

## Observations
- [fact] All 26 `.agents/skills/` true-conflicts resolve MAIN-SUPERSEDES #reconcile
- [technique] AST-dump equality separates reformat from real code change #verification
- [technique] Strip YAML frontmatter before diffing markdown for lost work #verification
- [gotcha] MSYS mangles `rev-parse <rev>:.dotpath`; use `ls-tree` #windows-shell
- [gotcha] D-001 strict-parity only fires on paths the PR changed #ci

## Relations
- relates_to [[agent-skills-toolchain mechanics]]
- relates_to [[Windows shell non-negotiables]]
