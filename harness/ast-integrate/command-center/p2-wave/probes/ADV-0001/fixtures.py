#!/usr/bin/env python3
"""Six-plus adversarial envelopes plus one consumer-usable negative control.

Attack classes (catalog evidence_requirement):
  semantically-empty, contradictory-sentinel, enum-unaccepted,
  plus missing-consumer-field, wrong-type, and null-record.

Every envelope is constructed to PASS the syntactic 12-condition reducer.
Only the control is readable by consumer.consume_file.
"""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
FIX = HERE / "fixtures"
ENVELOPE_REL = "command-center/p2-wave/probes/ADV-0001/fixtures/envelope.schema.json"
CONTROL_SHA = hashlib.sha256(b"ADV-0001-control-record").hexdigest()

ATTACK_IDS = [
    "semantically-empty",
    "contradictory-sentinel",
    "enum-unaccepted",
    "missing-consumer-field",
    "wrong-type-records",
    "null-record",
]
CONTROL_ID = "control-usable"
ALL_IDS = ATTACK_IDS + [CONTROL_ID]


def _probe(role: str, method: str, command: str, raw: str) -> dict:
    return {
        "role": role,
        "method": method,
        "command": command,
        "raw_output": raw,
        "exit_code": 0,
    }


def envelope(unit_id: str, sentinel: str, records: Any) -> dict:
    """Syntactic-complete receipt. `records` is the consumer payload, not a c12 input."""
    return {
        "unit_id": unit_id,
        "state": "SUCCESS",
        "sentinel": sentinel,
        "min_bytes_threshold": 128,
        "output_schema": ENVELOPE_REL,
        "spec_anchor": "_USER-PROMPTS.md:10627-10648",
        "artifacts": [
            {
                "path": f"command-center/p2-wave/probes/ADV-0001/fixtures/{unit_id}.json",
                "bytes": 1024,
                "sha256": "a" * 64,
                "exists": True,
                "role": "primary",
            }
        ],
        "evidence": [
            {
                "claim": "Envelope satisfies the twelve syntactic completion flags.",
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/_build_IMP0433.py:42",
                "probes": [
                    _probe("source", "file-read", "read envelope", "flags set")
                ],
            },
            {
                "claim": "Declared consumer path is named, not executed by the reducer.",
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/ADV-0001/consumer.py",
                "probes": [
                    _probe(
                        "verifier",
                        "file-read",
                        "stat consumer.py",
                        "consumer module present",
                    )
                ],
            },
        ],
        "tests": [{"id": "t1", "command": "syntactic-self-check", "result": "PASS"}],
        "negative_controls": [
            {
                "id": "c1",
                "kind": "known-broken-fixture",
                "description": "detector fires on the broken tree",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
            }
        ],
        "reviewer": {
            "reviewer_id": "fixture-reviewer",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/ADV-0001/UNIT-ARTIFACT-MANIFEST.json",
        },
        "downstream_consumers": [
            {
                "consumer": "command-center/p2-wave/probes/ADV-0001/consumer.py",
                "artifact_path": f"command-center/p2-wave/probes/ADV-0001/fixtures/{unit_id}.json",
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "notes": "Flags only. The reducer does not run this consumer.",
            }
        ],
        "records": records,
    }


def _specs() -> list[tuple[str, str, Any, str]]:
    """(id, sentinel, records, attack_class)."""
    return [
        (
            "semantically-empty",
            "SUCCESS:ATTACK-001-EMPTY",
            [],
            "schema-valid-but-semantically-empty",
        ),
        (
            "contradictory-sentinel",
            "SUCCESS:ATTACK-002-CONTRADICT",
            [
                {
                    "id": "REC-FAIL",
                    "sha256": CONTROL_SHA,
                    "status": "FAILED",
                    "kind": "receipt",
                }
            ],
            "correct-sentinel-contradictory-body",
        ),
        (
            "enum-unaccepted",
            "SUCCESS:ATTACK-003-ENUM",
            [
                {
                    "id": "REC-KIND",
                    "sha256": CONTROL_SHA,
                    "status": "OK",
                    "kind": "not-a-consumer-kind",
                }
            ],
            "valid-json-enum-no-consumer-accepts",
        ),
        (
            "missing-consumer-field",
            "SUCCESS:ATTACK-004-NOSHA",
            [{"id": "REC-NOSHA", "status": "OK", "kind": "receipt"}],
            "c12-flags-true-required-field-absent",
        ),
        (
            "wrong-type-records",
            "SUCCESS:ATTACK-005-TYPE",
            "not-an-array",
            "valid-json-wrong-type-for-consumer-field",
        ),
        (
            "null-record",
            "SUCCESS:ATTACK-006-NULL",
            [None],
            "valid-json-null-record-unusable",
        ),
        (
            CONTROL_ID,
            "SUCCESS:ATTACK-CONTROL",
            [
                {
                    "id": "REC-CONTROL-1",
                    "sha256": CONTROL_SHA,
                    "status": "OK",
                    "kind": "receipt",
                }
            ],
            "negative-control-consumer-readable",
        ),
    ]


def _seal(doc: dict, dest: Path) -> dict:
    dest.parent.mkdir(parents=True, exist_ok=True)
    rel = dest.relative_to(REPO).as_posix()
    doc = copy.deepcopy(doc)
    doc["artifacts"][0]["path"] = rel
    if isinstance(doc.get("downstream_consumers"), list) and doc["downstream_consumers"]:
        doc["downstream_consumers"][0]["artifact_path"] = rel
    raw = (json.dumps(doc, indent=1, sort_keys=True) + "\n").encode("utf-8")
    doc["artifacts"][0]["bytes"] = max(len(raw), 1024)
    doc["artifacts"][0]["sha256"] = hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()
    dest.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    return doc


def dump() -> list[dict]:
    FIX.mkdir(parents=True, exist_ok=True)
    out: list[dict] = []
    for fid, sentinel, records, klass in _specs():
        doc = envelope(fid, sentinel, records)
        dest = FIX / f"{fid}.json"
        sealed = _seal(doc, dest)
        out.append(
            {
                "id": fid,
                "class": klass,
                "path": dest.relative_to(REPO).as_posix(),
                "is_control": fid == CONTROL_ID,
                "doc": sealed,
            }
        )
    return out


def load() -> list[dict]:
    if not all((FIX / f"{i}.json").is_file() for i in ALL_IDS):
        return dump()
    out: list[dict] = []
    class_by_id = {i: k for i, _, _, k in _specs()}
    for fid in ALL_IDS:
        dest = FIX / f"{fid}.json"
        doc = json.loads(dest.read_text(encoding="utf-8"))
        out.append(
            {
                "id": fid,
                "class": class_by_id[fid],
                "path": dest.relative_to(REPO).as_posix(),
                "is_control": fid == CONTROL_ID,
                "doc": doc,
            }
        )
    return out


if __name__ == "__main__":
    rows = dump()
    for r in rows:
        print(f"{r['id']} control={r['is_control']} path={r['path']}")
