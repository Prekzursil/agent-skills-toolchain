#!/usr/bin/env python3
"""Probe 1: extract the frontmatter model FIELD per agent definition.

Does not classify from body mentions. A fixture whose prose contains
`sonnet` while frontmatter says `model: opus` must be assigned opus.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import audit_agent_roster as R  # noqa: E402

P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/AUD-0063/probe1_frontmatter_model.py"
)


def slim(agent: dict) -> dict:
    return {
        "name": agent["name"],
        "path": agent["path"],
        "kind": agent["kind"],
        "tree_id": agent["tree_id"],
        "has_frontmatter": agent["has_frontmatter"],
        "model_frontmatter": agent["model_frontmatter"],
        "model_map_parse": agent["model_map_parse"],
        "model_linewise_parse": agent["model_linewise_parse"],
        "model_tier": agent["model_tier"],
        "body_mentions_sonnet": agent["body_mentions_sonnet"],
        "naive_body_would_assign_sonnet": agent["naive_body_would_assign_sonnet"],
    }


def main() -> int:
    inv = R.inventory()
    ctl = R.control_checks(inv)
    mention = next(
        (a for a in inv["control_agents"] if a["name"] == "mention-only-lookup"),
        None,
    )
    payload = {
        "probe": "probe1-frontmatter-model",
        "unit_id": R.UNIT,
        "method": "yaml-mapping-parse of YAML frontmatter `model` field only",
        "command": P1,
        "production_trees": [
            {
                "id": t["id"],
                "present": t["present"],
                "md_count": t["md_count"],
                "path_rel": t["path_rel"],
            }
            for t in inv["production_trees"]
        ],
        "production_agent_count": inv["production_agent_count"],
        "control_agent_count": inv["control_agent_count"],
        "production_agents": [slim(a) for a in inv["production_agents"]],
        "control_agents": [slim(a) for a in inv["control_agents"]],
        "use_vs_mention": {
            "fixture": None if mention is None else slim(mention),
            "assigned_from_frontmatter": None
            if mention is None
            else mention["model_tier"],
            "body_contains_sonnet": None
            if mention is None
            else mention["body_mentions_sonnet"],
            "naive_grep_would_flag_sonnet": None
            if mention is None
            else mention["naive_body_would_assign_sonnet"],
            "classified_as_sonnet": False
            if mention is None
            else mention["model_tier"] == "sonnet",
        },
        "control": {
            "mention_assigned_opus_not_sonnet": ctl["mention_assigned_opus_not_sonnet"],
            "map_and_linewise_model_agree": ctl["map_and_linewise_model_agree"],
            "naive_grep_disagrees_with_frontmatter": ctl[
                "naive_grep_disagrees_with_frontmatter"
            ],
        },
        "pass": bool(
            ctl["mention_assigned_opus_not_sonnet"]
            and ctl["map_and_linewise_model_agree"]
            and ctl["naive_grep_disagrees_with_frontmatter"]
        ),
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    if not payload["pass"]:
        print("FAILED:AUD-0063-probe1 use-vs-mention or parse agreement", file=sys.stderr)
        return 1
    print("SUCCESS:AUD-0063-probe1 frontmatter model field extraction")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
