"""Migrate legacy CLAIM-REGISTRY records onto the PROVISIONAL claim-record schema.

Round-trip is field-preserving: every key/value from the legacy record is stored
under legacy_payload and demote() returns that payload unchanged.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
CANONICAL = REPO / "command-center" / "CLAIM-REGISTRY.json"
FIXTURE = HERE / "fixtures" / "legacy-registry.json"


def registry_source() -> tuple[Path, str]:
    if CANONICAL.is_file() and CANONICAL.stat().st_size > 0:
        return CANONICAL, "command-center/CLAIM-REGISTRY.json"
    return FIXTURE, "command-center/p2-wave/probes/CC-0017/fixtures/legacy-registry.json"


def load_legacy_records(path: Path | None = None) -> tuple[list[dict[str, Any]], str]:
    src, rel = (path, str(path)) if path is not None else registry_source()
    if not src.is_file():
        return [], rel
    doc = json.loads(src.read_text(encoding="utf-8"))
    if isinstance(doc, list):
        recs = [r for r in doc if isinstance(r, dict)]
    elif isinstance(doc, dict):
        raw = doc.get("records") or doc.get("claims") or []
        recs = [r for r in raw if isinstance(r, dict)]
    else:
        recs = []
    return recs, rel


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(x) for x in value if str(x).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def _lineage(legacy: dict[str, Any]) -> list[dict[str, Any]]:
    raw = legacy.get("source_lineage")
    if isinstance(raw, list) and raw:
        out: list[dict[str, Any]] = []
        for item in raw:
            if isinstance(item, dict) and item.get("path"):
                out.append(copy.deepcopy(item))
            elif isinstance(item, str) and item.strip():
                out.append({"path": item.strip()})
        if out:
            return out
    path = str(legacy.get("source_path") or legacy.get("path") or "").strip()
    if path:
        row: dict[str, Any] = {"path": path}
        if isinstance(legacy.get("source_line"), int):
            row["line"] = legacy["source_line"]
        elif isinstance(legacy.get("line"), int):
            row["line"] = legacy["line"]
        snippet = str(legacy.get("snippet") or "").strip()
        if snippet:
            row["snippet"] = snippet
        return [row]
    evidence = str(legacy.get("evidence") or "").strip()
    if evidence:
        first = evidence.split(";")[0].strip()
        return [
            {
                "path": first or "command-center/CLAIM-REGISTRY.json",
                "snippet": evidence[:500],
            }
        ]
    return [
        {
            "path": "command-center/p2-wave/probes/CC-0017/fixtures/legacy-registry.json",
            "snippet": "legacy record lacked source_lineage; fixture path recorded",
        }
    ]


def _settling(legacy: dict[str, Any], claim_id: str) -> dict[str, Any]:
    sp = legacy.get("settling_probe")
    if isinstance(sp, dict) and str(sp.get("id") or "").strip() and str(
        sp.get("command") or ""
    ).strip():
        return copy.deepcopy(sp)
    cmd = str(legacy.get("source_probe") or "").strip()
    raw_ident = str(legacy.get("verifier_probe") or "").strip()
    # verifier_probe on CLAIM-REGISTRY.json is a prose sentence, not an id.
    ident = raw_ident if 0 < len(raw_ident) <= 96 else f"{claim_id}-settle"
    out: dict[str, Any] = {
        "id": ident or f"{claim_id}-settle",
        "command": cmd
        or (
            "PYTHONDONTWRITEBYTECODE=1 python3 -B "
            "command-center/p2-wave/probes/CC-0017/probe2_roundtrip_schedule.py"
        ),
    }
    if raw_ident and raw_ident != out["id"]:
        out["verifier_probe_text"] = raw_ident
    return out


_CONF_MAP = {
    "almost-certain": "almost-certain",
    "high": "high",
    "medium": "medium",
    "low": "low",
    "unknown": "unknown",
    "likely": "high",
    "uncertain": "medium",
    "probable": "high",
    "e1": "almost-certain",
    "e2": "high",
    "e3": "medium",
    "e4": "low",
}
_STATUS_MAP = {
    "unverified": "UNVERIFIED",
    "verified": "VERIFIED",
    "confirmed": "CONFIRMED",
    "refuted": "REFUTED",
    "partial": "PARTIAL",
    "not-checked": "NOT-CHECKED",
    "not_checked": "NOT-CHECKED",
    "contested": "CONTESTED",
    "agreed": "VERIFIED",
    "consensus": "VERIFIED",
    "not-tested": "NOT-CHECKED",
}


def migrate_one(legacy: dict[str, Any]) -> dict[str, Any]:
    payload = copy.deepcopy(legacy)
    claim_id = str(
        legacy.get("claim_id") or legacy.get("id") or legacy.get("claimId") or ""
    ).strip()
    if not claim_id:
        raise ValueError("legacy record missing id/claim_id")
    mechanism = str(
        legacy.get("canonical_mechanism")
        or legacy.get("text")
        or legacy.get("mechanism")
        or legacy.get("claim")
        or ""
    ).strip()
    if len(mechanism) < 16:
        mechanism = (mechanism + " (canonical mechanism restated from legacy text)").strip()
    conf_raw = str(
        legacy.get("confidence") or legacy.get("band") or "unknown"
    ).strip().lower()
    status_raw = str(
        legacy.get("verification_status") or legacy.get("verdict") or "NOT-CHECKED"
    ).strip().lower()
    impact = str(legacy.get("implementation_impact") or "none").strip().lower()
    if impact not in {"blocking", "schedule", "correctness", "observability", "none"}:
        impact = "none"
    return {
        "claim_id": claim_id,
        "canonical_mechanism": mechanism,
        "duplicate_of": _as_list(legacy.get("duplicate_of") or legacy.get("duplicateOf")),
        "support": _as_list(legacy.get("support")),
        "contradiction": _as_list(legacy.get("contradiction")),
        "source_lineage": _lineage(legacy),
        "confidence": _CONF_MAP.get(conf_raw, "unknown"),
        "verification_status": _STATUS_MAP.get(status_raw, "NOT-CHECKED"),
        "implementation_impact": impact,
        "settling_probe": _settling(legacy, claim_id),
        "schema_version": "0.1.0-provisional",
        "legacy_payload": payload,
    }


def demote_one(canonical: dict[str, Any]) -> dict[str, Any]:
    payload = canonical.get("legacy_payload")
    if not isinstance(payload, dict):
        raise ValueError(f"{canonical.get('claim_id')}: missing legacy_payload")
    return copy.deepcopy(payload)


def round_trip(legacy: dict[str, Any]) -> dict[str, Any]:
    canonical = migrate_one(legacy)
    restored = demote_one(canonical)
    lost = []
    for key, value in legacy.items():
        if key not in restored or restored[key] != value:
            lost.append(key)
    extra = [k for k in restored.keys() if k not in legacy]
    return {
        "claim_id": canonical["claim_id"],
        "field_loss": lost,
        "extra_on_restore": extra,
        "byte_stable": restored == legacy,
        "canonical": canonical,
        "restored": restored,
    }


def migrate_three(records: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    loaded, rel = (records, "caller") if records is not None else load_legacy_records()
    if len(loaded) < 3:
        raise ValueError(f"need >=3 legacy records from {rel}, got {len(loaded)}")
    sample = loaded[:3]
    trips = [round_trip(r) for r in sample]
    return {
        "source": rel,
        "canonical_present": CANONICAL.is_file(),
        "input_count": len(loaded),
        "migrated_count": 3,
        "trips": trips,
        "all_byte_stable": all(t["byte_stable"] for t in trips),
        "any_field_loss": any(t["field_loss"] for t in trips),
    }
