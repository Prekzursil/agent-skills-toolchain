#!/usr/bin/env python3
"""Live capture loader. Hashes on-disk bytes; never trusts a remembered digest."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def repo_root() -> Path:
    for p in [HERE, *HERE.parents]:
        if (p / "command-center" / "WORK-UNIT-CATALOG.json").is_file():
            return p
    raise SystemExit("FAILED:RES-0178 repo root not found")


REPO = repo_root()
CAP = HERE / "captures"
LINEAGE = HERE / "source-lineage.json"
ARTIFACT_REL = (
    "command-center/research/teardown/"
    "RES-0178-teardown-skill-and-mcp-distribution-hubs.json"
)
SCHEMA_REL = "command-center/schema/ecosystem-teardown.schema.json"


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def digest_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return sha256_bytes(raw), len(raw)


def load_capture(capture_id: str) -> dict:
    path = CAP / f"{capture_id}.raw"
    if not path.is_file():
        raise FileNotFoundError(capture_id)
    raw = path.read_bytes()
    return {
        "id": capture_id,
        "path": path,
        "raw": raw,
        "text": raw.decode("utf-8", errors="replace"),
        "sha256": sha256_bytes(raw),
        "bytes": len(raw),
    }


def lineage_row(capture_id: str) -> dict:
    doc = json.loads(LINEAGE.read_text(encoding="utf-8"))
    for row in doc.get("sources") or []:
        if row.get("id") == capture_id:
            return row
    raise KeyError(capture_id)


def assert_snippet(capture_id: str, snippet: str) -> dict:
    cap = load_capture(capture_id)
    if snippet not in cap["text"]:
        raise AssertionError(f"snippet absent from {capture_id}: {snippet[:80]}")
    live = cap["sha256"]
    row = lineage_row(capture_id)
    recorded = str(row.get("sha256") or "")
    if recorded and recorded != live:
        raise AssertionError(
            f"lineage sha mismatch {capture_id}: recorded={recorded} live={live}"
        )
    return cap
