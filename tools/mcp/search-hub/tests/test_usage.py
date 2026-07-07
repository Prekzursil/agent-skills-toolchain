#!/usr/bin/env python3
"""Tests for the on-demand usage parsers (mocked HTTP getter -- no network)."""

from __future__ import annotations

import os
import sys

HUB_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HUB_DIR)

import usage  # noqa: E402


def _getter(status, body):
    """A fake getter returning canned (status, json, raw) regardless of args."""

    def get(_url, _key, _timeout):
        return status, body, "" if body is not None else "err-body"

    return get


def test_firecrawl_remaining_from_data():
    got = usage.firecrawl_usage(
        "k",
        "primary",
        _getter(200, {"success": True, "data": {"remainingCredits": 812}}),
    )
    assert got["ok"] and got["remaining"] == 812 and got["provider"] == "firecrawl"
    assert got["label"] == "primary"


def test_firecrawl_remaining_flat_body():
    got = usage.firecrawl_usage("k", "", _getter(200, {"remainingCredits": 5}))
    assert got["remaining"] == 5


def test_firecrawl_http_error_is_not_ok():
    got = usage.firecrawl_usage("k", "", _getter(402, None))
    assert not got["ok"] and "HTTP 402" in got["error"] and got["remaining"] is None


def test_tavily_plan_plus_paygo_headroom():
    body = {
        "account": {
            "plan_limit": 1000,
            "plan_usage": 400,
            "paygo_limit": 200,
            "paygo_usage": 50,
        }
    }
    got = usage.tavily_usage("k", "primary", _getter(200, body))
    assert got["ok"] and got["remaining"] == (1000 - 400) + (200 - 50)  # 750


def test_tavily_exhausted_is_zero_or_negative():
    body = {"account": {"plan_limit": 1000, "plan_usage": 1000}}
    got = usage.tavily_usage("k", "", _getter(200, body))
    assert got["remaining"] == 0


def test_tavily_no_plan_cap_is_unmetered_none():
    got = usage.tavily_usage("k", "", _getter(200, {"account": {"plan_usage": 5}}))
    assert got["remaining"] is None


def test_exa_is_error_driven_none():
    got = usage.exa_usage("k", "primary")
    assert got["ok"] and got["remaining"] is None and "error-driven" in got["note"]


def test_usage_for_dispatch():
    assert usage.usage_for("exa", "k", "")["provider"] == "exa"
    fc = usage.usage_for(
        "firecrawl", "k", "", _getter(200, {"data": {"remainingCredits": 1}})
    )
    assert fc["remaining"] == 1
    tv = usage.usage_for(
        "tavily",
        "k",
        "",
        _getter(200, {"account": {"plan_limit": 10, "plan_usage": 3}}),
    )
    assert tv["remaining"] == 7
