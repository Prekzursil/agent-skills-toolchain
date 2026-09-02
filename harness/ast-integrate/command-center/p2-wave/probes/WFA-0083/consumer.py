"""Downstream WFA consumer: parse + required-field assertion, not existence."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

# A hash match cannot see a schema-version mismatch. Each record type names
# fields a real downstream reader must obtain.
REQUIRED_FIELDS: dict[str, tuple[str, ...]] = {
    "AuditReport": ("unit_id", "state", "sentinel", "findings"),
    "ProbeReport": ("unit_id", "state", "sentinel"),
    "SweepReport": ("unit_id", "state", "sentinel"),
    "ExtractionReport": ("unit_id", "state"),
    "AdapterConformanceReport": ("unit_id", "state"),
    "FusionResult": ("unit_id", "state"),
    "RepairRecord": ("unit_id", "state"),
    "Graph": ("nodes", "edges"),
    "SemanticDiff": ("unit_id", "state"),
    "MechanismRecord": ("unit_id", "state"),
    "DispositionRecord": ("unit_id", "state"),
    "CoverageMatrix": ("unit_id", "state"),
    "WorkflowIR": ("unit_id", "state"),
    "BenchmarkResult": ("unit_id", "state"),
    "HandoffContract": ("unit_id", "state"),
    "CertificationRecord": ("unit_id", "state"),
    "WorkflowRecord": ("unit_id", "state"),
    "RegressionFixture": ("unit_id", "state"),
}


def required_for(record_type: str) -> tuple[str, ...]:
    return REQUIRED_FIELDS.get(record_type, ("unit_id",))


def consume(path: Path, record_type: str) -> dict[str, Any]:
    reader = "command-center/p2-wave/probes/WFA-0083/consumer.py"
    try:
        raw = path.read_bytes()
    except OSError as exc:
        return {
            "ok": False,
            "reader": reader,
            "error": f"unreadable:{type(exc).__name__}",
            "record_type": record_type,
        }
    try:
        doc = json.loads(raw.replace(b"\r\n", b"\n").decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        return {
            "ok": False,
            "reader": reader,
            "error": f"json-parse:{type(exc).__name__}:{exc}",
            "record_type": record_type,
        }
    if not isinstance(doc, dict):
        return {
            "ok": False,
            "reader": reader,
            "error": f"json-root:{type(doc).__name__}",
            "record_type": record_type,
        }
    if not doc:
        return {
            "ok": False,
            "reader": reader,
            "error": "json-object-empty",
            "record_type": record_type,
        }
    need = required_for(record_type)
    missing = [k for k in need if k not in doc]
    if missing:
        return {
            "ok": False,
            "reader": reader,
            "error": f"missing-required-fields:{','.join(missing)}",
            "record_type": record_type,
            "first_parsed_key": next(iter(doc)),
            "record_count": len(doc),
        }
    asserted = need[0]
    value = doc.get(asserted)
    if value is None or (isinstance(value, (str, list, dict)) and len(value) == 0):
        return {
            "ok": False,
            "reader": reader,
            "error": f"required-field-empty:{asserted}",
            "record_type": record_type,
            "first_parsed_key": next(iter(doc)),
            "record_count": len(doc),
        }
    return {
        "ok": True,
        "reader": reader,
        "record_type": record_type,
        "first_parsed_key": next(iter(doc)),
        "asserted_field": asserted,
        "asserted_value_type": type(value).__name__,
        "record_count": len(doc),
        "error": "",
    }


def consume_json(path: Path) -> dict[str, Any]:
    """Parse JSON and assert a non-empty first key. Not an exists() check."""
    reader = "command-center/p2-wave/probes/WFA-0083/consumer.py:consume_json"
    try:
        raw = path.read_bytes()
        doc = json.loads(raw.replace(b"\r\n", b"\n").decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return {
            "ok": False,
            "reader": reader,
            "error": f"json-parse:{type(exc).__name__}:{exc}",
        }
    if not isinstance(doc, dict) or not doc:
        return {
            "ok": False,
            "reader": reader,
            "error": f"json-root-unusable:{type(doc).__name__}",
        }
    key = next(iter(doc))
    val = doc[key]
    if val is None or (isinstance(val, (str, list, dict)) and len(val) == 0):
        return {
            "ok": False,
            "reader": reader,
            "error": f"first-key-empty:{key}",
            "first_parsed_key": key,
        }
    return {
        "ok": True,
        "reader": reader,
        "first_parsed_key": key,
        "asserted_field": key,
        "asserted_value_type": type(val).__name__,
        "record_count": len(doc),
        "error": "",
    }


def consume_registered(path: Path, record_type: str) -> dict[str, Any]:
    """Typed consume when the payload matches; otherwise JSON-key fallback.

    Typed failure of a sibling is recorded, not hidden. Malformed AuditReport
    controls must still call consume(..., 'AuditReport') directly.
    """
    typed = consume(path, record_type)
    if typed.get("ok"):
        return {**typed, "mode": "typed", "typed_ok": True}
    generic = consume_json(path)
    return {
        **generic,
        "mode": "json-fallback",
        "typed_ok": False,
        "typed_error": typed.get("error"),
        "record_type": record_type,
        "reader": "command-center/p2-wave/probes/WFA-0083/consumer.py:consume_registered",
    }


def prove_malformed_consumer() -> dict[str, Any]:
    """A file that hashes can still fail the consumer; that failure must fire."""
    import hashlib
    import tempfile

    malformed = {"unit_id": "WFA-0083", "state": "SUCCESS", "note": "missing sentinel and findings"}
    well = {
        "unit_id": "WFA-0083",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:WFA-0083",
        "findings": [{"id": "x", "severity": "INFO", "verdict": "CONFIRMED", "summary": "control well-formed payload"}],
    }
    with tempfile.TemporaryDirectory(prefix="wfa0083-cons-") as tmp:
        root = Path(tmp)
        bad = root / "malformed.json"
        good = root / "wellformed.json"
        bad.write_text(json.dumps(malformed) + "\n", encoding="utf-8", newline="\n")
        good.write_text(json.dumps(well) + "\n", encoding="utf-8", newline="\n")
        bad_sha = hashlib.sha256(bad.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
        bad_r = consume(bad, "AuditReport")
        good_r = consume(good, "AuditReport")
        ok = (
            (not bad_r["ok"])
            and "missing-required-fields" in str(bad_r.get("error") or "")
            and good_r["ok"]
            and len(bad_sha) == 64
        )
        return {
            "ok": ok,
            "malformed": bad_r,
            "well_formed": good_r,
            "malformed_sha256": bad_sha,
            "note": "malformed JSON still hashes; consumer rejects missing required fields",
        }
