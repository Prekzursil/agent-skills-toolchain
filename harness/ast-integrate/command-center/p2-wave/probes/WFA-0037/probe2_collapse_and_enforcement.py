#!/usr/bin/env python3
"""Probe 2: role collapse from the table; enforcement vs DECLARED-ONLY.

Both-states: strip the chair gate -> ENFORCED flips to DECLARED-ONLY.
Mutate beta vote_rights -> collapse flips false.
Flatten-collapse mutant hides identical behaviour.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import extract as E  # noqa: E402

OUT = REPO / "command-center/wfa/WFA-0037-extract-roles.json"
SPLIT = "wf-declared-split-roles"
COLLAPSED = "wf-collapsed-roles"
EMPTY = "wf-no-roles"


def fail(msg: str) -> int:
    print(f"FAILED:WFA-0037-probe2 {msg}")
    return 1


def by_id(rows: list[dict]) -> dict[str, dict]:
    return {str(r.get("candidate_id")): r for r in rows}


def collapse_from_table(row: dict) -> bool:
    fps = [str(r.get("behavior_fingerprint") or "") for r in (row.get("roles") or [])]
    return len(fps) >= 2 and len(set(fps)) == 1


def main() -> int:
    if not OUT.is_file():
        return fail("artifact-missing")
    doc = json.loads(OUT.read_text(encoding="utf-8"))
    table = by_id(doc.get("per_candidate") or [])
    for need in (SPLIT, COLLAPSED, EMPTY):
        if need not in table:
            return fail(f"missing-candidate {need}")

    split = table[SPLIT]
    collapsed = table[COLLAPSED]
    empty = table[EMPTY]

    if empty.get("fill") != "HONEST-NULL" or (empty.get("roles") or []):
        return fail(f"empty-not-honest-null fill={empty.get('fill')} n={len(empty.get('roles') or [])}")

    if not collapse_from_table(collapsed):
        return fail(
            "collapse-not-detectable-from-table "
            f"fps={[r.get('behavior_fingerprint') for r in collapsed.get('roles') or []]}"
        )
    if collapse_from_table(split):
        return fail("split-roles-false-collapse")
    flagged = collapsed.get("collapse") or {}
    if flagged.get("collapse") is not True:
        return fail(f"collapse-flag-missing {flagged}")

    roles = {str(r.get("id")): r for r in (split.get("roles") or [])}
    chair = roles.get("chair")
    scribe = roles.get("scribe")
    if not chair or not scribe:
        return fail(f"split-roles-incomplete {sorted(roles)}")
    if chair.get("enforcement") != "ENFORCED" or not chair.get("enforcement_surface"):
        return fail(f"chair-not-enforced {chair.get('enforcement')} {chair.get('enforcement_surface')}")
    if scribe.get("enforcement") != "DECLARED-ONLY":
        return fail(f"scribe-not-declared-only {scribe.get('enforcement')}")
    surface = Path(str(chair["enforcement_surface"]))
    if not surface.is_file() and not (REPO / str(chair["enforcement_surface"])).is_file():
        return fail(f"enforcement-surface-missing {chair['enforcement_surface']}")

    # Both-states: empty enforcement dir flips chair to DECLARED-ONLY.
    missing_dir = HERE / "fixtures" / "enforcement-absent"
    missing_dir.mkdir(parents=True, exist_ok=True)
    stripped = E.extract_root(E.FIXTURE_CORPUS, enforcement_root=missing_dir, mode="honest")
    stripped_split = by_id(stripped["candidates"])[SPLIT]
    stripped_chair = next(r for r in stripped_split["roles"] if r["id"] == "chair")
    if stripped_chair.get("enforcement") != "DECLARED-ONLY":
        return fail(f"both-states-enforcement-did-not-flip {stripped_chair.get('enforcement')}")

    # Both-states: differentiate beta vote_rights -> collapse false.
    raw = E.load_json(E.FIXTURE_CORPUS / "08-WORKFLOW-CANDIDATE-REGISTRY.json")
    mutated = copy.deepcopy(raw)
    for cand in mutated["candidates"]:
        if cand.get("id") != COLLAPSED:
            continue
        for role in cand.get("roles") or []:
            if role.get("id") == "beta":
                role["vote_rights"] = False
                role["vote_rights_quote"] = "beta may not vote (mutant)"
    hits = E.index_enforcement(E.ENFORCEMENT_DIR)
    mutated_row = E.extract_candidate(
        next(c for c in mutated["candidates"] if c["id"] == COLLAPSED),
        hits=hits,
        mode="honest",
    )
    if collapse_from_table(mutated_row):
        return fail("vote-rights-mutant-still-collapsed")

    flat = E.extract_root(E.FIXTURE_CORPUS, mode="flatten_collapse")
    flat_row = by_id(flat["candidates"])[COLLAPSED]
    if collapse_from_table(flat_row):
        return fail("flatten-mutant-still-shows-collapse")
    if not collapse_from_table(collapsed):
        return fail("honest-lost-collapse")

    print(
        "collapse_from_table=True split_distinct=True "
        "chair=ENFORCED scribe=DECLARED-ONLY "
        "enforcement_stripped=DECLARED-ONLY vote_mutant_uncollapsed=True "
        "flatten_mutant_hides_collapse=True honest_null=True"
    )
    print("SUCCESS:WFA-0037-probe2 collapse-and-enforcement")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
