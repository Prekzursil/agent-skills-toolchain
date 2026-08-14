"""Tests for the SKILLS-MANIFEST inventory generator and its CI gate.

Two layers, deliberately:

* Synthetic-tree tests own the behaviour (seeding, preservation, escaping, orphans), so
  they stay true as the real skill surface changes.
* Three live-repo tests own the DEFECT: the committed manifest must actually list every
  tracked skill, including the three names the audit measured as missing. Those three
  fail on the pre-fix manifest (`added=176`) and pass after regeneration -- both states
  were observed, not assumed.
"""

from __future__ import annotations

import pathlib
import subprocess
import sys
import io

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from gen_skills_manifest import (  # noqa: E402
    MANIFEST_RELPATH,
    UNCLASSIFIED_ORIGIN,
    Row,
    enumerate_skill_dirs,
    frontmatter_description,
    main,
    parse_manifest,
    render,
    sync,
)

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
GENERATOR = REPO_ROOT / "ci" / "gen_skills_manifest.py"
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "skill-dual-write.yml"
GATE_MARKER = "python ci/gen_skills_manifest.py --check"

# The exact names the audit reported as false negatives against the advertised inventory.
REGRESSION_NAMES = ("recall-workflow-agent", "run-agent-monitor", "workflow-monitor")


def _skill(root: pathlib.Path, name: str, description: str) -> None:
    directory = root / "skills" / name
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: {description}\n---\n\n# {name}\n",
        encoding="utf-8",
    )


def _manifest(root: pathlib.Path, body: str) -> None:
    path = root / MANIFEST_RELPATH
    path.parent.mkdir(parents=True, exist_ok=True)
    io.open(path, "w", encoding="utf-8", newline="\n").write(body)


# --------------------------------------------------------------------------- live repo


def test_generator_is_committed() -> None:
    assert GENERATOR.is_file()


def test_committed_manifest_lists_every_tracked_skill() -> None:
    """The defect itself: the advertised inventory must not omit a real skill."""
    result = sync(REPO_ROOT)
    assert result.added == [], (
        f"{MANIFEST_RELPATH} omits {len(result.added)} tracked skills; "
        "run python ci/gen_skills_manifest.py --write"
    )


def test_committed_manifest_lists_the_three_audited_skills() -> None:
    text = (REPO_ROOT / MANIFEST_RELPATH).read_text(encoding="utf-8")
    listed = {row.name for row in parse_manifest(text)[0]}
    tracked = enumerate_skill_dirs(REPO_ROOT)
    for name in REGRESSION_NAMES:
        assert name in tracked, f"{name} is no longer a tracked skill"
        assert name in listed, f"{name} is tracked but absent from {MANIFEST_RELPATH}"


def test_committed_manifest_has_no_malformed_table_lines() -> None:
    text = (REPO_ROOT / MANIFEST_RELPATH).read_text(encoding="utf-8")
    assert parse_manifest(text)[1] == []


def test_check_mode_passes_on_the_committed_manifest() -> None:
    assert main(["--check", "--repo", str(REPO_ROOT)]) == 0


def test_workflow_invokes_the_manifest_gate_by_explicit_path() -> None:
    """No repo-wide autodiscovery here: a gate runs only when a step names it."""
    assert GATE_MARKER in WORKFLOW.read_text(encoding="utf-8")


def test_nested_asset_skill_templates_are_not_counted() -> None:
    """`skills/*/assets/*/SKILL.md` is a template, not a skill.

    `git ls-files "skills/*/SKILL.md"` matches it because a git pathspec `*` crosses `/`,
    which is how a naive census reports 337 instead of 336. Enumeration here walks one
    level, so the template must NOT appear.
    """
    tracked = enumerate_skill_dirs(REPO_ROOT)
    assert "create-tooluniverse-skill" in tracked
    assert "skill_template" not in tracked


def test_generator_run_as_a_script_reports_ok(tmp_path: pathlib.Path) -> None:
    proc = subprocess.run(
        [sys.executable, str(GENERATOR), "--check", "--repo", str(REPO_ROOT)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=tmp_path,
    )
    assert proc.returncode == 0, proc.stderr
    assert "OK skills/SKILLS-MANIFEST.md" in proc.stdout


# ---------------------------------------------------------------------- synthetic tree


def test_check_fails_when_a_tracked_skill_has_no_row(tmp_path: pathlib.Path) -> None:
    _skill(tmp_path, "alpha", "first")
    _skill(tmp_path, "beta", "second")
    _manifest(tmp_path, render([Row("alpha", "custom", "first")]))
    assert main(["--check", "--repo", str(tmp_path)]) == 1


def test_write_then_check_closes_the_gap(tmp_path: pathlib.Path) -> None:
    _skill(tmp_path, "alpha", "first")
    _skill(tmp_path, "beta", "second")
    _manifest(tmp_path, render([Row("alpha", "custom", "first")]))
    assert main(["--check", "--repo", str(tmp_path)]) == 1
    assert main(["--write", "--repo", str(tmp_path)]) == 0
    assert main(["--check", "--repo", str(tmp_path)]) == 0


def test_write_is_idempotent(tmp_path: pathlib.Path) -> None:
    _skill(tmp_path, "alpha", "first")
    _manifest(tmp_path, "")
    main(["--write", "--repo", str(tmp_path)])
    once = (tmp_path / MANIFEST_RELPATH).read_text(encoding="utf-8")
    main(["--write", "--repo", str(tmp_path)])
    assert (tmp_path / MANIFEST_RELPATH).read_text(encoding="utf-8") == once


def test_write_preserves_curated_origin_and_description(tmp_path: pathlib.Path) -> None:
    _skill(
        tmp_path, "alpha", "frontmatter text that must NOT overwrite the curated row"
    )
    _manifest(tmp_path, render([Row("alpha", "vendored", "curated summary")]))
    main(["--write", "--repo", str(tmp_path)])
    rows = {
        r.name: r
        for r in parse_manifest(
            (tmp_path / MANIFEST_RELPATH).read_text(encoding="utf-8")
        )[0]
    }
    assert rows["alpha"] == Row("alpha", "vendored", "curated summary")


def test_seeded_row_uses_frontmatter_and_unclassified_origin(
    tmp_path: pathlib.Path,
) -> None:
    _skill(tmp_path, "beta", "seeded from frontmatter")
    _manifest(tmp_path, "")
    main(["--write", "--repo", str(tmp_path)])
    rows = {
        r.name: r
        for r in parse_manifest(
            (tmp_path / MANIFEST_RELPATH).read_text(encoding="utf-8")
        )[0]
    }
    assert rows["beta"] == Row("beta", UNCLASSIFIED_ORIGIN, "seeded from frontmatter")


def test_orphan_rows_are_reported_and_never_deleted(tmp_path: pathlib.Path) -> None:
    _skill(tmp_path, "alpha", "first")
    _manifest(
        tmp_path,
        render([Row("alpha", "custom", "first"), Row("gone", "custom", "retired")]),
    )
    result = sync(tmp_path)
    assert result.orphans == ["gone"]
    assert main(["--write", "--repo", str(tmp_path)]) == 0
    text = (tmp_path / MANIFEST_RELPATH).read_text(encoding="utf-8")
    assert "gone" in {row.name for row in parse_manifest(text)[0]}


def test_bare_pipe_line_is_malformed_and_dropped_by_write(
    tmp_path: pathlib.Path,
) -> None:
    _skill(tmp_path, "alpha", "first")
    _manifest(
        tmp_path,
        "| Skill Name | Origin | Description |\n|---|---|---|\n"
        "| alpha | custom | first |\n|\n",
    )
    result = sync(tmp_path)
    assert result.malformed == ["|"]
    main(["--write", "--repo", str(tmp_path)])
    text = (tmp_path / MANIFEST_RELPATH).read_text(encoding="utf-8")
    assert parse_manifest(text)[1] == []
    assert "\n|\n" not in text


def test_row_without_a_closing_pipe_is_repaired(tmp_path: pathlib.Path) -> None:
    _skill(tmp_path, "alpha", "first")
    _manifest(
        tmp_path,
        "| Skill Name | Origin | Description |\n|---|---|---|\n| alpha | custom | first\n",
    )
    main(["--write", "--repo", str(tmp_path)])
    text = (tmp_path / MANIFEST_RELPATH).read_text(encoding="utf-8")
    assert "| alpha | custom | first |\n" in text


def test_pipes_in_a_description_round_trip_without_shifting_columns(
    tmp_path: pathlib.Path,
) -> None:
    _skill(tmp_path, "alpha", "detects || true and set +e")
    _manifest(tmp_path, "")
    main(["--write", "--repo", str(tmp_path)])
    text = (tmp_path / MANIFEST_RELPATH).read_text(encoding="utf-8")
    assert r"detects \|\| true and set +e" in text
    rows, malformed = parse_manifest(text)
    assert malformed == []
    assert rows[0].description == "detects || true and set +e"
    assert main(["--check", "--repo", str(tmp_path)]) == 0


def test_block_scalar_description_is_read(tmp_path: pathlib.Path) -> None:
    directory = tmp_path / "skills" / "folded"
    directory.mkdir(parents=True)
    (directory / "SKILL.md").write_text(
        "---\nname: folded\ndescription: >-\n  first line\n  second line\n---\n",
        encoding="utf-8",
    )
    assert frontmatter_description(directory / "SKILL.md") == "first line second line"


def test_quoted_description_is_unquoted(tmp_path: pathlib.Path) -> None:
    directory = tmp_path / "skills" / "quoted"
    directory.mkdir(parents=True)
    (directory / "SKILL.md").write_text(
        '---\nname: quoted\ndescription: "a quoted summary"\n---\n', encoding="utf-8"
    )
    assert frontmatter_description(directory / "SKILL.md") == "a quoted summary"


def test_long_description_is_truncated_deterministically(
    tmp_path: pathlib.Path,
) -> None:
    _skill(tmp_path, "verbose", "word " * 200)
    _manifest(tmp_path, "")
    main(["--write", "--repo", str(tmp_path)])
    rows = parse_manifest((tmp_path / MANIFEST_RELPATH).read_text(encoding="utf-8"))[0]
    assert len(rows[0].description) <= 240
    assert rows[0].description.endswith("...")


def test_missing_manifest_is_created(tmp_path: pathlib.Path) -> None:
    _skill(tmp_path, "alpha", "first")
    assert main(["--check", "--repo", str(tmp_path)]) == 1
    assert main(["--write", "--repo", str(tmp_path)]) == 0
    assert (tmp_path / MANIFEST_RELPATH).is_file()


def test_a_directory_without_skill_md_is_not_a_skill(tmp_path: pathlib.Path) -> None:
    (tmp_path / "skills" / "not-a-skill").mkdir(parents=True)
    _skill(tmp_path, "alpha", "first")
    assert sorted(enumerate_skill_dirs(tmp_path)) == ["alpha"]
