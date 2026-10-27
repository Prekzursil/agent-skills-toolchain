#!/usr/bin/env python3
"""Probe 2: corrupted-cache recovery + empty-index-is-failure.

Cases: truncated, zero-byte, wrong-schema. Each must rebuild from sources
rather than crash or serve planted/empty bytes. An empty rebuilt index is a
failure, not OK. Independent of the cache module's own ok=true claims.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(HERE))

from scenario import (  # noqa: E402
    PAINT_BEFORE,
    QUERY_RED,
    build_capability_tree,
)
from tools.router.index_cache import (  # noqa: E402
    CACHE_SCHEMA,
    EmptyIndexError,
    assert_index_usable,
    diagnose_cache,
    fingerprint_tree,
    load_or_rebuild,
    write_cache_atomic,
)
from tools.router.query import route_next  # noqa: E402

ART = REPO / "command-center/receipts/IMP-0402.json"
SENTINEL = "SENTINEL:IMP-0402:INDEX-INVALIDATION-SAFE"


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0402-probe2 {msg}")
    return 1


def check_receipt() -> str | None:
    if not ART.is_file():
        return None
    text = ART.read_text(encoding="utf-8")
    if SENTINEL not in text:
        return "receipt sentinel absent"
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as exc:
        return f"receipt unparseable:{exc}"
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return f"receipt self-declared:{st}"
    return None


def plant_wrong_schema(cache: Path, fp, planted_description: str) -> None:
    """Valid JSON, matching live hashes, but the wrong schema and a lie in the payload."""
    doc = {
        "schema": "not-the-cache-schema/v0",
        "content_hash": fp.content_hash,
        "mtime_token": fp.mtime_token,
        "file_count": fp.file_count,
        "max_mtime_ns": fp.max_mtime_ns,
        "capabilities": [
            {
                "capability_id": "paint",
                "description": planted_description,
                "source_path": "caps/skills/paint/SKILL.md",
            }
        ],
    }
    write_cache_atomic(cache, doc)


def main() -> int:
    receipt_err = check_receipt()
    if receipt_err:
        return fail(receipt_err)

    observations: list[dict] = []
    with tempfile.TemporaryDirectory(prefix="imp0402-p2-") as tmp:
        root = Path(tmp) / "caps"
        cache_dir = Path(tmp) / "router-cache"
        cache = cache_dir / "capability-index.json"
        build_capability_tree(root)
        roots = [root]

        primed = load_or_rebuild(cache, roots)
        if primed.action != "rebuilt":
            return fail(f"prime should rebuild, got {primed.action}")
        good_bytes = cache.read_bytes()
        if len(good_bytes) < 80:
            return fail("primed cache unexpectedly tiny")

        # --- truncated ---
        cache.write_bytes(good_bytes[:40])
        diag_trunc = diagnose_cache(cache)
        if diag_trunc != "truncated":
            return fail(f"truncated diagnose={diag_trunc}")
        crashed = False
        try:
            rec_trunc = load_or_rebuild(cache, roots)
            ans_trunc = route_next(QUERY_RED, cache_path=cache, roots=roots)
        except Exception as exc:  # noqa: BLE001 — crash is the failure class
            crashed = True
            rec_trunc = None
            ans_trunc = {"error": f"{type(exc).__name__}:{exc}"}
        observations.append(
            {
                "case": "truncated",
                "diagnose": diag_trunc,
                "crashed": crashed,
                "action": None if rec_trunc is None else rec_trunc.action,
                "reason": None if rec_trunc is None else rec_trunc.reason,
                "capability_count": 0
                if rec_trunc is None
                else len(rec_trunc.index.get("capabilities") or []),
                "answer": None if crashed else ans_trunc.get("answer"),
            }
        )
        if crashed or rec_trunc is None:
            return fail("truncated cache crashed instead of rebuilding")
        if rec_trunc.action != "rebuilt" or rec_trunc.reason != "truncated":
            return fail(f"truncated recovery {rec_trunc.action}/{rec_trunc.reason}")
        if len(rec_trunc.index["capabilities"]) == 0:
            return fail("truncated recovery produced an empty index and treated it as OK")
        if PAINT_BEFORE not in (ans_trunc.get("answer") or ""):
            return fail("truncated recovery did not restore source description")

        # --- zero-byte ---
        cache.write_bytes(b"")
        diag_zero = diagnose_cache(cache)
        if diag_zero != "zero-byte":
            return fail(f"zero-byte diagnose={diag_zero}")
        rec_zero = load_or_rebuild(cache, roots)
        ans_zero = route_next(QUERY_RED, cache_path=cache, roots=roots)
        observations.append(
            {
                "case": "zero-byte",
                "diagnose": diag_zero,
                "action": rec_zero.action,
                "reason": rec_zero.reason,
                "capability_count": len(rec_zero.index["capabilities"]),
                "answer": ans_zero.get("answer"),
            }
        )
        if rec_zero.action != "rebuilt" or rec_zero.reason != "zero-byte":
            return fail(f"zero-byte recovery {rec_zero.action}/{rec_zero.reason}")
        if len(rec_zero.index["capabilities"]) == 0:
            return fail("zero-byte recovery served an empty index as OK")
        if PAINT_BEFORE not in (ans_zero.get("answer") or ""):
            return fail("zero-byte recovery lost the source description")

        # --- wrong-schema (planted lie with matching hashes) ---
        fp = fingerprint_tree(roots)
        planted = "mixes PLANTED-STALE-PIGMENT that must not be served"
        plant_wrong_schema(cache, fp, planted)
        diag_schema = diagnose_cache(cache)
        if diag_schema != "wrong-schema":
            return fail(f"wrong-schema diagnose={diag_schema}")
        rec_schema = load_or_rebuild(cache, roots)
        ans_schema = route_next(QUERY_RED, cache_path=cache, roots=roots)
        observations.append(
            {
                "case": "wrong-schema",
                "diagnose": diag_schema,
                "action": rec_schema.action,
                "reason": rec_schema.reason,
                "capability_count": len(rec_schema.index["capabilities"]),
                "answer": ans_schema.get("answer"),
                "planted_absent": planted not in (ans_schema.get("answer") or ""),
            }
        )
        if rec_schema.action != "rebuilt" or rec_schema.reason != "wrong-schema":
            return fail(f"wrong-schema recovery {rec_schema.action}/{rec_schema.reason}")
        if planted in (ans_schema.get("answer") or ""):
            return fail("wrong-schema cache served the planted stale description")
        if PAINT_BEFORE not in (ans_schema.get("answer") or ""):
            return fail("wrong-schema recovery did not restore source description")

        # --- empty-index is failure, not OK (independent of ok=true claims) ---
        empty_doc = {
            "schema": CACHE_SCHEMA,
            "content_hash": fp.content_hash,
            "mtime_token": fp.mtime_token,
            "capabilities": [],
        }
        empty_raised = False
        empty_exc = ""
        try:
            assert_index_usable(empty_doc)
        except EmptyIndexError as exc:
            empty_raised = True
            empty_exc = str(exc)
        observations.append(
            {
                "case": "empty-index-assert",
                "raised": empty_raised,
                "exc": empty_exc,
            }
        )
        if not empty_raised:
            return fail("empty capabilities list was accepted as OK")

        write_cache_atomic(cache, empty_doc)
        diag_empty = diagnose_cache(cache)
        if diag_empty != "empty-index":
            return fail(f"empty-index diagnose={diag_empty}")
        rec_empty_file = load_or_rebuild(cache, roots)
        if rec_empty_file.reason != "empty-index":
            return fail(f"empty cache file reason={rec_empty_file.reason}")
        if rec_empty_file.action != "rebuilt":
            return fail("empty cache file did not rebuild from sources")
        if len(rec_empty_file.index["capabilities"]) == 0:
            return fail("empty cache rebuild produced empty and treated it as OK")

        empty_root = Path(tmp) / "empty-sources"
        empty_root.mkdir()
        empty_cache = Path(tmp) / "empty-cache" / "capability-index.json"
        rebuilt_empty_raised = False
        try:
            load_or_rebuild(empty_cache, [empty_root])
        except EmptyIndexError:
            rebuilt_empty_raised = True
        observations.append(
            {
                "case": "empty-rebuilt-index",
                "raised": rebuilt_empty_raised,
            }
        )
        if not rebuilt_empty_raised:
            return fail("rebuild over empty sources was reported OK")

        # Both-states: good cache stays a hit (detector silent on good).
        rec_good = load_or_rebuild(cache, roots)
        observations.append(
            {
                "case": "valid-cache-silent",
                "action": rec_good.action,
                "reason": rec_good.reason,
            }
        )
        if rec_good.action != "cache-hit" or rec_good.reason != "ok":
            return fail(f"valid cache was not a hit: {rec_good.action}/{rec_good.reason}")

        # Two-strikes on empty sources: still failure, never OK.
        second_empty_raised = False
        try:
            load_or_rebuild(empty_cache, [empty_root])
        except EmptyIndexError:
            second_empty_raised = True
        if not second_empty_raised:
            return fail("second empty rebuild was reported OK (two-strikes must not weaken)")

    summary = {
        "probe": "probe2-corrupt-cache",
        "unit_id": "IMP-0402",
        "pass": True,
        "truncated_rebuilt": True,
        "zero_byte_rebuilt": True,
        "wrong_schema_rebuilt": True,
        "empty_index_is_failure": True,
        "valid_cache_is_hit": True,
        "observations": observations,
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    print("SUCCESS:IMP-0402-probe2 corrupt-cache rebuilds; empty index is failure")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
