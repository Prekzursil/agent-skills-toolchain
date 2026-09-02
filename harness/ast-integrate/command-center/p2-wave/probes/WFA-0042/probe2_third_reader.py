#!/usr/bin/env python3
"""Probe 2: third-reader blind relabel, UNMEASURABLE not averaged, freeze bump.

Mechanically independent of probe 1: this file imports labeller_c and gold,
not labeller_a / labeller_b. The third reader sees source bytes only.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import gold as G  # noqa: E402
import labeller_c as C  # noqa: E402
from dimensions import (  # noqa: E402
    DIMENSIONS,
    GOLD_VERSION,
    KAPPA_FLOOR,
    OUT_REL,
    THIRD_READER_N,
    UNIT_ID,
)
from io_source import load_source  # noqa: E402
from sampling_rule import load_selected  # noqa: E402

REPO = HERE.parents[3]
ART = REPO / OUT_REL


def fail(msg: str, extra=None) -> int:
    print(f"FAILED:{UNIT_ID}-probe2 {msg}")
    if extra is not None:
        print(json.dumps(extra, indent=2, default=str)[:4000])
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    blob = json.dumps(doc)
    if "SUCCESS:WFA-0042" not in blob:
        return fail("sentinel absent")
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")

    selected = load_selected()
    third_specs = [s for s in selected if s["third_reader"]]
    if len(third_specs) != THIRD_READER_N:
        return fail(f"third-reader n={len(third_specs)}")

    # Blind: C labels source bytes. A/B label dicts are not imported.
    third_ids = []
    for spec in third_specs:
        src = load_source(
            spec["abs_path"],
            rel=spec["path"],
            family=spec["family"],
            candidate_id=spec["candidate_id"],
        )
        labels = C.label_source(src)
        missing = [d for d in DIMENSIONS if d not in labels]
        if missing:
            return fail("third reader missed dimensions", missing)
        for dim, cell in labels.items():
            if cell.get("cell_state") not in {"EVIDENCED", "HONEST-NULL", "EMPTY"}:
                return fail("third reader bad cell_state", {dim: cell})
        third_ids.append(spec["candidate_id"])

    art_ids = doc.get("third_reader_ids") or []
    if art_ids != third_ids:
        return fail("artifact third-reader ids drifted", {"live": third_ids, "art": art_ids})

    pack = G.build_gold()
    unm = pack["kappa"]["unmeasurable"]
    if not unm:
        return fail(
            "no UNMEASURABLE dimension; averaging control is untested",
            pack["kappa"]["per_dimension"],
        )
    if pack["kappa"]["aggregate_kappa"] is not None:
        return fail("aggregate kappa must remain null")
    if doc.get("aggregate_kappa") is not None:
        return fail("artifact published an aggregate kappa")
    if list(doc.get("unmeasurable_dimensions") or []) != list(unm):
        return fail(
            "artifact UNMEASURABLE list drifted",
            {"live": unm, "art": doc.get("unmeasurable_dimensions")},
        )

    avg = G.averaging_mutant(pack["kappa"])
    if not avg["fired_on_bad_state"]:
        return fail("averaging mutant did not fire", avg)
    if not avg["silent_on_good_state"]:
        return fail("averaging mutant not silent on good state", avg)

    freeze_bad = G.freeze_mutant(scored=("WFA-0032",), bumped=False)
    freeze_good = G.freeze_mutant(scored=(), bumped=False)
    if not freeze_bad["fired_on_bad_state"]:
        return fail("post-score no-bump mutant did not fire", freeze_bad)
    if not freeze_good["silent_on_good_state"]:
        return fail("v1 freeze not silent before first score", freeze_good)
    if int(doc.get("gold_version") or 0) != GOLD_VERSION:
        return fail("gold_version drifted")
    if doc.get("extractors_scored"):
        return fail("extractors_scored must be empty at v1 freeze")
    if float(doc.get("kappa_floor")) != KAPPA_FLOOR:
        return fail("kappa floor drifted")

    payload = {
        "both_states": {
            "bad_low_kappa_averaged_fires": avg["fired_on_bad_state"],
            "bad_post_score_no_bump_fires": freeze_bad["fired_on_bad_state"],
            "good_unmeasurable_not_averaged": avg["silent_on_good_state"],
            "good_v1_freeze_silent": freeze_good["silent_on_good_state"],
        },
        "pass": True,
        "probe": "probe2-third-reader",
        "third_reader_ids": third_ids,
        "third_reader_n": len(third_ids),
        "unmeasurable": unm,
        "unit_id": UNIT_ID,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        f"SUCCESS:{UNIT_ID}-probe2 third-reader n={len(third_ids)} blind; "
        "UNMEASURABLE not averaged; freeze bump required after score"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
