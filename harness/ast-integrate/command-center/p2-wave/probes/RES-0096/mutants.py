"""Mutation operators applied to this repo's command-center tooling.

Each operator is a unique substring replacement in a named production file.
The executable suite is the assertion set of tools/command-center/tests/test_close.py
(replayed without pytest; pytest is not installed on this worktree).
"""
from __future__ import annotations

OPERATORS: list[dict] = [
    {
        "id": "M-SURVIVE-DEFER-DAYS",
        "file": "close.py",
        "old": "DEFAULT_DEFER_DAYS = 7",
        "new": "DEFAULT_DEFER_DAYS = 99",
        "expect": "SURVIVED",
        "mechanism": "defaults-never-exercised",
        "why": (
            "The only defer test passes --days 14 explicitly, so the argparse "
            "default bound to DEFAULT_DEFER_DAYS is never exercised."
        ),
    },
    {
        "id": "M-SURVIVE-SECURITY-CLASS",
        "file": "close.py",
        "old": 'parser.add_argument("--security-class", default="none")',
        "new": 'parser.add_argument("--security-class", default="classified")',
        "expect": "SURVIVED",
        "mechanism": "defaults-never-exercised",
        "why": (
            "test_open allocates an id and checks program/openness, never "
            "security_class, so the CLI default can change silently."
        ),
    },
    {
        "id": "M-SURVIVE-REQUIRE-COMPLETE",
        "file": "validate.py",
        "old": "require_complete: bool = False,",
        "new": "require_complete: bool = True,",
        "expect": "SURVIVED",
        "mechanism": "defaults-never-exercised",
        "why": (
            "close.main calls validate() with the default flag. The one test that "
            "mentions require_complete passes both True and False explicitly. "
            "Shipped CI is the store_true CLI flag, also default-off."
        ),
    },
    {
        "id": "M-KILL-DONE-VERIFIED",
        "file": "close.py",
        "old": (
            '    item["disposition"] = "DONE-VERIFIED"\n'
            '    item["status"] = "DONE-VERIFIED"'
        ),
        "new": (
            '    item["disposition"] = "DONE-CLAIMED"\n'
            '    item["status"] = "DONE-CLAIMED"'
        ),
        "expect": "KILLED",
        "mechanism": "control-harness-liveness",
        "why": (
            "test_close_sets_a_terminal_disposition_with_evidence asserts "
            "disposition == DONE-VERIFIED. A live harness must turn this red."
        ),
    },
]


def by_id(oid: str) -> dict:
    for op in OPERATORS:
        if op["id"] == oid:
            return op
    raise KeyError(oid)
