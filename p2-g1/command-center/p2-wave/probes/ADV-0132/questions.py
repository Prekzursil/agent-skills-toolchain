"""Questions and consensus priors only. No sealed agreed answers. No disk reads."""
from __future__ import annotations

QUESTION = (
    "Take a stratified sample of conclusions this program treats as SETTLED BY "
    "AGREEMENT (no executable test attached) and settle each one with an "
    "executable test written by an agent who does not see the agreed answer. "
    "What fraction of agreed conclusions the test refutes is the program's "
    "agreement-is-not-evidence rate, and it is the number that says whether "
    "any un-tested consensus in this program may be cited. Spec 11244 and "
    "11198: agreement is not proof; evidence gates outrank popularity."
)

CATALOG_SENTINEL = (
    "SUCCESS:ADV-0132 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and every sampled conclusion "
    "carries a pre-registered prediction whose timestamp precedes the test run, "
    "the negative control agrees with the pre-existing tests, and the mutation "
    "control went red. Any other terminal state is FAILED:ADV-0132 "
    "<classification> with the diagnostic tail attached."
)

# Consensus priors are what a catalog-reading predictor files BEFORE running.
# They are not sealed answers and are not imported by blind.py.
QUESTIONS: list[dict] = [
    {
        "id": "HC-CLAIM-LEDGER",
        "stratum": "HIGH-CONFIDENCE-AGREED-UNTESTED",
        "confidence_rank": 1,
        "question": (
            "Does command-center/CLAIM-REGISTRY.json exist on this worktree "
            "as a non-empty JSON claim ledger (a dict with a non-empty claims, "
            "entries, records, or items list)?"
        ),
        "input_paths": [
            "command-center/CLAIM-REGISTRY.json",
            "command-center/WORK-UNIT-CATALOG.json",
        ],
        "catalog_citation_count": 120,
        "why_high_confidence": (
            "WORK-UNIT-CATALOG.json cites CLAIM-REGISTRY.json 120 times and "
            "row R-H05 states it is already a claim/evidence ledger."
        ),
        "has_preexisting_executable_test": False,
        "consensus_prior": {"exists": True, "is_claim_ledger": True},
    },
    {
        "id": "HC-TEST-REGISTRY",
        "stratum": "HIGH-CONFIDENCE-AGREED-UNTESTED",
        "confidence_rank": 2,
        "question": (
            "Does command-center/TEST-REGISTRY.json exist on this worktree "
            "as a non-empty JSON test registry (a dict with a non-empty tests, "
            "entries, or records list)?"
        ),
        "input_paths": [
            "command-center/TEST-REGISTRY.json",
            "command-center/WORK-UNIT-CATALOG.json",
        ],
        "catalog_citation_count": 51,
        "why_high_confidence": (
            "WORK-UNIT-CATALOG.json lists TEST-REGISTRY.json as an input on "
            "51 units, treating the registry as a present settling index."
        ),
        "has_preexisting_executable_test": False,
        "consensus_prior": {"exists": True, "is_test_registry": True},
    },
    {
        "id": "HC-TWELVE-CONDITIONS",
        "stratum": "HIGH-CONFIDENCE-AGREED-UNTESTED",
        "confidence_rank": 3,
        "question": (
            "Does tools/command-center/completion_predicate.py define a "
            "CONDITIONS tuple whose length is 12?"
        ),
        "input_paths": [
            "tools/command-center/completion_predicate.py",
            "command-center/WORK-UNIT-CATALOG.json",
        ],
        "catalog_citation_count": 20,
        "why_high_confidence": (
            "IMP-0415 and the COMPLETION-GATES citations treat the shared "
            "predicate as a twelve-condition reducer. No TEST-REGISTRY row "
            "settles the live tuple length."
        ),
        "has_preexisting_executable_test": False,
        "consensus_prior": {"condition_count": 12},
    },
    {
        "id": "NC-RES-0063-ENGINES",
        "stratum": "NEGATIVE-CONTROL-HAS-TEST",
        "confidence_rank": 10,
        "question": (
            "Which engines does command-center/research/RES-0063.json list "
            "in catalog_fit_tests, in first-seen order?"
        ),
        "input_paths": ["command-center/research/RES-0063.json"],
        "has_preexisting_executable_test": True,
        "preexisting_test": (
            "PYTHONDONTWRITEBYTECODE=1 python3 -B "
            "command-center/p2-wave/probes/RES-0063/probe1_identity_citations.py"
        ),
        "consensus_prior": {
            "engines": ["airflow", "prefect", "dagster", "flyte"]
        },
    },
    {
        "id": "NC-RES-0108-CALIBRATION",
        "stratum": "NEGATIVE-CONTROL-HAS-TEST",
        "confidence_rank": 11,
        "question": (
            "In command-center/research/RES-0108.json calibration, what are "
            "tier1_row_count and tier3_scored_as_gem?"
        ),
        "input_paths": ["command-center/research/RES-0108.json"],
        "has_preexisting_executable_test": True,
        "preexisting_test": (
            "PYTHONDONTWRITEBYTECODE=1 python3 -B "
            "command-center/p2-wave/probes/RES-0108/probe1_blind_agreement.py"
        ),
        "consensus_prior": {"tier1_row_count": 10, "tier3_scored_as_gem": 0},
    },
]

by_id = {q["id"]: q for q in QUESTIONS}
