"""Load surviving claims for SYN-0042.

Prefers SYN-0041.final-report.json when present. When that upstream
artifact is absent, the hand-written fixture corpus is the audit
subject — recorded as such, never as a fake SYN-0041 read.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
SYN0041 = REPO / "command-center/synthesis/SYN-0041.final-report.json"
SYN0012 = REPO / "command-center/synthesis/SYN-0012.sensitivity.json"
ADV_DIR = REPO / "command-center/adversarial"
FIXTURE = HERE / "fixtures" / "surviving-claims.json"
SURVIVING = frozenset({"VERIFIED", "INFERRED", "UNVERIFIED", "DEFERRED"})


def _read_json(path: Path) -> Any:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None


def _items_from(doc: Any) -> list[dict[str, Any]]:
    if isinstance(doc, list):
        return [x for x in doc if isinstance(x, dict)]
    if not isinstance(doc, dict):
        return []
    for key in ("items", "claims", "surviving_claims", "report_items"):
        val = doc.get(key)
        if isinstance(val, list):
            return [x for x in val if isinstance(x, dict)]
    return []


def _normalize(raw: dict[str, Any], source: str) -> dict[str, Any]:
    label = str(raw.get("label") or raw.get("taxonomy") or "").upper()
    return {
        "id": str(raw.get("id") or raw.get("claim_id") or ""),
        "text": str(raw.get("text") or raw.get("claim_text") or raw.get("claim") or ""),
        "label": label,
        "caveat": str(raw.get("caveat") or raw.get("strongest_caveat") or ""),
        "replacement": str(raw.get("replacement") or ""),
        "source": source,
        "upstream_artifact": raw.get("upstream_artifact") or raw.get("source_id") or "",
    }


def load_fixture_claims() -> list[dict[str, Any]]:
    doc = _read_json(FIXTURE)
    items = _items_from(doc) if doc is not None else []
    return [_normalize(x, "fixture:surviving-claims") for x in items]


def load_syn0041_claims() -> list[dict[str, Any]]:
    doc = _read_json(SYN0041)
    if doc is None:
        return []
    return [_normalize(x, "SYN-0041") for x in _items_from(doc)]


def surviving_only(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for item in items:
        label = item.get("label") or ""
        if label in SURVIVING and item.get("text") and item.get("id"):
            out.append(item)
    return out


def measure_inputs() -> dict[str, Any]:
    adv_files = []
    if ADV_DIR.is_dir():
        adv_files = sorted(p.name for p in ADV_DIR.glob("*.json") if p.is_file())
    return {
        "syn0041": {
            "path": "command-center/synthesis/SYN-0041.final-report.json",
            "present": SYN0041.is_file(),
            "bytes": SYN0041.stat().st_size if SYN0041.is_file() else 0,
        },
        "syn0012": {
            "path": "command-center/synthesis/SYN-0012.sensitivity.json",
            "present": SYN0012.is_file(),
            "bytes": SYN0012.stat().st_size if SYN0012.is_file() else 0,
        },
        "b10_residuals": {
            "path": "command-center/adversarial/",
            "present": bool(adv_files),
            "files": adv_files,
            "note": (
                "Phase 12 refuter residuals (bucket B10) are the usual source "
                "of the strongest remaining caveat when present."
            ),
        },
        "fixture_fallback": {
            "path": "command-center/p2-wave/probes/SYN-0042/fixtures/surviving-claims.json",
            "present": FIXTURE.is_file(),
        },
    }


def load_audit_claims() -> dict[str, Any]:
    measured = measure_inputs()
    live = surviving_only(load_syn0041_claims())
    fixture = surviving_only(load_fixture_claims())
    if live:
        source = "SYN-0041"
        items = live
    else:
        source = "fixture:surviving-claims"
        items = fixture
    return {
        "source": source,
        "items": items,
        "rejected_skipped": [
            x["id"]
            for x in (load_syn0041_claims() or load_fixture_claims())
            if x.get("label") == "REJECTED"
        ],
        "inputs_measured": measured,
        "upstream_syn0041_present": measured["syn0041"]["present"],
        "note": (
            "Audited SYN-0041 surviving claims."
            if live
            else (
                "SYN-0041.final-report.json is absent on this worktree; the "
                "hand-written surviving-claims fixture is the audit subject. "
                "That is not a forged SYN-0041 read."
            )
        ),
    }
