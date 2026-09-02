#!/usr/bin/env python3
"""Conformance corpus: one all-pass row, twelve isolation rows, three anti-pattern rows."""
from __future__ import annotations

import copy
import json
from typing import Any

from conditions import ARTIFACT_SCHEMA, DEFAULT_MIN_BYTES, REQUIRED_SENTINEL


def _base() -> dict[str, Any]:
    return {
        "artifacts": [
            {
                "exists": True,
                "path": "artifact.json",
                "role": "primary",
            }
        ],
        "defects": [],
        "downstream_consumers": [
            {
                "consumer": "command-center/p2-wave/probes/TST-0001/harness.py",
                "executed": True,
                "exit_code": 0,
                "read_ok": True,
            }
        ],
        "evidence": [
            {
                "anchor": "oracle.py:check_c01",
                "claim": "condition C01 independently addressable",
                "verdict": "CONFIRMED",
            },
            {
                "anchor": "completion_predicate.py:reduce",
                "claim": "production reducer emits failing_condition_id",
                "verdict": "CONFIRMED",
            },
        ],
        "manifest_registration": {
            "manifest_path": "command-center/p2-wave/probes/TST-0001/UNIT-ARTIFACT-MANIFEST.json",
            "registered": True,
        },
        "min_bytes_threshold": DEFAULT_MIN_BYTES,
        "negative_controls": [
            {
                "fired_on_bad_state": True,
                "id": "always-true-reducer",
                "silent_on_good_state": True,
            }
        ],
        "reviewer": {
            "independent": True,
            "reviewer_id": "corpus-reviewer",
            "verdict": "PASS",
        },
        "sentinel": REQUIRED_SENTINEL,
        "state": "SUCCESS",
        "tests": [
            {
                "command": "true",
                "id": "t1",
                "result": "PASS",
            }
        ],
        "unit_id": "CORPUS-PASS",
    }


def _case(
    cid: str,
    expect: str | None,
    receipt: dict[str, Any],
    **extra: Any,
) -> dict[str, Any]:
    row = {
        "expect_failing_condition_id": expect,
        "id": cid,
        "min_bytes": DEFAULT_MIN_BYTES,
        "receipt": receipt,
        "required_sentinel": REQUIRED_SENTINEL,
        "schema": ARTIFACT_SCHEMA,
        "write_artifact": True,
    }
    row.update(extra)
    return row


def cases() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    out.append(_case("pass-control", None, _base()))

    r = _base()
    r["state"] = "RUNNING"
    r["unit_id"] = "CORPUS-C01"
    out.append(_case("fail-C01", "C01", r))

    r = _base()
    r["unit_id"] = "CORPUS-C02"
    out.append(_case("fail-C02", "C02", r, write_artifact=False))

    small = {
        "sentinel": REQUIRED_SENTINEL,
        "state": "SUCCESS",
        "unit_id": "CORPUS-C03",
    }
    r = _base()
    r["unit_id"] = "CORPUS-C03"
    out.append(
        _case(
            "fail-C03",
            "C03",
            r,
            artifact_contents=json.dumps(small, separators=(",", ":")) + "\n",
        )
    )

    invalid = {
        "_pad": "x" * 240,
        "sentinel": REQUIRED_SENTINEL,
        "state": "SUCCESS",
        "unit_id": 12345,
    }
    r = _base()
    r["unit_id"] = "CORPUS-C04"
    out.append(
        _case(
            "fail-C04",
            "C04",
            r,
            artifact_contents=json.dumps(invalid, sort_keys=True) + "\n",
        )
    )

    wrong = _base()
    wrong["sentinel"] = "WRONG:SENTINEL-VALUE"
    wrong["unit_id"] = "CORPUS-C05"
    out.append(_case("fail-C05", "C05", wrong))

    r = _base()
    r["evidence"] = []
    r["unit_id"] = "CORPUS-C06"
    out.append(_case("fail-C06", "C06", r))

    r = _base()
    r["tests"] = [{"command": "false", "id": "t1", "result": "FAIL"}]
    r["unit_id"] = "CORPUS-C07"
    out.append(_case("fail-C07", "C07", r))

    r = _base()
    r["negative_controls"] = [
        {
            "fired_on_bad_state": False,
            "id": "inert-control",
            "silent_on_good_state": True,
        }
    ]
    r["unit_id"] = "CORPUS-C08"
    out.append(_case("fail-C08", "C08", r))

    r = _base()
    r["reviewer"] = {
        "independent": True,
        "reviewer_id": "corpus-reviewer",
        "verdict": "FAIL",
    }
    r["unit_id"] = "CORPUS-C09"
    out.append(_case("fail-C09", "C09", r))

    r = _base()
    r["defects"] = [
        {
            "id": "D-P0-1",
            "severity": "P0",
            "status": "open",
            "summary": "open blocker attached to a success claim",
        }
    ]
    r["unit_id"] = "CORPUS-C10"
    out.append(_case("fail-C10", "C10", r))

    r = _base()
    r["manifest_registration"] = {
        "manifest_path": "command-center/p2-wave/probes/TST-0001/UNIT-ARTIFACT-MANIFEST.json",
        "registered": False,
    }
    r["unit_id"] = "CORPUS-C11"
    out.append(_case("fail-C11", "C11", r))

    r = _base()
    r["downstream_consumers"] = [
        {
            "consumer": "command-center/p2-wave/probes/TST-0001/harness.py",
            "executed": True,
            "exit_code": 0,
            "read_ok": False,
        }
    ]
    r["unit_id"] = "CORPUS-C12"
    out.append(_case("fail-C12", "C12", r))

    r = _base()
    r["exit_code"] = 0
    r["unit_id"] = "CORPUS-EXIT0"
    out.append(
        _case(
            "anti-exit0-no-artifact",
            "C02",
            r,
            write_artifact=False,
        )
    )

    r = _base()
    r["artifacts"] = [
        {
            "exists": True,
            "path": "artifact.json",
            "role": "primary",
            "sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        }
    ]
    r["unit_id"] = "CORPUS-DIGEST"
    out.append(_case("anti-digest-is-not-receipt", "C02", r, write_artifact=False))

    r = _base()
    r["evidence"] = [
        {
            "anchor": "prose:1",
            "claim": "artifact.json exists on disk at the declared path",
            "verdict": "CONFIRMED",
        },
        {
            "anchor": "prose:2",
            "claim": "path string cited as existence proof",
            "verdict": "CONFIRMED",
        },
    ]
    r["unit_id"] = "CORPUS-PATHTEXT"
    out.append(_case("anti-path-in-text-is-not-proof", "C02", r, write_artifact=False))

    return out


def isolation_cases() -> list[dict[str, Any]]:
    return [c for c in cases() if str(c["id"]).startswith("fail-C")]


def dump_fixtures(dest: Any) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    for case in cases():
        name = case["id"] + ".json"
        payload = copy.deepcopy(case)
        (dest / name).write_text(
            json.dumps(payload, indent=1, sort_keys=True) + "\n", encoding="utf-8"
        )
