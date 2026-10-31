"""Render invariants. The ordering one is a regression, not a hypothetical.

`write_all` regenerates DEPENDENCY-GRAPH.json so that the procedure the tool's own output
documents -- record an owner answer by flipping state in the catalog and re-rendering -- can
actually converge. The first version of that change appended the graph write AFTER
`render_manifest()`, which hashes what is on disk. Every single render therefore emitted a
manifest describing the PREVIOUS graph: `render.py --check` failed immediately after
`render.py`, and only went green on a second run, which looks exactly like a fix.

Measured at the time: DEPENDENCY-GRAPH.json 25317 -> 25261 bytes with the manifest still
recording 25317. The test below is the both-states control in permanent form -- one render
from a perturbed state must leave `check_all` empty.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import catalog as cat  # noqa: E402
import render  # noqa: E402


@pytest.fixture
def cc(tmp_path: Path) -> tuple[Path, dict]:
    """A minimal command-center root plus a catalog that produces a non-empty graph."""
    root = tmp_path / "command-center"
    (root / "events").mkdir(parents=True)
    (root / "events" / "EVENTS.jsonl").write_text("", encoding="utf-8")
    catalog = {
        "defaults": {},
        "owner_questions": [
            {"id": "OQ-1", "state": "OPEN", "text": "an open one"},
            {
                "id": "OQ-3",
                "state": "ANSWERED",
                "text": "release mode?",
                "answer": "PR-ONLY.",
                "answer_detail": "pull requests only.",
                "answered_on": "2026-08-10",
                "answer_provenance": "owner statement in session",
            },
        ],
        "items": [
            {
                "id": "R-A01",
                "status": "OPEN",
                "program": "A-toolchain",
                "next_smallest_action": "do the thing",
                "dependencies": [],
            },
            {
                "id": "R-A02",
                "status": "OPEN",
                "program": "A-toolchain",
                "next_smallest_action": "do the other thing",
                "dependencies": ["R-A01"],
            },
        ],
    }
    return root, catalog


def test_one_render_leaves_check_clean_from_a_perturbed_graph(cc) -> None:
    """THE regression: a single render must produce a self-consistent manifest+graph pair."""
    root, catalog = cc
    render.write_all(root, catalog)

    graph_file = root / "DEPENDENCY-GRAPH.json"
    poisoned = json.loads(graph_file.read_text(encoding="utf-8"))
    poisoned["edge_count"] = 99999
    graph_file.write_text(
        json.dumps(poisoned, indent=1), encoding="utf-8", newline="\n"
    )

    render.write_all(root, catalog)  # ONE render, not two
    assert render.check_all(root, catalog) == []
    assert (
        json.loads(graph_file.read_text(encoding="utf-8"))["edge_count"]
        == cat.build_graph(catalog)["edge_count"]
    )


def test_the_manifest_records_the_graph_it_just_wrote(cc) -> None:
    """Pins the ordering directly, so the failure names the cause instead of a symptom."""
    root, catalog = cc
    render.write_all(root, catalog)
    manifest = json.loads((root / "ARTIFACT-MANIFEST.json").read_text(encoding="utf-8"))
    entry = next(
        a for a in manifest["artifacts"] if a["path"].endswith("DEPENDENCY-GRAPH.json")
    )
    on_disk = (root / "DEPENDENCY-GRAPH.json").read_bytes()
    assert entry["bytes"] == len(on_disk), (
        "the manifest describes a different graph than the one on disk -- the graph write "
        "has moved back after render_manifest()"
    )


def test_write_all_does_not_touch_the_real_repo(cc) -> None:
    """`root` must bound every write; a graph path resolved from the live repo would not."""
    root, catalog = cc
    written = render.write_all(root, catalog)
    assert written, "write_all wrote nothing"
    for path in written:
        assert root in path.parents or path.parent == root, f"{path} escaped root"


def test_an_answered_question_renders_its_answer_not_just_its_state(cc) -> None:
    """A state flip with the decision invisible is the recorded-but-unreadable failure."""
    _, catalog = cc
    text = render.render_owner_decisions(catalog)
    assert "Answered — the decision of record" in text
    assert "PR-ONLY." in text
    assert "owner statement in session" in text, "provenance must survive rendering"
    assert "**1 open of 2.**" in text


def test_open_questions_still_render_with_no_answer_column_noise(cc) -> None:
    _, catalog = cc
    text = render.render_owner_decisions(catalog)
    assert "OQ-1" in text and "an open one" in text
