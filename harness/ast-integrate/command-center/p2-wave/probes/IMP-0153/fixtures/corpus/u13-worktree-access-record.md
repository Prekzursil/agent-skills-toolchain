# Session transcript excerpt

Operator: next we will implement a new workflow.

Proposed workflow: worktree-access-record

The system shall invoke worktree-access-record after each close.

Steps:
1. For each candidate path record the exact access method
2. A ref-only path must store git show ref:path, not a bare path

Acceptance: a planted row appears in the candidate list.
Ship this workflow.
