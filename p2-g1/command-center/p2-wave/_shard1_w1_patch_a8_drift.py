#!/usr/bin/env python3
"""Shard1-w1 fix cycle 1: repair stale Linux-worktree premises in A8 units.

The dead prior builder authored ARC-0054/ARC-0055 on a headless Linux
worktree where command-center/phase3/A8/DESIGN.json (ARC-0052 deliverable)
was absent. On this estate that artifact EXISTS as a delivered ARC-0052
receipt, so absence-guards fail and artifact prose states a falsehood.
This patch: (1) re-points the planted trap NEXT at a guaranteed-absent
fixture path, (2) converts absence-guards to ARC-0052 ownership guards,
(3) corrects the false prose. Every replacement must match exactly once.
"""
import sys
from pathlib import Path

REPO = Path("C:/Users/Prekzursil/p2-g1")
NL = chr(10)
PATCHES = []


def rep(rel, old_lines, new_lines):
    PATCHES.append((rel, NL.join(old_lines), NL.join(new_lines)))


rep("command-center/p2-wave/probes/ARC-0054/criteria.py",
    ['        "NEXT: python3 command-center/phase3/A8/DESIGN.json"'],
    ['        "NEXT: python3 command-center/phase3/A8/__arc0054_trap_absent_fixture__.json"'])

rep("command-center/p2-wave/probes/ARC-0054/reviewer.py",
    ['        "error_names_next_action greets any command-like NEXT line as a pass. "',
     '        "NEXT: python3 command-center/phase3/A8/DESIGN.json satisfies that regex "',
     '        "while DESIGN.json is absent on this worktree, so the owner still has "',
     '        "no executable next action. Shape is not reachability."'],
    ['        "error_names_next_action greets any command-like NEXT line as a pass. "',
     '        "NEXT: python3 command-center/phase3/A8/__arc0054_trap_absent_fixture__.json "',
     '        "satisfies that regex while the fixture path is guaranteed absent on any "',
     '        "worktree, so the owner still has no executable next action. "',
     '        "Shape is not reachability."'])

rep("command-center/p2-wave/probes/ARC-0054/emit_failure_modes.py",
    ['    "quoting a stale dollar cost. A8 DESIGN.json is also absent, so this unit "'],
    ['    "quoting a stale dollar cost. A8 DESIGN.json is the ARC-0052 receipt, so this unit "'])

rep("command-center/p2-wave/probes/ARC-0054/emit_failure_modes.py",
    ['        "design_present": False,'],
    ['        "design_present": (REPO / "command-center/phase3/A8/DESIGN.json").is_file(),'])

rep("command-center/p2-wave/probes/ARC-0054/emit_failure_modes.py",
    ['        "design_note": (',
     '            "A8 DESIGN.json is absent (ARC-0052 not delivered). This unit does "',
     '            "not rebuild A8 DESIGN. Claims about an A8 dossier are SENTENCE, "',
     '            "not DESIGN. Live pairing uses A1 DESIGN, the work-unit catalog, "',
     '            "and the G-1 measure printer."',
     '        ),'],
    ['        "design_note": (',
     '            "A8 DESIGN.json is present as the ARC-0052 delivered receipt "',
     '            "(a8-error/v1 for the cockpit surface). This unit does not rebuild "',
     '            "it. That receipt encodes no executable predicate for the five "',
     '            "catalog-named UX modes, so those claims stay SENTENCE-locus "',
     '            "overclaims. Live pairing uses A1 DESIGN, the work-unit catalog, "',
     '            "and the G-1 measure printer."',
     '        ),'])

rep("command-center/p2-wave/probes/ARC-0054/emit_failure_modes.py",
    ['                "A8 DESIGN.json is not the catching artifact on this tree "',
     '                "because it is absent."'],
    ['                "A8 DESIGN.json (the ARC-0052 receipt, a8-error/v1) is not the "',
     '                "catching artifact: it encodes no predicate for these five modes."'])

rep("command-center/p2-wave/probes/ARC-0054/emit_failure_modes.py",
    ['                "why_locus": (',
     '                    "command-center/phase3/A8/DESIGN.json is absent. A missing "',
     '                    "dossier cannot be a DESIGN locus."',
     '                ),'],
    ['                "why_locus": (',
     '                    "command-center/phase3/A8/DESIGN.json is present as the "',
     '                    "ARC-0052 receipt but states a8-error/v1 for the cockpit "',
     '                    "surface, not the five UX predicates of this unit; the "',
     '                    "claim overstates what the delivered DESIGN states."',
     '                ),'])

rep("command-center/p2-wave/probes/ARC-0054/emit_failure_modes.py",
    ['                "scoped_restatement": (',
     '                    "The contract is pinned by the ARC-0052 catalog sentence "',
     '                    "(happened / means / exact next action), not by an A8 dossier."',
     '                ),'],
    ['                "scoped_restatement": (',
     '                    "The contract this unit uses is pinned by its own scripted "',
     '                    "criteria and the ARC-0052 catalog sentence pattern; the "',
     '                    "delivered A8 DESIGN receipt (a8-error/v1) covers the "',
     '                    "cockpit surface, not these five modes."',
     '                ),'])

rep("command-center/p2-wave/probes/ARC-0055/decisions.py",
    ['        "a8_design_present": design.is_file(),'],
    ['        "a8_design_present": design.is_file(),',
     '        "a8_design_owned_by_dependency": _a8_design_owned(design),'])

rep("command-center/p2-wave/probes/ARC-0055/emit_security.py",
    ['    if clf["a8_design_present"]:',
     '        print("FAILED:ARC-0055 emit unexpectedly found A8 DESIGN.json")',
     '        return 1'],
    ['    if clf["a8_design_present"] and not clf.get("a8_design_owned_by_dependency"):',
     '        print("FAILED:ARC-0055 emit found A8 DESIGN.json without ARC-0052 ownership")',
     '        return 1'])

rep("command-center/p2-wave/probes/ARC-0055/emit_security.py",
    ['            "A8 DESIGN.json absent; not rebuilt. SUCCESS:ARC-0055"'],
    ['            "A8 DESIGN.json cited (ARC-0052 receipt), not rebuilt. SUCCESS:ARC-0055"'])

rep("command-center/p2-wave/probes/ARC-0055/emit_security.py",
    ['        "a8_design": {',
     '            "path": "command-center/phase3/A8/DESIGN.json",',
     '            "present": False,',
     '            "required_fix_if_blocked": "ARC-0052 DESIGN.json",',
     '            "rebuilt": False,',
     '            "note": "Missing DESIGN is a REFUTED DESIGN-locus claim, not a park. No ADV rebuild.",',
     '        },'],
    ['        "a8_design": {',
     '            "path": "command-center/phase3/A8/DESIGN.json",',
     '            "present": clf["a8_design_present"],',
     '            "owned_by_dependency": clf.get("a8_design_owned_by_dependency", False),',
     '            "required_fix_if_blocked": "ARC-0052 DESIGN.json",',
     '            "rebuilt": False,',
     '            "note": "A8 DESIGN.json is the ARC-0052 delivered receipt when present; cited, never rebuilt. It carries no DEFAULTED/EXPLICIT classification, so C2 stays REFUTED. No ADV rebuild.",',
     '        },'])

rep("command-center/p2-wave/probes/ARC-0055/emit_security.py",
    ['                "scoped_restatement": (',
     '                    "Classification is computed from live catalog + marketplace "',
     '                    "schema + session transcripts on this tree. A8 DESIGN.json "',
     '                    "is absent and was not rebuilt."',
     '                ),'],
    ['                "scoped_restatement": (',
     '                    "Classification is computed from live catalog + marketplace "',
     '                    "schema + session transcripts on this tree. A8 DESIGN.json "',
     '                    "is the ARC-0052 delivered receipt; it carries no "',
     '                    "DEFAULTED/EXPLICIT classification and was not rebuilt here."',
     '                ),'])

rep("command-center/p2-wave/probes/ARC-0055/emit_security.py",
    ['    units. This unit must not rebuild them. A8 DESIGN stays absent.'],
    ['    units. This unit must not rebuild them. A8 DESIGN is the ARC-0052 receipt when present.'])

rep("command-center/p2-wave/probes/ARC-0055/probe1_blast_radius.py",
    ['    if live["a8_design_present"]:',
     '        print("FAILED:ARC-0055-probe1 A8 DESIGN present; this unit must not rebuild it")',
     '        return 1'],
    ['    if live["a8_design_present"] and not live.get("a8_design_owned_by_dependency"):',
     '        print("FAILED:ARC-0055-probe1 A8 DESIGN present without ARC-0052 ownership; possible rebuild")',
     '        return 1'])

rep("command-center/p2-wave/probes/ARC-0055/probe2_fatigue_overclaim.py",
    ['    if (doc.get("a8_design") or {}).get("present") is True:',
     '        print("FAILED:ARC-0055-probe2 A8 DESIGN overclaimed present")',
     '        return 1'],
    ['    ad = doc.get("a8_design") or {}',
     '    if ad.get("present") is True and ad.get("owned_by_dependency") is not True:',
     '        print("FAILED:ARC-0055-probe2 A8 DESIGN present without ARC-0052 ownership")',
     '        return 1'])

rep("command-center/p2-wave/probes/ARC-0055/overclaim.py",
    ['    if (doc.get("a8_design") or {}).get("present") is True:',
     '        return False, "a8-design-claimed-present"'],
    ['    ad = doc.get("a8_design") or {}',
     '    if ad.get("present") is True and ad.get("owned_by_dependency") is not True:',
     '        return False, "a8-design-present-without-arc-0052-ownership"'])

HELPER = NL.join([
    "def _a8_design_owned(path):",
    "    import json as _json",
    "    try:",
    "        if not path.is_file():",
    "            return False",
    "        doc = _json.loads(path.read_text(encoding=" + chr(34) + "utf-8" + chr(34) + "))",
    "    except (OSError, ValueError):",
    "        return False",
    '    return doc.get("unit_id") == "ARC-0052" and doc.get("state") == "SUCCESS"',
    "",
    "",
])


def main():
    failures = []
    for rel, old, new in PATCHES:
        p = REPO / rel
        text = p.read_text(encoding="utf-8")
        n = text.count(old)
        if n != 1:
            failures.append(rel + " match-count=" + str(n) + " old=" + old[:70])
            continue
        p.write_text(text.replace(old, new), encoding="utf-8", newline=NL)
        print("patched", rel, "::", old.strip().split(NL)[0][:70])
    dp = REPO / "command-center/p2-wave/probes/ARC-0055/decisions.py"
    dt = dp.read_text(encoding="utf-8")
    head = dt.split("def classify")[0]
    if "_a8_design_owned" not in head:
        idx = dt.index("def classify(")
        dp.write_text(dt[:idx] + HELPER + dt[idx:], encoding="utf-8", newline=NL)
        print("patched decisions.py :: inserted _a8_design_owned helper")
    else:
        print("decisions.py helper already present")
    if failures:
        for f in failures:
            print("FAILED:patch", f)
        return 1
    print("SUCCESS:patch all", len(PATCHES), "replacements applied")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
