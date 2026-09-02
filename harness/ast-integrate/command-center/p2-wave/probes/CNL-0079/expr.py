"""Spec-quoted stopping expression for CNL-0079.

The harness prompt file is not on this Linux worktree. The string below is the
catalog title for CNL-0079 and the example CNL-0069 cites at _USER-PROMPTS.md:10938.
It is used unchanged — the A10 parser must accept this source, not a rewrite.
"""

SPEC_ANCHOR = "_USER-PROMPTS.md:10938"
SPEC_RANGE = "_USER-PROMPTS.md:10937-10942"
SPEC_EXPRESSION = "consensus >= 0.95 AND no_new_objection_rounds >= 2"
SPEC_LINE = SPEC_ANCHOR

# The other five required examples (catalog titles CNL-0078, 0080-0083) so the
# grammar is shown not to be a one-string regex.
A10_REQUIRED_EXAMPLES = (
    "unique_ideas >= 100 AND completeness_score >= 0.90",
    SPEC_EXPRESSION,
    "unanimity == true OR max_rounds == 12",
    "quality_gate == PASS AND unresolved_load_bearing_counterexample == 0",
    "evidence_saturation == true OR time_minutes >= 180",
    "proof_of_impossibility == true",
)
