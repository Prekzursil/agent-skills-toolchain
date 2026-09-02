"""Closed 15-value scout disposition vocabulary."""
from __future__ import annotations

DISPOSITION_VOCABULARY = (
    "ADOPT-AS-IS",
    "ADOPT-WITH-WRAPPER",
    "DISTILL",
    "EXTEND",
    "MERGE",
    "REPAIR",
    "RETIRE",
    "SPECIALIZE",
    "UNKNOWN-NEEDS-PROBE",
    "CLEAN-ROOM-REIMPLEMENT",
    "COMPOSE",
    "GENERALIZE",
    "REBUILD-FROM-SPEC",
    "REJECT",
    "TRANSLATE",
)

ADOPT_FAMILY = frozenset({"ADOPT-AS-IS", "ADOPT-WITH-WRAPPER"})
FORBIDDEN_ALIASES = frozenset({"PERMISSIVE-OK", "ADOPT", "OK", "CUSTOM-16", "MIT-OK"})


class ClosedVocabularyError(ValueError):
    pass


def vocabulary_size() -> int:
    return len(DISPOSITION_VOCABULARY)


def assert_disposition(token: str) -> str:
    if token not in DISPOSITION_VOCABULARY:
        raise ClosedVocabularyError(token)
    return token
