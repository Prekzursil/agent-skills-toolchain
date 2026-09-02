#!/usr/bin/env python3
"""Shared loaders for RES-0064 probes and emit."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
UNIT_ID = "RES-0064"
ARTIFACT_REL = "command-center/research/RES-0064.json"
SCHEMA_REL = "command-center/schema/workflow.schema.json"
INDEX_REL = "command-center/p2-wave/probes/RES-0064/captures/index.json"
SENTINEL = (
    "SUCCESS:RES-0064 in the receipt AND a mechanism table with a "
    "runtime-entanglement verdict per row and one inseparable example"
)
ENTANGLEMENT = frozenset({"SEPARABLE", "PARTIALLY-ENTANGLED", "INSEPARABLE"})
E_TIERS = frozenset({"E1", "E2", "E3", "E4"})


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def artifact_path() -> Path:
    return REPO / ARTIFACT_REL


def load_artifact() -> dict:
    return load_json(artifact_path())


def load_index() -> dict:
    return load_json(REPO / INDEX_REL)


def rail_by_id(index: dict) -> dict[str, dict]:
    return {r["id"]: r for r in index.get("rails") or [] if isinstance(r, dict)}


def capture_path(row: dict) -> Path:
    rel = str(row.get("path") or "").replace("\\", "/")
    return REPO / rel


def capture_text(row: dict) -> str:
    path = capture_path(row)
    return path.read_bytes().replace(b"\r\n", b"\n").decode("utf-8", "replace")


def local_schema_gap() -> dict:
    path = REPO / SCHEMA_REL
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    doc = json.loads(raw.decode("utf-8"))
    defs = doc.get("$defs") or doc.get("definitions") or {}
    stage = (defs.get("stage") or {}).get("properties") or {}
    inputs = stage.get("inputs")
    outputs = stage.get("outputs")
    blob = json.dumps(stage, sort_keys=True)
    text = raw.decode("utf-8")
    lines = text.splitlines()
    input_line = next((i + 1 for i, ln in enumerate(lines) if '"inputs"' in ln), None)
    output_line = next((i + 1 for i, ln in enumerate(lines) if '"outputs"' in ln), None)
    return {
        "path": SCHEMA_REL,
        "sha256": sha256_bytes(raw),
        "bytes": len(raw),
        "stage_property_names": sorted(stage),
        "inputs_schema": inputs,
        "outputs_schema": outputs,
        "inputs_are_string_array": inputs == {
            "type": "array",
            "items": {"type": "string"},
        },
        "outputs_are_string_array": outputs == {
            "type": "array",
            "items": {"type": "string"},
        },
        "mentions_file_type": '"File"' in blob,
        "mentions_directory_type": '"Directory"' in blob,
        "mentions_checksum": "checksum" in blob.lower(),
        "mentions_ro_crate": "ro-crate" in blob.lower() or "ro_crate" in blob.lower(),
        "mentions_secondary_files": "secondary" in blob.lower(),
        "inputs_line": input_line,
        "outputs_line": output_line,
    }
