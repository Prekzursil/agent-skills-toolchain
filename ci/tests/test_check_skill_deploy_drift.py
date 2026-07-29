"""Acceptance suite for the L10 skill-deploy drift reporter.

Every test is hermetic (``tmp_path`` only) so the suite runs on a CI runner that
has no ``~/.claude`` or ``~/.agents`` tree.

The load-bearing behaviour under test is the DIRECTION verdict.  The measured
failure this tool exists to prevent is a one-directional read reporting a
two-directionally divergent file as safe to overwrite, so the diverged and
strict-superset cases are pinned in both orientations.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = REPO_ROOT / "ci" / "check_skill_deploy_drift.py"
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "skill-dual-write.yml"


def _load():
    spec = importlib.util.spec_from_file_location(
        "check_skill_deploy_drift", MODULE_PATH
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


mod = _load()


def make_skill(root: Path, name: str, files: dict[str, str | bytes]) -> Path:
    """Create ``root/name/`` with the given skill-relative files."""
    base = root / name
    for rel, content in files.items():
        target = base / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, bytes):
            target.write_bytes(content)
        else:
            target.write_text(content, encoding="utf-8")
    return base


# --------------------------------------------------------------------------
# normalise / is_noise
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (b"a\r\nb", b"a\nb"),
        (b"a\rb", b"a\nb"),
        (b"a\nb", b"a\nb"),
        (b"", b""),
        (b"a\r\n\r\nb", b"a\n\nb"),
    ],
)
def test_normalise_collapses_every_eol_style(raw: bytes, expected: bytes) -> None:
    assert mod.normalise(raw) == expected


@pytest.mark.parametrize(
    "rel",
    [
        ".ruff_cache/0.15.17/123",
        "__pycache__/x.pyc",
        "node_modules/pkg/index.js",
        ".pytest_cache/CACHEDIR.TAG",
        ".venv/lib/site.py",
        ".git/config",
        "LICENSE.txtZone.Identifier",
        "SKILL.md.bak-fleet-20260713",
        "references/harness.py.bak-gembuild-B9",
    ],
)
def test_is_noise_true_for_byproducts(rel: str) -> None:
    assert mod.is_noise(rel) is True


@pytest.mark.parametrize(
    "rel",
    ["SKILL.md", "references/notes.md", "scripts/run.py", "assets/demo.png"],
)
def test_is_noise_false_for_content(rel: str) -> None:
    assert mod.is_noise(rel) is False


# --------------------------------------------------------------------------
# read_normalised / content_digest
# --------------------------------------------------------------------------


def test_read_normalised_returns_none_for_a_missing_file(tmp_path: Path) -> None:
    assert mod.read_normalised(tmp_path / "nope.md") is None


def test_read_normalised_returns_none_for_a_directory(tmp_path: Path) -> None:
    (tmp_path / "adir").mkdir()
    assert mod.read_normalised(tmp_path / "adir") is None


def test_content_digest_is_eol_insensitive(tmp_path: Path) -> None:
    crlf = tmp_path / "crlf.md"
    lf = tmp_path / "lf.md"
    crlf.write_bytes(b"line one\r\nline two\r\n")
    lf.write_bytes(b"line one\nline two\n")
    assert mod.content_digest(crlf) == mod.content_digest(lf)


def test_content_digest_is_none_when_unreadable(tmp_path: Path) -> None:
    assert mod.content_digest(tmp_path / "absent") is None


def test_significant_lines_drops_blank_and_whitespace_only_lines() -> None:
    assert mod.significant_lines(b"a\n\n   \nb\n") == {"a", "b"}


def test_significant_lines_survives_invalid_utf8() -> None:
    assert mod.significant_lines(b"ok\n\xff\xfe\n") != set()


# --------------------------------------------------------------------------
# classify_pair -- the load-bearing direction test
# --------------------------------------------------------------------------


def test_classify_pair_identical(tmp_path: Path) -> None:
    a, b = tmp_path / "a", tmp_path / "b"
    a.write_text("same\n", encoding="utf-8")
    b.write_text("same\n", encoding="utf-8")
    assert mod.classify_pair(a, b) == mod.IDENTICAL


def test_classify_pair_identical_across_eol_styles(tmp_path: Path) -> None:
    a, b = tmp_path / "a", tmp_path / "b"
    a.write_bytes(b"same\r\ntext\r\n")
    b.write_bytes(b"same\ntext\n")
    assert mod.classify_pair(a, b) == mod.IDENTICAL


def test_classify_pair_right_ahead_is_a_strict_superset(tmp_path: Path) -> None:
    a, b = tmp_path / "a", tmp_path / "b"
    a.write_text("keep\n", encoding="utf-8")
    b.write_text("keep\nextra\n", encoding="utf-8")
    assert mod.classify_pair(a, b) == mod.RIGHT_AHEAD


def test_classify_pair_left_ahead_is_the_mirror_case(tmp_path: Path) -> None:
    a, b = tmp_path / "a", tmp_path / "b"
    a.write_text("keep\nextra\n", encoding="utf-8")
    b.write_text("keep\n", encoding="utf-8")
    assert mod.classify_pair(a, b) == mod.LEFT_AHEAD


def test_classify_pair_diverged_when_both_sides_hold_unique_lines(
    tmp_path: Path,
) -> None:
    """The measured blind spot: a shorter file is NOT automatically stale."""
    a, b = tmp_path / "a", tmp_path / "b"
    a.write_text("shared\nonly-live\n", encoding="utf-8")
    b.write_text("shared\nonly-vault\nmore-vault\nyet-more\n", encoding="utf-8")
    assert mod.classify_pair(a, b) == mod.DIVERGED


def test_classify_pair_reorder_only(tmp_path: Path) -> None:
    a, b = tmp_path / "a", tmp_path / "b"
    a.write_text("one\ntwo\n", encoding="utf-8")
    b.write_text("two\none\n", encoding="utf-8")
    assert mod.classify_pair(a, b) == mod.REORDER_ONLY


def test_classify_pair_unreadable_is_diverged_not_equal(tmp_path: Path) -> None:
    """Two unreadable files must never compare EQUAL."""
    a = tmp_path / "a"
    a.write_text("x\n", encoding="utf-8")
    assert mod.classify_pair(a, tmp_path / "absent") == mod.DIVERGED
    assert mod.classify_pair(tmp_path / "absent", a) == mod.DIVERGED
    assert mod.classify_pair(tmp_path / "gone1", tmp_path / "gone2") == mod.DIVERGED


# --------------------------------------------------------------------------
# skill_names / skill_files
# --------------------------------------------------------------------------


def test_skill_names_requires_a_skill_md(tmp_path: Path) -> None:
    make_skill(tmp_path, "real", {"SKILL.md": "x\n"})
    (tmp_path / "notaskill").mkdir()
    (tmp_path / "loose.md").write_text("x\n", encoding="utf-8")
    assert mod.skill_names(tmp_path) == {"real"}


def test_skill_names_empty_for_a_missing_root(tmp_path: Path) -> None:
    assert mod.skill_names(tmp_path / "absent") == set()


def test_skill_files_excludes_noise_by_default(tmp_path: Path) -> None:
    make_skill(
        tmp_path,
        "s",
        {
            "SKILL.md": "x\n",
            ".ruff_cache/CACHEDIR.TAG": "junk\n",
            "SKILL.md.bak-fleet-20260713": "old\n",
        },
    )
    assert set(mod.skill_files(tmp_path, "s")) == {"SKILL.md"}


def test_skill_files_include_noise_opt_in(tmp_path: Path) -> None:
    make_skill(tmp_path, "s", {"SKILL.md": "x\n", ".ruff_cache/CACHEDIR.TAG": "junk\n"})
    assert set(mod.skill_files(tmp_path, "s", include_noise=True)) == {
        "SKILL.md",
        ".ruff_cache/CACHEDIR.TAG",
    }


def test_skill_files_empty_for_a_missing_skill(tmp_path: Path) -> None:
    assert mod.skill_files(tmp_path, "absent") == {}


# --------------------------------------------------------------------------
# _folded
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("verdicts", "expected"),
    [
        (set(), mod.IDENTICAL),
        ({mod.REORDER_ONLY}, mod.REORDER_ONLY),
        ({mod.RIGHT_AHEAD}, mod.RIGHT_AHEAD),
        ({mod.RIGHT_ONLY_FILE}, mod.RIGHT_AHEAD),
        ({mod.LEFT_AHEAD}, mod.LEFT_AHEAD),
        ({mod.LEFT_ONLY_FILE}, mod.LEFT_AHEAD),
        ({mod.DIVERGED}, mod.DIVERGED),
        ({mod.LEFT_AHEAD, mod.RIGHT_AHEAD}, mod.DIVERGED),
        ({mod.LEFT_ONLY_FILE, mod.RIGHT_ONLY_FILE}, mod.DIVERGED),
        ({mod.REORDER_ONLY, mod.RIGHT_AHEAD}, mod.RIGHT_AHEAD),
    ],
)
def test_folded_verdict(verdicts: set[str], expected: str) -> None:
    assert mod._folded(verdicts) == expected


# --------------------------------------------------------------------------
# compare_skill / reconcile
# --------------------------------------------------------------------------


def test_compare_skill_omits_identical_files(tmp_path: Path) -> None:
    left, right = tmp_path / "L", tmp_path / "R"
    make_skill(left, "s", {"SKILL.md": "same\n", "extra.md": "a\n"})
    make_skill(right, "s", {"SKILL.md": "same\n", "extra.md": "a\nb\n"})
    files = mod.compare_skill(left, right, "s")
    assert files == {"extra.md": mod.RIGHT_AHEAD}


def test_compare_skill_flags_one_sided_files(tmp_path: Path) -> None:
    left, right = tmp_path / "L", tmp_path / "R"
    make_skill(left, "s", {"SKILL.md": "x\n", "live-only.md": "l\n"})
    make_skill(right, "s", {"SKILL.md": "x\n", "vault-only.md": "v\n"})
    files = mod.compare_skill(left, right, "s")
    assert files == {
        "live-only.md": mod.LEFT_ONLY_FILE,
        "vault-only.md": mod.RIGHT_ONLY_FILE,
    }


def test_reconcile_counts_and_partitions(tmp_path: Path) -> None:
    left, right = tmp_path / "L", tmp_path / "R"
    make_skill(left, "identical", {"SKILL.md": "x\n"})
    make_skill(right, "identical", {"SKILL.md": "x\n"})
    make_skill(left, "stale", {"SKILL.md": "keep\n"})
    make_skill(right, "stale", {"SKILL.md": "keep\nnew\n"})
    make_skill(left, "diverged", {"SKILL.md": "shared\nlive\n"})
    make_skill(right, "diverged", {"SKILL.md": "shared\nvault\n"})
    make_skill(left, "live-only-skill", {"SKILL.md": "x\n"})
    make_skill(right, "vault-only-skill", {"SKILL.md": "x\n"})

    report = mod.reconcile(left, right)
    assert report["left_skill_count"] == 4
    assert report["right_skill_count"] == 4
    assert report["shared_skill_count"] == 3
    assert report["left_only_skills"] == ["live-only-skill"]
    assert report["right_only_skills"] == ["vault-only-skill"]
    assert report["summary"][mod.IDENTICAL] == 1
    assert report["summary"][mod.RIGHT_AHEAD] == 1
    assert report["summary"][mod.DIVERGED] == 1
    assert report["safe_to_deploy"] == ["stale/SKILL.md"]
    assert report["needs_merge"] == ["diverged/SKILL.md"]


def test_reconcile_never_lists_a_diverged_file_as_safe(tmp_path: Path) -> None:
    """Regression net for the whole point of the tool."""
    left, right = tmp_path / "L", tmp_path / "R"
    make_skill(left, "s", {"SKILL.md": "shared\nlive-unique\n"})
    make_skill(right, "s", {"SKILL.md": "shared\nv1\nv2\nv3\nv4\nv5\n"})
    report = mod.reconcile(left, right)
    assert report["safe_to_deploy"] == []
    assert report["needs_merge"] == ["s/SKILL.md"]


def test_reconcile_counts_reorder_only(tmp_path: Path) -> None:
    left, right = tmp_path / "L", tmp_path / "R"
    make_skill(left, "s", {"SKILL.md": "one\ntwo\n"})
    make_skill(right, "s", {"SKILL.md": "two\none\n"})
    report = mod.reconcile(left, right)
    assert report["summary"][mod.REORDER_ONLY] == 1
    assert report["needs_merge"] == []
    assert report["safe_to_deploy"] == []


def test_reconcile_left_ahead_needs_merge_not_deploy(tmp_path: Path) -> None:
    left, right = tmp_path / "L", tmp_path / "R"
    make_skill(left, "s", {"SKILL.md": "keep\nlive-extra\n"})
    make_skill(right, "s", {"SKILL.md": "keep\n"})
    report = mod.reconcile(left, right)
    assert report["summary"][mod.LEFT_AHEAD] == 1
    assert report["needs_merge"] == ["s/SKILL.md"]
    assert report["safe_to_deploy"] == []


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


def test_main_exit_ok_when_trees_agree(tmp_path: Path, capsys) -> None:
    left, right = tmp_path / "L", tmp_path / "R"
    make_skill(left, "s", {"SKILL.md": "x\n"})
    make_skill(right, "s", {"SKILL.md": "x\n"})
    assert mod.main(["--left", str(left), "--right", str(right)]) == mod.EXIT_OK
    assert "IDENTICAL" in capsys.readouterr().out


def test_main_exit_drift_on_a_safe_deploy_candidate(tmp_path: Path, capsys) -> None:
    left, right = tmp_path / "L", tmp_path / "R"
    make_skill(left, "s", {"SKILL.md": "keep\n"})
    make_skill(right, "s", {"SKILL.md": "keep\nnew\n"})
    assert mod.main(["--left", str(left), "--right", str(right)]) == mod.EXIT_DRIFT
    out = capsys.readouterr().out
    assert "SAFE TO DEPLOY" in out
    assert "+ s/SKILL.md" in out


def test_main_require_safe_tolerates_a_pure_deploy(tmp_path: Path) -> None:
    left, right = tmp_path / "L", tmp_path / "R"
    make_skill(left, "s", {"SKILL.md": "keep\n"})
    make_skill(right, "s", {"SKILL.md": "keep\nnew\n"})
    argv = ["--left", str(left), "--right", str(right), "--require-safe"]
    assert mod.main(argv) == mod.EXIT_OK


def test_main_require_safe_still_fails_on_divergence(tmp_path: Path, capsys) -> None:
    left, right = tmp_path / "L", tmp_path / "R"
    make_skill(left, "s", {"SKILL.md": "shared\nlive\n"})
    make_skill(right, "s", {"SKILL.md": "shared\nvault\n"})
    argv = ["--left", str(left), "--right", str(right), "--require-safe"]
    assert mod.main(argv) == mod.EXIT_DRIFT
    assert "NEEDS A HUMAN MERGE" in capsys.readouterr().out


def test_main_json_is_parseable(tmp_path: Path, capsys) -> None:
    left, right = tmp_path / "L", tmp_path / "R"
    make_skill(left, "s", {"SKILL.md": "shared\nlive\n"})
    make_skill(right, "s", {"SKILL.md": "shared\nvault\n"})
    mod.main(["--left", str(left), "--right", str(right), "--json"])
    payload = json.loads(capsys.readouterr().out)
    assert payload["needs_merge"] == ["s/SKILL.md"]
    assert payload["skills"]["s"]["verdict"] == mod.DIVERGED


def test_main_include_noise_flag_changes_the_verdict(tmp_path: Path) -> None:
    left, right = tmp_path / "L", tmp_path / "R"
    make_skill(left, "s", {"SKILL.md": "x\n", ".ruff_cache/TAG": "junk\n"})
    make_skill(right, "s", {"SKILL.md": "x\n"})
    base = ["--left", str(left), "--right", str(right)]
    assert mod.main(base) == mod.EXIT_OK
    assert mod.main([*base, "--include-noise"]) == mod.EXIT_DRIFT


def test_main_usage_error_on_a_missing_left_root(tmp_path: Path, capsys) -> None:
    right = tmp_path / "R"
    make_skill(right, "s", {"SKILL.md": "x\n"})
    argv = ["--left", str(tmp_path / "absent"), "--right", str(right)]
    assert mod.main(argv) == mod.EXIT_USAGE
    assert "not a directory" in capsys.readouterr().err


def test_main_usage_error_on_a_missing_right_root(tmp_path: Path, capsys) -> None:
    left = tmp_path / "L"
    make_skill(left, "s", {"SKILL.md": "x\n"})
    argv = ["--left", str(left), "--right", str(tmp_path / "absent")]
    assert mod.main(argv) == mod.EXIT_USAGE
    assert "not a directory" in capsys.readouterr().err


# --------------------------------------------------------------------------
# D4 wiring -- a check runs only because a workflow step names it
# --------------------------------------------------------------------------


def test_module_exists_at_the_documented_path() -> None:
    assert MODULE_PATH.is_file()


def test_this_suite_is_named_by_the_workflow() -> None:
    """No repo-wide autodiscovery: an unnamed suite never runs."""
    rel = Path(__file__).resolve().relative_to(REPO_ROOT).as_posix()
    assert rel in WORKFLOW.read_text(encoding="utf-8")
