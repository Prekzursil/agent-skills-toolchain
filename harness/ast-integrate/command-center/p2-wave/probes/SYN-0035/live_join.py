"""Join live banded claims to later verification outcomes.

Does not impute. CLAIM-REGISTRY.json is absent. command-center/adversarial
and command-center/confirmation may exist as unit artifacts, but they are
not claim-level Sherman-Kent band + confirmer/refuter joins, so they are
not in this scoring frame. The measurable live frame is evidence[] rows
on SUCCESS receipts that already carry a Sherman-Kent band and a verdict.

That frame is survivorship-biased (SUCCESS receipts do not file REFUTED
evidence). It is reported, not treated as the program-wide population.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from bands import normalize_band

ADJUDICATED = frozenset({"CONFIRMED", "REFUTED"})
KNOWN_VERDICTS = frozenset(
    {"CONFIRMED", "REFUTED", "PARTIAL", "NOT-CHECKED", "BLOCKED"}
)


def input_census(repo: Path) -> dict[str, Any]:
    def present(rel: str) -> dict[str, Any]:
        path = repo / rel
        return {
            "path": rel,
            "exists": path.is_file() or path.is_dir(),
            "is_file": path.is_file(),
            "is_dir": path.is_dir(),
        }

    return {
        "claim_registry": present("command-center/CLAIM-REGISTRY.json"),
        "agents_md": present("AGENTS.md"),
        "forecast_gate": present("command-center/analysis/forecast_gate.py"),
        "confirmation_dir": present("command-center/confirmation"),
        "adversarial_dir": present("command-center/adversarial"),
        "receipts_dir": present("command-center/receipts"),
    }


def _as_verdict(raw: object) -> str:
    if not isinstance(raw, str) or not raw.strip():
        return "NOT-CHECKED"
    verd = raw.strip().upper()
    if verd in KNOWN_VERDICTS:
        return verd
    return "NOT-CHECKED"


def live_evidence_rows(repo: Path) -> list[dict[str, Any]]:
    receipts = repo / "command-center" / "receipts"
    rows: list[dict[str, Any]] = []
    if not receipts.is_dir():
        return rows
    for path in sorted(receipts.glob("*.json")):
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            continue
        if not isinstance(doc, dict):
            continue
        if str(doc.get("state") or "").upper() != "SUCCESS":
            continue
        unit = str(doc.get("unit_id") or path.stem)
        evidence = doc.get("evidence")
        if not isinstance(evidence, list):
            continue
        rel = path.relative_to(repo).as_posix()
        for i, item in enumerate(evidence):
            if not isinstance(item, dict):
                continue
            band = normalize_band(item.get("confidence") or item.get("confidence_band"))
            if band is None:
                continue
            if "verdict" not in item:
                verd = "NOT-CHECKED"
            else:
                verd = _as_verdict(item.get("verdict"))
            claim_id = f"{unit}-EV-{i:02d}"
            rows.append(
                {
                    "claim_id": claim_id,
                    "band": band,
                    "oracle_label": None,
                    "confirmer_verdict": verd,
                    "set_id": "live-success-receipt-evidence",
                    "source_path": rel,
                    "anchor": item.get("anchor"),
                    "sampling_frame": (
                        "SUCCESS-receipt evidence[]; survivorship-biased; "
                        "not CLAIM-REGISTRY; not B09/B10 claim-level join"
                    ),
                }
            )
    return rows
