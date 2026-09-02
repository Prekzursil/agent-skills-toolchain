#!/usr/bin/env python3
"""Probe 1: guard fires on a deployed-path write that has a repo counterpart.

Known-present / planted-bad arm of the detector-control pair. Independently
materializes the fixture estate, performs a real Write to the deployed copy,
and asserts the advisory names the repo counterpart. Re-checks the receipt.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import estate as E  # noqa: E402

ART = REPO / E.ARTIFACT_REL
NOT_DELIVERING = {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}


def _check_artifact(fire: dict) -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:TST-0087-probe1 receipt missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as exc:
        print(f"FAILED:TST-0087-probe1 unparseable {exc}")
        return 1
    if E.SENTINEL not in text:
        print("FAILED:TST-0087-probe1 sentinel absent")
        return 1
    if doc.get("unit_id") != E.UNIT:
        print("FAILED:TST-0087-probe1 unit_id", doc.get("unit_id"))
        return 1
    st = str(doc.get("state") or "").upper()
    if st in NOT_DELIVERING:
        print(f"FAILED:TST-0087-probe1 self-declared:{st}")
        return 1
    planted = (doc.get("both_states") or {}).get("planted_bad") or {}
    if planted.get("fired") is not True:
        print("FAILED:TST-0087-probe1 receipt planted_bad.fired is not true")
        return 1
    if planted.get("path") != fire["deployed_rel"]:
        print(
            "FAILED:TST-0087-probe1 receipt path drift",
            planted.get("path"),
            fire["deployed_rel"],
        )
        return 1
    if planted.get("repo_counterpart") != fire["repo_counterpart"]:
        print("FAILED:TST-0087-probe1 receipt repo counterpart drift")
        return 1
    tests = {t.get("id"): t for t in (doc.get("tests") or []) if isinstance(t, dict)}
    row = tests.get("test_guard_fires_on_a_deployed_path_with_a_repo_counterpart")
    if not row or row.get("result") != "PASS":
        print("FAILED:TST-0087-probe1 catalog test row missing or not PASS")
        return 1
    return 0


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="tst0087-p1-") as tmp:
        fire = E.run_deployed_fire(Path(tmp) / "fire")
    payload = {
        "probe": "probe1-deployed-fires",
        "unit_id": E.UNIT,
        "pass": bool(fire.get("pass")),
        "fired": (fire.get("decision") or {}).get("fired"),
        "write_rel": fire.get("deployed_rel"),
        "repo_counterpart": fire.get("repo_counterpart"),
        "advisory": fire.get("advisory"),
        "live_write_path": fire.get("live_write_path"),
        "repo_path": fire.get("repo_path"),
    }
    print(json.dumps(payload, sort_keys=True))
    if not fire.get("pass"):
        print("FAILED:TST-0087-probe1 guard did not fire on deployed path")
        print(json.dumps(fire, indent=2, default=str)[:3000])
        return 1
    if _check_artifact(fire) != 0:
        return 1
    print(
        f"fired={payload['fired']} write_rel={payload['write_rel']} "
        f"repo_counterpart={payload['repo_counterpart']}"
    )
    print("SUCCESS:TST-0087-probe1 guard fired on deployed-path write")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
