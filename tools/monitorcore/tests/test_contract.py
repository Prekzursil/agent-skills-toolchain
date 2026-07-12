"""``monitorcore.contract`` — the typed MonitorSource/Snapshot contract.

Structural coverage of the generic contract WITHOUT any concrete adapter (monitorcore
must never depend on wfmon): the coarse :class:`SourceState` enum, the frozen typed
:class:`Snapshot`, the signature-only :class:`Alert`, and the ``runtime_checkable``
:class:`MonitorSource` protocol (a conforming in-test fake is / a bare object is-not an
instance). The poll-never-throws + fixture round-trip behaviour is proven against the real
``WfmonSource`` in the skill's ``tests/test_source.py`` (that adapter carries the poll guard).
"""

from __future__ import annotations

import dataclasses

import pytest

from monitorcore.contract import Alert, MonitorSource, Snapshot, SourceState
from monitorcore.report_doc import ReportDoc


class _FakeSource:
    """A minimal in-test adapter that satisfies :class:`MonitorSource` (typed tuple payload)."""

    id = "fake"

    def poll(self) -> Snapshot[tuple[int, ...]]:
        return Snapshot(
            source_id="fake",
            ts=1.0,
            reachable=True,
            stale=False,
            state=SourceState.RUNNING,
            headline="h",
            payload=(1, 2),
        )

    def render_native(self, snap: Snapshot[tuple[int, ...]]) -> object:
        return snap.headline

    def export_model(self, snap: Snapshot[tuple[int, ...]]) -> ReportDoc:
        return ReportDoc(title="t", generated_at="")

    def headline(self, snap: Snapshot[tuple[int, ...]]) -> str:
        return snap.headline

    def alert(self, snap: Snapshot[tuple[int, ...]]) -> Alert | None:
        return None


class _NotASource:
    """Implements none of the protocol surface."""


# ───────────────────────── SourceState ─────────────────────────
def test_source_state_is_the_coarse_vocabulary():
    assert set(SourceState) == {
        SourceState.IDLE,
        SourceState.RUNNING,
        SourceState.DONE,
        SourceState.ERROR,
        SourceState.UNREACHABLE,
        SourceState.STALLED,
    }


def test_source_state_is_a_plain_string():
    # StrEnum: members compare/format as their bare value (renderers embed them in f-strings)
    assert SourceState.RUNNING == "running"
    assert f"{SourceState.ERROR}" == "error"


# ───────────────────────── Snapshot ─────────────────────────
def test_snapshot_defaults_and_payload_not_flattened():
    snap = Snapshot(
        source_id="s",
        ts=2.0,
        reachable=True,
        stale=False,
        state=SourceState.DONE,
        headline="ok",
        payload=(1, 2),
    )
    assert snap.payload == (1, 2)  # typed payload preserved verbatim, never flattened
    assert snap.age_s is None and snap.error is None  # optional fields default to None


def test_snapshot_optional_fields_set():
    snap = Snapshot(
        source_id="s",
        ts=0.0,
        reachable=False,
        stale=True,
        state=SourceState.UNREACHABLE,
        headline="down",
        payload=None,
        age_s=3.5,
        error="boom",
    )
    assert snap.age_s == 3.5
    assert snap.error == "boom"


def test_snapshot_is_frozen():
    snap = _FakeSource().poll()
    with pytest.raises(dataclasses.FrozenInstanceError):
        snap.headline = "mutated"  # type: ignore[misc]


# ───────────────────────── Alert ─────────────────────────
def test_alert_defaults_and_frozen():
    alert = Alert(source_id="s", level="critical", headline="h")
    assert alert.detail == "" and alert.ts == 0.0
    with pytest.raises(dataclasses.FrozenInstanceError):
        alert.level = "warn"  # type: ignore[misc]


# ───────────────────────── MonitorSource (runtime_checkable) ─────────────────────────
def test_runtime_checkable_isinstance():
    assert isinstance(_FakeSource(), MonitorSource)
    assert not isinstance(_NotASource(), MonitorSource)


def test_fake_source_satisfies_every_protocol_method():
    src = _FakeSource()
    snap = src.poll()
    assert isinstance(snap, Snapshot)
    assert src.headline(snap) == "h"
    assert src.render_native(snap) == "h"
    assert isinstance(src.export_model(snap), ReportDoc)
    assert src.alert(snap) is None
