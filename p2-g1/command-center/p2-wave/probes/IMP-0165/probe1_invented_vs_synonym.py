"""IMP-0165 probe 1: invented role maps to UNKNOWN; known synonyms map; no nearest-neighbour snap.

Re-run: PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/IMP-0165/probe1_invented_vs_synonym.py
Both-states: a known synonym maps to its canonical role while invented names stay UNKNOWN
(no silent snapping). A difflib nearest-neighbour mutant snaps typo'd surfaces - production
must not; the AST control forbids fuzzy matching in role_extract.py.
"""
from __future__ import annotations

import ast
import difflib
import json
import sys
from pathlib import Path

W = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(W / "tools"))

from workflow_foundry.role_extract import SYNONYM_TABLE, UNKNOWN, normalize_role  # noqa: E402


def main() -> int:
    invented = [
        "floor-wax-auditor",
        "banana-steward",
        "quantum-shepherd",
        "IMP-0165-invented-zxqv",
    ]
    invented_rows = []
    for s in invented:
        got = normalize_role(s)
        invented_rows.append(
            {"surface": s, "got": got, "expected": UNKNOWN,
             "match": got == UNKNOWN, "snapped": got != UNKNOWN}
        )

    synonym_cases = [
        ("critic", "critic"),
        ("red team", "critic"),
        ("refuter", "critic"),
        ("RED-TEAM", "critic"),
        ("devil's advocate", "critic"),
        ("author", "proposer"),
    ]
    synonym_rows = []
    for s, c in synonym_cases:
        got = normalize_role(s)
        synonym_rows.append({"surface": s, "got": got, "expected": c, "match": got == c})

    traps = ["critical-path-owner", "red teammate", "referee-adjacent"]
    substring_trap_rows = []
    for s in traps:
        got = normalize_role(s)
        substring_trap_rows.append(
            {"surface": s, "got": got, "expected": UNKNOWN, "match": got == UNKNOWN}
        )

    # Nearest-neighbour mutant control: difflib snaps typos, production must not.
    vocab = sorted(set(list(SYNONYM_TABLE.keys()) + ["critic", "red team", "refuter"]))
    near_miss_rows = []
    for surface in ["critc", "refutr", "red teem"]:
        snap = difflib.get_close_matches(surface, vocab, n=1, cutoff=0.6)
        prod = normalize_role(surface)
        near_miss_rows.append(
            {
                "surface": surface,
                "production": prod,
                "production_unknown": prod == UNKNOWN,
                "nearest_neighbour_mutant": snap[0] if snap else "",
                "mutant_snapped": bool(snap),
            }
        )

    src = (W / "tools" / "workflow_foundry" / "role_extract.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    banned = {"difflib", "fuzzywuzzy", "rapidfuzz", "jellyfish", "levenshtein"}
    forbidden = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                if a.name.split(".")[0].lower() in banned:
                    forbidden.append(a.name)
        if isinstance(node, ast.ImportFrom):
            root = (node.module or "").split(".")[0].lower()
            if root in banned:
                forbidden.append(node.module or "")

    both_pass = all(
        r["match"] for r in invented_rows + synonym_rows + substring_trap_rows
    )
    snap_pass = (
        all(r["production_unknown"] for r in near_miss_rows)
        and all(r["mutant_snapped"] for r in near_miss_rows)
        and not forbidden
    )
    doc = {
        "unit_id": "IMP-0165",
        "probe": "probe1-invented-vs-synonym",
        "both_states": {
            "invented_rows": invented_rows,
            "synonym_rows": synonym_rows,
            "substring_trap_rows": substring_trap_rows,
            "pass": both_pass,
        },
        "no_silent_snap": {
            "near_miss_rows": near_miss_rows,
            "ast": {
                "source": "tools/workflow_foundry/role_extract.py",
                "exact": not forbidden,
                "forbidden_names": forbidden,
            },
            "comparable": {
                "critic": normalize_role("critic"),
                "red team": normalize_role("red team"),
                "refuter": normalize_role("refuter"),
            },
            "pass": snap_pass,
        },
    }
    doc["pass"] = both_pass and snap_pass
    out = Path(__file__).resolve().parent / "probe1-invented-vs-synonym.raw.json"
    out.write_text(json.dumps(doc, indent=1, sort_keys=True), encoding="utf-8")
    print(json.dumps(doc, sort_keys=True))
    if doc["pass"]:
        print("SUCCESS:IMP-0165-probe1 invented role is UNKNOWN; critic/red team/refuter"
              " map to critic; no nearest-neighbour snap")
        return 0
    print("FAILED:IMP-0165-probe1 both-states or no-snap control failed")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
