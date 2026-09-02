"""Frozen sampling and scale parameters for BLD-0059.

Recorded before any Monte Carlo draw. Changing these is a design change, not a
re-tune after seeing a miss.
"""
from __future__ import annotations

UNIT_ID = "BLD-0059"
SENTINEL = "SUCCESS:BLD-0059"
SCALE_FACTOR = 10
# Detect a class-wide defect at this prevalence with the stated confidence.
DESIGN_PREVALENCE = 0.20
CLAIMED_CONFIDENCE = 0.95
# Spec :11041 — expand when sampled error rate exceeds this pre-set threshold.
ESCALATION_THRESHOLD = 0.05
# Escalate iff sample_error_rate > ESCALATION_THRESHOLD (strict). Equal does not fire.
ESCALATION_COMPARISON = "strict_greater_than"
# A scheme with this n would often miss a 20% defective class — must be rejected.
WEAK_SCHEME_N = 3
MC_TRIALS = 4000
MC_SEED = 59059
# Representative class size for hypergeometric checks at 10x (prefix ADV * 10).
HYPERGEOMETRIC_N_10X = 1440
# Serial independent-reviewer pool size named by the unit title.
SERIAL_REVIEWER_POOL = 1
