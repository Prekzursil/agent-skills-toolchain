"""Tests for cli/status.py — pure status assembly (100% branch)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.models import PollResult, Provenance, TaskStatus, TaskSpec  # noqa: E402
from probes.base import ProbeReading  # noqa: E402
from cli import status as st  # noqa: E402


def _reading(
    done=4.0,
    total=8.0,
    *,
    phase="complex leg",
    frontier=4.0,
    gpu="GPU 0 98%",
    terminal=False,
    detail="d",
) -> ProbeReading:
    return ProbeReading(
        done=done,
        total=total,
        phase=phase,
        frontier=frontier,
        gpu=gpu,
        terminal=terminal,
        detail=detail,
    )


# ── derive_status ──────────────────────────────────────────────────────────────


def _derive(**over: bool) -> TaskStatus:
    base = dict(
        blind=False,
        failed=False,
        terminal=False,
        exists=True,
        progressing=False,
        has_progress=False,
        stalled=False,
    )
    base.update(over)
    return st.derive_status(**base)


def test_derive_blind_wins():
    assert _derive(blind=True, terminal=True) is TaskStatus.BLIND


def test_derive_failed():
    assert _derive(failed=True, terminal=True) is TaskStatus.FAILED


def test_derive_terminal_done():
    assert _derive(terminal=True) is TaskStatus.DONE


def test_derive_absent_pending():
    assert _derive(exists=False) is TaskStatus.PENDING


def test_derive_stalled():
    assert _derive(stalled=True) is TaskStatus.STALLED


def test_derive_running_via_progressing():
    assert _derive(progressing=True) is TaskStatus.RUNNING


def test_derive_running_via_has_progress():
    assert _derive(progressing=False, has_progress=True) is TaskStatus.RUNNING


def test_derive_pending_default():
    assert _derive() is TaskStatus.PENDING


# ── select_eta ─────────────────────────────────────────────────────────────────


def test_select_eta_measured():
    eta = st.select_eta(fraction=0.5, elapsed_s=100.0, prior_duration_s=None)
    assert eta.provenance is Provenance.MEASURED and eta.p50 == 100.0


def test_select_eta_falls_back_to_prior():
    # fraction 0.0 ⇒ linear not estimable ⇒ prior fallback
    eta = st.select_eta(fraction=0.0, elapsed_s=100.0, prior_duration_s=300.0)
    assert eta.provenance is Provenance.PRIOR


def test_select_eta_prior_requires_elapsed():
    eta = st.select_eta(fraction=None, elapsed_s=None, prior_duration_s=300.0)
    assert not eta.estimable and eta.provenance is Provenance.NONE


def test_select_eta_prior_not_estimable():
    eta = st.select_eta(fraction=None, elapsed_s=100.0, prior_duration_s=-5.0)
    assert not eta.estimable


def test_select_eta_none_when_nothing_known():
    eta = st.select_eta(fraction=0.0, elapsed_s=100.0, prior_duration_s=None)
    assert not eta.estimable


# ── detect_failed ──────────────────────────────────────────────────────────────


def test_detect_failed_true():
    poll = PollResult(exists=True, mtime=None, raw={"status": "FAILED"})
    assert st.detect_failed(poll) is True


def test_detect_failed_non_string_status():
    poll = PollResult(exists=True, mtime=None, raw={"status": 500})
    assert st.detect_failed(poll) is False


def test_detect_failed_benign_status():
    poll = PollResult(exists=True, mtime=None, raw={"status": "running"})
    assert st.detect_failed(poll) is False


# ── assemble_view ──────────────────────────────────────────────────────────────


def test_assemble_view_running():
    spec = TaskSpec(id="t", adapter="local-file-tail", parser="generic-logfile")
    poll = PollResult(exists=True, mtime=10.0, lines=["a", "b"], liveness=True)
    view = st.assemble_view(
        spec,
        poll,
        _reading(),
        progressing=True,
        stalled=False,
        elapsed_s=100.0,
        prior_duration_s=None,
    )
    assert view.status is TaskStatus.RUNNING
    assert view.fraction == 0.5
    assert view.lines_seen == 2
    assert view.eta.estimable


def test_assemble_view_blind_suppresses_flags():
    spec = TaskSpec(id="t", adapter="http-json")
    poll = PollResult(exists=False, mtime=None, liveness=False, error="boom")
    view = st.assemble_view(
        spec,
        poll,
        _reading(done=None, total=None, terminal=False),
        progressing=True,
        stalled=True,
        elapsed_s=None,
        prior_duration_s=None,
        blind_age=42.0,
    )
    assert view.status is TaskStatus.BLIND
    assert view.blind is True
    assert view.progressing is False  # suppressed while blind
    assert view.stalled is False  # suppressed while blind
    assert view.blind_age == 42.0


def test_task_view_to_dict_roundtrips_fields():
    spec = TaskSpec(
        id="t", adapter="process-pid", parser="", notify=["terminal", "stall"]
    )
    poll = PollResult(exists=True, mtime=5.0, liveness=True)
    view = st.assemble_view(
        spec,
        poll,
        _reading(terminal=True),
        progressing=False,
        stalled=False,
        elapsed_s=None,
        prior_duration_s=None,
    )
    data = view.to_dict()
    assert data["status"] == "done"
    assert data["notify"] == ["terminal", "stall"]
    assert data["eta"]["estimable"] is False
    assert data["exists"] is True
