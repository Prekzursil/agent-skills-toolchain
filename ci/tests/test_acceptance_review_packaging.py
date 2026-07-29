"""D-wu-19 -- the acceptance-review helper must be reachable from what SKILL.md says.

Two packaging failures shipped together and are asserted here as invariants, not prose:

  * SKILL.md said "From the repo root run the helper" and prescribed
    ``python scripts/acceptance_review.py``.  No repo root holds that file -- the helper
    ships BESIDE SKILL.md at ``<skill>/scripts/acceptance_review.py``, which is exactly
    what the same document's own "Files" block depicts.  Followed literally from a target
    repository root, step 1 of the advertised acceptance gate exits 2 with ENOENT, so no
    evidence, prompt, routing or verdict is ever produced.
  * ``ci/skills-allowlist/acceptance-review/`` shipped ONLY ``SKILL.md``.  The codex-runner
    copies that tree VERBATIM into ``$HOME/.agents/skills`` and then runs Codex with
    ``working-directory: work`` (the target checkout), so the helper was absent from the
    production CI skill surface too.

The projection cannot be repaired by copying the helper in after the copy step:
``ci/skill_surface_census.py`` merkle-compares the allowlist against the installed root, so
an extra installed file would fail the census.  The helper therefore lives IN the allowlist
as a second copy, and a drift step in ``quality.yml`` keeps it byte-equal to the canonical
one; that wiring is asserted below for the same reason ``test_ci_wiring.py`` asserts its own.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CANONICAL = REPO_ROOT / ".agents" / "skills" / "acceptance-review"
PROJECTION = REPO_ROOT / "skills" / "acceptance-review"
CI_ALLOWLIST = REPO_ROOT / "ci" / "skills-allowlist" / "acceptance-review"
SKILL_DIRS = (CANONICAL, PROJECTION, CI_ALLOWLIST)

HELPER_RELATIVE = Path("scripts") / "acceptance_review.py"
SKILL_DIR_TOKEN = "<SKILL_DIR>"
INVOCATION = re.compile(r"python\s+(\S*acceptance_review\.py)")

QUALITY_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "quality.yml"
DRIFT_MARKERS = (
    ".agents/skills/acceptance-review/scripts/acceptance_review.py",
    "ci/skills-allowlist/acceptance-review/scripts/acceptance_review.py",
)


def _read(path: Path) -> str:
    return path.read_bytes().decode("utf-8").replace("\r\n", "\n")


def test_every_skill_copy_ships_the_helper_it_advertises() -> None:
    """Including the CI projection the codex-runner installs verbatim."""
    missing = [d.name for d in SKILL_DIRS if not (d / HELPER_RELATIVE).is_file()]
    assert not missing, f"skill dirs advertise a helper they do not ship: {missing}"


def test_skill_md_anchors_every_invocation_to_the_skill_directory() -> None:
    """A bare relative path silently resolves against the caller's cwd -- the D-wu-19 bug."""
    for skill_dir in SKILL_DIRS:
        text = _read(skill_dir / "SKILL.md")
        assert "From the repo root run the helper" not in text, (
            f"{skill_dir.name}: SKILL.md still anchors the helper to a repo root"
        )
        assert SKILL_DIR_TOKEN in text, (
            f"{skill_dir.name}: SKILL.md uses no {SKILL_DIR_TOKEN} anchor"
        )
        invocations = INVOCATION.findall(text)
        assert invocations, f"{skill_dir.name}: SKILL.md invokes no helper at all"
        for raw in invocations:
            assert raw.startswith(f"{SKILL_DIR_TOKEN}/"), (
                f"{skill_dir.name}: unanchored helper invocation {raw!r}"
            )
            resolved = skill_dir / raw.replace(f"{SKILL_DIR_TOKEN}/", "")
            assert resolved.is_file(), f"{skill_dir.name}: {raw!r} resolves nowhere"


def test_ci_projection_helper_matches_the_canonical_helper() -> None:
    assert _read(CI_ALLOWLIST / HELPER_RELATIVE) == _read(CANONICAL / HELPER_RELATIVE)


def test_quality_workflow_guards_the_duplicated_helper() -> None:
    """The second copy is only safe while CI diffs it against the canonical one."""
    workflow = _read(QUALITY_WORKFLOW)
    for marker in DRIFT_MARKERS:
        assert marker in workflow, f"quality.yml does not diff {marker}"
