"""CC-0006 tests_required: known-present / known-absent / use-vs-mention / post-fix."""

from __future__ import annotations

import sys
from pathlib import Path

PROBE = Path(__file__).resolve().parent
REPO = PROBE.parents[3]
sys.path.insert(0, str(PROBE))

import wrong_recipe_gate as gate  # noqa: E402

FIXTURES = PROBE / "fixtures"
PRE_FIX = FIXTURES / "pre_fix_release_checklist.md"
SCRATCH = FIXTURES / "scratch_no_recipe.md"
PLANTED = FIXTURES / "planted_regression.md"
DOCUMENTARY = FIXTURES / "documentary_forbid.md"
LIVE_CHECKLIST = REPO / "command-center" / "RELEASE-CHECKLIST.md"
LIVE_SHELL = REPO / "rules" / "common" / "windows-shell.md"


def test_known_present_pre_fix_checklist_fires() -> None:
    """Known-present: pre-fix RELEASE-CHECKLIST 'git archive' line must fire."""
    report = gate.scan_paths([PRE_FIX], repo=REPO)
    assert report.hit_count >= 1, report.to_dict()
    assert report.prescriptive, report.to_dict()
    assert any(
        f.path.endswith("pre_fix_release_checklist.md") for f in report.prescriptive
    )
    assert all(f.recipe_id == gate.RECIPE_ID for f in report.prescriptive)


def test_known_absent_scratch_scores_zero() -> None:
    """Known-absent sentinel: scratch document with no recipe scores 0 hits."""
    report = gate.scan_paths([SCRATCH], repo=REPO)
    assert report.files_scanned == 1
    assert report.hit_count == 0, report.to_dict()
    assert report.prescriptive == []
    assert report.documentary == []
    assert report.ok_clean is True


def test_use_vs_mention_windows_shell_silent() -> None:
    """Use-vs-mention: windows-shell.md quotes the wrong recipe to forbid it — no fire."""
    assert LIVE_SHELL.is_file()
    report = gate.scan_paths([LIVE_SHELL], repo=REPO)
    assert report.hit_count == 0, report.to_dict()
    # May record documentary mentions; must not prescribe.
    assert report.prescriptive == [], report.to_dict()


def test_use_vs_mention_fixture_identical_string_silent() -> None:
    """Identical wrong string under documentary/forbid framing must not fire."""
    report = gate.scan_paths([DOCUMENTARY], repo=REPO)
    assert report.hit_count == 0, report.to_dict()
    assert report.documentary, "discriminator must SEE the mention, not skip the file"
    assert report.prescriptive == []


def test_post_fix_live_checklist_silent_planted_refires() -> None:
    """Post-fix: corrected checklist silent; planted regression re-fires."""
    live = gate.scan_paths([LIVE_CHECKLIST], repo=REPO)
    assert live.hit_count == 0, live.to_dict()
    assert live.prescriptive == [], live.to_dict()

    planted = gate.scan_paths([PLANTED], repo=REPO)
    assert planted.hit_count >= 1, planted.to_dict()
    assert planted.prescriptive, planted.to_dict()


def test_both_states_prescriptive_fires_documentary_silent() -> None:
    """Evidence control: FIRES on pre-fix/planted; SILENT on documentary+scratch+live."""
    bad = gate.scan_paths([PRE_FIX, PLANTED], repo=REPO)
    assert bad.hit_count >= 2, bad.to_dict()

    good = gate.scan_paths([DOCUMENTARY, SCRATCH, LIVE_CHECKLIST, LIVE_SHELL], repo=REPO)
    assert good.hit_count == 0, good.to_dict()
    assert good.ok_clean is True
