#!/usr/bin/env python3
"""Both-states control for ARC-0083.

Current catalogue MUST report the known defaults-only fields (a zero report
is a detector failure). A fully expanded catalogue MUST be silent.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "tools" / "command-center"))

import catalog as cat  # noqa: E402
import completeness as C  # noqa: E402
import jsonschema  # noqa: E402

CONTRACT = REPO / C.CONTRACT_REL


def fail(msg: str) -> int:
    print(f"FAILED:ARC-0083-probe1 {msg}")
    return 1


def main() -> int:
    if not CONTRACT.is_file():
        return fail(f"contract missing at {C.CONTRACT_REL}")
    doc = json.loads(CONTRACT.read_text(encoding="utf-8"))
    text = CONTRACT.read_text(encoding="utf-8")
    if "SUCCESS:ARC-0083" not in text:
        return fail("sentinel-absent")
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        return fail(f"self-declared:{doc.get('state')}")

    required = doc.get("required")
    if required != list(C.WORK_UNIT_FIELDS):
        return fail(f"required-fields-drift {required}")

    props = doc.get("properties") or {}
    for field in C.WORK_UNIT_FIELDS:
        if field not in props:
            return fail(f"property-absent:{field}")

    sub_enum = (props.get("execution_substrate") or {}).get("enum") or []
    fail_enum = ((props.get("failure_classification") or {}).get("items") or {}).get(
        "enum"
    ) or []
    if sorted(set(sub_enum)) != sorted(sub_enum) or not sub_enum:
        return fail("substrate-enum-not-closed")
    missing_sub = [s for s in C.DEFAULT_SUBSTRATES if s not in sub_enum]
    if missing_sub:
        return fail(f"substrate-enum-missing {missing_sub}")
    if not fail_enum or sorted(set(fail_enum)) != sorted(fail_enum):
        return fail("failure-enum-not-closed")
    missing_fc = [s for s in C.DEFAULT_FAILURE_SIX if s not in fail_enum]
    if missing_fc:
        return fail(f"failure-enum-missing-defaults {missing_fc}")

    jsonschema.Draft202012Validator.check_schema(doc)

    catalog = cat.load()
    live = C.analyze(catalog)
    print(
        "current defaults_only="
        f"{live['defaults_only_fields']} unresolved={live['unresolved_fields']}"
    )
    if not live["violations"]:
        return fail("detector-failure: current catalogue reported zero violations")
    missing_hist = [
        f for f in C.HISTORICAL_NINE if f not in live["defaults_only_fields"]
    ]
    if missing_hist:
        return fail(f"historical-nine-not-reported {missing_hist}")
    recorded = (doc.get("measured") or {}).get("defaults_only_fields")
    if recorded != live["defaults_only_fields"]:
        return fail(
            f"artifact-measurement-drift artifact={recorded} live={live['defaults_only_fields']}"
        )

    expanded = C.expand_per_unit(catalog)
    good = C.analyze(expanded)
    print(
        "expanded defaults_only="
        f"{good['defaults_only_fields']} unresolved={good['unresolved_fields']}"
    )
    if good["violations"]:
        return fail(f"expanded-not-silent {good['violations'][:4]}")

    sample = next(
        (item for item in cat.items(expanded) if item.get("id") == "R-A01"),
        cat.items(expanded)[0],
    )
    jsonschema.Draft202012Validator(doc).validate(sample)
    print(f"schema-accepts expanded item id={sample.get('id')}")

    mutant = json.loads(json.dumps(sample))
    mutant.pop("timeout_seconds", None)
    try:
        jsonschema.Draft202012Validator(doc).validate(mutant)
    except jsonschema.ValidationError:
        print("schema-rejects item missing timeout_seconds")
    else:
        return fail("schema-accepted incomplete item (timeout_seconds removed)")

    print(
        f"fired_on_current={bool(live['violations'])} "
        f"silent_on_expanded={not good['violations']} "
        f"historical_nine={len(C.HISTORICAL_NINE)}"
    )
    print("SUCCESS:ARC-0083-probe1 both-states defaults-only detector")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
