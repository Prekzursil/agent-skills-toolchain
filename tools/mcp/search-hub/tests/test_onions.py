#!/usr/bin/env python3
"""Unit tests for the onions-lane envelope + ask/modes/tagging (index-only).

Pure and network-free: everything is a function of tool name + arguments +
environ. These pin the hard envelope (no Tor, no .onion fetch), the default-ON
ask-before-search flow, the search modes, the kill switch, and the result
tagging, so a regression that quietly changes behaviour fails the build.
"""

from __future__ import annotations

import os
import sys

HUB_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HUB_DIR)

import onions  # noqa: E402


# --------------------------------------------------------------------------- #
# intent detection + helpers
# --------------------------------------------------------------------------- #
def test_requests_onions_detects_category_and_engine():
    assert onions.requests_onions({"categories": "onions"})
    assert onions.requests_onions({"categories": "general,onions"})
    assert onions.requests_onions({"categories": "onion index"})
    assert onions.requests_onions({"categories": ["general", "onion index"]})
    assert onions.requests_onions({"engines": "ahmia"})
    assert onions.requests_onions({"engines": ["ahmia", "google"]})
    assert not onions.requests_onions({"categories": "general"})
    assert not onions.requests_onions({"engines": "google"})
    assert not onions.requests_onions({})


def test_is_onion_url():
    assert onions.is_onion_url("http://juhanurmihxlp77nkq76.onion/x")
    assert onions.is_onion_url("juhanurmihxlp77nkq76.onion")
    assert onions.is_onion_url("https://foo.ONION")
    assert not onions.is_onion_url("https://example.com/onion")
    assert not onions.is_onion_url("https://notonion.com")
    assert not onions.is_onion_url("")
    assert not onions.is_onion_url(None)


def test_confirm_and_mode_parsing():
    assert onions.is_confirmed({"onion_confirm": True})
    assert onions.is_confirmed({"onion_confirm": "true"})
    assert not onions.is_confirmed({"onion_confirm": "no"})
    assert not onions.is_confirmed({})
    assert onions.selected_mode({"onion_mode": "deepest"}) == "deepest"
    assert onions.selected_mode({"onion_mode": "HIGH"}) == "high"
    assert onions.selected_mode({"onion_mode": "bogus"}) == onions.DEFAULT_MODE
    assert onions.selected_mode({}) == onions.DEFAULT_MODE


def test_kill_switch_default_on():
    assert onions.is_kill_switched({}) is False  # works by default
    assert onions.is_kill_switched({"ENABLE_ONIONS": "1"}) is False
    for off in ("0", "false", "no", "off"):
        assert onions.is_kill_switched({"ENABLE_ONIONS": off}) is True


# --------------------------------------------------------------------------- #
# the decision function (ask / run / forbid / killed / pass)
# --------------------------------------------------------------------------- #
def test_normal_search_passes_through():
    action, payload = onions.onion_decision(
        "searxng_web_search", {"query": "python"}, {}
    )
    assert action == onions.PASS and payload is None


def test_onion_intent_default_asks_before_searching():
    for args in (
        {"query": "x", "engines": "ahmia"},
        {"query": "x", "categories": "onions"},
        {"query": "x", "categories": "onion index"},
    ):
        action, payload = onions.onion_decision("searxng_web_search", args, {})
        assert action == onions.ASK, args
        assert payload["onion_confirmation_required"] is True
        assert "ask the human" in payload["action_required"].lower()
        assert {m["mode"] for m in payload["modes"]} == set(onions.MODES)
        assert onions.ENVELOPE_DOC in payload["envelope_doc"]


def test_confirmed_onion_search_runs_with_mode_applied():
    action, payload = onions.onion_decision(
        "searxng_web_search",
        {
            "query": "leak",
            "engines": "ahmia",
            "onion_confirm": True,
            "onion_mode": "high",
        },
        {},
    )
    assert action == onions.RUN
    searxng_args, mode = payload
    assert mode == "high"
    # Pins the clearnet Ahmia index engine + category, applies breadth, strips control args.
    assert searxng_args["engines"] == "ahmia"
    assert searxng_args["categories"] == onions.ONION_CATEGORY
    assert searxng_args["num_results"] == onions.MODES["high"]["num_results"]
    assert "onion_confirm" not in searxng_args and "onion_mode" not in searxng_args
    assert searxng_args["query"] == "leak"


def test_kill_switch_forces_off_even_when_confirmed():
    action, payload = onions.onion_decision(
        "searxng_web_search",
        {"query": "x", "engines": "ahmia", "onion_confirm": True},
        {"ENABLE_ONIONS": "0"},
    )
    assert action == onions.KILLED
    assert "hard-disabled" in payload


def test_web_url_read_of_onion_is_forbidden_always():
    for env in ({}, {"ENABLE_ONIONS": "1"}, {"ENABLE_ONIONS": "0"}):
        action, payload = onions.onion_decision(
            "web_url_read", {"url": "http://abc.onion/x"}, env
        )
        assert action == onions.FORBID
        assert "FORBIDDEN" in payload and onions.ENVELOPE_DOC in payload


def test_web_url_read_clearnet_passes():
    action, _ = onions.onion_decision(
        "web_url_read", {"url": "https://example.com"}, {}
    )
    assert action == onions.PASS


# --------------------------------------------------------------------------- #
# result tagging (clearly differentiate tor/onion results from normal)
# --------------------------------------------------------------------------- #
def test_tag_onion_response_prepends_banner_and_marker():
    child = {
        "jsonrpc": "2.0",
        "id": 5,
        "result": {
            "content": [{"type": "text", "text": "results..."}],
            "isError": False,
        },
    }
    tagged = onions.tag_onion_response(child, "deepest")
    banner = tagged["result"]["content"][0]["text"]
    assert "DARK-WEB INDEX RESULTS" in banner and "mode=deepest" in banner
    assert "NOT fetched" in banner
    assert tagged["result"]["_onion"]["tor"] is True
    assert tagged["result"]["_onion"]["onion_fetched"] is False
    assert tagged["result"]["_onion"]["mode"] == "deepest"
    # original content preserved after the banner
    assert tagged["result"]["content"][1]["text"] == "results..."
    # input not mutated
    assert child["result"]["content"][0]["text"] == "results..."


def test_prepare_onion_args_defaults_low_mode():
    args = onions.prepare_onion_args({"query": "q", "onion_confirm": True})
    assert args["num_results"] == onions.MODES["low"]["num_results"]
    assert args["engines"] == "ahmia"
