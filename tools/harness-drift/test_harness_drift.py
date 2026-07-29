"""Tests for the deterministic harness drift differ.

The load-bearing property is the two-directional read. The measured failure this
module replaces was 31 files classified deploy-safe that were actually two-way
DIVERGED, because the classifier only ever asked "does the repo have extra content".
:func:`test_live_unique_lines_alone_never_reads_as_repo_ahead` and
:func:`test_diverged_requires_both_directions` are the tests that fail if that
one-directional blind spot is ever reintroduced.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

import harness_drift as hd


# --------------------------------------------------------------------------
# normalise()
# --------------------------------------------------------------------------


def test_normalise_collapses_crlf_and_cr_to_lf() -> None:
    assert hd.normalise(b"a\r\nb\rc\nd") == ["a", "b", "c", "d"]


def test_normalise_strips_utf8_bom() -> None:
    assert hd.normalise("﻿hello".encode()) == ["hello"]


def test_normalise_returns_none_for_undecodable_bytes() -> None:
    assert hd.normalise(b"\xff\xfe\x00\x01binary") is None


# --------------------------------------------------------------------------
# two_directional_diff() / classify()
# --------------------------------------------------------------------------


def test_identical_line_lists_produce_no_unique_lines() -> None:
    assert hd.two_directional_diff(["a", "b"], ["a", "b"]) == (0, 0, 0)


def test_repo_superset_counts_only_repo_lines() -> None:
    only_repo, only_live, hunks = hd.two_directional_diff(["a", "b", "c"], ["a", "c"])
    assert (only_repo, only_live) == (1, 0)
    assert hunks == 1
    assert hd.classify(only_repo, only_live) == hd.V_REPO_AHEAD


def test_live_unique_lines_alone_never_reads_as_repo_ahead() -> None:
    """The exact shape a one-directional reader mis-called deploy-safe."""
    only_repo, only_live, _ = hd.two_directional_diff(["a", "c"], ["a", "b", "c"])
    assert (only_repo, only_live) == (0, 1)
    assert hd.classify(only_repo, only_live) == hd.V_LIVE_AHEAD
    assert hd.classify(only_repo, only_live) != hd.V_REPO_AHEAD


def test_diverged_requires_both_directions() -> None:
    only_repo, only_live, _ = hd.two_directional_diff(["a", "x"], ["a", "y", "z"])
    assert only_repo > 0
    assert only_live > 0
    assert hd.classify(only_repo, only_live) == hd.V_DIVERGED


def test_a_pure_move_classifies_as_diverged_not_safe() -> None:
    """Reordering is not an overwrite-safe change; it must land in DIVERGED."""
    only_repo, only_live, _ = hd.two_directional_diff(["a", "b"], ["b", "a"])
    assert hd.classify(only_repo, only_live) == hd.V_DIVERGED


def test_classify_no_unique_lines_is_noise() -> None:
    assert hd.classify(0, 0) == hd.V_NOISE


# --------------------------------------------------------------------------
# sha256_of() / compare_pair()
# --------------------------------------------------------------------------


def test_sha256_of_streams_files_larger_than_one_chunk(tmp_path: Path) -> None:
    blob = tmp_path / "big.bin"
    payload = b"z" * (hd._CHUNK * 2 + 7)
    blob.write_bytes(payload)
    digest, size = hd.sha256_of(blob)
    assert size == len(payload)
    assert len(digest) == 64


def _pair(tmp_path: Path, repo_bytes: bytes, live_bytes: bytes) -> hd.Row:
    repo_file = tmp_path / "repo.txt"
    live_file = tmp_path / "live.txt"
    repo_file.write_bytes(repo_bytes)
    live_file.write_bytes(live_bytes)
    return hd.compare_pair("hooks", "hooks/x.txt", repo_file, live_file)


def test_compare_pair_byte_equal_is_identical(tmp_path: Path) -> None:
    row = _pair(tmp_path, b"same\n", b"same\n")
    assert row.verdict == hd.V_IDENTICAL
    assert row.repo_sha256 == row.live_sha256
    assert row.note == ""


def test_compare_pair_line_ending_only_is_noise(tmp_path: Path) -> None:
    row = _pair(tmp_path, b"a\r\nb\r\n", b"a\nb\n")
    assert row.verdict == hd.V_NOISE
    assert row.repo_sha256 != row.live_sha256
    assert "normalised-identical" in row.note


def test_compare_pair_live_extra_line_is_live_ahead(tmp_path: Path) -> None:
    row = _pair(tmp_path, b"a\n", b"a\nextra\n")
    assert row.verdict == hd.V_LIVE_AHEAD
    assert row.only_live_lines == 1
    assert row.only_repo_lines == 0


def test_compare_pair_two_way_change_is_diverged(tmp_path: Path) -> None:
    row = _pair(tmp_path, b"a\nrepo\n", b"a\nlive\nmore\n")
    assert row.verdict == hd.V_DIVERGED
    assert row.only_repo_lines > 0
    assert row.only_live_lines > 0
    assert row.changed_hunks >= 1


@pytest.mark.parametrize(
    ("repo_bytes", "live_bytes"),
    [
        (b"\xff\xfe\x00ok", b"text\n"),
        (b"text\n", b"\xff\xfe\x00ok"),
    ],
)
def test_compare_pair_undecodable_either_side_is_diverged_binary(
    tmp_path: Path, repo_bytes: bytes, live_bytes: bytes
) -> None:
    row = _pair(tmp_path, repo_bytes, live_bytes)
    assert row.verdict == hd.V_DIVERGED_BIN
    assert "not UTF-8 decodable" in row.note


# --------------------------------------------------------------------------
# walk_tree()
# --------------------------------------------------------------------------


def _summary() -> hd.Summary:
    return hd.Summary()


def test_walk_tree_missing_root_yields_nothing(tmp_path: Path) -> None:
    assert hd.walk_tree(tmp_path / "nope", _summary(), "x") == {}


def test_walk_tree_collects_nested_files_with_posix_keys(tmp_path: Path) -> None:
    (tmp_path / "a" / "b").mkdir(parents=True)
    (tmp_path / "a" / "b" / "c.md").write_text("hi", encoding="utf-8")
    (tmp_path / "top.md").write_text("hi", encoding="utf-8")
    found = hd.walk_tree(tmp_path, _summary(), "x")
    assert sorted(found) == ["a/b/c.md", "top.md"]


def test_walk_tree_skips_excluded_dirs_and_backup_dirs(tmp_path: Path) -> None:
    for name in ("__pycache__", "_pre-frontmatter-20260727-064859", "_fleet-backups"):
        (tmp_path / name).mkdir()
        (tmp_path / name / "f.md").write_text("x", encoding="utf-8")
    (tmp_path / "_shared").mkdir()
    (tmp_path / "_shared" / "keep.md").write_text("x", encoding="utf-8")
    found = hd.walk_tree(tmp_path, _summary(), "x")
    assert sorted(found) == ["_shared/keep.md"]


def test_walk_tree_skips_generated_and_backup_files(tmp_path: Path) -> None:
    for name in ("a.pyc", "b.log", "c.md.bak", "d.md.bak-fleet-20260713", "e.orig"):
        (tmp_path / name).write_text("x", encoding="utf-8")
    (tmp_path / "keep.md").write_text("x", encoding="utf-8")
    assert sorted(hd.walk_tree(tmp_path, _summary(), "x")) == ["keep.md"]


def test_walk_tree_skips_nested_repositories(tmp_path: Path) -> None:
    nested = tmp_path / "RsaCtfTool"
    (nested / ".git").mkdir(parents=True)
    (nested / "main.py").write_text("x", encoding="utf-8")
    summary = _summary()
    assert hd.walk_tree(tmp_path, summary, "live/skills") == {}
    assert summary.skipped_nested_repos == [f"live/skills:{hd._posix(nested)}"]


def test_walk_tree_skips_symlinked_dirs_and_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Patched rather than real: a Windows symlink needs elevation, so a test that
    creates one silently skips instead of measuring."""
    (tmp_path / "linkdir").mkdir()
    (tmp_path / "linkdir" / "inner.md").write_text("x", encoding="utf-8")
    (tmp_path / "linkfile.md").write_text("x", encoding="utf-8")
    (tmp_path / "real.md").write_text("x", encoding="utf-8")
    fake = {tmp_path / "linkdir", tmp_path / "linkfile.md"}
    monkeypatch.setattr(hd, "is_symlink", lambda p: p in fake)
    summary = _summary()
    assert sorted(hd.walk_tree(tmp_path, summary, "live/x")) == ["real.md"]
    assert len(summary.skipped_symlinks) == 2


def test_is_symlink_delegates_to_pathlib(tmp_path: Path) -> None:
    plain = tmp_path / "plain.md"
    plain.write_text("x", encoding="utf-8")
    assert hd.is_symlink(plain) is False


# --------------------------------------------------------------------------
# _head_of()
# --------------------------------------------------------------------------


def test_head_of_returns_the_sha_for_a_real_repo(tmp_path: Path) -> None:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    subprocess.run(
        ["git", "-C", str(tmp_path), "config", "user.email", "t@e"], check=True
    )
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.name", "t"], check=True)
    (tmp_path / "f.md").write_text("x", encoding="utf-8")
    subprocess.run(["git", "-C", str(tmp_path), "add", "f.md"], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "commit", "-qm", "c"], check=True)
    assert len(hd._head_of(tmp_path)) == 40


def test_head_of_is_unknown_when_git_cannot_answer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def boom(*_a: object, **_k: object) -> None:
        raise OSError("git missing")

    monkeypatch.setattr(hd.subprocess, "run", boom)
    assert hd._head_of(tmp_path) == "UNKNOWN"


# --------------------------------------------------------------------------
# run() end-to-end over a synthetic estate
# --------------------------------------------------------------------------


@pytest.fixture()
def estate(tmp_path: Path) -> tuple[Path, Path]:
    """A synthetic repo+live pair exercising every verdict in one pass."""
    repo = tmp_path / "repo"
    live = tmp_path / "home"
    hooks_repo = repo / "hooks"
    hooks_live = live / ".claude" / "hooks"
    for d in (hooks_repo, hooks_live):
        d.mkdir(parents=True)
    (hooks_repo / "same.py").write_text("x = 1\n", encoding="utf-8")
    (hooks_live / "same.py").write_text("x = 1\n", encoding="utf-8")
    (hooks_repo / "crlf.py").write_bytes(b"x = 1\r\n")
    (hooks_live / "crlf.py").write_bytes(b"x = 1\n")
    (hooks_repo / "repo_ahead.py").write_text("a\nb\n", encoding="utf-8")
    (hooks_live / "repo_ahead.py").write_text("a\n", encoding="utf-8")
    (hooks_repo / "live_ahead.py").write_text("a\n", encoding="utf-8")
    (hooks_live / "live_ahead.py").write_text("a\nb\n", encoding="utf-8")
    (hooks_repo / "diverged.py").write_text("a\nrepo\n", encoding="utf-8")
    (hooks_live / "diverged.py").write_text("a\nlive\nmore\n", encoding="utf-8")
    (hooks_repo / "repo_only.py").write_text("a\n", encoding="utf-8")
    (hooks_live / "live_only.py").write_text("a\n", encoding="utf-8")
    return repo, live


def test_run_produces_every_verdict_and_area_counts(estate: tuple[Path, Path]) -> None:
    repo, live = estate
    summary, rows = hd.run(repo, live, only_areas={"hooks"})
    verdicts = {r.repo_path: r.verdict for r in rows}
    assert verdicts == {
        "hooks/crlf.py": hd.V_NOISE,
        "hooks/diverged.py": hd.V_DIVERGED,
        "hooks/live_ahead.py": hd.V_LIVE_AHEAD,
        "hooks/live_only.py": hd.V_LIVE_ONLY,
        "hooks/repo_ahead.py": hd.V_REPO_AHEAD,
        "hooks/repo_only.py": hd.V_REPO_ONLY,
        "hooks/same.py": hd.V_IDENTICAL,
    }
    assert summary.areas == ["hooks"]
    assert summary.total_rows == 7
    assert summary.counts[hd.V_DIVERGED] == 1
    assert summary.counts_by_area["hooks"][hd.V_LIVE_AHEAD] == 1


def test_run_one_sided_rows_carry_only_their_own_side(
    estate: tuple[Path, Path],
) -> None:
    repo, live = estate
    _, rows = hd.run(repo, live, only_areas={"hooks"})
    by_path = {r.repo_path: r for r in rows}
    repo_only = by_path["hooks/repo_only.py"]
    assert repo_only.repo_sha256 is not None
    assert repo_only.live_sha256 is None
    assert repo_only.note == "absent from live tree"
    live_only = by_path["hooks/live_only.py"]
    assert live_only.live_sha256 is not None
    assert live_only.repo_sha256 is None
    assert live_only.note == "absent from repo tree"


def test_run_records_missing_live_roots(estate: tuple[Path, Path]) -> None:
    repo, live = estate
    summary, _ = hd.run(repo, live, only_areas={"rules"})
    assert summary.missing_live_roots == [f"rules:{hd._posix(live / '.claude/rules')}"]


def test_run_without_area_filter_visits_every_mapped_area(
    estate: tuple[Path, Path],
) -> None:
    repo, live = estate
    summary, _ = hd.run(repo, live)
    assert summary.areas == [label for _, _, label in hd.AREA_MAP]


# --------------------------------------------------------------------------
# main()
# --------------------------------------------------------------------------


def test_main_writes_json_and_prints_counts(
    estate: tuple[Path, Path], tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo, live = estate
    out = tmp_path / "nested" / "drift.json"
    code = hd.main(
        [
            "--repo-root",
            str(repo),
            "--live-home",
            str(live),
            "--out",
            str(out),
            "--area",
            "hooks",
        ]
    )
    assert code == 0
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["summary"]["schema"] == "harness-drift/v2-deterministic"
    assert len(payload["rows"]) == 7
    captured = capsys.readouterr().out
    assert "rows=7" in captured
    assert hd.V_DIVERGED in captured


def test_main_defaults_repo_root_to_the_checkout(tmp_path: Path) -> None:
    """Exercises the argparse defaults; --live-home is redirected at an empty tree so
    the assertion never depends on the real machine's ~/.claude."""
    out = tmp_path / "d.json"
    code = hd.main(["--live-home", str(tmp_path), "--out", str(out), "--area", "rules"])
    assert code == 0
    payload = json.loads(out.read_text(encoding="utf-8"))
    expected_root = hd._posix(Path(hd.__file__).resolve().parents[2])
    assert payload["summary"]["repo_root"] == expected_root
    # Every repo rules/ file must land as REPO-ONLY against an empty live tree.
    assert payload["summary"]["counts"] == {
        hd.V_REPO_ONLY: payload["summary"]["total_rows"]
    }
