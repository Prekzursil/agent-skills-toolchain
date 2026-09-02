#!/usr/bin/env python3
"""Named probe 1: malicious fixture flagged; well-scoped fixture not (both-states).

Live re-run of tools/marketplace/permission_scan.py. A scanner that flags
every package fails the minimal_clean half. A mutation that adds an unused
subprocess.spawn grant to the well-scoped package must turn red.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO))

from tools.marketplace.permission_scan import both_states  # noqa: E402
from tools.marketplace.tests.test_permission_scan import (  # noqa: E402
    MALICIOUS_UNEXERCISED,
    run_all,
)

ART = REPO / "command-center/receipts/IMP-0475.json"
SENTINEL = "SENTINEL:IMP-0475:PERMISSIONS-SCANNED"


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0475-probe1 {msg}")
    return 1


def main() -> int:
    live = both_states()
    printable = {
        "probe": "probe1-both-states-permission-scan",
        "unit_id": "IMP-0475",
        "pass": live["pass"],
        "malicious_flagged": live["malicious_flagged"],
        "minimal_clean": live["minimal_clean"],
        "malicious_unexercised": live["malicious_unexercised"],
        "minimal_unexercised": live["minimal_unexercised"],
        "malicious_exfiltration": live["malicious_exfiltration"],
        "mutation_extra_grant_flagged": live["mutation_extra_grant_flagged"],
        "computed_not_asserted": True,
    }
    print(json.dumps(printable, sort_keys=True))
    if not live["pass"]:
        return fail("both-states live scan did not pass")
    if set(live["malicious_unexercised"]) != MALICIOUS_UNEXERCISED:
        return fail(f"unexercised set drifted {live['malicious_unexercised']}")
    if live["minimal_unexercised"]:
        return fail(f"minimal unexercised {live['minimal_unexercised']}")
    if not live["malicious_exfiltration"]:
        return fail("malicious exfiltration path not detected")
    if not live["mutation_extra_grant_flagged"]:
        return fail("extra-grant mutation did not flag")

    run_all()

    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("receipt missing")
    text = ART.read_text(encoding="utf-8")
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as exc:
        return fail(f"receipt unparseable {exc}")
    if not isinstance(doc, dict):
        return fail("receipt not an object")
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")
    if SENTINEL not in text:
        return fail("sentinel-absent")
    if doc.get("unit_id") != "IMP-0475":
        return fail(f"unit_id {doc.get('unit_id')}")
    report = doc.get("report") if isinstance(doc.get("report"), dict) else {}
    both = doc.get("both_states") or report.get("both_states") or {}
    if both.get("malicious_flagged") is not True:
        return fail("receipt both_states.malicious_flagged")
    if both.get("minimal_clean") is not True:
        return fail("receipt both_states.minimal_clean")
    answer = (
        doc.get("exact_question_answer")
        or report.get("exact_question_answer")
        or {}
    )
    if set(answer.get("imp0475.malicious") or []) != MALICIOUS_UNEXERCISED:
        return fail(f"receipt exact_question_answer malicious {answer}")
    if "imp0475.minimal" not in answer or list(answer["imp0475.minimal"]) != []:
        return fail(f"receipt exact_question_answer minimal {answer}")

    print(
        f"malicious_flagged=True minimal_clean=True "
        f"unexercised={live['malicious_unexercised']} "
        f"exfil={live['malicious_exfiltration']} mutation_red=True"
    )
    print("SUCCESS:IMP-0475-probe1 both-states: malicious flagged, minimal clean")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
