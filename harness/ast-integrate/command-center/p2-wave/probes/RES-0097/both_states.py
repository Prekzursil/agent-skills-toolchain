"""Estate both-states rule (section 3b) reconstructed from this worktree.

The catalog names `rules/common/single-signal-verification.md` section 3b as
the both-states test. That markdown file is ABSENT on this worktree. This
module reconstructs the operational rule from three independent local
anchors that all state the same pair of requirements.
"""
from __future__ import annotations

# Canonical reconstruction used by RES-0097 probes and the claim record.
RULE_ID = "single-signal-verification.md#3b-both-states"
RULE_FILE_PRESENT = False
RULE_FILE_PATH = "rules/common/single-signal-verification.md"

CANONICAL = (
    "A detector, gate, validator or probe is VALID only when it FIRES on a "
    "known-broken (bad) input AND stays SILENT on a known-good input. "
    "Silent-in-both-states measures nothing. Fires-in-both-states is a "
    "false-positive machine."
)

# Tokens that merely restate the binary discrimination test. A "NEW"
# mechanism whose novelty text is exhausted by these tokens is a dressed-up
# null result.
RESTATEMENT_TOKENS = (
    "fire on bad",
    "fires on bad",
    "fired_on_bad",
    "silent on good",
    "silent-on-good",
    "silent_on_good",
    "known-broken",
    "known-good",
    "known-bad",
    "silent in both",
    "silent-in-both",
    "fires in both",
    "fires-in-both",
    "both-states",
    "both states",
    "assay sensitivity",
    "distinguish effective from ineffective",
    "null when nothing is wrong",
)

ANCHORS = (
    {
        "path": "command-center/WORK-UNIT-CATALOG.json",
        "id": "ADV-0009",
        "claim": (
            "A detector is VALID only when the pair (fires, silent) holds; "
            "fires-in-both is a false-positive machine and silent-in-both is decorative."
        ),
    },
    {
        "path": "tools/command-center/tests/test_validate.py",
        "claim": (
            "A probe that is silent in both states measures nothing "
            "(rules/common/single-signal-verification.md 3b)."
        ),
    },
    {
        "path": "command-center/WORK-UNIT-CATALOG.json",
        "id": "RES-0002",
        "claim": (
            "both-states control: force a genuinely failing fetch (HTTP 404) and "
            "confirm the sentinel also reports FAILED there - if it reports FAILED "
            "in both states it measures nothing"
        ),
    },
)
