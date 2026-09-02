#!/usr/bin/env python3
"""Load the TST-0323 threshold file. Computed rates must not live in it."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PREREG_PATH = HERE / "threshold_prereg.json"
PROTOCOL_PATH = HERE / "protocol.json"

FORBIDDEN_PREREG_KEYS = frozenset(
    {
        "error_rate",
        "observed_rate",
        "observed_error_rate",
        "stratum_error_rates",
        "point_estimate",
        "sampled_error_rate",
        "k",
        "rates",
        "wilson",
        "escalations",
    }
)


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def load_prereg() -> dict:
    doc = json.loads(PREREG_PATH.read_text(encoding="utf-8"))
    if not isinstance(doc, dict):
        raise ValueError("threshold_prereg.json is not an object")
    hit = sorted(FORBIDDEN_PREREG_KEYS.intersection(doc))
    if hit:
        raise ValueError(f"prereg contaminated with computed fields {hit}")
    if doc.get("recorded_before_any_error_rate_computation") is not True:
        raise ValueError("prereg missing recorded_before_any_error_rate_computation=true")
    if "error_rate_threshold" not in doc:
        raise ValueError("prereg missing error_rate_threshold")
    if float(doc["error_rate_threshold"]) <= 0 or float(doc["error_rate_threshold"]) >= 1:
        raise ValueError("error_rate_threshold must be in (0, 1)")
    if doc.get("boundary") != "strict_gt":
        raise ValueError("prereg boundary must be strict_gt")
    strata = doc.get("strata")
    if not isinstance(strata, list) or len(strata) != 4:
        raise ValueError("prereg must declare the four 2x2 strata")
    return doc


def load_protocol() -> dict:
    doc = json.loads(PROTOCOL_PATH.read_text(encoding="utf-8"))
    if not isinstance(doc, dict):
        raise ValueError("protocol.json is not an object")
    blind = doc.get("blinding") or {}
    if blind.get("adjudicator_sees_platform_verdict") is not False:
        raise ValueError("protocol is not blind to platform_verdict")
    return doc


def receipt_field(rec: dict, key: str, default=None):
    """Read a domain field from receipt_core `report`, with top-level fallback."""
    if not isinstance(rec, dict):
        return default
    if key in rec and rec[key] is not None and key != "report":
        return rec[key]
    report = rec.get("report") if isinstance(rec.get("report"), dict) else {}
    if key in report:
        return report[key]
    return default
