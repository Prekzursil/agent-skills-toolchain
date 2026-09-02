#!/usr/bin/env python3
"""Pre-registered four-metric acceptance set attacked by WFA-0131.

WFA-0130's foundry artifact is absent on this tree. This unit pins a surrogate
registry derived from WFA-0130's catalog question (correctness, coverage,
recovery, usability + min effect size + tie-break) and hashes it BEFORE the
first campaign run. Scoring refuses a mutated copy.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
FIXTURES = HERE / "fixtures"
REGISTRY_PATH = FIXTURES / "registry.json"
PIN_PATH = FIXTURES / "registry.pin"

# Frozen numeric predicate. Weights, estimators, and control thresholds are
# part of the pin; they are not tuned after the first campaign.
REGISTRY: dict[str, Any] = {
    "id": "WFA-0130-surrogate-metric-set",
    "source_unit": "WFA-0130",
    "source_status": "output-absent-on-disk",
    "kind": "metric-registry",
    "frozen": True,
    "metrics": {
        "correctness": {
            "estimator": "mean(case.correct) on the scored slice",
            "slice_naive": "visible",
            "weight": 0.25,
            "range": [0.0, 1.0],
            "direction": "higher-is-better",
        },
        "coverage": {
            "estimator": (
                "count(unique declared_capabilities intersect required) "
                "/ count(required_capabilities)"
            ),
            "slice_naive": "visible",
            "weight": 0.25,
            "range": [0.0, 1.0],
            "direction": "higher-is-better",
        },
        "recovery": {
            "estimator": (
                "among cases whose first attempt failed, fraction that "
                "ended correct OR set claimed_recovered"
            ),
            "slice_naive": "visible",
            "weight": 0.25,
            "range": [0.0, 1.0],
            "direction": "higher-is-better",
        },
        "usability": {
            "estimator": "mean(fields_present / fields_required) on the scored slice",
            "slice_naive": "visible",
            "weight": 0.25,
            "range": [0.0, 1.0],
            "direction": "higher-is-better",
        },
    },
    "composite": "sum(weight_i * metric_i) over the four metrics",
    "min_effect_size": 0.05,
    "max_single_metric_regression": 0.10,
    "tie_break": ["correctness", "coverage", "recovery", "usability"],
    "naive_accept_rule": (
        "ACCEPT iff candidate.composite >= baseline.composite + min_effect_size "
        "AND no naive metric is worse than baseline by more than "
        "max_single_metric_regression"
    ),
    "counter_control": {
        "id": "gaming-control-v1",
        "held_out_gap_max": 0.25,
        "effort_surplus_min": 0.5,
        "held_out_gain_min": 0.05,
        "claimed_vs_heldout_cap_gap_max": 0.40,
        "usability_minus_heldout_correctness_max": 0.35,
        "fire_rule": (
            "FIRE if any clause trips; SILENT otherwise. Gated ACCEPT requires "
            "naive ACCEPT and SILENT."
        ),
    },
    "required_capabilities": [
        "parse-input",
        "branch-policy",
        "recover-fault",
        "emit-report",
    ],
    "output_fields": ["answer", "status", "capability", "notes"],
}


class RegistryPinError(Exception):
    """Post-hoc metric edit: live registry bytes do not match the pin."""

    code = "registry-pin-mismatch"


def canonical_bytes(obj: dict) -> bytes:
    text = json.dumps(obj, indent=2, sort_keys=True) + "\n"
    return text.replace("\r\n", "\n").encode("utf-8")


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def freeze_registry(path: Path | None = None) -> tuple[dict, str]:
    """Write registry.json then registry.pin. Must run before scoring."""
    dest = path or REGISTRY_PATH
    dest.parent.mkdir(parents=True, exist_ok=True)
    raw = canonical_bytes(REGISTRY)
    dest.write_bytes(raw)
    digest = sha256_bytes(raw)
    pin = dest.with_suffix(".pin")
    pin.write_text(digest + "\n", encoding="utf-8")
    return json.loads(raw.decode("utf-8")), digest


def load_pinned_registry(
    path: Path | None = None, expected_sha: str | None = None
) -> tuple[dict, str]:
    dest = path or REGISTRY_PATH
    if not dest.is_file():
        raise RegistryPinError(f"registry missing: {dest}")
    raw = dest.read_bytes().replace(b"\r\n", b"\n")
    live = sha256_bytes(raw)
    pin_path = dest.with_suffix(".pin")
    if expected_sha is None and pin_path.is_file():
        expected_sha = pin_path.read_text(encoding="utf-8").strip()
    if not expected_sha:
        raise RegistryPinError("no pin recorded before scoring")
    if live != expected_sha:
        raise RegistryPinError(
            f"{RegistryPinError.code} live={live} pin={expected_sha}"
        )
    doc = json.loads(raw.decode("utf-8"))
    if not isinstance(doc, dict):
        raise RegistryPinError("registry is not an object")
    return doc, live
