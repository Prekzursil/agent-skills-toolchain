#!/usr/bin/env python3
"""Five-source ID differ for CNF-0169.

Membership is computed, not read. Ten unordered pairs (C(5,2)=10), each with
both directed differences, counts, sample ids, and a digest of the full set.

Empty/absent sources are empty membership — not vacuous agreement with a
populated peer.
"""
from __future__ import annotations

import hashlib
import json
import re
from itertools import combinations
from pathlib import Path
from typing import Any, Iterable

UID_RE = re.compile(r"^[A-Z]{2,5}-\d{4}$")
SOURCES = ("claims", "tests", "artifacts", "catalog", "receipts")
PAIRS = tuple(combinations(SOURCES, 2))
SAMPLE = 12
SELF_UNIT = "CNF-0169"
REPO_FROM_HERE = Path(__file__).resolve().parents[3]

CLAIM_PATH = "command-center/CLAIM-REGISTRY.json"
TEST_PATH = "command-center/TEST-REGISTRY.json"
MANIFEST_PATH = "command-center/ARTIFACT-MANIFEST.json"
CATALOG_PATH = "command-center/WORK-UNIT-CATALOG.json"
RECEIPTS_DIR = "command-center/receipts"


def uid(value: Any) -> str | None:
    text = str(value or "").strip()
    if UID_RE.match(text):
        return text
    return None


def digest_ids(ids: Iterable[str]) -> str:
    blob = "\n".join(sorted(ids)).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def directed(left: set[str], right: set[str], *, keep_ids: bool = False) -> dict[str, Any]:
    ids = sorted(left - right)
    row: dict[str, Any] = {
        "count": len(ids),
        "sample_ids": ids[:SAMPLE],
        "digest": digest_ids(ids),
    }
    if keep_ids:
        row["ids"] = ids
    return row


def ten_pairwise(
    sets: dict[str, set[str]], *, keep_ids: bool = False
) -> list[dict[str, Any]]:
    missing = [name for name in SOURCES if name not in sets]
    if missing:
        raise ValueError(f"missing sources: {missing}")
    rows: list[dict[str, Any]] = []
    for left_name, right_name in PAIRS:
        left = sets[left_name]
        right = sets[right_name]
        lmr = directed(left, right, keep_ids=keep_ids)
        rml = directed(right, left, keep_ids=keep_ids)
        rows.append(
            {
                "pair": f"{left_name}|{right_name}",
                "left": left_name,
                "right": right_name,
                "left_minus_right": lmr,
                "right_minus_left": rml,
                "symmetric_count": lmr["count"] + rml["count"],
            }
        )
    if len(rows) != 10:
        raise RuntimeError(f"expected 10 pairwise rows, got {len(rows)}")
    return rows


def disagreeing_ids(pairs: list[dict[str, Any]]) -> set[str]:
    out: set[str] = set()
    for row in pairs:
        for side in ("left_minus_right", "right_minus_left"):
            payload = row.get(side) or {}
            if "ids" in payload:
                out.update(payload["ids"])
            else:
                out.update(payload.get("sample_ids") or [])
    return out


def colliding_across(left: Iterable[str], right: Iterable[str]) -> list[str]:
    """Duplicate-catalog: an id present in two same-kind registry slices."""
    return sorted(set(left) & set(right))


def duplicates_in_list(ids: list[str]) -> list[str]:
    seen: dict[str, int] = {}
    for item in ids:
        seen[item] = seen.get(item, 0) + 1
    return sorted(k for k, n in seen.items() if n > 1)


def load_json(path: Path) -> tuple[Any, str]:
    if not path.is_file():
        return None, "absent"
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        return None, f"unreadable:{type(exc).__name__}"
    if not raw.strip():
        return None, "empty"
    try:
        return json.loads(raw), "ok"
    except json.JSONDecodeError:
        return None, "unparseable"


def _iter_records(data: Any, keys: tuple[str, ...]) -> list[Any]:
    if data is None:
        return []
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in keys:
            val = data.get(key)
            if isinstance(val, list):
                return val
    return []


def _record_id(item: Any, keys: tuple[str, ...]) -> str | None:
    if isinstance(item, str):
        return uid(item)
    if not isinstance(item, dict):
        return None
    for key in keys:
        hit = uid(item.get(key))
        if hit:
            return hit
    return None


def _test_ids_from_claim(item: dict[str, Any]) -> list[str]:
    found: list[str] = []
    for key in ("test_id", "test", "settling_test"):
        hit = uid(item.get(key))
        if hit:
            found.append(hit)
    for key in ("test_ids", "tests", "cited_tests", "tests_required"):
        val = item.get(key)
        if isinstance(val, str):
            hit = uid(val)
            if hit:
                found.append(hit)
        elif isinstance(val, list):
            for entry in val:
                if isinstance(entry, str):
                    hit = uid(entry)
                    if hit:
                        found.append(hit)
                elif isinstance(entry, dict):
                    hit = _record_id(entry, ("id", "test_id", "unit_id"))
                    if hit:
                        found.append(hit)
    return found


def extract_claim_ids(data: Any) -> tuple[list[str], list[str], list[dict[str, str]]]:
    records = _iter_records(data, ("claims", "items", "entries"))
    ids: list[str] = []
    cites: list[dict[str, str]] = []
    for item in records:
        cid = _record_id(item, ("id", "claim_id", "unit_id"))
        if cid:
            ids.append(cid)
        if isinstance(item, dict):
            for tid in _test_ids_from_claim(item):
                cites.append({"claim_id": cid or "", "test_id": tid})
    return ids, duplicates_in_list(ids), cites


def extract_test_ids(data: Any) -> tuple[list[str], list[str]]:
    records = _iter_records(data, ("tests", "items", "entries"))
    ids: list[str] = []
    for item in records:
        tid = _record_id(item, ("id", "test_id", "unit_id", "name"))
        if tid:
            ids.append(tid)
    return ids, duplicates_in_list(ids)


def extract_catalog_ids(data: Any) -> tuple[list[str], list[str]]:
    records = _iter_records(data, ("work_units", "items", "units"))
    ids: list[str] = []
    for item in records:
        cid = _record_id(item, ("id", "unit_id"))
        if cid:
            ids.append(cid)
    return ids, duplicates_in_list(ids)


def extract_manifest_ids(data: Any) -> tuple[list[str], list[str]]:
    records = _iter_records(data, ("artifacts", "items", "entries"))
    ids: list[str] = []
    for item in records:
        if not isinstance(item, dict):
            hit = uid(item)
            if hit:
                ids.append(hit)
            continue
        hit = uid(item.get("unit_id") or item.get("id"))
        if hit:
            ids.append(hit)
            continue
        path = str(item.get("path") or "").replace("\\", "/")
        stem = Path(path).stem
        hit = uid(stem)
        if hit:
            ids.append(hit)
    return ids, duplicates_in_list(ids)


def manifest_missing_artifacts(data: Any, repo: Path) -> list[dict[str, Any]]:
    records = _iter_records(data, ("artifacts", "items", "entries"))
    missing: list[dict[str, Any]] = []
    for item in records:
        if not isinstance(item, dict):
            continue
        rel = str(item.get("path") or "").replace("\\", "/")
        if not rel:
            continue
        path = repo / rel
        exists = path.is_file()
        size = path.stat().st_size if exists else 0
        if not exists or size <= 0:
            missing.append(
                {
                    "path": rel,
                    "exists": exists,
                    "bytes": size,
                    "declared_present": item.get("present"),
                }
            )
    return missing


def extract_receipt_ids(receipts: Path, extra: Iterable[str] = ()) -> tuple[list[str], list[str]]:
    ids: list[str] = []
    if receipts.is_dir():
        for path in sorted(receipts.glob("*.json")):
            hit = uid(path.stem)
            if hit:
                ids.append(hit)
                continue
            data, status = load_json(path)
            if status != "ok" or not isinstance(data, dict):
                continue
            hit = uid(data.get("unit_id") or data.get("id"))
            if hit:
                ids.append(hit)
    raw_dups = duplicates_in_list(ids)
    have = set(ids)
    for stem in extra:
        hit = uid(stem)
        if hit and hit not in have:
            ids.append(hit)
            have.add(hit)
    return ids, raw_dups


def source_sets(extracted: dict[str, list[str]]) -> dict[str, set[str]]:
    return {name: set(extracted[name]) for name in SOURCES}


def dangling_test_cites(
    cites: list[dict[str, str]], test_ids: set[str]
) -> list[dict[str, str]]:
    return [c for c in cites if c.get("test_id") and c["test_id"] not in test_ids]


def load_live(repo: Path | None = None, *, extra_receipts: Iterable[str] = ()) -> dict[str, Any]:
    repo = repo or REPO_FROM_HERE
    claim_data, claim_st = load_json(repo / CLAIM_PATH)
    test_data, test_st = load_json(repo / TEST_PATH)
    man_data, man_st = load_json(repo / MANIFEST_PATH)
    cat_data, cat_st = load_json(repo / CATALOG_PATH)

    claim_ids, claim_dups, cites = extract_claim_ids(claim_data)
    test_ids, test_dups = extract_test_ids(test_data)
    art_ids, art_dups = extract_manifest_ids(man_data)
    cat_ids, cat_dups = extract_catalog_ids(cat_data)
    rec_ids, rec_dups = extract_receipt_ids(repo / RECEIPTS_DIR, extra_receipts)

    extracted = {
        "claims": claim_ids,
        "tests": test_ids,
        "artifacts": art_ids,
        "catalog": cat_ids,
        "receipts": rec_ids,
    }
    sets = source_sets(extracted)
    pairs = ten_pairwise(sets)
    test_set = sets["tests"]
    dangling = dangling_test_cites(cites, test_set)
    missing = manifest_missing_artifacts(man_data, repo) if man_st == "ok" else []
    intersection = set.intersection(*[sets[n] for n in SOURCES]) if sets else set()
    sources = {
        "claims": {
            "name": "claims",
            "path": CLAIM_PATH,
            "present": claim_st == "ok",
            "status": claim_st,
            "id_count": len(sets["claims"]),
            "duplicate_ids": claim_dups,
        },
        "tests": {
            "name": "tests",
            "path": TEST_PATH,
            "present": test_st == "ok",
            "status": test_st,
            "id_count": len(sets["tests"]),
            "duplicate_ids": test_dups,
        },
        "artifacts": {
            "name": "artifacts",
            "path": MANIFEST_PATH,
            "present": man_st == "ok",
            "status": man_st,
            "id_count": len(sets["artifacts"]),
            "duplicate_ids": art_dups,
        },
        "catalog": {
            "name": "catalog",
            "path": CATALOG_PATH,
            "present": cat_st == "ok",
            "status": cat_st,
            "id_count": len(sets["catalog"]),
            "duplicate_ids": cat_dups,
        },
        "receipts": {
            "name": "receipts",
            "path": RECEIPTS_DIR,
            "present": (repo / RECEIPTS_DIR).is_dir(),
            "status": "ok" if (repo / RECEIPTS_DIR).is_dir() else "absent",
            "id_count": len(sets["receipts"]),
            "duplicate_ids": rec_dups,
        },
    }
    all_present = all(sources[n]["present"] for n in SOURCES)
    agree = all_present and all(row["symmetric_count"] == 0 for row in pairs)
    return {
        "sources": sources,
        "sets": {k: sorted(v) for k, v in sets.items()},
        "pairwise_differences": pairs,
        "intersection_count": len(intersection),
        "intersection_sample": sorted(intersection)[:SAMPLE],
        "dangling_test_cites": dangling[:50],
        "dangling_test_cite_count": len(dangling),
        "manifest_missing_artifacts": missing[:50],
        "manifest_missing_artifact_count": len(missing),
        "all_sources_present": all_present,
        "five_way_agree": agree,
        "empty_treated_as_empty_membership": True,
    }


def pair_row(pairs: list[dict[str, Any]], left: str, right: str) -> dict[str, Any]:
    key = f"{left}|{right}"
    alt = f"{right}|{left}"
    for row in pairs:
        if row.get("pair") in {key, alt}:
            return row
    raise KeyError(key)
