"""Unit tests for CC-0022 decision-log reconcile + staleness sentinel."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
LIB = REPO / "command-center" / "lib"
PROBE = REPO / "command-center/p2-wave/probes/CC-0022"
OPT = REPO / "command-center/option-id/07-OPTION-UNIVERSE.family-M-slice.md"
PRE = REPO / "command-center/option-id/13-ARCHITECTURE-CANDIDATES.pre-fix-slice.md"
POST = REPO / "command-center/option-id/13-ARCHITECTURE-CANDIDATES.post-fix-slice.md"
BEFORE = PROBE / "fixtures/decision-log-before.md"
AFTER = PROBE / "fixtures/decision-log-after.md"
LIVE = REPO / "17-DECISION-LOG.md"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def fixtures_built():
    bf = _load("cc0022_build_fixtures", PROBE / "build_fixtures.py")
    assert bf.main() == 0
    return bf


@pytest.fixture(scope="module")
def sentinel(fixtures_built):
    return _load("decision_log_sentinel", LIB / "decision_log_sentinel.py")


@pytest.fixture(scope="module")
def reconcile(fixtures_built):
    return _load("decision_log_reconcile", LIB / "decision_log_reconcile.py")


@pytest.fixture(scope="module")
def collision(fixtures_built):
    return _load("option_id_collision_probe", LIB / "option_id_collision_probe.py")


@pytest.fixture(scope="module")
def snap(collision, fixtures_built):
    return collision.live_snapshot(repo=REPO, option_path=OPT, arch_path=POST)


def test_both_states_line_175_fires_then_silent(
    sentinel, collision, snap, fixtures_built
):
    before = BEFORE.read_text(encoding="utf-8")
    after = AFTER.read_text(encoding="utf-8")
    assert "MECH" not in before
    assert "MECH" in after
    line175 = before.splitlines()[174]
    assert "31-way option-id collision" in line175
    assert "Queued as P2-09" in line175
    pre_n = collision.collision_count(
        OPT.read_text(encoding="utf-8"), PRE.read_text(encoding="utf-8")
    )
    post_n = collision.collision_count(
        OPT.read_text(encoding="utf-8"), POST.read_text(encoding="utf-8")
    )
    assert pre_n == 31
    assert post_n == 0
    rb = sentinel.scan(before, snapshot=snap)
    ra = sentinel.scan(after, snapshot=snap)
    assert rb.fired is True
    assert any(f.entry_id == "DL-0042" for f in rb.fires)
    assert ra.fired is False
    assert ra.skipped_superseded >= 1


def test_planted_stale_also_fires(sentinel, snap, fixtures_built):
    after = AFTER.read_text(encoding="utf-8")
    planted = (
        after
        + "\n## DL-PLANT-STALE Planted stale\n"
        + "date: 2026-08-24\nstatus: CURRENT\nvalid_as_of: 2026-08-24\n\n"
        + "The 31-way option-id collision between 07-OPTION-UNIVERSE family M and "
        + "13-ARCHITECTURE-CANDIDATES is live. Status: Queued as P2-09.\n"
    )
    rp = sentinel.scan(planted, snapshot=snap)
    assert rp.fired is True
    assert any(f.entry_id == "DL-PLANT-STALE" for f in rp.fires)


def test_currently_true_entry_does_not_fire(sentinel, snap, fixtures_built):
    after = AFTER.read_text(encoding="utf-8")
    rb = sentinel.scan(AFTER.read_text(encoding="utf-8"), snapshot=snap)
    assert not any(f.entry_id == "DL-0001" for f in rb.fires)
    true_copy = (
        after
        + "\n## DL-PLANT-TRUE True claim\n"
        + "date: 2026-08-24\nstatus: CURRENT\nvalid_as_of: 2026-08-24\n\n"
        + "probe-assert: collision_count == 0\n"
    )
    rt = sentinel.scan(true_copy, snapshot=snap)
    assert rt.fired is False


def test_reconcile_preserves_meaning(reconcile, fixtures_built):
    before = BEFORE.read_text(encoding="utf-8")
    after = AFTER.read_text(encoding="utf-8")
    review = reconcile.unchanged_except_collision(before, after)
    assert review["ok"] is True
    assert reconcile.ORIGINAL_SENTENCE in after
    assert "superseded_by" in after
    assert LIVE.read_text(encoding="utf-8") == after
