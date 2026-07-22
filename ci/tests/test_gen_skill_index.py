"""Tests for the A01 skill-index generator.

Built on a synthetic tree rather than the live repo, so the assertions stay true as the real skill
surface changes. The live repo is exercised separately by one calibration test that pins the
generator against a figure the option card independently measured.
"""

from __future__ import annotations

import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from gen_skill_index import census, enumerate_skills, generate_declarations  # noqa: E402


def _mk(tmp: pathlib.Path, root: str, name: str, body: str = "# skill\n") -> None:
    d = tmp / root / name
    d.mkdir(parents=True, exist_ok=True)
    (d / "SKILL.md").write_text(body, encoding="utf-8")


def _marketplace(tmp: pathlib.Path, entries: list[str]) -> None:
    d = tmp / ".claude-plugin"
    d.mkdir(parents=True, exist_ok=True)
    (d / "marketplace.json").write_text(
        json.dumps({"plugins": [{"name": "p", "source": "./", "skills": entries}]}),
        encoding="utf-8",
    )


def test_enumerates_by_skill_md_not_by_directory_listing(tmp_path):
    """A directory without a SKILL.md is not a skill — listing alone would miscount it."""
    _mk(tmp_path, ".agents/skills", "real")
    (tmp_path / ".agents/skills/not-a-skill").mkdir(parents=True, exist_ok=True)
    assert enumerate_skills(tmp_path, ".agents/skills") == {"real"}


def test_dangling_is_declared_minus_on_disk(tmp_path):
    _mk(tmp_path, ".agents/skills", "present")
    _marketplace(tmp_path, ["./.agents/skills/present", "./skills/gone"])
    c = census(tmp_path)
    assert c["dangling_declared_but_absent"] == ["gone"]


def test_undeclared_is_on_disk_minus_declared(tmp_path):
    _mk(tmp_path, ".agents/skills", "declared")
    _mk(tmp_path, ".agents/skills", "forgotten")
    _marketplace(tmp_path, ["./.agents/skills/declared"])
    c = census(tmp_path)
    assert c["undeclared_on_disk"] == ["forgotten"]


def test_a_projection_only_skill_is_still_declared(tmp_path):
    """D-001 forbids implicit removals: generating must not silently drop a published skill."""
    _mk(tmp_path, ".agents/skills", "both")
    _mk(tmp_path, "skills", "both")
    _mk(tmp_path, "skills", "projection_only")
    gen = generate_declarations(tmp_path)
    assert "./.agents/skills/both" in gen
    assert "./skills/projection_only" in gen
    assert "./skills/both" not in gen, (
        "a skill present canonically must be declared ONCE, canonically"
    )


def test_control_fires_when_the_tree_is_empty(tmp_path):
    """An empty result must be reported as an unvalidated detector, not as 'no drift'."""
    assert census(tmp_path)["control_enumerator_found_skills"] is False


def test_control_passes_on_a_populated_tree(tmp_path):
    _mk(tmp_path, ".agents/skills", "x")
    assert census(tmp_path)["control_enumerator_found_skills"] is True


def test_calibration_against_the_card_measurement():
    """Pin the generator to a figure the A01 option card measured independently.

    The card states "110 declared skills, 6 dangling". If this generator disagrees with that on the
    real tree, either the generator is wrong or the surface moved — both are worth failing on,
    because the whole point of A01 is that this number stops being hand-maintained folklore.
    """
    repo = pathlib.Path(__file__).resolve().parent.parent.parent
    if not (repo / ".claude-plugin" / "marketplace.json").is_file():
        return  # not a full checkout; nothing to calibrate against
    c = census(repo)
    assert c["declared_count"] == 110, (
        f"declared drifted from the card's 110: {c['declared_count']}"
    )
    assert len(c["dangling_declared_but_absent"]) == 6, (
        f"dangling drifted from the card's 6: {c['dangling_declared_but_absent']}"
    )
