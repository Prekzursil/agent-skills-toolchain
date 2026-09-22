"""IMP-0010: projection map prediction matches dry-run; negative control.

Catalog tests_required:
- tools/plugin/tests/test_projection_map.py::test_prediction_matches_dry_run
- NEGATIVE CONTROL: remove one manifest entry and assert exactly one predicted
  path disappears (not zero, not many)
"""

from __future__ import annotations

import copy
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import projection_map as P  # noqa: E402

REPO = Path(__file__).resolve().parents[3]


@pytest.fixture(scope="module")
def projection_doc() -> dict:
    return P.build_projection_map(REPO)


def test_projection_map_validates_schema(projection_doc: dict) -> None:
    errs = P.validate_projection_map(projection_doc, REPO)
    assert errs == [], errs
    assert projection_doc["artifact"] == "projection-map"
    assert projection_doc["plugin"]
    assert projection_doc["version"]
    assert projection_doc["targets"]
    assert projection_doc["entrypoints"]


def test_consumes_generators_not_copies() -> None:
    """Reviewer evidence: generators are imported/called, not duplicated."""
    evidence = P.consumes_generators(REPO)
    assert evidence["imports_emit_hook_manifest"] is True
    assert evidence["imports_gen_skills_manifest"] is True
    assert evidence["emit_callable"] is True
    assert evidence["gen_callable"] is True
    assert evidence["emit_path_exists"] is True
    assert evidence["gen_path_exists"] is True


def test_prediction_matches_dry_run() -> None:
    """Catalog node: prediction live-path set == throwaway HOME dry-run listing."""
    with tempfile.TemporaryDirectory(prefix="imp0010-dry-") as tmp:
        home = Path(tmp) / "HOME"
        predicted = P.predict_live_paths(REPO, home=home)
        actual = P.dry_run_deploy(REPO, home=home)
        diff = P.diff_prediction_against_dry_run(predicted, actual)
        assert diff["ok"] is True, diff
        assert diff["predicted_count"] == diff["actual_count"]
        assert not diff["predicted_but_absent"]
        assert not diff["present_but_unpredicted"]
        # Sanity: skills + settings + hooks projected + dispatch.
        assert any(p.endswith("settings.json") for p in predicted)
        assert any("hooks.codex-plugin.json" in p for p in predicted)
        assert any("_dispatch/manifest.json" in p.replace("\\", "/") for p in predicted)
        assert any("/skills/" in p.replace("\\", "/") for p in predicted)


def test_negative_control_remove_one_skill_drops_exactly_one_path() -> None:
    """NEGATIVE CONTROL: remove one DEPLOYED-MANIFEST entry → exactly one path gone."""
    deployed = P.load_deployed(REPO)
    assert len(deployed) >= 2, "need >=2 deployed skills for negative control"
    baseline = P.predict_live_paths(REPO, home=Path("/tmp/imp0010-neg-home-base"))
    removed = deployed[0]
    assert isinstance(removed, dict) and isinstance(removed.get("name"), str)
    mutated = copy.deepcopy(deployed)
    mutated.pop(0)
    reduced = P.predict_live_paths(
        REPO, home=Path("/tmp/imp0010-neg-home-base"), deployed=mutated
    )
    disappeared = baseline - reduced
    appeared = reduced - baseline
    assert len(disappeared) == 1, (
        f"expected exactly one path to disappear, got {len(disappeared)}: "
        f"{sorted(disappeared)[:5]}"
    )
    assert not appeared, f"unexpected new paths: {sorted(appeared)[:5]}"
    only = next(iter(disappeared))
    assert removed["name"] in only.replace("\\", "/")
    assert only.replace("\\", "/").endswith(f"/skills/{removed['name']}/SKILL.md")


def test_settings_and_dispatch_and_skills_are_represented(projection_doc: dict) -> None:
    ids = {ep["id"] for ep in projection_doc["entrypoints"]}
    assert any(i.startswith("settings:") for i in ids)
    assert any(i.startswith("hooks:") for i in ids)
    assert any(i.startswith("dispatch:") for i in ids)
    assert any(i.startswith("skill:") for i in ids)
    # Round-trip: emitted hooks event count matches hooks:* entrypoints.
    emitted = P.emit_hooks_for_live(REPO)
    hook_eps = {i for i in ids if i.startswith("hooks:")}
    assert hook_eps == {f"hooks:{k}" for k in emitted["hooks"]}
