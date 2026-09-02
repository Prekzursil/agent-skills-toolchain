"""Pre-registered controls for ADV-0143.

This module must not import the corpus walker, reviewers, or extent
measurer. Numbers are frozen in source before any sample is drawn and
before any rater pair is seen.
"""

# Completeness sample
SAMPLE_N = 30
SAMPLE_SEED = 20260824
CHUNK_CHARS = 480

# Extent plant: recovered UTF-8 byte length must match the payload exactly.
EXTENT_TOLERANCE_BYTES = 0

# Verdict-stability: two independent reviewers, 10 rows, exact-verdict rate.
STABILITY_N = 10
AGREEMENT_THRESHOLD = 0.8
AGREEMENT_METRIC = "exact-verdict-match-rate"
KAPPA_THRESHOLD = 0.5
KAPPA_METRIC = "cohens-kappa-four-verdicts"
CHOSEN_BEFORE_RUN = True
RATIONALE = (
    "Catalog control size is 10 rows. Four verdict labels are specified in "
    "the unit evidence requirement. 8/10 exact matches (0.8) is the minimum "
    "operational agreement before the criteria may be used; Cohen's kappa "
    "0.5 is the chance-corrected floor on those four labels. Both numbers "
    "were frozen from the catalog control size and label cardinality, not "
    "from observed rater pairs."
)
