"""Controls for committed-blob reading. TST-0334's three required tests.

Every test builds its own throwaway git repo, so nothing here depends on this repository's state or
mutates it - the "a test that runs with cwd=REPO silently repairs the real tree" shape this program
already found once.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import blobread as br  # noqa: E402

CRLF_BODY = b"line one\r\nline two\r\nline three\r\n"
LF_BODY = b"line one\nline two\nline three\n"


def _repo(tmp_path: Path) -> Path:
    root = tmp_path / "r"
    root.mkdir()
    run = lambda *a: subprocess.run(  # noqa: E731 - terse local helper
        ["git", "-C", str(root), *a], check=True, capture_output=True
    )
    subprocess.run(["git", "init", "-q", str(root)], check=True, capture_output=True)
    run("config", "user.email", "t@t")
    run("config", "user.name", "t")
    return root


def _commit_lf_checkout_crlf(root: Path, rel: str) -> None:
    """Commit LF bytes, then materialise CRLF in the working tree.

    This is the exact production situation: git stores LF, a Windows checkout under
    core.autocrlf=true writes CRLF, and any content check has to choose which it means.
    Reproduced by writing the two forms explicitly rather than relying on the box's autocrlf, so
    the test behaves the same on Linux CI.
    """
    path = root / rel
    path.write_bytes(LF_BODY)
    subprocess.run(
        ["git", "-C", str(root), "add", rel], check=True, capture_output=True
    )
    subprocess.run(
        ["git", "-C", str(root), "commit", "-qm", "lf"], check=True, capture_output=True
    )
    path.write_bytes(CRLF_BODY)  # the working tree now diverges from the blob


def test_read_blob_returns_the_committed_lf_bytes_not_the_crlf_worktree(
    tmp_path: Path,
) -> None:
    """TST-0334's core claim, and the one a formatter gate depends on."""
    root = _repo(tmp_path)
    _commit_lf_checkout_crlf(root, "f.txt")

    blob = br.read_blob("f.txt", "HEAD", repo=root)
    assert blob == LF_BODY
    assert br.crlf_count(blob) == 0, "the committed blob must have no CRLF"
    assert br.crlf_count((root / "f.txt").read_bytes()) == 3, (
        "the worktree must have CRLF"
    )
    assert blob != (root / "f.txt").read_bytes(), (
        "if these were equal the fixture would not reproduce the defect and every assertion "
        "below would be vacuous"
    )


def test_three_route_comparison_reports_counts_and_crlf_for_each_route(
    tmp_path: Path,
) -> None:
    """TST-0334 test 1: byte counts and CRLF counts from all routes, demonstrated not asserted."""
    root = _repo(tmp_path)
    _commit_lf_checkout_crlf(root, "f.txt")

    report = br.three_route_comparison("f.txt", "HEAD", repo=root)
    routes = report["routes"]
    assert routes["git_cat_file"]["crlf"] == 0
    assert routes["git_show"]["crlf"] == 0
    assert routes["working_tree"]["crlf"] == 3
    assert routes["git_cat_file"]["bytes"] < routes["working_tree"]["bytes"], (
        "CRLF must make the worktree form larger; equal sizes mean the fixture did not diverge"
    )


def test_the_control_proves_the_difference_is_line_endings_not_content(
    tmp_path: Path,
) -> None:
    """TST-0334 test 3. Without this control the report cannot distinguish EOL from real drift."""
    root = _repo(tmp_path)
    _commit_lf_checkout_crlf(root, "f.txt")

    report = br.three_route_comparison("f.txt", "HEAD", repo=root)
    assert report["control_identical_after_lf_normalisation"] is True
    assert len(set(report["lf_normalised_digests"].values())) == 1
    assert "ONLY in line endings" in report["verdict"]


def test_the_control_FIRES_when_the_content_genuinely_differs(tmp_path: Path) -> None:
    """The control's own both-states proof: it must not report 'only line endings' for real drift.

    A control that says 'identical after normalisation' no matter what measures nothing.
    """
    root = _repo(tmp_path)
    _commit_lf_checkout_crlf(root, "f.txt")
    (root / "f.txt").write_bytes(b"COMPLETELY different content\r\n")

    report = br.three_route_comparison("f.txt", "HEAD", repo=root)
    assert report["control_identical_after_lf_normalisation"] is False
    assert "CONTENT" in report["verdict"]


def test_git_archive_is_measured_so_the_refusal_is_evidence_backed(
    tmp_path: Path,
) -> None:
    """`git archive` is the trap the prescribing rule got wrong until 2026-08-09.

    Measured rather than asserted: the archive route is reported alongside the others so a reader
    can see why it is not used, instead of taking it on faith.
    """
    root = _repo(tmp_path)
    _commit_lf_checkout_crlf(root, "f.txt")
    report = br.three_route_comparison("f.txt", "HEAD", repo=root)
    assert "git_archive_tar_bytes" in report["routes"], (
        "the archive route must appear in the report; silently omitting it would hide the trap"
    )


def test_an_absent_path_raises_rather_than_returning_empty(tmp_path: Path) -> None:
    """Fail closed. Returning b'' for a missing path would make every content check trivially pass."""
    root = _repo(tmp_path)
    _commit_lf_checkout_crlf(root, "f.txt")
    with pytest.raises(br.BlobReadError):
        br.read_blob("no-such-file.txt", "HEAD", repo=root)


def test_backslash_paths_are_accepted_and_normalised(tmp_path: Path) -> None:
    """A Windows-shaped path is not a valid git pathspec; callers on this box will pass one anyway."""
    root = _repo(tmp_path)
    (root / "sub").mkdir()
    (root / "sub" / "g.txt").write_bytes(LF_BODY)
    subprocess.run(
        ["git", "-C", str(root), "add", "-A"], check=True, capture_output=True
    )
    subprocess.run(
        ["git", "-C", str(root), "commit", "-qm", "s"], check=True, capture_output=True
    )

    assert br.read_blob("sub\\g.txt", "HEAD", repo=root) == LF_BODY
