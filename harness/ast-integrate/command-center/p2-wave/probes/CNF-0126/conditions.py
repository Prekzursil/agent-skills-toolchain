"""Promotion conditions for spec span 11125-11133 (promote-only-after).

Only catalog-quoted wording is treated as known. Unquoted lines in the same
span stay in the table as NOT-CHECKED when _USER-PROMPTS.md is absent — they
are not invented and they are not dropped.
"""
from __future__ import annotations

SPEC_FILE = "_USER-PROMPTS.md"
WAVE4 = "command-center/WAVE4-PLUGIN-LIFECYCLE-VERIFY.json"
REL_0004 = "command-center/receipts/REL-0004.json"
REL_0005 = "command-center/receipts/REL-0005.json"
REL_0006 = "command-center/receipts/REL-0006.json"
REL_0008 = "command-center/receipts/REL-0008.json"
REL_0014 = "command-center/receipts/REL-0014.json"
REL_0018 = "command-center/receipts/REL-0018.json"
REL_0019 = "command-center/receipts/REL-0019.json"

UNQUOTED = (
    "UNQUOTED: line is inside promote-only-after span 11125-11133; the catalog "
    "corpus has no verbatim quote and the spec file is not on this worktree"
)

SUBSTITUTE_RECEIPTS = [WAVE4, REL_0004, REL_0005, REL_0006]

PROMOTION_CONDITIONS = [
    {
        "id": "PG-11125-private-canary-first",
        "spec_anchor": "_USER-PROMPTS.md:11125",
        "wording": "private canary first / shadow mode or private canary first",
        "wording_provenance": (
            "catalog quotes: REL-0004 inputs; IMP/REL units naming 11125; "
            "OQ-9 text ('Spec :11125 and promotion gate :11131')"
        ),
        "receipt_paths": [REL_0004],
        "unsatisfiable_under": "PR-ONLY",
        "unsatisfiable_wording": (
            "with no canary channel, the private-canary-first condition cannot "
            "be satisfied as written"
        ),
    },
    {
        "id": "PG-11126-unquoted",
        "spec_anchor": "_USER-PROMPTS.md:11126",
        "wording": UNQUOTED,
        "wording_provenance": "span membership from REL-0003 inputs (11125-11133)",
        "receipt_paths": [SPEC_FILE],
        "unsatisfiable_under": None,
        "unsatisfiable_wording": None,
    },
    {
        "id": "PG-11127-unquoted",
        "spec_anchor": "_USER-PROMPTS.md:11127",
        "wording": UNQUOTED,
        "wording_provenance": "span membership from REL-0003 inputs (11125-11133)",
        "receipt_paths": [SPEC_FILE],
        "unsatisfiable_under": None,
        "unsatisfiable_wording": None,
    },
    {
        "id": "PG-11128-unquoted",
        "spec_anchor": "_USER-PROMPTS.md:11128",
        "wording": UNQUOTED,
        "wording_provenance": "span membership from REL-0003 inputs (11125-11133)",
        "receipt_paths": [SPEC_FILE],
        "unsatisfiable_under": None,
        "unsatisfiable_wording": None,
    },
    {
        "id": "PG-11129-all-required-gates-pass",
        "spec_anchor": "_USER-PROMPTS.md:11129",
        "wording": "all required gates pass",
        "wording_provenance": "catalog quotes: REL-0014 inputs; ADV-0016 spec_anchor",
        "receipt_paths": [REL_0014, REL_0018],
        "unsatisfiable_under": None,
        "unsatisfiable_wording": None,
    },
    {
        "id": "PG-11130-fp-fn-telemetry",
        "spec_anchor": "_USER-PROMPTS.md:11130",
        "wording": "false-positive and false-negative telemetry acceptable",
        "wording_provenance": "catalog quotes: REL-0019 inputs",
        "receipt_paths": [REL_0019],
        "unsatisfiable_under": None,
        "unsatisfiable_wording": None,
    },
    {
        "id": "PG-11131-canary-succeeds",
        "spec_anchor": "_USER-PROMPTS.md:11131",
        "wording": "canary succeeds (promotion gate)",
        "wording_provenance": (
            "catalog OQ-9 text names promotion gate :11131 as a canary that "
            "PR-ONLY does not have; stopping condition 13 at :11390 uses the "
            "same canary-succeeds wording"
        ),
        "receipt_paths": [REL_0004, WAVE4],
        "unsatisfiable_under": "PR-ONLY",
        "unsatisfiable_wording": (
            "with no canary channel, the canary-succeeds condition cannot be "
            "satisfied as written"
        ),
    },
    {
        "id": "PG-11132-no-data-loss",
        "spec_anchor": "_USER-PROMPTS.md:11132",
        "wording": "no data loss occurs",
        "wording_provenance": "catalog quotes: REL-0008 question_or_target",
        "receipt_paths": [REL_0008],
        "unsatisfiable_under": None,
        "unsatisfiable_wording": None,
    },
    {
        "id": "PG-11133-unquoted",
        "spec_anchor": "_USER-PROMPTS.md:11133",
        "wording": UNQUOTED,
        "wording_provenance": "span membership from REL-0003 inputs (11125-11133)",
        "receipt_paths": [SPEC_FILE],
        "unsatisfiable_under": None,
        "unsatisfiable_wording": None,
    },
]


def condition_by_id(cid: str) -> dict:
    for c in PROMOTION_CONDITIONS:
        if c["id"] == cid:
            return c
    raise KeyError(cid)
