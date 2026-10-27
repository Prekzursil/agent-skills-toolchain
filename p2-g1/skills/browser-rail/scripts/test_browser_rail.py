"""Unit tests for the PURE half of browser_rail.

No browser, no network, no playwright install required. The playwright-touching
half of the module is manually verified (see README.md) and is deliberately not
exercised here -- a mock of Playwright would only assert that the mock works.
"""

from __future__ import annotations

import pytest

import browser_rail
from browser_rail import (
    DEFAULT_CDP_PORTS,
    MIN_SCANNED_PAYLOAD_LEN,
    POST_JSON_JS,
    RAIL_VERBS,
    UPLOAD_TEXT_JS,
    VERB_TABLE,
    AuthSignals,
    PayloadInlinedError,
    assert_payload_not_inlined,
    cdp_http_endpoint,
    cdp_version_endpoint,
    classify_auth,
    domain_matches,
    normalize_domain,
)

# --------------------------------------------------------------------------
# cdp_http_endpoint
# --------------------------------------------------------------------------


def test_cdp_endpoint_defaults_to_loopback():
    # Loopback-only by default: the rail must not expose a debugger to the LAN.
    assert cdp_http_endpoint() == "http://127.0.0.1:9222"


def test_cdp_endpoint_honors_overrides():
    assert cdp_http_endpoint(port=9333, host="localhost") == "http://localhost:9333"


# --------------------------------------------------------------------------
# normalize_domain
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("https://www.Grok.com/chat?x=1", "grok.com"),
        ("grok.com", "grok.com"),
        ("https://grok.com:8443/x", "grok.com"),
        ("https://user:pw@grok.com/x", "grok.com"),
        ("http://localhost:3000/", "localhost"),
        ("https://grok.com./", "grok.com"),
        # Bare host:port must still resolve a host...
        ("localhost:3000", "localhost"),
        # ...while no-authority schemes must resolve to NO host. "about:blank"
        # otherwise parses as host "about", port "blank".
        ("about:blank", ""),
        ("data:text/html,<h1>hi</h1>", ""),
        ("mailto:someone@example.com", ""),
        ("file:///C:/tmp/x.html", ""),
        ("", ""),
        ("   ", ""),
    ],
)
def test_normalize_domain(raw, expected):
    assert normalize_domain(raw) == expected


# --------------------------------------------------------------------------
# domain_matches -- the two guards a naive `domain in url` check fails
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "page_url",
    [
        "https://grok.com/chat",
        "https://www.grok.com/chat",
        "https://api.grok.com/v1",
        "https://a.b.grok.com/",
    ],
)
def test_domain_matches_accepts_domain_and_subdomains(page_url):
    assert domain_matches(page_url, "grok.com") is True


@pytest.mark.parametrize(
    "page_url",
    [
        "https://notgrok.com/chat",  # suffix collision
        "https://evil.com/grok.com",  # domain appears in the PATH
        "https://grok.com.evil.com/",  # domain is a prefix label
        "https://grok.co/",
        "about:blank",
        "",
    ],
)
def test_domain_matches_rejects_lookalikes(page_url):
    assert domain_matches(page_url, "grok.com") is False


def test_domain_matches_rejects_empty_target():
    # An empty target must never match everything.
    assert domain_matches("https://grok.com/", "") is False


def test_domain_matches_accepts_url_as_target():
    assert domain_matches("https://grok.com/chat", "https://grok.com/other") is True


# --------------------------------------------------------------------------
# AuthSignals.both_states_ready -- the both-states discipline, encoded
# --------------------------------------------------------------------------


def test_both_states_ready_requires_evidence_in_each_direction():
    assert AuthSignals(
        logged_out_names=("Sign in",), logged_in_names=("Sign out",)
    ).both_states_ready
    assert AuthSignals(
        logged_out_url_substrings=("/login",), logged_in_names=("Sign out",)
    ).both_states_ready


@pytest.mark.parametrize(
    "signals",
    [
        AuthSignals(),
        AuthSignals(logged_out_names=("Sign in",)),  # negative only
        AuthSignals(logged_in_names=("Sign out",)),  # positive only
    ],
)
def test_both_states_ready_false_when_one_direction_missing(signals):
    assert signals.both_states_ready is False


# --------------------------------------------------------------------------
# classify_auth
# --------------------------------------------------------------------------

SIGNALS = AuthSignals(
    logged_out_url_substrings=("/login", "/sign-in"),
    logged_out_names=("Sign in", "Create account"),
    logged_in_names=("Sign out", "New chat"),
)


def test_classify_auth_detects_logged_out_by_url():
    verdict = classify_auth("https://grok.com/login?next=/chat", ["New chat"], SIGNALS)
    assert verdict.authed is False
    assert verdict.reason == "logged-out-url"
    assert verdict.evidence == "/login"


def test_classify_auth_detects_logged_out_by_control():
    verdict = classify_auth("https://grok.com/", ["Sign in", "Pricing"], SIGNALS)
    assert verdict.authed is False
    assert verdict.reason == "logged-out-control"


def test_classify_auth_detects_logged_in_by_control():
    verdict = classify_auth("https://grok.com/chat", ["New chat", "Help"], SIGNALS)
    assert verdict.authed is True
    assert verdict.reason == "logged-in-control"
    assert verdict.known is True


def test_classify_auth_returns_unknown_when_nothing_fires():
    # Silence is NOT a logged-out verdict. An empty page must read UNKNOWN.
    verdict = classify_auth("https://grok.com/", [], SIGNALS)
    assert verdict.authed is None
    assert verdict.reason == "no-signal-fired"
    assert verdict.known is False


def test_classify_auth_is_case_insensitive():
    verdict = classify_auth("https://grok.com/", ["SIGN OUT"], SIGNALS)
    assert verdict.authed is True


def test_classify_auth_prefers_logged_out_when_both_appear():
    # Stated error-direction bias: ambiguity resolves to "not authed", because a
    # false "authed" is the expensive mistake.
    verdict = classify_auth("https://grok.com/", ["Sign in", "Sign out"], SIGNALS)
    assert verdict.authed is False


# --------------------------------------------------------------------------
# assert_payload_not_inlined
# --------------------------------------------------------------------------


def test_assert_payload_not_inlined_passes_when_content_is_an_arg():
    assert_payload_not_inlined(UPLOAD_TEXT_JS, {"text": "a long secret payload body"})


def test_assert_payload_not_inlined_raises_when_content_is_concatenated():
    payload = "a long secret payload body"
    bad_js = "(arg) => { return '" + payload + "'; }"
    with pytest.raises(PayloadInlinedError, match="pass it as the evaluate"):
        assert_payload_not_inlined(bad_js, payload)


def test_assert_payload_not_inlined_scans_nested_structures():
    payload = "deeply nested payload text"
    bad_js = "(arg) => '" + payload + "'"
    with pytest.raises(PayloadInlinedError):
        assert_payload_not_inlined(bad_js, {"outer": [{"inner": payload}]})


def test_assert_payload_not_inlined_ignores_non_string_leaves():
    assert_payload_not_inlined("(arg) => arg.n", {"n": 5, "ok": True, "z": None})


def test_assert_payload_not_inlined_skips_short_payloads_by_design():
    # DETECTOR WEAKNESS, asserted so it stays visible: a payload shorter than
    # MIN_SCANNED_PAYLOAD_LEN is not scanned even when it IS inlined.
    short = "x" * (MIN_SCANNED_PAYLOAD_LEN - 1)
    assert_payload_not_inlined(f"(arg) => '{short}'", short)

    exactly_long_enough = "y" * MIN_SCANNED_PAYLOAD_LEN
    with pytest.raises(PayloadInlinedError):
        assert_payload_not_inlined(
            f"(arg) => '{exactly_long_enough}'", exactly_long_enough
        )


# --------------------------------------------------------------------------
# The shipped JS constants must themselves obey the contract
# --------------------------------------------------------------------------


@pytest.mark.parametrize("js", [UPLOAD_TEXT_JS, POST_JSON_JS])
def test_shipped_js_reads_everything_from_the_arg(js):
    assert "arg." in js


def test_post_json_js_sends_credentials():
    # Reusing the page's own session is the whole point of the rail.
    assert "credentials: 'include'" in POST_JSON_JS


# --------------------------------------------------------------------------
# cdp_version_endpoint + DEFAULT_CDP_PORTS -- pure session-probe helpers
# --------------------------------------------------------------------------


def test_cdp_version_endpoint_defaults_to_loopback():
    assert cdp_version_endpoint() == "http://127.0.0.1:9222/json/version"


def test_cdp_version_endpoint_honors_overrides():
    assert (
        cdp_version_endpoint(port=9333, host="localhost")
        == "http://localhost:9333/json/version"
    )


def test_default_cdp_ports_cover_both_rail_profiles():
    # The primary automation profile plus the conventional second profile.
    assert DEFAULT_CDP_PORTS == (9222, 9333)


# --------------------------------------------------------------------------
# VERB_TABLE -- the Browser Use naming borrow, checkable without a browser
# --------------------------------------------------------------------------

# The 13 borrowed verbs, spelled out so a rename or a dropped verb fails loudly
# rather than silently shrinking the surface (fan-out contract: enumerate, never
# ship a bare set).
EXPECTED_BROWSER_USE_VERBS = frozenset(
    {
        "browser_navigate",
        "browser_click",
        "browser_type",
        "browser_get_state",
        "browser_scroll",
        "browser_go_back",
        "browser_list_tabs",
        "browser_switch_tab",
        "browser_close_tab",
        "browser_extract_content",
        "browser_list_sessions",
        "browser_close_session",
        "browser_close_all",
    }
)

# The nested-agent verb Browser Use ships that the rail deliberately does NOT
# adopt: the rail is a primitive layer, not an agent runtime.
EXCLUDED_VERB = "retry_with_browser_use_agent"


def test_verb_table_has_exactly_the_thirteen_browser_use_verbs():
    assert set(VERB_TABLE) == EXPECTED_BROWSER_USE_VERBS
    assert len(VERB_TABLE) == 13


def test_retry_agent_verb_is_absent_everywhere():
    # The one Browser Use verb the rail refuses on purpose must not sneak back in
    # through either table or as a module attribute.
    assert EXCLUDED_VERB not in VERB_TABLE
    assert EXCLUDED_VERB not in RAIL_VERBS
    assert not hasattr(browser_rail, EXCLUDED_VERB)


@pytest.mark.parametrize("verb", sorted(EXPECTED_BROWSER_USE_VERBS))
def test_each_canonical_verb_is_importable_and_callable(verb):
    # The browser_* name a caller relies on must resolve on the module...
    assert callable(getattr(browser_rail, verb))


@pytest.mark.parametrize("verb", sorted(VERB_TABLE))
def test_each_verb_table_target_resolves(verb):
    # ...and the function VERB_TABLE points at must exist and be callable, so the
    # alias layer can never dangle. No browser is needed to check resolution.
    assert callable(getattr(browser_rail, VERB_TABLE[verb]))


def test_navigate_aliases_the_existing_tab_reuse_function():
    # browser_navigate is an ALIAS, not a reimplementation: it must BE
    # find_or_open_page so tab reuse is preserved.
    assert VERB_TABLE["browser_navigate"] == "find_or_open_page"
    assert browser_rail.browser_navigate is browser_rail.find_or_open_page


@pytest.mark.parametrize("verb", sorted(RAIL_VERBS))
def test_rail_specific_verbs_alias_their_implementations(verb):
    # The four rail-only verbs get browser_* aliases too, each bound to its
    # original implementation so the whole surface reads uniformly.
    assert getattr(browser_rail, verb) is getattr(browser_rail, RAIL_VERBS[verb])
