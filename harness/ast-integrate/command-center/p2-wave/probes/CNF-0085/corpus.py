#!/usr/bin/env python3
"""Receipt corpus: pass control plus partial, malformed, and sentinel-missing rows.

Each negative row is the passing production-shaped receipt with one isolated
break so first-fail ids are attributable. Fixtures live under fixtures/.
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
REL = "command-center/p2-wave/probes/CNF-0085/fixtures"

SCHEMA_REL = f"{REL}/artifact.schema.json"
PASS_ART = f"{REL}/pass/artifact.json"
PASS_MAN = f"{REL}/pass/manifest.json"
UNIT = "FIX-0001"
SENTINEL = "SUCCESS:FIX-0001 fixture-pass"
FLOOR = 64
ANCHOR_A = "command-center/p2-wave/probes/CNF-0085/corpus.py:1"
ANCHOR_B = "command-center/p2-wave/probes/CNF-0085/spec.py:1"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _art(rel: str, role: str = "primary") -> dict[str, Any]:
    path = REPO / rel
    raw = path.read_bytes()
    return {
        "path": rel,
        "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "exists": True,
        "role": role,
    }


def _src(fp: str, command: str, raw: str) -> dict[str, Any]:
    return {
        "role": "source",
        "method": "file-read",
        "command": command,
        "raw_output": raw,
        "fingerprint": fp,
    }


def _ver(fp: str, command: str, raw: str) -> dict[str, Any]:
    return {
        "role": "verifier",
        "method": "schema-validate",
        "command": command,
        "raw_output": raw,
        "fingerprint": fp,
    }


def passing_receipt() -> dict[str, Any]:
    return {
        "row_id": "all-satisfied",
        "unit_id": UNIT,
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "process_exit_code": 0,
        "schema_path": SCHEMA_REL,
        "min_bytes_threshold": FLOOR,
        "artifacts": [_art(PASS_ART)],
        "evidence": [
            {
                "claim": "pass artifact exists on disk",
                "verdict": "CONFIRMED",
                "anchor": ANCHOR_A,
                "probes": [
                    _src("fp-src-exist", f"stat {PASS_ART}", "present"),
                    _ver("fp-ver-exist", f"jsonschema {PASS_ART}", "ok"),
                ],
            },
            {
                "claim": "pass artifact is readable JSON",
                "verdict": "CONFIRMED",
                "anchor": ANCHOR_B,
                "probes": [
                    _src("fp-src-json", f"python3 -c json.load {PASS_ART}", '{"ok":true}'),
                    _ver("fp-ver-json", f"python3 jsonschema {SCHEMA_REL}", "valid"),
                ],
            },
        ],
        "tests": [
            {
                "id": "t1",
                "command": "PYTHONDONTWRITEBYTECODE=1 python3 -c pass",
                "result": "PASS",
            }
        ],
        "negative_controls": [
            {
                "id": "c1",
                "kind": "known-broken-fixture",
                "description": "always-true stub fails the differential",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
            }
        ],
        "reviewer": {
            "reviewer_id": "cnf-0085-fixture-reviewer",
            "verdict": "PASS",
            "independent": True,
        },
        "defects": [],
        "manifest_registration": {
            "registered": True,
            "manifest_path": PASS_MAN,
        },
        "downstream_consumers": [
            {
                "consumer": "json.loads",
                "artifact_path": PASS_ART,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": {
                    "role": "verifier",
                    "method": "command",
                    "command": f"python3 -c json.loads {PASS_ART}",
                    "raw_output": '{"unit_id":"FIX-0001"}',
                    "fingerprint": "fp-consumer-json",
                },
            }
        ],
    }


def _mut(row_id: str, expect: str, fn) -> dict[str, Any]:
    rec = copy.deepcopy(passing_receipt())
    rec["row_id"] = row_id
    rec["expect_failing_condition_id"] = expect
    fn(rec)
    return rec


def ensure_fixtures(repo: Path | None = None) -> Path:
    root = repo or REPO
    fix = root / REL
    (fix / "pass").mkdir(parents=True, exist_ok=True)
    (fix / "empty").mkdir(parents=True, exist_ok=True)
    (fix / "tiny").mkdir(parents=True, exist_ok=True)
    (fix / "badjson").mkdir(parents=True, exist_ok=True)
    (fix / "nosentinel").mkdir(parents=True, exist_ok=True)
    (fix / "c4missing").mkdir(parents=True, exist_ok=True)
    (fix / "unregistered").mkdir(parents=True, exist_ok=True)
    (fix / "absent").mkdir(parents=True, exist_ok=True)

    schema = {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "type": "object",
        "required": ["unit_id"],
        "properties": {
            "unit_id": {"type": "string"},
            "sentinel": {"type": "string"},
        },
    }
    (fix / "artifact.schema.json").write_text(
        json.dumps(schema, indent=2) + "\n", encoding="utf-8"
    )

    pass_doc = {
        "unit_id": UNIT,
        "sentinel": SENTINEL,
        "payload": "x" * 80,
        "note": "positive control for CNF-0085",
    }
    (fix / "pass" / "artifact.json").write_text(
        json.dumps(pass_doc, indent=2) + "\n", encoding="utf-8"
    )
    (fix / "pass" / "manifest.json").write_text(
        json.dumps(
            {
                "artifacts": [
                    {"path": PASS_ART, "present": True, "unit_id": UNIT}
                ]
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    (fix / "empty" / "artifact.json").write_bytes(b"")
    tiny = {"unit_id": UNIT, "sentinel": SENTINEL}
    (fix / "tiny" / "artifact.json").write_text(
        json.dumps(tiny, separators=(",", ":")) + "\n", encoding="utf-8"
    )
    (fix / "badjson" / "artifact.json").write_text("{" + (" " * 80) + "\n", encoding="utf-8")
    nosent = {
        "unit_id": UNIT,
        "payload": "y" * 80,
        "comment": "mentions SUCCESS:FIX-0001 only as a different token family",
    }
    (fix / "nosentinel" / "artifact.json").write_text(
        json.dumps(nosent, indent=2) + "\n", encoding="utf-8"
    )
    c4miss = {
        "sentinel": SENTINEL,
        "payload": "z" * 80,
        "note": "unit_id omitted so C4 fails while C5 would pass",
    }
    (fix / "c4missing" / "artifact.json").write_text(
        json.dumps(c4miss, indent=2) + "\n", encoding="utf-8"
    )
    (fix / "unregistered" / "artifact.json").write_text(
        json.dumps(pass_doc, indent=2) + "\n", encoding="utf-8"
    )
    (fix / "unregistered" / "manifest.json").write_text(
        json.dumps({"artifacts": [{"path": "other.json", "present": True}]}, indent=2)
        + "\n",
        encoding="utf-8",
    )

    def write_manifest(rel_art: str, directory: str) -> None:
        (fix / directory / "manifest.json").write_text(
            json.dumps(
                {"artifacts": [{"path": rel_art, "present": True}]},
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

    write_manifest(f"{REL}/empty/artifact.json", "empty")
    write_manifest(f"{REL}/tiny/artifact.json", "tiny")
    write_manifest(f"{REL}/badjson/artifact.json", "badjson")
    write_manifest(f"{REL}/nosentinel/artifact.json", "nosentinel")
    write_manifest(f"{REL}/c4missing/artifact.json", "c4missing")
    write_manifest(f"{REL}/absent/artifact.json", "absent")
    return fix


def _point_at(rec: dict[str, Any], art_rel: str, man_rel: str) -> None:
    rec["artifacts"] = [_art(art_rel)]
    rec["manifest_registration"] = {"registered": True, "manifest_path": man_rel}
    rec["downstream_consumers"][0]["artifact_path"] = art_rel


def receipts() -> list[Any]:
    """Corpus including the pass control, per-condition breaks, partial, malformed."""
    rows: list[Any] = [passing_receipt()]
    rows[-1]["expect_failing_condition_id"] = None

    rows.append(
        _mut(
            "invalid-terminal-DONE",
            "C1",
            lambda r: r.update(state="DONE"),
        )
    )
    rows.append(
        _mut(
            "exit-zero-missing-artifact",
            "C2",
            lambda r: (
                r.update(process_exit_code=0),
                r.update(
                    artifacts=[
                        {
                            "path": f"{REL}/absent/artifact.json",
                            "bytes": 64,
                            "sha256": "a" * 64,
                            "exists": True,
                            "role": "primary",
                        }
                    ]
                ),
                r.update(
                    manifest_registration={
                        "registered": True,
                        "manifest_path": f"{REL}/absent/manifest.json",
                    }
                ),
            ),
        )
    )
    rows.append(
        _mut(
            "plausible-digest-no-file",
            "C2",
            lambda r: r.update(
                artifacts=[],
                process_exit_code=0,
            ),
        )
    )
    rows.append(
        _mut(
            "empty-artifact",
            "C3",
            lambda r: _point_at(
                r, f"{REL}/empty/artifact.json", f"{REL}/empty/manifest.json"
            ),
        )
    )
    rows.append(
        _mut(
            "tiny-under-floor",
            "C3",
            lambda r: (
                _point_at(r, f"{REL}/tiny/artifact.json", f"{REL}/tiny/manifest.json"),
                r.update(min_bytes_threshold=200),
            ),
        )
    )
    rows.append(
        _mut(
            "unparseable-partial-json",
            "C4",
            lambda r: _point_at(
                r, f"{REL}/badjson/artifact.json", f"{REL}/badjson/manifest.json"
            ),
        )
    )
    rows.append(
        _mut(
            "schema-required-key-missing",
            "C4",
            lambda r: _point_at(
                r, f"{REL}/c4missing/artifact.json", f"{REL}/c4missing/manifest.json"
            ),
        )
    )
    rows.append(
        _mut(
            "sentinel-missing",
            "C5",
            lambda r: _point_at(
                r, f"{REL}/nosentinel/artifact.json", f"{REL}/nosentinel/manifest.json"
            ),
        )
    )
    rows.append(
        _mut(
            "partial-one-evidence-anchor",
            "C6",
            lambda r: r.update(evidence=r["evidence"][:1]),
        )
    )
    rows.append(
        _mut(
            "tests-failed",
            "C7",
            lambda r: r.update(
                tests=[{"id": "t1", "command": "false", "result": "FAIL"}]
            ),
        )
    )
    rows.append(
        _mut(
            "inert-negative-control",
            "C8",
            lambda r: r.update(
                negative_controls=[
                    {
                        "id": "c1",
                        "kind": "known-broken-fixture",
                        "description": "did not fire",
                        "fired_on_bad_state": False,
                        "silent_on_good_state": True,
                    }
                ]
            ),
        )
    )
    rows.append(
        _mut(
            "reviewer-absent",
            "C9",
            lambda r: r.pop("reviewer", None),
        )
    )
    rows.append(
        _mut(
            "open-p0-defect",
            "C10",
            lambda r: r.update(
                defects=[
                    {
                        "id": "D-P0",
                        "severity": "P0",
                        "status": "open",
                        "summary": "blocker attached to a SUCCESS receipt",
                    }
                ]
            ),
        )
    )
    rows.append(
        _mut(
            "manifest-row-absent",
            "C11",
            lambda r: _point_at(
                r,
                f"{REL}/unregistered/artifact.json",
                f"{REL}/unregistered/manifest.json",
            ),
        )
    )
    rows.append(
        _mut(
            "downstream-not-readable",
            "C12",
            lambda r: r.update(
                downstream_consumers=[
                    {
                        "consumer": "json.loads",
                        "artifact_path": PASS_ART,
                        "executed": True,
                        "read_ok": False,
                        "exit_code": 1,
                        "probe": {
                            "role": "verifier",
                            "method": "command",
                            "command": "python3 -c json.loads",
                            "raw_output": "FAILED read",
                            "fingerprint": "fp-consumer-fail",
                        },
                    }
                ]
            ),
        )
    )
    rows.append("this-is-not-a-receipt")
    return rows


def row_id_of(receipt: Any) -> str:
    if isinstance(receipt, dict):
        return str(receipt.get("row_id") or "unnamed")
    return f"malformed-{type(receipt).__name__}"
