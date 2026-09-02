# Session transcript excerpt

Operator: next we will implement a new workflow.

Proposed workflow: adapter-chain-run

The system shall invoke adapter-chain-run after each close.

Steps:
1. Run repo, live, marketplace, then prose adapters in order
2. Union candidate rows keyed by workflow id and source

Acceptance: a planted row appears in the candidate list.
Ship this workflow.
