#!/usr/bin/env python3
"""Tests for provider specs + the exhaustion-signal classifier (402 vs 429).

Pure, mocked: no live keys, no network -- just canned child response dicts fed
through ``providers.classify`` for each provider's rules.
"""

from __future__ import annotations

import os
import sys

HUB_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HUB_DIR)

import providers  # noqa: E402


def _spec(platform: str) -> providers.ProviderSpec:
    return {s.platform: s for s in providers.default_providers()}[platform]


def _iserror(text: str) -> dict:
    return {"result": {"isError": True, "content": [{"type": "text", "text": text}]}}


def _rpc_error(message: str, data: str = "") -> dict:
    return {"error": {"code": -32000, "message": message, "data": data}}


# --------------------------------------------------------------------------- #
# default_providers wiring: verified package/env facts
# --------------------------------------------------------------------------- #
def test_default_providers_env_and_cmds():
    specs = {s.platform: s for s in providers.default_providers()}
    assert specs["exa"].key_env == "EXA_API_KEY"
    assert specs["tavily"].key_env == "TAVILY_API_KEY"
    assert specs["firecrawl"].key_env == "FIRECRAWL_API_KEY"
    assert specs["exa"].cmd == ("cmd", "/c", "npx", "-y", "exa-mcp-server")
    assert specs["tavily"].cmd == ("cmd", "/c", "npx", "-y", "tavily-mcp@latest")
    assert specs["firecrawl"].cmd == ("cmd", "/c", "npx", "-y", "firecrawl-mcp@latest")
    assert {s.prefix for s in specs.values()} == {"ex", "tv", "fc"}
    # Only Exa lacks a usage endpoint (error-driven only).
    assert specs["exa"].usage_url == "" and specs["exa"].usage_kind == ""
    assert specs["tavily"].usage_url.endswith("/usage")
    assert specs["firecrawl"].usage_url.endswith("/credit-usage")


# --------------------------------------------------------------------------- #
# error_text extraction (both MCP error shapes)
# --------------------------------------------------------------------------- #
def test_error_text_from_both_shapes():
    assert "Insufficient" in providers.error_text(_iserror("Insufficient credits"))
    assert "boom" in providers.error_text(_rpc_error("boom", "detail"))
    assert (
        providers.error_text({"result": {"content": [{"type": "text", "text": "ok"}]}})
        == ""
    )
    assert providers.error_text({"result": {}}) == ""


def test_retry_after_parsing():
    assert providers.retry_after_seconds("... Retry-After: 42 ...") == 42
    assert providers.retry_after_seconds("retry after 7 seconds") == 7
    assert providers.retry_after_seconds("no hint here") is None


# --------------------------------------------------------------------------- #
# per-provider classification
# --------------------------------------------------------------------------- #
def test_firecrawl_402_exhausted_429_rate():
    fc = _spec("firecrawl")
    sig, _ = providers.classify(fc, _iserror("HTTP 402: Insufficient credits"))
    assert sig == providers.EXHAUSTED
    sig, retry = providers.classify(fc, _iserror("429 rate limit, Retry-After: 30"))
    assert sig == providers.RATE_LIMITED and retry == 30


def test_exa_tag_exhausted_and_429_pure_rate():
    ex = _spec("exa")
    for tag in ("NO_MORE_CREDITS", "API_KEY_BUDGET_EXCEEDED"):
        sig, _ = providers.classify(ex, _rpc_error(f"Exa error: {tag}"))
        assert sig == providers.EXHAUSTED, tag
    # Exa 429 must NOT be ambiguous -> pure rate limit (never rotate).
    sig, _ = providers.classify(ex, _iserror("429 Too Many Requests"))
    assert sig == providers.RATE_LIMITED


def test_tavily_429_is_ambiguous_but_explicit_quota_is_exhausted():
    tv = _spec("tavily")
    sig, _ = providers.classify(tv, _iserror("429 rate limit"))
    assert sig == providers.AMBIGUOUS  # resolved later via /usage probe
    sig, _ = providers.classify(tv, _iserror("usage limit exceeded for your plan"))
    assert sig == providers.EXHAUSTED


def test_clean_result_passes():
    for platform in ("exa", "tavily", "firecrawl"):
        sig, retry = providers.classify(
            _spec(platform), {"result": {"content": [{"type": "text", "text": "hi"}]}}
        )
        assert sig == providers.PASS and retry is None


def test_exhaust_wins_over_rate_when_both_present():
    # A message mentioning both 402 and 429: hard-exhaustion must win.
    fc = _spec("firecrawl")
    sig, _ = providers.classify(
        fc, _iserror("402 Insufficient credits (was 429 earlier)")
    )
    assert sig == providers.EXHAUSTED
