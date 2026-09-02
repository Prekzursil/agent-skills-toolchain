#!/usr/bin/env python3
"""Probe 1: decomposition returns the exact source id set vs recorded lineage.

Also: a fusion whose sources cannot be reconstructed is REJECTED at
certification (not shipped with a note), and rename via the id migration
map still decomposes.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from engine import OPERATORS, apply_rename, certify, decompose, fuse, plant_lossy  # noqa: E402
from scenario import SENTINEL, live_results, make_sources, operator_plan  # noqa: E402

UNIT = "WFA-0063"
ART = REPO / "command-center/wfa/WFA-0063-fusion-decomposability.json"


def fail(msg: str, extra=None) -> int:
    print(f"FAILED:{UNIT}-probe1 {msg}")
    if extra is not None:
        print(json.dumps(extra, indent=2, default=str)[:4000])
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("unit_id") != UNIT:
        return fail("unit_id", doc.get("unit_id"))
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        return fail(f"self-declared {doc.get('state')}")
    blob = json.dumps(doc)
    if SENTINEL not in blob:
        return fail("sentinel absent")

    live = live_results()
    if not live["pass"]:
        return fail("live suite not green", live)

    sources = make_sources()
    plan = operator_plan(sources)
    id_rows = []
    for operator in OPERATORS:
        spec = plan[operator]
        fusion = fuse(operator, spec["sources"], spec["params"])
        recovered = decompose(fusion)
        expected = sorted(s["id"] for s in spec["sources"])
        got = sorted(s["id"] for s in recovered)
        lineage = sorted(fusion["lineage"]["source_ids"])
        if got != expected or got != lineage:
            return fail(
                f"id-set {operator}",
                {"expected": expected, "recovered": got, "lineage": lineage},
            )
        cert = certify(fusion)
        if cert["verdict"] != "CERTIFIED":
            return fail(f"certify {operator}", cert)
        id_rows.append(
            {
                "operator": operator,
                "expected": expected,
                "recovered": got,
                "lineage": lineage,
            }
        )

    union = fuse("union", plan["union"]["sources"], plan["union"]["params"])
    for mode in ("strip-components", "drop-lineage", "drop-one-component"):
        planted = plant_lossy(union, mode)
        verdict = certify(planted)
        if verdict["verdict"] != "REJECTED":
            return fail(f"lossy {mode} was not rejected", verdict)
        if verdict["reason"] not in {
            "sources-not-reconstructable",
            "not-a-fusion",
        } and not str(verdict["reason"]).startswith("sources"):
            # still rejected; reason must be reconstructability, not a note
            if verdict["verdict"] == "CERTIFIED":
                return fail(f"lossy {mode} certified")
        if planted.get("notes") and verdict["verdict"] == "CERTIFIED":
            return fail("shipped with a note", verdict)
        if verdict["verdict"] != "REJECTED":
            return fail(f"lossy {mode}", verdict)

    old = union["lineage"]["source_ids"][0]
    new = f"{old}.renamed"
    renamed = apply_rename(union, old, new)
    rec = decompose(renamed)
    rec_ids = sorted(s["id"] for s in rec)
    lin_ids = sorted(renamed["lineage"]["source_ids"])
    if rec_ids != lin_ids:
        return fail("rename id-set", {"recovered": rec_ids, "lineage": lin_ids})
    if new not in rec_ids or old in rec_ids:
        return fail("rename did not apply", rec_ids)
    if renamed["lineage"]["id_migration_map"].get(old) != new:
        return fail("migration map missing", renamed["lineage"]["id_migration_map"])
    if certify(renamed)["verdict"] != "CERTIFIED":
        return fail("rename certification")

    art_ops = [c.get("operator") for c in doc.get("cases") or [] if c.get("kind") == "positive"]
    if set(art_ops) != set(OPERATORS):
        return fail("artifact cases missing operators", art_ops)

    print(
        json.dumps(
            {
                "pass": True,
                "probe": "probe1-idset-certify",
                "unit_id": UNIT,
                "operators": list(OPERATORS),
                "id_rows": id_rows,
                "lossy_rejected": 3,
                "rename_survived": True,
            },
            sort_keys=True,
        )
    )
    print(
        "idset_ok=True lossy_rejected=3 rename_ok=True operators="
        + ",".join(OPERATORS)
    )
    print(f"SUCCESS:{UNIT}-probe1 id-set vs lineage and certification reject")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
