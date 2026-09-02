"""Replay the corpus through all seven call sites and hash each column.

Equality is proven by comparing the seven SHA-256 column hashes, not by
eyeballing the table. canonical_verdict() is the byte identity of a cell.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Iterable

from call_sites import JUDGES, SITE_IDS, identity_ok
from corpus import all_rows
from reducer import evaluate


def canonical_verdict(verdict: dict[str, Any]) -> bytes:
    return json.dumps(verdict, sort_keys=True, separators=(",", ":")).encode("utf-8")


def digest_column(verdicts: list[dict[str, Any]]) -> str:
    h = hashlib.sha256()
    for v in verdicts:
        h.update(canonical_verdict(v))
        h.update(b"\n")
    return h.hexdigest()


def replay(
    skip_by_site: dict[str, Iterable[int]] | None = None,
) -> dict[str, Any]:
    skips = {
        site: frozenset(int(x) for x in (skip_by_site or {}).get(site, ()))
        for site in SITE_IDS
    }
    rows = all_rows()
    matrix: list[dict[str, Any]] = []
    columns: dict[str, list[dict[str, Any]]] = {s: [] for s in SITE_IDS}
    for row in rows:
        cell: dict[str, Any] = {"row_id": row["unit_id"], "sites": {}}
        for site in SITE_IDS:
            verdict = JUDGES[site](row, skip=skips[site])
            cell["sites"][site] = verdict
            columns[site].append(verdict)
        hashes = {s: hashlib.sha256(canonical_verdict(cell["sites"][s])).hexdigest() for s in SITE_IDS}
        cell["row_hashes_agree"] = len(set(hashes.values())) == 1
        matrix.append(cell)
    column_hashes = {s: digest_column(columns[s]) for s in SITE_IDS}
    unique = set(column_hashes.values())
    disagreements: list[dict[str, Any]] = []
    for cell in matrix:
        if cell["row_hashes_agree"]:
            continue
        payloads = {s: canonical_verdict(cell["sites"][s]) for s in SITE_IDS}
        disagreements.append(
            {
                "row_id": cell["row_id"],
                "distinct_payloads": len(set(payloads.values())),
                "failing_condition_by_site": {
                    s: cell["sites"][s].get("failing-condition-id") for s in SITE_IDS
                },
                "verdict_by_site": {s: cell["sites"][s].get("verdict") for s in SITE_IDS},
            }
        )
    return {
        "site_ids": list(SITE_IDS),
        "n_rows": len(rows),
        "n_sites": len(SITE_IDS),
        "row_ids": [r["unit_id"] for r in rows],
        "matrix": matrix,
        "column_hashes": column_hashes,
        "hashes_agree": len(unique) == 1,
        "distinct_column_hash_count": len(unique),
        "disagreements": disagreements,
        "identity_ok": identity_ok(),
        "shared_reducer": "command-center/p2-wave/probes/TST-0003/reducer.py:evaluate",
        "skip_by_site": {k: sorted(v) for k, v in skips.items() if v},
        "evaluate_is_shared": all(
            JUDGES[s].reducer is evaluate for s in SITE_IDS  # type: ignore[attr-defined]
        ),
    }
