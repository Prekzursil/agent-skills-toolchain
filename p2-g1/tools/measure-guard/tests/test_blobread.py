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


def test_git_archive_payload_is_byte_identical_to_the_WORKTREE_not_the_blob(
    tmp_path: Path,
) -> None:
    """`git archive` is the trap the prescribing rule got wrong until 2026-08-09.

    Asserts the strongest available form: the EXTRACTED member is byte-identical to the working
    tree, same sha256, and differs from the committed blob. An earlier version of this test only
    checked that the route key was present, which would have passed even if the payload had been
    the blob - it asserted the report's shape rather than the claim.

    Extraction matters. Counting CRLF across the whole tar CONTAINER happens to work for
    `--format=tar` and silently inverts to 0 for `--format=tar.gz` or `--format=zip`, which would
    turn this check into "git archive is LF-clean" - a false negative in the exact gate the module
    exists to provide.
    """
    root = _repo(tmp_path)
    _commit_lf_checkout_crlf(root, "f.txt")
    report = br.three_route_comparison("f.txt", "HEAD", repo=root)
    routes = report["routes"]

    assert "git_archive" in routes, (
        "the archive route must appear; silently omitting it would hide the trap"
    )

    # WHETHER CONVERSION APPLIES IS MEASURED, NOT GUESSED FROM sys.platform. An earlier version of
    # this test asserted archive == working_tree unconditionally and passed on Windows while failing
    # on a Linux runner with archive at 29 bytes / 0 CRLF against a worktree of 32 / 3. That was the
    # same platform-specific-assertion-without-a-gate defect fixed in
    # platform/coordination/test_leases.py earlier in this session - repeating it was worse than the
    # original, and the CI failure is what caught it.
    #
    # The underlying FACT is narrower than "git archive returns the worktree bytes": archive applies
    # export-time EOL conversion WHERE CONFIGURED. On a Windows checkout with autocrlf that yields
    # CRLF; on a stock Linux runner it yields the blob unchanged. So the trap is real but scoped, and
    # branching on the measured behaviour keeps a discriminating assertion on BOTH platforms rather
    # than skipping one.
    conversion_applied = (
        routes["git_archive"]["sha256_12"] != routes["git_cat_file"]["sha256_12"]
    )
    if conversion_applied:
        assert routes["git_archive"] == routes["working_tree"], (
            "where export conversion applies, the archive payload must match the WORKING TREE byte "
            "for byte - that is exactly what makes it the wrong bytes to verify a blob against"
        )
        assert routes["git_archive"]["crlf"] > 0
    else:
        assert routes["git_archive"] == routes["git_cat_file"], (
            "with no export conversion the archive payload must equal the blob; if it matched "
            "neither the blob nor the worktree, something else is rewriting it and the whole "
            "comparison is untrustworthy"
        )
        assert routes["git_archive"]["crlf"] == 0

    # Platform-independent and the module's actual thesis: cat-file NEVER applies conversion, so it
    # is the route to trust. This holds on every platform and is what a caller relies on.
    assert routes["git_cat_file"] == routes["git_show"], (
        "cat-file and show must agree; both read the blob"
    )
    assert routes["git_cat_file"]["crlf"] == 0, (
        "the committed blob is LF and cat-file must report it as such regardless of platform"
    )


def test_the_lf_control_now_covers_the_archive_route_too(tmp_path: Path) -> None:
    """The archive route was previously excluded from the content control.

    That left the one route the module exists to indict as the only route with no content check, so
    a genuine content difference in the archive payload would have gone unnoticed.
    """
    root = _repo(tmp_path)
    _commit_lf_checkout_crlf(root, "f.txt")
    report = br.three_route_comparison("f.txt", "HEAD", repo=root)
    assert "git_archive" in report["lf_normalised_digests"], (
        "the archive route must be inside the LF-normalisation control, not exempt from it"
    )
    assert report["control_identical_after_lf_normalisation"] is True


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


def test_known_file_blob_bytes() -> dict:
    """IMP-0440: helper refuses to treat the worktree as the blob."""
    import tempfile

    with tempfile.TemporaryDirectory(prefix="imp0440-known-") as td:
        root = _repo(Path(td))
        _commit_lf_checkout_crlf(root, "known.txt")
        blob = br.blob_bytes("HEAD", "known.txt", repo=root)
        tree = (root / "known.txt").read_bytes()
        ok = blob == LF_BODY and tree == CRLF_BODY and blob != tree
        if not ok:
            raise AssertionError("known-file blob_bytes did not separate blob from worktree")
        return {"ok": True, "pass": True, "blob_crlf": br.crlf_count(blob), "tree_crlf": br.crlf_count(tree)}


def test_helper_refuses_archive_in_source() -> dict:
    src = Path(br.__file__).read_text(encoding="utf-8")
    if "git archive" in src and "REFUSED" not in src and "refuse" not in src.lower():
        raise AssertionError("blobread no longer refuses git archive")
    return {"ok": True, "pass": True, "refuses_archive": True}


def test_worktree_is_not_oracle() -> dict:
    src = Path(br.__file__).read_text(encoding="utf-8")
    if "working tree" not in src.lower() and "worktree" not in src.lower():
        raise AssertionError("blobread no longer documents the worktree trap")
    return {"ok": True, "pass": True, "worktree_not_oracle": True}
