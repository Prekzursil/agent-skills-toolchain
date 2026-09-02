#!/usr/bin/env python3
"""Probe 2: both-states matching-touch control + inverted-arming mutant.

Required test: touching a matching path must load the paths:-scoped *rule*
(globs analog) and only then. A non-matching touch must not. A mutant that
treats missing paths as never-loaded and paths: as always-on (the wrong
arming assumption) must disagree with the instrument on the two fixture skills.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from observe import claimed_claude_code_inversion, classify_all  # noqa: E402

OUT = HERE / "probe2-both-states.raw.json"


def main() -> int:
    snap = classify_all()
    match = {o["id"]: o for o in snap["observations_matching_touch"]}
    nomatch = {o["id"]: o for o in snap["observations_nonmatching_touch"]}
    glob_rule = match.get("glob-scoped.mdc")
    glob_rule_no = nomatch.get("glob-scoped.mdc")
    paths_key = match.get("paths-key-only.mdc")
    always = match.get("always-on.mdc")
    desc = match.get("desc-only.mdc")
    no_fm = match.get("no-frontmatter.mdc")
    skill_lazy = match.get("res0010-skill-with-paths")
    skill_always = match.get("res0010-skill-no-paths")
    skill_lazy_no = nomatch.get("res0010-skill-with-paths")

    failed: list[str] = []
    if not glob_rule or glob_rule["turn0_body"] != "not-loaded":
        failed.append("glob-rule-t0-body")
    if not glob_rule or glob_rule["after_touch_body"] != "loaded":
        failed.append("glob-rule-match-body")
    if not glob_rule_no or glob_rule_no["after_touch_body"] != "not-loaded":
        failed.append("glob-rule-nonmatch-body")
    if not always or always["turn0_body"] != "loaded":
        failed.append("always-on-t0")
    if not desc or desc["turn0_body"] != "not-loaded" or desc["turn0_catalog"] != "loaded":
        failed.append("desc-only-agentFetched")
    if not no_fm or no_fm["turn0_body"] != "not-loaded" or no_fm["turn0_catalog"] != "not-loaded":
        failed.append("no-frontmatter-manual")
    # Claude Code paths: key on a Cursor .mdc does NOT fileGlob.
    if not paths_key or paths_key["rule_type"] == "fileGlobbed":
        failed.append("paths-key-must-not-fileGlob")
    if not paths_key or paths_key["after_touch_body"] != "not-loaded":
        failed.append("paths-key-must-not-load-on-touch")
    # Skills: matching touch does not inject body (CLI ls() ignores paths).
    if not skill_lazy or skill_lazy["after_touch_body"] != "not-loaded":
        failed.append("skill-paths-body-still-not-injected")
    if not skill_lazy_no or skill_lazy_no["after_touch_body"] != "not-loaded":
        failed.append("skill-paths-nonmatch")
    if not skill_always or skill_always["turn0_body"] != "not-loaded":
        failed.append("skill-no-paths-body-not-always-on")

    # Catalog inversion must disagree with the instrument (not silent on Cursor).
    skills = {s["name"]: s for s in snap["skills"]}
    mutant_hits = 0
    for name in ("res0010-skill-no-paths", "res0010-skill-with-paths"):
        rec = skills[name]
        live = match[name]
        claimed = claimed_claude_code_inversion(rec)
        if (
            claimed["turn0_body"] != live["turn0_body"]
            or claimed["after_touch_body"] != live["after_touch_body"]
        ):
            mutant_hits += 1
    if mutant_hits < 2:
        failed.append("claimed-inversion-silent")

    OUT.write_text(
        json.dumps(
            {
                "matching": match,
                "nonmatching": nomatch,
                "failed": failed,
                "mutant_hits": mutant_hits,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    if failed:
        print("FAILED:RES-0010-probe2 " + ",".join(failed))
        return 1
    print(
        "glob_t0="
        + glob_rule["turn0_body"]
        + " glob_match="
        + glob_rule["after_touch_body"]
        + " glob_nonmatch="
        + glob_rule_no["after_touch_body"]
        + " paths_key_type="
        + str(paths_key["rule_type"])
        + " skill_paths_t0_body="
        + skill_lazy["turn0_body"]
        + " skill_paths_after_match_body="
        + skill_lazy["after_touch_body"]
        + " skill_no_paths_t0_body="
        + skill_always["turn0_body"]
        + " mutant_hits="
        + str(mutant_hits)
    )
    print("SUCCESS:RES-0010-probe2 both-states matching-touch control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
