#!/usr/bin/env python3
"""Unit tests for the onions-lane envelope guard (index-only, default OFF).

Pure and network-free: the guard is a function of tool name + arguments + the
flag. These pin the hard envelope so a regression that quietly re-opens the lane
fails the build.
"""

from __future__ import annotations

import os
import sys

HUB_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HUB_DIR)

import onions  # noqa: E402


def test_flag_defaults_off():
    assert onions.flag_enabled({}) is False
    assert onions.flag_enabled({"ENABLE_ONIONS": ""}) is False
    assert onions.flag_enabled({"ENABLE_ONIONS": "0"}) is False
    assert onions.flag_enabled({"ENABLE_ONIONS": "false"}) is False
    assert onions.flag_enabled({"ENABLE_ONIONS": "1"}) is True
    assert onions.flag_enabled({"ENABLE_ONIONS": "true"}) is True


def test_requests_onions_detects_category_and_engine():
    assert onions.requests_onions({"categories": "onions"})
    assert onions.requests_onions({"categories": "general,onions"})
    assert onions.requests_onions({"engines": "ahmia"})
    assert onions.requests_onions({"engines": ["ahmia", "google"]})
    assert not onions.requests_onions({"categories": "general"})
    assert not onions.requests_onions({})


def test_is_onion_url():
    assert onions.is_onion_url("http://juhanurmihxlp77nkq76.onion/x")
    assert onions.is_onion_url("juhanurmihxlp77nkq76.onion")
    assert onions.is_onion_url("https://foo.ONION")
    assert not onions.is_onion_url("https://example.com/onion")
    assert not onions.is_onion_url("https://notonion.com")
    assert not onions.is_onion_url("")
    assert not onions.is_onion_url(None)


def test_guard_blocks_onions_category_when_flag_off():
    reason = onions.guard(
        "searxng_web_search", {"query": "x", "categories": "onions"}, enabled=False
    )
    assert reason is not None
    assert "ENABLE_ONIONS=1" in reason
    assert onions.ENVELOPE_DOC in reason


def test_guard_allows_onions_category_when_flag_on():
    assert (
        onions.guard(
            "searxng_web_search", {"query": "x", "categories": "onions"}, enabled=True
        )
        is None
    )


def test_guard_blocks_ahmia_engine_when_flag_off():
    reason = onions.guard(
        "searxng_web_search", {"query": "x", "engines": "ahmia"}, enabled=False
    )
    assert reason is not None


def test_guard_ignores_non_onion_search_regardless_of_flag():
    assert onions.guard("searxng_web_search", {"query": "x"}, enabled=False) is None
    assert (
        onions.guard(
            "searxng_web_search", {"query": "x", "categories": "general"}, enabled=False
        )
        is None
    )


def test_guard_never_lets_web_url_read_fetch_onion_even_with_flag_on():
    for enabled in (False, True):
        reason = onions.guard(
            "web_url_read",
            {"url": "http://juhanurmihxlp77nkq76.onion/search"},
            enabled=enabled,
        )
        assert reason is not None
        assert "FORBIDDEN" in reason
        assert onions.ENVELOPE_DOC in reason


def test_guard_allows_web_url_read_for_clearnet():
    assert (
        onions.guard("web_url_read", {"url": "https://example.com"}, enabled=True)
        is None
    )
