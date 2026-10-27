"""Merge discovered records by frozen identity. Never append a second row."""
from __future__ import annotations

from typing import Any

from identity import canonical_id, content_hash, content_payload, field_delta

SCHEMA = "wfa-0085-registry-v1"


def empty_store() -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "records": [],
        "checkpoint": {
            "completed_sources": [],
            "last_source": "",
            "n_completed": 0,
        },
    }


def index_records(store: dict[str, Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for rec in store.get("records") or []:
        if isinstance(rec, dict) and rec.get("stable_id"):
            out[str(rec["stable_id"])] = rec
    return out


def _sort_store(store: dict[str, Any]) -> None:
    recs = list(store.get("records") or [])
    recs.sort(key=lambda r: str(r.get("stable_id") or ""))
    store["records"] = recs
    ck = store.setdefault("checkpoint", {})
    ck["n_completed"] = len(ck.get("completed_sources") or [])


def _new_record(stable: str, raw_id: str, src: dict[str, Any], source_file: str) -> dict[str, Any]:
    ch = content_hash(src)
    aliases = [] if raw_id == stable else [raw_id]
    return {
        "adjudication": None,
        "aliases": aliases,
        "body": src.get("body"),
        "content_hash": ch,
        "evidence": [
            {
                "delta": None,
                "kind": "insert",
                "source_file": source_file,
                "source_uri": src.get("source_uri"),
            }
        ],
        "family": src.get("family"),
        "mechanism": src.get("mechanism"),
        "provenance": [
            {
                "content_hash": ch,
                "source_file": source_file,
                "source_uri": src.get("source_uri"),
            }
        ],
        "stable_id": stable,
        "title": src.get("title"),
    }


def merge_source(
    store: dict[str, Any],
    src: dict[str, Any],
    source_file: str,
    migration_map: dict[str, str],
) -> dict[str, Any]:
    """Insert / observe / update by canonical id. Preserves locked adjudications.

    Returns a result dict: action in {insert, observe, update, noop}.
    """
    raw_id = str(src.get("id") or "")
    if not raw_id:
        raise ValueError(f"{source_file} missing id")
    stable = canonical_id(raw_id, migration_map)
    by_id = index_records(store)
    incoming_hash = content_hash(src)
    if stable not in by_id:
        rec = _new_record(stable, raw_id, src, source_file)
        store["records"].append(rec)
        _sort_store(store)
        return {"action": "insert", "stable_id": stable, "duplicate": False}

    rec = by_id[stable]
    if raw_id != stable and raw_id not in rec["aliases"]:
        rec["aliases"] = sorted(set(rec["aliases"]) | {raw_id})

    already = any(p.get("source_file") == source_file for p in rec["provenance"])
    if already and rec.get("content_hash") == incoming_hash:
        _sort_store(store)
        return {"action": "noop", "stable_id": stable, "duplicate": False}

    if already:
        for p in rec["provenance"]:
            if p.get("source_file") == source_file:
                p["content_hash"] = incoming_hash
                p["source_uri"] = src.get("source_uri")
    else:
        rec["provenance"].append(
            {
                "content_hash": incoming_hash,
                "source_file": source_file,
                "source_uri": src.get("source_uri"),
            }
        )
        rec["provenance"].sort(key=lambda p: str(p.get("source_file") or ""))

    if rec.get("content_hash") == incoming_hash:
        rec["evidence"].append(
            {
                "delta": None,
                "kind": "observe",
                "source_file": source_file,
                "source_uri": src.get("source_uri"),
            }
        )
        _sort_store(store)
        return {"action": "observe", "stable_id": stable, "duplicate": False}

    before = content_payload(rec)
    after = content_payload(src)
    delta = field_delta(before, after)
    rec["title"] = src.get("title")
    rec["family"] = src.get("family")
    rec["mechanism"] = src.get("mechanism")
    rec["body"] = src.get("body")
    rec["content_hash"] = incoming_hash
    rec["evidence"].append(
        {
            "delta": delta,
            "kind": "update",
            "source_file": source_file,
            "source_uri": src.get("source_uri"),
        }
    )
    _sort_store(store)
    return {
        "action": "update",
        "stable_id": stable,
        "duplicate": False,
        "delta_fields": sorted(delta.keys()),
        "adjudication_preserved": rec.get("adjudication") is not None,
    }


def mark_checkpoint(store: dict[str, Any], source_file: str) -> None:
    ck = store.setdefault("checkpoint", {})
    done = list(ck.get("completed_sources") or [])
    if source_file not in done:
        done.append(source_file)
    ck["completed_sources"] = done
    ck["last_source"] = source_file
    ck["n_completed"] = len(done)


def set_adjudication(store: dict[str, Any], stable_id: str, adj: dict[str, Any]) -> None:
    rec = index_records(store).get(stable_id)
    if rec is None:
        raise KeyError(stable_id)
    rec["adjudication"] = dict(adj)


def stable_ids(store: dict[str, Any]) -> list[str]:
    return sorted(str(r["stable_id"]) for r in store.get("records") or [])
