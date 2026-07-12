"""Tests for the vendored subagent-transcript renderer (``monitorcore.agent_tail``).

These tests do NOT travel from the source tree (the retired agent-monitor tool had none) — they
are authored here to bring the vendored module to 100% line+branch coverage. They assert
the exact coloured OUTPUT of ``render`` (byte-for-byte, using timestamp-less entries so the
strings are timezone-independent), exercise every ``render`` event-kind branch, cover
``read_tail_entries`` (backfill N / missing file / blank + malformed line), ``fmt_ts``,
``_one_line``, ``_tool_summary``, ``load_meta``, and ``header``, and drive BOTH the Windows
and the non-Windows path of ``_enable_vt`` on any platform by monkeypatching ``os.name`` and
injecting a fake ``ctypes`` — so the ubuntu CI runner exercises the ``nt`` branch too.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from monitorcore import agent_tail as at

_FIXTURES = Path(__file__).parent / "fixtures"
_FIXTURE_JSONL = _FIXTURES / "agent-deadbeef.jsonl"

# ANSI constants mirrored from the module for exact-output assertions.
R = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
GREY = "\033[90m"
RED = "\033[91m"
GREEN = "\033[92m"
YEL = "\033[93m"
CYAN = "\033[96m"

TS0 = "--:--:--"  # ts for a timestamp-less entry (deterministic, no timezone)


def _entry(*blocks):
    """Wrap content blocks in a message entry WITHOUT a timestamp (ts = ``--:--:--``)."""
    return {"message": {"content": list(blocks)}}


# ───────────────────────── render — exact coloured output ─────────────────────────
def test_render_text_block_exact():
    (line,) = at.render(_entry({"type": "text", "text": "hello"}), 140)
    assert line == f"{GREY}{TS0}{R}  {GREEN}📝 hello{R}"


def test_render_thinking_block_exact():
    (line,) = at.render(_entry({"type": "thinking", "thinking": "pondering"}), 140)
    assert line == f"{GREY}{TS0}  💭 pondering{R}"


def test_render_tool_use_block_exact():
    (line,) = at.render(
        _entry({"type": "tool_use", "name": "Bash", "input": {"command": "echo hi"}}),
        140,
    )
    assert line == (
        f"{GREY}{TS0}{R}  {CYAN}🔧 {BOLD}Bash{R}{CYAN}  {DIM}command={R}echo hi{R}"
    )


def test_render_tool_result_ok_exact():
    (line,) = at.render(_entry({"type": "tool_result", "content": "ok"}), 140)
    assert line == f"{GREY}{TS0}{R}  {YEL}↳{R} {DIM}ok{R}"


def test_render_tool_result_error_exact():
    (line,) = at.render(
        _entry({"type": "tool_result", "content": "boom", "is_error": True}), 140
    )
    assert line == f"{GREY}{TS0}{R}  {RED}✗{R} {DIM}boom{R}"


def test_render_tool_result_non_str_content_json_encoded():
    (line,) = at.render(_entry({"type": "tool_result", "content": {"a": 1}}), 140)
    assert line == f'{GREY}{TS0}{R}  {YEL}↳{R} {DIM}{{"a": 1}}{R}'


def test_render_non_dict_block_bare_line():
    (line,) = at.render(_entry("bare-string"), 140)
    assert line == f"{GREY}{TS0}{R}  bare-string"


def test_render_content_string_wrapped_as_text():
    (line,) = at.render({"message": {"content": "plain string"}}, 140)
    assert line == f"{GREY}{TS0}{R}  {GREEN}📝 plain string{R}"


def test_render_message_not_dict_yields_nothing():
    assert at.render({"message": "not-a-dict"}, 140) == []


def test_render_content_none_yields_nothing():
    assert at.render({"message": {"content": None}}, 140) == []


def test_render_empty_thinking_and_text_are_skipped():
    assert at.render(_entry({"type": "thinking", "thinking": ""}), 140) == []
    assert at.render(_entry({"type": "text", "text": ""}), 140) == []


def test_render_unknown_type_is_ignored():
    # exercises the elif-chain fall-through (no branch matches)
    assert at.render(_entry({"type": "mystery"}), 140) == []


def test_render_tool_use_missing_name_defaults_to_question_mark():
    (line,) = at.render(_entry({"type": "tool_use", "input": {"foo": "bar"}}), 140)
    assert f"🔧 {BOLD}?{R}" in line
    # no _KEY_ARGS present -> json.dumps fallback in _tool_summary
    assert '{"foo": "bar"}' in line


def test_render_tool_use_non_dict_input():
    (line,) = at.render(_entry({"type": "tool_use", "input": "raw-input"}), 140)
    assert line.endswith(f"{CYAN}  raw-input{R}")


def test_render_tool_summary_skips_falsy_key_uses_next():
    # command present but empty -> skipped; query is the chosen key
    (line,) = at.render(
        _entry(
            {"type": "tool_use", "name": "X", "input": {"command": "", "query": "q"}}
        ),
        140,
    )
    assert f"{DIM}query={R}q" in line


# ───────────────────────── _one_line ─────────────────────────
def test_one_line_collapses_whitespace():
    assert at._one_line("a\n  b\t c", 140) == "a b c"


def test_one_line_truncates_with_ellipsis():
    out = at._one_line("x" * 200, 50)
    assert out == "x" * 49 + "…"
    assert len(out) == 50


def test_one_line_exact_width_not_truncated():
    assert at._one_line("y" * 20, 20) == "y" * 20


# ───────────────────────── fmt_ts ─────────────────────────
def test_fmt_ts_none_and_empty():
    assert at.fmt_ts(None) == "--:--:--"
    assert at.fmt_ts("") == "--:--:--"


def test_fmt_ts_valid_iso_returns_hhmmss_shape():
    out = at.fmt_ts("2026-05-27T07:30:00+00:00")
    assert len(out) == 8 and out[2] == ":" and out[5] == ":"
    assert out.replace(":", "").isdigit()


def test_fmt_ts_valid_iso_with_z_suffix():
    out = at.fmt_ts("2026-05-27T07:30:00.000Z")
    assert len(out) == 8 and out[2] == ":" and out[5] == ":"


def test_fmt_ts_invalid_long_string_slices_tail():
    # len > 9, not parseable -> iso[-9:-1]
    assert at.fmt_ts("not-a-timestamp") == "timestam"


def test_fmt_ts_invalid_short_string_returned_asis():
    # len <= 9, not parseable -> returned unchanged
    assert at.fmt_ts("nope") == "nope"


# ───────────────────────── read_tail_entries ─────────────────────────
def test_read_tail_entries_missing_file_returns_empty():
    assert at.read_tail_entries(str(_FIXTURES / "does-not-exist.jsonl"), 5) == []


def test_read_tail_entries_backfill_n_skips_blank_and_malformed(tmp_path):
    p = tmp_path / "agent-x.jsonl"
    p.write_text(
        '{"i": 1}\n'
        "\n"  # blank line -> skipped
        "{not valid json\n"  # starts with "{" but unparseable -> skipped
        '{"i": 2}\n'
        '{"i": 3}\n',
        encoding="utf-8",
    )
    rows = at.read_tail_entries(str(p), 2)
    assert rows == [{"i": 2}, {"i": 3}]


def test_read_tail_entries_from_fixture():
    rows = at.read_tail_entries(str(_FIXTURE_JSONL), 8)
    assert len(rows) == 3
    assert rows[0]["message"]["content"][0]["text"].startswith("Starting the fixture")


def test_fixture_feed_renders_expected_glyphs():
    # The cockpit Feed maps each fixture entry through render(); assert the payloads
    # and glyphs land (timestamp portion is timezone-dependent, so is not asserted).
    rows = at.read_tail_entries(str(_FIXTURE_JSONL), 8)
    lines = [ln for e in rows for ln in at.render(e, 160)]
    assert any("📝 Starting the fixture task" in ln for ln in lines)
    assert any(f"🔧 {BOLD}Bash{R}" in ln for ln in lines)
    assert any("↳" in ln and "hello" in ln for ln in lines)


# ───────────────────────── load_meta / header ─────────────────────────
def test_load_meta_reads_sidecar():
    m = at.load_meta(str(_FIXTURE_JSONL))
    assert m["agentType"] == "general-purpose"
    assert m["name"] == "fixture-agent"


def test_load_meta_missing_returns_empty(tmp_path):
    assert at.load_meta(str(tmp_path / "no-meta.jsonl")) == {}


def test_header_with_meta_prints_name_and_description(capsys):
    at.header(str(_FIXTURE_JSONL), 40)
    out = capsys.readouterr().out
    assert "fixture-agent" in out
    assert "general-purpose" in out
    assert "fixture agent for run-agent-monitor smoke" in out


def test_header_without_meta_falls_back_to_basename(tmp_path, capsys):
    p = tmp_path / "agent-nometa.jsonl"
    p.write_text("{}\n", encoding="utf-8")
    at.header(str(p), 40)
    out = capsys.readouterr().out
    assert "agent-nometa.jsonl" in out
    assert "(agent)" in out  # default agentType when meta is empty


# ───────────────────────── _enable_vt (cross-platform, fully stubbed) ─────────────
class _FakeStream:
    def __init__(self, raises: bool = False):
        self.raises = raises
        self.reconfigured = False

    def reconfigure(self, **_kw):
        if self.raises:
            raise ValueError("cannot reconfigure")
        self.reconfigured = True


class _FakeMode:
    value = 0


class _FakeKernel:
    def __init__(self, console_mode_ret: int = 1):
        self._ret = console_mode_ret
        self.set_called = False

    def GetStdHandle(self, _n):
        return 11

    def GetConsoleMode(self, _h, _ref):
        return self._ret

    def SetConsoleMode(self, _h, _mode):
        self.set_called = True


class _FakeWindll:
    def __init__(self, kernel):
        self.kernel32 = kernel


class _FakeCtypes:
    def __init__(self, kernel, windll_raises: bool = False):
        self._kernel = kernel
        self._windll_raises = windll_raises

    @property
    def windll(self):
        if self._windll_raises:
            raise AttributeError("windll absent (non-Windows)")
        return _FakeWindll(self._kernel)

    def c_uint32(self):
        return _FakeMode()

    def byref(self, x):
        return x


def _patch_streams(monkeypatch, raises: bool = False):
    out, err = _FakeStream(raises), _FakeStream(raises)
    monkeypatch.setattr(sys, "stdout", out)
    monkeypatch.setattr(sys, "stderr", err)
    return out, err


def test_enable_vt_non_windows_reconfigures_streams(monkeypatch):
    monkeypatch.setattr(at.os, "name", "posix")
    out, err = _patch_streams(monkeypatch, raises=False)
    at._enable_vt()
    assert out.reconfigured and err.reconfigured


def test_enable_vt_reconfigure_failure_is_swallowed(monkeypatch):
    monkeypatch.setattr(at.os, "name", "posix")
    out, err = _patch_streams(monkeypatch, raises=True)
    at._enable_vt()  # must not raise
    assert not out.reconfigured and not err.reconfigured


def test_enable_vt_windows_sets_console_mode(monkeypatch):
    monkeypatch.setattr(at.os, "name", "nt")
    _patch_streams(monkeypatch, raises=False)
    kernel = _FakeKernel(console_mode_ret=1)
    monkeypatch.setitem(sys.modules, "ctypes", _FakeCtypes(kernel))
    at._enable_vt()
    assert kernel.set_called is True


def test_enable_vt_windows_get_console_mode_false_skips_set(monkeypatch):
    monkeypatch.setattr(at.os, "name", "nt")
    _patch_streams(monkeypatch, raises=False)
    kernel = _FakeKernel(console_mode_ret=0)
    monkeypatch.setitem(sys.modules, "ctypes", _FakeCtypes(kernel))
    at._enable_vt()
    assert kernel.set_called is False


def test_enable_vt_windows_windll_missing_is_swallowed(monkeypatch):
    monkeypatch.setattr(at.os, "name", "nt")
    _patch_streams(monkeypatch, raises=False)
    kernel = _FakeKernel()
    monkeypatch.setitem(sys.modules, "ctypes", _FakeCtypes(kernel, windll_raises=True))
    at._enable_vt()  # must not raise
    assert kernel.set_called is False


@pytest.mark.parametrize("iso", ["", None])
def test_fmt_ts_falsy_parametrized(iso):
    assert at.fmt_ts(iso) == "--:--:--"


# ───────────────────────── live-tail CLI (added in WU7) ─────────────────────────
def test_default_width_returns_columns(monkeypatch):
    monkeypatch.setattr(
        at.shutil,
        "get_terminal_size",
        lambda _fallback: type("S", (), {"columns": 77})(),
    )
    assert at._default_width() == 77


def test_default_width_falls_back_on_error(monkeypatch):
    def boom(_fallback):
        raise OSError("no tty")

    monkeypatch.setattr(at.shutil, "get_terminal_size", boom)
    assert at._default_width() == 140


def test_wait_for_file_present_immediately():
    assert (
        at._wait_for_file("/anything", sleep=lambda _s: None, exists=lambda _p: True)
        is True
    )


def test_wait_for_file_never_appears(capsys):
    slept = []
    ok = at._wait_for_file(
        "/ghost", sleep=lambda s: slept.append(s), exists=lambda _p: False, limit=2
    )
    assert ok is False
    out = capsys.readouterr().out
    assert "Waiting for /ghost" in out and "File never appeared" in out
    assert slept == [0.5, 0.5, 0.5]  # limit+1 polls before giving up


def test_wait_for_file_appears_after_polls():
    calls = {"n": 0}

    def exists(_p):
        calls["n"] += 1
        return calls["n"] >= 3  # missing twice, then appears

    assert at._wait_for_file("/late", sleep=lambda _s: None, exists=exists) is True


def test_follow_step_emits_new_entries(tmp_path):
    p = tmp_path / "agent-x.jsonl"
    p.write_text(
        "garbage\n"  # non-{ -> skipped
        "{bad json\n"  # unparseable -> skipped
        + '{"message": {"content": [{"type": "text", "text": "hello"}]}}\n',
        encoding="utf-8",
    )
    out = []
    pos, buf, last, announced = at._follow_step(
        str(p), (0, b"", 0.0, False), 160, 20.0, now=lambda: 100.0, out=out.append
    )
    assert any("📝 hello" in ln for ln in out)
    assert (
        pos == p.stat().st_size and buf == b"" and last == 100.0 and announced is False
    )


def test_follow_step_truncation_resets(tmp_path):
    p = tmp_path / "agent-x.jsonl"
    p.write_text(
        '{"message": {"content": [{"type": "text", "text": "again"}]}}\n',
        encoding="utf-8",
    )
    out = []
    # pos far past EOF -> truncation branch resets to 0 then re-reads
    _pos, _buf, _last, _ann = at._follow_step(
        str(p),
        (10_000, b"stale", 0.0, False),
        160,
        20.0,
        now=lambda: 5.0,
        out=out.append,
    )
    assert any("📝 again" in ln for ln in out)


def test_follow_step_idle_notice_once(tmp_path):
    p = tmp_path / "agent-x.jsonl"
    p.write_text("{}\n", encoding="utf-8")
    size = p.stat().st_size
    out = []
    state = at._follow_step(
        str(p), (size, b"", 0.0, False), 160, 20.0, now=lambda: 1000.0, out=out.append
    )
    assert any("idle" in ln for ln in out) and state[3] is True
    # already announced -> no second notice
    out.clear()
    at._follow_step(str(p), state, 160, 20.0, now=lambda: 2000.0, out=out.append)
    assert out == []


def test_follow_step_not_yet_idle_is_silent(tmp_path):
    p = tmp_path / "agent-x.jsonl"
    p.write_text("{}\n", encoding="utf-8")
    size = p.stat().st_size
    out = []
    at._follow_step(
        str(p), (size, b"", 5.0, False), 160, 20.0, now=lambda: 10.0, out=out.append
    )
    assert out == []  # 10 - 5 = 5s < 20s idle threshold


def test_follow_step_oserror_leaves_state_unchanged():
    state = (5, b"x", 1.0, True)
    assert (
        at._follow_step("/no/such/file.jsonl", state, 160, 20.0, now=lambda: 9.0)
        == state
    )


def test_main_returns_1_when_file_never_appears(monkeypatch):
    monkeypatch.setattr(at, "_wait_for_file", lambda *a, **k: False)
    assert at.main(["/ghost.jsonl"]) == 1


def test_main_backfill_then_follow(monkeypatch, capsys):
    monkeypatch.setattr(at, "_follow_forever", lambda *a, **k: 0)
    rc = at.main([str(_FIXTURE_JSONL), "--backfill", "3", "--width", "120"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "fixture-agent" in out  # header
    assert "last 3 events" in out and "live" in out
    assert "Starting the fixture task" in out  # a backfilled entry rendered


def test_main_skips_backfill_when_zero(monkeypatch, capsys):
    monkeypatch.setattr(at, "_follow_forever", lambda *a, **k: 0)
    rc = at.main([str(_FIXTURE_JSONL), "--backfill", "0", "--width", "120"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "last 0 events" not in out  # backfill block skipped
