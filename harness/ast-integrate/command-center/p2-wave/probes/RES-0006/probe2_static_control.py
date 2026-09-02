#!/usr/bin/env python3
"""Probe 2: archived-tag zero churn (both-states) and half-life arithmetic."""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from catalog import ARCHIVED_TAG_ID  # noqa: E402
from tracker import (  # noqa: E402
    class_half_life,
    measure,
    reputation_mutant_table,
)

ART = REPO / "command-center/research/RES-0006.json"
LN2 = math.log(2.0)


def fail(msg: str) -> int:
    print(f"FAILED:RES-0006-probe2 {msg}")
    return 1


def close(a: float | None, b: float | None) -> bool:
    if a is None and b is None:
        return True
    if a is None or b is None:
        return False
    return abs(float(a) - float(b)) <= max(1e-9, 1e-12 * max(abs(float(a)), abs(float(b)), 1.0))


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        return fail("artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if "SUCCESS:RES-0006" not in ART.read_text(encoding="utf-8"):
        return fail("sentinel absent")

    live = measure()
    tag = live["archived_tag"]
    if tag["churn"] != 0 or tag["changed"] is not False:
        return fail("archived-tag showed churn on the static state")
    if tag["wave1_sha256"] != tag["wave2_sha256"]:
        return fail("archived-tag hashes differ")

    broken = measure(
        mutate_source_id=ARCHIVED_TAG_ID,
        mutate_fn=lambda body: body + "\nMUTANT-BYTE\n",
    )
    if broken["archived_tag"]["churn"] != 1 or broken["archived_tag"]["changed"] is not True:
        return fail("archived-tag mutant did not go red")
    if broken["archived_tag"]["wave1_sha256"] == broken["archived_tag"]["wave2_sha256"]:
        return fail("archived-tag mutant hashes still equal")
    print(
        "both_states static_churn=0 mutant_churn=1 "
        f"static_sha={tag['wave1_sha256'][:12]}"
    )

    art_ctrl = doc.get("archived_tag_control") or {}
    if art_ctrl.get("churn") != 0:
        return fail("artifact archived-tag churn")

    dt = live["observation_hours"]
    for live_row, art_row in zip(live["half_life_table"], doc.get("half_life_table") or []):
        n = int(art_row["n_sources"])
        k = int(art_row["n_changed"])
        recomputed = class_half_life(n, k, dt)
        if recomputed["n_changed"] != live_row["n_changed"]:
            return fail(f"live vs artifact churn {live_row['source_class']}")
        if not close(recomputed["half_life_hours"], art_row.get("half_life_hours")):
            return fail(
                f"half-life arithmetic {art_row['source_class']} "
                f"recomputed={recomputed['half_life_hours']} "
                f"published={art_row.get('half_life_hours')}"
            )
        if recomputed["bound"] != art_row.get("bound"):
            return fail(f"bound {art_row['source_class']}")
        method = str(art_row.get("method") or "")
        trigger_src = str(art_row.get("revalidation_trigger_source") or "")
        if method == "reputation-prior" or trigger_src == "reputation-prior":
            return fail(f"reputation leak {art_row['source_class']}")
        if "snapshot-churn" not in method:
            return fail(f"method not snapshot-churn {art_row['source_class']} {method}")
        if k == 0:
            if art_row.get("half_life_hours") is not None:
                return fail(f"censored class invented a point T½ {art_row['source_class']}")
            if art_row.get("bound") != "lower":
                return fail(f"censored class bound {art_row['source_class']}")
        else:
            expected = LN2 * n * dt / k
            if not close(art_row.get("half_life_hours"), expected):
                return fail(f"mle plug-in {art_row['source_class']}")

    # Known-broken reputation table must not match the measured archival row.
    rep = {r["source_class"]: r for r in reputation_mutant_table(dt)}
    archival = next(
        r for r in (doc.get("half_life_table") or []) if r.get("source_class") == "archival"
    )
    if archival.get("half_life_hours") == rep["archival"]["half_life_hours"]:
        return fail("archival T½ matches reputation mutant")
    if archival.get("method") == "reputation-prior":
        return fail("artifact method is reputation-prior")
    if archival.get("n_changed") != 0:
        return fail("archival should be the zero-churn class in this panel")

    eco = doc.get("decay_on_write") or {}
    if eco.get("changed") is not True:
        return fail("decay-on-write control silent")
    if eco.get("wave1_sha256") == eco.get("wave2_sha256"):
        return fail("decay-on-write hashes equal")

    print(
        "arithmetic_ok=true reputation_rejected=true "
        f"censored={[r['source_class'] for r in live['half_life_table'] if r['n_changed'] == 0]}"
    )
    print("SUCCESS:RES-0006-probe2 static-control half-life-arithmetic")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
