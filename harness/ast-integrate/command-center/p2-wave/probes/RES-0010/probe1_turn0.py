#!/usr/bin/env python3
"""Probe 1: two fixture skills at turn 0 + live client source needle.

Required test: install two fixture skills (one with paths:, one without) and
record which is present at turn 0.

Second independent signal: the installed cursor-agent index.js still contains
the `paths??globs` and alwaysApply classifiers (different data field: source
text vs classified fixture records).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from observe import classify_all  # noqa: E402

OUT = HERE / "probe1-turn0.raw.json"


def main() -> int:
    snap = classify_all()
    OUT.write_text(json.dumps(snap, indent=2) + "\n", encoding="utf-8")
    client = snap["client"]
    if not client["exists"] or not client["needle_skill_paths"] or not client["needle_always_apply"]:
        print("FAILED:RES-0010-probe1 live client needles absent")
        return 1
    skills = {s["name"]: s for s in snap["skills"]}
    no_paths = skills.get("res0010-skill-no-paths")
    with_paths = skills.get("res0010-skill-with-paths")
    if not no_paths or not with_paths:
        print("FAILED:RES-0010-probe1 fixture skills missing")
        return 1
    obs = {o["id"]: o for o in snap["observations_matching_touch"] if o["kind"] == "skill"}
    n0 = obs["res0010-skill-no-paths"]
    p0 = obs["res0010-skill-with-paths"]
    # Direct instrument: both are catalog-present at turn 0; neither body-injected.
    if n0["turn0_catalog"] != "loaded" or p0["turn0_catalog"] != "loaded":
        print("FAILED:RES-0010-probe1 catalog presence not recorded", n0, p0)
        return 1
    if n0["turn0_body"] != "not-loaded" or p0["turn0_body"] != "not-loaded":
        print("FAILED:RES-0010-probe1 body injection at t0 not recorded", n0, p0)
        return 1
    if not with_paths["paths_key_present"] or no_paths["paths_key_present"]:
        print("FAILED:RES-0010-probe1 paths: fixture polarity wrong")
        return 1
    if not with_paths["globs"]:
        print("FAILED:RES-0010-probe1 paths: not copied into globs")
        return 1
    if no_paths["globs"]:
        print("FAILED:RES-0010-probe1 no-paths skill unexpectedly globbed")
        return 1
    print(
        "client_version="
        + str(client["version"])
        + " sha_match="
        + str(client["sha256_match"])
        + " offset_paths="
        + str(client["offset_skill_paths"])
        + " skill_no_paths_t0_catalog="
        + n0["turn0_catalog"]
        + " skill_no_paths_t0_body="
        + n0["turn0_body"]
        + " skill_with_paths_t0_catalog="
        + p0["turn0_catalog"]
        + " skill_with_paths_t0_body="
        + p0["turn0_body"]
        + " builtin_n="
        + str(len(snap["builtin_skills"]))
    )
    print("SUCCESS:RES-0010-probe1 turn-0 loaded/not-loaded per fixture skill")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
