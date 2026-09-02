#!/usr/bin/env python3
"""Probe 2: nearest-sibling differential, overclaim, silent-override negative control."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import instantiate as I  # noqa: E402

ART = (
    REPO
    / "command-center/design/council/CNL-0112-forecasting-and-expert-elicitation-preset-with-a-proper-sc.md"
)


def fail(msg: str) -> int:
    print(f"FAILED:CNL-0112-probe2 {msg}")
    return 1


def main() -> int:
    if not ART.is_file():
        return fail("artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    task = I.load_json(I.TASK)
    sibling_raw = I.load_json(I.SIBLING)

    live = I.instantiate(I.CNL_0112_PRESET, task)
    sib = I.instantiate(I.sibling_as_preset(sibling_raw), task)
    axes = I.differ_axes(live, sib)
    print(f"sibling_id={sibling_raw['id']} differ_axes={axes} n={len(axes)}")
    if len(axes) < 3:
        return fail(f"profile not measurably different n={len(axes)}")

    named = doc.get("nearest_sibling") or {}
    if named.get("named") is not True:
        return fail("nearest sibling not named")
    if named.get("id") != sibling_raw["id"]:
        return fail(f"sibling id mismatch {named.get('id')}")
    rec_axes = (doc.get("sibling_instantiation") or {}).get("differ_axes") or []
    if sorted(rec_axes) != sorted(axes):
        return fail(f"recorded axes {rec_axes} != live {axes}")

    lib_live = I.library_on_disk()
    lib_doc = doc.get("library") or {}
    if lib_doc.get("on_this_worktree") != lib_live["on_this_worktree"]:
        return fail("library.on_this_worktree does not match disk")
    if lib_live["on_this_worktree"]:
        return fail("library present; this probe expected absence and must not invent a 72-count")
    if lib_doc.get("presets_compared_from_disk") not in (0, None):
        return fail("overclaim: presets_compared_from_disk > 0 while library absent")
    if named.get("library_bytes_read") is not False:
        return fail("overclaim: nearest_sibling.library_bytes_read is not false")
    blob = ART.read_text(encoding="utf-8")
    forbidden = (
        "read 72 presets from disk",
        "12-COUNCIL-PROTOCOLS-AND-PRESETS.json was read from disk on this worktree",
    )
    for phrase in forbidden:
        if phrase in blob:
            return fail(f"overclaim phrase present: {phrase}")

    bad = I.instantiate(
        I.CNL_0112_PRESET,
        task,
        overrides={"scoring.primary_rule": "linear_probability_score"},
    )
    print(f"silent_override accepted={bad.get('ok')} reject={bad.get('reject')}")
    if bad.get("ok") is True:
        return fail("silent override of non-editable scoring.primary_rule was accepted")
    if (bad.get("reject") or {}).get("reason") != "silent-override-of-non-editable-dial":
        return fail("override reject reason mismatch")

    rev = doc.get("reviewer") or {}
    if rev.get("independent") is not True:
        return fail("reviewer not independent")
    if "probe2" not in str(rev.get("reviewer_id") or ""):
        return fail("reviewer_id is not the probe2 reviewer")

    print("negative_control NC-silent-non-editable-override FIRES on scoring.primary_rule=linear; SILENT on editable stopping.max_rounds")
    ok_edit = I.instantiate(
        I.CNL_0112_PRESET,
        task,
        overrides={"stopping.max_rounds": 8},
    )
    if not ok_edit.get("ok"):
        return fail("editable dial stopping.max_rounds was rejected")
    print("SUCCESS:CNL-0112-probe2 sibling-differential overclaim silent-override")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
