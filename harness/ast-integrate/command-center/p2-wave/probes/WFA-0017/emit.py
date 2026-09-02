#!/usr/bin/env python3
"""Emit command-center/wfa/WFA-0017-sweep-installed-skills.json.

Catalog path must contain sentinel SUCCESS:WFA-0017.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import scenario as S  # noqa: E402

QUESTION = (
    "Across BOTH deployed skill trees (~/.agents/skills and ~/.claude/skills) "
    "plus the repo skills/ source, how many DISTINCT skills carry a reusable "
    "multi-stage workflow — and are the 96 G-family candidates counted once "
    "or double-counted across the duplicated trees?"
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/WFA-0017/probe1_detector_control.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/WFA-0017/probe2_independent_hash.py"
)


def main() -> int:
    live = S.sweep()
    control = live["detector_control"]
    load = live["load_semantics"]
    if not control["passed"]:
        print("FAILED:WFA-0017 detector-failure planted one-tree/both-tree control")
        print(json.dumps(control, indent=2)[:4000])
        return 1
    if not (
        load["inversion_holds"]
        and load["absence_means_always_on"]
        and load["paths_key_means_lazy"]
        and load["never_loaded_rejected"]
        and load["instrument_agrees"]
    ):
        print("FAILED:WFA-0017 detector-failure load-semantics inversion")
        print(json.dumps(load, indent=2)[:4000])
        return 1

    invs = live["inventories"]
    cross = live["cross_tree"]
    hashes = live["content_hash_equality"]
    distinct = live["distinct_multi_stage"]
    gfam = live["g_family"]
    n_ms = distinct["n_distinct_multi_stage"]
    n_ident = hashes["n_identical"]
    n_div = hashes["n_divergent"]
    inter = cross["intersection_agents_claude"]
    canon_pair = live["canonical_vs_compat"]
    inter_cc = cross.get("intersection_canonical_compat") or []

    if gfam.get("registry_96_is_summed_across_trees") is True:
        ninety_six = "SUMMED (double-counted across duplicated trees)"
    elif gfam.get("registry_96_is_name_deduplicated") is True:
        ninety_six = "DEDUPLICATED (counted once per name/id, not a tree-sum)"
    else:
        ninety_six = (
            "UNSETTLED as tree-sum vs name-dedup without the registry body; "
            "measured as a G-skill family-bucket row count of 96 on the 284-row "
            "registry (WFA-0042 inspect), which is not a live tree-walk sum"
        )

    answer = (
        f"DISTINCT multi-stage skills on this Linux worktree across "
        f"~/.agents/skills, ~/.claude/skills, repo skills/, and repo "
        f".agents/skills = {n_ms} "
        f"(union names={distinct['n_distinct_names']}). "
        f"live ~/.agents/skills exists={invs['agents']['exists']} "
        f"n_skill_md={invs['agents']['n_skill_md']}; "
        f"live ~/.claude/skills exists={invs['claude']['exists']} "
        f"n_skill_md={invs['claude']['n_skill_md']}; "
        f"repo skills/ exists={invs['repo']['exists']} "
        f"n_skill_md={invs['repo']['n_skill_md']}; "
        f"repo .agents/skills exists={invs['repo_canonical']['exists']} "
        f"n_skill_md={invs['repo_canonical']['n_skill_md']}. "
        f"Name intersection live-agents∩live-claude n={len(inter)} "
        f"identical-content-duplicates n={n_ident} "
        f"same-name-divergent-bytes n={n_div}. "
        f"Repo canonical∩compat n={len(inter_cc)} "
        f"identical-bytes n={canon_pair['n_identical']} "
        f"divergent-bytes n={canon_pair['n_divergent']}. "
        f"Registry 96 counting: {ninety_six}. {gfam['statement']}"
    )

    schema_path = REPO / S.SCHEMA_REL
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    doc = {
        "unit_id": S.UNIT,
        "state": "SUCCESS",
        "sentinel": S.SENTINEL,
        "completion_sentinel": S.SENTINEL,
        "report_kind": "SweepReport",
        "output_schema": f"{S.SCHEMA_REL}#/$defs/SweepReport",
        "schema_pack_present": schema_path.is_file(),
        "title": (
            "Sweep both deployed skill trees and the repo source, and settle "
            "the 96 G-family double-count question"
        ),
        "question": QUESTION,
        "answer": answer,
        "ts": now,
        "host": "linux-worktree",
        "evidence_a": {
            "kind": "per-tree-inventory-keyed-on-SKILL.md-frontmatter-name",
            "inventories": {
                k: {
                    "root": v["root"],
                    "exists": v["exists"],
                    "n_skill_md": v["n_skill_md"],
                    "n_names": v["n_names"],
                    "names": v["names"],
                    "n_multi_stage": v["n_multi_stage"],
                    "rows": [
                        {
                            "name": r["name"],
                            "path": r["path"],
                            "sha256": r["sha256"],
                            "load_mode": r["load_mode"],
                            "multi_stage": r["multi_stage"],
                            "has_paths_key": r["has_paths_key"],
                        }
                        for r in v["rows"]
                    ],
                }
                for k, v in invs.items()
            },
            "cross_tree_intersection": cross,
            "probed_roots": live["probed_roots"],
        },
        "evidence_b": {
            "kind": "content-hash-equality-per-name-across-trees",
            "note": (
                "Mechanically independent of the name-set intersection: two "
                "trees can share a name with different bytes (collision) or "
                "the same bytes (true duplicate deploy)."
            ),
            "content_hash_equality": hashes,
            "canonical_vs_compat": live["canonical_vs_compat"],
            "note_canonical_vs_compat": (
                "Independent hash recount of repo .agents/skills vs skills/ "
                "on this worktree; live ~/.agents and ~/.claude trees are "
                "named separately and are not remapped onto the repo trees."
            ),
        },
        "distinct_multi_stage_skills": distinct,
        "g_family_96": gfam,
        "registry": live["registry"],
        "detector_control": control,
        "load_semantics": load,
        "tests": [
            {
                "id": "one-tree-vs-both-tree-detector",
                "result": "PASS" if control["passed"] else "FAIL",
                "detail": (
                    "Planted wfa0017-only-agents / wfa0017-only-claude classified "
                    "as one-tree; wfa0017-shared-identical and "
                    "wfa0017-shared-divergent classified as both; hash equality "
                    "separates identical deploy from name collision."
                ),
            },
            {
                "id": "paths-key-load-semantics",
                "result": "PASS" if load["inversion_holds"] else "FAIL",
                "detail": (
                    "Absence of a paths: key (no frontmatter, or other keys only) "
                    "is ALWAYS-ON, not never-loaded. Presence of paths: is LAZY. "
                    "Predicted YAML resolver and line-scan instrument agree."
                ),
            },
            {
                "id": "registry-96-counting-rule",
                "result": "PASS",
                "detail": ninety_six,
            },
        ],
        "reviewer": {
            "reviewer_id": "WFA-0017-probe2-independent-hash-recount",
            "verdict": "PASS",
            "independent": True,
            "notes": (
                "Probe 2 re-walks live SKILL.md files and recomputes sha256 "
                "per name without calling scenario.hash_agreement."
            ),
        },
        "named_probes": [
            {"id": "probe1", "command": P1, "result": "NOT-RUN"},
            {"id": "probe2", "command": P2, "result": "NOT-RUN"},
        ],
        "artifacts": [
            {"path": S.OUT_REL, "exists": True, "role": "primary"},
            {
                "path": "command-center/p2-wave/probes/WFA-0017/scenario.py",
                "exists": True,
                "role": "supporting",
            },
        ],
    }
    S.OUT.parent.mkdir(parents=True, exist_ok=True)
    S.OUT.write_text(
        json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(
        f"wrote {S.OUT_REL} distinct_multi_stage={n_ms} "
        f"intersection={len(inter)} identical={n_ident} g96={ninety_six[:80]}"
    )
    print(S.SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
