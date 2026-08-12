"""Tests for ``monitorcore.pane`` — the switchable-pane seam, 100% line+branch.

Everything here is pure: fabricated snapshots and fabricated panes, no source, no clock, no
terminal. The escape-injection assertions live with the concrete panes (``test_pane_views``)
and the whole-board frame (``test_unified``); this module pins the seam's own contracts.
"""

from __future__ import annotations

from monitorcore.contract import Snapshot, SourceState
from monitorcore.pane import (
    CURSOR,
    GUTTER,
    NOT_MEASURED,
    Pane,
    PaneBody,
    PaneCtx,
    PaneId,
    clamp,
    cursor_rows,
    not_measured,
    pane_bar,
    payload_of,
    payload_rows,
    safe,
    snap_is_stale,
    state_badge,
)

NOW = 1_784_283_000.0


class _Payload:
    def __init__(self, **kw: object) -> None:
        for key, value in kw.items():
            setattr(self, key, value)


def _snap(
    payload: object,
    *,
    source_id: str = "src",
    reachable: bool = True,
    stale: bool = False,
    state: SourceState = SourceState.IDLE,
    headline: str = "hello",
    age_s: float | None = 12.0,
    error: str | None = None,
) -> Snapshot[object]:
    return Snapshot(
        source_id=source_id,
        ts=NOW,
        reachable=reachable,
        stale=stale,
        state=state,
        headline=headline,
        payload=payload,
        age_s=age_s,
        error=error,
    )


class _FakePane:
    id: str = "fake"
    title: str = "fake"
    source_id: str = "src"

    def body(self, snap: Snapshot[object] | None, ctx: PaneCtx) -> PaneBody:
        return PaneBody((f"{snap is None}",), 1 + ctx.selected)


# ───────────────────────────── safe ─────────────────────────────
def test_safe_returns_empty_string_for_none_never_the_word_none():
    assert safe(None) == ""


def test_safe_strips_every_control_byte_at_ingest():
    # The ESC introducer, BEL and the 8-bit C1 CSI are DROPPED, which defangs the sequence
    # at the root; the inert ``[2J`` residue is plain text a terminal will never act on.
    out = safe("a\x1b[2Jb\x07c\x9bd")
    assert out == "a[2Jbcd"
    assert not any(ch in out for ch in ("\x1b", "\x07", "\x9b"))


def test_safe_coerces_non_strings():
    assert safe(7) == "7"


def test_safe_also_MASKS_secrets_because_a_pane_is_the_last_mile_for_raw_errors():
    """Sources keep ``Snapshot.error`` RAW "for logs"; the pane is what puts it on screen.

    ``state_badge`` and ``not_measured`` both paint that raw string, so a barrier that only
    stripped control bytes would print a live credential next to an already-masked headline.
    """
    token = "sk-" + "c" * 24
    out = safe(f"auth failed for {token}")
    assert token not in out and "[REDACTED:api-key]" in out


def test_safe_collapses_the_operators_home_path():
    assert safe(r"C:\Users\someone\.dbxmon\events.jsonl").startswith("~")


def test_safe_is_idempotent_over_an_already_scrubbed_field():
    once = safe("plain name")
    assert safe(once) == once


# ───────────────────────────── clamp ─────────────────────────────
def test_clamp_pins_to_zero_when_nothing_is_selectable():
    assert clamp(4, 0) == 0
    assert clamp(4, -1) == 0


def test_clamp_bounds_below_and_above_and_passes_through():
    assert clamp(-3, 5) == 0
    assert clamp(9, 5) == 4
    assert clamp(2, 5) == 2


# ───────────────────────────── cursor_rows ─────────────────────────────
def test_cursor_rows_marks_only_the_selected_row():
    rows = cursor_rows(["a", "b", "c"], PaneCtx(cols=20, now=NOW, selected=1))
    assert rows[0].startswith(GUTTER)
    assert rows[1].startswith(CURSOR)
    assert rows[2].startswith(GUTTER)


def test_cursor_rows_without_a_cursor_uses_the_plain_gutter_everywhere():
    rows = cursor_rows(["a", "b"], PaneCtx(cols=20, now=NOW, selected=0, cursor=False))
    assert [r[:2] for r in rows] == [GUTTER, GUTTER]


def test_cursor_rows_clips_to_the_pane_width_and_strips_escapes():
    (row,) = cursor_rows(
        ["\x1b[31m" + "x" * 40], PaneCtx(cols=12, now=NOW, cursor=False)
    )
    assert len(row) == 12
    assert "\x1b" not in row


def test_cursor_rows_on_an_empty_row_set_is_empty():
    assert cursor_rows([], PaneCtx(cols=20, now=NOW)) == ()


# ───────────────────────────── not_measured ─────────────────────────────
def test_not_measured_without_detail():
    assert not_measured("mcp") == f"mcp: {NOT_MEASURED}"


def test_not_measured_with_a_scrubbed_detail():
    text = not_measured("mcp", "no\x1b[2Jconfig")
    assert text == f"mcp: {NOT_MEASURED} (no[2Jconfig)"
    assert "\x1b" not in text


# ───────────────────────────── payload_rows ─────────────────────────────
def test_payload_rows_on_a_missing_snapshot_is_empty():
    assert payload_rows(None, "rows") == ()


def test_payload_rows_reads_a_tuple_and_a_list_payload():
    assert payload_rows(_snap(_Payload(rows=(1, 2))), "rows") == (1, 2)
    assert payload_rows(_snap(_Payload(rows=[3])), "rows") == (3,)


def test_payload_rows_tolerates_a_payload_without_the_attribute():
    assert payload_rows(_snap(_Payload(other=1)), "rows") == ()
    assert payload_rows(_snap(None), "rows") == ()


def test_payload_rows_tolerates_a_non_sequence_attribute():
    assert payload_rows(_snap(_Payload(rows=42)), "rows") == ()


def test_payload_rows_drops_elements_of_the_WRONG_TYPE_when_a_type_is_declared():
    """A right-shaped container holding wrong rows used to reach the row formatter.

    The container check alone let ``rows=("oops",)`` through, and ``row.bucket`` then raised
    ``AttributeError`` inside the paint path — tearing down the WHOLE board, not one pane.
    """
    assert payload_rows(_snap(_Payload(rows=("oops", 1, 2))), "rows", of=int) == (1, 2)
    assert payload_rows(_snap(_Payload(rows=("oops",))), "rows", of=int) == ()


def test_payload_rows_accepts_a_tuple_of_types():
    got = payload_rows(_snap(_Payload(rows=(1, "a", 2.5))), "rows", of=(int, float))
    assert got == (1, 2.5)


def test_payload_rows_without_a_declared_type_keeps_every_element():
    assert payload_rows(_snap(_Payload(rows=("oops",))), "rows") == ("oops",)


# ───────────────────────────── payload_of (the SCALAR twin) ─────────────────────────────
def test_payload_of_returns_the_payload_when_the_type_matches():
    payload = _Payload(band="green")
    assert payload_of(_snap(payload), _Payload) is payload


def test_payload_of_on_a_missing_snapshot_is_none():
    assert payload_of(None, _Payload) is None


def test_payload_of_on_a_wrong_typed_payload_is_none_rather_than_a_raise():
    """The hole this closes: a pane reading ``.band`` off a str kills the WHOLE board."""
    assert payload_of(_snap("not a payload"), _Payload) is None
    assert payload_of(_snap(None), _Payload) is None


# ───────────────────────────── snap_is_stale ─────────────────────────────
def test_snap_is_stale_reports_the_retained_last_good_flag():
    assert snap_is_stale(_snap(None, stale=True)) is True
    assert snap_is_stale(_snap(None, stale=False)) is False


def test_snap_is_stale_treats_a_missing_snapshot_as_unmeasured_not_stale():
    """Absent is not stale — the caller routes ``None`` to a *not measured* row instead."""
    assert snap_is_stale(None) is False


# ───────────────────────────── state_badge ─────────────────────────────
def test_state_badge_for_an_unregistered_source_says_not_measured():
    text = state_badge(None, source_id="mcp")
    assert text == f"mcp: {NOT_MEASURED} (no source registered)"


def test_state_badge_renders_age_and_headline():
    text = state_badge(_snap(_Payload()), source_id="src")
    assert "src [idle]" in text
    assert "age=12s" in text
    assert "hello" in text
    assert "[unreachable" not in text


def test_state_badge_unmeasured_age_is_a_dash_not_zero():
    text = state_badge(_snap(_Payload(), age_s=None), source_id="src")
    assert "age=-" in text
    assert "age=0s" not in text


def test_state_badge_flags_unreachable_and_stale_together_with_the_error():
    text = state_badge(
        _snap(
            _Payload(),
            reachable=False,
            stale=True,
            state=SourceState.UNREACHABLE,
            error="boom\x1b[2J",
        ),
        source_id="src",
    )
    assert "[unreachable stale]" in text
    assert "err=boom" in text
    assert "\x1b" not in text


def test_state_badge_flags_stale_alone():
    text = state_badge(_snap(_Payload(), stale=True), source_id="src")
    assert "[stale]" in text


# ───────────────────────────── pane_bar ─────────────────────────────
def test_pane_bar_brackets_only_the_active_pane():
    class _Other(_FakePane):
        id: str = "other"
        title: str = "other"

    bar = pane_bar([_FakePane(), _Other()], "other", 80)
    assert "[2:other]" in bar
    assert "[1:fake]" not in bar
    assert "1:fake" in bar
    assert "tab=next" in bar and "q=quit" in bar


def test_pane_bar_is_clipped_to_the_width():
    assert len(pane_bar([_FakePane()], "fake", 14)) <= 14


# ───────────────────────────── protocol / dataclasses ─────────────────────────────
def test_a_fake_pane_structurally_satisfies_the_pane_protocol():
    assert isinstance(_FakePane(), Pane)


def test_pane_body_and_ctx_defaults():
    assert PaneBody() == PaneBody((), 0)
    ctx = PaneCtx(cols=10, now=NOW)
    assert ctx.selected == 0 and ctx.cursor is True


def test_pane_ids_are_plain_strings():
    assert PaneId.CODEX == "codex"
    assert [p.value for p in PaneId] == [
        "codex",
        "agents",
        "workflows",
        "databricks",
        "mcp",
        "health",
    ]
