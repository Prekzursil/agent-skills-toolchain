#!/usr/bin/env python3
"""WFA-0011 probe 2: field-level drift (signal B) + commit-time newer-side."""
from __future__ import annotations

import inspect
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import newer as newer_mod  # noqa: E402
from extract import heading_ids, load_json_records  # noqa: E402
from fixtures import control_paths, write_control  # noqa: E402
from gate import compare_texts, plant_field_drift  # noqa: E402
from newer import json_always_wins, newer_side  # noqa: E402

UNIT = "WFA-0011"
ART = REPO / "command-center" / "wfa" / "WFA-0011-md-json-mirror-parity.json"
SENTINEL = "SUCCESS:WFA-0011"
BLOCKED = {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}
PLANT_ID = "wf-saved-control-01"


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe2 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact-absent")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    st = str(doc.get("state") or "").upper()
    if st in BLOCKED:
        return fail(f"self-declared:{st}")
    if SENTINEL not in text:
        return fail("sentinel-absent")

    src = inspect.getsource(newer_mod.newer_side)
    if "assumed_json" in src and "True" in src.split("assumed_json")[1][:80]:
        # Honest function must assign False, not True.
        if "assumed_json\": True" in src or "assumed_json'] = True" in src:
            return fail("newer_side-hardcodes-assumed-json")
    if "newer\": \"json\"" in src.replace(" ", "") and "clocks" not in src:
        return fail("newer_side-hardcodes-json-winner")

    write_control()
    paths = control_paths()
    md = paths["08_md"].read_text(encoding="utf-8")
    js = paths["08_json"].read_text(encoding="utf-8")

    good = compare_texts(md, js, repo=REPO, md_path=paths["08_md"], json_path=paths["08_json"])
    if not good["signal_a"]["equal"]:
        return fail("good-state-id-set")
    if not good["signal_b"]["equal"]:
        return fail(f"good-state-fields:{good['signal_b']['drifts']}")
    if good["signal_b"]["sample_size"] != 30:
        return fail(f"sample-size:{good['signal_b']['sample_size']}")
    fams = good["signal_b"]["family_counts_in_sample"]
    if len(fams) != 9:
        return fail(f"sample-not-stratified:{fams}")

    # Planted per-field drifts: id set stays equal; signal B must fire.
    both = {"good_silent": good["signal_b"]["equal"]}
    for field, planted in (
        ("classification", "PLANTED-DRIFT-CLASS"),
        ("licence", "PLANTED-DRIFT-LICENCE"),
        ("family", "PLANTED-DRIFT-FAMILY"),
    ):
        drifted = plant_field_drift(md, PLANT_ID, field, planted)
        if set(heading_ids(drifted)) != set(heading_ids(md)):
            return fail(f"{field}-plant-changed-id-set")
        bad = compare_texts(drifted, js, repo=REPO)
        if not bad["signal_a"]["equal"]:
            return fail(f"{field}-plant-broke-signal-a")
        hits = [d for d in bad["signal_b"]["drifts"] if d["id"] == PLANT_ID and d["field"] == field]
        if not hits:
            return fail(f"{field}-plant-not-caught-by-B drifts={bad['signal_b']['drifts']}")
        if hits[0]["markdown"] != planted:
            return fail(f"{field}-plant-value:{hits[0]}")
        both[f"{field}_fires"] = True

    # Commit-time newer-side: never assume JSON.
    md_newer = newer_side(None, None, REPO, clocks={"markdown": 200, "json": 100})
    js_newer = newer_side(None, None, REPO, clocks={"markdown": 100, "json": 200})
    tie = newer_side(None, None, REPO, clocks={"markdown": 100, "json": 100})
    if md_newer["newer"] != "markdown" or md_newer["assumed_json"]:
        return fail(f"md-newer:{md_newer}")
    if js_newer["newer"] != "json" or js_newer["assumed_json"]:
        return fail(f"js-newer:{js_newer}")
    if tie["newer"] != "tie" or tie["assumed_json"]:
        return fail(f"tie:{tie}")
    mutant = json_always_wins(clocks={"markdown": 200, "json": 100})
    if mutant["newer"] != "json" or not mutant["assumed_json"]:
        return fail(f"mutant-not-json-default:{mutant}")
    if md_newer["newer"] == mutant["newer"]:
        return fail("honest-collapsed-to-json-always-wins")

    # Control 09 good-state fields.
    md9 = paths["09_md"].read_text(encoding="utf-8")
    js9 = paths["09_json"].read_text(encoding="utf-8")
    good9 = compare_texts(md9, js9, repo=REPO)
    if not good9["parity"]:
        return fail("09-good-parity")
    if len(load_json_records(js9)) != 36:
        return fail("09-json-n")

    out = {
        "ok": True,
        "both_states": both,
        "sample_size": good["signal_b"]["sample_size"],
        "families_in_sample": sorted(fams),
        "newer": {
            "markdown_clock_wins": md_newer["newer"],
            "json_clock_wins": js_newer["newer"],
            "tie": tie["newer"],
            "assumed_json": False,
            "mutant_assumes_json": mutant["assumed_json"],
        },
        "signal_b_independent_of_id_set": True,
    }
    print(json.dumps(out, sort_keys=True))
    print(
        f"good_silent={both['good_silent']} "
        f"class_fires={both['classification_fires']} "
        f"licence_fires={both['licence_fires']} "
        f"family_fires={both['family_fires']} "
        f"newer_md={md_newer['newer']} newer_js={js_newer['newer']} tie={tie['newer']}"
    )
    print(
        f"SUCCESS:{UNIT}-probe2 field-drift both-states; commit-time newer-side; "
        "never assume JSON"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
