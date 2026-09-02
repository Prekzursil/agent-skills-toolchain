# Self-consistency sampling protocol (local corpus fixture; not a copyrighted reprint)

The method uses 1 generator and samples 40 reasoning paths as the participant count for aggregation.

Turn structure: all 40 paths are generated independently in parallel, then a majority vote aggregates them; there is no sequential debate.

The stopping rule is: stop after exactly 40 paths have been sampled; there is no early exit.

Scoring is exact-match accuracy of the majority-vote answer on GSM8K.
