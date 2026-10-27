"""Detector controls for the declared-vs-delivered reconciler.

Every count this tool prints is worthless without these. The first live run scored
UNIT-ID-REFERENCED on 100% of the units that reached that branch because the plan document
was inside its own evidence set; that bug was invisible in the summary line and obvious the
moment the distribution was read. So the controls below assert the SHAPE of the detector --
it must fire on a known-present artifact, stay silent on a known-absent one, and refuse to
count a plan restatement as delivery.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import reconcile_delivery as rd  # noqa: E402


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    root = tmp_path / "r"
    (root / "command-center").mkdir(parents=True)
    (root / "delivered").mkdir()
    subprocess.run(["git", "init", "-q", str(root)], check=True, capture_output=True)
    _git(root, "config", "user.email", "t@t")
    _git(root, "config", "user.name", "t")
    return root


def _commit_all(root: Path) -> None:
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "fixture")


def _catalog(units: list[dict]) -> dict:
    return {"work_units": units}


def test_fires_on_an_artifact_at_its_declared_path(repo: Path) -> None:
    """Control 1: a known-PRESENT artifact must be found."""
    (repo / "command-center" / "real.json").write_text('{"a":1}', encoding="utf-8")
    _commit_all(repo)
    report = rd.reconcile(
        repo, _catalog([{"id": "U-1", "output_path": "command-center/real.json"}])
    )
    assert report["rows"][0]["disposition"] == "DELIVERED-AT-DECLARED-PATH"


def test_silent_on_a_known_absent_artifact(repo: Path) -> None:
    """Control 2: a path that does not exist must NOT be scored as delivered."""
    (repo / "command-center" / "unrelated.json").write_text("{}", encoding="utf-8")
    _commit_all(repo)
    report = rd.reconcile(
        repo, _catalog([{"id": "U-1", "output_path": "command-center/ghost.json"}])
    )
    assert report["rows"][0]["disposition"] == "NOT-PRODUCED"
    assert report["delivered_any_form"] == 0


def test_an_empty_file_is_not_delivery(repo: Path) -> None:
    """Control 3: present-but-EMPTY must read as absent, not as a delivered artifact."""
    (repo / "command-center" / "hollow.json").write_text("", encoding="utf-8")
    _commit_all(repo)
    report = rd.reconcile(
        repo, _catalog([{"id": "U-1", "output_path": "command-center/hollow.json"}])
    )
    assert report["rows"][0]["disposition"] != "DELIVERED-AT-DECLARED-PATH"


def test_finds_the_same_artifact_moved_to_another_directory(repo: Path) -> None:
    """The whole point: the plan's namespace and delivery's namespace differ."""
    (repo / "delivered" / "moved.json").write_text('{"a":1}', encoding="utf-8")
    _commit_all(repo)
    report = rd.reconcile(
        repo, _catalog([{"id": "U-1", "output_path": "command-center/moved.json"}])
    )
    row = report["rows"][0]
    assert row["disposition"] == "DELIVERED-ELSEWHERE-EXACT"
    assert row["candidates"] == ["delivered/moved.json"]


def test_multiple_name_matches_are_flagged_ambiguous_not_silently_resolved(
    repo: Path,
) -> None:
    """Picking the first candidate would manufacture certainty the data does not support."""
    (repo / "delivered" / "dup.json").write_text("{}", encoding="utf-8")
    (repo / "command-center" / "sub").mkdir()
    (repo / "command-center" / "sub" / "dup.json").write_text("{}", encoding="utf-8")
    _commit_all(repo)
    report = rd.reconcile(
        repo, _catalog([{"id": "U-1", "output_path": "elsewhere/dup.json"}])
    )
    row = report["rows"][0]
    assert row["ambiguous"] is True
    assert len(row["candidates"]) == 2


def test_the_plan_restating_its_own_id_is_NOT_delivery(repo: Path) -> None:
    """The exact bug this tool shipped with, pinned so it cannot come back.

    A unit id inside `WORK-UNIT-CATALOG.json` is the plan naming itself. Counting it made
    the detector fire on 100% of units. With the exclusion the same input must read
    NOT-PRODUCED.
    """
    units = [{"id": "ADV-0001", "output_path": "command-center/never.json"}]
    (repo / "command-center" / "WORK-UNIT-CATALOG.json").write_text(
        json.dumps(_catalog(units)), encoding="utf-8"
    )
    _commit_all(repo)
    report = rd.reconcile(repo, _catalog(units))
    assert report["rows"][0]["disposition"] == "NOT-PRODUCED"
    assert report["declaring_docs_excluded_from_id_scan"] >= 1


def test_a_mention_OUTSIDE_the_plan_is_referenced_but_still_not_delivered(
    repo: Path,
) -> None:
    """UNIT-ID-REFERENCED must be its own verdict, never folded into a delivered count."""
    units = [{"id": "ADV-0001", "output_path": "command-center/never.json"}]
    (repo / "delivered" / "notes.md").write_text(
        "we worked on ADV-0001 today", encoding="utf-8"
    )
    _commit_all(repo)
    report = rd.reconcile(repo, _catalog(units))
    assert report["rows"][0]["disposition"] == "UNIT-ID-REFERENCED"
    assert report["delivered_any_form"] == 0


def test_fails_closed_on_an_empty_catalog(repo: Path) -> None:
    (repo / "command-center" / "x.json").write_text("{}", encoding="utf-8")
    _commit_all(repo)
    with pytest.raises(ValueError):
        rd.reconcile(repo, _catalog([]))
