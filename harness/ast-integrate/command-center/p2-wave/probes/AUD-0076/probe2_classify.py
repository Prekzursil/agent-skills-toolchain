"""Named probe 2: classify each requirement against the live artifact corpus.

Mechanically different from probe 1: targeted search of owner_questions,
catalog items, and work units. The scratch-planted canary must be DROPPED.
An extractor that classifies everything as REPRESENTED has no power.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from classify import classify_requirements  # noqa: E402
from common import (  # noqa: E402
    CATALOG,
    OUT,
    PLANTED_TOKEN,
    UNIT,
    artifact_probe_records,
    artifact_requirements,
)
from corpus import owner_surface  # noqa: E402
from extract import live_and_scratch_extract  # noqa: E402

ART = OUT


def fail(msg: str, extra=None) -> int:
    print(f"FAILED:{UNIT}-probe2 {msg}")
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

    surface = owner_surface()
    catalog = surface["catalog"]
    catalog_text = CATALOG.read_text(encoding="utf-8")
    extracted = live_and_scratch_extract(
        catalog, catalog_text, surface["surface_text"]
    )
    live_cls = classify_requirements(extracted["live"], catalog)
    scratch_cls = classify_requirements(extracted["scratch"], catalog)

    if not scratch_cls["planted_dropped"]:
        return fail("planted canary was not classified DROPPED", scratch_cls)
    if not scratch_cls["not_all_represented"]:
        return fail("classifier labelled everything REPRESENTED")
    if live_cls["live_counts"]["SUPERSEDED"] < 1:
        return fail("no SUPERSEDED live requirement; three-way vocabulary collapsed")
    if PLANTED_TOKEN in json.dumps(live_cls["live"]):
        return fail("plant leaked into live classification")

    art_reqs = artifact_requirements(doc)
    live_map = {r["id"]: r for r in live_cls["live"]}
    if [r["id"] for r in art_reqs] != [r["id"] for r in live_cls["live"]]:
        return fail(
            "artifact requirement order/id != live classification",
            {
                "art": [r.get("id") for r in art_reqs],
                "live": [r["id"] for r in live_cls["live"]],
            },
        )
    for art in art_reqs:
        live = live_map.get(art.get("id"))
        if live is None:
            return fail(f"artifact id missing live {art.get('id')}")
        if art.get("verdict") != live["verdict"]:
            return fail(f"verdict drift {art.get('id')}", {"art": art, "live": live})

    controls = doc.get("negative_controls") or []
    plant_ctrl = next(
        (c for c in controls if isinstance(c, dict) and c.get("id") == "AUD-0076-PLANT-DROPPED"),
        None,
    )
    fired = plant_ctrl.get("fired_on_bad_state", plant_ctrl.get("detector_fired"))
    silent = plant_ctrl.get("silent_on_good_state", plant_ctrl.get("silent_on_good"))
    if not plant_ctrl or fired is not True:
        return fail("artifact missing planted DROPPED control")
    if silent is not True:
        return fail("control not silent-on-good")

    rec2 = artifact_probe_records(doc).get("probe2") or {}
    if rec2.get("planted_dropped") is not True:
        return fail("artifact probe2 did not record planted_dropped")
    if rec2.get("live_counts") != live_cls["live_counts"]:
        return fail("artifact probe2 live_counts mismatch", rec2)

    out = {
        "probe": "probe2-classify",
        "unit_id": UNIT,
        "pass": True,
        "live_counts": live_cls["live_counts"],
        "scratch_counts": scratch_cls["counts"],
        "planted_dropped": True,
        "not_all_represented": True,
        "superseded_live": live_cls["live_counts"]["SUPERSEDED"],
        "live_dropped_ids": live_cls["live_dropped_ids"],
        "artifact_matches_live": True,
    }
    (HERE / "probe2-classify.raw.json").write_text(
        json.dumps(out, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(out, sort_keys=True))
    print("SUCCESS:AUD-0076-probe2 classify REPRESENTED/SUPERSEDED/DROPPED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
