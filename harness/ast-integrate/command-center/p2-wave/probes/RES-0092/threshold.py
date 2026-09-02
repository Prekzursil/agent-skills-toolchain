"""Pre-stated variance threshold for RES-0092.

This module must not import the pipeline, the relation checker, or any
fixture. The number is frozen in source before any follow-up input is
generated and before any distance is computed.

Chosen from the pipeline's determinism, not from observed distances:
CNF-0075 execute_case is a deterministic capability step (exact 0.0/1.0
scores, no LLM sampler). Independent cases are an unordered collection
once scores are rebound to case id. A single case-id mismatch after a
non-identity permutation is an order-dependence defect, not noise.
Therefore the acceptable distance is exactly 0.
"""

VARIANCE_THRESHOLD = 0
DISTANCE_METRIC = "case-id-score-mismatches"
CHOSEN_BEFORE_RUN = True
RATIONALE = (
    "Deterministic capability pipeline (CNF-0075 execute_case) emits "
    "exact 0.0/1.0 scores. Independent cases form an unordered collection "
    "for pass/fail keyed by case id. Any mismatch after permutation is a "
    "genuine order-dependence defect, so the threshold is 0. Chosen from "
    "the pipeline's determinism, not from observed distances."
)
