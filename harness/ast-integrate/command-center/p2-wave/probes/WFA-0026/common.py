#!/usr/bin/env python3
"""Shared paths and hashing for WFA-0026."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
UNIT = "WFA-0026"
OUT_REL = "command-center/wfa/WFA-0026-sweep-practitioner-reports.json"
RULE_REL = "command-center/p2-wave/probes/WFA-0026/grading_rule.json"
SCHEMA_REL = "command-center/p2-wave/probes/WFA-0026/sweep_report.schema.json"
VENDOR_SWEEP = "command-center/wfa/WFA-0021-sweep-vendor-documentation.json"
SENTINEL = "SUCCESS:WFA-0026"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/WFA-0026/probe1_trust_grade_mechanical.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/WFA-0026/probe2_duplicate_and_injection.py"
)
QUESTION = (
    "Which orchestration mechanisms are described by practitioners as in "
    "production use, are NOT covered by vendor documentation or papers, and "
    "what trust grade does each source earn under a written grading rule?"
)


def digest_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def digest_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def dump_json(path: Path, doc) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")


def folded(text: str) -> str:
    return " ".join((text or "").split()).casefold()
