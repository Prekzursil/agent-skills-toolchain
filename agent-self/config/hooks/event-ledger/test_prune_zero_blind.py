#!/usr/bin/env python
"""Regression suite for prune-report.py ZERO-BLINDNESS (D-n01).

The defect: the report built its capability universe only from positive event
observations, then labelled the bottom of that tally "prune candidates". A capability
that never fired could not enter the tally at all, so with an installed universe of
{frequent-tool, used-once, never-invoked} and a ledger of 100 frequent-tool + 1
used-once events the report named `used-once` the top prune candidate, omitted
`never-invoked` entirely, and called its 2-capability list "FULL RANKING".

These are pytest-collectible `test_*` functions ON PURPOSE. The sibling
`test_prune_oats.py` is a `main()`-style standalone runner, so the named CI step
`python -m pytest hooks/ -q --import-mode=importlib` (.github/workflows/quality.yml)
collects ZERO tests from it -- measured: `pytest hooks/event-ledger/ --co` reported
"no tests collected". This file rides that existing named step instead of needing a
new one.

Seeding writes events.jsonl directly (the read path prune-report actually uses) because
`ledger.append` fsyncs under a lock: 101 real appends measured ~37s per test on Windows.
`test_ledger_append_rows_are_consumed` keeps one small case on the real writer so the
two sides cannot silently drift apart.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
PRUNE_PATH = HERE / "prune-report.py"

INSTALLED = ["frequent-tool", "used-once", "never-invoked"]


@pytest.fixture
def prune(tmp_path, monkeypatch):
    """Load prune-report.py against an isolated, empty EVENT_LEDGER_ROOT.

    `ledger` is popped from sys.modules first: three different `ledger.py` files exist
    in this repo and they would otherwise share one flat sys.modules key, letting
    collection order decide which one prune-report imports.
    """
    root = tmp_path / "ledger-root"
    root.mkdir()
    monkeypatch.setenv("EVENT_LEDGER_ROOT", str(root))
    monkeypatch.syspath_prepend(str(HERE))
    monkeypatch.delitem(sys.modules, "ledger", raising=False)

    spec = importlib.util.spec_from_file_location("prune_report_zb", PRUNE_PATH)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert mod.ledger.ROOT == root, "ledger did not pick up the isolated root"
    return mod


def _write_events(prune_mod, counts: dict[str, int], slug: str = "projX") -> None:
    """Append synthetic `turn` rows carrying a `tool` field, straight to events.jsonl."""
    project = Path(prune_mod.ledger.ROOT) / slug
    project.mkdir(parents=True, exist_ok=True)
    with (project / "events.jsonl").open("a", encoding="utf-8") as fh:
        for tool, n in counts.items():
            row = json.dumps(
                {"kind": "turn", "ts": "2026-07-29T12:00:00", "tool": tool}
            )
            for _ in range(n):
                fh.write(row + "\n")


def _section(out: str, start: str, end: str) -> str:
    assert start in out, f"missing section {start!r}"
    body = out.split(start, 1)[1]
    return body.split(end, 1)[0] if end in body else body


@pytest.fixture
def seeded(prune):
    """100 frequent-tool fires + 1 used-once fire = 101 tool events."""
    _write_events(prune, {"frequent-tool": 100, "used-once": 1})
    return prune


def test_never_fired_capability_is_the_top_prune_candidate(seeded):
    """With an inventory, the 0-fire capability outranks the 1-fire one."""
    out = seeded.report(min_events=100, top=1, installed=INSTALLED)
    assert "never-invoked" in out
    least = _section(out, "LEAST-FIRED", "MOST-FIRED")
    assert "never-invoked" in least
    assert "used-once" not in least, "a 1-fire capability outranked a 0-fire one"


def test_inventory_ranking_enumerates_the_whole_installed_universe(seeded):
    out = seeded.report(min_events=100, top=5, installed=INSTALLED)
    assert "FULL RANKING (3 capabilities = 3 installed + 0 observed-only" in out
    assert "1 of them NEVER fired" in out
    for name in INSTALLED:
        assert name in _section(out, "FULL RANKING", "PER-PROJECT")


def test_zero_fire_entries_do_not_distort_percentages(seeded):
    """The zeros are admitted AFTER the total, so shares must be unchanged."""
    without = seeded.report(min_events=100, top=5)
    with_inv = seeded.report(min_events=100, top=5, installed=INSTALLED)
    for out in (without, with_inv):
        assert "Tool events      : 101" in out
        assert "99.0%  frequent-tool" in out
    assert "0.0%  never-invoked" in with_inv


def test_observation_only_ranking_is_not_labelled_full(seeded):
    """Without an inventory the report must not claim a complete universe."""
    out = seeded.report(min_events=100, top=1)
    assert "FULL RANKING" not in out
    assert "OBSERVED-ONLY RANKING (2 capabilities seen firing" in out
    assert "no --installed inventory given" in out
    assert "CANNOT appear below" in out


def test_partial_inventory_is_reported_as_incomplete(seeded):
    """An inventory missing an observed capability must say so, not overstate."""
    out = seeded.report(min_events=100, top=1, installed=["never-invoked"])
    assert "FULL RANKING (3 capabilities = 1 installed + 2 observed-only" in out
    assert "2 capabilities fired but are ABSENT from the inventory" in out


def test_json_list_inventory_file(seeded, tmp_path):
    path = tmp_path / "inv.json"
    path.write_text(json.dumps(INSTALLED), encoding="utf-8")
    out = seeded.report(min_events=100, top=1, installed=path)
    assert "never-invoked" in _section(out, "LEAST-FIRED", "MOST-FIRED")


def test_json_object_inventory_shapes(seeded, tmp_path):
    keyed = tmp_path / "keyed.json"
    keyed.write_text(json.dumps({n: {} for n in INSTALLED}), encoding="utf-8")
    wrapped = tmp_path / "wrapped.json"
    wrapped.write_text(json.dumps({"capabilities": INSTALLED}), encoding="utf-8")
    for path in (keyed, wrapped):
        out = seeded.report(min_events=100, top=1, installed=path)
        assert "3 installed + 0 observed-only" in out


def test_plain_text_inventory_file_ignores_comments_and_blanks(seeded, tmp_path):
    path = tmp_path / "inv.txt"
    path.write_text(
        "# installed capabilities\nfrequent-tool\n\nused-once\nnever-invoked\n",
        encoding="utf-8",
    )
    out = seeded.report(min_events=100, top=1, installed=path)
    assert "3 installed + 0 observed-only" in out


@pytest.mark.parametrize(
    "name,body",
    [
        ("missing.json", None),
        ("empty.json", "[]"),
        ("blank.txt", "# only a comment\n\n"),
        ("bad.json", "{not json"),
        ("mis-shaped.json", '{"capabilities": 7}'),
    ],
)
def test_unusable_inventory_fails_the_report_instead_of_degrading(
    seeded, tmp_path, name, body
):
    """A broken inventory must NOT silently fall back to the zero-blind universe."""
    path = tmp_path / name
    if body is not None:
        path.write_text(body, encoding="utf-8")
    out = seeded.report(min_events=100, top=1, installed=path)
    assert "FAILED" in out
    assert "LEAST-FIRED" not in out
    assert "RANKING" not in out


def test_explicit_name_list_is_accepted_without_a_file(seeded):
    out = seeded.report(min_events=100, top=1, installed=(" never-invoked ", ""))
    assert "FULL RANKING (3 capabilities = 1 installed + 2 observed-only" in out


def test_duplicate_inventory_names_do_not_inflate_the_count(seeded, tmp_path):
    """A repeated name must count once, or the "N installed" figure overstates."""
    path = tmp_path / "dupes.txt"
    path.write_text(
        "never-invoked\nnever-invoked\n never-invoked \nused-once\n", encoding="utf-8"
    )
    out = seeded.report(min_events=100, top=5, installed=path)
    assert "UNIVERSE: 2 installed capabilities" in out
    assert "1 of them NEVER fired" in out
    ranking = _section(out, "FULL RANKING", "PER-PROJECT")
    assert ranking.count("never-invoked") == 1


def test_cli_wires_the_installed_flag(seeded, tmp_path, monkeypatch, capsys):
    """The flag must reach report() from argv, not only from a direct call."""
    path = tmp_path / "inv.json"
    path.write_text(json.dumps(INSTALLED), encoding="utf-8")
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "prune-report.py",
            "--min-events",
            "100",
            "--top",
            "1",
            "--installed",
            str(path),
        ],
    )
    assert seeded.main() == 0
    out = capsys.readouterr().out
    assert "3 installed + 0 observed-only" in out
    assert "never-invoked" in _section(out, "LEAST-FIRED", "MOST-FIRED")


def test_ledger_append_rows_are_consumed(prune):
    """Anchor the real writer: ledger.append rows must feed the same tally."""
    project = str(Path(prune.ledger.ROOT) / "projReal")
    for tool in ("frequent-tool", "frequent-tool", "used-once"):
        prune.ledger.append(
            project, "turn", head="a", branch="main", dirty_files=0, tool=tool
        )
    out = prune.report(min_events=3, top=1, installed=INSTALLED)
    assert "Tool events      : 3" in out
    assert "never-invoked" in _section(out, "LEAST-FIRED", "MOST-FIRED")


def test_sparse_data_still_short_circuits_with_an_inventory(prune):
    """The inventory must not turn the sparse-data advisory into a ranking."""
    _write_events(prune, {"frequent-tool": 3})
    out = prune.report(min_events=100, top=1, installed=INSTALLED)
    assert "INSUFFICIENT DATA" in out
    assert "LEAST-FIRED" not in out


def test_empty_ledger_root_advisory_is_unchanged(prune):
    """No projects at all: still the empty-root advisory, inventory or not."""
    assert not list(Path(prune.ledger.ROOT).iterdir())
    out = prune.report(installed=INSTALLED)
    assert "empty or does not exist" in out
