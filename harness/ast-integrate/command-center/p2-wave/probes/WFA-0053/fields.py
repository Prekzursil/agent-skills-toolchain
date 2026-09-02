"""IR field catalog for the paper-protocol adapter.

Required parameters (catalog WFA-0053): missing any one forces UNDERSPECIFIED.
Protocol vocabulary is the IR coverage list from _USER-PROMPTS.md:10926-10934.
WorkflowIR constructs are the WFA-0044 target; unquoted ones stay MISSING.
"""
from __future__ import annotations

REQUIRED_PARAMS = (
    "participant_count",
    "turn_structure",
    "stopping_rule",
    "scoring",
)

PROTOCOL_VOCABULARY = (
    "conflicts_of_interest",
    "information_partitioning",
    "role_mandates",
    "nested_subcouncil",
    "deliberation_protocol",
    "speaking_quotas",
    "minimum_engagement",
    "voting_aggregation",
    "stopping_expression",
)

WORKFLOW_IR_CONSTRUCTS = (
    "stages",
    "roles",
    "gates",
    "tool_policy",
    "fan_out_barriers",
    "loops_convergence",
    "human_checkpoints",
    "retries",
    "resume",
    "lineage",
)

# Fillable fields the adapter may quote-anchor. Required ∪ vocab ∪ IR constructs.
ALL_FIELDS = REQUIRED_PARAMS + PROTOCOL_VOCABULARY + WORKFLOW_IR_CONSTRUCTS

AUTHOR_MUST_SUPPLY = {
    "participant_count": (
        "an exact integer bound on participants (agents, models, panelists, "
        "or sampled paths), not a bare plural"
    ),
    "turn_structure": (
        "an ordered turn or round sequence (who speaks, in what order, "
        "serial vs parallel), not 'they talk'"
    ),
    "stopping_rule": (
        "a decidable stop predicate (round cap, IQR threshold, named gate "
        "such as ACCEPT, or a composable AND/OR/NOT expression), not "
        "'until they feel done'"
    ),
    "scoring": (
        "a named metric and selection rule (exact-match, majority vote, "
        "median absolute error) on a named set, not 'quality is assessed'"
    ),
}

FIXTURES = (
    {
        "paper_id": "role-committee-specified",
        "family": "role-committees",
        "rel": "command-center/p2-wave/probes/WFA-0053/fixtures/paper-role-committee-specified.md",
        "expect_verdict": "TRANSLATED",
        "control": "positive",
    },
    {
        "paper_id": "self-consistency-specified",
        "family": "self-consistency",
        "rel": "command-center/p2-wave/probes/WFA-0053/fixtures/paper-self-consistency-specified.md",
        "expect_verdict": "TRANSLATED",
        "control": "positive",
    },
    {
        "paper_id": "debate-specified",
        "family": "debate",
        "rel": "command-center/p2-wave/probes/WFA-0053/fixtures/paper-debate-specified.md",
        "expect_verdict": "TRANSLATED",
        "control": "positive",
    },
    {
        "paper_id": "delphi-specified",
        "family": "Delphi",
        "rel": "command-center/p2-wave/probes/WFA-0053/fixtures/paper-delphi-specified.md",
        "expect_verdict": "TRANSLATED",
        "control": "positive",
    },
    {
        "paper_id": "partial-missing-scoring",
        "family": "partial-control",
        "rel": "command-center/p2-wave/probes/WFA-0053/fixtures/paper-partial-missing-scoring.md",
        "expect_verdict": "UNDERSPECIFIED",
        "control": "partial-refusal",
        "expect_missing": ["scoring"],
    },
    {
        "paper_id": "underspecified",
        "family": "deliberate-underspecified",
        "rel": "command-center/p2-wave/probes/WFA-0053/fixtures/paper-underspecified.md",
        "expect_verdict": "UNDERSPECIFIED",
        "control": "both-states-refusal",
        "expect_missing": [
            "participant_count",
            "turn_structure",
            "stopping_rule",
            "scoring",
        ],
    },
)
