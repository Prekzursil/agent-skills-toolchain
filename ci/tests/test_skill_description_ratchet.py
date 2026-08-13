"""Acceptance + WIRING suite for ``ci/check_skill_description_ratchet.py``.

WHY THIS FILE EXISTS
--------------------
Two halves, and the second is the one the INTEGRATE lane exists for.

BEHAVIOUR (hermetic, ``tmp_path`` only).  A gate that has never gone red is
indistinguishable from a no-op (``rules/common/ci-hygiene.md`` #1).  Every
violation class below is proven to FIRE against a deliberately broken fixture,
and the green case is proven to stay silent, so the gate's silence carries
information.  The ``over-spec`` fixture is not synthetic: it reproduces the
lane's own measured self-inflicted defect, where a writer bug stamped a
4,000-char control string over 7 real descriptions across 3 trees and was caught
only by a post-write re-read.  This gate would have caught it in CI.

WIRING.  ``test_the_workflow_runs_this_suite_by_explicit_path`` and
``test_the_ratchet_has_an_agent_facing_surface`` go RED if the integration is
removed -- respectively if the workflow step is deleted, or if no curated skill
tells an agent the command.  Same shape as
``ci/tests/test_deploy_skills_daily.py``, and for the same measured reason: this
repository has NO test autodiscovery, so a directory glob is one refactor away
from silently un-gating the tool, and a tool with no agent-facing surface is
never invoked at all.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
TOOL_PATH = REPO_ROOT / "ci" / "check_skill_description_ratchet.py"
EXEMPTIONS_PATH = REPO_ROOT / "ci" / "skill-description-exemptions.txt"
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "skill-dual-write.yml"

CANONICAL_SKILL_ROOT = REPO_ROOT / ".agents" / "skills"
PROJECTED_SKILL_ROOT = REPO_ROOT / "skills"

# Assert the COMMAND, not the file name: a document that merely names the script in
# prose is a mention, not a route an agent can run (use-vs-mention).
INVOCATION_MARKER = "python ci/check_skill_description_ratchet.py"
WORKFLOW_EXPLICIT_MARKER = (
    "python -m pytest ci/tests/test_skill_description_ratchet.py"
)
WORKFLOW_GLOB_MARKER = "python -m pytest ci/tests tools/d001-dual-write/tests"


def _load():
    spec = importlib.util.spec_from_file_location(
        "_skill_description_ratchet", TOOL_PATH
    )
    assert spec is not None and spec.loader is not None, f"cannot load {TOOL_PATH}"
    module = importlib.util.module_from_spec(spec)
    # Register BEFORE exec: ``@dataclass`` resolves annotations through
    # ``sys.modules[cls.__module__]``, which is None for a module loaded by path
    # alone (AttributeError on 3.14).  ci/tests/test_check_skill_context_budget.py
    # sidesteps this by importing via a sys.path insert; this is the same fix for
    # the explicit-path style used by ci/tests/test_deploy_skills_daily.py.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


mod = _load()


def _skill(root: Path, name: str, description: str, folded: bool = False) -> None:
    directory = root / name
    directory.mkdir(parents=True, exist_ok=True)
    if folded:
        body = f"---\nname: {name}\ndescription: >\n  {description}\n---\n\nbody\n"
    else:
        body = f"---\nname: {name}\ndescription: {description}\n---\n\nbody\n"
    (directory / "SKILL.md").write_text(body, encoding="utf-8")


@pytest.fixture()
def clean(tmp_path: Path) -> tuple[Path, Path]:
    """A one-skill root that is within every rule, plus an empty exemptions file."""
    root = tmp_path / "skills"
    _skill(root, "alpha", "Use when alpha. Do NOT use for beta; use beta instead.")
    exemptions = tmp_path / "exempt.txt"
    exemptions.write_text("# none\n", encoding="utf-8")
    return root, exemptions


def _run(root: Path, exemptions: Path) -> int:
    return mod.main(["--root", str(root), "--exemptions", str(exemptions)])


# ---------------------------------------------------------------------------
# BOTH STATES: the gate must be silent on clean input and FIRE on each defect.
# ---------------------------------------------------------------------------


def test_a_clean_surface_passes(clean: tuple[Path, Path]) -> None:
    assert _run(*clean) == mod.EXIT_OK


def test_an_oversized_description_fails(clean: tuple[Path, Path]) -> None:
    """The lane's own self-inflicted defect: a 4,000-char description."""
    root, exemptions = clean
    _skill(root, "bravo", "x" * 4000)
    assert _run(root, exemptions) == mod.EXIT_VIOLATION


def test_a_description_exactly_at_the_spec_limit_passes(
    clean: tuple[Path, Path],
) -> None:
    """Boundary: 1024 is allowed, 1025 is not -- an off-by-one here mis-gates."""
    root, exemptions = clean
    _skill(root, "bravo", "y" * mod.SPEC_MAX_CHARS)
    assert _run(root, exemptions) == mod.EXIT_OK
    _skill(root, "bravo", "y" * (mod.SPEC_MAX_CHARS + 1))
    assert _run(root, exemptions) == mod.EXIT_VIOLATION


def test_a_folded_description_fails(clean: tuple[Path, Path]) -> None:
    root, exemptions = clean
    _skill(root, "bravo", "folded text here", folded=True)
    assert _run(root, exemptions) == mod.EXIT_VIOLATION


def test_a_pinned_over_spec_skill_passes_but_may_not_grow(tmp_path: Path) -> None:
    """The ratchet: grandfathered at its pinned size, red the moment it grows."""
    root = tmp_path / "skills"
    _skill(root, "legacy", "z" * 1500)
    exemptions = tmp_path / "exempt.txt"
    exemptions.write_text("over-spec:legacy:1500\n", encoding="utf-8")
    assert _run(root, exemptions) == mod.EXIT_OK
    _skill(root, "legacy", "z" * 1501)
    assert _run(root, exemptions) == mod.EXIT_VIOLATION


def test_a_stale_exemption_fails(tmp_path: Path) -> None:
    """Shrink-only: fixing a skill without deleting its line is itself a failure."""
    root = tmp_path / "skills"
    _skill(root, "legacy", "z" * 100)
    exemptions = tmp_path / "exempt.txt"
    exemptions.write_text("over-spec:legacy:1500\n", encoding="utf-8")
    assert _run(root, exemptions) == mod.EXIT_VIOLATION


def test_a_stale_folded_exemption_fails(tmp_path: Path) -> None:
    root = tmp_path / "skills"
    _skill(root, "legacy", "now one line")
    exemptions = tmp_path / "exempt.txt"
    exemptions.write_text("folded:legacy\n", encoding="utf-8")
    assert _run(root, exemptions) == mod.EXIT_VIOLATION


def test_an_exemption_for_a_nonexistent_skill_fails(clean: tuple[Path, Path]) -> None:
    root, exemptions = clean
    exemptions.write_text("over-spec:ghost:1500\n", encoding="utf-8")
    assert _run(root, exemptions) == mod.EXIT_VIOLATION


def test_an_exemption_that_grants_nothing_is_a_config_error(
    clean: tuple[Path, Path],
) -> None:
    """A pin at or below the spec limit is dead data, not a permissive default."""
    root, exemptions = clean
    exemptions.write_text("over-spec:alpha:1024\n", encoding="utf-8")
    assert _run(root, exemptions) == mod.EXIT_CONFIG


def test_a_malformed_exemption_is_a_config_error(clean: tuple[Path, Path]) -> None:
    root, exemptions = clean
    exemptions.write_text("over-spec:missing-the-max\n", encoding="utf-8")
    assert _run(root, exemptions) == mod.EXIT_CONFIG


def test_an_empty_walk_fails_closed(tmp_path: Path) -> None:
    """"Found nothing, therefore pass" is the no-op gate ci-hygiene #1 forbids."""
    root = tmp_path / "skills"
    root.mkdir()
    exemptions = tmp_path / "exempt.txt"
    exemptions.write_text("# none\n", encoding="utf-8")
    assert _run(root, exemptions) == mod.EXIT_CONFIG


def test_a_skill_with_no_description_fails_closed(clean: tuple[Path, Path]) -> None:
    root, exemptions = clean
    directory = root / "broken"
    directory.mkdir()
    (directory / "SKILL.md").write_text("---\nname: broken\n---\nbody\n", "utf-8")
    assert _run(root, exemptions) == mod.EXIT_CONFIG


def test_crlf_and_lf_measure_the_same_length(tmp_path: Path) -> None:
    """A Windows working tree and the LF blob CI checks out must agree.

    windows-shell.md #8b: a local green measured against different bytes than CI
    reads is the false-confidence class this repo has already been bitten by.
    """
    lengths = []
    for index, newline in enumerate(("\n", "\r\n")):
        root = tmp_path / f"r{index}"
        directory = root / "alpha"
        directory.mkdir(parents=True)
        text = "---\nname: alpha\ndescription: same text\n---\n\nbody\n"
        (directory / "SKILL.md").write_bytes(text.replace("\n", newline).encode())
        lengths.append(mod.parse_description(directory / "SKILL.md", "alpha", "r").chars)
    assert lengths[0] == lengths[1], f"CRLF/LF disagree: {lengths}"


def test_the_advisory_total_never_blocks(clean: tuple[Path, Path]) -> None:
    """The session-dependent number is reported, never enforced."""
    root, exemptions = clean
    for index in range(30):
        _skill(root, f"bulk{index}", "q" * 900)
    assert _run(root, exemptions) == mod.EXIT_OK


def test_the_verdicts_are_distinguishable(clean: tuple[Path, Path]) -> None:
    """Rule 3c control: a probe returning one verdict for every state proves nothing.

    If clean/violation/config all collapsed to the same exit code this suite would
    be measuring only that the tool is importable.
    """
    root, exemptions = clean
    ok = _run(root, exemptions)
    _skill(root, "bravo", "x" * 4000)
    violation = _run(root, exemptions)
    exemptions.write_text("over-spec:bogus\n", encoding="utf-8")
    config = _run(root, exemptions)
    assert len({ok, violation, config}) == 3, (ok, violation, config)


# ---------------------------------------------------------------------------
# THE REAL SURFACE -- these assert the gate is green on the committed tree.
# ---------------------------------------------------------------------------


def test_the_committed_skill_surface_is_green() -> None:
    """Green at HEAD by construction; a new violation turns THIS red."""
    assert mod.main(["--repo", str(REPO_ROOT)]) == mod.EXIT_OK


def test_every_pinned_exemption_is_still_earned() -> None:
    """Redundant with the run above, but names the ratchet property explicitly."""
    exemptions = mod.parse_exemptions(EXEMPTIONS_PATH)
    descriptions = mod.collect(
        [CANONICAL_SKILL_ROOT, PROJECTED_SKILL_ROOT]
    )
    violations, _ = mod.evaluate(descriptions, exemptions)
    stale = [v for v in violations if v["rule"] in {"stale-exemption", "unknown-exemption"}]
    assert not stale, f"the exemptions file has drifted: {stale}"


# ---------------------------------------------------------------------------
# INTEGRATION -- these go RED if the wiring is removed.
# ---------------------------------------------------------------------------


def test_the_tool_and_its_exemptions_exist() -> None:
    assert TOOL_PATH.is_file(), f"missing {TOOL_PATH}"
    assert EXEMPTIONS_PATH.is_file(), f"missing {EXEMPTIONS_PATH}"


def test_the_workflow_runs_this_suite_by_explicit_path() -> None:
    assert WORKFLOW.is_file(), f"missing {WORKFLOW}"
    assert WORKFLOW_EXPLICIT_MARKER in WORKFLOW.read_text(encoding="utf-8"), (
        "skill-dual-write.yml no longer invokes this suite by explicit path"
    )


def test_the_workflow_runs_the_gate_itself() -> None:
    """The suite proves the tool works; this step proves the tool is USED on the tree."""
    assert INVOCATION_MARKER in WORKFLOW.read_text(encoding="utf-8"), (
        "skill-dual-write.yml no longer runs the ratchet against the repo surface"
    )


def test_the_workflow_glob_still_covers_this_directory() -> None:
    """The second, independent route.  Either one alone is a single signal."""
    rel = Path(__file__).resolve().parent.relative_to(REPO_ROOT).as_posix()
    assert rel == "ci/tests"
    assert WORKFLOW_GLOB_MARKER in WORKFLOW.read_text(encoding="utf-8")


def _skills_carrying_the_invocation(root: Path) -> set[str]:
    if not root.is_dir():
        return set()
    return {
        path.parent.name
        for path in root.glob("*/SKILL.md")
        if INVOCATION_MARKER in path.read_text(encoding="utf-8", errors="replace")
    }


def test_the_ratchet_has_an_agent_facing_surface() -> None:
    """A tool no curated skill names as a command is never run by an agent."""
    carriers = _skills_carrying_the_invocation(CANONICAL_SKILL_ROOT)
    assert carriers, (
        f"no curated skill tells an agent to run `{INVOCATION_MARKER}`; a skill "
        "author gets no warning that the description is a budgeted, truncatable "
        "recall surface"
    )


def test_the_agent_facing_surface_is_dual_written() -> None:
    canonical = _skills_carrying_the_invocation(CANONICAL_SKILL_ROOT)
    projected = _skills_carrying_the_invocation(PROJECTED_SKILL_ROOT)
    assert canonical == projected, (
        f"ratchet reference not dual-written: only in .agents/skills="
        f"{sorted(canonical - projected)} only in skills={sorted(projected - canonical)}"
    )
