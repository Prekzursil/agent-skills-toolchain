"""Both-state tests for the M20 skill-context budget gate."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import check_skill_context_budget as budget  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
RUNNER_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "codex-runner.yml"


def _write_skill(root: Path, name: str, description: str, body: str = "body") -> None:
    target = root / name
    target.mkdir(parents=True, exist_ok=True)
    (target / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: {description}\n---\n{body}\n",
        encoding="utf-8",
    )


def _write_allowlist(repo: Path, *names: str) -> Path:
    path = repo / "daily.txt"
    path.write_text("\n".join(names) + "\n", encoding="utf-8")
    return path


def _seed_control(repo: Path) -> None:
    _write_skill(repo / ".agents" / "skills", budget.CONTROL_SKILL, "control")


def test_large_body_is_per_use_not_per_session(tmp_path: Path) -> None:
    """Known-broken pre-M20: no analyzer separated trigger text from body cost."""
    _seed_control(tmp_path)
    _write_skill(tmp_path / ".agents" / "skills", "daily", "short trigger")
    runtime = tmp_path / "runtime"
    _write_skill(runtime, "daily", "short trigger", "x")
    allowlist = _write_allowlist(tmp_path, "daily")

    before = budget.analyze(tmp_path, allowlist, runtime)
    _write_skill(runtime, "daily", "short trigger", "x" * 50_000)
    after = budget.analyze(tmp_path, allowlist, runtime)

    assert after.trigger_chars == before.trigger_chars
    assert after.body_chars > before.body_chars + 49_000


def test_budget_boundary_passes_then_one_more_char_fails(tmp_path: Path) -> None:
    """Known-broken pre-M20: the installed tier had no enforceable budget boundary."""
    _seed_control(tmp_path)
    _write_skill(tmp_path / ".agents" / "skills", "daily", "abcd")
    runtime = tmp_path / "runtime"
    _write_skill(runtime, "daily", "abcd")
    allowlist = _write_allowlist(tmp_path, "daily")
    report = budget.analyze(tmp_path, allowlist, runtime)

    assert budget.check(report, report.trigger_chars) is None
    with pytest.raises(budget.BudgetExceeded, match="exceeds"):
        budget.check(report, report.trigger_chars - 1)


def test_cli_exit_codes_distinguish_pass_over_budget_and_invalid(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Known-broken pre-M20: no production CLI could gate the workflow exit."""
    _seed_control(tmp_path)
    _write_skill(tmp_path / ".agents" / "skills", "daily", "abcd")
    runtime = tmp_path / "runtime"
    _write_skill(runtime, "daily", "abcd")
    allowlist = _write_allowlist(tmp_path, "daily")
    report = budget.analyze(tmp_path, allowlist, runtime)
    args = [
        "--repo",
        str(tmp_path),
        "--allowlist",
        str(allowlist),
        "--runtime-root",
        str(runtime),
    ]

    assert budget.main([*args, "--max-trigger-chars", str(report.trigger_chars)]) == 0
    assert "skill context budget:" in capsys.readouterr().out
    assert (
        budget.main([*args, "--max-trigger-chars", str(report.trigger_chars - 1)]) == 1
    )
    assert "OVER BUDGET:" in capsys.readouterr().err
    assert budget.main([*args, "--max-trigger-chars", "0"]) == 2
    assert "CONFIGURATION ERROR:" in capsys.readouterr().err


def test_catalog_unions_projection_only_and_prefers_canonical(tmp_path: Path) -> None:
    """Known-broken pre-M20: no budget detector implemented the D-001 union."""
    _seed_control(tmp_path)
    canonical = tmp_path / ".agents" / "skills" / "shared" / "SKILL.md"
    _write_skill(tmp_path / ".agents" / "skills", "shared", "canonical")
    _write_skill(tmp_path / "skills", "shared", "projection")
    _write_skill(tmp_path / "skills", "projection-only", "retained library")
    _write_skill(
        tmp_path / "skills-claude-only", "claude-only", "retained provider skill"
    )

    catalog = budget.build_catalog(tmp_path)

    assert catalog["shared"] == canonical
    assert "projection-only" in catalog
    assert "claude-only" in catalog


def test_canonical_trigger_growth_cannot_hide_behind_stale_runtime(
    tmp_path: Path,
) -> None:
    """Known-broken pre-M20: stale CI text could mask canonical budget growth."""
    _seed_control(tmp_path)
    canonical = tmp_path / ".agents" / "skills"
    _write_skill(canonical, "daily", "short")
    runtime = tmp_path / "runtime"
    _write_skill(runtime, "daily", "short")
    allowlist = _write_allowlist(tmp_path, "daily")
    before = budget.analyze(tmp_path, allowlist, runtime)

    _write_skill(canonical, "daily", "x" * 1_000)
    after = budget.analyze(tmp_path, allowlist, runtime)

    assert after.runtime_trigger_chars == before.runtime_trigger_chars
    assert after.canonical_trigger_chars > before.canonical_trigger_chars + 900
    assert after.trigger_chars == after.canonical_trigger_chars


def test_detector_refuses_an_unvalidated_zero(tmp_path: Path) -> None:
    """Known-broken pre-M20: no known-present control guarded an empty census."""
    with pytest.raises(budget.ConfigurationError, match=budget.CONTROL_SKILL):
        budget.build_catalog(tmp_path)


def test_daily_skill_must_exist_in_authoritative_root(tmp_path: Path) -> None:
    """Known-broken pre-M20: the runner never checked DAILY against D-001 authority."""
    _seed_control(tmp_path)
    _write_skill(tmp_path / "skills", "projection-only", "not authoritative")
    runtime = tmp_path / "runtime"
    _write_skill(runtime, "projection-only", "not authoritative")
    allowlist = _write_allowlist(tmp_path, "projection-only")

    with pytest.raises(budget.ConfigurationError, match="authoritative"):
        budget.analyze(tmp_path, allowlist, runtime)


@pytest.mark.parametrize("mismatch", ["missing", "extra"])
def test_runtime_membership_must_equal_allowlist(tmp_path: Path, mismatch: str) -> None:
    """Known-broken pre-M20: the manifest was not read by the installing workflow."""
    _seed_control(tmp_path)
    _write_skill(tmp_path / ".agents" / "skills", "daily", "selected")
    runtime = tmp_path / "runtime"
    if mismatch == "extra":
        _write_skill(runtime, "daily", "selected")
        _write_skill(runtime, "surprise", "not declared")
    allowlist = _write_allowlist(tmp_path, "daily")

    with pytest.raises(budget.ConfigurationError, match="does not match allowlist"):
        budget.analyze(tmp_path, allowlist, runtime)


@pytest.mark.parametrize("bad_lines", [("daily", "daily"), ("not_valid!",)])
def test_allowlist_rejects_duplicate_or_invalid_names(
    tmp_path: Path, bad_lines: tuple[str, ...]
) -> None:
    """Known-broken pre-M20: the allowlist had no production parser or validation."""
    allowlist = _write_allowlist(tmp_path, *bad_lines)

    with pytest.raises(budget.ConfigurationError):
        budget.read_allowlist(allowlist)


def test_committed_codex_tier_is_bounded_and_retains_library() -> None:
    """Known-broken pre-M20: CI never enforced the committed 8,000-char contract."""
    report = budget.analyze(
        REPO_ROOT,
        REPO_ROOT / "ci" / "codex-skill-allowlist.txt",
        REPO_ROOT / "ci" / "skills-allowlist",
    )

    budget.check(report, budget.DEFAULT_MAX_TRIGGER_CHARS)
    assert report.daily_count == 21
    assert report.library_count > 0


def test_runner_checks_installed_tier_before_codex_exec() -> None:
    """Known-broken pre-M20: the runner masked copy errors and had no budget gate."""
    workflow = RUNNER_WORKFLOW.read_text(encoding="utf-8")
    check = 'python "$GITHUB_WORKSPACE/runner/ci/check_skill_context_budget.py"'
    copy = 'cp -r "$GITHUB_WORKSPACE"/runner/ci/skills-allowlist/*'
    codex_exec = "codex exec --dangerously-bypass-approvals-and-sandbox"

    assert check in workflow
    assert "--max-trigger-chars 8000" in workflow
    assert '--runtime-root "$HOME/.agents/skills"' in workflow
    assert "2>/dev/null || true" not in workflow[workflow.index(copy) :].splitlines()[0]
    assert workflow.index(copy) < workflow.index(check) < workflow.index(codex_exec)


def _write_skill_with_frontmatter_name(
    root: Path, directory: str, frontmatter_name: str, description: str = "d"
) -> None:
    """Write a skill whose frontmatter name deliberately differs from its directory name."""
    target = root / directory
    target.mkdir(parents=True, exist_ok=True)
    (target / "SKILL.md").write_text(
        f"---\nname: {frontmatter_name}\ndescription: {description}\n---\nbody\n",
        encoding="utf-8",
    )


@pytest.mark.parametrize("side", ["runtime", "canonical"])
def test_frontmatter_name_must_match_its_directory(tmp_path: Path, side: str) -> None:
    """Mutation-exposed gap: both name checks were dead code that no case exercised.

    The loader keys on the frontmatter name, so a skill whose frontmatter disagrees with its
    directory installs under a name nothing references - present on disk, absent to the runtime.
    Disabling either branch previously left the whole suite green.
    """
    _seed_control(tmp_path)
    canonical_root = tmp_path / ".agents" / "skills"
    runtime = tmp_path / "runtime"

    if side == "runtime":
        _write_skill(canonical_root, "daily", "selected")
        _write_skill_with_frontmatter_name(runtime, "daily", "something-else")
    else:
        _write_skill_with_frontmatter_name(canonical_root, "daily", "something-else")
        _write_skill(runtime, "daily", "selected")

    allowlist = _write_allowlist(tmp_path, "daily")

    with pytest.raises(budget.ConfigurationError, match="does not match directory"):
        budget.analyze(tmp_path, allowlist, runtime)


def test_matching_frontmatter_name_is_accepted(tmp_path: Path) -> None:
    """The both-states partner: identical name and directory must NOT raise."""
    _seed_control(tmp_path)
    _write_skill(tmp_path / ".agents" / "skills", "daily", "selected")
    _write_skill(tmp_path / "runtime", "daily", "selected")
    allowlist = _write_allowlist(tmp_path, "daily")

    report = budget.analyze(tmp_path, allowlist, tmp_path / "runtime")
    assert report is not None
