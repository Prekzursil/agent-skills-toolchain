#!/usr/bin/env python3
"""Materialize a corpus case into an evaluation snapshot.

Oracle and reducer both consume this snapshot. They do not share check code.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from conditions import ARTIFACT_SCHEMA, DEFAULT_MIN_BYTES, REQUIRED_SENTINEL


def snapshot_from_case(case: dict[str, Any], workdir: Path) -> dict[str, Any]:
    receipt = case["receipt"]
    rel = str(((receipt.get("artifacts") or [{}])[0] or {}).get("path") or "artifact.json")
    path = workdir / rel
    write = case.get("write_artifact", True)
    min_bytes = int(case.get("min_bytes", receipt.get("min_bytes_threshold", DEFAULT_MIN_BYTES)))
    contents = case.get("artifact_contents")
    if write:
        path.parent.mkdir(parents=True, exist_ok=True)
        if contents is None:
            text = json.dumps(receipt, indent=1, sort_keys=True) + "\n"
            raw = text.encode("utf-8")
            if len(raw) < min_bytes:
                padded = dict(receipt)
                need = min_bytes - len(raw) + 32
                padded["_pad"] = "x" * max(need, 32)
                text = json.dumps(padded, indent=1, sort_keys=True) + "\n"
            path.write_text(text, encoding="utf-8")
        else:
            if isinstance(contents, bytes):
                path.write_bytes(contents)
            else:
                path.write_text(str(contents), encoding="utf-8")
    exists = path.is_file()
    if exists:
        raw = path.read_bytes()
        size = len(raw)
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            text = raw.decode("utf-8", errors="replace")
    else:
        size = 0
        text = ""
    return {
        "artifact_exists": exists,
        "artifact_path": rel,
        "artifact_size": size,
        "artifact_text": text,
        "case_id": case["id"],
        "min_bytes": min_bytes,
        "receipt": receipt,
        "required_sentinel": str(case.get("required_sentinel", REQUIRED_SENTINEL)),
        "schema": case.get("schema") or ARTIFACT_SCHEMA,
    }
