#!/usr/bin/env python3
"""Census of the 63 Phase-3 lens artifacts (ARC-0003 .. ARC-0065).

Authorship is READ from each artifact's provenance/produced_by field when the
file exists, then CROSS-CHECKED against the catalog assignment. Absence is a
measured GAP, never filled in by narration.
"""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
CATALOG = REPO / "command-center" / "WORK-UNIT-CATALOG.json"
LENS_LO = 3
LENS_HI = 65


def norm(value) -> str:
    return str(value or "").strip().lower()


def load_catalog_units() -> list[dict]:
    data = json.loads(CATALOG.read_text(encoding="utf-8"))
    return [u for u in (data.get("work_units") or []) if isinstance(u, dict)]


def lens_units(catalog_units: list[dict] | None = None) -> list[dict]:
    units = catalog_units if catalog_units is not None else load_catalog_units()
    out = []
    for unit in units:
        uid = str(unit.get("id") or "")
        if not uid.startswith("ARC-"):
            continue
        try:
            n = int(uid.split("-")[1])
        except (IndexError, ValueError):
            continue
        if LENS_LO <= n <= LENS_HI:
            out.append(unit)
    out.sort(key=lambda u: u["id"])
    return out


def catalog_assignment(unit: dict) -> dict:
    asg = unit.get("assigned_model_vendor_role") or {}
    vendors = []
    v = asg.get("vendor")
    if v:
        vendors.append(str(v))
    models = []
    m = asg.get("model")
    if m:
        models.append(str(m))
    for co in asg.get("co_assignments") or []:
        if not isinstance(co, dict):
            continue
        if co.get("vendor"):
            vendors.append(str(co["vendor"]))
        if co.get("model"):
            models.append(str(co["model"]))
    seen_v, uniq_v = set(), []
    for item in vendors:
        key = norm(item)
        if key and key not in seen_v:
            seen_v.add(key)
            uniq_v.append(item)
    seen_m, uniq_m = set(), []
    for item in models:
        key = norm(item)
        if key and key not in seen_m:
            seen_m.add(key)
            uniq_m.append(item)
    return {
        "unit_id": unit.get("id"),
        "vendor": uniq_v[0] if uniq_v else None,
        "vendors": uniq_v,
        "model": uniq_m[0] if uniq_m else None,
        "models": uniq_m,
        "role": asg.get("role"),
    }


def extract_authorship(doc) -> dict:
    """Prefer explicit provenance; fall back to produced_by. Do not invent ids."""
    if not isinstance(doc, dict):
        return {
            "source_field": None,
            "author_id": None,
            "vendor": None,
            "model": None,
            "role": None,
            "raw": None,
        }
    prov = doc.get("provenance") if isinstance(doc.get("provenance"), dict) else {}
    produced = doc.get("produced_by") if isinstance(doc.get("produced_by"), dict) else {}
    if prov:
        src, blob = "provenance", {**produced, **prov}
    elif produced:
        src, blob = "produced_by", dict(produced)
    else:
        return {
            "source_field": None,
            "author_id": None,
            "vendor": None,
            "model": None,
            "role": None,
            "raw": None,
        }
    author_id = blob.get("author_id") or blob.get("judge_id") or blob.get("id")
    if author_id is not None:
        author_id = str(author_id)
    return {
        "source_field": src,
        "author_id": author_id,
        "vendor": blob.get("vendor"),
        "model": blob.get("model"),
        "role": blob.get("role"),
        "raw": blob,
    }


def assignment_provenance_mismatch(catalog: dict, authorship: dict) -> dict | None:
    if not authorship.get("source_field"):
        return None
    notes = []
    cv, av = norm(catalog.get("vendor")), norm(authorship.get("vendor"))
    if cv and av and cv != av:
        notes.append(f"vendor catalog={catalog.get('vendor')} disk={authorship.get('vendor')}")
    cm, am = norm(catalog.get("model")), norm(authorship.get("model"))
    if cm and am and cm != am:
        notes.append(f"model catalog={catalog.get('model')} disk={authorship.get('model')}")
    if not notes:
        return None
    return {"mismatch": True, "notes": notes}


def census_row(unit: dict) -> dict:
    rel = str(unit.get("output_path") or "").replace("\\", "/")
    path = REPO / rel if rel else None
    cat = catalog_assignment(unit)
    row = {
        "unit_id": unit.get("id"),
        "title": unit.get("title"),
        "path": rel,
        "present": False,
        "parseable": False,
        "bytes": 0,
        "catalog": cat,
        "authorship": {
            "source_field": None,
            "author_id": None,
            "vendor": None,
            "model": None,
            "role": None,
            "raw": None,
        },
        "provenance_gap": "ABSENT-FILE",
        "assignment_crosscheck": None,
    }
    if not rel or path is None or not path.is_file():
        return row
    raw = path.read_bytes()
    row["present"] = True
    row["bytes"] = len(raw)
    try:
        doc = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        row["provenance_gap"] = "UNPARSEABLE"
        return row
    row["parseable"] = True
    auth = extract_authorship(doc)
    row["authorship"] = auth
    if not auth.get("source_field"):
        row["provenance_gap"] = "PROVENANCE-ABSENT"
    else:
        row["provenance_gap"] = None
    row["assignment_crosscheck"] = assignment_provenance_mismatch(cat, auth)
    return row


def census() -> dict:
    units = lens_units()
    rows = [census_row(u) for u in units]
    present = [r for r in rows if r["present"]]
    gaps = [r for r in rows if r["provenance_gap"]]
    mismatches = [r for r in present if r.get("assignment_crosscheck")]
    return {
        "expected": 63,
        "enumerated": len(rows),
        "present": len(present),
        "absent": len(rows) - len(present),
        "provenance_gaps": len(gaps),
        "assignment_mismatches": len(mismatches),
        "rows": rows,
    }


def row_by_unit(report: dict, unit_id: str) -> dict | None:
    for row in report.get("rows") or []:
        if row.get("unit_id") == unit_id:
            return row
    return None


if __name__ == "__main__":
    report = census()
    print(
        f"enumerated={report['enumerated']} present={report['present']} "
        f"absent={report['absent']} provenance_gaps={report['provenance_gaps']} "
        f"mismatches={report['assignment_mismatches']}"
    )
    if report["enumerated"] != 63:
        raise SystemExit("FAILED:census expected 63 lens units")
    print("SUCCESS:ARC-0066-census")
