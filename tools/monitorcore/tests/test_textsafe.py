"""Unit tests for ``monitorcore.textsafe``.

All functions under test are PURE (no filesystem, no globals). Coverage targets every
branch: ANSI CSI/single-char escapes, the five HTML meta-chars, dynamic-length fences
(including triple-backticks appearing inside content), head+tail truncation with a byte
offset marker, UTF-8-safe boundary backoff on both the head and tail cuts, the degenerate
"nothing left to elide" guard, per-artifact hard capping, and base64 elision of both a
``data:...;base64,`` URI and a long standalone run.
"""

from monitorcore.textsafe import (
    cap_artifact,
    elide_base64,
    html_escape,
    safe_fence,
    strip_ansi,
    truncate_block,
)

# --------------------------------------------------------------------------- strip_ansi


def test_strip_ansi_removes_sgr():
    assert strip_ansi("\x1b[31mred\x1b[0m") == "red"


def test_strip_ansi_multi_param():
    assert strip_ansi("\x1b[1;32mx\x1b[0m") == "x"


def test_strip_ansi_cursor_and_erase():
    assert strip_ansi("a\x1b[2Kb\x1b[10;5H") == "ab"


def test_strip_ansi_single_char_escape():
    # ESC c (RIS) and ESC = are non-CSI escapes; both stripped.
    assert strip_ansi("\x1bcx\x1b=y") == "xy"


def test_strip_ansi_identity_on_plain():
    assert strip_ansi("plain text 123") == "plain text 123"


# -------------------------------------------------------------------------- html_escape


def test_html_escape_all_meta_chars():
    assert html_escape('<a href="x">&\'') == "&lt;a href=&quot;x&quot;&gt;&amp;&#x27;"


def test_html_escape_each():
    assert html_escape("<") == "&lt;"
    assert html_escape(">") == "&gt;"
    assert html_escape("&") == "&amp;"
    assert html_escape('"') == "&quot;"
    assert html_escape("'") == "&#x27;"


def test_html_escape_ampersand_first():
    # A raw '&' must not double-escape the '<' that follows it.
    assert html_escape("a & <b>") == "a &amp; &lt;b&gt;"


def test_html_escape_identity_on_plain():
    assert html_escape("safe_string-42") == "safe_string-42"


# --------------------------------------------------------------------------- safe_fence


def test_safe_fence_default_three():
    assert safe_fence("no backticks here") == "```"


def test_safe_fence_single_backtick_still_three():
    assert safe_fence("inline `code` span") == "```"


def test_safe_fence_triple_inside_yields_four():
    assert safe_fence("```") == "````"
    assert safe_fence("text\n```\nmore") == "````"


def test_safe_fence_longest_run_wins():
    # Longest run is 4 backticks -> fence must be 5.
    assert safe_fence("a ``` b ```` c ``") == "`````"


# ---------------------------------------------------------------------- truncate_block


def test_truncate_block_identity_under_cap():
    assert truncate_block("short", 100) == "short"


def test_truncate_block_identity_at_cap_boundary():
    s = "A" * 100
    assert truncate_block(s, 100) == s


def test_truncate_block_head_tail_marker():
    s = "A" * 5000
    out = truncate_block(s, 100, head=50, tail=20)
    assert out == "A" * 50 + "\n...[4930 bytes elided @50]...\n" + "A" * 20


def test_truncate_block_utf8_boundary_backoff_both_ends():
    # Each 'é' is 2 bytes in UTF-8 (0xC3 0xA9). head=51 and tail=21 both land on a
    # continuation byte, forcing a backoff to an even boundary.
    s = "é" * 1000  # 2000 bytes
    out = truncate_block(s, 100, head=51, tail=21)
    assert out == "é" * 25 + "\n...[1930 bytes elided @50]...\n" + "é" * 10
    # Result is valid UTF-8 (no half char) -- re-encoding round-trips.
    assert out.encode("utf-8").decode("utf-8") == out


def test_truncate_block_degenerate_nothing_to_elide():
    # n > cap but head+tail cover the whole string -> nothing to elide -> identity.
    s = "A" * 50
    assert truncate_block(s, 10, head=2000, tail=800) == s


# ----------------------------------------------------------------------- cap_artifact


def test_cap_artifact_identity_under_cap():
    assert cap_artifact("hi", 100) == "hi"


def test_cap_artifact_identity_at_boundary():
    s = "B" * 64
    assert cap_artifact(s, 64) == s


def test_cap_artifact_hard_cap_marker():
    out = cap_artifact("A" * 300, 100)
    assert out == "A" * 100 + "\n[200 bytes elided]"


def test_cap_artifact_utf8_boundary_backoff():
    # 'é' == 2 bytes; cap=101 lands on a continuation byte -> backoff to 100.
    out = cap_artifact("é" * 100, 101)  # 200 bytes
    assert out == "é" * 50 + "\n[100 bytes elided]"
    assert out.encode("utf-8").decode("utf-8") == out


# ----------------------------------------------------------------------- elide_base64


def test_elide_base64_data_uri():
    out = elide_base64("pre data:image/png;base64,QUJDREVG post")
    assert out == "pre <base64 image elided 8 bytes> post"


def test_elide_base64_data_uri_with_padding():
    out = elide_base64("x data:x;base64,QUJDRA== y")
    assert out == "x <base64 image elided 8 bytes> y"


def test_elide_base64_long_run():
    out = elide_base64("( " + "A" * 500 + " )")
    assert out == "( <base64 image elided 500 bytes> )"


def test_elide_base64_short_run_untouched():
    assert elide_base64("ABCDabcd1234") == "ABCDabcd1234"


def test_elide_base64_no_base64_identity():
    assert (
        elide_base64("just some prose, nothing to see.")
        == "just some prose, nothing to see."
    )
