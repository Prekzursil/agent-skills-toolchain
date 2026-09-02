"""Shared measurement for ADV-0097 named probes and the emitted artifact."""
from __future__ import annotations

from pathlib import Path

from fixture import COUNTEREXAMPLE_ID, DISSENT_TOKEN, MAJORITY_TOKEN, STAGES
from trace import matrix

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
PRODUCTION_PATHS = (
    "tools/council/simulate.py",
    "tools/council/vote/tally.py",
    "command-center/design/council/CNL-0070-minority-report-generation-and-mandatory-preservation.md",
    "command-center/design/council/CNL-0097-lost-dissent-diffing-the-transcript-against-the-synthesis.md",
    "command-center/design/council/CNL-0120-dissent-preservation-simulation-with-a-planted-dropped-dis.md",
    "command-center/phase3/A1/FAILURE-MODES.json",
)


def production_inventory() -> list[dict]:
    rows = []
    for rel in PRODUCTION_PATHS:
        path = REPO / rel
        rows.append(
            {
                "path": rel,
                "exists": path.is_file(),
                "bytes": path.stat().st_size if path.is_file() else 0,
            }
        )
    return rows


def evaluate() -> dict:
    m = matrix()
    husk = m["husk"]
    preserve = m["preserve"]
    mutant = m["drop_majority"]
    omit = m["omit"]
    live_ok = (
        m["control_majority_survives_on_live"]
        and m["control_majority_survives_on_preserve"]
        and m["control_fires_on_majority_drop"]
        and m["preserve_keeps_token"]
        and m["preserve_keeps_claim"]
        and husk["first_dissent_token_absent"] == "artifact_manifest"
        and husk["first_dissent_claim_absent"] == "synthesis"
        and omit["first_dissent_token_absent"] == "synthesis"
        and mutant["trace_broken"]
        and not husk["trace_broken"]
    )
    token_verdict = "CONFIRMED"
    claim_verdict = "CONFIRMED"
    if not m["control_majority_survives_on_live"] or not m["control_fires_on_majority_drop"]:
        token_verdict = "NOT-CHECKED"
        claim_verdict = "NOT-CHECKED"
    return {
        "ok": live_ok,
        "matrix": m,
        "inventory": production_inventory(),
        "live_policy": "husk",
        "token_drop_stage": husk["first_dissent_token_absent"],
        "claim_drop_stage": husk["first_dissent_claim_absent"],
        "token_verdict": token_verdict,
        "claim_verdict": claim_verdict,
        "majority_control_pass": m["control_majority_survives_on_live"],
        "majority_drop_control_fires": m["control_fires_on_majority_drop"],
        "preserve_both_survive": m["preserve_keeps_token"] and m["preserve_keeps_claim"],
        "tokens": {
            "dissent": DISSENT_TOKEN,
            "majority": MAJORITY_TOKEN,
            "counterexample": COUNTEREXAMPLE_ID,
        },
        "stages": list(STAGES),
        "husk_rows": husk["rows"],
        "preserve_rows": preserve["rows"],
        "omit_rows": omit["rows"],
        "drop_majority_rows": mutant["rows"],
    }
