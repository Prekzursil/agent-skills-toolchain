"""Tests for the A01 skill-index generator.

Built on a synthetic tree rather than the live repo, so the assertions stay true as the real skill
surface changes. The live repo is exercised separately by one test that requires the committed
marketplace routes to equal the generated snapshot exactly.
"""

from __future__ import annotations

import json
import pathlib
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from gen_skill_index import (  # noqa: E402
    census,
    declared_from_marketplace,
    enumerate_skills,
    generate_declarations,
)

GENERATOR = pathlib.Path(__file__).resolve().parent.parent / "gen_skill_index.py"


KNOWN_PRESENT_CANONICAL = "010-editor"
KNOWN_PRESENT_PROJECTION_ONLY = "azure-observability"


def _mk(tmp: pathlib.Path, root: str, name: str, body: str = "# skill\n") -> None:
    d = tmp / root / name
    d.mkdir(parents=True, exist_ok=True)
    (d / "SKILL.md").write_text(body, encoding="utf-8")


def _marketplace(tmp: pathlib.Path, entries: list[str]) -> None:
    d = tmp / ".claude-plugin"
    d.mkdir(parents=True, exist_ok=True)
    (d / "marketplace.json").write_text(
        json.dumps(
            {
                "name": "p",
                "plugins": [
                    {
                        "name": "p",
                        "source": "./",
                        "strict": False,
                        "description": "preserve me",
                        "skills": entries,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )


def _run(tmp: pathlib.Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(GENERATOR), "--repo", str(tmp), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
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


def test_projection_roots_are_a_name_union_with_first_root_precedence(tmp_path):
    """Known-broken pre-change: the same projection-only name is emitted twice."""
    _mk(tmp_path, "skills", "duplicate")
    _mk(tmp_path, "skills-claude-only", "duplicate")
    assert generate_declarations(tmp_path) == ["./skills/duplicate"]


def test_generation_carries_forward_declared_only_entries(tmp_path):
    """Known-broken pre-change: regeneration silently drops a published absent path."""
    _mk(tmp_path, ".agents/skills", "current")
    _marketplace(tmp_path, ["./skills/current", "./skills/published-alias"])
    assert generate_declarations(tmp_path) == [
        "./.agents/skills/current",
        "./skills/published-alias",
    ]


def test_control_fires_when_the_tree_is_empty(tmp_path):
    """An empty result must be reported as an unvalidated detector, not as 'no drift'."""
    assert census(tmp_path)["control_enumerator_found_skills"] is False


def test_control_passes_on_a_populated_tree(tmp_path):
    _mk(tmp_path, ".agents/skills", "010-editor")
    assert census(tmp_path)["control_enumerator_found_skills"] is True


def test_unrelated_populated_tree_does_not_satisfy_known_present_control(tmp_path):
    """Known-broken pre-change: any nonempty root passes the detector control."""
    _mk(tmp_path, ".agents/skills", "unrelated")
    assert census(tmp_path)["control_enumerator_found_skills"] is False


def test_check_rejects_projection_route_for_canonical_skill(tmp_path):
    """Known-broken pre-change: basename-only drift accepts the wrong root."""
    _mk(tmp_path, ".agents/skills", "010-editor")
    _marketplace(tmp_path, ["./skills/010-editor"])
    stale = _run(tmp_path, "--check", "--fail-on-drift")
    assert stale.returncode == 1, stale.stdout + stale.stderr

    _marketplace(tmp_path, ["./.agents/skills/010-editor"])
    current = _run(tmp_path, "--check", "--fail-on-drift")
    assert current.returncode == 0, current.stdout + current.stderr


def test_write_updates_only_the_generated_skill_index(tmp_path):
    """Known-broken pre-change: the generator has no write mode."""
    _mk(tmp_path, ".agents/skills", "010-editor")
    _mk(tmp_path, "skills", "projection-only")
    _marketplace(tmp_path, ["./skills/010-editor"])

    proc = _run(tmp_path, "--write")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    doc = json.loads(
        (tmp_path / ".claude-plugin/marketplace.json").read_text(encoding="utf-8")
    )
    plugin = doc["plugins"][0]
    assert plugin["skills"] == [
        "./.agents/skills/010-editor",
        "./skills/projection-only",
    ]
    assert plugin["strict"] is False
    assert plugin["description"] == "preserve me"


def test_committed_marketplace_matches_generated_declarations():
    """Known-broken pre-change: the committed hand-list differs from generated output."""
    repo = pathlib.Path(__file__).resolve().parent.parent.parent
    if not (repo / ".claude-plugin" / "marketplace.json").is_file():
        return  # not a full checkout; nothing to compare
    doc = json.loads(
        (repo / ".claude-plugin/marketplace.json").read_text(encoding="utf-8")
    )
    assert doc["plugins"][0]["skills"] == generate_declarations(repo)


def test_committed_marketplace_is_the_generated_union():
    """Known-broken pre-F14: the committed 110-entry hand-list is not the generated union."""
    repo = pathlib.Path(__file__).resolve().parent.parent.parent
    if not (repo / ".claude-plugin" / "marketplace.json").is_file():
        return  # not a full checkout; nothing to calibrate against
    canonical = enumerate_skills(repo, ".agents/skills")
    projection_only = enumerate_skills(repo, "skills-claude-only") - canonical
    declared, doc = declared_from_marketplace(repo)

    assert KNOWN_PRESENT_CANONICAL in canonical
    assert KNOWN_PRESENT_CANONICAL in declared
    assert KNOWN_PRESENT_PROJECTION_ONLY in projection_only
    assert KNOWN_PRESENT_PROJECTION_ONLY in declared
    assert doc["plugins"][0]["skills"] == generate_declarations(repo)


def test_plugin_release_version_advances_with_the_surface():
    """Known-broken pre-F14: version 0.2.0 keeps installed users on the old cache."""
    repo = pathlib.Path(__file__).resolve().parent.parent.parent
    marketplace_path = repo / ".claude-plugin" / "marketplace.json"
    plugin_path = repo / ".claude-plugin" / "plugin.json"
    if not marketplace_path.is_file() or not plugin_path.is_file():
        return  # not a full checkout; nothing to calibrate against

    marketplace_doc = json.loads(marketplace_path.read_text(encoding="utf-8"))
    plugin_doc = json.loads(plugin_path.read_text(encoding="utf-8"))
    marketplace_version = marketplace_doc["plugins"][0]["version"]
    assert marketplace_version == plugin_doc["version"]
    assert plugin_doc["version"] != "0.2.0"
