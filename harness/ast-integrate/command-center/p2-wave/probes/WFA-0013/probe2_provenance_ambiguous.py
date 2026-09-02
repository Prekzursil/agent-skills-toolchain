#!/usr/bin/env python3
"""Probe 2: commit-anchored provenance, AMBIGUOUS reporting, reverse join.

Both-states: the good fixture passes; a working-tree-only provenance ref is
rejected; forcing the AMBIGUOUS file into WORKFLOW is rejected; dropping the
ghost registry row hides the reverse-join miss.
"""
from __future__ import annotations

import copy
import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from classify import AMBIGUOUS, WORKFLOW  # noqa: E402
from fixture import (  # noqa: E402
    AMBIGUOUS_YAML,
    GHOST_REGISTRY_PATH,
    UNTRACKED_WORKFLOW,
    build_fixture,
)
from sweep import provenance_is_commit_anchored, sweep_repo  # noqa: E402


def fail(msg: str) -> int:
    print(f"FAILED:WFA-0013-probe2 {msg}")
    return 1


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="wfa0013-p2-") as raw:
        root = Path(raw) / "repo"
        meta = build_fixture(root)
        result = sweep_repo(root, meta["registry"], controls=meta["controls"])

        if not result.new_candidates:
            return fail("good fixture produced no new candidates")
        for item in result.new_candidates:
            if not provenance_is_commit_anchored(
                item["provenance_ref"], item["commit"], item["path"]
            ):
                return fail(f"new candidate not commit-anchored: {item}")
            if item["path"] == UNTRACKED_WORKFLOW:
                return fail("untracked working-tree workflow entered new_candidates")

        classified_paths = {c.path for c in result.classified}
        if UNTRACKED_WORKFLOW in classified_paths:
            return fail("untracked file entered classified set")

        amb_paths = {c["path"] for c in result.ambiguous}
        if AMBIGUOUS_YAML not in amb_paths:
            return fail("AMBIGUOUS yaml missing from ambiguous list")
        if any(c["classification"] != AMBIGUOUS for c in result.ambiguous):
            return fail("ambiguous list contains a forced binary verdict")
        wf_paths = {c["path"] for c in result.new_candidates + result.already_enumerated}
        if AMBIGUOUS_YAML in wf_paths:
            return fail("AMBIGUOUS file forced into WORKFLOW")

        ghosts = [r["provenance_path"] for r in result.reverse_join["no_tree_match"]]
        if GHOST_REGISTRY_PATH not in ghosts:
            return fail(f"ghost path not in reverse join: {ghosts}")
        matched = [r["provenance_path"] for r in result.reverse_join["matched"]]
        if meta["known_workflow"] not in matched:
            return fail("registry quality.yml did not reverse-join to ls-tree")

        wt_mutant = copy.deepcopy(result.new_candidates[0])
        wt_mutant["provenance_ref"] = str(root / wt_mutant["path"])
        if provenance_is_commit_anchored(
            wt_mutant["provenance_ref"], wt_mutant["commit"], wt_mutant["path"]
        ):
            return fail("working-tree path was accepted as commit-anchored")

        forced = [c for c in result.classified if c.path == AMBIGUOUS_YAML]
        if not forced or forced[0].classification != AMBIGUOUS:
            return fail("ambiguous control row missing")
        forced_binary = forced[0].classification == WORKFLOW
        if forced_binary:
            return fail("classifier forced AMBIGUOUS to WORKFLOW")

        drop_ghost = copy.deepcopy(meta["registry"])
        drop_ghost["candidates"] = [
            r for r in drop_ghost["candidates"] if r.get("provenance") != GHOST_REGISTRY_PATH
        ]
        dropped = sweep_repo(root, drop_ghost, controls=meta["controls"])
        dropped_ghosts = [r["provenance_path"] for r in dropped.reverse_join["no_tree_match"]]
        if GHOST_REGISTRY_PATH in dropped_ghosts:
            return fail("dropped ghost still reported")
        if dropped.reverse_join["no_tree_match"]:
            return fail("drop-ghost mutant still has unmatched rows")

    payload = {
        "probe": "probe2-provenance-ambiguous-reverse-join",
        "unit_id": "WFA-0013",
        "new_candidates_anchored": True,
        "working_tree_ref_rejected": True,
        "ambiguous_reported": True,
        "ambiguous_not_forced_workflow": True,
        "untracked_excluded": True,
        "reverse_join_ghost": True,
        "drop_ghost_mutant_clears_unmatched": True,
        "pass": True,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        "anchored=True wt_ref_rejected=True ambiguous_reported=True "
        "untracked_excluded=True reverse_join_ghost=True drop_ghost_clears=True"
    )
    print("SUCCESS:WFA-0013-probe2 provenance AMBIGUOUS reverse-join both-states")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
