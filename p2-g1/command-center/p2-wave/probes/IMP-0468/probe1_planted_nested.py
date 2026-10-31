"""Planted + nested case-collision detection before any zero scan is trusted (IMP-0468)."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools" / "command-center"))

import case_collision as cc  # noqa: E402

FIXTURE = HERE / "fixtures" / "planted-collision.json"


def main() -> int:
    # planted top-level collision is detected with both keys + both values
    top = cc.detect_file(FIXTURE, repo=REPO)
    assert top["walk_hits"], json.dumps(top)[:200]
    keys = set(top["walk_hits"][0]["keys"])
    assert keys == {"Name", "name"}, keys

    # nested collision (two levels deep) is also detected
    with tempfile.TemporaryDirectory() as td:
        nested = Path(td) / "pkg" / "deep.json"
        nested.parent.mkdir(parents=True)
        nested.write_text(json.dumps(
            {"outer": {"ID": "a", "id": "b", "keep": 1}}), encoding="utf-8")
        res = cc.detect_file(nested, repo=REPO)
        assert res["walk_hits"], "nested collision missed"
        assert set(res["walk_hits"][0]["keys"]) == {"ID", "id"}

    # non-case-distinct pairs stay silent
    with tempfile.TemporaryDirectory() as td:
        clean = Path(td) / "ok.json"
        clean.write_text(json.dumps({"Id": "same-key-once", "x": 1}), encoding="utf-8")
        res = cc.detect_file(clean, repo=REPO)
        assert not res["walk_hits"], res["walk_hits"]

    # the full required-controls battery (planted, nested, non_case, clean, id_id)
    controls = cc.run_required_controls()
    assert controls["all_passed"] is True, json.dumps(controls, default=str)[:300]

    print(json.dumps({
        "probe": "probe1-planted-nested",
        "unit_id": "IMP-0468",
        "planted_fired": True,
        "planted_keys": sorted(keys),
        "nested_fired": True,
        "non_case_silent": True,
        "controls_all_passed": True,
        "fixture": "command-center/p2-wave/probes/IMP-0468/fixtures/planted-collision.json",
        "sentinel": "SENTINEL:IMP-0468:CASE-COLLISION-SCANNED",
    }, indent=2))
    print("SUCCESS:IMP-0468-probe1 planted + nested collisions detected; "
          "non-case stays silent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
