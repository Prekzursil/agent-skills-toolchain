#!/usr/bin/env python3
"""Probe 1: unit test per matcher kind plus the 60-query labelled corpus traces.

Every non-empty selection must name the exact table row that fired. Payload
mentions of sibling patterns must not add rows (use-vs-mention).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools" / "router"))

import rule_matcher as RM  # noqa: E402

ART = REPO / "command-center/receipts/IMP-0389.json"
SENTINEL = "SENTINEL:IMP-0389:RULE-MATCHER-DETERMINISTIC"


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0389-probe1 {msg}")
    return 1


def main() -> int:
    table = RM.builtin_table()
    RM.validate_table(table)
    if len(table) != 52:
        return fail(f"table_rows={len(table)} want=52")

    kind_qs = RM.kind_unit_queries(table)
    kind_ok: dict[str, bool] = {}
    for kind in RM.KINDS:
        query = kind_qs[kind]
        result = RM.match_query(query, table)
        ok = (
            not result.empty
            and result.fired_row_ids == query["expected_row_ids"]
            and result.model_calls == 0
            and len(result.fired_row_ids) == 1
        )
        naive = RM.naive_payload_scan(query, table)
        # Payload mentions siblings; a payload scanner would over-fire.
        if len(naive) < 2:
            return fail(f"kind {kind} payload contrast too weak naive={naive}")
        if set(result.fired_row_ids) == set(naive):
            return fail(f"kind {kind} matched payload mentions (use-vs-mention)")
        kind_ok[kind] = ok
        print(
            f"kind {kind} row={result.fired_row_ids} "
            f"ok={ok} naive_extra={sorted(set(naive) - set(result.fired_row_ids))[:4]}"
        )
        if not ok:
            return fail(f"kind-unit {kind}")

    corpus = RM.labelled_corpus(table)
    if len(corpus) != 60:
        return fail(f"corpus={len(corpus)} want=60")
    traces = RM.trace_corpus(corpus, table)
    bad = [t for t in traces if not t["label_ok"]]
    empty = [t for t in traces if t["empty"]]
    if bad:
        return fail(f"label mismatches { [t['query_id'] for t in bad][:8] }")
    if len(empty) < 8:
        return fail(f"empty_traces={len(empty)} want>=8")
    if any(t["model_calls"] != 0 for t in traces):
        return fail("model_calls_nonzero")
    per_kind = {k: 0 for k in RM.KINDS}
    for t in traces:
        if t.get("kind") in per_kind:
            per_kind[t["kind"]] += 1
    if any(per_kind[k] != 13 for k in RM.KINDS):
        return fail(f"per_kind {per_kind}")

    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("receipt missing")
    receipt = json.loads(ART.read_text(encoding="utf-8"))
    text = ART.read_text(encoding="utf-8")
    if SENTINEL not in text:
        return fail("sentinel-absent")
    if str(receipt.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared:{receipt.get('state')}")
    rec_traces = receipt.get("corpus_traces") or []
    if len(rec_traces) != 60:
        return fail(f"receipt traces {len(rec_traces)} want=60")
    live_ids = [t["query_id"] for t in traces]
    rec_ids = [t.get("query_id") for t in rec_traces]
    if live_ids != rec_ids:
        return fail("receipt trace query_id order drifted")
    for live, rec in zip(traces, rec_traces):
        if live["fired_row_ids"] != rec.get("fired_row_ids"):
            return fail(f"receipt trace drifted {live['query_id']}")

    summary = {
        "probe": "probe1-matcher-kinds",
        "unit_id": "IMP-0389",
        "kinds_ok": kind_ok,
        "corpus": 60,
        "empty_traces": len(empty),
        "label_ok": len(traces) - len(bad),
        "model_calls": 0,
        "pass": True,
    }
    print(json.dumps(summary, sort_keys=True))
    print("SUCCESS:IMP-0389-probe1 matcher kinds and 60-query traces")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
