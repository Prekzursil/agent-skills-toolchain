"""Both-states controls for the subworkflow-reference gate.

The gate's whole value is that it FIRES on the defect it was built for, so every test here builds a
throwaway git repo and plants the exact shape. Nothing reads or mutates this repository.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import refcheck as rc  # noqa: E402
from conftest import commit_all as _commit  # noqa: E402
from conftest import make_git_repo  # noqa: E402


def _repo(tmp_path: Path) -> Path:
    return make_git_repo(tmp_path / "r")


def _blueprint(source: str) -> str:
    return json.dumps(
        {
            "workflow_id": "bp-probe",
            "subworkflows": {
                "shared.thing": {"workflow_id": "shared.thing", "source": source}
            },
        }
    )


def test_fires_on_a_reference_to_an_uncommitted_file(tmp_path: Path) -> None:
    """THE defect: three committed blueprints pointed at uncommitted _shared/*.subworkflow.json."""
    root = _repo(tmp_path)
    (root / "wf").mkdir()
    (root / "wf" / "bp.json").write_text(
        _blueprint("wf/_shared/shared.thing.subworkflow.json"), encoding="utf-8"
    )
    _commit(root)
    # The target EXISTS on disk but was never committed - exactly the state the working tree hid.
    (root / "wf" / "_shared").mkdir()
    (root / "wf" / "_shared" / "shared.thing.subworkflow.json").write_text(
        "{}", encoding="utf-8"
    )

    report = rc.scan(root)
    assert report["references_checked"] == 1
    assert len(report["dangling"]) == 1
    entry = report["dangling"][0]
    assert entry["source"] == "wf/_shared/shared.thing.subworkflow.json"
    assert entry["referrer"] == "wf/bp.json"


def test_silent_once_the_target_is_committed(tmp_path: Path) -> None:
    """Both-states pair: committing the dependency must clear the finding, nothing else."""
    root = _repo(tmp_path)
    (root / "wf" / "_shared").mkdir(parents=True)
    (root / "wf" / "bp.json").write_text(
        _blueprint("wf/_shared/shared.thing.subworkflow.json"), encoding="utf-8"
    )
    (root / "wf" / "_shared" / "shared.thing.subworkflow.json").write_text(
        "{}", encoding="utf-8"
    )
    _commit(root)

    report = rc.scan(root)
    assert report["references_checked"] == 1
    assert report["dangling"] == []


def test_the_list_form_of_subworkflows_is_walked_too(tmp_path: Path) -> None:
    """Both container shapes occur in the corpus; walking only one would half-measure."""
    root = _repo(tmp_path)
    (root / "wf").mkdir()
    (root / "wf" / "bp.json").write_text(
        json.dumps(
            {
                "subworkflows": [
                    {"workflow_id": "a", "source": "wf/missing-a.json"},
                    {"workflow_id": "b", "source": "wf/missing-b.json"},
                ]
            }
        ),
        encoding="utf-8",
    )
    _commit(root)
    report = rc.scan(root)
    assert report["references_checked"] == 2
    assert len(report["dangling"]) == 2


def test_a_source_naming_a_DIRECTORY_resolves(tmp_path: Path) -> None:
    """Some corpus values name a directory; treating those as dangling would be a false positive."""
    root = _repo(tmp_path)
    (root / "wf" / "pack").mkdir(parents=True)
    (root / "wf" / "pack" / "inner.json").write_text("{}", encoding="utf-8")
    (root / "wf" / "bp.json").write_text(_blueprint("wf/pack"), encoding="utf-8")
    _commit(root)
    assert rc.scan(root)["dangling"] == []


def test_fixture_directories_are_skipped_and_counted(tmp_path: Path) -> None:
    """`platform/lib/wfdsl/examples/` holds schema fixtures whose source covers a field.

    Measured on the real repo: `wf-full-coverage.json` self-describes as the DSL conformance
    workhorse, and `platform/lib/wfdsl/semantics.py:658,672` reads `subworkflows` only as a set of
    declared NAMES to cross-check workflow_id - nothing opens the path. Creating the file would
    satisfy no consumer.
    """
    root = _repo(tmp_path)
    ex = root / "platform" / "lib" / "wfdsl" / "examples"
    ex.mkdir(parents=True)
    (ex / "wf-full-coverage.json").write_text(
        _blueprint("platform/workflows/does-not-exist.json"), encoding="utf-8"
    )
    _commit(root)
    report = rc.scan(root)
    assert report["dangling"] == [], "a fixture directory must not produce a finding"
    assert int(report["fixture_files_skipped"]) >= 1, (
        "the skip must be COUNTED, not silent; an uncounted exclusion is how a gate quietly stops "
        "measuring"
    )


def test_a_backslash_source_is_normalised(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    (root / "wf" / "pack").mkdir(parents=True)
    (root / "wf" / "pack" / "inner.json").write_text("{}", encoding="utf-8")
    (root / "wf" / "bp.json").write_text(
        _blueprint("wf\\pack\\inner.json"), encoding="utf-8"
    )
    _commit(root)
    assert rc.scan(root)["dangling"] == []


def test_scan_fails_closed_on_an_empty_repo(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    with pytest.raises(ValueError, match="fail closed"):
        rc.scan(root)


def _git_can_read_this_repo() -> bool:
    """Can git enumerate THIS checkout at all?

    False in exactly one known situation, and it is an environment artifact rather than a defect:
    this checkout is a git WORKTREE, so its `.git` is a FILE containing
    `gitdir: C:/Users/.../worktrees/ast-integrate` - a Windows absolute path. Under WSL that path
    does not resolve, git reports "not a git repository", and `ls-files` returns nothing.

    A CI runner uses a normal `git clone` with a real `.git` DIRECTORY and enumerates ~9,500 files,
    so the two live-repo assertions below DO run in the environment that gates merges. The condition
    is deliberately narrow - git returning nothing AT ALL - so it can never mask a genuine dangling
    reference, only an unreadable repository.
    """
    return bool(rc.tracked(rc.REPO))


NEEDS_GIT = pytest.mark.skipif(
    not _git_can_read_this_repo(),
    reason=(
        "git cannot enumerate this checkout - a worktree whose .git file names a Windows absolute "
        "gitdir, unresolvable under WSL. NOT-CHECKED here rather than pass or fail; CI uses a real "
        "clone and does run this."
    ),
)


@NEEDS_GIT
def test_the_cli_refuses_a_collapsed_walk() -> None:
    """A gate reporting `0 dangling` because it found NOTHING is a no-op wearing a green badge.

    MIN_REFERENCES is asserted against the real repo, so if the walk ever breaks the CLI fails
    rather than congratulating itself.
    """
    assert rc.MIN_REFERENCES > 0
    report = rc.scan()
    assert int(report["references_checked"]) >= rc.MIN_REFERENCES, (
        f"real repo has {report['references_checked']} references, below the floor "
        f"{rc.MIN_REFERENCES}; either the corpus shrank or the walk broke"
    )


@NEEDS_GIT
def test_the_real_repo_has_no_dangling_subworkflow_sources() -> None:
    """The live assertion. If this fails, a committed document depends on an uncommitted path."""
    report = rc.scan()
    assert report["dangling"] == [], (
        f"dangling subworkflow sources: {report['dangling']}"
    )
