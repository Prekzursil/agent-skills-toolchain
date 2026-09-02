#!/usr/bin/env python3
"""Probe 2: rollback rehearsal — reconstruct sources from decompose() and run smoke.

Expected outputs come from the fixture catalog (make_sources), matched by
structural fingerprint, not from lineage-copied expected fields alone.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from engine import (  # noqa: E402
    OPERATORS,
    apply_rename,
    decompose,
    fuse,
    run_smoke,
    workflow_fp,
)
from scenario import SENTINEL, make_sources, operator_plan  # noqa: E402

UNIT = "WFA-0063"
ART = REPO / "command-center/wfa/WFA-0063-fusion-decomposability.json"


def fail(msg: str, extra=None) -> int:
    print(f"FAILED:{UNIT}-probe2 {msg}")
    if extra is not None:
        print(json.dumps(extra, indent=2, default=str)[:4000])
    return 1


def match_original(recovered: dict, catalog: list[dict]) -> dict | None:
    fp = workflow_fp(recovered)
    hits = [o for o in catalog if workflow_fp(o) == fp]
    if len(hits) != 1:
        return None
    return hits[0]


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if SENTINEL not in json.dumps(doc):
        return fail("sentinel absent")
    if doc.get("unit_id") != UNIT:
        return fail("unit_id")

    catalog = list(make_sources().values())
    plan = operator_plan(make_sources())
    rehearsed: list[dict] = []

    for operator in OPERATORS:
        spec = plan[operator]
        fusion = fuse(operator, spec["sources"], spec["params"])
        recovered = decompose(fusion)
        if len(recovered) != len(spec["sources"]):
            return fail(f"count {operator}", {"got": len(recovered)})
        for rec in recovered:
            orig = match_original(rec, catalog)
            if orig is None:
                return fail(f"fingerprint {operator}:{rec['id']}")
            # Re-run smoke on the reconstructed copy, compare to catalog expected.
            live = run_smoke(rec)
            if not live["ok"]:
                return fail(f"smoke reconstructed {operator}:{rec['id']}", live)
            if live["observed"] != orig["smoke"]["expected"]:
                return fail(
                    f"catalog expected mismatch {operator}:{rec['id']}",
                    {
                        "observed": live["observed"],
                        "catalog_expected": orig["smoke"]["expected"],
                    },
                )
            catalog_run = run_smoke(orig)
            if catalog_run["observed"] != live["observed"]:
                return fail(
                    f"independent catalog re-run {operator}:{rec['id']}",
                    {"catalog": catalog_run, "reconstructed": live},
                )
            rehearsed.append(
                {
                    "operator": operator,
                    "recovered_id": rec["id"],
                    "matched_source": orig["id"],
                    "observed": live["observed"],
                    "expected": orig["smoke"]["expected"],
                }
            )

    # Rename path: still match originals by fingerprint and pass smoke.
    union = fuse("union", plan["union"]["sources"], plan["union"]["params"])
    old = union["lineage"]["source_ids"][0]
    renamed = apply_rename(union, old, f"{old}.renamed")
    for rec in decompose(renamed):
        orig = match_original(rec, catalog)
        if orig is None:
            return fail(f"rename fingerprint {rec['id']}")
        live = run_smoke(rec)
        if not live["ok"] or live["observed"] != orig["smoke"]["expected"]:
            return fail(f"rename smoke {rec['id']}", live)

    art_reh = doc.get("rollback_rehearsal") or {}
    if not art_reh.get("covers_all_operators"):
        return fail("artifact rehearsal coverage", art_reh)

    print(
        json.dumps(
            {
                "pass": True,
                "probe": "probe2-rollback-rehearsal",
                "unit_id": UNIT,
                "rehearsed_count": len(rehearsed),
                "operators": list(OPERATORS),
            },
            sort_keys=True,
        )
    )
    print(
        f"rehearsed={len(rehearsed)} operators={len(OPERATORS)} "
        "catalog_expected_matched=True"
    )
    print(f"SUCCESS:{UNIT}-probe2 rollback rehearsal per operator")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
