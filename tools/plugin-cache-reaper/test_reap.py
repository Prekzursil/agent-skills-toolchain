"""Regression suite for the plugin-cache staging reaper.

Every test here encodes a safety property of a tool that deletes from a LIVE
user directory, so the interesting cases are the refusals, not the deletions:

* a real cache entry (``cache/<marketplace>/<plugin>/<version>``) is never a
  candidate, no matter how old it is;
* a husk that is still young by EITHER age signal is never a candidate;
* a path that is not a ``.../plugins/cache`` directory is refused outright;
* dry-run deletes nothing.

The husk fixtures reproduce the DEFINING trait of a real husk -- a partial .git with
nothing checked out. They do NOT reproduce its shape: six live husks had 20/1/4/19/22/15
children, so the single-child fixture is a simplification. Candidacy is name-based
(STAGING_RE), never child-count-based, so the simplification does not weaken the tests. The only child
of an abandoned staging dir is ``.git``.
"""

from __future__ import annotations

import os
import stat
from pathlib import Path

import pytest

import reap

HEAD_BYTES = b"ref: refs/heads/main\n"
MINUTE_MS = 60_000
NOW = 1_785_340_000_000


def make_cache(tmp_path: Path) -> Path:
    root = tmp_path / "plugins" / "cache"
    root.mkdir(parents=True)
    return root


def make_husk(root: Path, name: str, *, mtime_ms: int, body: int = 3) -> Path:
    """Create a husk whose only child is a ``.git`` tree.

    A simplification: real husks carry 20/1/4/19/22/15 children (measured). Only the
    partial ``.git`` with no worktree is load-bearing, and matching is by name.
    """
    path = root / name
    objects = path / ".git" / "objects" / "pack"
    objects.mkdir(parents=True)
    (objects / "pack-deadbeef.pack").write_bytes(b"x" * body)
    # write_bytes, not write_text: on Windows the text writer would translate the
    # newline to CRLF and the byte tally would differ between platforms.
    (path / ".git" / "HEAD").write_bytes(HEAD_BYTES)
    seconds = mtime_ms / 1000
    os.utime(path, (seconds, seconds))
    return path


# --------------------------------------------------------------------------
# name parsing
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("temp_subdir_1785339700529_jhd39f.clone", ("subdir", 1785339700529)),
        ("temp_git_1785337883179_wzra7p", ("git", 1785337883179)),
        ("temp_github_1785337883179_wzra7p", ("github", 1785337883179)),
        ("temp_npm_1785337883179_wzra7p", ("npm", 1785337883179)),
        ("temp_local_1785337883179_wzra7p", ("local", 1785337883179)),
        ("temp_unknown_1785337883179_wzra7p", ("unknown", 1785337883179)),
    ],
)
def test_parse_staging_name_accepts_every_observed_shape(name, expected):
    assert reap.parse_staging_name(name) == expected


@pytest.mark.parametrize(
    "name",
    [
        "claude-plugins-official",
        "metaswarm-marketplace",
        "aikido",
        "1.2.3",
        "unknown",
        "temp_subdir_178533970052_jhd39f",  # 12-digit ms
        "temp_bogus_1785339700529_jhd39f",  # unknown kind
        "temp_subdir_1785339700529_JHD39F",  # uppercase suffix
        "temp_subdir_1785339700529_jhd39f.clone.bak",
        "xtemp_subdir_1785339700529_jhd39f",
    ],
)
def test_parse_staging_name_rejects_non_staging_names(name):
    assert reap.parse_staging_name(name) is None


# --------------------------------------------------------------------------
# the two-signal age gate
# --------------------------------------------------------------------------


def test_is_reapable_requires_both_signals_old():
    old = NOW - 10 * MINUTE_MS
    assert reap.is_reapable(
        name_ms=old, mtime_ms=old, now_ms=NOW, min_age_ms=5 * MINUTE_MS
    )


def test_is_reapable_refuses_when_name_is_young():
    assert not reap.is_reapable(
        name_ms=NOW - MINUTE_MS,
        mtime_ms=NOW - 10 * MINUTE_MS,
        now_ms=NOW,
        min_age_ms=5 * MINUTE_MS,
    )


def test_is_reapable_refuses_when_mtime_is_young():
    """An in-flight clone has an old-enough NAME but a fresh mtime."""
    assert not reap.is_reapable(
        name_ms=NOW - 10 * MINUTE_MS,
        mtime_ms=NOW - MINUTE_MS,
        now_ms=NOW,
        min_age_ms=5 * MINUTE_MS,
    )


# --------------------------------------------------------------------------
# long-path helper
# --------------------------------------------------------------------------


def test_long_path_prefixes_on_windows():
    assert reap.long_path(Path(r"C:\a\b"), windows=True) == r"\\?\C:\a\b"


def test_long_path_is_idempotent():
    once = reap.long_path(Path(r"C:\a"), windows=True)
    assert reap.long_path(Path(once), windows=True) == once


def test_long_path_is_untouched_off_windows():
    assert reap.long_path(Path("/a/b"), windows=False) == str(Path("/a/b"))


# --------------------------------------------------------------------------
# size walk
# --------------------------------------------------------------------------


def test_tree_size_bytes_sums_nested_files(tmp_path):
    root = make_cache(tmp_path)
    husk = make_husk(root, "temp_git_1785337883179_wzra7p", mtime_ms=NOW, body=7)
    assert reap.tree_size_bytes(husk, windows=False) == 7 + len(HEAD_BYTES)


def test_tree_size_bytes_returns_zero_for_missing_path(tmp_path):
    assert reap.tree_size_bytes(tmp_path / "nope", windows=False) == 0


def test_tree_size_bytes_skips_entries_that_raise(tmp_path, monkeypatch):
    """A husk can vanish mid-walk; that must not raise."""

    class Exploding:
        path = "irrelevant"

        def is_dir(self, follow_symlinks=True):
            raise OSError("gone")

    monkeypatch.setattr(reap.os, "scandir", lambda _p: [Exploding()])
    assert reap.tree_size_bytes(tmp_path, windows=False) == 0


# --------------------------------------------------------------------------
# deletion helpers
# --------------------------------------------------------------------------


def test_force_remove_clears_readonly_bit(tmp_path, monkeypatch):
    target = tmp_path / "pack-deadbeef.pack"
    target.write_bytes(b"x")
    os.chmod(target, stat.S_IREAD)
    calls: list[str] = []
    real_unlink = os.unlink

    def flaky_unlink(path):
        calls.append(str(path))
        if len(calls) == 1:
            raise PermissionError("read-only")
        real_unlink(path)

    monkeypatch.setattr(reap.os, "unlink", flaky_unlink)
    reap._force_remove(str(target))
    assert len(calls) == 2
    assert not target.exists()


def test_remove_tree_deletes_the_whole_husk(tmp_path):
    root = make_cache(tmp_path)
    husk = make_husk(root, "temp_git_1785337883179_wzra7p", mtime_ms=NOW)
    reap.remove_tree(husk, windows=False)
    assert not husk.exists()
    assert root.exists()


def test_remove_tree_tolerates_a_missing_path(tmp_path):
    """Covers both give-up paths: unscannable dir, and rmdir that cannot run."""
    reap.remove_tree(tmp_path / "already-gone", windows=False)
    assert tmp_path.exists()


# --------------------------------------------------------------------------
# root validation
# --------------------------------------------------------------------------


def test_validate_root_accepts_a_plugin_cache(tmp_path):
    reap.validate_root(make_cache(tmp_path))


@pytest.mark.parametrize("bad", ["cache", "other/cache", "plugins/store"])
def test_validate_root_refuses_anything_else(bad):
    with pytest.raises(ValueError, match="refusing to scan"):
        reap.validate_root(Path(bad))


def test_default_cache_root_points_at_the_plugin_cache():
    assert reap.default_cache_root().parts[-3:] == (".claude", "plugins", "cache")


# --------------------------------------------------------------------------
# candidate discovery
# --------------------------------------------------------------------------


def test_find_candidates_picks_only_old_husks(tmp_path):
    root = make_cache(tmp_path)
    old = NOW - 200 * MINUTE_MS
    make_husk(root, "temp_subdir_1785000000000_aaaaaa.clone", mtime_ms=old)
    make_husk(root, "temp_git_1785000000001_bbbbbb", mtime_ms=old)
    # a live clone: name is old but the tree is being written right now
    make_husk(root, "temp_git_1785000000002_cccccc", mtime_ms=NOW)
    # a real plugin cache entry, far older than any husk
    real = root / "claude-plugins-official" / "aikido" / "1.2.3"
    real.mkdir(parents=True)
    os.utime(root / "claude-plugins-official", ((NOW - 10**7) / 1000,) * 2)
    # a FILE that happens to be named like a husk, backdated so that the ONLY
    # thing keeping it out of the candidate list is the is-a-directory check
    decoy = root / "temp_git_1785000000003_dddddd"
    decoy.write_text("x", encoding="utf-8")
    os.utime(decoy, (old / 1000, old / 1000))

    found = reap.find_candidates(
        root, now_ms=NOW, min_age_ms=120 * MINUTE_MS, windows=False
    )
    assert [c.path.name for c in found] == [
        "temp_subdir_1785000000000_aaaaaa.clone",
        "temp_git_1785000000001_bbbbbb",
    ]
    assert all(c.size_bytes > 0 for c in found)


def test_find_candidates_can_skip_measuring(tmp_path):
    root = make_cache(tmp_path)
    make_husk(root, "temp_git_1785000000001_bbbbbb", mtime_ms=NOW - 10**7)
    found = reap.find_candidates(
        root, now_ms=NOW, min_age_ms=MINUTE_MS, windows=False, measure=False
    )
    assert [c.size_bytes for c in found] == [0]


def test_find_candidates_returns_empty_when_root_absent(tmp_path):
    root = tmp_path / "plugins" / "cache"
    assert (
        reap.find_candidates(root, now_ms=NOW, min_age_ms=MINUTE_MS, windows=False)
        == []
    )


# --------------------------------------------------------------------------
# reap()
# --------------------------------------------------------------------------


def test_reap_dry_run_deletes_nothing(tmp_path):
    root = make_cache(tmp_path)
    husk = make_husk(root, "temp_git_1785000000001_bbbbbb", mtime_ms=NOW - 10**7)
    report = reap.reap(
        root, now_ms=NOW, min_age_ms=MINUTE_MS, apply=False, windows=False
    )
    assert report["count"] == 1
    assert report["applied"] is False
    assert report["removed"] == []
    assert report["oldest"] == "temp_git_1785000000001_bbbbbb"
    assert husk.exists()


def test_reap_apply_removes_and_counts_by_kind(tmp_path):
    root = make_cache(tmp_path)
    old = NOW - 10**7
    for name in (
        "temp_git_1785000000001_bbbbbb",
        "temp_git_1785000000002_cccccc",
        "temp_subdir_1785000000003_dddddd.clone",
    ):
        make_husk(root, name, mtime_ms=old)
    report = reap.reap(
        root, now_ms=NOW, min_age_ms=MINUTE_MS, apply=True, windows=False
    )
    assert report["count"] == 3
    assert report["by_kind"] == {"git": 2, "subdir": 1}
    assert len(report["removed"]) == 3
    assert report["bytes"] > 0
    assert [p.name for p in root.iterdir()] == []


def test_reap_reports_nothing_for_a_clean_cache(tmp_path):
    root = make_cache(tmp_path)
    report = reap.reap(
        root, now_ms=NOW, min_age_ms=MINUTE_MS, apply=True, windows=False
    )
    assert report == {
        "root": str(root),
        "applied": True,
        "count": 0,
        "bytes": 0,
        "by_kind": {},
        "removed": [],
        "oldest": None,
    }


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


def test_main_dry_run_emits_a_success_marker(tmp_path, capsys):
    root = make_cache(tmp_path)
    make_husk(root, "temp_git_1785000000001_bbbbbb", mtime_ms=NOW - 10**7)
    code = main_with(["--root", str(root), "--min-age-minutes", "1"])
    out = capsys.readouterr().out
    assert code == 0
    assert out.startswith("SUCCESS:plugin-cache-reap would reap 1 staging dirs")


def test_main_apply_reports_reaped(tmp_path, capsys):
    root = make_cache(tmp_path)
    make_husk(root, "temp_git_1785000000001_bbbbbb", mtime_ms=NOW - 10**7)
    code = main_with(["--root", str(root), "--min-age-minutes", "1", "--apply"])
    out = capsys.readouterr().out
    assert code == 0
    assert "reaped 1 staging dirs" in out
    assert list(root.iterdir()) == []


def test_main_no_measure_reports_zero_bytes(tmp_path, capsys):
    root = make_cache(tmp_path)
    make_husk(root, "temp_git_1785000000001_bbbbbb", mtime_ms=NOW - 10**7)
    code = main_with(["--root", str(root), "--min-age-minutes", "1", "--no-measure"])
    assert code == 0
    assert "(0 bytes)" in capsys.readouterr().out


def test_main_refuses_a_zero_age_window(capsys):
    code = main_with(["--root", "x/plugins/cache", "--min-age-minutes", "0"])
    assert code == 2
    assert "must be >= 1" in capsys.readouterr().err


def test_main_refuses_a_root_that_is_not_a_plugin_cache(capsys):
    code = main_with(["--root", "some/other/dir"])
    assert code == 2
    assert "refusing to scan" in capsys.readouterr().err


def test_main_falls_back_to_the_default_cache_root(tmp_path, capsys, monkeypatch):
    root = make_cache(tmp_path)
    monkeypatch.setattr(reap, "default_cache_root", lambda: root)
    assert main_with([]) == 0
    assert str(root) in capsys.readouterr().out


def main_with(argv: list[str]) -> int:
    return reap.main(argv, now_ms=NOW)
