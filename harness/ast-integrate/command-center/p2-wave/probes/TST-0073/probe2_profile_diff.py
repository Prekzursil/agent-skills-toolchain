#!/usr/bin/env python3
"""Probe 2: pre-install vs post-uninstall path-by-path census.

Every residual must be documented-intentional user data. Documented user
files that existed before install stay byte-identical. Negative control:
scorched-earth delete clears registrations (would fake a clean sweep) but
fails user-data survival — the first signal alone is not enough.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from lab import USER_KEEP  # noqa: E402
from scenario import run_suite  # noqa: E402

ART = REPO / "command-center/receipts/TST-0073.json"
SENTINEL = "SUCCESS:TST-0073"


def fail(msg: str) -> int:
    print(f"FAILED:TST-0073-probe2 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if doc.get("unit_id") != "TST-0073":
        return fail(f"unit_id={doc.get('unit_id')}")
    if SENTINEL not in text:
        return fail("sentinel absent")
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        return fail(f"self-declared {doc.get('state')}")

    suite = run_suite()
    complete = suite["complete"]
    scorched = suite["scorched"]
    tests = suite["tests"]
    diff = complete["diff"]

    if not diff["equal_except_documented"]:
        return fail(f"unexpected residuals defects={diff['defects']}")
    documented = [r["path"] for r in diff["documented_residuals"]]
    if not documented:
        return fail("install-created user data did not remain (nothing to document)")
    if diff["missing"] or diff["changed"]:
        return fail(f"missing={diff['missing']} changed={diff['changed']}")
    if not complete["user_data"]["ok"]:
        return fail("documented user data did not survive")
    if not complete["unrelated_still"]["user_keep"]:
        return fail(f"{USER_KEEP} missing after complete uninstall")
    if scorched["user_data"]["ok"] or scorched["unrelated_still"]["user_keep"]:
        return fail("scorched-earth control still reported user data survival")
    if scorched["post_uninstall"]["orphan_count"] != 0:
        return fail("scorched control unexpectedly left orphans")
    if not tests["test_documented_user_data_survives"]:
        return fail("test_documented_user_data_survives")
    if not tests["profile_diff_only_documented"]:
        return fail("profile_diff_only_documented")

    artifact_diff = doc.get("profile_diff") or {}
    if artifact_diff.get("equal_except_documented") is not True:
        return fail("artifact profile_diff.equal_except_documented is not true")

    payload = {
        "pass": True,
        "probe": "probe2-profile-diff",
        "unit_id": "TST-0073",
        "equal_except_documented": True,
        "documented_residuals": documented,
        "defect_count": len(diff["defects"]),
        "unchanged_count": diff["unchanged_count"],
        "pre_count": diff["pre_count"],
        "post_count": diff["post_count"],
        "user_data_ok": True,
        "scorched_user_data_ok": scorched["user_data"]["ok"],
        "scorched_cleared_orphans": scorched["post_uninstall"]["orphan_count"] == 0,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        f"defects=0 documented={documented} unchanged={diff['unchanged_count']} "
        "scorched_kills_user_data=True"
    )
    print("SUCCESS:TST-0073-probe2 pre/post uninstall diff and user-data survival")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
