#!/usr/bin/env python3
"""Namespace-collision extractor, gate, and same-id dispatch refusal.

A definition is one (namespace, meaning) binding of a literal id. The gate
fails closed on any id with two or more distinct definitions. Dispatch refuses
to run two work units that share an id, even if their titles match.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

M_TOKEN = re.compile(r"^M-0*(\d{1,2})$", re.I)
COLLECTION_KIND = {
    "work_units": "work_unit",
    "units": "work_unit",
    "options": "option",
    "mechanisms": "mechanism",
    "blueprints": "blueprint",
    "presets": "preset",
    "cards": "card",
    "records": None,
}


def canonical_id(raw: str) -> str:
    text = str(raw or "").strip()
    match = M_TOKEN.match(text)
    if match:
        return f"M-{int(match.group(1))}"
    return text


def id_sort_key(ident: str) -> tuple:
    match = M_TOKEN.match(ident)
    if match:
        return (0, int(match.group(1)))
    return (1, ident)


def meaning_fingerprint(namespace: str, kind: str, meaning: str) -> str:
    payload = json.dumps(
        {"kind": kind, "meaning": meaning, "namespace": namespace},
        sort_keys=True,
        ensure_ascii=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _as_record(obj: Any, *, path: str, namespace: str, kind: str) -> dict[str, Any] | None:
    if not isinstance(obj, dict):
        return None
    raw = obj.get("id")
    if not isinstance(raw, str) or not raw.strip():
        return None
    ident = canonical_id(raw)
    if not ident:
        return None
    title = str(obj.get("title") or obj.get("name") or "")
    meaning = str(
        obj.get("definition")
        or obj.get("meaning")
        or obj.get("body")
        or obj.get("question_or_target")
        or title
        or ident
    )
    ns = str(obj.get("namespace") or namespace)
    rec_kind = str(obj.get("kind") or kind or "record")
    fp = meaning_fingerprint(ns, rec_kind, meaning)
    return {
        "id": ident,
        "raw_id": raw.strip(),
        "kind": rec_kind,
        "namespace": ns,
        "path": path,
        "title": title,
        "meaning": meaning,
        "fingerprint": fp,
    }


def extract_document(doc: Any, *, path: str, default_namespace: str = "") -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if isinstance(doc, list):
        for item in doc:
            rec = _as_record(
                item,
                path=path,
                namespace=default_namespace or "anonymous",
                kind="record",
            )
            if rec:
                rows.append(rec)
        return rows
    if not isinstance(doc, dict):
        return rows
    namespace = str(doc.get("namespace") or default_namespace or Path(path).stem)
    default_kind = str(doc.get("kind") or "record")
    rec = _as_record(doc, path=path, namespace=namespace, kind=default_kind)
    if rec and not any(isinstance(doc.get(k), list) for k in COLLECTION_KIND):
        rows.append(rec)
    for key, mapped_kind in COLLECTION_KIND.items():
        blob = doc.get(key)
        if not isinstance(blob, list):
            continue
        kind = mapped_kind or default_kind
        for item in blob:
            got = _as_record(item, path=path, namespace=namespace, kind=kind)
            if got:
                rows.append(got)
    return rows


def extract_path(path: Path, *, repo: Path | None = None) -> list[dict[str, Any]]:
    rel = path.as_posix()
    if repo is not None:
        try:
            rel = path.resolve().relative_to(repo.resolve()).as_posix()
        except ValueError:
            rel = path.as_posix()
    text = path.read_text(encoding="utf-8")
    try:
        doc = json.loads(text)
    except json.JSONDecodeError:
        return []
    return extract_document(doc, path=rel)


def extract_paths(paths: Iterable[Path], *, repo: Path | None = None) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in paths:
        if path.is_file() and path.suffix.lower() == ".json":
            rows.extend(extract_path(path, repo=repo))
    return rows


def id_map(rows: Iterable[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[row["id"]].append(row)
    return dict(sorted(grouped.items(), key=lambda kv: kv[0]))


def distinct_definitions(defs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: dict[str, dict[str, Any]] = {}
    for row in defs:
        key = f"{row['namespace']}::{row['fingerprint']}"
        if key not in seen:
            seen[key] = row
    return list(seen.values())


def multi_definition_ids(mapping: dict[str, list[dict[str, Any]]]) -> list[str]:
    out: list[str] = []
    for ident, defs in mapping.items():
        if len(distinct_definitions(defs)) > 1:
            out.append(ident)
    return sorted(out, key=id_sort_key)


def intersecting_ids(
    mapping: dict[str, list[dict[str, Any]]], ns_a: str, ns_b: str
) -> list[str]:
    out: list[str] = []
    for ident, defs in mapping.items():
        namespaces = {d["namespace"] for d in defs}
        if ns_a in namespaces and ns_b in namespaces:
            out.append(ident)
    return sorted(out, key=id_sort_key)


def gate(rows: Iterable[dict[str, Any]]) -> dict[str, Any]:
    mapping = id_map(rows)
    colliding = multi_definition_ids(mapping)
    return {
        "ok": len(colliding) == 0,
        "colliding_ids": colliding,
        "id_count": len(mapping),
        "definition_count": sum(len(v) for v in mapping.values()),
        "reason": (
            None
            if not colliding
            else f"{len(colliding)} id(s) resolve to more than one definition"
        ),
    }


def dispatch(units: list[dict[str, Any]]) -> dict[str, Any]:
    by_id: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for unit in units:
        ident = canonical_id(str(unit.get("id") or ""))
        tagged = dict(unit)
        tagged["id"] = ident
        by_id[ident].append(tagged)
    refused: list[dict[str, Any]] = []
    ran: list[dict[str, Any]] = []
    for ident, group in by_id.items():
        if ident and len(group) > 1:
            for item in group:
                refused.append(
                    {
                        "id": ident,
                        "path": item.get("path"),
                        "title": item.get("title"),
                        "reason": "duplicate-work-unit-id",
                    }
                )
        else:
            ran.extend(group)
    return {
        "ok": len(refused) == 0,
        "ran": ran,
        "refused": refused,
        "refused_ids": sorted({r["id"] for r in refused}),
    }


def compact_map(mapping: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for ident, defs in mapping.items():
        distinct = distinct_definitions(defs)
        out[ident] = {
            "definition_count": len(distinct),
            "record_count": len(defs),
            "multi": len(distinct) > 1,
            "definitions": [
                {
                    "namespace": d["namespace"],
                    "kind": d["kind"],
                    "path": d["path"],
                    "title": d["title"],
                    "meaning": d["meaning"],
                    "fingerprint": d["fingerprint"],
                }
                for d in distinct
            ],
        }
    return out
