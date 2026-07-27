"""Both-states acceptance for :mod:`monitorcore.health_source`.

Every case below pairs a KNOWN-GOOD fixture with a KNOWN-BROKEN one. A detector that is silent
in both states measures nothing, so each broken case asserts the adapter actually FIRES — most
importantly ``test_dead_feed_is_stalled_not_healthy``, which is the whole reason this source
exists: a readable file is not a live feed, and a frozen last-good frame must never render as a
healthy machine.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from monitorcore.contract import MonitorSource, SourceState
from monitorcore.health_source import SystemHealthSource
from monitorcore.render_html import render_html
from monitorcore.render_md import render_md


def _sample(
    *,
    band: str = "green",
    driver: str = "",
    phys: float = 40.0,
    commit: float = 30.0,
    procs: int = 400,
    gdi_max: int = 500,
    orphans: int = 0,
    age_s: float = 0.0,
) -> dict[str, object]:
    ts = time.time() - age_s
    return {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(ts)) + "Z",
        "band": band,
        "driver": driver,
        "commit": {"limit_mb": 179165, "used_mb": 50000, "pct": commit},
        "phys": {"total_mb": 32390, "used_mb": 13000, "pct": phys},
        "proc": {"count": procs, "handles": 400000, "threads": 9000},
        "gui": {
            "sampled": True,
            "gdi_total": 18000,
            "usr_total": 7000,
            "gdi_max": gdi_max,
            "gdi_max_proc": "Taskmgr:104908",
            "usr_max": 1200,
        },
        "census": {"node": 108, "python": 203},
        "orphans": {
            "count": orphans,
            "top": [{"pid": 16636, "name": "node.exe", "ppid": 17008, "rss_mb": 2}]
            if orphans
            else [],
        },
    }


def _write(tmp_path: Path, *samples: dict[str, object], trailing: str = "") -> Path:
    p = tmp_path / "events.ndjson"
    body = "".join(json.dumps(s) + "\n" for s in samples) + trailing
    p.write_text(body, encoding="utf-8")
    return p


def _src(path: Path, **kw: object) -> SystemHealthSource:
    return SystemHealthSource(path, **kw)  # type: ignore[arg-type]


# --- contract conformance ---------------------------------------------------------------


def test_satisfies_monitorsource_protocol(tmp_path: Path) -> None:
    assert isinstance(_src(_write(tmp_path, _sample())), MonitorSource)


# --- known-good -------------------------------------------------------------------------


def test_healthy_sample_is_idle_and_fresh(tmp_path: Path) -> None:
    snap = _src(_write(tmp_path, _sample())).poll()
    assert snap.state is SourceState.IDLE
    assert snap.reachable is True
    assert snap.stale is False
    assert snap.error is None


def test_healthy_sample_raises_no_alert(tmp_path: Path) -> None:
    src = _src(_write(tmp_path, _sample()))
    assert src.alert(src.poll()) is None


# --- known-broken: the dead-man rule (the case this source exists for) -------------------


def test_dead_feed_is_stalled_not_healthy(tmp_path: Path) -> None:
    """Sentinel died: the file still parses green, but the row must NOT read healthy."""
    path = _write(tmp_path, _sample(band="green", age_s=600))
    snap = _src(path, dead_man_s=45.0).poll()
    assert snap.state is SourceState.STALLED, "a dead feed rendered as a live state"
    assert snap.stale is True
    assert snap.age_s is not None and snap.age_s > 45
    assert "DEAD" in snap.headline


def test_dead_feed_alerts_critical(tmp_path: Path) -> None:
    src = _src(_write(tmp_path, _sample(band="green", age_s=600)), dead_man_s=45.0)
    alert = src.alert(src.poll())
    assert alert is not None and alert.level == "critical"


def test_fresh_feed_just_inside_window_is_not_stalled(tmp_path: Path) -> None:
    """The negative control for the dead-man: it must NOT fire on an ordinary slow tick."""
    snap = _src(_write(tmp_path, _sample(age_s=20)), dead_man_s=45.0).poll()
    assert snap.state is not SourceState.STALLED
    assert snap.stale is False


@pytest.mark.parametrize(
    ("age_s", "expect_stalled"),
    [(40.0, False), (44.0, False), (46.0, True), (50.0, True)],
)
def test_dead_man_boundary(tmp_path: Path, age_s: float, expect_stalled: bool) -> None:
    """The BOUNDARY, not just the extremes.

    Found in production 2026-07-21: the sentinel was killed and, polled 37.4s later, the adapter
    reported ``running`` / no alert / not stale. That is correct against ``dead_man_s=45`` — but
    the suite only covered 20s (inside) and 600s (far outside), so nothing pinned the transition
    and the in-window silence read as a defect at first glance. A window that tolerates a slow
    tick is inherently a window in which a dead feed still looks alive; the measured worst tick
    was 11.90s, so 45s is ~3.8x headroom. That blind interval is a DESIGN COST, not a bug, and
    the mitigation is a supervisor that restarts the sentinel -- the dead-man is the backstop,
    never the primary recovery.
    """
    snap = _src(_write(tmp_path, _sample(age_s=age_s)), dead_man_s=45.0).poll()
    assert (snap.state is SourceState.STALLED) is expect_stalled
    assert snap.stale is expect_stalled


# --- known-broken: truncated final line --------------------------------------------------


def test_truncated_final_line_falls_back_to_previous(tmp_path: Path) -> None:
    """A live tail WILL catch a half-written line; it must not crash or mis-parse."""
    path = _write(
        tmp_path, _sample(band="green"), trailing='{"ts":"2026-07-21T00:00:00Z","ba'
    )
    snap = _src(path).poll()
    assert snap.reachable is True
    assert snap.payload.band == "green"
    assert snap.state is SourceState.IDLE


def test_only_a_truncated_line_is_unreachable_not_a_guess(tmp_path: Path) -> None:
    path = tmp_path / "events.ndjson"
    path.write_text('{"ts":"2026-07-21T00:00:00Z","ba', encoding="utf-8")
    snap = _src(path).poll()
    assert snap.state is SourceState.UNREACHABLE


# --- known-broken: missing feed ----------------------------------------------------------


def test_missing_file_is_unreachable(tmp_path: Path) -> None:
    snap = _src(tmp_path / "nope.ndjson").poll()
    assert snap.state is SourceState.UNREACHABLE
    assert snap.reachable is False
    assert snap.error is not None


def test_poll_never_raises_on_a_directory(tmp_path: Path) -> None:
    """poll() MUST NOT raise — contract's cardinal rule."""
    d = tmp_path / "adir"
    d.mkdir()
    snap = _src(d).poll()  # opening a directory raises inside; must be swallowed
    assert snap.state is SourceState.UNREACHABLE


# --- the regression that motivated the whole source --------------------------------------


def test_low_commit_high_physical_is_not_green(tmp_path: Path) -> None:
    """THE memguard defect, as a test.

    Measured 2026-07-21: commit 57.1% (memguard band OK) while physical was 96.4%. A
    commit-only detector reported healthy. The sentinel bands each signal independently, so
    this sample arrives already banded red — the adapter must carry that through as ERROR
    rather than re-deriving health from commit.
    """
    snap = _src(
        _write(
            tmp_path, _sample(band="red", driver="phys=96.4", commit=57.1, phys=96.4)
        )
    ).poll()
    assert snap.state is SourceState.ERROR
    assert snap.payload.commit_pct == pytest.approx(57.1)
    assert snap.payload.phys_pct == pytest.approx(96.4)


def test_red_band_alerts_critical_and_names_driver(tmp_path: Path) -> None:
    src = _src(_write(tmp_path, _sample(band="red", driver="phys=96.4", phys=96.4)))
    alert = src.alert(src.poll())
    assert alert is not None
    assert alert.level == "critical"
    assert "phys=96.4" in alert.headline


def test_yellow_band_is_running_and_warns_only_at_orange(tmp_path: Path) -> None:
    src_y = _src(_write(tmp_path, _sample(band="yellow")))
    snap_y = src_y.poll()
    assert snap_y.state is SourceState.RUNNING
    assert src_y.alert(snap_y) is None, (
        "yellow must not alert; orange is the first alerting band"
    )


def test_orange_band_alerts_at_warn_not_critical(tmp_path: Path) -> None:
    """The band the docstring calls "the first alerting band" — and the only ``warn`` producer.

    ``level`` is chosen by a conditional EXPRESSION (``"critical" if rank >= 3 else "warn"``),
    which coverage.py does not count as a branch, so the 100% figure does NOT imply this path
    ran. Only an explicit orange case pins it.
    """
    src = _src(_write(tmp_path, _sample(band="orange", driver="commit=88")))
    snap = src.poll()
    assert snap.state is SourceState.ERROR
    alert = src.alert(snap)
    assert alert is not None
    assert alert.level == "warn", "orange must warn, not escalate to critical"


def test_unknown_band_is_treated_as_healthy_not_alerting(tmp_path: Path) -> None:
    """An unrecognised future band degrades to rank 0 rather than raising inside poll()."""
    src = _src(_write(tmp_path, _sample(band="chartreuse")))
    snap = src.poll()
    assert snap.state is SourceState.IDLE
    assert src.alert(snap) is None


def test_gdi_pin_surfaces_in_headline(tmp_path: Path) -> None:
    """The Taskmgr 9999/10000 finding must be visible, not buried in the payload."""
    snap = _src(_write(tmp_path, _sample(band="red", gdi_max=9999))).poll()
    assert "9999" in snap.headline and "Taskmgr" in snap.headline


def test_orphan_count_surfaces(tmp_path: Path) -> None:
    snap = _src(_write(tmp_path, _sample(orphans=1))).poll()
    assert snap.payload.orphan_count == 1
    assert snap.payload.orphan_top and "node.exe" in snap.payload.orphan_top[0]
    assert "orphan" in snap.headline


# --- newest-wins ordering -----------------------------------------------------------------


def test_newest_sample_wins(tmp_path: Path) -> None:
    path = _write(
        tmp_path, _sample(band="green", age_s=120), _sample(band="red", phys=96.4)
    )
    snap = _src(path).poll()
    assert snap.payload.band == "red", (
        "adapter read an older sample than the newest available"
    )


def test_export_model_includes_driver_and_orphans(tmp_path: Path) -> None:
    src = _src(_write(tmp_path, _sample(band="red", driver="phys=96.4", orphans=1)))
    doc = src.export_model(src.poll())
    section = doc.blocks[0]
    kv = dict(section.children[0].pairs)  # type: ignore[union-attr]
    assert kv["driver"] == "phys=96.4"
    assert kv["orphaned MCP runtimes"] == "1"
    assert section.badge == "red"
    assert doc.active is True, "a red board must mark the doc active"


def test_export_model_is_deterministic_for_a_given_snapshot(tmp_path: Path) -> None:
    """generated_at derives from snap.ts, not wall-clock — golden exports must be stable."""
    src = _src(_write(tmp_path, _sample()))
    snap = src.poll()
    assert src.export_model(snap).generated_at == src.export_model(snap).generated_at


# --- escape-injection: a sample is UNTRUSTED INPUT ----------------------------------------
#
# Reproduced against this adapter before the scrub floor was added: the sentinel feed is a
# user-writable file and its fields carry OS-supplied strings, so a crafted sample painted a
# raw OSC sequence (ESC ] 0 ; … BEL) straight onto the operator's terminal through the
# headline. Each case below pins ONE sink; together they are the both-states proof that the
# floor is applied in the RENDER path and not merely unit-tested in redact.py.

HOSTILE = "\x1b]0;pwn\x07"
CONTROL_BYTES = ("\x1b", "\x07", "\x9b", "\x00")


def _hostile_sample() -> dict[str, object]:
    s = _sample(band="red", driver=HOSTILE, gdi_max=9999, orphans=1)
    gui = s["gui"]
    assert isinstance(gui, dict)
    gui["gdi_max_proc"] = HOSTILE
    s["census"] = {"ev\x1b[2Jil": 3}
    s["orphans"] = {
        "count": 1,
        "top": [{"pid": 1, "name": HOSTILE, "ppid": 2, "rss_mb": 3}],
    }
    return s


def _assert_inert(text: str) -> None:
    assert not any(c in text for c in CONTROL_BYTES), (
        f"escape byte survived to a frame: {text!r}"
    )


def test_no_escape_byte_in_payload_fields(tmp_path: Path) -> None:
    p = _src(_write(tmp_path, _hostile_sample())).poll().payload
    _assert_inert(p.band)
    _assert_inert(p.driver)
    _assert_inert(p.gdi_max_proc or "")
    _assert_inert(p.orphan_top[0])
    _assert_inert(p.census[0][0])


def test_no_escape_byte_in_headline_or_alert(tmp_path: Path) -> None:
    """The live (non-stalled) headline is the sink that actually reaches the terminal."""
    src = _src(_write(tmp_path, _hostile_sample()))
    snap = src.poll()
    assert snap.state is SourceState.ERROR, (
        "fixture must exercise the LIVE headline path"
    )
    _assert_inert(snap.headline)
    _assert_inert(src.headline(snap))
    alert = src.alert(snap)
    assert alert is not None
    _assert_inert(alert.headline)
    _assert_inert(alert.detail)


def test_no_escape_byte_in_export_model(tmp_path: Path) -> None:
    src = _src(_write(tmp_path, _hostile_sample()))
    doc = src.export_model(src.poll())
    _assert_inert(doc.title)
    _assert_inert(doc.subtitle)
    _assert_inert(repr(doc.blocks[0].children))


def test_no_escape_byte_in_degraded_error(tmp_path: Path) -> None:
    """An OSError message is attacker-influenceable too — it can quote the path."""
    snap = _src(tmp_path / f"no{HOSTILE}such.ndjson").poll()
    _assert_inert(snap.headline)
    assert snap.error is not None
    _assert_inert(snap.error)


def test_control_strip_has_no_off_switch(tmp_path: Path) -> None:
    """``redact_enabled=False`` may disable SECRET masking, never the control-byte strip.

    An off switch shared between the two would let a caller re-open the terminal-injection
    hole while only intending to see unmasked paths, so the two are deliberately split.
    """
    src = _src(_write(tmp_path, _hostile_sample()), redact_enabled=False)
    snap = src.poll()
    _assert_inert(snap.headline)
    _assert_inert(snap.payload.driver)


def test_dead_feed_headline_is_inert(tmp_path: Path) -> None:
    """The STALLED headline interpolates the last band — pin that path too."""
    s = _hostile_sample()
    s["band"] = HOSTILE
    snap = _src(_write(tmp_path, s), dead_man_s=0.0).poll()
    assert snap.state is SourceState.STALLED
    _assert_inert(snap.headline)


# --- the export must survive the SHARED renderers ------------------------------------------


def test_export_model_does_not_emit_work_queue_rollup_keys(tmp_path: Path) -> None:
    """``rollup`` is not an open mapping — a domain-keyed one takes the whole export down.

    ``render_md._rollup_line`` and ``render_html`` index total/done/error/running/idle/tokens
    DIRECTLY. An earlier revision of this adapter emitted ``(processes, handles, threads,
    orphans)``, which raised ``KeyError: 'total'`` in Markdown and ``KeyError: 'running'`` in
    HTML — i.e. the export path was unusable. An empty rollup is the only correct value for a
    non-queue source (matching ``McpSource``); the counts live in the KV block instead.
    """
    src = _src(_write(tmp_path, _sample(band="red", orphans=1)))
    assert src.export_model(src.poll()).rollup == ()


def test_export_model_is_not_a_work_unit_card(tmp_path: Path) -> None:
    """``card=True`` would silently DROP every KV and Table in this section.

    A card is the work-unit ENTITY renderer — it emits model/tokens/tool-calls/task/output and
    never reads ``children``. An earlier revision set it, so the export rendered an empty
    "0 tokens - 0 tool calls" shell with the whole payload missing, in BOTH renderers.
    """
    src = _src(_write(tmp_path, _sample(band="red", orphans=1)))
    doc = src.export_model(src.poll())
    assert doc.blocks[0].card is False, (
        "a card drops the generic children this source emits"
    )


@pytest.mark.parametrize("render", [render_md, render_html])
def test_export_model_content_survives_the_shared_renderers(
    tmp_path: Path, render: object
) -> None:
    """End-to-end: the payload must actually appear in the rendered frame, not just the doc."""
    src = _src(_write(tmp_path, _sample(band="red", driver="phys=96.4", orphans=1)))
    out = render(src.export_model(src.poll()))  # type: ignore[operator]
    for probe in ("processes", "orphaned MCP runtimes", "node.exe", "phys=96.4"):
        assert probe in out, f"{probe!r} was dropped on the way to the rendered frame"


# --- coverage of the remaining degrade paths ------------------------------------------------


def test_non_string_timestamp_degrades_to_no_age(tmp_path: Path) -> None:
    s = _sample()
    s["ts"] = 12345  # a number, not an ISO-8601 string
    snap = _src(_write(tmp_path, s)).poll()
    assert snap.payload.sample_ts == 0.0
    assert snap.age_s is None, (
        "an unparseable ts must not fabricate a freshness reading"
    )


def test_unparseable_timestamp_degrades_to_no_age(tmp_path: Path) -> None:
    s = _sample()
    s["ts"] = "not-a-date"
    snap = _src(_write(tmp_path, s)).poll()
    assert snap.payload.sample_ts == 0.0
    assert snap.age_s is None


def test_blank_trailing_lines_are_skipped(tmp_path: Path) -> None:
    snap = _src(_write(tmp_path, _sample(band="red"), trailing="\n   \n")).poll()
    assert snap.payload.band == "red"


def test_non_object_json_line_falls_back_to_previous(tmp_path: Path) -> None:
    """A line that parses but is not an object must be skipped, not coerced."""
    path = _write(tmp_path, _sample(band="red"), trailing="[1, 2, 3]\n")
    snap = _src(path).poll()
    assert snap.payload.band == "red"


def test_non_list_orphan_top_is_ignored(tmp_path: Path) -> None:
    s = _sample()
    s["orphans"] = {"count": 2, "top": "not-a-list"}
    snap = _src(_write(tmp_path, s)).poll()
    assert snap.payload.orphan_count == 2
    assert snap.payload.orphan_top == ()


def test_headline_and_render_native_expose_the_snapshot(tmp_path: Path) -> None:
    src = _src(_write(tmp_path, _sample()))
    snap = src.poll()
    assert src.headline(snap) == snap.headline
    assert src.render_native(snap) is snap.payload


def test_export_model_of_an_unreachable_snapshot_carries_the_error(
    tmp_path: Path,
) -> None:
    """No sample yet: no census block, and the error must be stated rather than dropped."""
    src = _src(tmp_path / "nope.ndjson")
    doc = src.export_model(src.poll())
    section = doc.blocks[0]
    assert doc.rollup == ()
    texts = [getattr(c, "text", "") for c in section.children]
    assert any(t.startswith("error: ") for t in texts)
