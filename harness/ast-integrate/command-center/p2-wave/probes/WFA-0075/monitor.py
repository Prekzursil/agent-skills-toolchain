#!/usr/bin/env python3
"""Disposition-drift monitor for WFA-0075.

Compares two candidate-registry versions. A classification (disposition)
change is FAIL unless BOTH are present:

  1. at least one named evidence field actually changed
  2. a non-empty written reason on the v2 record

The monitor reports the evidence field *names* that changed, not a boolean
"something moved". Id aliases from the migration map are applied before
comparison, so a rename is not a disposition change.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

KIND_SILENT = "SILENT_DRIFT"
KIND_DOCUMENTED = "DOCUMENTED"
KIND_RENAME_ONLY = "RENAME_ONLY"
KIND_UNCHANGED = "UNCHANGED"
KIND_ADDED = "ADDED"
KIND_REMOVED = "REMOVED"

REASON_KEYS = (
    "disposition_change_reason",
    "change_reason",
    "reason",
)


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def alias_pairs(migration: dict[str, Any] | None) -> list[tuple[str, str]]:
    if not isinstance(migration, dict):
        return []
    pairs: list[tuple[str, str]] = []
    aliases = migration.get("aliases")
    if isinstance(aliases, list):
        for row in aliases:
            if not isinstance(row, dict):
                continue
            src = str(row.get("from") or row.get("old") or "").strip()
            dst = str(row.get("to") or row.get("new") or "").strip()
            if src and dst:
                pairs.append((src, dst))
    raw_map = migration.get("map")
    if isinstance(raw_map, dict):
        for src, dst in raw_map.items():
            s, d = str(src).strip(), str(dst).strip()
            if s and d:
                pairs.append((s, d))
    return pairs


def resolve_id(cid: str, migration: dict[str, Any] | None) -> str:
    """Follow alias rows transitively. Cycles stop on the last seen id."""
    fwd = {src: dst for src, dst in alias_pairs(migration)}
    seen: set[str] = set()
    cur = cid
    while cur in fwd and cur not in seen:
        seen.add(cur)
        cur = fwd[cur]
    return cur


def candidates_of(doc: Any) -> list[dict[str, Any]]:
    if isinstance(doc, dict):
        raw = doc.get("candidates")
        if isinstance(raw, list):
            return [c for c in raw if isinstance(c, dict) and c.get("id")]
    if isinstance(doc, list):
        return [c for c in doc if isinstance(c, dict) and c.get("id")]
    return []


def classification_of(rec: dict[str, Any]) -> str:
    for key in ("classification", "disposition"):
        val = rec.get(key)
        if val is not None and str(val).strip():
            return str(val).strip()
    return ""


def evidence_map(rec: dict[str, Any]) -> dict[str, str]:
    ev = rec.get("evidence")
    if isinstance(ev, dict):
        return {str(k): "" if v is None else str(v) for k, v in ev.items()}
    if ev is None:
        return {}
    return {"evidence": str(ev)}


def evidence_fields_changed(
    v1: dict[str, Any], v2: dict[str, Any]
) -> list[str]:
    e1, e2 = evidence_map(v1), evidence_map(v2)
    keys = sorted(set(e1) | set(e2))
    return [k for k in keys if e1.get(k, "") != e2.get(k, "")]


def written_reason(rec: dict[str, Any]) -> str:
    for key in REASON_KEYS:
        val = rec.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    return ""


def index_by_canonical(
    doc: Any, migration: dict[str, Any] | None
) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for rec in candidates_of(doc):
        cid = str(rec["id"])
        canon = resolve_id(cid, migration)
        if canon in out:
            raise ValueError(
                f"canonical id collision {canon!r} from {out[canon]['id']!r} "
                f"and {cid!r}"
            )
        out[canon] = rec
    return out


def compare(
    v1_doc: Any,
    v2_doc: Any,
    migration: dict[str, Any] | None = None,
    *,
    require_evidence_delta: bool = True,
    require_reason: bool = True,
) -> dict[str, Any]:
    """Return findings. fail=True iff any SILENT_DRIFT row exists."""
    left = index_by_canonical(v1_doc, migration)
    right = index_by_canonical(v2_doc, migration)
    ids = sorted(set(left) | set(right))
    findings: list[dict[str, Any]] = []

    for canon in ids:
        a = left.get(canon)
        b = right.get(canon)
        if a is None and b is not None:
            findings.append(
                {
                    "canonical_id": canon,
                    "v1_id": None,
                    "v2_id": str(b["id"]),
                    "v1_classification": None,
                    "v2_classification": classification_of(b),
                    "kind": KIND_ADDED,
                    "evidence_fields_changed": [],
                    "has_reason": bool(written_reason(b)),
                    "reason": written_reason(b),
                    "fail": False,
                }
            )
            continue
        if a is not None and b is None:
            findings.append(
                {
                    "canonical_id": canon,
                    "v1_id": str(a["id"]),
                    "v2_id": None,
                    "v1_classification": classification_of(a),
                    "v2_classification": None,
                    "kind": KIND_REMOVED,
                    "evidence_fields_changed": [],
                    "has_reason": False,
                    "reason": "",
                    "fail": False,
                }
            )
            continue
        assert a is not None and b is not None
        c1, c2 = classification_of(a), classification_of(b)
        fields = evidence_fields_changed(a, b)
        reason = written_reason(b)
        has_reason = bool(reason)
        v1_id, v2_id = str(a["id"]), str(b["id"])
        renamed = v1_id != v2_id
        if c1 == c2:
            kind = KIND_RENAME_ONLY if renamed else KIND_UNCHANGED
            findings.append(
                {
                    "canonical_id": canon,
                    "v1_id": v1_id,
                    "v2_id": v2_id,
                    "v1_classification": c1,
                    "v2_classification": c2,
                    "kind": kind,
                    "evidence_fields_changed": fields,
                    "has_reason": has_reason,
                    "reason": reason,
                    "fail": False,
                }
            )
            continue
        evidence_ok = (not require_evidence_delta) or bool(fields)
        reason_ok = (not require_reason) or has_reason
        documented = evidence_ok and reason_ok
        findings.append(
            {
                "canonical_id": canon,
                "v1_id": v1_id,
                "v2_id": v2_id,
                "v1_classification": c1,
                "v2_classification": c2,
                "kind": KIND_DOCUMENTED if documented else KIND_SILENT,
                "evidence_fields_changed": fields,
                "has_reason": has_reason,
                "reason": reason,
                "fail": not documented,
            }
        )

    silent_ids = [f["canonical_id"] for f in findings if f["kind"] == KIND_SILENT]
    documented_ids = [
        f["canonical_id"] for f in findings if f["kind"] == KIND_DOCUMENTED
    ]
    rename_ids = [
        f["canonical_id"] for f in findings if f["kind"] == KIND_RENAME_ONLY
    ]
    return {
        "fail": bool(silent_ids),
        "silent_drift_ids": silent_ids,
        "documented_ids": documented_ids,
        "rename_only_ids": rename_ids,
        "findings": findings,
    }


def compare_paths(
    v1_path: Path,
    v2_path: Path,
    map_path: Path | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    migration = load_json(map_path) if map_path is not None else None
    result = compare(load_json(v1_path), load_json(v2_path), migration, **kwargs)
    result["v1_path"] = str(v1_path)
    result["v2_path"] = str(v2_path)
    result["map_path"] = str(map_path) if map_path is not None else None
    return result


def main() -> int:
    import sys

    if len(sys.argv) < 3:
        print("FAILED:monitor usage monitor.py <v1.json> <v2.json> [map.json]")
        return 2
    v1, v2 = Path(sys.argv[1]), Path(sys.argv[2])
    mp = Path(sys.argv[3]) if len(sys.argv) > 3 else None
    result = compare_paths(v1, v2, mp)
    print(json.dumps(result, sort_keys=True))
    return 1 if result["fail"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
