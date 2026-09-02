---
name: angr
description: Use when symbolic execution, path exploration, constraint solving, or programmatic reasoning about binary behavior is needed beyond manual reversing.
---

# angr

## Overview

Use angr for scripted program analysis: symbolic execution, state exploration, and solver-backed reasoning. It is useful when manual reversing alone is too slow or when you need proof about reachable states.

## Quick Workflow

1. Work in a dedicated Python environment so Z3 and angr dependencies stay isolated.
2. Build the smallest `Project` and entry state that matches the question.
3. Constrain inputs early so the search space stays tractable.
4. Explore to concrete targets or bad states, then extract solver results and verify them against the real binary.
5. Save the analysis script alongside notes about addresses, assumptions, and architecture.

## Common Mistakes

- Starting from unconstrained full-program symbolic execution and exploding the state space.
- Treating a solver result as valid without replaying it against the real binary.
- Forgetting architecture, loader, or environment assumptions when comparing angr results with runtime behavior.

## Reference Map

Read `references/upstream.md` for install notes and a minimal sanity-check workflow.
