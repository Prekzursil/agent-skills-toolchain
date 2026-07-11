"""Tests for ui/render.py — pure render-string builders (100% branch)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.models import EtaEstimate, Provenance, TaskSpec, TaskStatus  # noqa: E402
from cli.status import TaskView  # noqa: E402
from ui import render  # noqa: E402


def _eta(p50=None, p90=None, prov=Provenance.NONE) -> EtaEstimate:
    return EtaEstimate(p50=p50, p90=p90, provenance=prov)


def _view(**over: object) -> TaskView:
    base: dict[str, object] = {
        "id": "t1",
        "adapter": "local-file-tail",
        "parser": "generic-logfile",
        "status": TaskStatus.RUNNING,
        "exists": True,
        "done": 4.0,
        "total": 8.0,
        "fraction": 0.5,
        "phase": "complex leg",
        "gpu": "GPU 0 98%",
        "terminal": False,
        "eta": _eta(100.0, 150.0, Provenance.MEASURED),
        "progressing": True,
        "stalled": False,
        "blind": False,
        "blind_age": None,
        "elapsed_s": 100.0,
        "error": None,
        "detail": "complex leg · GPU 0 98%",
    }
    base.update(over)
    return TaskView(**base)  # type: ignore[arg-type]


# ── status_badge ──────────────────────────────────────────────────────────────


def test_status_badge_covers_all_statuses():
    for status in TaskStatus:
        assert render.status_badge(status), f"missing badge for {status}"


# ── format_duration ───────────────────────────────────────────────────────────


def test_format_duration_none():
    assert render.format_duration(None) == "—"


def test_format_duration_seconds_only():
    assert render.format_duration(45.4) == "45s"


def test_format_duration_minutes():
    assert render.format_duration(200.0) == "3m20s"


def test_format_duration_hours():
    assert render.format_duration(3720.0) == "1h02m"


# ── format_eta ─────────────────────────────────────────────────────────────────


def test_format_eta_not_estimable():
    assert render.format_eta(_eta()) == "eta —"


def test_format_eta_estimable():
    out = render.format_eta(_eta(100.0, 150.0, Provenance.MEASURED))
    assert "p50 1m40s" in out and "p90 2m30s" in out and "[measured]" in out


# ── render_bar ─────────────────────────────────────────────────────────────────


def test_render_bar_unknown_total():
    bar = render.render_bar(None)
    assert "--%" in bar and "·" in bar


def test_render_bar_normal():
    bar = render.render_bar(0.5, width=10)
    assert bar == "[█████     ] 50%"


def test_render_bar_overshoot_marks_and_fills():
    bar = render.render_bar(1.25, width=10)
    assert bar.startswith("[██████████]") and bar.endswith("125%!")


# ── render_sparkline ───────────────────────────────────────────────────────────


def test_render_sparkline_empty():
    assert render.render_sparkline([]) == ""


def test_render_sparkline_flat_series_is_mid_block():
    out = render.render_sparkline([5.0, 5.0, 5.0])
    assert out == "▅▅▅"


def test_render_sparkline_scaled():
    out = render.render_sparkline([0.0, 100.0])
    assert out[0] == "▁" and out[-1] == "█"


# ── parse_gpu_percent ──────────────────────────────────────────────────────────


def test_parse_gpu_percent_found():
    assert render.parse_gpu_percent("0: 98%, mem 40%") == 98.0


def test_parse_gpu_percent_absent():
    assert render.parse_gpu_percent("no numbers here") is None


# ── render_gpu / render_stall_flag ─────────────────────────────────────────────


def test_render_gpu_present():
    assert render.render_gpu("GPU 0 98%") == "GPU 0 98%"


def test_render_gpu_empty():
    assert render.render_gpu("") == "—"


def test_render_stall_flag_true():
    assert render.render_stall_flag(_view(stalled=True)) == "STALL"


def test_render_stall_flag_false():
    assert render.render_stall_flag(_view(stalled=False)) == ""


# ── render_progress_cell ───────────────────────────────────────────────────────


def test_render_progress_cell_unknown_and_no_phase():
    cell = render.render_progress_cell(_view(fraction=None, phase=""))
    assert cell == "—  —"


def test_render_progress_cell_frontier_and_phase():
    cell = render.render_progress_cell(_view(fraction=0.5, done=4.0, total=8.0))
    assert cell == "complex leg  4/8"


# ── render_blind_banner ────────────────────────────────────────────────────────


def test_render_blind_banner_none_blind():
    assert render.render_blind_banner([_view(blind=False)]) == ""


def test_render_blind_banner_age_unknown():
    banner = render.render_blind_banner([_view(id="x", blind=True, blind_age=None)])
    assert "x (blind ?)" in banner


def test_render_blind_banner_with_age():
    banner = render.render_blind_banner([_view(id="y", blind=True, blind_age=90.0)])
    assert "y (blind 1m30s)" in banner


# ── render_task_row ────────────────────────────────────────────────────────────


def test_render_task_row_with_gpu_and_stall():
    row = render.render_task_row(_view(gpu="GPU 0 98%", stalled=True))
    assert "gpu GPU 0 98%" in row and "STALL" in row


def test_render_task_row_no_gpu_no_stall():
    row = render.render_task_row(_view(gpu="", stalled=False))
    assert "gpu" not in row and "STALL" not in row


# ── render_status_report ───────────────────────────────────────────────────────


def test_render_status_report_empty():
    assert render.render_status_report([]) == "No tasks registered."


def test_render_status_report_with_banner():
    report = render.render_status_report([_view(blind=True, blind_age=10.0)])
    assert "BLIND — holding" in report and "TASKWATCH" in report


def test_render_status_report_without_banner():
    report = render.render_status_report([_view(blind=False)])
    assert "BLIND —" not in report and "▶ RUN" in report


# ── render_registry_table ──────────────────────────────────────────────────────


def test_render_registry_table_empty():
    assert render.render_registry_table([]) == "No tasks registered."


def test_render_registry_table_rows():
    specs = [
        TaskSpec(id="a", adapter="local-file-tail", parser="generic-logfile"),
        TaskSpec(id="b", adapter="process-pid", parser=""),
    ]
    table = render.render_registry_table(specs)
    assert "a" in table and "generic-logfile" in table
    # empty parser renders as an em-dash placeholder
    assert "—" in table
