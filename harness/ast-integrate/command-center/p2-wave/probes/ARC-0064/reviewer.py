#!/usr/bin/env python3
"""Independent test-architect review for ARC-0064.

Names a mutation the hop-assert suite does NOT catch, and proves it by
applying the mutation and re-running hop 3. Also plants a local ``judge``
copy so the census detector has a known-broken control.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
TOOLS = REPO / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from completion.census import census_file  # noqa: E402

import engine as E  # noqa: E402

PLANTED = HERE / "fixtures" / "planted_local_predicate.py"
UNCAUGHT_ID = "council-voting-rule-swap"


def uncaught_voting_rule_mutant() -> dict:
    """Swap council voting.rule; hop 3 still passes (class/id/roles only)."""
    root = E.SCRATCH / "uncaught-voting"
    E.reset_root(root)
    install_root = root / "install"
    hops_dir = root / "hops"
    hops_dir.mkdir(parents=True, exist_ok=True)
    inst = E.install_package(install_root, stubbed=False)
    wf = E.register_workflow(install_root, stubbed=False)
    preset = install_root / E.PRESET_REL
    doc = json.loads(preset.read_text(encoding="utf-8"))
    original = (doc.get("voting") or {}).get("rule")
    voting = dict(doc.get("voting") or {})
    voting["rule"] = "majority"
    doc["voting"] = voting
    preset.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    hop = E.open_council(install_root, hops_dir, stubbed=False)
    stays = bool(inst.get("assert_ok") and wf.get("assert_ok") and hop.get("assert_ok"))
    return {
        "id": UNCAUGHT_ID,
        "description": (
            "After a successful A2 install, rewrite the council preset "
            "voting.rule from the live value to 'majority'. Hop 3 still "
            "passes because it asserts preset id, four roles, and the "
            "workflow-catalog member, not voting-rule equality. The hybrid "
            "suite would NOT catch this semantic swap."
        ),
        "would_stay_green": stays,
        "mutated_field": "voting.rule",
        "original_rule": original,
        "mutated_to": "majority",
        "hop3_assert_ok": bool(hop.get("assert_ok")),
        "install_assert_ok": bool(inst.get("assert_ok")),
        "workflow_assert_ok": bool(wf.get("assert_ok")),
    }


def planted_local_copy_hits() -> list[dict]:
    if not PLANTED.is_file():
        return []
    return census_file(PLANTED, root=REPO, detector="ast")


def review() -> dict:
    mutant = uncaught_voting_rule_mutant()
    planted = planted_local_copy_hits()
    kinds = {h.get("kind") for h in planted}
    planted_ok = bool(
        "local-judge-def" in kinds or "local-predicate-def" in kinds
    ) and bool(planted)
    identity = E.object_identity()
    graph = E.import_graph_ok()
    engine_hits = E.engine_census_clean()
    ok = bool(
        mutant.get("would_stay_green") is True
        and planted_ok
        and identity.get("object_identity_proven") is True
        and graph.get("all_sites_ok") is True
        and graph.get("engine_imports_judge") is True
        and engine_hits == []
    )
    return {
        "reviewer_id": "ARC-0064-independent-test-architect",
        "independent": True,
        "verdict": "PASS" if ok else "FAIL",
        "uncaught_mutation": mutant,
        "planted_local_copy": {
            "path": "command-center/p2-wave/probes/ARC-0064/fixtures/planted_local_predicate.py",
            "hits": planted,
            "detected": planted_ok,
        },
        "engine_census_hits": engine_hits,
        "identity": identity,
        "import_graph": {
            "all_sites_ok": graph.get("all_sites_ok"),
            "engine_imports_judge": graph.get("engine_imports_judge"),
        },
        "ok": ok,
    }
