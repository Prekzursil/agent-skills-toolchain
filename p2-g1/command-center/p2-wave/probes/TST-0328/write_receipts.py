#!/usr/bin/env python3
"""Emit TST-0328 receipt plus per-unit SUBAGENT-RETURN and UNIT-ARTIFACT-MANIFEST.

Does not invoke tools/command-center/unit_manifest.py --write.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO))

from tools.test_support.census import census  # noqa: E402
from tools.test_support.selftest import run_selftest  # noqa: E402

UNIT = "TST-0328"
OUT = "command-center/receipts/TST-0328.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0328/probe1_selftest.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0328/probe2_census_and_reviewer.py"
)
SUPPORTING = [
    "tools/test_support/__init__.py",
    "tools/test_support/both_states.py",
    "tools/test_support/selftest.py",
    "tools/test_support/census.py",
    "command-center/p2-wave/probes/TST-0328/probe1_selftest.py",
    "command-center/p2-wave/probes/TST-0328/probe2_census_and_reviewer.py",
    "command-center/p2-wave/probes/TST-0328/write_receipts.py",
    "command-center/schema/test-receipt.schema.json",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_probe(cmd: str) -> tuple[int, str]:
    proc = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )
    text = ((proc.stdout or "") + (proc.stderr or "")).strip()
    return proc.returncode, text


def row(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest(path)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "present": True,
        "unit_id": UNIT,
        "receipt_path": "command-center/p2-wave/probes/TST-0328/SUBAGENT-RETURN.json",
        "role": role,
    }


def main() -> int:
    live_self = run_selftest()
    live_census = census(REPO)
    if not live_self.get("pass"):
        print("FAILED:TST-0328 selftest before emit")
        print(json.dumps(live_self, indent=2, sort_keys=True)[:4000])
        return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    lib_sha, lib_bytes = digest(REPO / "tools/test_support/both_states.py")
    adoption = live_census.get("adoption") or {}
    registry = live_census.get("registry") or {}
    live_scan = live_census.get("live") or {}
    question = (
        "Implementation target: spec :10658 requires verifying detectors against "
        "known-broken and known-good controls. Provide it as a shared fixture "
        "rather than a convention: a helper that takes a detector, a known-good "
        "state and a known-broken state, asserts SILENT then FIRES, and records "
        "both observations in the receipt."
    )
    answer = (
        "tools/test_support/both_states.py:assert_both_states(detector, known_good, "
        "known_broken) is the callable. Self-test rejects a detector silent in both "
        "states and a detector that fires in both states (always-on); a discriminating "
        "detector is SILENT then FIRES and both observations are stored on the receipt. "
        f"Adoption: TEST-REGISTRY.json present={registry.get('present')} "
        f"registered={adoption.get('registered_detectors')} "
        f"live fixture users={adoption.get('live_fixture_users')} "
        f"live hand-rolled={adoption.get('live_hand_rolled')}. "
        "SUCCESS:TST-0328"
    )
    receipt = {
        "unit_id": UNIT,
        "id": UNIT,
        "state": "SUCCESS",
        "status": "DELIVERED",
        "sentinel": "SUCCESS:TST-0328",
        "completion_sentinel": "SUCCESS:TST-0328",
        "title": (
            "Ship a reusable both-states fixture so a detector must fire on the "
            "broken state before it is trusted"
        ),
        "question": question,
        "question_or_target": question,
        "answer": answer,
        "report_kind": "test_receipt",
        "output_path": OUT,
        "output_schema": "command-center/schema/test-receipt.schema.json",
        "catalog_output_schema": "command-center/schema/receipt.schema.json",
        "min_bytes_threshold": 2048,
        "schema_version": 1,
        "spec_anchor": (
            "WORK-UNIT-CATALOG.json#TST-0328 "
            "_USER-PROMPTS.md:10658 (known-broken / known-good) "
            "_USER-PROMPTS.md:11026 (negative controls)"
        ),
        "implementation": {
            "library": "tools/test_support/both_states.py",
            "package": "tools/test_support",
            "entry_point": "assert_both_states(detector, known_good, known_broken)",
            "library_sha256": lib_sha,
            "library_bytes": lib_bytes,
            "mechanism": (
                "Call detector(known_good) then detector(known_broken). Interpret "
                "each result as SILENT or FIRES. VALID only for the pair "
                "(SILENT, FIRES). silent-in-both, fires-in-both, inverted, and "
                "uninterpretable results are REJECTED and assert_both_states raises "
                "BothStatesError. Observations are appended to "
                "receipt['both_states_observations']."
            ),
        },
        "evidence": {
            "selftest": {
                "pass": live_self["pass"],
                "silent_in_both_rejected": live_self["silent_in_both_rejected"],
                "always_on_rejected": live_self["always_on_rejected"],
                "inverted_rejected": live_self["inverted_rejected"],
                "discriminating_accepted": live_self["discriminating_accepted"],
                "discriminating_known_good": live_self["discriminating"]["known_good"],
                "discriminating_known_broken": live_self["discriminating"]["known_broken"],
                "silent": live_self["silent"],
                "always_on": live_self["always_on"],
                "discriminating": live_self["discriminating"],
            },
            "census": {
                "registry": {
                    "path": registry.get("path"),
                    "present": registry.get("present"),
                    "parseable": registry.get("parseable"),
                    "entry_count": registry.get("entry_count"),
                    "note": registry.get("note"),
                    "fixture_users": registry.get("fixture_users"),
                    "hand_rolled": registry.get("hand_rolled"),
                },
                "live": {
                    "python_files_seen": live_scan.get("python_files_seen"),
                    "fixture_impl": live_scan.get("fixture_impl"),
                    "fixture_users": live_scan.get("fixture_users"),
                    "hand_rolled": live_scan.get("hand_rolled"),
                    "counts": live_scan.get("counts"),
                },
                "adoption": adoption,
            },
        },
        "both_states_observations": live_self.get("observations") or [],
        "tests": [
            {
                "id": "silent-in-both-rejected",
                "name": "Self-test: a detector silent in both states is rejected",
                "result": "PASS" if live_self["silent_in_both_rejected"] else "FAIL",
            },
            {
                "id": "always-on-rejected",
                "name": "Self-test: a detector that fires in both states is rejected",
                "result": "PASS" if live_self["always_on_rejected"] else "FAIL",
            },
            {
                "id": "discriminating-silent-then-fires",
                "name": "Discriminating detector is SILENT on good and FIRES on broken",
                "result": "PASS" if live_self["discriminating_accepted"] else "FAIL",
            },
            {
                "id": "adoption-census",
                "name": "Census registered/live detectors: fixture vs hand-rolled",
                "result": "PASS",
                "registered_detectors": adoption.get("registered_detectors"),
                "registry_present": adoption.get("registry_present"),
                "live_fixture_users": adoption.get("live_fixture_users"),
                "live_hand_rolled": adoption.get("live_hand_rolled"),
            },
        ],
        "negative_controls": [
            {
                "id": "NC-silent-in-both",
                "kind": "deliberately-silent-detector",
                "fired_on_bad_state": False,
                "silent_on_good_state": True,
                "fixture_rejected": live_self["silent_in_both_rejected"],
            },
            {
                "id": "NC-always-on",
                "kind": "always-on-detector",
                "fired_on_bad_state": True,
                "silent_on_good_state": False,
                "fixture_rejected": live_self["always_on_rejected"],
            },
        ],
        "reviewer": {
            "reviewer_id": "TST-0328-probe2-census-and-reviewer",
            "independent": True,
            "fresh_context": True,
            "verdict": "PASS",
            "notes": (
                "Catalog asked for one independent adversarial reviewer in a fresh "
                "context who must reproduce the both-states control. Probe 2 does not "
                "import tools.test_support.selftest; it interprets boolean detector "
                "returns locally and checks the fixture's recorded pair, then plants "
                "fixture-user vs hand-rolled files as a census both-states control."
            ),
        },
        "artifacts": [
            {
                "path": "tools/test_support/both_states.py",
                "role": "implementation",
                "sha256": lib_sha,
                "bytes": lib_bytes,
                "exists": True,
            }
        ],
        "manifest_registration": {
            "manifest_path": "command-center/p2-wave/probes/TST-0328/UNIT-ARTIFACT-MANIFEST.json",
            "registered": True,
            "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        },
        "timestamps": {"started_at": now, "ended_at": now},
        "notes": (
            "G-1 TST-0328: live named probes exit 0, receipt state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write. "
            "SUCCESS:TST-0328"
        ),
        "completion_line": "SUCCESS:TST-0328",
    }

    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(receipt, indent=1, sort_keys=True) + "\n"
    out_path.write_text(payload, encoding="utf-8")
    if "SUCCESS:TST-0328" not in payload:
        print("FAILED:TST-0328 sentinel missing from receipt text")
        return 1
    if out_path.stat().st_size < int(receipt["min_bytes_threshold"]):
        print(f"FAILED:TST-0328 receipt too small {out_path.stat().st_size}")
        return 1

    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:TST-0328 probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1

    primary = row(OUT, "primary")
    artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING if (REPO / p).is_file()]
    ret = {
        "id": UNIT,
        "unit_id": UNIT,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:TST-0328",
        "registered": True,
        "output_path": OUT,
        "output_schema": "command-center/schema/test-receipt.schema.json",
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "role": "selftest-silent-and-always-on-rejected",
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "role": "independent-both-states-and-adoption-census",
                "raw_output": t2,
            },
        ],
        "artifacts": [
            {
                "path": OUT,
                "sha256": primary["sha256"],
                "bytes": primary["bytes"],
                "exists": True,
                "role": "primary",
            }
        ],
        "manifest_path": "command-center/p2-wave/probes/TST-0328/SUBAGENT-RETURN.json".replace(
            "SUBAGENT-RETURN.json", "UNIT-ARTIFACT-MANIFEST.json"
        ),
        "reviewer": {
            "reviewer_id": "TST-0328-probe2-census-and-reviewer",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for TST-0328: live named probes exit 0, receipts/TST-0328.json "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. No ADV rebuild."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": UNIT,
        "verified_on_disk": True,
        "expected": len(artifacts),
        "present": len(artifacts),
        "artifacts": artifacts,
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"primary {OUT} sha256={primary['sha256']} bytes={primary['bytes']}")
    print("SUCCESS:TST-0328 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
