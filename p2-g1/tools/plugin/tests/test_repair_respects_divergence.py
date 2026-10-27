#!/usr/bin/env python3
"""IMP-0025: two-way repair refuses DIVERGED; one-directional mutant overwrites it."""
from __future__ import annotations

from pathlib import Path

DIVERGED_REL = "rules/common/both-unique.md"
REPO_AHEAD_REL = "rules/project/testing.md"
LIVE_UNIQUE = "live unique marker IMP0025"
REPO_UNIQUE = "repo unique marker IMP0025-long-enough-to-win-one-directional"


def plant_pair(root: Path) -> tuple[Path, Path]:
    repo = Path(root) / "repo"
    live = Path(root) / "live"
    shared_d = "# diverged shared\n"
    (repo / DIVERGED_REL).parent.mkdir(parents=True, exist_ok=True)
    (live / DIVERGED_REL).parent.mkdir(parents=True, exist_ok=True)
    (repo / DIVERGED_REL).write_text(shared_d + REPO_UNIQUE + "\n", encoding="utf-8")
    (live / DIVERGED_REL).write_text(shared_d + LIVE_UNIQUE + "\n", encoding="utf-8")
    shared_r = "# repo-ahead shared\n"
    (repo / REPO_AHEAD_REL).parent.mkdir(parents=True, exist_ok=True)
    (live / REPO_AHEAD_REL).parent.mkdir(parents=True, exist_ok=True)
    (repo / REPO_AHEAD_REL).write_text(shared_r + REPO_UNIQUE + "\n", encoding="utf-8")
    (live / REPO_AHEAD_REL).write_text(shared_r, encoding="utf-8")
    return repo, live


def test_diverged_files_never_touched(one_directional: bool = False) -> None:
    import tempfile

    from plugin.repair import apply_repair

    with tempfile.TemporaryDirectory(prefix="imp0025-div-") as tmp:
        repo, live = plant_pair(Path(tmp))
        before = (live / DIVERGED_REL).read_bytes()
        plan = apply_repair(repo, live, one_directional=one_directional, dry_run=False)
        after = (live / DIVERGED_REL).read_bytes()
        assert DIVERGED_REL not in plan["applied"]
        assert after == before
        assert LIVE_UNIQUE.encode() in after


def test_negative_control_diverged_refused_repo_ahead_repaired() -> None:
    import tempfile

    from plugin.repair import apply_repair

    with tempfile.TemporaryDirectory(prefix="imp0025-neg-") as tmp:
        repo, live = plant_pair(Path(tmp))
        before = (live / DIVERGED_REL).read_bytes()
        plan = apply_repair(repo, live, one_directional=False, dry_run=False)
        after = (live / DIVERGED_REL).read_bytes()
        repo_ahead_after = (live / REPO_AHEAD_REL).read_bytes()
        assert DIVERGED_REL not in plan["applied"]
        assert REPO_AHEAD_REL in plan["applied"]
        assert after == before
        assert LIVE_UNIQUE.encode() in after
        assert REPO_UNIQUE.encode() in repo_ahead_after


def test_mutation_one_directional_makes_diverged_test_go_red() -> None:
    try:
        test_diverged_files_never_touched(one_directional=True)
    except AssertionError:
        return
    raise AssertionError("one-directional mutant did not make diverged test go red")


if __name__ == "__main__":
    test_negative_control_diverged_refused_repo_ahead_repaired()
    test_diverged_files_never_touched(one_directional=False)
    test_mutation_one_directional_makes_diverged_test_go_red()
    print("SUCCESS:IMP-0025 tests")
