#!/usr/bin/env python3
"""Probe 2: emitted CouncilSpec validates; Phase-7A acceptor takes it.

Dependency-gated: if a live IMP-0261 schema exists it is applied as well.
Both-states: a spec missing stopping is rejected; the example spec is accepted.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO))

from tools.blueprints.product.customer_council.compose import (  # noqa: E402
    compose_council_spec,
    load_example,
)
from tools.blueprints.product.customer_council.phase7a import (  # noqa: E402
    live_7a_schema_path,
    validate_councilspec,
)
from tools.blueprints.product.customer_council.run import (  # noqa: E402
    run_customer_council,
)

ART = REPO / "command-center" / "receipts" / "IMP-0249.json"
SECTIONS = (
    "charter",
    "participants",
    "roles",
    "engagement",
    "budgets",
    "evidence",
    "voting",
    "stopping",
    "outcomes",
    "integrity",
    "artifacts",
    "execution",
    "meta",
)


def main() -> int:
    run = run_customer_council()
    spec = run["councilspec"]
    missing = [k for k in SECTIONS if k not in spec]
    if missing:
        print(f"FAILED:IMP-0249-probe2 missing sections {missing}")
        return 1
    report = validate_councilspec(spec)
    if not report["ok"]:
        print("FAILED:IMP-0249-probe2 spec failed 7A schema")
        print(json.dumps(report, indent=2)[:4000])
        return 1
    acceptance = run["acceptance"]
    if not acceptance.get("accepted"):
        print("FAILED:IMP-0249-probe2 7A runtime did not accept spec")
        print(json.dumps(acceptance, indent=2)[:4000])
        return 1
    if acceptance.get("deliberation_executed"):
        print("FAILED:IMP-0249-probe2 acceptor executed deliberation")
        return 1

    bad = copy.deepcopy(spec)
    del bad["stopping"]
    bad_report = validate_councilspec(bad)
    if bad_report["ok"]:
        print("FAILED:IMP-0249-probe2 missing-stopping spec was accepted (vacuous schema)")
        return 1

    extra = copy.deepcopy(spec)
    extra["unknown_section"] = {"x": 1}
    extra_report = validate_councilspec(extra)
    if extra_report["ok"]:
        print("FAILED:IMP-0249-probe2 unknown root key was accepted")
        return 1

    example = load_example()
    again = compose_council_spec(
        question=example["question"],
        stakeholders=example["stakeholders"],
        risk_tier=example["risk_tier"],
    )
    if again != spec:
        print("FAILED:IMP-0249-probe2 compose is not a pure function of inputs")
        return 1

    live = live_7a_schema_path()
    if not ART.is_file() or ART.stat().st_size < 200:
        print("FAILED:IMP-0249-probe2 receipt missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if "SUCCESS:IMP-0249" not in json.dumps(doc):
        print("FAILED:IMP-0249-probe2 sentinel absent")
        return 1

    out = {
        "probe": "probe2-councilspec-contract",
        "unit_id": "IMP-0249",
        "pass": True,
        "accepted": True,
        "schema_path": report["schema_path"],
        "live_schema": report["live_schema"],
        "live_schema_path": None if live is None else live.relative_to(REPO).as_posix(),
        "gated_on_live_7a_schema": live is not None,
        "missing_stopping_rejected": True,
        "unknown_key_rejected": True,
        "named_participants": acceptance.get("named_participants"),
        "named_rounds": acceptance.get("named_rounds"),
        "both_states": True,
    }
    print(json.dumps(out, sort_keys=True))
    print(
        f"accepted=True schema={report['schema_path']} live={report['live_schema']} "
        f"stopping_rejected=True"
    )
    print("SUCCESS:IMP-0249-probe2 CouncilSpec validates and 7A runtime accepts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
