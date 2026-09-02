#!/usr/bin/env python3
"""Named probe 1: detector control — restatement vs condition-naming."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import detector as D  # noqa: E402

FIXTURES = HERE / "fixtures"


def load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def main() -> int:
    rest = load("vacuous-restatement.json")
    spec = load("specific-condition.json")
    further = load("further-testing.json")
    generic = load("generic-disclaimer.json")

    r = D.assess(rest["text"], rest["caveat"])
    s = D.assess(spec["text"], spec["caveat"])
    f = D.assess(further["text"], further["caveat"])
    g = D.assess(generic["text"], generic["caveat"])

    restatement_flagged = bool(r["vacuous"]) and r["rule"] == "RESTATEMENT"
    specific_silent = (not s["vacuous"]) and s["verdict"] == "SPECIFIC"
    further_flagged = bool(f["vacuous"]) and f["rule"] == "FURTHER_TESTING"
    generic_flagged = bool(g["vacuous"]) and g["rule"] == "GENERIC_DISCLAIMER"
    separated = restatement_flagged and specific_silent

    print(
        json.dumps(
            {
                "restatement_flagged_vacuous": restatement_flagged,
                "restatement_rule": r["rule"],
                "condition_naming_not_flagged": specific_silent,
                "specific_rule": s["rule"],
                "further_testing_flagged": further_flagged,
                "generic_disclaimer_flagged": generic_flagged,
                "separated": separated,
            },
            sort_keys=True,
        )
    )
    if not restatement_flagged:
        print(
            f"FAILED:SYN-0042-probe1 restatement not flagged vacuous rule={r['rule']}"
        )
        return 1
    if not specific_silent:
        print(
            f"FAILED:SYN-0042-probe1 condition-naming caveat was flagged "
            f"vacuous={s['vacuous']} rule={s['rule']}"
        )
        return 1
    if not further_flagged:
        print(
            f"FAILED:SYN-0042-probe1 further-testing not flagged rule={f['rule']}"
        )
        return 1
    if not generic_flagged:
        print(
            f"FAILED:SYN-0042-probe1 generic disclaimer not flagged rule={g['rule']}"
        )
        return 1
    print(
        "SUCCESS:SYN-0042-probe1 restatement vacuous; condition-naming specific; "
        "fixtures separated"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
