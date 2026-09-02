#!/usr/bin/env python3
"""Named probe 2: independent live-tree walk + hand-edit negative control.

Catalog signal (2): an independently written directory walk finds zero
deployed files lacking a provenance record. Combined with probe 1's
cat-file check, both directions are covered.

NEGATIVE CONTROL: hand-edit one deployed file; verification names exactly
that file as unverified. BOTH-STATES: the same walk is silent on the
pre-edit tree.

Reviewer gate: AST check that place_file is the sole live-tree writer.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
PLUGIN = REPO / "tools" / "plugin"
sys.path.insert(0, str(PLUGIN))

import deploy_provenance as dp  # noqa: E402

ART = REPO / "command-center/receipts/IMP-0033.json"
SENTINEL = "SUCCESS:IMP-0033"

# Independent of dp.FAMILIES / dp.walk_live_family_files.
LIVE_ROOTS = (
    ".claude/skills",
    ".claude/hooks",
    ".claude/rules",
)


def independent_walk(home: Path) -> list[str]:
    found: list[str] = []
    for rel in LIVE_ROOTS:
        root = home / rel
        if not root.is_dir():
            continue
        for dirpath, _, filenames in os.walk(root):
            for name in sorted(filenames):
                path = Path(dirpath) / name
                if not path.is_file():
                    continue
                found.append(path.relative_to(home).as_posix())
    return sorted(found)


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        print("FAILED:IMP-0033-probe2 receipt missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    if SENTINEL not in text:
        print("FAILED:IMP-0033-probe2 sentinel absent")
        return 1

    gate = dp.live_write_callees()
    if not gate.get("place_file_is_sole_live_writer"):
        print("FAILED:IMP-0033-probe2 live write outside place_file")
        print(json.dumps(gate, indent=2))
        return 1

    with tempfile.TemporaryDirectory(prefix="imp0033-p2-") as td:
        root = Path(td)
        src = root / "src"
        home = root / "home"
        home.mkdir()
        planted = dp.plant_throwaway_plugin(src)
        git_dir = Path(planted["git_dir"])
        dp.deploy_all_via_scripts(repo=src, home=home, git_dir=git_dir, worktree=REPO)

        ledger_doc = json.loads((home / ".claude/deploy-provenance.json").read_text(encoding="utf-8"))
        recorded = sorted(r["live_path"] for r in ledger_doc["records"])
        walked = independent_walk(home)
        missing_record = sorted(set(walked) - set(recorded))
        missing_file = sorted(set(recorded) - set(walked))
        if missing_record or missing_file:
            print(
                json.dumps(
                    {"missing_record": missing_record, "missing_file": missing_file},
                    indent=2,
                )
            )
            print("FAILED:IMP-0033-probe2 walk/ledger disagree")
            return 1
        if len(walked) != planted["n_deployable"]:
            print(
                f"FAILED:IMP-0033-probe2 walk={len(walked)} "
                f"want={planted['n_deployable']}"
            )
            return 1

        before = dp.verify_deployed(home, git_dir)
        if not before.clean:
            print("FAILED:IMP-0033-probe2 pre-edit not clean")
            print(json.dumps(before.as_dict(), indent=2))
            return 1

        target = home / ".claude/skills/bravo/SKILL.md"
        original = target.read_bytes()
        target.write_bytes(original + b"PROBE2-HAND-EDIT\n")
        after = dp.verify_deployed(home, git_dir)
        if after.unverified != [".claude/skills/bravo/SKILL.md"]:
            print("FAILED:IMP-0033-probe2 hand-edit did not name exactly bravo")
            print(json.dumps(after.as_dict(), indent=2))
            return 1
        if after.missing_record or after.missing_file:
            print("FAILED:IMP-0033-probe2 hand-edit disturbed completeness")
            return 1
        if ".claude/skills/bravo/SKILL.md" in after.verified:
            print("FAILED:IMP-0033-probe2 edited file still verified")
            return 1
        if len(after.verified) != planted["n_deployable"] - 1:
            print("FAILED:IMP-0033-probe2 other files did not stay verified")
            return 1

        # Restore: good-state walk still complete (both-states).
        target.write_bytes(original)
        restored = dp.verify_deployed(home, git_dir)
        if not restored.clean:
            print("FAILED:IMP-0033-probe2 restore did not return to clean")
            return 1

    out = {
        "probe": "probe2-walk-and-handedit",
        "unit_id": "IMP-0033",
        "pass": True,
        "walk_count": len(walked),
        "ledger_count": len(recorded),
        "missing_record": missing_record,
        "missing_file": missing_file,
        "pre_edit_clean": True,
        "hand_edit_unverified": after.unverified,
        "hand_edit_exact": True,
        "restored_clean": True,
        "place_file_is_sole_live_writer": True,
        "reviewer": "AST: _atomic_write callers == [place_file]",
        "method": "independent os.walk of .claude/{skills,hooks,rules} vs ledger keys",
    }
    print(json.dumps(out, indent=2, sort_keys=True))
    print("SUCCESS:IMP-0033-probe2 walk complete; hand-edit names exactly one file")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
