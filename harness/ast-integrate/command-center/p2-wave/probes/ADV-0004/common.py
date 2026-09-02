"""Shared paths and constants for ADV-0004 truncation-sweep probes."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
UNIT = "ADV-0004"
OUT_REL = "command-center/adversarial/ADV-0004-artifact-truncation-sweep.json"
SCHEMA_DIR_REL = "command-center/schema"
REDUCER_DIR_REL = "command-center/p2-wave/probes/IMP-0416"
POSITIVE_WS_REL = "command-center/p2-wave/probes/IMP-0416/fixtures/positive"
PLANTED_SENTINEL = "SUCCESS:ADV-0004-PLANTED-SENTINEL-FIRST"
PLANTED_ATOMIC_SENTINEL = "SUCCESS:ADV-0004-PLANTED-ATOMIC-COMPLETE"
PADDING_KEY = "_adv0004_payload_tail"
PADDING_BLOB = "TAIL" + ("X" * 2400)
PERCENT_STEPS = list(range(0, 101, 5))
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0004/probe1_truncation_sweep.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0004/probe2_write_order.py"
)
SENTINEL = (
    "SUCCESS:ADV-0004 emitted ONLY when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, records BOTH named probes "
    "verbatim with their raw output, carries exactly one verdict from "
    "{CONFIRMED|REFUTED|PARTIAL|NOT-CHECKED|BLOCKED} per enumerated target, "
    "and records the result of every listed control/negative test. Any "
    "missing control downgrades the unit's verdicts to NOT-CHECKED. "
    "Otherwise FAILED:ADV-0004 <reason>."
)
QUESTION = (
    "For each artifact schema, at what truncation fraction does the "
    "completion predicate stop accepting the file - and is there any schema "
    "where a truncated artifact passes because the sentinel is written "
    "before the payload?"
)


def dump_json(doc: Any) -> str:
    return json.dumps(doc, indent=2, sort_keys=True, ensure_ascii=True) + "\n"


def digest_bytes(raw: bytes) -> tuple[str, int]:
    norm = raw.replace(b"\r\n", b"\n")
    return hashlib.sha256(norm).hexdigest(), len(norm)


def digest_file(path: Path) -> tuple[str, int]:
    return digest_bytes(path.read_bytes() if path.is_file() else b"")


def schema_paths() -> list[Path]:
    root = REPO / SCHEMA_DIR_REL
    return sorted(p for p in root.glob("*.schema.json") if p.is_file())
