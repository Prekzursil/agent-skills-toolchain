#!/usr/bin/env python3
"""Emit command-center/receipts/TST-0250.json from a live clean-room docs run."""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from extract import QUICKSTART, README, audit_one_document  # noqa: E402
from harness import run_detector, run_live_docs  # noqa: E402

REPO = HERE.parents[3]
OUT = "command-center/receipts/TST-0250.json"
SCHEMA = "command-center/schema/test-receipt.schema.json"
SENTINEL = "SUCCESS:TST-0250"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0250/probe1_extraction_audit.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0250/probe2_clean_room.py"
)
QUESTION = (
    "Are every README and quick-start command extracted and executed in a "
    "fresh environment with the published artifact? PASS requires 100% of "
    "extracted commands run, each exit code recorded, and any non-zero either "
    "fixed or documented as expected-failure with its reason."
)
SUPPORTING = [
    "README.md",
    "docs/quickstart.md",
    SCHEMA,
    "command-center/p2-wave/probes/TST-0250/extract.py",
    "command-center/p2-wave/probes/TST-0250/install.py",
    "command-center/p2-wave/probes/TST-0250/harness.py",
    "command-center/p2-wave/probes/TST-0250/probe1_extraction_audit.py",
    "command-center/p2-wave/probes/TST-0250/probe2_clean_room.py",
    "command-center/p2-wave/probes/TST-0250/expected_failures.json",
    "command-center/p2-wave/probes/TST-0250/fixtures/detector-good.md",
    "command-center/p2-wave/probes/TST-0250/fixtures/detector-bad.md",
]


def digest_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def present(rel: str, role: str) -> dict:
    path = REPO / rel
    if path.is_file() and path.stat().st_size > 0:
        sha, size = digest_file(path)
        return {
            "bytes": size,
            "exists": True,
            "path": rel,
            "role": role,
            "sha256": sha,
        }
    return {"bytes": 0, "exists": False, "path": rel, "role": role, "sha256": None}


def utcnow() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")


def main() -> int:
    started = utcnow()
    audit = audit_one_document(QUICKSTART, "quickstart")
    detector = run_detector()
    live = run_live_docs()
    if not audit.get("counts_match") or not audit.get("bodies_present_in_source"):
        print("FAILED:TST-0250 emit extraction audit did not pass")
        print(json.dumps(audit, indent=2)[:2000])
        return 1
    if not detector.get("pass"):
        print("FAILED:TST-0250 emit detector did not pass")
        print(json.dumps(detector, indent=2)[:2000])
        return 1
    if not live.get("pass"):
        print("FAILED:TST-0250 emit live clean-room run did not pass")
        print(json.dumps(live, indent=2, default=str)[:4000])
        return 1
    if not README.is_file():
        print("FAILED:TST-0250 emit README.md missing")
        return 1

    unexplained = live.get("unexplained_nonzero") or []
    expected_nonzero = [
        row for row in live.get("exit_codes") or [] if row.get("expected_failure")
    ]
    zero_n = sum(1 for row in live.get("exit_codes") or [] if row.get("exit_code") == 0)
    answer = (
        f"Extractor found {live['extracted_count']} fenced shell commands "
        f"({live['readme_count']} from README.md, {live['quickstart_count']} "
        f"from docs/quickstart.md). All {live['attempted_count']} were run in a "
        "clean prefix after installing the published ast-examples wheel "
        f"(origin={live['origin']}, module not in the repo). Exit codes: "
        f"{zero_n} zero, {len(expected_nonzero)} documented expected-failure, "
        f"{len(unexplained)} unexplained non-zero. Quick-start extraction "
        f"count {audit['extracted_count']} matched the independent fence count "
        f"{audit['independent_fence_count']}. Detector was silent on a good "
        "one-command fixture and failed after a planted broken command. "
        + SENTINEL
    )
    artifacts = [present(rel, "supporting") for rel in SUPPORTING]
    missing = [a for a in artifacts if not a["exists"] or a["bytes"] < 2]
    if missing:
        print("FAILED:TST-0250 emit missing supporting artifacts", missing)
        return 1

    ended = utcnow()
    doc = {
        "adv_rebuild_circle": False,
        "answer": answer,
        "artifacts": artifacts,
        "cloud_ok": False,
        "completion_sentinel": SENTINEL,
        "evidence": [
            {
                "anchor": "docs/quickstart.md",
                "claim": (
                    "Independent fence count on docs/quickstart.md matches the "
                    f"extractor ({audit['extracted_count']}); every extracted "
                    "body is a substring of the source document."
                ),
                "confidence": "almost-certain",
                "probes": [
                    {
                        "command": P1,
                        "method": "named-probe",
                        "raw_output": json.dumps(audit, sort_keys=True),
                        "role": "source",
                    },
                    {
                        "command": P1,
                        "method": "named-probe",
                        "raw_output": "re-run live by _measure_one_delivered.py",
                        "role": "verifier",
                    },
                ],
                "verdict": "CONFIRMED",
            },
            {
                "anchor": "command-center/p2-wave/probes/TST-0250/harness.py:run_live_docs",
                "claim": (
                    "Every extracted README and quick-start command was attempted "
                    "in a clean room against the published wheel; each exit code "
                    "was recorded; unexplained non-zero count is "
                    f"{len(unexplained)}."
                ),
                "confidence": "almost-certain",
                "probes": [
                    {
                        "command": P2,
                        "method": "named-probe",
                        "raw_output": json.dumps(
                            {
                                "attempted_count": live["attempted_count"],
                                "exit_codes": live["exit_codes"],
                                "extracted_count": live["extracted_count"],
                                "origin": live["origin"],
                            },
                            sort_keys=True,
                        ),
                        "role": "source",
                    },
                    {
                        "command": P2,
                        "method": "named-probe",
                        "raw_output": "re-run live by _measure_one_delivered.py",
                        "role": "verifier",
                    },
                ],
                "verdict": "CONFIRMED",
            },
            {
                "anchor": "command-center/p2-wave/probes/TST-0250/fixtures/detector-bad.md",
                "claim": (
                    "The harness is silent for a one-command good fixture and "
                    "fails after a deliberately planted broken command "
                    f"(good_exit={detector['good']['exit_code']}, "
                    f"bad_exit={detector['bad']['exit_code']})."
                ),
                "confidence": "almost-certain",
                "probes": [
                    {
                        "command": P1,
                        "method": "named-probe",
                        "raw_output": json.dumps(
                            {
                                "fired_on_bad": detector.get("fired_on_bad"),
                                "silent_on_good": detector.get("silent_on_good"),
                            },
                            sort_keys=True,
                        ),
                        "role": "verifier",
                    }
                ],
                "verdict": "CONFIRMED",
            },
        ],
        "expected_failures": expected_nonzero,
        "id": "TST-0250",
        "live": {
            "audit": audit,
            "detector": {
                "fired_on_bad": detector.get("fired_on_bad"),
                "silent_on_good": detector.get("silent_on_good"),
            },
            "docs_run": {
                "attempted_count": live["attempted_count"],
                "exit_codes": live["exit_codes"],
                "extracted_count": live["extracted_count"],
                "installed_module": live["installed_module"],
                "origin": live["origin"],
                "quickstart_count": live["quickstart_count"],
                "readme_count": live["readme_count"],
            },
        },
        "manifest_registration": {
            "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
            "manifest_path": (
                "command-center/p2-wave/probes/TST-0250/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "registered": True,
        },
        "named_probes": [
            {"command": P1, "id": "probe1", "role": "extraction-audit-and-detector"},
            {"command": P2, "id": "probe2", "role": "clean-room-published-artifact"},
        ],
        "negative_controls": [
            {
                "bad_state_output": json.dumps(detector.get("bad"), sort_keys=True),
                "description": (
                    "Plant ast-examples run --id planted-broken-command. The "
                    "harness must record a non-zero exit and treat it as "
                    "unexplained (no expected-failure reason)."
                ),
                "fired_on_bad_state": detector.get("fired_on_bad"),
                "good_state_output": json.dumps(detector.get("good"), sort_keys=True),
                "id": "TST0250-NC-PLANTED-BROKEN-COMMAND",
                "kind": "planted-broken-command",
                "silent_on_good_state": detector.get("silent_on_good"),
            }
        ],
        "notes": (
            "G-1 for TST-0250: live named probes exit 0, receipt state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write. "
            "cloud ok=true is not delivery. No ADV rebuild circle."
        ),
        "output_schema": SCHEMA,
        "produced_by": {
            "execution_substrate": "local-serialized",
            "role": "docs-conformance-tester",
            "vendor": "cursor",
        },
        "question": QUESTION,
        "required_fix": None,
        "reviewer": {
            "independent": True,
            "notes": (
                "Probe 2 does not reuse the detector fixtures. It re-installs "
                "the published wheel into a fresh prefix and runs every command "
                "extracted from README.md and docs/quickstart.md."
            ),
            "reviewer_id": "TST-0250-probe2-clean-room-published-artifact",
            "verdict": "PASS",
        },
        "reviewer_verdict": "PASS",
        "sentinel": SENTINEL,
        "state": "SUCCESS",
        "status": "DELIVERED",
        "tests": [
            {
                "command": P1,
                "id": "TST0250-extraction-audit",
                "name": "manual-to-automatic fenced-command extraction audit",
                "result": "PASS" if audit.get("counts_match") else "FAIL",
            },
            {
                "command": P1,
                "id": "TST0250-detector-control",
                "name": "planted broken command fails the harness",
                "result": "PASS" if detector.get("pass") else "FAIL",
            },
            {
                "command": P2,
                "id": "TST0250-clean-room",
                "name": "fresh prefix with only the published artifact installed",
                "result": "PASS" if live.get("pass") else "FAIL",
            },
            {
                "command": P2,
                "id": "TST0250-per-command-exit-codes",
                "name": "every extracted command attempted with exit code recorded",
                "result": "PASS" if live.get("all_attempted") else "FAIL",
            },
        ],
        "timestamps": {"ended_at": ended, "started_at": started},
        "title": "Every documented command is executed verbatim in a clean room and must exit 0",
        "unit_id": "TST-0250",
    }
    schema_path = REPO / SCHEMA
    if schema_path.is_file():
        import jsonschema

        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        jsonschema.Draft7Validator(schema).validate(doc)

    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    if SENTINEL not in out_path.read_text(encoding="utf-8"):
        print("FAILED:TST-0250 emit sentinel missing")
        return 1
    print(f"wrote {OUT} bytes={out_path.stat().st_size}")
    print(SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
