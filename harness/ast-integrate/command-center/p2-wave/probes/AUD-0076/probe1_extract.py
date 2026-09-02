"""Named probe 1: extract owner-imperative statements + scratch-plant recall.

Signal: structured extraction from the recoverable owner corpus. A second
pass over a scratch copy must produce the planted canary. This probe does
not classify representation.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

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
    if "SUCCESS:AUD-0076" not in blob:
        return fail("sentinel absent")

    surface = owner_surface()
    catalog = surface["catalog"]
    catalog_text = CATALOG.read_text(encoding="utf-8")
    extracted = live_and_scratch_extract(
        catalog, catalog_text, surface["surface_text"]
    )
    live = extracted["live"]
    if len(live) < 3:
        return fail("live extract too small", extracted)
    if not extracted["planted_extracted"]:
        return fail("planted canary not extracted from scratch copy")
    if PLANTED_TOKEN in json.dumps(live):
        return fail("plant leaked into live extract")

    art_reqs = [
        r
        for r in artifact_requirements(doc)
        if isinstance(r, dict) and not r.get("planted")
    ]
    live_ids = [r["id"] for r in live]
    art_ids = [r.get("id") for r in art_reqs]
    if live_ids != art_ids:
        return fail("artifact requirement ids != live extract", {"live": live_ids, "art": art_ids})
    for live_row, art_row in zip(live, art_reqs):
        if live_row["text"] != art_row.get("text"):
            return fail(f"text drift {live_row['id']}")

    rec1 = artifact_probe_records(doc).get("probe1") or {}
    if rec1.get("live_count") != len(live):
        return fail("artifact probe1 live_count mismatch", rec1)
    if rec1.get("planted_extracted") is not True:
        return fail("artifact did not record planted extraction")

    out = {
        "probe": "probe1-extract",
        "unit_id": UNIT,
        "pass": True,
        "source": surface["source"],
        "transcript_found": bool(surface["locator"].get("found")),
        "live_count": len(live),
        "scratch_count": extracted["scratch_count"],
        "planted_extracted": True,
        "planted_ids": extracted["planted_ids"],
        "live_ids": live_ids,
        "artifact_matches_live": True,
    }
    (HERE / "probe1-extract.raw.json").write_text(
        json.dumps(out, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(out, sort_keys=True))
    print("SUCCESS:AUD-0076-probe1 extract owner-imperative list and planted recall")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
