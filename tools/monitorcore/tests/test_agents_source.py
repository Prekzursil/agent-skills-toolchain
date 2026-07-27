"""Tests for ``monitorcore.agents_source`` — the subagent adapter, 100% line+branch.

Hermetic by construction: the "live" path drives the REAL
:func:`monitorcore.discovery.scan` against a transcript tree built in ``tmp_path`` from the
committed fixture, and every other path uses an injected ``scan_fn`` / ``pick_fn`` / clock.
Nothing touches ``~/.claude``, the network, or a terminal.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from monitorcore.agents_source import (
    UNGROUPED_WF,
    AgentRow,
    AgentsPayload,
    AgentsSource,
    _counts,
    row_from_scan,
    workflow_key,
)
from monitorcore.contract import MonitorSource, SourceState
from monitorcore.render_html import render_html
from monitorcore.render_md import render_md

NOW = 1_784_283_000.0
FIXTURES = Path(__file__).parent / "fixtures"


def _row(**kw: object) -> AgentRow:
    base: dict[str, object] = {
        "name": "a",
        "agent_type": "general-purpose",
        "desc": "",
        "wf": "",
        "bucket": "idle",
        "age_s": 1.0,
        "running": False,
        "size": 10,
        "last": "",
        "path": "p",
    }
    base.update(kw)
    return AgentRow(**base)


def _scan_row(**kw: object) -> dict[str, object]:
    base: dict[str, object] = {
        "jsonl": "/x/agent-1.jsonl",
        "name": "scout",
        "type": "general-purpose",
        "desc": "read the plan",
        "wf": "",
        "size": 120,
        "age": 4.0,
        "running": True,
        "last": "📝 reading",
    }
    base.update(kw)
    return base


def _source(rows: list[dict[str, object]]) -> AgentsSource:
    return AgentsSource(
        subdir="/fake",
        scan_fn=lambda *_a, **_k: rows,
        exists_fn=lambda _p: True,
        clock=lambda: NOW,
    )


def _subagents_tree(tmp_path: Path) -> Path:
    """A real ``subagents/`` tree: one flat Task agent + one workflow-owned agent."""
    root = tmp_path / "subagents"
    (root / "workflows" / "wf_0001").mkdir(parents=True)
    targets = (
        root / "agent-deadbeef.jsonl",
        root / "workflows" / "wf_0001" / "agent-cafe0001.jsonl",
    )
    for target in targets:
        shutil.copy(FIXTURES / "agent-deadbeef.jsonl", target)
        shutil.copy(
            FIXTURES / "agent-deadbeef.meta.json",
            target.parent / f"{target.stem}.meta.json",
        )
    return root


# ───────────────────────────── row_from_scan ─────────────────────────────
def test_row_from_scan_scrubs_every_field_and_buckets_a_running_agent():
    row = row_from_scan(_scan_row(name="ev\x1bil", desc="d\x07e"))
    assert row.bucket == "running"
    assert "\x1b" not in row.name and "\x07" not in row.desc
    assert row.age_s == 4.0 and row.size == 120


def test_row_from_scan_buckets_an_errored_tail_via_the_existing_bucket_agent():
    assert row_from_scan(_scan_row(last="✗ boom")).bucket == "error"


def test_row_from_scan_buckets_a_quiet_agent_as_idle():
    assert row_from_scan(_scan_row(running=False, last="")).bucket == "idle"


def test_row_from_scan_defaults_missing_and_mistyped_fields_without_raising():
    row = row_from_scan({})
    assert row.name == "" and row.age_s == 0.0 and row.size == 0
    mistyped = row_from_scan(_scan_row(age="soon", size="big"))
    assert mistyped.age_s == 0.0 and mistyped.size == 0


def test_row_from_scan_accepts_an_int_age():
    assert row_from_scan(_scan_row(age=9)).age_s == 9.0


# ───────────────────────────── workflow_key ─────────────────────────────
def test_workflow_key_buckets_a_flat_task_agent():
    assert workflow_key(_row(wf="")) == UNGROUPED_WF
    assert workflow_key(_row(wf="wf_7")) == "wf_7"


# ───────────────────────────── poll ─────────────────────────────
def test_poll_over_a_real_transcript_tree_finds_both_agents(tmp_path: Path):
    root = _subagents_tree(tmp_path)
    snap = AgentsSource(subdir=str(root), clock=lambda: NOW).poll()
    assert snap.reachable is True and snap.stale is False
    assert len(snap.payload.rows) == 2
    assert {workflow_key(r) for r in snap.payload.rows} == {UNGROUPED_WF, "wf_0001"}
    assert snap.payload.root.endswith("subagents")
    # ``now`` is injected, so the ages are deterministic rather than wall-clock.
    assert snap.age_s is not None


def test_poll_reports_running_and_error_states():
    running = _source([_scan_row(running=True)]).poll()
    assert running.state is SourceState.RUNNING

    errored = _source([_scan_row(last="✗ nope")]).poll()
    assert errored.state is SourceState.ERROR
    assert "1 error" in errored.headline

    quiet = _source([_scan_row(running=False)]).poll()
    assert quiet.state is SourceState.IDLE


def test_poll_with_no_rows_reports_an_unmeasured_age_not_zero():
    snap = _source([]).poll()
    assert snap.payload.rows == ()
    assert snap.age_s is None


def test_poll_without_a_subdir_uses_the_injected_picker():
    src = AgentsSource(
        scan_fn=lambda *_a, **_k: [_scan_row()],
        pick_fn=lambda _p: "/d",
        exists_fn=lambda _p: True,
        clock=lambda: NOW,
    )
    assert src.poll().payload.root == "/d"


def test_poll_is_unreachable_when_no_transcripts_exist_anywhere():
    src = AgentsSource(pick_fn=lambda _p: None, clock=lambda: NOW)
    snap = src.poll()
    assert snap.reachable is False and snap.stale is True
    assert snap.state is SourceState.UNREACHABLE
    assert snap.payload == AgentsPayload()
    assert snap.error == "no subagent transcripts found"


def test_poll_never_raises_and_retains_the_last_good_payload():
    calls = {"n": 0}

    def _flaky(*_a: object, **_k: object) -> list[dict[str, object]]:
        calls["n"] += 1
        if calls["n"] == 1:
            return [_scan_row(name="kept")]
        raise OSError("disk gone\x1b[2J")

    src = AgentsSource(
        subdir="/fake", scan_fn=_flaky, exists_fn=lambda _p: True, clock=lambda: NOW
    )
    good = src.poll()
    bad = src.poll()
    assert good.payload.rows[0].name == "kept"
    assert bad.reachable is False and bad.payload is good.payload
    assert bad.error is not None and "\x1b" not in bad.error


# ───────────────────────────── contract surface ─────────────────────────────
def test_agents_source_satisfies_the_monitor_source_protocol():
    assert isinstance(AgentsSource(), MonitorSource)


def test_render_native_falls_back_to_the_headline_when_empty():
    src = _source([])
    snap = src.poll()
    assert src.render_native(snap) == snap.headline


def test_render_native_lists_the_rows():
    src = _source([_scan_row(name="scout")])
    text = src.render_native(src.poll())
    assert isinstance(text, str) and "scout" in text


def test_export_model_carries_one_card_per_agent():
    src = _source(
        [_scan_row(name="scout"), _scan_row(name="dead", running=False, wf="wf_9")]
    )
    doc = src.export_model(src.poll())
    assert doc.title == "agents"
    assert [b.title for b in doc.blocks] == ["scout", "dead"]  # pyright: ignore[reportAttributeAccessIssue]
    assert [b.badge for b in doc.blocks] == ["running", "idle"]  # pyright: ignore[reportAttributeAccessIssue]
    assert doc.generated_at.startswith("2026-")


def test_export_model_leaves_the_agent_shaped_rollup_EMPTY():
    """Neither ``done`` nor ``tokens`` is measured here, so no rollup line is honest."""
    src = _source([_scan_row()])
    assert src.export_model(src.poll()).rollup == ()


@pytest.mark.parametrize("render", [render_md, render_html])
def test_export_model_round_trips_through_the_shared_renderers(render: object):
    """The gate the previous rollup missed: ``export(doc, "md")`` KeyError'd on ``done``.

    Asserting on ``dict(doc.rollup)["total"]`` never touched a renderer, so a rollup that
    omitted two REQUIRED keys passed 100% coverage and still crashed the live export path.
    """
    src = _source([_scan_row(name="scout"), _scan_row(name="dead", running=False)])
    out = render(src.export_model(src.poll()))  # pyright: ignore[reportCallIssue]
    assert isinstance(out, str) and "scout" in out


def test_headline_is_the_poll_time_one_liner():
    src = _source([_scan_row()])
    snap = src.poll()
    assert src.headline(snap) == snap.headline
    assert "in 1 workflows" in snap.headline


def test_alert_classifies_error_unreachable_and_healthy():
    src = _source([_scan_row(last="✗ boom")])
    critical = src.alert(src.poll())
    assert critical is not None and critical.level == "critical"

    unreachable = AgentsSource(pick_fn=lambda _p: None, clock=lambda: NOW)
    warn = unreachable.alert(unreachable.poll())
    assert warn is not None and warn.level == "warn"

    healthy = _source([_scan_row(running=False)])
    assert healthy.alert(healthy.poll()) is None


def test_an_unexpected_bucket_still_tallies_without_a_keyerror():
    """``done`` is unreachable today but IS in ``bucket_agent``'s vocabulary — tolerate it."""
    assert _counts([_row(bucket="mystery"), _row(bucket="done")]) == {
        "running": 0,
        "idle": 0,
        "error": 0,
        "mystery": 1,
        "done": 1,
    }


# ─────────────────────── absent vs empty (an unmeasured source) ───────────────────────
def test_an_ABSENT_subagents_dir_is_unreachable_not_an_empty_measured_scan():
    """``scan`` over a missing path returns ``[]`` — indistinguishable from a real idle dir."""
    src = AgentsSource(
        subdir="/nope",
        scan_fn=lambda *_a, **_k: [],
        exists_fn=lambda _p: False,
        clock=lambda: NOW,
    )
    snap = src.poll()
    assert snap.reachable is False and snap.stale is True
    assert snap.state is SourceState.UNREACHABLE
    assert snap.error is not None and "subagents dir not found" in snap.error
    assert snap.payload == AgentsPayload()


def test_an_EMPTY_but_PRESENT_subagents_dir_is_a_measured_zero():
    """The control for the test above: reached-and-empty must stay reachable."""
    snap = _source([]).poll()
    assert snap.reachable is True and snap.state is SourceState.IDLE
    assert snap.payload.rows == ()


def test_the_absent_dir_message_collapses_the_home_path():
    src = AgentsSource(
        subdir=str(Path.home() / "secret" / "subagents"),
        exists_fn=lambda _p: False,
        clock=lambda: NOW,
    )
    assert str(Path.home()) not in (src.poll().error or "")


def test_the_committed_meta_fixture_is_the_one_the_tree_builder_uses():
    meta = json.loads(
        (FIXTURES / "agent-deadbeef.meta.json").read_text(encoding="utf-8")
    )
    assert meta["name"] == "fixture-agent"


@pytest.mark.parametrize("hostile", ["\x1b]0;pwn\x07", "\x9b2J", "a\x00b"])
def test_no_control_byte_survives_ingest(hostile: str):
    row = row_from_scan(_scan_row(name=hostile, last=hostile, desc=hostile, wf=hostile))
    joined = row.name + row.last + row.desc + row.wf
    assert not any(ch in joined for ch in ("\x1b", "\x07", "\x9b", "\x00"))
