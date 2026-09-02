#!/usr/bin/env python3
"""Probe 1: one negative case per skill-contract rule; conforming twins pass.

A both-states control: the same checker accepts the conforming pair and
rejects each malformed twin. A mutant that always returns ok is detected.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import contract as C  # noqa: E402
import fixtures as F  # noqa: E402

UNIT = "TST-0043"


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe1 {msg}")
    return 1


def always_ok_mutant(path: Path, *, tree_root: Path | None = None) -> C.SkillCheck:
    skill_id = path.parent.name
    rel = path.as_posix()
    if tree_root is not None:
        try:
            rel = path.relative_to(tree_root).as_posix()
        except ValueError:
            rel = path.as_posix()
    return C.SkillCheck(path=rel, skill_id=skill_id, ok=True, reasons=[], fields={})


def main() -> int:
    F.write_static_fixtures()
    with tempfile.TemporaryDirectory(prefix="tst0043-p1-") as td:
        root = Path(td)
        F.conforming_tree(root / "good")
        good = C.check_tree(root / "good")
        if len(good) != 2 or any(not g.ok for g in good):
            return fail(f"conforming tree not all ok: {[g.reasons for g in good]}")

        neg_results = []
        mutant_missed = []
        for skill_id, text, expected in F.NEGATIVES:
            case_root = root / "neg" / skill_id
            F.write_tree(case_root, {skill_id: text})
            checks = C.check_tree(case_root)
            if len(checks) != 1:
                return fail(f"{skill_id} expected 1 skill, got {len(checks)}")
            chk = checks[0]
            if chk.ok:
                return fail(f"{skill_id} unexpectedly ok")
            if expected not in chk.reasons:
                return fail(
                    f"{skill_id} expected {expected} in {chk.reasons}"
                )
            planted = case_root / "skills" / skill_id / "SKILL.md"
            mutant = always_ok_mutant(planted, tree_root=case_root)
            if mutant.ok:
                mutant_missed.append(skill_id)
            neg_results.append(
                {
                    "skill_id": skill_id,
                    "expected": expected,
                    "reasons": chk.reasons,
                    "ok": chk.ok,
                }
            )

        if not mutant_missed:
            return fail("always-ok mutant did not miss any negative (control broken)")
        if set(mutant_missed) != {n[0] for n in F.NEGATIVES}:
            return fail("always-ok mutant did not miss every negative")

        # Static fixtures must match the in-memory trees (evidence cites them).
        static_good = C.check_tree(F.STATIC / "conforming")
        if len(static_good) != 2 or any(not g.ok for g in static_good):
            return fail("static conforming fixtures failed")
        broken = C.check_skill_file(
            F.STATIC / "malformed/skills/broken-yaml/SKILL.md",
            tree_root=F.STATIC / "malformed",
        )
        if broken.ok or C.REASON_FRONTMATTER_UNPARSEABLE not in broken.reasons:
            return fail(f"static broken-yaml not unparseable: {broken.reasons}")
        no_fm = C.check_skill_file(
            F.STATIC / "malformed/skills/no-frontmatter/SKILL.md",
            tree_root=F.STATIC / "malformed",
        )
        if no_fm.ok or C.REASON_FRONTMATTER_ABSENT not in no_fm.reasons:
            return fail(f"static no-frontmatter not absent: {no_fm.reasons}")
        missing_name = C.check_skill_file(
            F.STATIC / "malformed/skills/missing-name/SKILL.md",
            tree_root=F.STATIC / "malformed",
        )
        if missing_name.ok or C.REASON_NAME_MISSING not in missing_name.reasons:
            return fail(f"static missing-name: {missing_name.reasons}")

        payload = {
            "probe": "probe1-contract-negatives",
            "unit_id": UNIT,
            "conforming_ok": [g.skill_id for g in good],
            "negative_count": len(neg_results),
            "negatives": neg_results,
            "always_ok_mutant_missed": sorted(mutant_missed),
            "both_states": True,
        }
        print(json.dumps(payload, indent=2, sort_keys=True))
        print(f"conforming={len(good)} negatives={len(neg_results)}")
        print("SUCCESS:TST-0043-probe1 negatives fire; conforming twins pass")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
