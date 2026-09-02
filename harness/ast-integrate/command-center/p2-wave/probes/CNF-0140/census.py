"""Exhaustive P0/P1 confirmation census (CNF-0140).

Coverage proof: every P0/P1 claim is listed against a confirmation record
id or an explicit NOT-CHECKED. Sampling may apply only to lower severity.
A percentage without the id list is not a census.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

EXHAUSTIVE = frozenset({"P0", "P1"})
CANONICAL_RECORDS_REL = "command-center/confirmation/records"
LIVE_REGISTRY_REL = "command-center/CLAIM-REGISTRY.json"
LIVE_REGRADE_REL = "command-center/receipts/CNF-0142.json"
LIVE_FRAME_REL = "command-center/receipts/CNF-0137.json"
RECORD_DIR_CANDIDATES = (
    CANONICAL_RECORDS_REL,
    "command-center/confirmation/B09",
    "command-center/confirmation/b09",
    "command-center/confirmation/records/B09",
)


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def normalize_severity(raw: Any) -> str | None:
    if raw is None:
        return None
    text = str(raw).strip().upper().replace(" ", "")
    if not text:
        return None
    if text in EXHAUSTIVE or text in {"P2", "P3", "P4", "P5"}:
        return text
    if text in {"0", "SEV0", "CRITICAL"}:
        return "P0"
    if text in {"1", "SEV1", "HIGH"}:
        return "P1"
    if text.startswith("P") and len(text) >= 2 and text[1].isdigit():
        return "P" + text[1]
    return text if text.startswith("P") else None


def claim_id_of(row: dict[str, Any]) -> str | None:
    for key in ("id", "claim_id", "claimId"):
        val = row.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    return None


def record_claim_id(row: dict[str, Any]) -> str | None:
    """Claim the record confirms. Never the record's own `id`."""
    for key in ("claim_id", "claimId", "claim"):
        val = row.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    return None


def _as_claim_list(doc: Any) -> list[dict[str, Any]]:
    if isinstance(doc, list):
        return [x for x in doc if isinstance(x, dict)]
    if not isinstance(doc, dict):
        return []
    for key in ("claims", "records", "items", "entries"):
        block = doc.get(key)
        if isinstance(block, list):
            return [x for x in block if isinstance(x, dict)]
    out: list[dict[str, Any]] = []
    for key, val in doc.items():
        if key.startswith("_") or key in {"schema_version", "meta"}:
            continue
        if isinstance(val, dict) and (val.get("severity") or val.get("id") or val.get("text")):
            row = dict(val)
            row.setdefault("id", str(key))
            out.append(row)
    return out


def load_registry(path: Path) -> dict[str, Any]:
    meta = {
        "path": str(path),
        "present": path.is_file() and path.stat().st_size > 0,
        "parse_error": None,
        "claims": [],
        "ungraded_claim_ids": [],
    }
    if not meta["present"]:
        return meta
    try:
        doc = _read_json(path)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        meta["parse_error"] = f"{type(exc).__name__}:{exc}"
        return meta
    claims = []
    ungraded = []
    for row in _as_claim_list(doc):
        cid = claim_id_of(row)
        if not cid:
            continue
        sev = normalize_severity(row.get("severity") or row.get("severity_label") or row.get("grade"))
        item = {
            "id": cid,
            "severity": sev,
            "raw": row,
        }
        claims.append(item)
        if sev is None:
            ungraded.append(cid)
    meta["claims"] = claims
    meta["ungraded_claim_ids"] = ungraded
    return meta


def load_regrades(path: Path | None) -> dict[str, str]:
    """claim_id -> revised severity. Missing file is an empty overlay."""
    out: dict[str, str] = {}
    if path is None or not path.is_file() or path.stat().st_size <= 0:
        return out
    try:
        doc = _read_json(path)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return out
    rows: list[Any] = []
    if isinstance(doc, dict):
        for key in ("regrades", "under_graded", "under_grades", "reinjections", "items"):
            block = doc.get(key)
            if isinstance(block, list):
                rows.extend(block)
        census_inj = doc.get("census_reinjections")
        if isinstance(census_inj, list):
            rows.extend(census_inj)
    elif isinstance(doc, list):
        rows = doc
    for row in rows:
        if not isinstance(row, dict):
            continue
        cid = row.get("claim_id") or row.get("id")
        revised = normalize_severity(
            row.get("revised_severity")
            or row.get("new_severity")
            or row.get("effective_severity")
            or row.get("to")
        )
        if isinstance(cid, str) and cid.strip() and revised:
            out[cid.strip()] = revised
    return out


def _record_id_of(doc: dict[str, Any], stem: str) -> str:
    for key in ("id", "record_id", "confirmation_id"):
        val = doc.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    return stem


def load_records(records_dir: Path) -> dict[str, Any]:
    listing: list[str] = []
    by_id: dict[str, dict[str, Any]] = {}
    by_claim: dict[str, list[str]] = {}
    unparseable: list[str] = []
    present = records_dir.is_dir()
    if present:
        files = sorted(p for p in records_dir.iterdir() if p.is_file() and p.suffix.lower() == ".json")
        listing = [p.name for p in files]
        for path in files:
            try:
                doc = _read_json(path)
            except (OSError, UnicodeDecodeError, json.JSONDecodeError):
                unparseable.append(path.name)
                continue
            if not isinstance(doc, dict):
                unparseable.append(path.name)
                continue
            rid = _record_id_of(doc, path.stem)
            rec = {
                "record_id": rid,
                "path": str(path),
                "name": path.name,
                "doc": doc,
                "claim_id": record_claim_id(doc),
                "verdict": str(doc.get("verdict") or "") or None,
            }
            by_id[rid] = rec
            if rec["claim_id"]:
                by_claim.setdefault(rec["claim_id"], []).append(rid)
    return {
        "path": str(records_dir),
        "present": present,
        "listing": listing,
        "listing_count": len(listing),
        "by_id": by_id,
        "by_claim": by_claim,
        "unparseable": unparseable,
    }


def _pick_record(claim_id: str, records: dict[str, Any]) -> dict[str, Any] | None:
    ids = records["by_claim"].get(claim_id) or []
    if not ids:
        return None
    # Stable: lexicographic record id. Census is coverage, not latest-wins scoring.
    rid = sorted(ids)[0]
    return records["by_id"].get(rid)


def census(
    registry_path: Path,
    records_dir: Path,
    regrade_path: Path | None = None,
) -> dict[str, Any]:
    reg = load_registry(registry_path)
    recs = load_records(records_dir)
    regrades = load_regrades(regrade_path)
    ledger: list[dict[str, Any]] = []
    for claim in reg["claims"]:
        author = claim["severity"]
        revised = regrades.get(claim["id"])
        effective = revised or author
        if effective not in EXHAUSTIVE:
            continue
        match = _pick_record(claim["id"], recs)
        if match is None:
            # Deleted/missing record: gap. Unparseable files never enter by_claim.
            ledger.append(
                {
                    "claim_id": claim["id"],
                    "author_severity": author,
                    "effective_severity": effective,
                    "regraded": bool(revised),
                    "record_id": "NOT-CHECKED",
                    "record_path": None,
                    "record_parses": False,
                    "record_verdict": None,
                    "status": "GAP",
                    "gap_reason": "record-absent",
                }
            )
            continue
        ledger.append(
            {
                "claim_id": claim["id"],
                "author_severity": author,
                "effective_severity": effective,
                "regraded": bool(revised),
                "record_id": match["record_id"],
                "record_path": match["name"],
                "record_parses": True,
                "record_verdict": match["verdict"],
                "status": "RESOLVED",
                "gap_reason": None,
            }
        )
    ledger.sort(key=lambda r: r["claim_id"])
    n = len(ledger)
    resolved = sum(1 for r in ledger if r["status"] == "RESOLVED")
    gaps = n - resolved
    cited = [r["record_id"] for r in ledger if r["record_id"] != "NOT-CHECKED"]
    cited_ok = 0
    cited_fail: list[str] = []
    for rid in cited:
        rec = recs["by_id"].get(rid)
        if rec is None:
            cited_fail.append(rid)
            continue
        cited_ok += 1
    coverage = None if n == 0 else resolved / n
    gap_rate = None if n == 0 else gaps / n
    return {
        "registry_path": str(registry_path),
        "registry_present": bool(reg["present"]),
        "registry_parse_error": reg["parse_error"],
        "records_dir": str(records_dir),
        "records_dir_present": bool(recs["present"]),
        "regrade_path": str(regrade_path) if regrade_path is not None else None,
        "regrade_applied_count": sum(1 for r in ledger if r["regraded"]),
        "ungraded_claim_ids": list(reg["ungraded_claim_ids"]),
        "ledger": ledger,
        "counts": {
            "registry_claim_total": len(reg["claims"]),
            "registry_p0_p1_count": n,
            "ledger_row_count": n,
            "registry_p0_p1_equals_ledger": n == len(ledger),
            "records_directory_listing_count": recs["listing_count"],
            "records_unparseable_count": len(recs["unparseable"]),
            "resolved_count": resolved,
            "gap_count": gaps,
            "cited_record_count": len(cited),
            "cited_records_exist_and_parse": cited_ok,
            "cited_record_failures": cited_fail,
            "coverage_rate": coverage,
            "gap_rate": gap_rate,
            "coverage_rate_is_null_when_empty_population": n == 0,
        },
        "records_listing": recs["listing"],
        "records_unparseable": recs["unparseable"],
    }


def cross_registry_ok(result: dict[str, Any]) -> tuple[bool, str]:
    """Every cited record id exists on disk in the listing and parsed."""
    counts = result["counts"]
    fails = counts.get("cited_record_failures") or []
    if fails:
        return False, f"cited-missing:{fails[:8]}"
    if int(counts["cited_record_count"]) != int(counts["cited_records_exist_and_parse"]):
        return False, "cited-count-mismatch"
    listing = set(result.get("records_listing") or [])
    for row in result["ledger"]:
        if row["status"] != "RESOLVED":
            continue
        name = row.get("record_path")
        if not name or name not in listing:
            return False, f"resolved-not-in-listing:{row.get('claim_id')}"
        if row.get("record_parses") is not True:
            return False, f"resolved-unparsed:{row.get('claim_id')}"
    return True, "cited-ok"


def coverage_is_full_gaps(result: dict[str, Any]) -> bool:
    counts = result["counts"]
    n = int(counts["registry_p0_p1_count"])
    if n < 1:
        return False
    return (
        int(counts["resolved_count"]) == 0
        and int(counts["gap_count"]) == n
        and counts["coverage_rate"] == 0.0
        and counts["gap_rate"] == 1.0
    )


def refuses_vacuous_full_coverage(result: dict[str, Any]) -> bool:
    counts = result["counts"]
    if int(counts["registry_p0_p1_count"]) != 0:
        return True
    return counts["coverage_rate"] is None and counts["gap_rate"] is None


def question_verdict(result: dict[str, Any]) -> str:
    """Answer the catalog question from the census, never from a percentage alone."""
    if not result["registry_present"] or result.get("registry_parse_error"):
        return "NOT-CHECKED"
    counts = result["counts"]
    n = int(counts["registry_p0_p1_count"])
    if n == 0:
        # Empty population is not "every claim confirmed".
        return "NOT-CHECKED"
    if result.get("ungraded_claim_ids"):
        if int(counts["gap_count"]) == 0:
            return "PARTIAL"
    if int(counts["gap_count"]) == 0 and counts["coverage_rate"] == 1.0:
        return "CONFIRMED"
    return "REFUTED"


def discover_records_dir(repo: Path) -> Path:
    for rel in RECORD_DIR_CANDIDATES:
        path = repo / rel
        if path.is_dir():
            return path
    return repo / CANONICAL_RECORDS_REL


def live_census(repo: Path) -> dict[str, Any]:
    return census(
        repo / LIVE_REGISTRY_REL,
        discover_records_dir(repo),
        repo / LIVE_REGRADE_REL,
    )


def load_sampling_leaks(repo: Path, result: dict[str, Any]) -> list[str]:
    """P0/P1 claim ids the sampling frame marks as sample-only, if the frame exists."""
    path = repo / LIVE_FRAME_REL
    if not path.is_file():
        return []
    try:
        doc = _read_json(path)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return []
    exhaustive_ids = {row["claim_id"] for row in result["ledger"]}
    leaks: list[str] = []
    rows: list[Any] = []
    if isinstance(doc, dict):
        for key in ("claims", "frame", "rows", "members"):
            block = doc.get(key)
            if isinstance(block, list):
                rows = block
                break
        strata = doc.get("strata")
        if isinstance(strata, list):
            for stratum in strata:
                if isinstance(stratum, dict) and isinstance(stratum.get("claim_ids"), list):
                    sampling = str(stratum.get("sampling") or stratum.get("mode") or "").lower()
                    if sampling in {"sample", "sampled", "lower-severity", "stratified-sample"}:
                        for cid in stratum["claim_ids"]:
                            if cid in exhaustive_ids:
                                leaks.append(str(cid))
    for row in rows:
        if not isinstance(row, dict):
            continue
        cid = row.get("claim_id") or row.get("id")
        mode = str(row.get("sampling") or row.get("mode") or row.get("treatment") or "").lower()
        if cid in exhaustive_ids and mode in {"sample", "sampled", "lower-severity"}:
            leaks.append(str(cid))
    return sorted(set(leaks))
