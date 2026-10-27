"""RES-0150 catalog contract constants."""
from __future__ import annotations

UNIT_ID = "RES-0150"
OUTPUT_REL = (
    "command-center/research/evidence-quality/"
    "RES-0150-unfavorable-evidence-quota-mechanism.json"
)
SCHEMA_REL = "command-center/schema/design-spec.schema.json"
SENTINEL = "SUCCESS:RES-0150"
QUESTION = (
    "How can a research run be required to return a minimum share of "
    "disconfirming evidence without creating an incentive to fabricate weak "
    "objections - what quota definition, what quality floor per objection, "
    "and what detector catches padded objections?"
)
TITLE = "Enforce an unfavourable-evidence quota without manufacturing it"
HONEST_VERDICT = "UNDER-QUOTA-HONEST"
QUOTA_MET = "QUOTA-MET"
MIN_N = 2
MIN_SHARE = 0.25
NEAR_DUP_JACCARD = 0.50
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0150/probe1_padding_set.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0150/probe2_honest_under_quota.py"
)
REVIEWER_ID = "RES-0150-probe2-honest-under-quota"
KENT_BANDS = (
    "certain",
    "almost certain",
    "probable",
    "chances about even",
    "probably not",
    "almost certainly not",
    "impossible",
)
PADDING_FLAGS = (
    "PAD-NEAR-DUP",
    "PAD-MECH-COLLAPSE",
    "PAD-VACUOUS",
    "PAD-RESTATE",
    "PAD-NO-LINEAGE",
    "PAD-POLARITY",
    "PAD-NOT-IN-CORPUS",
    "PAD-SUPPORT-CITED-AS-DISCONFIRM",
)
