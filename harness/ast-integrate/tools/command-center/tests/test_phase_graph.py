"""CC-0016 both-states control: mutate the sidecar, the extended gate fires;
regenerate from authored source, the gate is silent. V-GRAPH is untouched.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import catalog as cat  # noqa: E402
import phase_graph as pg  # noqa: E402
import render  # noqa: E402
import validate as val  # noqa: E402

TINY_AUTHORED = {
    "allocation_buckets": [
        {"covers_phases": "0", "id": "B01", "planned_units": 1},
    ],
    "author": "test",
    "declared_critical_path": ["0", "1"],
    "description": "tiny fixture",
    "edges": [
        {
            "author": "test",
            "contested": False,
            "contested_id": None,
            "from": "0",
            "id": "E01",
            "kind": "HARD",
            "provenance": "authored-from-spec-prose",
            "reason": "1 follows 0",
            "to": "1",
        }
    ],
    "phases": [
        {"allocation_bucket": "B01", "id": "0", "title": "root"},
        {"allocation_bucket": None, "id": "1", "title": "leaf"},
    ],
    "program_preconditions": [],
    "schema_version": 1,
    "unit": "CC-0016",
}


def _root_with_authored(tmp_path: Path) -> tuple[Path, dict]:
    root = tmp_path / "command-center"
    (root / "events").mkdir(parents=True)
    (root / "events" / "EVENTS.jsonl").write_text("", encoding="utf-8")
    (root / "sources").mkdir()
    (root / "sources" / "phase-graph-authored.json").write_text(
        json.dumps(TINY_AUTHORED, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    catalog = {
        "defaults": {},
        "owner_questions": [],
        "items": [
            {
                "id": "R-A01",
                "status": "OPEN",
                "program": "A-toolchain",
                "next_smallest_action": "do the thing",
                "dependencies": [],
            }
        ],
    }
    return root, catalog


def test_mutation_fires_and_regen_is_silent(tmp_path: Path) -> None:
    root, catalog = _root_with_authored(tmp_path)
    render.write_all(root, catalog)
    assert render.check_all(root, catalog) == []
    assert pg.check(root) == 0

    sidecar = json.loads(pg.sidecar_path(root).read_text(encoding="utf-8"))
    sidecar["edges"][0]["to"] = "0"
    pg.sidecar_path(root).write_text(
        json.dumps(sidecar, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    drift = render.check_all(root, catalog)
    assert any("PHASE-GRAPH.json" in item for item in drift)

    pg.write_sidecar(root)
    assert render.check_all(root, catalog) == []


def test_item_graph_vgraph_unaffected_by_sidecar(tmp_path: Path) -> None:
    root, catalog = _root_with_authored(tmp_path)
    render.write_all(root, catalog)
    live = json.loads((root / "DEPENDENCY-GRAPH.json").read_text(encoding="utf-8"))
    derived = cat.build_graph(catalog)
    assert live == derived
    violations, _stats = val.validate(catalog, graph=live, register_path=None)
    assert not any(v.get("check") == "V-GRAPH" for v in violations)

    mutant = dict(live)
    mutant["phase_level"] = {"note": "forbidden"}
    extra, _ = val.validate(catalog, graph=mutant, register_path=None)
    assert any(v.get("check") == "V-GRAPH" for v in extra)
