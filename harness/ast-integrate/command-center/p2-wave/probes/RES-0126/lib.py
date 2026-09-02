"""Shared paths and checks for RES-0126 (export/dual-use landscape, not legal advice)."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
UNIT_ID = "RES-0126"
ART_REL = "command-center/research/RES-0126.json"
ART = REPO / ART_REL
SENTINEL = (
    "SUCCESS:RES-0126 in the receipt AND a capability-by-capability "
    "factual basis with an explicit no-legal-conclusion statement"
)
NO_LEGAL = (
    "NO-LEGAL-CONCLUSION: this record reports a factual landscape and the "
    "owner decisions it triggers. It is not legal advice, not an ECCN "
    "classification, not an ITAR determination, and not a license-required "
    "or license-not-required ruling. No downstream unit may treat this "
    "output as a legal conclusion."
)
CLASSES = ("reverse-engineering", "security-scanning", "automation")
DISPOSITIONS = ("FLAGGED", "NOT-FLAGGED")
OVERCLAIM = re.compile(
    r"\b(?:requires an? (?:export )?license|is export-controlled|"
    r"is ITAR-controlled|classified as ECCN|ECCN is 4D004)\b",
    re.I,
)


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def sha256_path(path: Path) -> tuple[str, int]:
    raw = path.read_bytes()
    norm = raw.replace(b"\r\n", b"\n")
    return hashlib.sha256(norm).hexdigest(), len(norm)


def dump_json(doc: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(doc, indent=2, ensure_ascii=False, sort_keys=True) + "\n"
    path.write_text(text, encoding="utf-8", newline="\n")


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def rel(path: Path) -> str:
    return path.resolve().relative_to(REPO).as_posix()
