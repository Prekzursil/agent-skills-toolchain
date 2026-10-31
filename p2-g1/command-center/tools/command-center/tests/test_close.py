"""The close path: every verb, and every refusal.

The register rots if closing is dearer than opening, so the cost symmetry is
itself asserted here (`test_close_is_one_command_like_open`). The refusal tests
matter as much as the happy paths: a close that accepts blank evidence quietly
converts DONE-VERIFIED into DONE-CLAIMED, which this register defines as
NOT-CHECKED.
"""

from __future__ import annotations

import json
from pathlib import Path

import catalog as cat
import close
import pytest
import validate as val

NOW = "2026-08-09T12:00:00+00:00"


@pytest.fixture()
def workspace(tmp_path: Path):
    """An isolated copy of the real catalog so no test can touch the committed one."""
    catalog = cat.load()
    catalog_file = tmp_path / "WORK-UNIT-CATALOG.json"
    graph_file = tmp_path / "DEPENDENCY-GRAPH.json"
    events_file = tmp_path / "events" / "EVENTS.jsonl"
    cat.save(catalog, catalog_file)
    cat.save(cat.build_graph(catalog), graph_file)
    return catalog_file, graph_file, events_file


def run(workspace, *argv: str) -> int:
    catalog_file, graph_file, events_file = workspace
    return close.main(
        [
            *argv,
            "--catalog",
            str(catalog_file),
            "--graph",
            str(graph_file),
            "--events",
            str(events_file),
            "--now",
            NOW,
        ]
    )


def read(workspace) -> dict:
    return cat.load(workspace[0])


def item(catalog: dict, item_id: str) -> dict:
    return cat.by_id(catalog)[item_id]


# --------------------------------------------------------------------------
# verbs
# --------------------------------------------------------------------------


def test_close_sets_a_terminal_disposition_with_evidence(workspace, capsys):
    assert (
        run(
            workspace,
            "R-M08",
            "--evidence",
            "renamed to monitor.retired-20260718; Test-Path old=False",
        )
        == 0
    )
    closed = item(read(workspace), "R-M08")
    assert closed["disposition"] == "DONE-VERIFIED"
    assert closed["section"] == "SETTLED"
    assert "monitor.retired" in closed["disposition_evidence"]
    assert closed["history"][-1]["action"] == "close"
    assert "SUCCESS:cc-close close R-M08" in capsys.readouterr().out


def test_close_without_evidence_is_refused(workspace, capsys):
    assert run(workspace, "R-M08") == 1
    assert run(workspace, "R-M08", "--evidence", "   ") == 1
    assert "FAILED:cc-close" in capsys.readouterr().out
    assert cat.is_open(item(read(workspace), "R-M08"))


def test_defer_keeps_the_item_open_and_never_deletes(workspace):
    assert (
        run(workspace, "R-M14", "--defer", "owner flagged highest-risk", "--days", "14")
        == 0
    )
    deferred = item(read(workspace), "R-M14")
    assert cat.is_open(deferred)
    assert deferred["defer"]["reason"] == "owner flagged highest-risk"
    assert deferred["defer"]["until"].startswith("2026-08-23")


def test_supersede_requires_a_real_replacement(workspace, capsys):
    assert run(workspace, "R-M03", "--superseded-by", "R-NOPE") == 1
    assert "unknown item" in capsys.readouterr().out
    assert (
        run(
            workspace,
            "R-M03",
            "--superseded-by",
            "R-M01",
            "--evidence",
            "R-M01 subsumes the stanza work",
        )
        == 0
    )
    assert item(read(workspace), "R-M03")["disposition"] == "SUPERSEDED"


def test_drop_records_the_owner_decision(workspace):
    assert (
        run(
            workspace,
            "R-M14",
            "--dropped",
            "owner decision GRILL-DECISIONS:22 additive only",
        )
        == 0
    )
    dropped = item(read(workspace), "R-M14")
    assert dropped["disposition"] == "DROPPED-BY-OWNER"
    assert "GRILL-DECISIONS" in dropped["disposition_evidence"]


def test_note_records_progress_without_closing(workspace):
    assert (
        run(
            workspace,
            "R-A02",
            "--note",
            "13-file ledger half landed",
            "--action",
            "residual = clean-room baseline",
        )
        == 0
    )
    noted = item(read(workspace), "R-A02")
    assert cat.is_open(noted)
    assert noted["history"][-1]["action"] == "note"
    assert noted["next_smallest_action"] == "residual = clean-room baseline"


def test_open_allocates_the_next_free_id_in_that_program(workspace):
    assert (
        run(
            workspace,
            "--open",
            "wire the cockpit health probe",
            "--program",
            "MONITOR",
            "--action",
            "add probe",
        )
        == 0
    )
    catalog = read(workspace)
    assert "R-M20" in cat.by_id(catalog)
    assert item(catalog, "R-M20")["program"] == "MONITOR"
    assert (
        run(
            workspace,
            "--open",
            "second monitor item",
            "--program",
            "MONITOR",
            "--action",
            "x",
        )
        == 0
    )
    assert "R-M21" in cat.by_id(read(workspace))


def test_open_without_a_program_is_refused(workspace, capsys):
    assert run(workspace, "--open", "orphan") == 1
    assert "needs --program" in capsys.readouterr().out


def test_unknown_item_is_refused(workspace, capsys):
    assert run(workspace, "R-ZZ99", "--evidence", "x") == 1
    assert "no such item" in capsys.readouterr().out


def test_no_verb_is_refused(workspace, capsys):
    assert run(workspace) == 1
    assert "nothing to do" in capsys.readouterr().out


# --------------------------------------------------------------------------
# invariants the close path must preserve
# --------------------------------------------------------------------------


def test_every_mutation_regenerates_the_graph_and_logs_an_event(workspace):
    catalog_file, graph_file, events_file = workspace
    assert (
        run(workspace, "R-M08", "--evidence", "done; ls shows monitor.retired-20260718")
        == 0
    )
    catalog = cat.load(catalog_file)
    assert json.loads(graph_file.read_text(encoding="utf-8")) == cat.build_graph(
        catalog
    )
    events = [
        json.loads(line)
        for line in events_file.read_text(encoding="utf-8").splitlines()
    ]
    assert events[-1]["verb"] == "close"
    assert events[-1]["id"] == "R-M08"


def test_the_event_log_is_append_only(workspace):
    _, _, events_file = workspace
    run(workspace, "R-M08", "--evidence", "a b")
    run(workspace, "R-M09", "--evidence", "c d")
    lines = events_file.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    assert [json.loads(line)["id"] for line in lines] == ["R-M08", "R-M09"]


def test_a_close_that_would_break_reachability_is_refused(workspace, capsys):
    """Closing R-M01 while R-M04 still depends on it is fine (a dependent may
    outlive its dependency), but closing a BLOCKED item while its blocker is
    open contradicts the declared graph and must be refused."""
    assert run(workspace, "R-M17", "--evidence", "GitHubActionsSource shipped") == 1
    out = capsys.readouterr().out
    assert "REACH-1" in out and "still-open R-M13" in out
    assert cat.is_open(item(read(workspace), "R-M17"))


def test_a_preexisting_violation_elsewhere_does_not_block_an_unrelated_close(
    workspace, capsys
):
    """The deadlock guard. If a stale violation anywhere could block every close,
    the only satisfying action would be somebody else's work -- exactly the
    advisory-with-no-legal-move failure this lane exists to avoid."""
    catalog_file, graph_file, events_file = workspace
    broken = cat.load(catalog_file)
    cat.by_id(broken)["R-A21"]["dependencies"] = ["R-GHOST"]
    cat.save(broken, catalog_file)
    cat.save(cat.build_graph(broken), graph_file)
    assert val.validate(cat.load(catalog_file))[0], (
        "precondition: the catalog is already dirty"
    )
    assert (
        run(
            workspace,
            "R-M08",
            "--evidence",
            "quarantined; ls shows monitor.retired-20260718",
        )
        == 0
    )
    assert item(read(workspace), "R-M08")["disposition"] == "DONE-VERIFIED"


def test_dry_run_writes_nothing(workspace):
    catalog_file, _, events_file = workspace
    before = catalog_file.read_bytes()
    assert run(workspace, "R-M08", "--evidence", "x y", "--dry-run") == 0
    assert catalog_file.read_bytes() == before
    assert not events_file.exists()


def test_close_is_one_command_like_open(workspace):
    """Cost symmetry, asserted rather than asserted-in-prose: opening and closing
    are each a single argv with the same shape."""
    assert (
        run(
            workspace,
            "--open",
            "a new thing",
            "--program",
            "HARNESS",
            "--action",
            "start it",
        )
        == 0
    )
    new_id = sorted(i for i in cat.by_id(read(workspace)) if i.startswith("R-H"))[-1]
    assert run(workspace, new_id, "--evidence", "shipped at tools/x.py:1") == 0
    assert item(read(workspace), new_id)["disposition"] == "DONE-VERIFIED"


def test_list_filters_by_program_and_openness(workspace, capsys):
    assert (
        run(workspace, "--list", "--program", "B-workflow_design", "--only-open") == 0
    )
    out = capsys.readouterr().out
    assert "R-B08" in out and "R-A01" not in out
    assert run(workspace, "--list") == 0
    assert "R-A01" in capsys.readouterr().out


def test_unreadable_catalog_fails_closed(tmp_path: Path, capsys):
    assert close.main(["--list", "--catalog", str(tmp_path / "missing.json")]) == 1
    assert "FAILED:cc-close" in capsys.readouterr().out


def test_next_id_rejects_an_unknown_program():
    with pytest.raises(ValueError):
        close.next_id(cat.load(), "NOT-A-PROGRAM")


def test_now_defaults_to_wall_clock_utc():
    assert close._now().tzinfo is not None
    assert close._now(NOW).isoformat() == NOW


def test_closing_every_open_item_leaves_a_valid_catalog(workspace):
    """The end state has to be legal too: a register you cannot finish is a
    register that will be abandoned."""
    catalog = read(workspace)
    order, residual = cat.topological_order(catalog)
    assert residual == []
    for item_id in order:
        entry = cat.by_id(catalog)[item_id]
        if cat.is_open(entry):
            entry["disposition"] = "DONE-VERIFIED"
            entry["status"] = "DONE-VERIFIED"
            entry["section"] = "SETTLED"
            entry["disposition_evidence"] = f"simulated close of {item_id}"
    violations, stats = val.validate(catalog, graph=cat.build_graph(catalog))
    assert violations == [], [str(entry) for entry in violations]
    assert stats["open"] == 0
