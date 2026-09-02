# Multi-agent debate protocol (local corpus fixture; not a copyrighted reprint)

We use N=3 agents as debaters.

Turn structure: in each round every agent writes a critique of the others' answers, then updates its own answer.

The stopping rule is: stop after 2 debate rounds.

Scoring is exact-match accuracy on GSM8K of the final majority answer among the 3 agents.
