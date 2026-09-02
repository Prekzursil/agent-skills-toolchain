#!/usr/bin/env python3
"""Repo paths, hashing, and source lineage for RES-0154."""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
UNIT = "RES-0154"
OUT_REL = (
    "command-center/research/evidence-quality/"
    "RES-0154-refuter-incentive-and-yield-design.json"
)
SENTINEL = "SUCCESS:RES-0154"
SCHEMA_DECLARED = "command-center/schema/measurement-run.schema.json"
BILL_SECONDS_PER_ARTIFACT = 60


def now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes()
    digest = sha256_bytes(raw)
    return digest, len(raw.replace(b"\r\n", b"\n"))


def lineage(rel: str, fetched_at: str) -> dict:
    path = REPO / rel
    digest, size = sha256_file(path)
    return {
        "resolved_url": f"file:{rel}",
        "fetched_at": fetched_at,
        "sha256": digest,
        "bytes": size,
    }


def billed_hours(n_artifacts: int) -> float:
    return n_artifacts * BILL_SECONDS_PER_ARTIFACT / 3600.0
