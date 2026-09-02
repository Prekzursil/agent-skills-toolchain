#!/usr/bin/env python3
"""Probe 2: feature coverage + hermetic suite (egress blocked).

Signal 2 of IMP-0118: the marketplace tests run green against the fixture
with network egress blocked, and every declared feature is exercised by at
least one package. Both-states: create_connection is refused by the same
blocker that the suite ran under.
"""
from __future__ import annotations

import json
import socket
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from tools.marketplace.crypto import verify_signature  # noqa: E402
from tools.marketplace.features import DECLARED_FEATURES, coverage_matrix  # noqa: E402
from tools.marketplace.fixture import build, load_payloads  # noqa: E402
from tools.marketplace.hermetic import BLOCK_MSG, egress_blocked  # noqa: E402
from tools.marketplace.storage import read_json, registry_dir  # noqa: E402
from tools.marketplace.tests import test_fixture_registry as T  # noqa: E402

ART = REPO / "command-center/receipts/IMP-0118.json"


def main() -> int:
    build(REPO)
    index = read_json(registry_dir(REPO) / "index.json")
    payloads = load_payloads(REPO)
    sig_status = {}
    for entry in index["packages"]:
        pid = entry["id"]
        sig_status[pid] = verify_signature(payloads[pid], entry.get("signature"))
        if sig_status[pid] != "OK":
            print(f"FAILED:IMP-0118-probe2 signature {pid} {sig_status[pid]}")
            return 1
    matrix = coverage_matrix(index, payloads, sig_status)
    if not matrix["complete"]:
        print(json.dumps(matrix, indent=2)[:4000])
        print("FAILED:IMP-0118-probe2 coverage incomplete")
        return 1

    ran: list[str] = []
    with egress_blocked():
        for name, fn in T.all_tests():
            if name == "test_suite_passes_with_egress_blocked":
                continue
            fn()  # type: ignore[misc]
            ran.append(name)
        blocked_live = False
        try:
            socket.create_connection(("192.0.2.1", 80), timeout=1)
        except OSError as exc:
            blocked_live = BLOCK_MSG in str(exc)
        if not blocked_live:
            print("FAILED:IMP-0118-probe2 egress blocker not live")
            return 1

    if "test_fixture_is_lint_clean" not in ran:
        print("FAILED:IMP-0118-probe2 catalog test not executed")
        return 1

    report = {
        "probe": "probe2-hermetic-coverage",
        "unit_id": "IMP-0118",
        "declared_features": list(DECLARED_FEATURES),
        "missing": matrix["missing"],
        "label_mismatches": matrix["label_mismatches"],
        "covered_by": matrix["covered_by"],
        "tests_run_under_egress_block": ran,
        "egress_blocker_live": True,
        "coverage_complete": True,
        "pass": True,
    }
    print(json.dumps(report, sort_keys=True)[:4000])
    if not ART.is_file():
        print("FAILED:IMP-0118-probe2 receipt missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:IMP-0118-probe2 self-declared {doc.get('state')}")
        return 1
    if "SUCCESS:IMP-0118" not in text:
        print("FAILED:IMP-0118-probe2 sentinel absent")
        return 1
    rec_cov = ((doc.get("coverage") or {}).get("complete"))
    if rec_cov is not True:
        print("FAILED:IMP-0118-probe2 receipt coverage.complete is not true")
        return 1
    print("SUCCESS:IMP-0118-probe2 hermetic suite and feature coverage")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
