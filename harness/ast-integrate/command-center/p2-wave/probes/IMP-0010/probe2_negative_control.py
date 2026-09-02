#!/usr/bin/env python3
"""Probe 2: drop one manifest entry → exactly one predicted path vanishes.

Also proves the projection consumes the two generators rather than restating
their destination templates.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools" / "plugin"))
import projection_map as pm  # noqa: E402

ART = REPO / "command-center" / "receipts" / "IMP-0010.json"
PROJ = REPO / "tools" / "plugin" / "projection_map.py"


def main() -> int:
    src = PROJ.read_text(encoding="utf-8")
    if "emit_hook_manifest" not in src or "gen_skills_manifest" not in src:
        print("FAILED:IMP-0010-probe2 projection does not import the generators")
        return 1
    if ".claude/hooks/_dispatch" in src or ".claude/skills" in src:
        print("FAILED:IMP-0010-probe2 projection duplicates generator live-path templates")
        return 1
    hook_src = (REPO / "ci" / "emit_hook_manifest.py").read_text(encoding="utf-8")
    skill_src = (REPO / "ci" / "gen_skills_manifest.py").read_text(encoding="utf-8")
    if "hooks" not in hook_src or "_dispatch" not in hook_src:
        print("FAILED:IMP-0010-probe2 hook generator missing dispatch template")
        return 1
    if "skills" not in skill_src or "SKILL.md" not in skill_src:
        print("FAILED:IMP-0010-probe2 skill generator missing SKILL.md template")
        return 1

    bundle = pm.load_bundle(REPO)
    removed_name = bundle["skills"]["skills"][0]["name"]
    mutated = pm.drop_entry(bundle, "skill", removed_name)
    with tempfile.TemporaryDirectory(prefix="imp0010-p2-") as tmp:
        home = Path(tmp)
        before = set(pm.predict(bundle, home))
        after = set(pm.predict(mutated, home))
        gone = before - after
        added = after - before
        if len(gone) != 1 or added:
            print(
                json.dumps(
                    {"gone": sorted(gone), "added": sorted(added), "before": len(before), "after": len(after)},
                    indent=2,
                )
            )
            print("FAILED:IMP-0010-probe2 expected exactly one predicted path to disappear")
            return 1
        disappeared = next(iter(gone))
        if not disappeared.endswith(f"/skills/{removed_name}/SKILL.md"):
            print(f"FAILED:IMP-0010-probe2 wrong path vanished: {disappeared}")
            return 1
        actual = set(pm.dry_run(mutated, home))
        if actual != after:
            print("FAILED:IMP-0010-probe2 mutated dry-run != mutated prediction")
            return 1

    if ART.is_file():
        text = ART.read_text(encoding="utf-8")
        if "SUCCESS:IMP-0010" not in text:
            print("FAILED:IMP-0010-probe2 receipt sentinel absent")
            return 1
        doc = json.loads(text)
        if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
            print("FAILED:IMP-0010-probe2 receipt blocked")
            return 1

    print(
        json.dumps(
            {
                "probe": "probe2-negative-control",
                "unit_id": "IMP-0010",
                "removed_entry": removed_name,
                "paths_removed": 1,
                "disappeared": disappeared,
                "consumes_generators": True,
                "duplicates_templates": False,
                "pass": True,
            },
            sort_keys=True,
        )
    )
    print("SUCCESS:IMP-0010-probe2 exactly one predicted path disappeared")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
