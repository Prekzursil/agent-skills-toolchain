#!/usr/bin/env python3
"""Shared constants and I/O for RES-0146. Classifiers never import labels from here."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
UNIT = "RES-0146"
SENTINEL = "SUCCESS:RES-0146"
ART_REL = "command-center/research/evidence-quality/RES-0146-ai-slop-source-detectability.json"
ART = REPO / ART_REL
CAPTURE_DIR = HERE / "captures"
INDEX_PATH = CAPTURE_DIR / "INDEX.json"
N_DOCS = 50
N_PER_CLASS = 25
# A priori margin over coin-flip (0.50). Frozen before scoring.
MARGIN = 0.10
AUTO_DEMOTE_POINT = 0.50 + MARGIN  # 0.60
# Wilson lower bound must also clear this to support auto-demotion.
WILSON_FLOOR = 0.50 + MARGIN
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0146/probe1_lexical_coinflip.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0146/probe2_stats_leak_mutant.py"
)
QUESTION = (
    "Can a low-quality machine-generated source be distinguished from a genuine "
    "practitioner write-up reliably enough to auto-demote it, or is the honest "
    "answer NOT DECIDABLE - measured as accuracy on a 50-document set where the "
    "ground truth is established by publication provenance rather than by reading style?"
)
UA = "ast-integrate-RES-0146-research (+https://example.invalid/res-0146; no auth)"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def digest_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return sha256_bytes(raw), len(raw)


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def dump_json(path: Path, obj: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=1, sort_keys=True) + "\n", encoding="utf-8")


def load_index() -> dict:
    return load_json(INDEX_PATH)
