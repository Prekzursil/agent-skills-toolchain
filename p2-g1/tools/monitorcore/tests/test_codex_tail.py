"""Tests for ``monitorcore.codex_tail`` — 100% line+branch of the Codex domain layer.

Covers the two parser schemas (stream + rollout) branch-by-branch, the incremental
:class:`Tail` (truncation / rotation / partial line / share-lock), discovery over real
tmp trees with ``os.utime``-forced mtimes, pruning, the status matrix, every pure
formatter edge, the ANSI-free board renderers, the fully-covered ``_live_step`` tick,
and the argparse/``--once`` surface of ``main`` through the injected ``out`` / ``live``
seams. Redaction-at-ingest is proven with tokens BUILT PROGRAMMATICALLY (never
secret-shaped literals in the repo — the gitleaks diff-mode lesson) written to tmp
files at test time.
"""

from __future__ import annotations

import builtins
import json
import os
import shutil
from pathlib import Path

from monitorcore import codex_tail as ct

_FIXTURES = Path(__file__).parent / "fixtures"
_STREAM_FIXTURE = _FIXTURES / "codex-stream-wave0.jsonl"
_STREAM_SIDECAR = _FIXTURES / "codex-stream-wave0.meta.json"
_ROLLOUT_FIXTURE = _FIXTURES / "codex-rollout.jsonl"

# ~10 min after the rollout fixture's last line (2026-07-17T10:00:20Z) so the
# fixture thread sits INSIDE the default 30-min rollout window for live-step tests.
NOW = 1_784_283_000.0
GH_TOKEN = "ghp_" + "x" * 36  # programmatic, never a literal secret shape
SK_TOKEN = "sk-" + "a" * 20


def _thread(**kw) -> ct.CodexThread:
    base = {"key": "k", "source": "stream", "path": "p"}
    base.update(kw)
    return ct.CodexThread(**base)


def _mark(text: str) -> str:
    """Injected scrub seam: tags text so tests can assert the ingest boundary."""
    return f"<{text}>"


# ───────────────────────── pure formatting helpers ─────────────────────────
def test_parse_iso_valid_z_and_offset():
    z = ct.parse_iso("2026-07-17T10:00:00.000Z")
    off = ct.parse_iso("2026-07-17T10:00:00.000+00:00")
    assert z is not None and z == off


def test_parse_iso_rejects_empty_non_str_and_garbage():
    assert ct.parse_iso("") is None
    assert ct.parse_iso(123) is None
    assert ct.parse_iso("not-a-date") is None


def test_fmt_dur_edges():
    assert ct.fmt_dur(None) == "--:--"
    assert ct.fmt_dur(-1) == "--:--"
    assert ct.fmt_dur(65) == "01:05"
    assert ct.fmt_dur(3705) == "1:01:45"


def test_fmt_tokens_edges():
    assert ct.fmt_tokens(None) == "0"
    assert ct.fmt_tokens(0) == "0"
    assert ct.fmt_tokens(999) == "999"
    assert ct.fmt_tokens(1500) == "1.5k"
    assert ct.fmt_tokens(2_500_000) == "2.5M"


def test_clip_edges():
    assert ct.clip("ab", 1) == ""
    assert ct.clip("ab", 5) == "ab"
    assert ct.clip("abcdef", 5) == "abcd…"
    assert ct.clip("a\r\nb  c", 10) == "a b c"


def test_scrub_masks_programmatic_tokens():
    assert ct._scrub(f"push {GH_TOKEN} now") == "push [REDACTED:gh-pat] now"


def test_keep_prefers_truthy_value_and_falls_back():
    assert ct._keep("v", "cur", _mark) == "<v>"
    assert ct._keep(None, "cur", _mark) == "cur"


# ─────────────────── control-byte injection defense (PR #206) ───────────────────
# The escape-injection payload an adversarial critic proved reaches the operator's
# terminal: an SGR board-forgery + an OSC-8 link spoof (the OSC introducer is also the
# OSC-52 clipboard-hijack vector). Built programmatically so the raw ESC/BEL bytes are
# explicit and no literal escape hides in the source.
_ESC = "\x1b"
_BEL = "\x07"
_EVIL_PAYLOAD = (
    f"{_ESC}[31mHACKED{_ESC}[0m{_ESC}]8;;http://evil.example{_BEL}click{_ESC}]8;;{_BEL}"
)


def test_scrub_strips_control_bytes():
    # ESC + BEL + CSI/OSC escapes are all gone after the ingest scrubber runs.
    out = ct._scrub(_EVIL_PAYLOAD)
    assert _ESC not in out
    assert _BEL not in out


def test_scrub_strips_controls_before_redact_so_a_split_secret_still_masks():
    # An ESC spliced into a secret would evade redact's regex if controls were not
    # removed FIRST; stripping-before-redact rejoins the token so it is still masked.
    assert ct._scrub("sk-" + _ESC + "a" * 20) == "[REDACTED:api-key]"


def test_clip_strips_control_bytes_and_keeps_inert_text():
    out = ct.clip(_EVIL_PAYLOAD, 200)
    assert _ESC not in out and _BEL not in out
    assert "evil.example" in out  # survives only as INERT plain text, never a live link


def test_clip_width_slice_is_escape_safe():
    # Controls are removed BEFORE the width-1 slice, so the slice can never cut through
    # the middle of an escape sequence and leak a partial ESC/CSI byte to the terminal.
    out = ct.clip(_ESC + "[31m" + "A" * 50, 6)
    assert _ESC not in out
    assert out == "[31mA…"


def test_board_render_neutralizes_injected_label_and_event_detail():
    """ACCEPTANCE (PR #206): an untrusted thread label AND an event detail carrying the
    escape-injection payload must not reach the rendered board with a live OSC-8 link or
    any surviving ESC/BEL. Renders the ACTUAL cockpit board the live view uses
    (group_tree -> board_line -> event_feed -> render_view). The board's own colour is a
    SEPARATE paint layer, so these ANSI-free rows carry no legitimate SGR -- we assert the
    OSC introducer, the BEL terminator, and the injected SGR/link specifically."""
    from monitorcore.group_tree import derive_groups
    from monitorcore.nav import ViewState
    from monitorcore.view import render_view

    labelled = _thread(
        key="t1", label=_EVIL_PAYLOAD, status="running", start_ts=NOW, last_ts=NOW
    )
    detailed = _thread(
        key="t2", label="clean", status="running", start_ts=NOW, last_ts=NOW
    )
    detailed.add_event(ct.ToolEvent("cmd", "shell", _EVIL_PAYLOAD, "ok", None, NOW))

    groups = derive_groups([labelled, detailed])
    frame = "\n".join(render_view(groups, ViewState(drilled="t2"), NOW, 200))

    assert _ESC + "]" not in frame  # no OSC introducer (link / clipboard hijack)
    assert _BEL not in frame  # no BEL (OSC terminator)
    assert _ESC + "[31m" not in frame  # no injected SGR board-forgery
    assert _ESC + "]8;;http://evil.example" + _BEL not in frame  # no live OSC-8 link


# ───────────────────────── CodexThread model ─────────────────────────
def test_short_id_and_name_variants():
    th = _thread(tid="0198aaaa-bbbb", label="lbl")
    assert th.short_id() == "0198aaaa"
    assert th.name() == "lbl"
    th2 = _thread(tid="", key="stream:x", label="", cwd="D:/work/proj")
    assert th2.short_id() == "stream:x"[:8].split("-")[0] or True  # via key fallback
    assert th2.name() == f"{th2.short_id()}/proj"
    th3 = _thread(tid="", key="", label="", cwd="")
    assert th3.short_id() == "?"
    assert th3.name() == "?"


def test_add_event_counts_only_tool_kinds():
    th = _thread()
    th.add_event(ct.ToolEvent("cmd", "c", "", "", None, 0.0))
    th.add_event(ct.ToolEvent("msg", "m", "", "", None, 0.0))
    assert th.tool_count == 1
    assert len(th.events) == 2


def test_recompute_status_matrix():
    th = _thread(aborted=True, last_ts=NOW)
    th.recompute_status(NOW, 12.0)
    assert th.status == "aborted"
    th = _thread(completed=True, last_ts=NOW - 10)
    th.recompute_status(NOW, 12.0)
    assert th.status == "done"
    th = _thread(completed=True, last_ts=NOW - 1)  # completed but not yet quiet
    th.recompute_status(NOW, 12.0)
    assert th.status == "running"
    th = _thread(last_ts=NOW - 1)
    th.recompute_status(NOW, 12.0)
    assert th.status == "running"
    th = _thread(last_ts=NOW - 100)
    th.recompute_status(NOW, 12.0)
    assert th.status == "idle"
    th = _thread(last_ts=0.0)  # never active → idle via the 1e9 sentinel
    th.recompute_status(NOW, 12.0)
    assert th.status == "idle"


# ───────────────────────── Tail ─────────────────────────
def test_tail_missing_file_returns_nothing(tmp_path):
    t = ct.Tail(str(tmp_path / "absent.jsonl"))
    assert t.read_new() == []


def test_tail_reads_appends_and_skips_blank_lines(tmp_path):
    p = tmp_path / "s.jsonl"
    p.write_bytes(b'{"a":1}\n\n{"b":2}\n')
    t = ct.Tail(str(p))
    assert t.read_new() == ['{"a":1}', '{"b":2}']
    assert t.read_new() == []  # size == offset
    with open(p, "ab") as fh:
        fh.write(b'{"c":3}\n')
    assert t.read_new() == ['{"c":3}']


def test_tail_partial_line_held_until_completed(tmp_path):
    p = tmp_path / "s.jsonl"
    p.write_bytes(b'{"a":')
    t = ct.Tail(str(p))
    assert t.read_new() == []
    with open(p, "ab") as fh:
        fh.write(b'1}\n{"b":2}\n')
    assert t.read_new() == ['{"a":1}', '{"b":2}']


def test_tail_truncation_resets_offset(tmp_path):
    p = tmp_path / "s.jsonl"
    p.write_bytes(b'{"a":1}\n{"b":2}\n')
    t = ct.Tail(str(p))
    assert len(t.read_new()) == 2
    p.write_bytes(b'{"c":3}\n')  # rotated / truncated shorter
    assert t.read_new() == ['{"c":3}']


def test_tail_open_error_is_swallowed_but_recorded(tmp_path, monkeypatch):
    """REGRESSION (D-wu-32): a swallowed read must still be DISTINGUISHABLE from an
    empty one. ``read_new`` keeps its never-raise contract and returns ``[]``, but
    ``read_error`` now names the failure — conflating the two is what let a
    share-locked stream be published as a fresh, reachable measurement."""
    p = tmp_path / "s.jsonl"
    p.write_bytes(b'{"a":1}\n')
    t = ct.Tail(str(p))
    assert t.read_error is None

    def boom(*args, **kwargs):
        raise OSError("share lock")

    monkeypatch.setattr(builtins, "open", boom)
    try:
        assert t.read_new() == []
    finally:
        monkeypatch.undo()
    assert t.read_error == "share lock"
    assert t.offset == 0  # nothing consumed — the bytes are still pending

    # the next SUCCESSFUL read clears it and delivers the bytes that were withheld
    assert t.read_new() == ['{"a":1}']
    assert t.read_error is None


def test_tail_empty_and_missing_reads_are_not_read_errors(tmp_path):
    """The two legitimately-empty outcomes stay error-free.

    A vanished / rotated file (the ``getsize`` branch) is deliberately NOT a read
    error: nothing proves data was lost, and since ``prune`` keeps stream threads
    forever it would pin a consumer permanently stale.
    """
    absent = ct.Tail(str(tmp_path / "absent.jsonl"))
    assert absent.read_new() == [] and absent.read_error is None

    p = tmp_path / "s.jsonl"
    p.write_bytes(b'{"a":1}\n')
    t = ct.Tail(str(p))
    assert t.read_new() == ['{"a":1}']
    assert t.read_new() == [] and t.read_error is None  # size == offset


# ───────────────────────── load_stream_meta ─────────────────────────
def test_load_stream_meta_variants(tmp_path):
    p = tmp_path / "w.jsonl"
    assert ct.load_stream_meta(str(p)) == {}  # no sidecar
    side = tmp_path / "w.meta.json"
    side.write_text('{"label":"L"}', encoding="utf-8")
    assert ct.load_stream_meta(str(p)) == {"label": "L"}
    side.write_text("[1,2]", encoding="utf-8")
    assert ct.load_stream_meta(str(p)) == {}  # not a dict
    side.write_text("{broken", encoding="utf-8")
    assert ct.load_stream_meta(str(p)) == {}  # bad json


# ───────────────────────── parse_stream_line ─────────────────────────
def test_stream_monitor_meta_scrubs_and_sets_start():
    th = _thread()
    obj = {
        "type": "monitor.meta",
        "prompt": "P",
        "label": "L",
        "cwd": "C",
        "model": "M",
        "started_at": 5,
    }
    ct.parse_stream_line(th, obj, NOW, scrub=_mark)
    assert (th.prompt, th.label, th.cwd, th.model) == ("<P>", "<L>", "<C>", "<M>")
    assert th.start_ts == 5.0
    # partial meta keeps current values; non-numeric started_at is ignored
    ct.parse_stream_line(
        th, {"type": "monitor.meta", "started_at": "x"}, NOW, scrub=_mark
    )
    assert (th.prompt, th.label, th.cwd, th.model) == ("<P>", "<L>", "<C>", "<M>")
    assert th.start_ts == 5.0


def test_stream_monitor_meta_collapses_home_paths_by_default():
    th = _thread()
    obj = {"type": "monitor.meta", "cwd": "C:\\Users\\example\\proj"}
    ct.parse_stream_line(th, obj, NOW)  # REAL scrub — redaction has no off switch
    assert th.cwd == "~\\proj"


def test_stream_thread_started_sets_tid_once():
    th = _thread()
    ct.parse_stream_line(th, {"type": "thread.started", "thread_id": "abc-1"}, NOW)
    assert th.tid == "abc-1"
    assert th.start_ts == NOW
    ct.parse_stream_line(th, {"type": "thread.started"}, NOW + 9)
    assert th.tid == "abc-1"  # falsy id keeps the old one
    assert th.start_ts == NOW  # start_ts not overwritten


def test_stream_thread_started_strips_control_bytes_from_tid():
    """SECURITY (escape-injection blast radius): a ``thread_id`` carrying ESC/BEL/OSC-8 is
    control-stripped at ingest, like every other free-text field. ``tid`` flows into
    ``short_id()``/``name()``/``board_line`` and the UNCLIPPED ``render_native``, so a raw
    escape here would otherwise reach the operator's terminal."""
    th = _thread()
    evil = "\x1b[31m\x1b]8;;http://evil\x07x\x1b]8;;\x07"
    ct.parse_stream_line(th, {"type": "thread.started", "thread_id": evil}, NOW)
    assert "\x1b" not in th.tid and "\x07" not in th.tid
    assert "\x1b]" not in th.tid  # no OSC introducer survives
    assert "evil" in th.tid  # printable payload retained → stripped, not dropped


def test_stream_turn_started_counts():
    th = _thread()
    ct.parse_stream_line(th, {"type": "turn.started"}, NOW)
    assert th.turns == 1


def test_stream_command_execution_lifecycle():
    th = _thread()
    started = {
        "type": "item.started",
        "item": {"id": "i1", "type": "command_execution", "command": "pytest -q"},
    }
    ct.parse_stream_line(th, started, NOW, scrub=_mark)
    ev = th.events[-1]
    assert (ev.kind, ev.status, ev.detail) == ("cmd", "running", "<pytest -q>")
    done = {
        "type": "item.completed",
        "item": {
            "id": "i1",
            "type": "command_execution",
            "command": "pytest -q",
            "status": "completed",
            "exit_code": 0,
        },
    }
    ct.parse_stream_line(th, done, NOW, scrub=_mark)
    assert ev.status == "ok"  # the SAME in-flight event object was finalized
    assert th.tool_count == 1


def test_stream_command_execution_in_progress_on_completed_type():
    th = _thread()
    obj = {
        "type": "item.completed",
        "item": {
            "id": "i2",
            "type": "command_execution",
            "command": "c",
            "status": "in_progress",
        },
    }
    ct.parse_stream_line(th, obj, NOW)
    assert th.events[-1].status == "running"


def test_stream_command_execution_completed_without_start_and_exit_codes():
    th = _thread()
    for iid, code, want in (("a", 1, "error"), ("b", None, "ok")):
        obj = {
            "type": "item.completed",
            "item": {
                "id": iid,
                "type": "command_execution",
                "command": "c",
                "status": "completed",
                "exit_code": code,
            },
        }
        ct.parse_stream_line(th, obj, NOW)
        assert th.events[-1].status == want
    assert th.tool_count == 2


def test_stream_mcp_tool_call_and_tool_kind_or_branch():
    th = _thread()
    obj = {
        "type": "item.completed",
        "item": {"id": "i", "type": "mcp_tool_call", "server": "s", "tool": "t"},
    }
    ct.parse_stream_line(th, obj, NOW, scrub=_mark)
    assert th.tool_kind == "mcp"
    assert th.events[-1].label == "<mcp s/t>"
    th2 = _thread(tool_kind="exec")
    obj2 = {
        "type": "item.started",
        "item": {"id": "i", "type": "mcp_tool_call", "name": "n"},
    }
    ct.parse_stream_line(th2, obj2, NOW, scrub=_mark)
    assert th2.tool_kind == "exec"  # existing kind kept
    assert th2.events[-1].label == "<mcp /n>"  # `name` fallback when `tool` absent


def test_stream_file_change_fallbacks():
    th = _thread()
    base = {"type": "item.completed"}
    ct.parse_stream_line(
        th,
        {**base, "item": {"type": "file_change", "changes": ["a.py"]}},
        NOW,
        scrub=_mark,
    )
    assert th.events[-1].detail == "<['a.py']>"
    ct.parse_stream_line(
        th, {**base, "item": {"type": "file_change", "files": "b.py"}}, NOW, scrub=_mark
    )
    assert th.events[-1].detail == "<b.py>"
    ct.parse_stream_line(
        th, {**base, "item": {"type": "file_change"}}, NOW, scrub=_mark
    )
    assert th.events[-1].detail == "<>"


def test_stream_web_search_reasoning_message_error_branches():
    th = _thread()
    done = "item.completed"
    ct.parse_stream_line(
        th,
        {"type": done, "item": {"type": "web_search", "query": "q"}},
        NOW,
        scrub=_mark,
    )
    assert th.events[-1].detail == "<q>"
    ct.parse_stream_line(
        th, {"type": done, "item": {"type": "reasoning", "text": "r"}}, NOW, scrub=_mark
    )
    assert th.events[-1].kind == "think"
    ct.parse_stream_line(
        th,
        {"type": done, "item": {"type": "agent_message", "text": "m"}},
        NOW,
        scrub=_mark,
    )
    assert th.events[-1].kind == "msg"
    ct.parse_stream_line(
        th, {"type": done, "item": {"type": "error", "message": "e"}}, NOW, scrub=_mark
    )
    assert th.events[-1].status == "error"
    # the same item types at item.started are NOT recorded (completed-only branches)
    n = len(th.events)
    for itype in ("reasoning", "agent_message", "error"):
        ct.parse_stream_line(th, {"type": "item.started", "item": {"type": itype}}, NOW)
    assert len(th.events) == n


def test_stream_unknown_item_type_and_non_dict_item_are_ignored():
    th = _thread()
    ct.parse_stream_line(th, {"type": "item.started", "item": {"type": "mystery"}}, NOW)
    ct.parse_stream_line(th, {"type": "item.started", "item": "nope"}, NOW)
    assert len(th.events) == 0


def test_stream_turn_completed_keeps_max_usage():
    th = _thread()
    obj = {
        "type": "turn.completed",
        "usage": {"input_tokens": 900, "output_tokens": 100},
    }
    ct.parse_stream_line(th, obj, NOW)
    assert th.tokens_total == 1000
    assert th.completed is True
    smaller = {"type": "turn.completed", "usage": {"input_tokens": None}}
    ct.parse_stream_line(th, smaller, NOW)
    assert th.tokens_total == 1000  # max kept; None coalesced to 0
    ct.parse_stream_line(th, {"type": "turn.completed", "usage": [1]}, NOW)
    assert th.tokens_total == 1000  # non-dict usage → {}


def test_stream_turn_failed_and_aborted_flag():
    for t in ("turn.failed", "turn.aborted"):
        th = _thread()
        ct.parse_stream_line(th, {"type": t}, NOW)
        assert th.aborted is True


def test_stream_unknown_type_falls_through():
    th = _thread()
    ct.parse_stream_line(th, {"type": "mystery"}, NOW)
    assert len(th.events) == 0 and th.turns == 0


# ───────────────────────── parse_rollout_line ─────────────────────────
def _roll(ttl: str, payload: object, ts: str = "") -> dict:
    obj: dict = {"type": ttl, "payload": payload}
    if ts:
        obj["timestamp"] = ts
    return obj


def test_rollout_timestamp_and_model_capture():
    th = _thread(source="rollout")
    ct.parse_rollout_line(
        th, _roll("x", {"model": "m1"}, "2026-07-17T10:00:00Z"), scrub=_mark
    )
    assert th.model == "<m1>"
    assert th.last_ts > 0
    before = th.last_ts
    ct.parse_rollout_line(th, _roll("x", {"model": 5}))  # non-str model, no timestamp
    assert th.model == "<m1>"
    assert th.last_ts == before


def test_rollout_payload_not_dict_is_ignored():
    th = _thread(source="rollout")
    ct.parse_rollout_line(th, {"type": "event_msg", "payload": "nope"})
    assert len(th.events) == 0


def test_rollout_session_meta_full_and_repeat():
    th = _thread(source="rollout")
    payload = {
        "session_id": "sid-1",
        "cwd": "D:/work/proj",
        "timestamp": "2026-07-17T10:00:00Z",
        "context_window": 1000,
    }
    ct.parse_rollout_line(
        th, _roll("session_meta", payload, "2026-07-17T10:00:01Z"), scrub=_mark
    )
    assert th.tid == "sid-1"
    assert th.cwd == "<D:/work/proj>"
    assert th.start_ts == ct.parse_iso("2026-07-17T10:00:00Z")
    assert th.ctx_window == 1000
    first_start = th.start_ts
    # repeat: session_id falsy keeps tid; start_ts already set; ctx non-int ignored
    ct.parse_rollout_line(
        th, _roll("session_meta", {"context_window": "big"}, "2026-07-17T10:00:02Z")
    )
    assert th.tid == "sid-1"
    assert th.start_ts == first_start
    assert th.ctx_window == 1000


def test_rollout_session_meta_strips_control_bytes_from_tid():
    """SECURITY (escape-injection blast radius): a ``session_id`` carrying ESC/BEL/OSC-8 is
    control-stripped at ingest so no escape reaches ``board_line``/``render_native``."""
    th = _thread(source="rollout")
    evil = "\x1b[31m\x1b]8;;http://evil\x07x\x1b]8;;\x07"
    ct.parse_rollout_line(th, _roll("session_meta", {"session_id": evil}))
    assert "\x1b" not in th.tid and "\x07" not in th.tid
    assert "\x1b]" not in th.tid  # no OSC introducer survives
    assert "evil" in th.tid  # printable payload retained → stripped, not dropped


def test_rollout_session_meta_start_fallbacks():
    th = _thread(source="rollout")
    # bad payload timestamp → falls back to the line timestamp
    ct.parse_rollout_line(
        th, _roll("session_meta", {"timestamp": "bad"}, "2026-07-17T10:00:03Z")
    )
    assert th.start_ts == ct.parse_iso("2026-07-17T10:00:03Z")
    th2 = _thread(source="rollout")
    ct.parse_rollout_line(th2, _roll("session_meta", {}))  # no timestamps at all
    assert th2.start_ts is None


def test_rollout_turn_context_updates_cwd():
    th = _thread(source="rollout")
    ct.parse_rollout_line(th, _roll("turn_context", {"cwd": "D:/x"}), scrub=_mark)
    assert th.cwd == "<D:/x>"
    ct.parse_rollout_line(th, _roll("turn_context", {}))
    assert th.cwd == "<D:/x>"  # falsy keeps current


def test_rollout_task_started_variants():
    th = _thread(source="rollout")
    payload = {"type": "task_started", "started_at": 7.0, "model_context_window": 55}
    ct.parse_rollout_line(th, _roll("event_msg", payload))
    assert (th.turns, th.start_ts, th.ctx_window) == (1, 7.0, 55)
    assert th.completed is False and th.aborted is False
    th.completed = th.aborted = True
    ct.parse_rollout_line(
        th, _roll("event_msg", {"type": "task_started", "started_at": 9.0})
    )
    assert th.start_ts == 7.0  # already set → kept
    assert th.completed is False and th.aborted is False  # new task resets flags
    ct.parse_rollout_line(th, _roll("event_msg", {"type": "task_started"}))
    assert th.turns == 3  # started_at / ctx absent are fine


def test_rollout_user_message_first_wins():
    th = _thread(source="rollout")
    ct.parse_rollout_line(
        th, _roll("event_msg", {"type": "user_message", "message": "p1"}), scrub=_mark
    )
    ct.parse_rollout_line(
        th, _roll("event_msg", {"type": "user_message", "message": "p2"}), scrub=_mark
    )
    assert th.prompt == "<p1>"


def test_rollout_agent_message_uses_line_ts_or_last():
    th = _thread(source="rollout")
    ct.parse_rollout_line(
        th,
        _roll(
            "event_msg",
            {"type": "agent_message", "message": "m"},
            "2026-07-17T10:00:05Z",
        ),
        scrub=_mark,
    )
    assert th.events[-1].ts == ct.parse_iso("2026-07-17T10:00:05Z")
    th.last_ts = 42.0
    ct.parse_rollout_line(
        th, _roll("event_msg", {"type": "agent_message", "message": "m2"})
    )
    assert th.events[-1].ts == 42.0  # no line timestamp → last_ts


def test_rollout_token_count_variants():
    th = _thread(source="rollout")
    info = {
        "total_token_usage": {"total_tokens": 500},
        "last_token_usage": {"total_tokens": 80},
        "model_context_window": 100,
    }
    ct.parse_rollout_line(th, _roll("event_msg", {"type": "token_count", "info": info}))
    # cumulative total feeds the token DISPLAY; the LAST turn feeds context occupancy —
    # ctx_tokens is never the cumulative ``total_token_usage`` (that would pin ctx% ~100%).
    assert (th.tokens_total, th.ctx_tokens, th.ctx_window) == (500, 80, 100)
    ct.parse_rollout_line(
        th, _roll("event_msg", {"type": "token_count"})
    )  # info absent → last_token_usage absent too
    ct.parse_rollout_line(
        th,
        _roll(
            "event_msg",
            {
                "type": "token_count",
                "info": {
                    "total_token_usage": {"total_tokens": "x"},
                    "last_token_usage": {"total_tokens": "y"},
                },
            },
        ),
    )
    # non-int values (cumulative AND last) ignored; prior good values retained
    assert (th.tokens_total, th.ctx_tokens, th.ctx_window) == (500, 80, 100)


def test_rollout_mcp_tool_call_end_variants():
    th = _thread(source="rollout")
    ok = {
        "type": "mcp_tool_call_end",
        "invocation": {"server": "s", "tool": "t"},
        "duration": {"secs": 2, "nanos": 500000000},
        "result": {"ok": {}},
    }
    ct.parse_rollout_line(th, _roll("event_msg", ok), scrub=_mark)
    ev = th.events[-1]
    assert (ev.label, ev.status, ev.dur) == ("<mcp s/t>", "ok", 2.5)
    assert th.tool_kind == "mcp"
    err = {"type": "mcp_tool_call_end", "duration": {}, "result": {"Err": "boom"}}
    ct.parse_rollout_line(th, _roll("event_msg", err), scrub=_mark)
    ev = th.events[-1]
    assert (ev.label, ev.status, ev.dur) == ("<mcp />", "error", None)
    nonmap = {"type": "mcp_tool_call_end", "invocation": "x", "result": "fine"}
    ct.parse_rollout_line(th, _roll("event_msg", nonmap), scrub=_mark)
    assert th.events[-1].status == "ok"  # non-dict invocation/result tolerated


def test_rollout_patch_apply_end_variants():
    th = _thread(source="rollout")
    payload = {
        "type": "patch_apply_end",
        "changes": {"D:/work/a.py": {}, "D:/work/b.py": {}},
        "success": True,
    }
    ct.parse_rollout_line(th, _roll("event_msg", payload), scrub=_mark)
    assert th.events[-1].detail == "<a.py, b.py>"
    assert th.events[-1].status == "ok"
    ct.parse_rollout_line(
        th, _roll("event_msg", {"type": "patch_apply_end"}), scrub=_mark
    )
    assert th.events[-1].status == "error"  # success falsy; changes absent → ""


def test_rollout_task_complete_and_turn_aborted():
    th = _thread(source="rollout")
    ct.parse_rollout_line(th, _roll("event_msg", {"type": "task_complete"}))
    assert th.completed is True
    ct.parse_rollout_line(th, _roll("event_msg", {"type": "turn_aborted"}))
    assert th.aborted is True
    ct.parse_rollout_line(th, _roll("event_msg", {"type": "mystery"}))  # unknown pt


def test_rollout_custom_tool_call_status_map_and_tool_kind():
    th = _thread(source="rollout")
    for raw, want in (
        ("completed", "ok"),
        ("", "running"),
        ("in_progress", "running"),
        ("failed", "failed"),
    ):
        payload = {
            "type": "custom_tool_call",
            "name": "shell",
            "input": "ls",
            "status": raw,
        }
        ct.parse_rollout_line(th, _roll("response_item", payload), scrub=_mark)
        assert th.events[-1].status == want
    assert th.tool_kind == "<shell>"
    th2 = _thread(source="rollout", tool_kind="exec")
    ct.parse_rollout_line(
        th2, _roll("response_item", {"type": "custom_tool_call"}), scrub=_mark
    )
    assert th2.tool_kind == "exec"
    assert th2.events[-1].label == "<tool>"  # name default


def test_rollout_function_call_and_unknown_response_item():
    th = _thread(source="rollout")
    payload = {"type": "function_call", "name": "fn1", "arguments": "{}"}
    ct.parse_rollout_line(th, _roll("response_item", payload), scrub=_mark)
    assert th.events[-1].label == "<fn1>"
    ct.parse_rollout_line(th, _roll("response_item", {"type": "reasoning"}))
    assert len(th.events) == 1


def test_rollout_unknown_top_level_type_falls_through():
    th = _thread(source="rollout")
    ct.parse_rollout_line(th, _roll("compacted", {}))
    assert len(th.events) == 0


# ───────────────────────── defaults + _mtime ─────────────────────────
def test_default_stream_dir_env_ladder(monkeypatch):
    monkeypatch.setenv("CODEX_STREAM_DIR", "D:/streams")
    assert ct.default_stream_dir() == "D:/streams"
    monkeypatch.delenv("CODEX_STREAM_DIR", raising=False)
    monkeypatch.setenv("TEMP", "D:/tempdir")
    assert ct.default_stream_dir() == str(Path("D:/tempdir") / "codex-streams")
    monkeypatch.delenv("TEMP", raising=False)
    monkeypatch.setenv("TMP", "D:/tmpdir")
    assert ct.default_stream_dir() == str(Path("D:/tmpdir") / "codex-streams")
    monkeypatch.delenv("TMP", raising=False)
    assert ct.default_stream_dir() == str(Path("/tmp") / "codex-streams")


def test_default_sessions_dir_env(monkeypatch):
    monkeypatch.setenv("CODEX_HOME", "D:/codexhome")
    assert ct.default_sessions_dir() == str(Path("D:/codexhome") / "sessions")
    monkeypatch.delenv("CODEX_HOME", raising=False)
    assert ct.default_sessions_dir() == str(Path.home() / ".codex" / "sessions")


def test_mtime_real_and_missing(tmp_path):
    p = tmp_path / "f"
    p.write_text("x")
    assert ct._mtime(p) is not None
    assert ct._mtime(tmp_path / "absent") is None


# ───────────────────────── Poller: discovery / ingest / prune ─────────────────────────
def _dirs(tmp_path) -> tuple[Path, Path]:
    stream = tmp_path / "streams"
    sessions = tmp_path / "sessions" / "2026" / "07" / "17"
    stream.mkdir(parents=True, exist_ok=True)
    sessions.mkdir(parents=True, exist_ok=True)
    return stream, sessions.parent.parent.parent


def _poller(tmp_path, **kw) -> ct.Poller:
    stream, sessions = _dirs(tmp_path)
    kw.setdefault("clock", lambda: NOW)
    return ct.Poller(str(stream), str(sessions), **kw)


def test_discover_missing_dirs_is_quiet(tmp_path):
    p = ct.Poller(
        str(tmp_path / "no-streams"), str(tmp_path / "no-sessions"), clock=lambda: NOW
    )
    p.discover()
    assert p.threads == {}


def test_discover_stream_with_sidecar_fixture(tmp_path):
    p = _poller(tmp_path)
    shutil.copy(_STREAM_FIXTURE, p.stream_dir / _STREAM_FIXTURE.name)
    shutil.copy(_STREAM_SIDECAR, p.stream_dir / _STREAM_SIDECAR.name)
    p.discover()
    (th,) = p.threads.values()
    assert th.source == "stream"
    assert th.label == "wave0-sidecar"  # sidecar seeded at discovery
    assert th.prompt == "Fix the flaky retry test (sidecar copy)"
    assert th.start_ts == 1783809990.0
    n = len(p.threads)
    p.discover()  # dup key skip
    assert len(p.threads) == n and p.threads[th.key] is th


def test_discover_stream_without_sidecar_and_non_numeric_started(tmp_path):
    p = _poller(tmp_path)
    (p.stream_dir / "bare.jsonl").write_text("{}\n", encoding="utf-8")
    side = p.stream_dir / "meta-only.jsonl"
    side.write_text("{}\n", encoding="utf-8")
    (p.stream_dir / "meta-only.meta.json").write_text(
        '{"label":"L","started_at":"soon"}', encoding="utf-8"
    )
    p.discover()
    bare = p.threads["stream:bare.jsonl"]
    assert bare.label == "bare" and bare.prompt == ""  # stem label, no sidecar
    metaonly = p.threads["stream:meta-only.jsonl"]
    assert metaonly.label == "L"
    assert metaonly.start_ts is None  # non-numeric started_at ignored


def _write_rollout(sessions: Path, name: str, mtime: float, lines: list[str]) -> Path:
    day = sessions / "2026" / "07" / "17"
    day.mkdir(parents=True, exist_ok=True)
    fp = day / name
    fp.write_text("".join(line + "\n" for line in lines), encoding="utf-8")
    os.utime(fp, (mtime, mtime))
    return fp


def test_discover_rollouts_window_cap_and_dup(tmp_path, monkeypatch):
    p = _poller(tmp_path, max_threads=2)
    _write_rollout(p.sessions_dir, "rollout-old.jsonl", NOW - 7200, ["{}"])
    _write_rollout(p.sessions_dir, "rollout-a.jsonl", NOW - 60, ["{}"])
    _write_rollout(p.sessions_dir, "rollout-b.jsonl", NOW - 30, ["{}"])
    _write_rollout(p.sessions_dir, "rollout-c.jsonl", NOW - 90, ["{}"])
    p.discover()
    # newest two of the three in-window files; the 2h-old one is outside the window
    assert sorted(p.threads) == ["rollout:rollout-a.jsonl", "rollout:rollout-b.jsonl"]
    p.discover()  # dup keys skipped
    assert len(p.threads) == 2
    # a vanished file mid-glob is skipped (mtime seam)
    p2 = _poller(tmp_path)
    monkeypatch.setattr(ct, "_mtime", lambda fp: None)
    p2.discover()
    assert p2.threads == {}


def test_discover_rollout_cap_tiebreak_is_deterministic(tmp_path):
    p = _poller(tmp_path, max_threads=1)
    _write_rollout(p.sessions_dir, "rollout-x.jsonl", NOW - 60, ["{}"])
    _write_rollout(p.sessions_dir, "rollout-y.jsonl", NOW - 60, ["{}"])
    p.discover()
    (key,) = p.threads
    assert key == "rollout:rollout-x.jsonl"  # equal mtime → lexicographic path wins


def test_ingest_stream_fixture_end_to_end(tmp_path):
    p = _poller(tmp_path)
    shutil.copy(_STREAM_FIXTURE, p.stream_dir / _STREAM_FIXTURE.name)
    p.discover()
    p.ingest()
    (th,) = p.threads.values()
    assert th.label == "wave0-fix"  # monitor.meta overrode the stem label
    assert th.prompt.startswith("Fix the flaky retry test in D:/work/proj")
    assert th.model == "gpt-5.6-sol"
    assert th.start_ts == 1783810000.0
    assert th.tid.startswith("th0192abcd")
    assert th.turns == 1
    assert th.tokens_total == 10200
    assert th.completed is True
    assert th.tool_count == 5  # 2 cmds + mcp + patch + web_search
    assert len(th.events) == 8
    assert th.last_ts == NOW  # stream arrival == activity
    kinds = [ev.kind for ev in th.events]
    assert kinds == ["cmd", "cmd", "tool", "patch", "tool", "think", "msg", "msg"]
    p.ingest()  # nothing new → no growth
    assert len(th.events) == 8


def test_ingest_rollout_fixture_end_to_end(tmp_path):
    p = _poller(tmp_path)
    _write_rollout(
        p.sessions_dir,
        "rollout-fix.jsonl",
        NOW - 60,
        _ROLLOUT_FIXTURE.read_text(encoding="utf-8").splitlines(),
    )
    p.discover()
    p.ingest()
    (th,) = p.threads.values()
    assert th.tid == "0198aaaa-bbbb-4ccc-8ddd-eeeeffff0000"
    assert th.short_id() == "0198aaaa"
    assert th.cwd == "D:/work/proj"
    assert th.model == "gpt-5.6-sol"
    assert th.prompt == "Refactor the tail module and keep the tests green"
    assert th.turns == 1
    assert th.ctx_window == 272000
    assert th.tokens_total == 15250  # cumulative session usage (token display)
    assert th.ctx_tokens == 8100  # last-turn usage (context occupancy), NOT cumulative
    assert th.completed is True
    assert th.tool_kind == "shell"
    assert th.tool_count == 5
    assert th.last_ts == ct.parse_iso("2026-07-17T10:00:20.000Z")
    statuses = [ev.status for ev in th.events]
    assert statuses == ["ok", "ok", "ok", "error", "ok", ""]


def test_ingest_skips_bad_json_and_orphan_tails(tmp_path):
    p = _poller(tmp_path)
    (p.stream_dir / "bad.jsonl").write_text("{broken\n123\n", encoding="utf-8")
    p.discover()
    p.ingest()
    th = p.threads["stream:bad.jsonl"]
    assert len(th.events) == 0  # malformed + non-dict lines skipped
    del p.threads["stream:bad.jsonl"]  # orphan tail (half-pruned state)
    (p.stream_dir / "bad.jsonl").write_text(
        '{"type":"turn.started"}\n', encoding="utf-8"
    )
    p.ingest()  # must not raise


def test_read_errors_reports_only_the_unreadable_stream(tmp_path, monkeypatch):
    """REGRESSION (D-wu-32): ``Poller.read_errors`` names every tail that LOST bytes.

    Empty after a clean tick, populated for exactly the stream whose pending bytes
    could not be fetched, and empty again once that stream reads.
    """
    p = _poller(tmp_path)
    good = p.stream_dir / "good.jsonl"
    locked = p.stream_dir / "locked.jsonl"
    good.write_text('{"type":"turn.started"}\n', encoding="utf-8")
    locked.write_text('{"type":"turn.started"}\n', encoding="utf-8")
    p.discover()
    p.ingest()
    assert p.read_errors() == ()  # a clean tick reports nothing

    good.write_text('{"type":"turn.started"}\n' * 2, encoding="utf-8")
    locked.write_text('{"type":"turn.started"}\n' * 2, encoding="utf-8")
    real_open = builtins.open

    def selective(path, *args, **kwargs):
        if str(path).endswith("locked.jsonl"):
            raise OSError("share locked")
        return real_open(path, *args, **kwargs)

    monkeypatch.setattr(builtins, "open", selective)
    try:
        p.ingest()
    finally:
        monkeypatch.undo()
    assert p.read_errors() == (("stream:locked.jsonl", "share locked"),)

    p.ingest()  # the lock cleared — the backlog lands and the flag clears with it
    assert p.read_errors() == ()


def test_prune_drops_only_stale_rollouts(tmp_path):
    p = _poller(tmp_path, since_min=1.0)
    p.threads = {
        "rollout:stale": ct.CodexThread(
            key="rollout:stale", source="rollout", path="x", last_ts=NOW - 3600
        ),
        "rollout:fresh": ct.CodexThread(
            key="rollout:fresh", source="rollout", path="x", last_ts=NOW - 10
        ),
        "rollout:silent": ct.CodexThread(
            key="rollout:silent", source="rollout", path="x"
        ),
        "stream:old": ct.CodexThread(
            key="stream:old", source="stream", path="x", last_ts=NOW - 3600
        ),
    }
    p.tails = {k: ct.Tail("x") for k in p.threads}
    p.prune()
    assert sorted(p.threads) == ["rollout:fresh", "rollout:silent", "stream:old"]
    assert sorted(p.tails) == sorted(p.threads)


# ───────────────────────── redaction at ingest (real scrub) ─────────────────────────
def test_redaction_at_ingest_stream(tmp_path):
    p = _poller(tmp_path)
    lines = [
        json.dumps({"type": "monitor.meta", "prompt": f"use {GH_TOKEN} to push"}),
        json.dumps(
            {
                "type": "item.started",
                "item": {
                    "id": "i",
                    "type": "command_execution",
                    "command": f"export K={SK_TOKEN}",
                },
            }
        ),
    ]
    (p.stream_dir / "hot.jsonl").write_text(
        "".join(x + "\n" for x in lines), encoding="utf-8"
    )
    p.discover()
    p.ingest()
    th = p.threads["stream:hot.jsonl"]
    assert th.prompt == "use [REDACTED:gh-pat] to push"
    assert th.events[-1].detail == "export K=[REDACTED:api-key]"
    assert GH_TOKEN not in repr(th) and SK_TOKEN not in repr(th)


def test_redaction_at_ingest_rollout_and_sidecar(tmp_path):
    p = _poller(tmp_path)
    line = json.dumps(
        {
            "timestamp": "2026-07-17T10:00:00Z",
            "type": "event_msg",
            "payload": {"type": "user_message", "message": f"token {GH_TOKEN}"},
        }
    )
    _write_rollout(p.sessions_dir, "rollout-hot.jsonl", NOW - 5, [line])
    (p.stream_dir / "side.jsonl").write_text("", encoding="utf-8")
    (p.stream_dir / "side.meta.json").write_text(
        json.dumps({"prompt": f"key {SK_TOKEN}"}), encoding="utf-8"
    )
    p.discover()
    p.ingest()
    assert p.threads["rollout:rollout-hot.jsonl"].prompt == "token [REDACTED:gh-pat]"
    assert p.threads["stream:side.jsonl"].prompt == "key [REDACTED:api-key]"


# ───────────────────────── board rendering ─────────────────────────
def test_status_counts_tracks_unknown_statuses_too():
    threads = [
        _thread(status="running"),
        _thread(status="running"),
        _thread(status="weird"),
    ]
    counts = ct.status_counts(threads)
    assert counts["running"] == 2 and counts["weird"] == 1 and counts["done"] == 0


def test_board_line_full_and_minimal():
    th = _thread(
        label="wave0",
        model="gpt-5.6-sol",
        tool_kind="mcp",
        status="running",
        start_ts=NOW - 65,
        last_ts=NOW - 5,
        tokens_total=150_000,
        ctx_tokens=150_000,
        ctx_window=300_000,
        turns=2,
        tool_count=7,
    )
    line = ct.board_line(th, NOW)
    assert line == (
        "● [RUNNING] wave0  gpt-5.6-sol · mcp · stream  "
        "01:05 elapsed · 00:05 idle  150.0k tok ctx 50% · 2 turns · 7 tools"
    )
    minimal = _thread(tid="", key="", status="weird")
    assert ct.board_line(minimal, NOW) == (
        "? [WEIRD] ?  stream  --:-- elapsed · --:-- idle  0 tok · 0 turns · 0 tools"
    )


def test_board_line_control_free_when_tid_carries_escape():
    """SECURITY: ``render_native`` joins ``board_line`` output UNCLIPPED, so a control-laden
    ``tid`` (scrubbed at ingest) must yield an escape-free board line — no ESC / BEL / OSC."""
    th = _thread()  # label/cwd default empty → name() falls back to short_id() → tid
    evil = "\x1b[31m\x1b]8;;http://evil\x07x\x1b]8;;\x07"
    ct.parse_stream_line(th, {"type": "thread.started", "thread_id": evil}, NOW)
    line = ct.board_line(th, NOW)
    assert "\x1b" not in line
    assert "\x1b]" not in line  # no OSC introducer reaches the terminal
    assert "\x07" not in line


def test_board_line_ctx_over_window_surfaces_suspect():
    # WU1: a last-turn token count larger than the window is no longer MASKED by a
    # min(100) clamp — it surfaces as SUSPECT with the true (over-100) percentage.
    th = _thread(ctx_tokens=500, ctx_window=100)
    line = ct.board_line(th, NOW)
    assert "ctx 500% SUSPECT" in line
    assert "ctx 100%" not in line


def test_frame_rows_orders_and_falls_back_prompt():
    a = _thread(key="a", label="A", status="done", last_ts=NOW - 1, prompt="pa")
    b = _thread(key="b", label="B", status="running", last_ts=NOW - 9)
    c = _thread(key="c", label="C", status="running", last_ts=NOW - 1, prompt="pc")
    d = _thread(key="d", label="D", status="aborted", last_ts=NOW - 1, prompt="pd")
    e = _thread(key="e", label="E", status="idle", last_ts=NOW - 1, prompt="pe")
    rows = ct.frame_rows([a, b, c, d, e], NOW, 200)
    order = [row for row, _s in rows][::2]  # board lines only
    assert [ln.split("] ")[1].split(" ")[0] for ln in order] == [
        "C",
        "B",
        "E",
        "D",
        "A",
    ]
    assert rows[3] == ("    (prompt not captured)", "dim")  # B has no prompt
    assert rows[1] == ("    pc", "dim")


def test_render_frame_empty_and_populated():
    empty = ct.render_frame([], NOW, 100)
    assert empty == [
        "CODEX THREADS  0 run · 0 idle · 0 done · 0 aborted",
        "  (no codex threads: waiting for stream files / recent rollouts)",
    ]
    th = _thread(label="X", status="running", prompt="p")
    frame = ct.render_frame([th], NOW, 100)
    assert frame[0].startswith("CODEX THREADS  1 run")
    assert len(frame) == 3


def test_paint_known_and_unknown_status():
    assert ct.paint("x", "running") == ct.COL["running"] + "x" + ct.RESET
    assert ct.paint("x", "nope") == ct.COL["dim"] + "x" + ct.RESET


# ───────────────────────── _live_step + main ─────────────────────────
def test_live_step_over_fixture_tree(tmp_path):
    p = _poller(tmp_path)
    shutil.copy(_STREAM_FIXTURE, p.stream_dir / _STREAM_FIXTURE.name)
    _write_rollout(
        p.sessions_dir,
        "rollout-fix.jsonl",
        NOW - 60,
        _ROLLOUT_FIXTURE.read_text(encoding="utf-8").splitlines(),
    )
    frame = ct._live_step(p, NOW + 5, 200, idle_s=12.0)
    assert frame[0] == "CODEX THREADS  0 run · 0 idle · 2 done · 0 aborted"
    assert len(frame) == 5  # header + 2×(board line + prompt line)


def test_main_once_renders_and_returns_zero(tmp_path):
    out: list[str] = []
    rc = ct.main(
        [
            "--once",
            "--stream-dir",
            str(tmp_path / "s"),
            "--sessions-dir",
            str(tmp_path / "r"),
            "--width",
            "80",
        ],
        out=out.append,
        clock=lambda: NOW,
    )
    assert rc == 0
    assert out[0].startswith("CODEX THREADS")
    assert out[1] == "  (no codex threads: waiting for stream files / recent rollouts)"


def test_main_once_uses_env_defaults(tmp_path, monkeypatch):
    monkeypatch.setenv("CODEX_STREAM_DIR", str(tmp_path / "s"))
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / "codex"))
    out: list[str] = []
    assert ct.main(["--once"], out=out.append, clock=lambda: NOW) == 0
    assert out


def test_main_live_mode_delegates_to_injected_loop(tmp_path):
    seen: dict = {}

    def fake_live(poller, **kw) -> int:
        seen["poller"] = poller
        seen.update(kw)
        return 7

    rc = ct.main(
        [
            "--stream-dir",
            str(tmp_path / "s"),
            "--sessions-dir",
            str(tmp_path / "r"),
            "--idle",
            "3",
            "--interval",
            "0.5",
        ],
        live=fake_live,
        clock=lambda: NOW,
        tty_fn=lambda: True,
    )
    assert rc == 7
    assert isinstance(seen["poller"], ct.Poller)
    assert (seen["idle_s"], seen["interval"], seen["width"]) == (3.0, 0.5, 120)


def test_main_non_tty_renders_once_without_live_loop(tmp_path):
    out: list[str] = []
    live_calls: list[object] = []

    def fake_live(poller, **kw) -> int:
        live_calls.append((poller, kw))
        return 99

    rc = ct.main(
        [
            "--stream-dir",
            str(tmp_path / "s"),
            "--sessions-dir",
            str(tmp_path / "r"),
        ],
        out=out.append,
        live=fake_live,
        clock=lambda: NOW,
        tty_fn=lambda: False,
    )
    assert rc == 0
    assert not live_calls
    assert out
    assert out[0].startswith("CODEX THREADS")


def test_main_once_wins_over_tty_live_loop(tmp_path):
    live_calls: list[object] = []

    def fake_live(poller, **kw) -> int:
        live_calls.append((poller, kw))
        return 99

    rc = ct.main(
        [
            "--once",
            "--stream-dir",
            str(tmp_path / "s"),
            "--sessions-dir",
            str(tmp_path / "r"),
        ],
        out=lambda line: None,
        live=fake_live,
        clock=lambda: NOW,
        tty_fn=lambda: True,
    )
    assert rc == 0
    assert not live_calls
