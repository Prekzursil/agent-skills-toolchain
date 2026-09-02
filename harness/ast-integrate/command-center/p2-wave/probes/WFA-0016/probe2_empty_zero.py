#!/usr/bin/env python3
"""Probe 2: EMPTY assets, explicit ZERO_RELEASES, registry-omit (evidence A)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import scenario as S  # noqa: E402

ART = REPO / "command-center/wfa/WFA-0016-sweep-releases.json"


def fail(msg: str) -> int:
    print(f"FAILED:WFA-0016-probe2 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if "SUCCESS:WFA-0016" not in json.dumps(doc):
        return fail("sentinel-absent")
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared:{st}")

    hunt = S.hunt_host_registry()
    live = S.sweep_fixture_world(hunt["join_registry"])

    empty = live["empty_assets"]
    if not empty:
        return fail("empty asset missing from inventory")
    if any(row.get("skipped") for row in empty):
        return fail("empty asset was skipped")
    rec_empty = (doc.get("fixture_sweep") or {}).get("empty_assets") or []
    if not rec_empty:
        return fail("artifact omitted EMPTY rows")
    if any(row.get("skipped") for row in rec_empty):
        return fail("artifact skipped EMPTY")

    zeros = live["zero_release_repos"]
    if "owner/silent-repo" not in zeros:
        return fail("silent-repo not explicitly ZERO_RELEASES")
    rec_zeros = (doc.get("fixture_sweep") or {}).get("zero_release_repos") or []
    if "owner/silent-repo" not in rec_zeros:
        return fail("artifact folded zero-release repo into a silent pass")

    silent = next(r for r in live["repos"] if r["name"] == "owner/silent-repo")
    if silent.get("classification") != "ZERO_RELEASES":
        return fail(f"silent classification {silent.get('classification')}")
    if silent.get("release_count") != 0:
        return fail("silent-repo release_count != 0")

    omitted = [row.get("id") for row in live["omitted_from_registry"]]
    if S.OMIT_ID not in omitted:
        return fail("omitted shipped blueprint not reported")
    if S.MATCH_ID in omitted:
        return fail("registered match id reported as omitted")
    rec_omit = [
        row.get("id")
        for row in (doc.get("fixture_sweep") or {}).get("omitted_from_registry") or []
    ]
    if S.OMIT_ID not in rec_omit:
        return fail("artifact missing registry-omit finding")

    ids = set((hunt["join_registry"] or {}).get("ids") or [])
    if S.MATCH_ID not in ids:
        return fail("match id missing from join registry")
    if S.OMIT_ID in ids:
        return fail("omit id should not be in join registry")

    out = {
        "probe": "probe2-empty-zero-omit",
        "unit_id": "WFA-0016",
        "empty_not_skipped": True,
        "zero_releases_explicit": True,
        "omit_id": S.OMIT_ID,
        "match_not_omitted": True,
        "pass": True,
    }
    print(json.dumps(out, sort_keys=True))
    print(
        f"empty={len(empty)} zeros={zeros} omit={S.OMIT_ID} "
        f"match_in_registry={S.MATCH_ID in ids}"
    )
    print("SUCCESS:WFA-0016-probe2 EMPTY ZERO_RELEASES registry-omit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
