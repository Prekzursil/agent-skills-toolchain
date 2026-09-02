#!/usr/bin/env python3
"""Probe 2: empty-set path, 8 no-fit negatives, row-deletion mutation.

Independent of probe1's kind units. Verifies:
  * eight no-fit queries yield zero rows (empty set is reachable, not defaulted)
  * payload mentions of table patterns do not fire (use-vs-mention)
  * the table has no always-fire row
  * deleting MUTATION_ROW_ID turns exactly one labelled query red
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools" / "router"))

import rule_matcher as RM  # noqa: E402

ART = REPO / "command-center/receipts/IMP-0389.json"


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0389-probe2 {msg}")
    return 1


def main() -> int:
    table = RM.load_table(REPO / RM.TABLE_REL) if (REPO / RM.TABLE_REL).is_file() else RM.builtin_table()
    builtin = RM.builtin_table()
    if [r.row_id for r in table] != [r.row_id for r in builtin]:
        return fail("on-disk table drifted from builtin")

    corpus = RM.labelled_corpus(table)
    empty_qs = [q for q in corpus if q["expected_empty"]]
    if len(empty_qs) < 8:
        return fail(f"empty labels {len(empty_qs)} < 8")

    # Empty-set path: role fields unset. Must not be swallowed by a default.
    default_like = [
        r.row_id
        for r in table
        if r.pattern in RM.FORBIDDEN_GLOBS or RM.posix_norm(r.pattern) in RM.FORBIDDEN_CWD
    ]
    if default_like:
        return fail(f"always-fire rows {default_like}")

    empty_hits = []
    naive_nonempty = 0
    for query in empty_qs:
        result = RM.match_query(query, table)
        if not result.empty or result.fired_row_ids:
            empty_hits.append((query["query_id"], result.fired_row_ids))
        if result.model_calls != 0:
            return fail("model_calls_nonzero")
        if RM.naive_payload_scan(query, table):
            naive_nonempty += 1
    if empty_hits:
        return fail(f"no-fit fired {empty_hits}")
    if naive_nonempty < 6:
        return fail(f"use-vs-mention contrast weak naive_nonempty={naive_nonempty}")

    # Bare query with no roles and empty payload: still empty (no default).
    bare = RM.match_query(
        {"query_id": "q-bare", "payload": "", "keyword": None, "path": None, "cwd": None, "tool_verb": None},
        table,
    )
    if not bare.empty:
        return fail(f"bare query fired {bare.fired_row_ids} (default row)")

    red = RM.mutation_reds(table, corpus, RM.MUTATION_ROW_ID)
    expected_red = f"q-{RM.MUTATION_ROW_ID}"
    if red != [expected_red]:
        return fail(f"mutation reds={red} want=[{expected_red}]")

    # Live table still green after we restore (mutation used a copy).
    restored = [t for t in RM.trace_corpus(corpus, table) if not t["label_ok"]]
    if restored:
        return fail("original table not green after mutation copy")

    if not ART.is_file():
        return fail("receipt missing")
    receipt = json.loads(ART.read_text(encoding="utf-8"))
    mut = receipt.get("mutation_control") or {}
    if mut.get("deleted_row_id") != RM.MUTATION_ROW_ID:
        return fail("receipt mutation target drifted")
    if mut.get("red_query_ids") != [expected_red]:
        return fail("receipt mutation reds drifted")
    if int(receipt.get("empty_set_count") or 0) < 8:
        return fail("receipt empty_set_count < 8")
    if receipt.get("model_calls") not in (0, False, None) and receipt.get("model_calls") != 0:
        if receipt.get("model_call") is not False and receipt.get("model_calls") != 0:
            return fail("receipt claims a model call")

    summary = {
        "probe": "probe2-empty-mutation",
        "unit_id": "IMP-0389",
        "empty_queries": len(empty_qs),
        "empty_all_zero": True,
        "use_vs_mention_naive_nonempty": naive_nonempty,
        "bare_empty": True,
        "mutation_reds": red,
        "pass": True,
    }
    print(json.dumps(summary, sort_keys=True))
    print(
        f"empty={len(empty_qs)} naive_mentions={naive_nonempty} "
        f"mutation_red={red} deleted={RM.MUTATION_ROW_ID}"
    )
    print("SUCCESS:IMP-0389-probe2 empty-set path and single-query mutation")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
