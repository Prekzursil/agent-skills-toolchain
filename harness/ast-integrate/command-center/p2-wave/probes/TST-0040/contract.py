"""Claim-record contract for TST-0040.

Eight required fields from the catalog question. A missing or blank
settling_experiment is a violation. Whitespace is empty. Same-probe
source/verifier is a violation. Vacuous 'every record is complete' on
an absent registry is refused.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[4]
REGISTRY_REL = "command-center/CLAIM-REGISTRY.json"
SCHEMA_REL = "command-center/schema/claim-record.schema.json"
CONTRACT_SCHEMA_REL = (
    "command-center/p2-wave/probes/TST-0040/claim-contract.schema.json"
)

REQUIRED_FIELDS: tuple[str, ...] = (
    "id",
    "canonical_mechanism",
    "verdict",
    "confidence_band",
    "source_lineage",
    "source_probe",
    "verifier_probe",
    "settling_experiment",
)

ALIASES: dict[str, tuple[str, ...]] = {
    "id": ("id", "claim_id"),
    "canonical_mechanism": (
        "canonical_mechanism",
        "mechanism",
        "canonical_mechanism_statement",
    ),
    "verdict": ("verdict", "verification_status"),
    "confidence_band": ("confidence_band", "band"),
    "source_lineage": ("source_lineage", "lineage", "source_lineage_anchors"),
    "source_probe": ("source_probe",),
    "verifier_probe": ("verifier_probe", "verify_probe"),
    "settling_experiment": (
        "settling_experiment",
        "settling_probe",
        "exact_settling_probe",
    ),
}

VERDICTS = frozenset(
    {"CONFIRMED", "REFUTED", "PARTIAL", "NOT-CHECKED", "BLOCKED"}
)
BANDS = frozenset(
    {"almost-certain", "likely", "roughly-even", "unlikely", "remote"}
)
PROBE_KEYS = ("tool", "engine", "shell", "field", "command", "fingerprint")
CLAIM_LIST_KEYS = ("claims", "records", "items", "entries")


def golden_claim() -> dict[str, Any]:
    return {
        "id": "TST-0040-GOLDEN",
        "canonical_mechanism": (
            "Independent re-check requires a named source probe and a "
            "mechanically different verifier probe on the same claim."
        ),
        "verdict": "CONFIRMED",
        "confidence_band": "almost-certain",
        "source_lineage": {
            "path": "command-center/WORK-UNIT-CATALOG.json",
            "line": 77773,
            "note": "TST-0040 question names the eight required fields",
        },
        "source_probe": {
            "tool": "python3",
            "engine": "jsonschema.Draft7Validator",
            "shell": "bash",
            "field": "required",
        },
        "verifier_probe": {
            "tool": "python3",
            "engine": "contract.validate_claim",
            "shell": "bash",
            "field": "strip-empty-and-fingerprint",
        },
        "settling_experiment": (
            "Remove settling_experiment from this record, require "
            "validate_claim ok=false with missing-settling_experiment, "
            "restore the field, and require ok=true."
        ),
    }


def _is_blank_string(value: Any) -> bool:
    return isinstance(value, str) and not value.strip()


def _lineage_ok(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, dict):
        if not value:
            return False
        for item in value.values():
            if isinstance(item, str) and item.strip():
                return True
            if isinstance(item, (int, float)) and not isinstance(item, bool):
                return True
            if isinstance(item, (list, dict)) and item:
                return True
        return False
    if isinstance(value, list):
        return any(_lineage_ok(item) for item in value)
    return False


def _probe_ok(value: Any) -> bool:
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, dict):
        for key in PROBE_KEYS:
            raw = value.get(key)
            if isinstance(raw, str) and raw.strip():
                return True
        # Any other nonempty string value still counts as a declaration.
        for raw in value.values():
            if isinstance(raw, str) and raw.strip():
                return True
        return False
    return False


def probe_fingerprint(value: Any) -> str | None:
    if not _probe_ok(value):
        return None
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, dict):
        parts: dict[str, str] = {}
        for key in PROBE_KEYS:
            raw = value.get(key)
            if isinstance(raw, str) and raw.strip():
                parts[key] = raw.strip()
        if not parts:
            for key, raw in sorted(value.items()):
                if isinstance(raw, str) and raw.strip():
                    parts[str(key)] = raw.strip()
        return json.dumps(parts, sort_keys=True, separators=(",", ":"))
    return None


def first_value(record: dict[str, Any], field: str) -> Any:
    for key in ALIASES[field]:
        if key in record:
            return record[key]
    return None


def field_present(record: dict[str, Any], field: str) -> bool:
    value = first_value(record, field)
    if value is None:
        return False
    if field in {"source_probe", "verifier_probe"}:
        return _probe_ok(value)
    if field == "source_lineage":
        return _lineage_ok(value)
    if field == "verdict":
        return isinstance(value, str) and value.strip() in VERDICTS
    if field == "confidence_band":
        return isinstance(value, str) and value.strip() in BANDS
    if isinstance(value, str):
        return bool(value.strip())
    return value not in (None, {}, [])


def validate_claim(record: Any) -> dict[str, Any]:
    violations: list[dict[str, str]] = []
    if not isinstance(record, dict):
        return {
            "ok": False,
            "violations": [
                {"rule": "not-object", "detail": "claim record is not a JSON object"}
            ],
        }

    for field in REQUIRED_FIELDS:
        if field not in record:
            violations.append(
                {
                    "rule": f"missing-{field}",
                    "detail": f"required field {field} is absent",
                }
            )
            continue
        value = record[field]
        if field in {"source_probe", "verifier_probe"}:
            if not _probe_ok(value):
                violations.append(
                    {
                        "rule": f"missing-{field}",
                        "detail": f"{field} is empty or undeclared",
                    }
                )
        elif field == "source_lineage":
            if not _lineage_ok(value):
                violations.append(
                    {
                        "rule": "missing-source_lineage",
                        "detail": "source_lineage is empty",
                    }
                )
        elif field == "verdict":
            if _is_blank_string(value) or value is None:
                violations.append(
                    {
                        "rule": "missing-verdict",
                        "detail": "verdict is empty",
                    }
                )
            elif not isinstance(value, str) or value.strip() not in VERDICTS:
                violations.append(
                    {
                        "rule": "invalid-verdict",
                        "detail": f"verdict {value!r} is not in the closed set",
                    }
                )
        elif field == "confidence_band":
            if _is_blank_string(value) or value is None:
                violations.append(
                    {
                        "rule": "missing-confidence_band",
                        "detail": "confidence_band is empty",
                    }
                )
            elif not isinstance(value, str) or value.strip() not in BANDS:
                violations.append(
                    {
                        "rule": "invalid-confidence_band",
                        "detail": (
                            f"confidence_band {value!r} is not a Sherman-Kent band"
                        ),
                    }
                )
        elif isinstance(value, str):
            if not value.strip():
                violations.append(
                    {
                        "rule": f"missing-{field}",
                        "detail": f"{field} is blank",
                    }
                )
        elif value in (None, {}, []):
            violations.append(
                {
                    "rule": f"missing-{field}",
                    "detail": f"{field} is empty",
                }
            )

    src_fp = probe_fingerprint(record.get("source_probe"))
    ver_fp = probe_fingerprint(record.get("verifier_probe"))
    if src_fp is not None and ver_fp is not None and src_fp == ver_fp:
        violations.append(
            {
                "rule": "same-probe-rerun",
                "detail": (
                    "verifier_probe fingerprint is byte-identical to "
                    "source_probe; that is one signal, not two"
                ),
            }
        )

    return {"ok": not violations, "violations": violations}


def mutate_missing(field: str) -> dict[str, Any]:
    rec = golden_claim()
    rec.pop(field, None)
    return rec


def mutate_blank(field: str) -> dict[str, Any]:
    rec = golden_claim()
    rec[field] = "   " if field != "source_lineage" else {}
    if field in {"source_probe", "verifier_probe"}:
        rec[field] = {"tool": "", "engine": "", "shell": "", "field": ""}
    return rec


def both_states() -> dict[str, Any]:
    good = validate_claim(golden_claim())
    missing = validate_claim(mutate_missing("settling_experiment"))
    blank = validate_claim(mutate_blank("settling_experiment"))
    missing_rules = {row["rule"] for row in missing["violations"]}
    blank_rules = {row["rule"] for row in blank["violations"]}
    return {
        "good_ok": good["ok"],
        "good_violations": good["violations"],
        "missing_ok": missing["ok"],
        "missing_rules": sorted(missing_rules),
        "blank_ok": blank["ok"],
        "blank_rules": sorted(blank_rules),
        "control_pass": (
            good["ok"] is True
            and missing["ok"] is False
            and "missing-settling_experiment" in missing_rules
            and blank["ok"] is False
            and "missing-settling_experiment" in blank_rules
        ),
    }


def negatives_per_rule() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for field in REQUIRED_FIELDS:
        rec = mutate_missing(field)
        result = validate_claim(rec)
        rules = {row["rule"] for row in result["violations"]}
        expect = f"missing-{field}"
        rows.append(
            {
                "rule": expect,
                "mutant": f"absent-{field}",
                "ok": result["ok"],
                "fired": expect in rules,
                "rules": sorted(rules),
            }
        )
        rec2 = mutate_blank(field)
        result2 = validate_claim(rec2)
        rules2 = {row["rule"] for row in result2["violations"]}
        rows.append(
            {
                "rule": expect,
                "mutant": f"blank-{field}",
                "ok": result2["ok"],
                "fired": expect in rules2,
                "rules": sorted(rules2),
            }
        )

    bad_verdict = golden_claim()
    bad_verdict["verdict"] = "TRUE"
    r = validate_claim(bad_verdict)
    rules = {row["rule"] for row in r["violations"]}
    rows.append(
        {
            "rule": "invalid-verdict",
            "mutant": "verdict-TRUE",
            "ok": r["ok"],
            "fired": "invalid-verdict" in rules,
            "rules": sorted(rules),
        }
    )

    bad_band = golden_claim()
    bad_band["confidence_band"] = "HIGH"
    r = validate_claim(bad_band)
    rules = {row["rule"] for row in r["violations"]}
    rows.append(
        {
            "rule": "invalid-confidence_band",
            "mutant": "band-HIGH",
            "ok": r["ok"],
            "fired": "invalid-confidence_band" in rules,
            "rules": sorted(rules),
        }
    )

    same = golden_claim()
    same["verifier_probe"] = json.loads(json.dumps(same["source_probe"]))
    r = validate_claim(same)
    rules = {row["rule"] for row in r["violations"]}
    rows.append(
        {
            "rule": "same-probe-rerun",
            "mutant": "identical-fingerprints",
            "ok": r["ok"],
            "fired": "same-probe-rerun" in rules,
            "rules": sorted(rules),
        }
    )
    return rows


def extract_records(doc: Any) -> list[Any]:
    if isinstance(doc, list):
        return list(doc)
    if not isinstance(doc, dict):
        return []
    for key in CLAIM_LIST_KEYS:
        value = doc.get(key)
        if isinstance(value, list):
            return list(value)
    if any(k in doc for k in ("id", "claim_id", "canonical_mechanism")):
        return [doc]
    return []


def census_registry(repo: Path | None = None) -> dict[str, Any]:
    root = repo or REPO
    path = root / REGISTRY_REL
    per_field = {
        field: {
            "missing": 0,
            "present": 0,
            "absent_key": 0,
            "empty": 0,
        }
        for field in REQUIRED_FIELDS
    }
    base: dict[str, Any] = {
        "path": REGISTRY_REL,
        "present": path.is_file(),
        "parseable": False,
        "record_count": 0,
        "schema_valid_count": 0,
        "schema_invalid_count": 0,
        "non_object_count": 0,
        "vacuous_universal_refused": False,
        "every_record_complete": False,
        "answer": "NO",
        "reason": "",
        "per_field_missing": per_field,
    }
    if not path.is_file():
        base["vacuous_universal_refused"] = True
        base["reason"] = (
            "command-center/CLAIM-REGISTRY.json is absent; refusing the "
            "vacuous reading that every (zero) record carries every field"
        )
        return base
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        base["vacuous_universal_refused"] = True
        base["reason"] = f"registry unparseable: {type(exc).__name__}"
        return base

    base["parseable"] = True
    records = extract_records(doc)
    base["record_count"] = len(records)
    if not records:
        base["vacuous_universal_refused"] = True
        base["reason"] = (
            "registry parsed but contained zero claim records; refusing "
            "vacuous universal completeness"
        )
        return base

    complete = 0
    for rec in records:
        if not isinstance(rec, dict):
            base["non_object_count"] += 1
            base["schema_invalid_count"] += 1
            for field in REQUIRED_FIELDS:
                per_field[field]["missing"] += 1
                per_field[field]["absent_key"] += 1
            continue
        result = validate_claim(rec)
        if result["ok"] and all(field_present(rec, f) for f in REQUIRED_FIELDS):
            complete += 1
            base["schema_valid_count"] += 1
        else:
            base["schema_invalid_count"] += 1
        for field in REQUIRED_FIELDS:
            if field_present(rec, field):
                per_field[field]["present"] += 1
            else:
                per_field[field]["missing"] += 1
                keys = ALIASES[field]
                if not any(k in rec for k in keys):
                    per_field[field]["absent_key"] += 1
                else:
                    per_field[field]["empty"] += 1

    all_complete = complete == len(records) and base["schema_invalid_count"] == 0
    base["every_record_complete"] = all_complete
    if all_complete:
        base["answer"] = "YES"
        base["reason"] = (
            f"all {len(records)} registry records carry the eight fields "
            "and pass the contract"
        )
    else:
        base["answer"] = "NO"
        missing_summary = {
            field: per_field[field]["missing"]
            for field in REQUIRED_FIELDS
            if per_field[field]["missing"]
        }
        base["reason"] = (
            f"{base['schema_valid_count']}/{len(records)} records pass; "
            f"per-field missing={missing_summary}"
        )
    return base


def schema_required_fields(repo: Path | None = None) -> list[str]:
    """Top-level required[] on the catalog-declared file (often a $ref shim)."""
    root = repo or REPO
    doc = json.loads((root / SCHEMA_REL).read_text(encoding="utf-8"))
    req = doc.get("required") or []
    return [str(x) for x in req]


def load_schema(repo: Path | None = None) -> dict[str, Any]:
    root = repo or REPO
    return json.loads((root / SCHEMA_REL).read_text(encoding="utf-8"))


def load_contract_schema(repo: Path | None = None) -> dict[str, Any]:
    root = repo or REPO
    return json.loads((root / CONTRACT_SCHEMA_REL).read_text(encoding="utf-8"))


def contract_schema_required_fields(repo: Path | None = None) -> list[str]:
    doc = load_contract_schema(repo)
    req = doc.get("required") or []
    return [str(x) for x in req]


def catalog_schema_is_shim(repo: Path | None = None) -> bool:
    doc = load_schema(repo)
    return bool(doc.get("$ref")) and not doc.get("required")


def payload(doc: Any) -> dict[str, Any]:
    """Domain census lives on the receipt or under report/extensions."""
    if not isinstance(doc, dict):
        return {}
    for key in ("report", "extensions"):
        inner = doc.get(key)
        if isinstance(inner, dict) and (
            "registry_census" in inner or "claims" in inner
        ):
            return inner
    return doc
