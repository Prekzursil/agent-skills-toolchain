#!/usr/bin/env python3
"""Probe 2: independent unique-line differ + reviewer unanticipated edit.

Catalog evidence (2): byte-level comparison of the user's unique lines before
and after, computed by unique_line_differ (does not import three_way_merge).
An existence check would pass a truncated file; the census hash would not.

NEGATIVE CONTROL: the same upgrade with the classifier disabled drops unique
lines (fired_on_bad) while the classified path keeps them (silent_on_good).

Reviewer: reordered JSON keys plus a comment the default override did not plant.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
PLUGIN = REPO / "tools" / "plugin"
sys.path.insert(0, str(PLUGIN))

import unique_line_differ as differ  # noqa: E402
import update as upd  # noqa: E402

ART = REPO / "command-center/receipts/IMP-0024.json"
UNIT = "IMP-0024"


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        print("FAILED:IMP-0024-probe2 receipt missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    if "SUCCESS:IMP-0024" not in text:
        print("FAILED:IMP-0024-probe2 sentinel absent")
        return 1

    v1, v2 = upd.payload_v1(), upd.payload_v2()
    with tempfile.TemporaryDirectory(prefix="imp0024-p2-") as td:
        good = Path(td) / "classified"
        upd.seed_live_tree(good, v1, version="1.0.0")
        ours = upd.apply_user_override(good)
        pre_unique = differ.unique_ours_lines(v1["notes.md"], ours["notes.md"])
        if not pre_unique:
            print("FAILED:IMP-0024-probe2 no unique ours lines planted")
            return 1
        r_good = upd.update(
            good,
            base_payload=v1,
            theirs_payload=v2,
            from_version="1.0.0",
            to_version="1.1.0",
            classifier_enabled=True,
        )
        if not r_good.proceeded:
            print("FAILED:IMP-0024-probe2 classified update refused")
            return 1
        after_good = (good / "notes.md").read_bytes()
        census_good = differ.census(v1["notes.md"], ours["notes.md"], after_good)
        try:
            differ.assert_unique_lines_survive(v1["notes.md"], ours["notes.md"], after_good)
        except AssertionError as exc:
            print("FAILED:IMP-0024-probe2 unique lines missing on classified path")
            print(exc)
            return 1
        if census_good["unique_sha256"] != census_good["present_sha256"]:
            print("FAILED:IMP-0024-probe2 unique-line census hash diverged")
            return 1
        # Truncation detector: a file that still exists but lost unique lines.
        truncated = b"# notes\nshipped-v2\n"
        census_trunc = differ.census(v1["notes.md"], ours["notes.md"], truncated)
        if census_trunc["all_unique_present"] or not census_trunc["missing_count"]:
            print("FAILED:IMP-0024-probe2 truncated twin was not distinguished")
            return 1

        bad = Path(td) / "no-classifier"
        upd.seed_live_tree(bad, v1, version="1.0.0")
        ours_bad = upd.apply_user_override(bad)
        r_bad = upd.update(
            bad,
            base_payload=v1,
            theirs_payload=v2,
            from_version="1.0.0",
            to_version="1.1.0",
            classifier_enabled=False,
        )
        if not r_bad.proceeded:
            print("FAILED:IMP-0024-probe2 negative control did not run")
            return 1
        after_bad = (bad / "notes.md").read_bytes()
        census_bad = differ.census(v1["notes.md"], ours_bad["notes.md"], after_bad)
        fired_on_bad = census_bad["all_unique_present"] is False
        silent_on_good = census_good["all_unique_present"] is True
        if not fired_on_bad or not silent_on_good:
            print("FAILED:IMP-0024-probe2 negative control both-states failed")
            print(json.dumps({"good": census_good, "bad": census_bad}, indent=2))
            return 1

        reviewer = Path(td) / "reviewer"
        upd.seed_live_tree(reviewer, v1, version="1.0.0")
        ours_r = upd.apply_reviewer_unanticipated(reviewer)
        r_rev = upd.update(
            reviewer,
            base_payload=v1,
            theirs_payload=v2,
            from_version="1.0.0",
            to_version="1.1.0",
        )
        if not r_rev.proceeded:
            print("FAILED:IMP-0024-probe2 reviewer edit caused a stop")
            print(json.dumps(r_rev.as_dict(), default=str)[:2000])
            return 1
        rev_settings_text = (reviewer / "settings.json").read_text(encoding="utf-8")
        rev_settings = upd.parsed_settings(reviewer)
        rev_notes = (reviewer / "notes.md").read_bytes()
        key_order_ok = list(rev_settings.keys())[:2] == ["font", "theme"]
        comment_in_json = "reviewer: key order is load-bearing" in rev_settings_text
        comment_in_notes = upd.REVIEWER_COMMENT_LINE.encode("ascii") in rev_notes
        differ.assert_unique_lines_survive(v1["notes.md"], ours_r["notes.md"], rev_notes)
        if not (key_order_ok and comment_in_json and comment_in_notes):
            print("FAILED:IMP-0024-probe2 reviewer reorder/comment did not survive")
            print(json.dumps({
                "keys": list(rev_settings.keys()),
                "json": rev_settings_text,
                "notes": rev_notes.decode("utf-8"),
            }))
            return 1
        if rev_settings.get("telemetry") is not False:
            print("FAILED:IMP-0024-probe2 reviewer merge dropped upstream key")
            return 1

        conflicted = Path(td) / "conflict"
        upd.seed_live_tree(conflicted, v1, version="1.0.0")
        upd.apply_user_theme_conflict(conflicted)
        before = upd.tree_sha(conflicted)
        r_c = upd.update(
            conflicted,
            base_payload=v1,
            theirs_payload=upd.payload_conflict_theirs(),
            from_version="1.0.0",
            to_version="1.1.0",
        )
        if r_c.proceeded or r_c.wrote or upd.tree_sha(conflicted) != before:
            print("FAILED:IMP-0024-probe2 conflicted update mutated the tree")
            return 1

    out = {
        "probe": "probe2-unique-line-differ",
        "unit_id": UNIT,
        "pass": True,
        "differ_module": "tools/plugin/unique_line_differ.py",
        "imports_three_way_merge": False,
        "unique_ours_lines_before": [ln.decode("utf-8") for ln in pre_unique],
        "census_classified": census_good,
        "census_truncated_control": {
            "all_unique_present": census_trunc["all_unique_present"],
            "missing_count": census_trunc["missing_count"],
            "truncated": census_trunc["truncated"] or census_trunc["missing_count"] > 0,
        },
        "fired_on_bad": fired_on_bad,
        "silent_on_good": silent_on_good,
        "reviewer": {
            "constructed": "reordered JSON keys (font before theme) plus a JSONC comment and a notes.md comment",
            "key_order": list(rev_settings.keys()),
            "jsonc_comment_survived": comment_in_json,
            "notes_comment_survived": comment_in_notes,
            "upstream_telemetry_landed": True,
        },
        "conflicted_wrote_nothing": True,
        "two_independent_signals": True,
    }
    print(json.dumps(out, indent=2, sort_keys=True))
    print("SUCCESS:IMP-0024-probe2 unique-line differ + negative control + reviewer edit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
