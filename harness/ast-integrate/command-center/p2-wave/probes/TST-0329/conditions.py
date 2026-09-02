"""The twelve unit-completion conditions TST-0329 conformance-tests.

Texts are the COMPLETION-GATES transcription used by IMP-0433
(command-center/p2-wave/_build_IMP0433.py), which names
gate_a_unit_completion_predicate.conditions. Spec anchors:
_USER-PROMPTS.md:10631-10644 (the twelve) and :10646 (exit 0 is never
success; missing artifact with exit 0 is still incomplete).
"""
from __future__ import annotations

CONDITIONS: list[dict[str, str]] = [
    {
        "id": "C1",
        "text": "process/task reached a valid terminal state",
        "spec": "_USER-PROMPTS.md:10631",
    },
    {
        "id": "C2",
        "text": "expected artifact exists",
        "spec": "_USER-PROMPTS.md:10632",
        "named_anti_pattern": (
            "exit code zero with a missing artifact (_USER-PROMPTS.md:10646)"
        ),
    },
    {
        "id": "C3",
        "text": "artifact is non-empty and exceeds a meaningful minimum size",
        "spec": "_USER-PROMPTS.md:10633",
    },
    {
        "id": "C4",
        "text": "artifact parses against its schema",
        "spec": "_USER-PROMPTS.md:10634",
    },
    {
        "id": "C5",
        "text": "required sentinel is present",
        "spec": "_USER-PROMPTS.md:10635",
    },
    {
        "id": "C6",
        "text": "required evidence anchors exist",
        "spec": "_USER-PROMPTS.md:10636",
    },
    {
        "id": "C7",
        "text": "required tests ran and passed",
        "spec": "_USER-PROMPTS.md:10637",
    },
    {
        "id": "C8",
        "text": "negative controls or mutations fail as expected",
        "spec": "_USER-PROMPTS.md:10638",
    },
    {
        "id": "C9",
        "text": "independent reviewer status is PASS",
        "spec": "_USER-PROMPTS.md:10639",
    },
    {
        "id": "C10",
        "text": "no unresolved P0/P1 defect is attached",
        "spec": "_USER-PROMPTS.md:10640",
    },
    {
        "id": "C11",
        "text": "output was registered in the artifact manifest",
        "spec": "_USER-PROMPTS.md:10643",
    },
    {
        "id": "C12",
        "text": "downstream consumers can read it",
        "spec": "_USER-PROMPTS.md:10644",
    },
]

CONDITION_IDS: tuple[str, ...] = tuple(c["id"] for c in CONDITIONS)
CONDITION_TEXT = {c["id"]: c["text"] for c in CONDITIONS}

VALID_TERMINALS = frozenset(
    {"SUCCESS", "COMPLETE", "FAILED", "BLOCKED", "ERROR", "TIMEOUT"}
)
SUCCESS_TERMINALS = frozenset({"SUCCESS", "COMPLETE"})
OPEN_BLOCKER = frozenset({"P0", "P1"})
MIN_BYTES = 512
SENTINEL = "SUCCESS:TST-0329-FIXTURE"
ARTIFACT_REL = "out/artifact.json"
SCHEMA_REL = "out/artifact.schema.json"
EVIDENCE_REL = "evidence/anchor.txt"
MANIFEST_REL = "UNIT-ARTIFACT-MANIFEST.json"

# Import aliases used by reducer.py / scenario.py
CONDITION_IDS = CONDITION_IDS
CONDITION_TEXT = CONDITION_TEXT
VALID_TERMINALS = VALID_TERMINALS
SUCCESS_TERMINALS = SUCCESS_TERMINALS
OPEN_BLOCKER = OPEN_BLOCKER
ARTIFACT_REL = ARTIFACT_REL
SCHEMA_REL = SCHEMA_REL
EVIDENCE_REL = EVIDENCE_REL
MANIFEST_REL = MANIFEST_REL
