"""Tests for searxng_config — the pure settings.yml transform.

The fixture mirrors the SHAPE of the owner's live `D:\\searxng\\settings.yml` (measured
2026-07-24) with a PLACEHOLDER secret. The real `secret_key` is never committed.
"""

from __future__ import annotations

import pytest
import yaml

from searxng_config import (
    BEGIN_MARKER,
    END_MARKER,
    REGIONAL_ENGINES,
    ConflictError,
    apply_block,
    enabled_specs,
    find_top_level_key,
    has_managed_block,
    remove_block,
    render_engines_block,
    unified_diff,
)

LIVE_SHAPE = """# SearXNG local-first meta-search instance
use_default_settings: true

server:
  secret_key: "PLACEHOLDER_NOT_A_REAL_KEY"
  limiter: false
  public_instance: false

search:
  formats:
    - html
    - json

ui:
  static_use_hash: true
"""


# --------------------------------------------------------------------------
# the measured engine table
# --------------------------------------------------------------------------


def test_enabled_specs_are_only_the_measured_working_ones() -> None:
    names = {s.name for s in enabled_specs()}
    assert names == {
        "yandex",
        "quark",
        "360search",
        "baidu kaifa",
        "naver news",
        "seznam",
        "mojeek",
    }


def test_engines_measured_broken_are_never_enabled() -> None:
    """Regression guard: these failed a live probe and must stay out of the block."""
    enabled = {s.name for s in enabled_specs()}
    for broken in ("baidu", "sogou", "naver", "yahoo", "qwant"):
        assert broken not in enabled


def test_broken_engines_are_retained_with_their_failure_mode() -> None:
    """Deleting them would lose why they are off, and invite a silent re-enable."""
    by_name = {s.name: s for s in REGIONAL_ENGINES}
    assert by_name["baidu"].status == "blocked"
    assert by_name["naver"].status == "silent-fail"
    assert by_name["yahoo"].status == "broken"
    assert all(s.detail for s in REGIONAL_ENGINES)


def test_slow_cn_engines_carry_a_raised_timeout() -> None:
    """Measured: a quark/360search fan-out took 14.75s. A default timeout drops them."""
    by_name = {s.name: s for s in REGIONAL_ENGINES}
    assert by_name["quark"].timeout >= 10.0
    assert by_name["360search"].timeout >= 10.0


def test_works_property_tracks_status() -> None:
    by_name = {s.name: s for s in REGIONAL_ENGINES}
    assert by_name["yandex"].works is True
    assert by_name["sogou"].works is False


# --------------------------------------------------------------------------
# render_engines_block
# --------------------------------------------------------------------------


def test_rendered_block_is_valid_yaml() -> None:
    """A malformed block takes the owner's search down — parse it, do not eyeball it."""
    parsed = yaml.safe_load(render_engines_block())
    assert isinstance(parsed, dict)
    assert "engines" in parsed


def test_rendered_block_enables_exactly_the_working_engines() -> None:
    parsed = yaml.safe_load(render_engines_block())
    listed = {e["name"] for e in parsed["engines"]}
    assert listed == {s.name for s in enabled_specs()}
    assert all(e["disabled"] is False for e in parsed["engines"])
    assert all(e["timeout"] > 0 for e in parsed["engines"])


def test_rendered_block_is_wrapped_in_managed_markers() -> None:
    block = render_engines_block()
    assert block.startswith(BEGIN_MARKER)
    assert block.rstrip().endswith(END_MARKER)


def test_rendered_block_documents_the_broken_engines_as_comments() -> None:
    block = render_engines_block()
    for broken in ("baidu", "sogou", "naver", "yahoo", "qwant"):
        assert broken in block
    parsed = yaml.safe_load(block)
    # ...but they must be inert: present as prose, absent from the parsed mapping
    assert "sogou" not in {e["name"] for e in parsed["engines"]}


def test_rendered_block_records_the_bang_shortcuts() -> None:
    """The bang is the zero-config route; losing it loses the headline capability."""
    block = render_engines_block()
    assert "!yd" in block
    assert "!qk" in block


def test_render_with_no_broken_engines_omits_the_comment_footer() -> None:
    specs = enabled_specs()
    block = render_engines_block(specs)
    assert "left off deliberately" not in block
    assert yaml.safe_load(block)["engines"]


def test_render_with_only_broken_engines_yields_an_empty_engine_list() -> None:
    broken = tuple(s for s in REGIONAL_ENGINES if not s.works)
    parsed = yaml.safe_load(render_engines_block(broken))
    assert parsed["engines"] is None


# --------------------------------------------------------------------------
# find_top_level_key — the duplicate-key guard
# --------------------------------------------------------------------------


def test_find_top_level_key_locates_an_unindented_key() -> None:
    assert find_top_level_key(LIVE_SHAPE, "server") == 4
    assert find_top_level_key(LIVE_SHAPE, "use_default_settings") == 2


def test_find_top_level_key_ignores_indented_occurrences() -> None:
    assert find_top_level_key(LIVE_SHAPE, "formats") is None
    assert find_top_level_key(LIVE_SHAPE, "limiter") is None


def test_find_top_level_key_absent() -> None:
    assert find_top_level_key(LIVE_SHAPE, "engines") is None


def test_find_top_level_key_ignores_the_managed_block() -> None:
    """Our own block must not be mistaken for a pre-existing user key."""
    applied = apply_block(LIVE_SHAPE, render_engines_block())
    assert find_top_level_key(applied, "engines") is None


def test_find_top_level_key_tolerates_whitespace_before_the_colon() -> None:
    assert find_top_level_key("engines :\n  - name: x\n", "engines") == 1


# --------------------------------------------------------------------------
# apply / remove / diff
# --------------------------------------------------------------------------


def test_apply_block_appends_and_keeps_the_original_content() -> None:
    out = apply_block(LIVE_SHAPE, render_engines_block())
    assert LIVE_SHAPE.rstrip() in out
    assert has_managed_block(out)


def test_applied_file_is_valid_yaml_with_both_the_old_and_new_keys() -> None:
    parsed = yaml.safe_load(apply_block(LIVE_SHAPE, render_engines_block()))
    assert parsed["use_default_settings"] is True
    assert parsed["search"]["formats"] == ["html", "json"]
    assert {e["name"] for e in parsed["engines"]} == {s.name for s in enabled_specs()}


def test_apply_block_is_idempotent() -> None:
    once = apply_block(LIVE_SHAPE, render_engines_block())
    twice = apply_block(once, render_engines_block())
    assert once == twice


def test_apply_block_refuses_a_pre_existing_engines_key() -> None:
    """A second top-level `engines:` is invalid YAML — refuse, never guess a merge."""
    hostile = LIVE_SHAPE + "\nengines:\n  - name: google\n    disabled: true\n"
    with pytest.raises(ConflictError, match="already defines a top-level 'engines:'"):
        apply_block(hostile, render_engines_block())


def test_apply_block_adds_a_missing_trailing_newline() -> None:
    out = apply_block("use_default_settings: true", render_engines_block())
    assert "use_default_settings: true\n" in out
    assert yaml.safe_load(out)["use_default_settings"] is True


def test_apply_block_on_empty_input() -> None:
    out = apply_block("", render_engines_block())
    assert has_managed_block(out)
    assert yaml.safe_load(out)["engines"]


def test_remove_block_restores_the_original_bytes() -> None:
    applied = apply_block(LIVE_SHAPE, render_engines_block())
    assert remove_block(applied) == LIVE_SHAPE + "\n"


def test_remove_block_is_a_no_op_without_a_block() -> None:
    assert remove_block(LIVE_SHAPE) == LIVE_SHAPE


def test_remove_block_preserves_content_after_the_block() -> None:
    """The block is not guaranteed to be last — anything after it must survive.

    If the END_MARKER did not clear the in-block state, every line after the block would
    be swallowed: silent data loss in the owner's settings.yml. (Caught by the mutation
    check; every earlier test happened to put the block at EOF.)
    """
    text = apply_block(LIVE_SHAPE, render_engines_block()) + "\ntrailing_key: 1\n"
    out = remove_block(text)
    assert "trailing_key: 1" in out
    assert BEGIN_MARKER not in out
    assert END_MARKER not in out
    assert yaml.safe_load(out)["trailing_key"] == 1


def test_find_top_level_key_sees_a_key_after_the_managed_block() -> None:
    """The duplicate-key guard must keep looking past the end of our own block."""
    text = apply_block(LIVE_SHAPE, render_engines_block())
    text += "\nengines:\n  - name: google\n    disabled: true\n"
    assert find_top_level_key(text, "engines") is not None


def test_apply_block_refuses_a_conflicting_key_placed_after_the_block() -> None:
    text = apply_block(LIVE_SHAPE, render_engines_block())
    text += "\nengines:\n  - name: google\n    disabled: true\n"
    with pytest.raises(ConflictError):
        apply_block(text, render_engines_block())


def test_has_managed_block_needs_both_markers() -> None:
    assert has_managed_block(LIVE_SHAPE) is False
    assert has_managed_block(LIVE_SHAPE + BEGIN_MARKER) is False
    assert has_managed_block(LIVE_SHAPE + BEGIN_MARKER + "\n" + END_MARKER) is True


def test_apply_then_remove_round_trips_through_yaml() -> None:
    applied = apply_block(LIVE_SHAPE, render_engines_block())
    assert yaml.safe_load(remove_block(applied)) == yaml.safe_load(LIVE_SHAPE)


def test_unified_diff_shows_the_change_and_is_empty_when_identical() -> None:
    applied = apply_block(LIVE_SHAPE, render_engines_block())
    diff = unified_diff(LIVE_SHAPE, applied)
    assert "+engines:" in diff
    assert "a/settings.yml" in diff
    assert unified_diff(LIVE_SHAPE, LIVE_SHAPE) == ""


def test_unified_diff_honours_a_custom_path_label() -> None:
    assert "a/custom.yml" in unified_diff("a\n", "b\n", path="custom.yml")
