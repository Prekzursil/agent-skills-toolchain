#!/usr/bin/env python3
"""Pinned mixed cohort for WFA-0091: valid, null, schema-invalid, planted, absent."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent

PLANTED_DIGEST = hashlib.sha256(b"WFA-0091-planted-digest-for-missing-file").hexdigest()

VALID_REL = "U-VALID/result.json"
INVALID_REL = "U-INVALID/result.json"
NULL_REL = "U-NULL/result.json"
PLANTED_REL = "U-PLANTED/result.json"
ABSENT_REL = "U-ABSENT/result.json"


def workspace() -> Path:
    return HERE / "fixtures" / "workspace"


def lf_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def file_digest(rel: str) -> str:
    return lf_sha256(workspace() / rel)


def load_json(rel: str) -> dict[str, Any]:
    return json.loads((workspace() / rel).read_text(encoding="utf-8"))


def contracts() -> list[dict[str, Any]]:
    from fanin import RESULT_SCHEMA  # local import; same directory on sys.path

    schema = RESULT_SCHEMA
    return [
        {"unit_id": "U-VALID", "output_path": VALID_REL, "schema": schema},
        {"unit_id": "U-NULL", "output_path": NULL_REL, "schema": schema},
        {"unit_id": "U-INVALID", "output_path": INVALID_REL, "schema": schema},
        {"unit_id": "U-PLANTED", "output_path": PLANTED_REL, "schema": schema},
        {"unit_id": "U-ABSENT", "output_path": ABSENT_REL, "schema": schema},
    ]


def inbound() -> dict[str, Any]:
    planted_payload = {
        "unit_id": "U-PLANTED",
        "status": "SUCCESS",
        "artifact_kind": "workflow-result",
    }
    return {
        "U-VALID": {
            "payload": load_json(VALID_REL),
            "digest": file_digest(VALID_REL),
        },
        "U-NULL": None,
        "U-INVALID": {
            "payload": load_json(INVALID_REL),
            "digest": file_digest(INVALID_REL),
        },
        "U-PLANTED": {
            "payload": planted_payload,
            "digest": PLANTED_DIGEST,
        },
        # U-ABSENT deliberately omitted: not received
    }


def assert_fixture_layout() -> None:
    ws = workspace()
    if not (ws / VALID_REL).is_file():
        raise FileNotFoundError(ws / VALID_REL)
    if not (ws / INVALID_REL).is_file():
        raise FileNotFoundError(ws / INVALID_REL)
    if (ws / PLANTED_REL).exists():
        raise RuntimeError("planted path must be absent on disk")
    if (ws / NULL_REL).exists():
        raise RuntimeError("null unit must have no receipt file")
    if (ws / ABSENT_REL).exists():
        raise RuntimeError("absent unit must have no receipt file")
    if not SHA256_OK(PLANTED_DIGEST):
        raise RuntimeError("planted digest is not well-formed sha256 hex")


def SHA256_OK(value: str) -> bool:
    import re

    return bool(re.fullmatch(r"[a-fA-F0-9]{64}", value))
