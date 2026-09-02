#!/usr/bin/env python3
"""Ingest gate for CNF-0026 impossibility records.

A record enters the file only when it schema-validates (two signals, named
settling experiment), the two signals use different channels and methods,
and the failure is not live-reproducible on this worktree.

The catalog output_schema path is a generated shim that $ref's a generic
report profile and carries no record-level constraints (and does not
resolve without a network/registry). The unit tests_required are encoded
here as a local Draft-07 schema: one-signal and unnamed settling
experiments are schema-invalid.
"""
from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft7Validator

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
SCHEMA_PATH = REPO / "command-center/schema/impossibility-record.schema.json"
CONTROL_ID = "CONTROL-REPRODUCIBLE-CRLF"
CONTROL_REL = (
    "command-center/p2-wave/probes/CNF-0026/fixtures/control_reproducible_crlf.txt"
)
REPRO_STATUSES = {"REPRODUCED", "REPRODUCIBLE"}

_SIGNAL = {
    "type": "object",
    "required": ["id", "channel", "method", "observation"],
    "properties": {
        "id": {"type": "string", "minLength": 1},
        "channel": {"type": "string", "minLength": 1},
        "method": {"type": "string", "minLength": 1},
        "observation": {"type": "string", "minLength": 1},
    },
}
_ATTEMPT = {
    "type": "object",
    "required": ["substrate", "action", "result"],
    "properties": {
        "substrate": {"type": "string", "minLength": 1},
        "action": {"type": "string", "minLength": 1},
        "result": {"type": "string", "minLength": 1},
    },
}
_SETTLING = {
    "type": "object",
    "required": [
        "name",
        "command",
        "expected_observation",
        "discriminating_outcome",
    ],
    "properties": {
        "name": {"type": "string", "minLength": 1},
        "command": {"type": "string", "minLength": 1},
        "expected_observation": {"type": "string", "minLength": 1},
        "discriminating_outcome": {"type": "string", "minLength": 1},
    },
}
IMPOSSIBILITY_RECORD = {
    "type": "object",
    "required": [
        "failure_id",
        "title",
        "source_units",
        "reproduction_status",
        "missing_prerequisite",
        "substrates_attempted",
        "attempts",
        "signals",
        "settling_experiment",
        "blocks_phase15_gate",
    ],
    "properties": {
        "failure_id": {"type": "string", "minLength": 1},
        "title": {"type": "string", "minLength": 1},
        "source_units": {
            "type": "array",
            "minItems": 1,
            "items": {"type": "string", "minLength": 1},
        },
        "reproduction_status": {
            "type": "string",
            "minLength": 1,
            "not": {"enum": ["REPRODUCED", "REPRODUCIBLE"]},
        },
        "missing_prerequisite": {"type": "string", "minLength": 1},
        "substrates_attempted": {
            "type": "array",
            "minItems": 1,
            "items": {"type": "string", "minLength": 1},
        },
        "attempts": {"type": "array", "minItems": 1, "items": _ATTEMPT},
        "signals": {
            "type": "array",
            "minItems": 2,
            "items": _SIGNAL,
        },
        "settling_experiment": _SETTLING,
        "blocks_phase15_gate": {"type": "boolean"},
        "phase15_gate_notes": {"type": "string"},
        "failure_class": {"type": "string"},
        "subject_path": {"type": "string"},
    },
}
DEFINITIONS = {"impossibility_record": IMPOSSIBILITY_RECORD}
LOCAL_ENVELOPE = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "definitions": DEFINITIONS,
    "type": "object",
    "required": [
        "unit_id",
        "state",
        "sentinel",
        "records",
        "reproducible_control",
    ],
    "properties": {
        "unit_id": {"type": "string", "const": "CNF-0026"},
        "state": {"type": "string", "enum": ["SUCCESS"]},
        "sentinel": {"type": "string", "minLength": 80},
        "records": {
            "type": "array",
            "minItems": 1,
            "items": {"$ref": "#/definitions/impossibility_record"},
        },
        "reproducible_control": {
            "type": "object",
            "required": ["failure_id", "refused"],
            "properties": {
                "failure_id": {"type": "string", "const": CONTROL_ID},
                "refused": {"type": "boolean", "const": True},
                "reason": {"type": "string"},
                "detector_observation": {"type": "string"},
            },
        },
    },
}


class Refuse(ValueError):
    def __init__(self, code: str, detail: str) -> None:
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


def assert_catalog_schema_present() -> None:
    if not SCHEMA_PATH.is_file() or SCHEMA_PATH.stat().st_size <= 0:
        raise Refuse("schema-invalid", f"catalog schema missing: {SCHEMA_PATH}")
    json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def load_schema() -> dict:
    """Local envelope schema (catalog shim is presence-checked, not used)."""
    assert_catalog_schema_present()
    return LOCAL_ENVELOPE


def envelope_schema() -> dict:
    return load_schema()


def record_schema() -> dict:
    schema = load_schema()
    return {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "definitions": schema["definitions"],
        "$ref": "#/definitions/impossibility_record",
    }


def crlf_present(path: Path) -> bool:
    return path.is_file() and b"\r\n" in path.read_bytes()


def control_detector_observation(repo: Path | None = None) -> str:
    repo = repo or REPO
    path = repo / CONTROL_REL
    n = path.read_bytes().count(b"\r\n") if path.is_file() else 0
    return (
        f"path={CONTROL_REL} is_file={path.is_file()} "
        f"crlf_count={n} detector_fired={crlf_present(path)}"
    )


def _validate_independence(record: dict) -> None:
    signals = record.get("signals") or []
    if len(signals) < 2:
        raise Refuse("single-signal", "fewer than two signals")
    channels = [s.get("channel") for s in signals]
    methods = [s.get("method") for s in signals]
    if len(set(channels)) < 2:
        raise Refuse(
            "single-channel",
            "signals must use two mechanically different channels",
        )
    if len(set(methods)) < 2:
        raise Refuse(
            "single-method",
            "signals must use two mechanically different methods",
        )
    se = record.get("settling_experiment") or {}
    if not se.get("name") or not se.get("command"):
        raise Refuse(
            "no-settling-experiment",
            "a record with no named settling experiment is refused",
        )


def _refuse_reproducible(record: dict, repo: Path) -> None:
    fid = str(record.get("failure_id") or "")
    if fid == CONTROL_ID:
        raise Refuse(
            "reproducible-control",
            "the planted reproducible control is never admissible",
        )
    status = str(record.get("reproduction_status") or "").upper()
    if status in REPRO_STATUSES:
        raise Refuse(
            "reproducible-control",
            f"reproduction_status={status} is a reproducible failure",
        )
    subj = record.get("subject_path")
    klass = str(record.get("failure_class") or "")
    if subj and klass == "crlf-artefact":
        if crlf_present(repo / str(subj)):
            raise Refuse(
                "reproducible-control",
                f"CRLF detector fired on {subj}; failure is reproducible",
            )


def accept_record(record: dict, repo: Path | None = None) -> None:
    repo = repo or REPO
    Draft7Validator(record_schema()).validate(record)
    _validate_independence(record)
    _refuse_reproducible(record, repo)


def accept_artifact(doc: dict, repo: Path | None = None) -> None:
    repo = repo or REPO
    Draft7Validator(envelope_schema()).validate(doc)
    for rec in doc.get("records") or []:
        accept_record(rec, repo)
    ctrl = doc.get("reproducible_control") or {}
    if ctrl.get("refused") is not True:
        raise Refuse("reproducible-control", "artifact did not record a refused control")
    if ctrl.get("failure_id") != CONTROL_ID:
        raise Refuse("reproducible-control", "control id mismatch")
    ids = {r.get("failure_id") for r in doc.get("records") or []}
    if CONTROL_ID in ids:
        raise Refuse(
            "reproducible-control",
            "planted reproducible control leaked into records",
        )
