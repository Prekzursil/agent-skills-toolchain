"""Tests for ``agent_tail.render_detail`` and the spilled-output resolver.

``render`` (covered in ``test_agent_tail.py``) is a one-line-per-event feed: every
field collapsed and truncated to terminal width. That is the right shape for a
dense board and the wrong shape for reading what an agent actually did — the
reasoning is present in the transcript and thrown away at render time, and a
large tool result lives in a sidecar file that nothing in this repo read.

These tests pin the readable counterpart: reasoning intact, every tool argument
rather than the one guessed to be most informative, spilled output resolved from
``toolUseResult.persistedOutputPath``, and — where a cap still applies — an
explicit statement of how much was withheld rather than a silent cut.
"""

from __future__ import annotations

from monitorcore import agent_tail as at


def _entry(*blocks):
    """Content blocks in a message entry WITHOUT a timestamp (ts = ``--:--:--``)."""
    return {"message": {"content": list(blocks)}}


# ───────────────────────────── wrapping primitives ─────────────────────────────


def test_wrap_preserves_blank_lines_and_paragraphs():
    assert at._wrap("one\n\ntwo", 40, "| ") == ["| one", "| ", "| two"]


def test_wrap_empty_string_yields_one_gutter_line():
    assert at._wrap("", 40, "| ") == ["| "]


def test_wrap_hard_wraps_long_lines():
    out = at._wrap("x" * 50, 20, "")
    assert len(out) == 3
    assert all(len(seg) <= 20 for seg in out)


def test_wrap_floors_a_narrow_width():
    """A width of 1 would wrap one character per line; the floor keeps it legible."""
    assert at._wrap("hello world", 1, "") == ["hello world"]
    out = at._wrap("y" * 40, 1, "")
    assert out == ["y" * 20, "y" * 20], "floored to 20, not wrapped at 1"


def test_wrap_coerces_non_strings():
    assert at._wrap(42, 40, "") == ["42"]


def test_capped_passes_through_under_the_cap():
    assert at._capped(["a", "b"], 5, "") == ["a", "b"]
    assert at._capped(["a", "b"], None, "") == ["a", "b"]


def test_capped_announces_what_it_withheld():
    out = at._capped(["a", "b", "c", "d"], 2, ", rest at /tmp/x")
    assert out[:2] == ["a", "b"]
    assert "2 more line(s), rest at /tmp/x" in out[2]


# ───────────────────────────── reasoning ─────────────────────────────


def test_detail_renders_full_reasoning_not_one_truncated_line():
    think = "first paragraph of reasoning\n\nsecond paragraph " + "w" * 300
    out = at.render_detail(_entry({"type": "thinking", "thinking": think}), 80)
    body = "\n".join(out)
    assert "reasoning" in out[0]
    assert "first paragraph of reasoning" in body
    assert "second paragraph" in body
    assert len(out) > 3, "multi-line, unlike render()'s single truncated line"
    assert "…" not in body, "nothing elided below the cap"


def test_detail_states_when_reasoning_was_not_retained():
    """Older transcripts keep the signature and drop the prose. An empty pane
    must not read as 'the agent did not think'."""
    out = at.render_detail(
        _entry({"type": "thinking", "thinking": "", "signature": "opaque-ciphertext"}),
        80,
    )
    assert len(out) == 1
    assert "reasoning not retained" in out[0]
    assert "opaque-ciphertext" not in out[0], "a signature is ciphertext, never shown"


def test_detail_skips_an_empty_thinking_block_with_no_signature():
    assert at.render_detail(_entry({"type": "thinking", "thinking": ""}), 80) == []


# ───────────────────────────── text and tool calls ─────────────────────────────


def test_detail_renders_text_and_skips_empty_text():
    out = at.render_detail(_entry({"type": "text", "text": "hello there"}), 80)
    assert "message" in out[0]
    assert "hello there" in out[1]
    assert at.render_detail(_entry({"type": "text", "text": ""}), 80) == []


def test_detail_shows_every_tool_argument_sorted():
    """``render`` shows one key from a fixed preference list; this shows them all."""
    out = at.render_detail(
        _entry(
            {
                "type": "tool_use",
                "name": "Edit",
                "input": {
                    "file_path": "/tmp/a.py",
                    "old_string": "before",
                    "new_string": "after",
                    "replace_all": False,
                },
            }
        ),
        80,
    )
    body = "\n".join(out)
    for key in ("file_path", "old_string", "new_string", "replace_all"):
        assert f"{key}:" in body
    assert "before" in body
    assert "after" in body
    assert body.index("file_path:") < body.index("new_string:"), "keys are sorted"


def test_detail_json_encodes_non_string_tool_arguments():
    out = at.render_detail(
        _entry({"type": "tool_use", "name": "T", "input": {"n": [1, 2]}}), 80
    )
    assert "1," in "\n".join(out)


def test_detail_handles_non_dict_tool_input():
    out = at.render_detail(
        _entry({"type": "tool_use", "name": "T", "input": "raw-string"}), 80
    )
    assert "raw-string" in "\n".join(out)


def test_detail_handles_absent_tool_input():
    out = at.render_detail(_entry({"type": "tool_use", "name": "T"}), 80)
    assert len(out) == 1
    assert "T" in out[0]


# ───────────────────────────── results ─────────────────────────────


def test_detail_renders_inline_result():
    out = at.render_detail(_entry({"type": "tool_result", "content": "all good"}), 80)
    assert "result" in out[0]
    assert "all good" in out[1]


def test_detail_marks_an_error_result():
    out = at.render_detail(
        _entry({"type": "tool_result", "content": "boom", "is_error": True}), 80
    )
    assert "✗" in out[0]


def test_detail_json_encodes_structured_result_content():
    out = at.render_detail(_entry({"type": "tool_result", "content": {"k": "v"}}), 80)
    assert '"k"' in "\n".join(out)


# ───────────────────────── content-shape edge cases ─────────────────────────


def test_detail_handles_odd_message_shapes():
    assert at.render_detail({"message": {"content": 42}}, 80) == []
    assert at.render_detail({"message": "not a dict"}, 80) == []
    out = at.render_detail({"message": {"content": "plain text body"}}, 80)
    assert "plain text body" in "\n".join(out)


def test_detail_renders_a_non_dict_content_block():
    out = at.render_detail({"message": {"content": [["odd", "block"]]}}, 80)
    assert "odd" in "\n".join(out)


def test_detail_ignores_an_unknown_block_type():
    assert at.render_detail(_entry({"type": "image", "source": "x"}), 80) == []


# ───────────────────────────── the cap ─────────────────────────────


def test_detail_cap_applies_and_says_so():
    many = "\n".join(f"line {i}" for i in range(50))
    out = at.render_detail(
        _entry({"type": "thinking", "thinking": many}), 80, max_lines=5
    )
    assert "more line(s)" in out[-1]


def test_detail_uncapped_when_max_lines_is_none():
    many = "\n".join(f"l{i}" for i in range(30))
    out = at.render_detail(
        _entry({"type": "thinking", "thinking": many}), 80, max_lines=None
    )
    assert "more line(s)" not in "\n".join(out)


# ─────────────────── resolve_persisted_output — the spill ───────────────────


def test_resolve_persisted_output_reads_the_sidecar(tmp_path):
    spill = tmp_path / "toolu_abc.txt"
    spill.write_text("the whole 500 KB of output", encoding="utf-8")
    text, path = at.resolve_persisted_output(
        {"toolUseResult": {"persistedOutputPath": str(spill)}}
    )
    assert text == "the whole 500 KB of output"
    assert path == str(spill)


def test_resolve_persisted_output_reports_an_unreadable_claim(tmp_path):
    missing = str(tmp_path / "gone.txt")
    text, path = at.resolve_persisted_output(
        {"toolUseResult": {"persistedOutputPath": missing}}
    )
    assert text is None
    assert path == missing, "the path is returned so a caller can name it"


def test_resolve_persisted_output_absent_cases():
    nothing = (None, None)
    assert at.resolve_persisted_output({}) == nothing
    assert at.resolve_persisted_output({"toolUseResult": "a string"}) == nothing
    assert at.resolve_persisted_output({"toolUseResult": {}}) == nothing
    assert (
        at.resolve_persisted_output({"toolUseResult": {"persistedOutputPath": ""}})
        == nothing
    )
    assert (
        at.resolve_persisted_output({"toolUseResult": {"persistedOutputPath": 7}})
        == nothing
    )


def test_detail_resolves_a_spilled_result_instead_of_the_preview(tmp_path):
    spill = tmp_path / "toolu_big.txt"
    spill.write_text("FULL OUTPUT MARKER", encoding="utf-8")
    entry = {
        "message": {
            "content": [{"type": "tool_result", "content": "Output too large. trunc"}]
        },
        "toolUseResult": {"persistedOutputPath": str(spill)},
    }
    body = "\n".join(at.render_detail(entry, 80))
    assert "FULL OUTPUT MARKER" in body
    assert "resolved 18 bytes" in body
    assert "Output too large" not in body, "the preview is replaced, not appended"


def test_detail_says_so_when_the_spill_is_unreadable(tmp_path):
    entry = {
        "message": {"content": [{"type": "tool_result", "content": "preview only"}]},
        "toolUseResult": {"persistedOutputPath": str(tmp_path / "vanished.txt")},
    }
    body = "\n".join(at.render_detail(entry, 80))
    assert "persisted output unreadable" in body
    assert "preview only" in body, "the preview still shows, but labelled as partial"


def test_detail_can_skip_spill_resolution(tmp_path):
    spill = tmp_path / "s.txt"
    spill.write_text("SHOULD NOT APPEAR", encoding="utf-8")
    entry = {
        "message": {"content": [{"type": "tool_result", "content": "preview"}]},
        "toolUseResult": {"persistedOutputPath": str(spill)},
    }
    body = "\n".join(at.render_detail(entry, 80, resolve_persisted=False))
    assert "SHOULD NOT APPEAR" not in body
    assert "preview" in body


# ─────────────────── window + renderer plumbing ───────────────────


def test_read_tail_entries_honours_a_custom_window(tmp_path):
    p = tmp_path / "a.jsonl"
    pad = "x" * 200
    p.write_text(
        "\n".join('{"i":%d,"pad":"%s"}' % (i, pad) for i in range(40)),
        encoding="utf-8",
    )
    narrow = at.read_tail_entries(str(p), 50, window=400)
    wide = at.read_tail_entries(str(p), 50, window=200_000)
    assert len(narrow) < len(wide), "a smaller window reaches less far back"
    assert wide[-1]["i"] == 39


def test_follow_step_uses_an_injected_renderer(tmp_path):
    p = tmp_path / "a.jsonl"
    p.write_text(
        '{"message":{"content":[{"type":"text","text":"hi"}]}}\n', encoding="utf-8"
    )
    seen: list[str] = []
    at._follow_step(
        str(p),
        (0, b"", 0.0, False),
        80,
        9e9,
        now=lambda: 1.0,
        out=seen.append,
        renderer=lambda _e, _w: ["RENDERED-BY-INJECTED"],
    )
    assert seen == ["RENDERED-BY-INJECTED"]


def test_main_detail_mode_prints_full_reasoning(tmp_path, capsys, monkeypatch):
    monkeypatch.setattr(at, "_follow_forever", lambda *a, **k: 0)
    p = tmp_path / "agent-x.jsonl"
    p.write_text(
        '{"message":{"content":[{"type":"thinking","thinking":"deep\\nthought"}]}}\n',
        encoding="utf-8",
    )
    rc = at.main(
        [str(p), "--detail", "--max-lines", "0", "--backfill", "4", "--width", "80"]
    )
    assert rc == 0
    out = capsys.readouterr().out
    assert "reasoning" in out
    assert "deep" in out
    assert "thought" in out


def test_main_passes_a_detail_renderer_to_the_follow_loop(tmp_path, monkeypatch):
    """--detail must change the LIVE feed too, not just the backfill."""
    captured: dict[str, object] = {}

    def fake_follow(*_a, **kw):
        captured.update(kw)
        return 0

    monkeypatch.setattr(at, "_follow_forever", fake_follow)
    p = tmp_path / "agent-y.jsonl"
    p.write_text(
        '{"message":{"content":[{"type":"text","text":"hi"}]}}\n', encoding="utf-8"
    )

    at.main([str(p), "--backfill", "0"])
    assert captured["renderer"] is None, "plain mode keeps the one-line feed"

    captured.clear()
    at.main([str(p), "--detail", "--backfill", "0"])
    renderer = captured["renderer"]
    assert renderer is not None
    lines = renderer(
        {"message": {"content": [{"type": "text", "text": "live detail"}]}}, 80
    )
    assert any("live detail" in ln for ln in lines)
