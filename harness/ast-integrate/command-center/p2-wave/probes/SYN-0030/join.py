#!/usr/bin/env python3
"""Four-way referential join: catalog, artifact, test, claim.

Join keys are ids and id-typed foreign keys. Titles are never keys.
Eight directed orphan counts, one per direction of four adjacent pairs:

  catalog <-> artifact
  catalog <-> test
  catalog <-> claim
  test    <-> claim
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable, Mapping

DIRECTION_ORDER = (
    "catalog_without_artifact",
    "artifact_without_catalog",
    "catalog_without_test",
    "test_without_catalog",
    "catalog_without_claim",
    "claim_without_catalog",
    "test_without_claim",
    "claim_without_test",
)

PAIR_OF = {
    "catalog_without_artifact": "catalog-artifact",
    "artifact_without_catalog": "catalog-artifact",
    "catalog_without_test": "catalog-test",
    "test_without_catalog": "catalog-test",
    "catalog_without_claim": "catalog-claim",
    "claim_without_catalog": "catalog-claim",
    "test_without_claim": "test-claim",
    "claim_without_test": "test-claim",
}

FROM_TO = {
    "catalog_without_artifact": ("catalog", "artifact"),
    "artifact_without_catalog": ("artifact", "catalog"),
    "catalog_without_test": ("catalog", "test"),
    "test_without_catalog": ("test", "catalog"),
    "catalog_without_claim": ("catalog", "claim"),
    "claim_without_catalog": ("claim", "catalog"),
    "test_without_claim": ("test", "claim"),
    "claim_without_test": ("claim", "test"),
}

LIVE_PATHS = {
    "catalog": "command-center/WORK-UNIT-CATALOG.json",
    "artifact": "command-center/ARTIFACT-MANIFEST.json",
    "test": "command-center/TEST-REGISTRY.json",
    "claim": "command-center/CLAIM-REGISTRY.json",
}

TITLE_KEYS = (
    "title",
    "name",
    "label",
    "headline",
    "claim_title",
    "unit_title",
    "test_title",
    "artifact_title",
)


def _as_id(value: Any) -> str:
    if value is None or isinstance(value, bool):
        return ""
    if isinstance(value, (int, float)):
        return str(value).strip()
    if isinstance(value, str):
        return value.strip()
    return ""


def _id_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [text for text in (_as_id(item) for item in value) if text]
    text = _as_id(value)
    return [text] if text else []


def _records(doc: Any, list_keys: tuple[str, ...]) -> list[dict[str, Any]]:
    if isinstance(doc, list):
        return [row for row in doc if isinstance(row, dict)]
    if not isinstance(doc, dict):
        return []
    for key in list_keys:
        raw = doc.get(key)
        if isinstance(raw, list):
            return [row for row in raw if isinstance(row, dict)]
    return []


def _record_id(row: Mapping[str, Any]) -> str:
    return _as_id(row.get("id"))


def _unit_fk(row: Mapping[str, Any]) -> str:
    for key in ("unit_id", "work_unit_id", "bound_unit_id"):
        text = _as_id(row.get(key))
        if text:
            return text
    return ""


def _claim_fks(row: Mapping[str, Any]) -> list[str]:
    for key in ("claim_ids", "claim_id", "bound_claim_ids"):
        ids = _id_list(row.get(key))
        if ids:
            return ids
    return []


def _orphan(left: Iterable[str], right: set[str]) -> list[str]:
    return sorted({item for item in left if item not in right})


def _direction(name: str, ids: list[str], denominator: int) -> dict[str, Any]:
    src, dst = FROM_TO[name]
    return {
        "direction": name,
        "pair": PAIR_OF[name],
        "from_registry": src,
        "to_registry": dst,
        "count": len(ids),
        "denominator": int(denominator),
        "ids": ids,
        "join_key": "id",
    }


def _walk_tests(doc: Any) -> list[tuple[str, str, list[str]]]:
    rows = []
    # Live TEST-REGISTRY.json stores identity-bearing rows under invariants[];
    # fixture corpora use tests[]. Prefer tests/entries/items when present.
    for row in _records(doc, ("tests", "entries", "items", "invariants")):
        rid = _record_id(row)
        if not rid:
            continue
        rows.append((rid, _unit_fk(row), _claim_fks(row)))
    return rows


def _walk_claims(doc: Any) -> list[tuple[str, str]]:
    rows = []
    for row in _records(doc, ("claims", "entries", "items")):
        rid = _record_id(row)
        if not rid:
            continue
        rows.append((rid, _unit_fk(row)))
    return rows


def _walk_artifacts(doc: Any) -> list[tuple[str, str]]:
    rows = []
    for row in _records(doc, ("artifacts", "entries", "items")):
        rid = _record_id(row)
        unit = _unit_fk(row)
        rows.append((rid, unit))
    return rows


def extract_catalog(doc: Any) -> dict[str, Any]:
    """Catalog side is work_units[].id — never title, never items[]."""
    rows = _records(doc, ("work_units",))
    ids: list[str] = []
    unkeyed = 0
    seen: set[str] = set()
    for row in rows:
        rid = _record_id(row)
        if not rid:
            unkeyed += 1
            continue
        if rid not in seen:
            ids.append(rid)
            seen.add(rid)
    return {
        "ids": ids,
        "id_set": set(ids),
        "record_count": len(rows),
        "unkeyed": unkeyed,
        "join_key": "work_units[].id",
    }


def join_registries(
    catalog_doc: Any,
    artifact_doc: Any,
    test_doc: Any,
    claim_doc: Any,
) -> dict[str, Any]:
    catalog = extract_catalog(catalog_doc)
    cat_ids: set[str] = catalog["id_set"]

    artifacts = _walk_artifacts(artifact_doc)
    tests = _walk_tests(test_doc)
    claims = _walk_claims(claim_doc)

    art_units = [unit for _rid, unit in artifacts if unit]
    test_units = [unit for _tid, unit, _cids in tests if unit]
    claim_ids_list = [cid for cid, _unit in claims]
    claim_id_set = set(claim_ids_list)
    claim_units = [unit for _cid, unit in claims if unit]
    test_claim_fks: set[str] = set()
    for _tid, _unit, cids in tests:
        test_claim_fks.update(cids)

    catalog_without_artifact = _orphan(catalog["ids"], set(art_units))
    artifact_without_catalog = sorted(
        {
            (rid or unit or "<anonymous-artifact>")
            for rid, unit in artifacts
            if (not unit) or (unit not in cat_ids)
        }
    )

    catalog_without_test = _orphan(catalog["ids"], set(test_units))
    test_without_catalog = sorted(
        {
            tid
            for tid, unit, _cids in tests
            if (not unit) or (unit not in cat_ids)
        }
    )

    catalog_without_claim = _orphan(catalog["ids"], set(claim_units))
    claim_without_catalog = sorted(
        {
            cid
            for cid, unit in claims
            if (not unit) or (unit not in cat_ids)
        }
    )

    test_without_claim = sorted(
        {
            tid
            for tid, _unit, cids in tests
            if (not cids) or (not any(cid in claim_id_set for cid in cids))
        }
    )
    claim_without_test = _orphan(claim_ids_list, test_claim_fks)

    denom = {
        "catalog": len(catalog["ids"]),
        "artifact": len(artifacts),
        "test": len(tests),
        "claim": len(claims),
    }
    payload = {
        "catalog_without_artifact": catalog_without_artifact,
        "artifact_without_catalog": artifact_without_catalog,
        "catalog_without_test": catalog_without_test,
        "test_without_catalog": test_without_catalog,
        "catalog_without_claim": catalog_without_claim,
        "claim_without_catalog": claim_without_catalog,
        "test_without_claim": test_without_claim,
        "claim_without_test": claim_without_test,
    }
    directions = [
        _direction(name, payload[name], denom[FROM_TO[name][0]])
        for name in DIRECTION_ORDER
    ]
    nonzero = [row["direction"] for row in directions if row["count"] > 0]
    return {
        "directed_counts": directions,
        "by_direction": {row["direction"]: row for row in directions},
        "nonzero_directions": nonzero,
        "all_eight_zero": not nonzero,
        "join_keys_are_ids": True,
        "title_keys_rejected": list(TITLE_KEYS),
        "extracts": {
            "catalog": {
                "id_count": denom["catalog"],
                "record_count": catalog["record_count"],
                "unkeyed": catalog["unkeyed"],
                "join_key": catalog["join_key"],
            },
            "artifact": {"record_count": denom["artifact"], "join_key": "artifacts[].unit_id"},
            "test": {"record_count": denom["test"], "join_key": "tests[].id"},
            "claim": {"record_count": denom["claim"], "join_key": "claims[].id"},
        },
    }


def counts_map(result: Mapping[str, Any]) -> dict[str, int]:
    return {
        row["direction"]: int(row["count"])
        for row in result.get("directed_counts") or []
    }


def title_join_registries(
    catalog_doc: Any,
    artifact_doc: Any,
    test_doc: Any,
    claim_doc: Any,
) -> dict[str, list[str]]:
    """Negative control: join on title. Must disagree with the id join on collisions."""

    def titles(doc: Any, keys: tuple[str, ...]) -> set[str]:
        found: set[str] = set()
        for row in _records(doc, keys):
            for tk in TITLE_KEYS:
                text = _as_id(row.get(tk))
                if text:
                    found.add(text)
                    break
        return found

    cat_t = titles(catalog_doc, ("work_units",))
    art_t = titles(artifact_doc, ("artifacts", "entries", "items"))
    test_t = titles(test_doc, ("tests", "entries", "items"))
    claim_t = titles(claim_doc, ("claims", "entries", "items"))
    return {
        "catalog_without_artifact": sorted(cat_t - art_t),
        "artifact_without_catalog": sorted(art_t - cat_t),
        "catalog_without_test": sorted(cat_t - test_t),
        "test_without_catalog": sorted(test_t - cat_t),
        "catalog_without_claim": sorted(cat_t - claim_t),
        "claim_without_catalog": sorted(claim_t - cat_t),
        "test_without_claim": sorted(test_t - claim_t),
        "claim_without_test": sorted(claim_t - test_t),
    }


def load_json(path: Path) -> tuple[Any, dict[str, Any]]:
    status = {
        "path": path.as_posix(),
        "present": path.is_file(),
        "bytes": path.stat().st_size if path.is_file() else 0,
        "parseable": False,
        "error": None,
        "treated_as": None,
    }
    if not path.is_file():
        status["error"] = "absent"
        status["treated_as"] = "empty"
        return {}, status
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        status["error"] = f"{type(exc).__name__}: {exc}"
        status["treated_as"] = "empty"
        return {}, status
    status["parseable"] = True
    return doc, status


def load_live(repo: Path) -> dict[str, Any]:
    docs: dict[str, Any] = {}
    statuses: dict[str, Any] = {}
    for kind, rel in LIVE_PATHS.items():
        doc, status = load_json(repo / rel)
        status["path"] = rel
        docs[kind] = doc
        statuses[kind] = status
    result = join_registries(docs["catalog"], docs["artifact"], docs["test"], docs["claim"])
    result["registry_status"] = statuses
    cc14 = repo / "command-center/receipts/CC-0014.json"
    result["cc0014_binding"] = {
        "path": "command-center/receipts/CC-0014.json",
        "present": cc14.is_file(),
        "used": False,
        "reason": "CC-0014 receipt not shipped; join uses registry id fields only",
    }
    return result
