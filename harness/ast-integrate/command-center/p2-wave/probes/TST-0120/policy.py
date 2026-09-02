"""Written equivalent-mutant triage policy (TST-0120).

A mutation score is gameable at the exclusion step. This module is the
policy, not a score: every claimed equivalent mutant needs a recorded
justification and an independent reviewer, and the exclusion count is
published next to the score.
"""
from __future__ import annotations

AUTHOR_ID = "TST-0120-author-openai-codex"
REVIEWER_ID = "TST-0120-reviewer-anthropic-opus"

# Catalog test ids.
TEST_SCORE_WITH_COUNT = "test_score_is_published_with_the_exclusion_count"
TEST_UNJUSTIFIED = "test_an_unjustified_exclusion_is_rejected"

MIN_JUSTIFICATION_CHARS = 80

BOILERPLATE_JUSTIFICATIONS = frozenset(
    {
        "equivalent",
        "equivalent mutant",
        "eq",
        "same",
        "same behaviour",
        "same behavior",
        "noop",
        "no-op",
        "n/a",
        "na",
        "trivial",
        "see above",
        "obvious",
        "harmless",
    }
)

REQUIRED_EXCLUSION_FIELDS = (
    "mutant_id",
    "operator",
    "location",
    "justification",
    "reviewer_id",
)

# TST-0015 estate operators this policy knows how to triage.
ESTATE_OPERATORS = (
    "lf-crlf-flip",
    "json-key-case-flip",
    "path-separator-flip",
    "sentinel-deletion",
    "mid-write-truncation",
    "default-argument-change",
    "use-vs-mention-swap",
)

POLICY_ID = "TST-0120-equivalent-mutant-triage-v1"

POLICY_TEXT = """\
Equivalent-mutant triage policy (TST-0120)
==========================================

1. Meaning of a score
   mutation_score = killed / (total - exclusion_count)
   A published score that omits exclusion_count is an OVERCLAIM, including
   when the omitted count would have been zero. The count must equal the
   number of accepted exclusion records.

2. What may be excluded
   Only a mutant that is semantically identical to the original on the
   published oracle pack may be proposed as equivalent. Measured divergence
   on any oracle input makes the mutant NOT equivalent; a written story
   cannot override the measurement.

3. Exclusion record (all required)
   mutant_id, operator, location, justification, reviewer_id.
   - justification >= 80 characters, not a boilerplate token ("equivalent",
     "noop", "same", "n/a", ...).
   - justification must name the semantic reason (why observers cannot
     distinguish original from mutant).
   - reviewer_id must be present and MUST NOT equal the author_id.
   - operator must be one of the TST-0015 estate operators.

4. Review trail
   Exclusion is where the score becomes gameable. Every accepted exclusion
   is listed with its justification and reviewer. Publishing a score with
   no exclusion list (or with a count that does not match the list) is
   rejected as overclaim.

5. Unjustified exclusion (must be rejected)
   - missing field
   - boilerplate or short justification
   - missing or same-as-author reviewer
   - unknown operator
   - mutant the oracle pack distinguishes from the original
   - exclusion_count that does not match len(exclusions)

6. Detector-control (both states)
   PLANTED: score without exclusion_count → reject (overclaim).
   PLANTED: boilerplate / distinguishable "equivalent" → reject.
   CLEAN: justified, reviewed, oracle-identical exclusions + matching
   exclusion_count → accept, and the score is the killed/remaining ratio.
"""

# Import aliases used by triage.py / probes.
AUTHOR_ID = AUTHOR_ID
REVIEWER_ID = REVIEWER_ID
MIN_JUSTIFICATION_CHARS = MIN_JUSTIFICATION_CHARS
BOILERPLATE_JUSTIFICATIONS = BOILERPLATE_JUSTIFICATIONS
REQUIRED_EXCLUSION_FIELDS = REQUIRED_EXCLUSION_FIELDS
ESTATE_OPERATORS = ESTATE_OPERATORS
POLICY_ID = POLICY_ID

# Names used by emit.py / probes.
TEST_SCORE_WITH_COUNT = TEST_SCORE_WITH_COUNT
TEST_UNJUSTIFIED = TEST_UNJUSTIFIED

POLICY = {
    "id": POLICY_ID,
    "author_id": AUTHOR_ID,
    "min_justification_chars": MIN_JUSTIFICATION_CHARS,
    "boilerplate_justifications": sorted(BOILERPLATE_JUSTIFICATIONS),
    "required_exclusion_fields": list(REQUIRED_EXCLUSION_FIELDS),
    "estate_operators": list(ESTATE_OPERATORS),
    "score_formula": "killed / (total - exclusion_count)",
    "overclaim_rule": (
        "a score published without its exclusion_count is an overclaim"
    ),
    "text": POLICY_TEXT,
}
