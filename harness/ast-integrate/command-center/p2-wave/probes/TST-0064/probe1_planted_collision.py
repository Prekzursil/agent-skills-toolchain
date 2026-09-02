#!/usr/bin/env python3
"""Probe 1: detector finds a planted case collision in a scratch git repo.

Both-states: colliding Foo.md/foo.md FIRES; non-colliding README.md vs
docs/readme.md is SILENT. A string-comparing exact-path control stays
silent on the planted pair (detector control for the hole).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import detector as D  # noqa: E402

ART = REPO / "command-center/receipts/TST-0064.json"
UNIT = "TST-0064"


def fail(msg: str) -> int:
    print(f"FAILED:TST-0064-probe1 {msg}")
    return 1


def main() -> int:
    control = D.both_states_control()
    hit = control["gate_on_plant"]
    clean = control["gate_on_clean"]
    naive = control["naive_exact_on_plant"]
    print(
        json.dumps(
            {
                "probe": "probe1-planted-collision",
                "unit_id": UNIT,
                "gate_fired_on_plant": hit["fired"],
                "gate_silent_on_clean": clean["silent"],
                "xor": control["fired_in_exactly_one_condition"],
                "git_ls_files_contains_planted_pair": control[
                    "git_ls_files_contains_planted_pair"
                ],
                "naive_exact_silent_on_plant": naive["silent"],
                "plant_collision_group_count": control["colliding"][
                    "collision_group_count"
                ],
                "clean_collision_group_count": control["clean"][
                    "collision_group_count"
                ],
                "plant_source": control["colliding"]["source"],
                "tracked_on_plant": control["tracked_on_plant"],
            },
            sort_keys=True,
        )
    )
    if control["colliding"]["source"] != "git-ls-files":
        return fail(f"scratch plant source={control['colliding']['source']} want git-ls-files")
    if not control["git_ls_files_contains_planted_pair"]:
        return fail("git ls-files did not contain both planted paths")
    if not hit["fired"]:
        return fail("casefold gate silent on planted Foo.md/foo.md")
    if int(control["colliding"]["collision_group_count"]) < 1:
        return fail("plant collision_group_count < 1")
    planted = {D.PLANTED_UPPER, D.PLANTED_LOWER}
    found = False
    for group in control["colliding"]["collisions"]:
        if planted.issubset(set(group.get("paths") or [])):
            found = True
            break
    if not found:
        return fail("planted pair missing from collision groups")
    if not clean["silent"]:
        return fail("casefold gate fired on clean non-colliding pair")
    if int(control["clean"]["path_count"]) < 2:
        return fail("clean scratch listed fewer than 2 paths")
    if not naive["silent"]:
        return fail("exact-string control fired on planted pair (control is broken)")
    if naive["fired"]:
        return fail("exact-string control must be blind to casefold pairs")
    if not control["fired_in_exactly_one_condition"]:
        return fail("control silent-in-both or fire-in-both")

    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")
    if "SUCCESS:TST-0064" not in ART.read_text(encoding="utf-8"):
        return fail("sentinel absent")
    ext = doc.get("extensions") if isinstance(doc.get("extensions"), dict) else {}
    both = ext.get("both_states") or doc.get("both_states") or {}
    if both.get("fired_in_exactly_one_condition") is not True:
        return fail("artifact both_states xor is not true")
    if both.get("naive_exact_silent_on_plant") is not True:
        return fail("artifact did not record naive-exact blindness")
    if both.get("git_ls_files_contains_planted_pair") is not True:
        return fail("artifact did not record git ls-files plant")
    print("SUCCESS:TST-0064-probe1 planted case collision fires; clean pair silent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
