"""WF-8 regression: every glyph the cockpit puts on the terminal grid is 1 cell wide.

WHY THIS EXISTS.  ``rules/common/bash-hud-and-terminal-emit.md`` #5 records a
measured alignment corruption: an emoji-presentation or East-Asian *Wide* glyph
occupies TWO cells on Windows Terminal, so a run label or feed line carrying one
overlaps its neighbour and every column budget computed from ``len(str)`` is
short by one per glyph.  U+26A0 WARNING SIGN is named there explicitly as the
corruptor that was measured, and ``!``/``U+2713``/``U+2717`` are named as the
width-1-unambiguous replacements.  Before this guard the cockpit shipped four
of them: U+26A0 in the run label and U+1F4AD / U+1F4DD / U+1F527 in the
fallback feed renderer.

DETECTOR CONTROL.  ``test_width_classifier_fires_on_known_bad`` is not
decoration.  A width guard that is silent because its classifier is broken is
indistinguishable from a width guard that is silent because the code is clean
(``rules/common/single-signal-verification.md`` #3b: prove the probe fires in
the KNOWN-BROKEN state before its silence counts as evidence).  If that test is
ever deleted, every other assertion in this file becomes unfalsifiable.

SCOPE, stated so it is not overclaimed.  This file asserts NARROW-ness only for
glyphs that are *definitively* two cells: East_Asian_Width in {W, F}, the emoji
planes at/above U+1F300, and the rule-named U+26A0.  It deliberately does NOT
assert anything about East-Asian *Ambiguous* glyphs, which the cockpit still
uses (U+25CF active, U+21BB retry, U+2713/U+2717/U+25D4 counts, U+25B8 phase,
U+21B3 tool-result).  Those render 1 cell under a Latin font and 2 under a CJK
font, so they are a real but font-dependent residual, NOT covered here.
"""

from __future__ import annotations

import unicodedata

import workflow_monitor as wm
import workflow_run as wr

# U+26A0 defaults to TEXT presentation in Unicode (so east_asian_width reports
# 'A'), but Windows Terminal renders it emoji-wide -- measured, and the reason
# the estate rule names this codepoint by hand rather than by property.
RULE_NAMED_WIDE = {"⚠"}


def is_wide(ch: str) -> bool:
    """True when ``ch`` definitively occupies two terminal cells."""
    if ch in RULE_NAMED_WIDE:
        return True
    if ord(ch) >= 0x1F300:  # emoji planes; Emoji_Presentation by default
        return True
    return unicodedata.east_asian_width(ch) in ("W", "F")


def wide_glyphs(text: str) -> list[str]:
    return [ch for ch in text if is_wide(ch)]


def _agent(**over):
    """A WFAgent on a benign baseline (same idiom as test_quiet_wording.py)."""
    base = dict(
        agent_id="x",
        index=0,
        label="x",
        phase_index=0,
        phase_title="",
        model="",
        state="progress",
        tokens=0,
        tool_calls=0,
        duration_ms=0,
        last_tool="",
        last_summary="",
        prompt_preview="",
        result_preview="",
        attempt=1,
        started_at=0,
        last_progress_at=0,
    )
    base.update(over)
    return wr.WFAgent(**base)


def _run(agent, *, wf_id: str, status: str = "running") -> wr.WFRun:
    return wr.WFRun(
        wf_id=wf_id,
        name=wf_id,
        status=status,
        phases=[],
        agent_count=1,
        total_tokens=0,
        total_tool_calls=0,
        duration_ms=0,
        started_at=0,
        manifest_path="",
        session="",
        mtime=0.0,
        agents=[agent],
    )


# ── detector control (must FIRE before any silence below is evidence) ────────


def test_width_classifier_fires_on_known_bad():
    """The classifier must catch each glyph WF-8 removed, and stay silent on the
    replacements and on the ambiguous marks the cockpit legitimately uses."""
    for ch in ("⚠", "\U0001f4ad", "\U0001f4dd", "\U0001f527"):
        assert is_wide(ch), f"classifier blind to {ch!r} -- guard would be inert"
    for ch in ("!", "*", ">", "+", "~", "✓", "✗"):
        assert not is_wide(ch), f"classifier false-positives on {ch!r}"
    assert wide_glyphs("a\U0001f527b") == ["\U0001f527"]
    assert wide_glyphs("plain ascii") == []


# ── behavioural: the two renderers WF-8 named ───────────────────────────────


def test_run_label_error_marker_is_narrow():
    now = 1_000_000.0
    label = wm._run_label(_run(_agent(state="error"), wf_id="e"), now).plain
    assert wide_glyphs(label) == [], f"wide glyph in run label: {label!r}"
    # The marker still has to be a distinct, present error mark.
    assert label.startswith("! ")


def test_every_run_label_branch_is_narrow():
    """err / quiet / retry / active / idle all render narrow markers."""
    now = 1_000_000.0
    cases = [
        _run(_agent(state="error"), wf_id="err"),
        _run(_agent(last_progress_at=now - wm.QUIET_MS - 1), wf_id="quiet"),
        _run(_agent(attempt=2), wf_id="retry"),
        _run(_agent(), wf_id="active"),
        _run(_agent(), wf_id="done", status="completed"),
    ]
    for run in cases:
        plain = wm._run_label(run, now).plain
        assert wide_glyphs(plain) == [], f"{run.wf_id}: wide glyph in {plain!r}"


def test_fallback_render_emits_no_wide_glyphs():
    """The fallback feed renderer (used when vendored agent_tail is absent)."""
    entry = {
        "message": {
            "content": [
                {"type": "thinking", "thinking": "pondering the plan"},
                {"type": "text", "text": "hello world"},
                {"type": "tool_use", "name": "Bash"},
                {"type": "tool_result", "content": "ok"},
                {"type": "tool_result", "content": "boom", "is_error": True},
            ]
        }
    }
    lines = wm._fallback_render(entry)
    assert len(lines) == 5, "fixture must exercise every block branch"
    for line in lines:
        assert wide_glyphs(line.plain) == [], f"wide glyph in feed line: {line.plain!r}"
    # The three markers WF-8 replaced must still be present and distinguishable.
    assert lines[0].plain.startswith("* ")
    assert lines[1].plain.startswith("> ")
    assert lines[2].plain.startswith("+ ")


def test_fallback_render_markers_are_mutually_distinct():
    """A width fix must not collapse two block types onto the same marker."""
    entry = {
        "message": {
            "content": [
                {"type": "thinking", "thinking": "t"},
                {"type": "text", "text": "x"},
                {"type": "tool_use", "name": "Bash"},
                {"type": "tool_result", "content": "ok"},
                {"type": "tool_result", "content": "bad", "is_error": True},
            ]
        }
    }
    markers = [ln.plain[0] for ln in wm._fallback_render(entry)]
    assert len(set(markers)) == len(markers), f"marker collision: {markers}"


# ── whole-module guard (catches a future addition anywhere in the file) ─────


def test_module_source_carries_no_wide_glyph():
    """Covers code paths this file does not construct, and future edits.

    Scans the WHOLE source, comments included: a banner drawn with a wide glyph
    corrupts the header line just as a run label does.
    """
    with open(wm.__file__, encoding="utf-8") as fh:
        source = fh.read()
    offenders = sorted(
        {f"U+{ord(ch):04X} {unicodedata.name(ch, '?')}" for ch in source if is_wide(ch)}
    )
    assert offenders == [], f"wide glyphs in {wm.__file__}: {offenders}"
