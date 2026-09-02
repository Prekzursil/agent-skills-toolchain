"""Live rediscovery control for CNF-0082.

Runs the probe-local scout (declared source-class file walk) against planted
incumbents. Production IMP-0209 / WFA-0143 artifacts are surveyed, never rebuilt.
"""
from __future__ import annotations

from pathlib import Path

import recommend
import scenario as S
import scout

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]


def production_scout_census(repo: Path) -> dict:
    """Look for shipped scout artifacts. Do not implement IMP-0209 here."""
    candidates = [
        "command-center/receipts/IMP-0209.json",
        "command-center/foundry/WFA-0143-workflow-scout-executable-search-rank-and-provenance.json",
        "command-center/wfa/WFA-0127-workflow-scout-executable-spec.json",
    ]
    present = []
    missing = []
    for rel in candidates:
        path = repo / rel
        if path.is_file() and path.stat().st_size > 0:
            present.append(rel)
        else:
            missing.append(rel)
    foundry = "tools/foundry/scout.py"
    foundry_present = (repo / foundry).is_file()
    # Named IMP-0209 / WFA-0143 receipts only. tools/foundry/scout.py is a
    # single-library coverage gate, not the five source-class scout.
    return {
        "estate_library_scout": foundry if foundry_present else None,
        "named_artifacts_missing": missing,
        "named_artifacts_present": present,
        "production_present": bool(present),
        "production_present": bool(present),
    }


def foundry_library_control(repo: Path) -> dict:
    """Plant into the estate library scout (tools/foundry/scout.py). Not IMP-0209."""
    import json
    import sys

    plant_id = "wf.cnf0082.foundry.superior"
    plant_rel = (
        "command-center/p2-wave/probes/CNF-0082/fixtures/foundry-library.json"
    )
    empty_rel = (
        "command-center/p2-wave/probes/CNF-0082/fixtures/foundry-library-empty.json"
    )
    out = {
        "estate_module": "tools/foundry/scout.py",
        "id": "foundry-library-plant",
        "kind": "estate-library-scout",
        "plant": {"id": plant_id, "path": plant_rel},
        "verdict": "blind",
    }
    tools = repo / "tools"
    if not (tools / "foundry" / "scout.py").is_file():
        out["error"] = "foundry-scout-absent"
        return out
    if str(tools) not in sys.path:
        sys.path.insert(0, str(tools))
    from foundry.scout import scout as estate_scout
    from foundry.typed_goal import parse_typed_goal

    incumbents = json.loads(
        (tools / "foundry" / "library" / "incumbents.json").read_text(
            encoding="utf-8"
        )
    )
    donor = (incumbents.get("workflows") or incumbents.get("workflows") or [{}])[0]
    planted_wf = {
        "capabilities": ["static-scan", "write-config"],
        "covers": {
            "constraints": {"discovery_only": True},
            "intents": ["cnf-0082 foundry plant"],
        },
        "discovery_only": True,
        "id": plant_id,
        "kind": "workflow",
        "params": donor.get("params")
        or {"schema": {"repo": {"type": "string", "required": True}}, "values": {"repo": "."}},
        "quality": 99,
        "stages": donor.get("stages") or [],
        "stopping": donor.get("stopping") or {"max_stages": 2, "on_error": "halt"},
    }
    planted_lib = dict(incumbents)
    planted_lib["workflows"] = list(incumbents.get("workflows") or []) + [planted_wf]
    empty_lib = dict(incumbents)
    empty_lib["workflows"] = [
        {
            "capabilities": ["benchmark"],
            "discovery_only": False,
            "id": "wf.unrelated.benchmark",
            "kind": "workflow",
            "params": {"schema": {}, "values": {}},
            "quality": 10,
            "stages": [
                {
                    "depends_on": [],
                    "id": "bench",
                    "inputs": ["fused.json"],
                    "kind": "benchmark",
                    "outputs": ["score.json"],
                }
            ],
            "stopping": {"max_stages": 1, "on_error": "halt"},
        }
    ]
    plant_path = repo / plant_rel
    empty_path = repo / empty_rel
    plant_path.parent.mkdir(parents=True, exist_ok=True)
    plant_path.write_text(json.dumps(planted_lib, indent=2) + "\n", encoding="utf-8")
    empty_path.write_text(json.dumps(empty_lib, indent=2) + "\n", encoding="utf-8")
    goal = parse_typed_goal(
        "Discover catalog-class workflows and record them as blueprints "
        "without execution"
    )
    live = estate_scout(goal)
    planted = estate_scout(goal, library_path=plant_path)
    empty = estate_scout(goal, library_path=empty_path)
    found = planted.verdict == "ADOPT" and planted.adopted_id == plant_id
    out.update(
        {
            "both_states": bool(found) and empty.verdict == "BUILD",
            "empty_path": empty_rel,
            "empty_verdict": empty.verdict,
            "live_default_adopted": live.adopted_id,
            "live_default_verdict": live.verdict,
            "planted_adopted": planted.adopted_id,
            "planted_verdict": planted.verdict,
            "verdict": "found" if found else "blind",
        }
    )
    return out


def class_control(fixture_root: Path, cls: str) -> dict:
    plant_path = S.plant_rel(cls)
    plant = {
        "id": S.plant_id(cls),
        "path": plant_path,
        "quality_score": S.PLANT_SCORE,
        "source_class": cls,
        "superior": True,
    }
    hits = scout.search(fixture_root, source_classes=(cls,))
    rec = recommend.assess(hits, S.plant_id(cls))
    ghosts = recommend.ghost_ids(hits)
    on_disk = (REPO / plant_path).is_file()
    verdict = rec["verdict"]
    if verdict == "recommendation-defect":
        verdict = "found"
    return {
        "ghosts_returned": ghosts,
        "id": f"plant-{cls}",
        "kind": "source-class-plant",
        "plant": plant,
        "plant_on_disk": on_disk,
        "plant_rank": rec["plant_rank"],
        "ranked_above_rebuild": rec["ranked_above_rebuild"],
        "rebuild_rank": rec["rebuild_rank"],
        "recommendation_defect": rec["defect"],
        "recommendation_verdict": rec["verdict"],
        "scout_output": hits,
        "source_class": cls,
        "verdict": verdict,
    }


def invalid_plant_control(fixture_root: Path) -> dict:
    hits = scout.search(fixture_root, source_classes=("local",))
    decoy_id = "wf.cnf0082.local.nonmatching"
    returned = any(h.get("id") == decoy_id for h in hits)
    return {
        "id": "invalid-plant-nonmatching-tokens",
        "kind": "invalid-plant",
        "plant": {
            "id": decoy_id,
            "path": (
                "command-center/p2-wave/probes/CNF-0082/fixtures/sources/"
                "local/wf-cnf0082-local-nonmatching.json"
            ),
        },
        "returned": returned,
        "verdict": "invalid-plant" if returned else "silent",
    }


def index_injection_control(fixture_root: Path) -> dict:
    hits = scout.search(fixture_root)
    ghosts = recommend.ghost_ids(hits)
    return {
        "ghosts": ghosts,
        "id": "index-injection-ghosts",
        "kind": "index-injection",
        "plant": {
            "id": "wf.cnf0082.*.ghost",
            "path": "command-center/p2-wave/probes/CNF-0082/fixtures/sources/*/index.json",
        },
        "verdict": "found" if ghosts else "silent",
    }


def recommendation_mutant(fixture_root: Path) -> dict:
    """Both-states for ranking: live plant-above-rebuild vs mutant rebuild-on-top."""
    live = scout.search(fixture_root, source_classes=("local",))
    live_rec = recommend.assess(live, S.plant_id("local"))
    mutant_hits = scout.search(
        fixture_root,
        source_classes=("local",),
        rebuild_score=10_000,
    )
    mutant_rec = recommend.assess(mutant_hits, S.plant_id("local"))
    return {
        "id": "recommendation-mutant-rebuild-on-top",
        "kind": "recommendation-mutant",
        "live_defect": live_rec["defect"],
        "live_ranked_above_rebuild": live_rec["ranked_above_rebuild"],
        "mutant_defect": mutant_rec["defect"],
        "mutant_ranked_above_rebuild": mutant_rec["ranked_above_rebuild"],
        "plant": {
            "id": S.plant_id("local"),
            "path": S.plant_rel("local"),
        },
        "verdict": "recommendation-defect" if mutant_rec["defect"] else "found",
    }


def run(repo: Path | None = None) -> dict:
    repo = repo or REPO
    fixtures = S.ensure_fixtures()
    rows = [class_control(fixtures, cls) for cls in S.SOURCE_CLASSES]
    invalid = invalid_plant_control(fixtures)
    injection = index_injection_control(fixtures)
    mutant = recommendation_mutant(fixtures)
    foundry = foundry_library_control(repo)
    census = production_scout_census(repo)
    missing_plant = [r["source_class"] for r in rows if not r["plant_on_disk"]]
    missing_verdict = [
        r["source_class"] for r in rows if r["verdict"] not in {"found", "blind"}
    ]
    blind = [r["source_class"] for r in rows if r["verdict"] == "blind"]
    found = [r["source_class"] for r in rows if r["verdict"] == "found"]
    rec_defects = [r["source_class"] for r in rows if r["recommendation_defect"]]
    ghosts_leaked = [r["source_class"] for r in rows if r["ghosts_returned"]]
    return {
        "blind_classes": blind,
        "census": census,
        "class_rows": rows,
        "found_classes": found,
        "foundry_library": foundry,
        "ghosts_leaked": ghosts_leaked,
        "index_injection": injection,
        "invalid_plant": invalid,
        "missing_plant": missing_plant,
        "missing_verdict": missing_verdict,
        "recommendation_defects": rec_defects,
        "recommendation_mutant": mutant,
        "source_classes": list(S.SOURCE_CLASSES),
    }
