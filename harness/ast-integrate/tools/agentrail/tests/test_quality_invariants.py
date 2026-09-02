"""The bar itself, asserted in-repo so it cannot quietly slip between CI runs.

ZERO ``# pragma: no cover`` in package SOURCE, no coverage ``omit``, no ``exclude_lines``, and
the basedpyright ``extraPaths`` guard present. Each is checked by reading the artifact, not by
trusting a comment that says so.
"""

from __future__ import annotations

import io
import tokenize
import tomllib
from pathlib import Path

import pytest

import agentrail

PACKAGE_ROOT = Path(agentrail.__file__).parent
PYPROJECT = tomllib.loads(
    (PACKAGE_ROOT.parent / "pyproject.toml").read_text(encoding="utf-8")
)
SOURCE_FILES = tuple(sorted(PACKAGE_ROOT.rglob("*.py")))
PRAGMA = "pragma: no cover"


def coverage_pragmas(source: str) -> tuple[tuple[int, str], ...]:
    """Real coverage pragmas -- COMMENT tokens only.

    A plain substring search over the file is a use-vs-mention error: three modules here
    DISCUSS ``# pragma: no cover`` in their docstrings to explain why they carry none, and a
    naive grep reports all three as violations. Tokenising separates the comment from the prose.
    """
    comments: list[tuple[int, str]] = []
    for token in tokenize.generate_tokens(io.StringIO(source).readline):
        if token.type == tokenize.COMMENT and PRAGMA in token.string:
            comments.append((token.start[0], token.string))
    return tuple(comments)


@pytest.mark.parametrize("path", SOURCE_FILES, ids=lambda path: path.name)
def test_no_module_carries_a_coverage_pragma(path: Path) -> None:
    found = coverage_pragmas(path.read_text(encoding="utf-8"))
    assert found == (), (
        f"{path.name} carries {len(found)} coverage pragma(s): {found}. "
        f"100% is reached by testing every branch, never by excluding one."
    )


def test_the_pragma_detector_would_catch_a_real_one() -> None:
    """The control: a detector trusted for its silence must be shown to fire."""
    assert coverage_pragmas("x = 1  # pragma: no cover\n") == (
        (1, "# pragma: no cover"),
    )
    assert coverage_pragmas('"""a docstring mentioning pragma: no cover."""\n') == ()


def test_coverage_is_branch_mode_with_nothing_excluded() -> None:
    coverage = PYPROJECT["tool"]["coverage"]
    assert coverage["run"]["branch"] is True
    assert "omit" not in coverage["run"]
    assert "report" not in coverage, "no exclude_lines: nothing is waived"


def test_the_basedpyright_sibling_guard_is_declared() -> None:
    """An editable install of agentspec is INVISIBLE to basedpyright -- measured, not theory."""
    assert PYPROJECT["tool"]["basedpyright"]["extraPaths"] == ["../agentspec"]
    assert PYPROJECT["tool"]["basedpyright"]["typeCheckingMode"] == "standard"


def test_agentspec_is_not_declared_as_a_pip_dependency() -> None:
    """It is an unpublished in-repo sibling; pip would resolve the name off PyPI."""
    assert PYPROJECT["project"]["dependencies"] == []
    assert PYPROJECT["project"]["optional-dependencies"]["dev"]


def test_the_live_marker_is_registered_so_strict_markers_cannot_trip() -> None:
    markers = PYPROJECT["tool"]["pytest"]["ini_options"]["markers"]
    assert any(marker.startswith("live:") for marker in markers)


def test_the_rails_config_ships_inside_the_wheel() -> None:
    """Config is the product: a rail row that is not packaged is a rail that does not exist."""
    assert PYPROJECT["tool"]["setuptools"]["package-data"]["agentrail"] == [
        "rails.toml"
    ]
    assert PYPROJECT["tool"]["setuptools"]["packages"] == ["agentrail"]
    assert (PACKAGE_ROOT / "rails.toml").is_file()
