"""Hermetic twelve-condition fixtures for IMP-0415.

Each violating tree differs from the positive tree by the minimum change that
breaks the named condition. C2 (missing file) can cascade into size/parse/
sentinel/downstream; probe1 only requires that the named condition is among
the FAIL set and that the verdict is not COMPLETE.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

SENTINEL = "SENTINEL:FIXTURE-0415"
ART_REL = "out/primary.json"
SCHEMA_REL = "schema/primary.schema.json"
MANIFEST_REL = "UNIT-ARTIFACT-MANIFEST.json"
PADDING = "x" * 160

SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "required": ["ok", "marker"],
    "properties": {
        "ok": {"type": "boolean"},
        "marker": {"type": "string"},
        "padding": {"type": "string"},
    },
}


def _write(path: Path, doc: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(doc, (bytes, bytearray)):
        path.write_bytes(bytes(doc))
        return
    if isinstance(doc, str):
        path.write_text(doc, encoding="utf-8")
        return
    path.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")


def positive_record() -> dict[str, Any]:
    return {
        "state": "SUCCESS",
        "exit_code": 0,
        "sentinel": SENTINEL,
        "min_bytes_threshold": 128,
        "artifact_path": ART_REL,
        "schema_path": SCHEMA_REL,
        "digest": "not-a-live-hash",
        "artifacts": [
            {
                "path": ART_REL,
                "exists": True,
                "role": "primary",
                "sha256": "a" * 64,
            }
        ],
        "evidence": [
            {
                "claim": "primary artifact is on disk",
                "anchor": ART_REL,
                "verdict": "CONFIRMED",
            },
            {
                "claim": "schema is on disk",
                "anchor": SCHEMA_REL,
                "verdict": "CONFIRMED",
            },
        ],
        "tests": [{"id": "t1", "command": "python3 -B probe", "result": "PASS"}],
        "negative_controls": [
            {
                "id": "nc1",
                "kind": "known-broken-fixture",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
            }
        ],
        "reviewer": {
            "reviewer_id": "fixture-reviewer",
            "verdict": "PASS",
            "independent": True,
        },
        "defects": [],
        "manifest_registration": {
            "registered": True,
            "manifest_path": MANIFEST_REL,
        },
        "downstream_consumers": [
            {
                "consumer": "probe-reader",
                "artifact_path": ART_REL,
                "executed": True,
                "read_ok": True,
            }
        ],
    }


def _write_positive_tree(root: Path) -> None:
    artifact = {"ok": True, "marker": SENTINEL, "padding": PADDING}
    _write(root / SCHEMA_REL, SCHEMA)
    _write(root / ART_REL, artifact)
    _write(
        root / MANIFEST_REL,
        {
            "schema_version": 1,
            "artifacts": [{"path": ART_REL, "present": True, "unit_id": "TST-0415"}],
        },
    )


def materialize(root: Path, *, violate: int | None = None) -> dict[str, Any]:
    """Write a hermetic tree and return the reducer record.

    violate=n breaks condition n (1-12). violate=None is the positive control.
    """
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    record = positive_record()
    _write_positive_tree(root)

    if violate is None:
        return record
    if violate == 1:
        record["state"] = "DONE"
    elif violate == 2:
        art = root / ART_REL
        if art.is_file():
            art.unlink()
    elif violate == 3:
        record["min_bytes_threshold"] = 10_000_000
    elif violate == 4:
        _write(root / ART_REL, {"marker": SENTINEL, "padding": PADDING})
    elif violate == 5:
        _write(
            root / ART_REL,
            {"ok": True, "marker": "NO-SENTINEL-HERE", "padding": PADDING},
        )
    elif violate == 6:
        record["evidence"] = []
        record["evidence_anchors"] = []
    elif violate == 7:
        record["tests"] = [{"id": "t1", "command": "python3 -B probe", "result": "FAIL"}]
    elif violate == 8:
        record["negative_controls"][0]["fired_on_bad_state"] = False
    elif violate == 9:
        record.pop("reviewer")
    elif violate == 10:
        record["defects"] = [
            {
                "id": "D1",
                "severity": "P0",
                "status": "open",
                "summary": "open blocker attached to a success",
            }
        ]
    elif violate == 11:
        _write(
            root / MANIFEST_REL,
            {"schema_version": 1, "artifacts": []},
        )
        record["manifest_registration"]["registered"] = True
    elif violate == 12:
        record["downstream_consumers"][0]["executed"] = False
        record["downstream_consumers"][0]["read_ok"] = True
    else:
        raise ValueError(f"violate must be 1..12 or None, got {violate}")
    return record


def exit_zero_alone() -> dict[str, Any]:
    """The catalog exact-target fixture: exit 0 and nothing else."""
    return {"exit_code": 0}


def exit_zero_self_attested() -> dict[str, Any]:
    """Exit 0 plus flags/digest/path-in-text with no file on disk."""
    return {
        "exit_code": 0,
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "digest": "a" * 64,
        "sha256": "a" * 64,
        "artifact_path": "out/primary.json",
        "schema_path": "schema/primary.schema.json",
        "artifacts": [
            {
                "path": "out/primary.json",
                "exists": True,
                "sha256": "a" * 64,
                "role": "primary",
            }
        ],
        "schema_valid": True,
        "manifest_registered": True,
        "downstream_read_ok": True,
        "evidence": [{"anchor": "out/primary.json"}],
        "tests": [{"id": "t1", "result": "PASS"}],
        "negative_controls": [
            {"fired_on_bad_state": True, "silent_on_good_state": True}
        ],
        "reviewer": {"verdict": "PASS", "independent": True},
        "manifest_registration": {
            "registered": True,
            "manifest_path": "UNIT-ARTIFACT-MANIFEST.json",
        },
        "downstream_consumers": [{"executed": True, "read_ok": True}],
    }
