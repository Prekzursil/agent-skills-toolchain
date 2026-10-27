"""IMP-0010 tests: the projection predicts exactly what a dry-run deploy does."""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[2]
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from plugin import projection_map as pm  # noqa: E402


def test_prediction_matches_dry_run() -> None:
    with tempfile.TemporaryDirectory() as td:
        home = Path(td) / "home"
        bundle = pm.load_bundle(TOOLS.parent)
        predicted = pm.predict(bundle, home)
        actual = pm.dry_run(bundle, home)
        assert predicted == actual, pm.diff_sets(predicted, actual)
        diff = pm.diff_sets(predicted, actual)
        assert diff["predicted_absent"] == []
        assert diff["present_unpredicted"] == []
        assert len(predicted) >= 3


def test_negative_control_drop_one_skill_exactly_one_path_disappears() -> None:
    with tempfile.TemporaryDirectory() as td:
        home = Path(td) / "home"
        bundle = pm.load_bundle(TOOLS.parent)
        base = pm.predict(bundle, home)
        skills = bundle["skills"]["skills"]
        victim = skills[0]["name"]
        dropped = pm.drop_entry(bundle, "skill", victim)
        after = pm.predict(dropped, home)
        gone = set(base) - set(after)
        assert len(gone) == 1, f"expected exactly one predicted path to disappear, got {sorted(gone)}"
        assert any(victim in g for g in gone)
        # and the dry-run agrees with the dropped prediction too
        home2 = Path(td) / "home2"
        after2 = pm.predict(dropped, home2)
        actual = pm.dry_run(dropped, home2)
        assert after2 == actual
