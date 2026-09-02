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
    # VormWeb (G-7) is a lane engine too: naming it alone is onion intent.
    assert onions.requests_onions({"engines": "vormweb"})
    assert onions.requests_onions({"engines": ["VormWeb", "duckduckgo"]})
    assert not onions.requests_onions({"categories": "general"})
    assert not onions.requests_onions({"engines": "google"})
    assert not onions.requests_onions({})


def test_lane_engine_set_is_exactly_ahmia_and_vormweb():
    # Not Evil / Torch etc. stay excluded (envelope re-evaluation trigger).
    assert onions.ONION_ENGINES == frozenset({"ahmia", "vormweb"})
    assert onions.ONION_ENGINE_ORDER == ("ahmia", "vormweb")


def test_requested_onion_engines_keeps_lane_order_and_drops_others():
    assert onions.requested_onion_engines({"engines": "vormweb,ahmia,google"}) == [
        "ahmia",
        "vormweb",
    ]
    assert onions.requested_onion_engines({"engines": "vormweb"}) == ["vormweb"]
    assert onions.requested_onion_engines({"categories": "onion index"}) == []
    assert onions.requested_onion_engines({}) == []


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
# engine set: ahmia + vormweb by default, ENABLE_VORMWEB per-engine kill switch
# --------------------------------------------------------------------------- #
def test_default_engines_include_ahmia_and_vormweb():
    # G-7: VormWeb is DEFAULT-ON. Unset or truthy ENABLE_VORMWEB keeps it.
    for env in ({}, {"ENABLE_VORMWEB": "1"}, {"ENABLE_VORMWEB": "true"}):
        assert onions.enabled_engines(env) == ["ahmia", "vormweb"], env
    assert onions.is_engine_kill_switched("vormweb", {}) is False
    # Ahmia is the lane anchor: it has no per-engine switch (ENABLE_ONIONS kills it).
    assert onions.is_engine_kill_switched("ahmia", {"ENABLE_VORMWEB": "0"}) is False


def test_vormweb_kill_switch_drops_it_from_the_default_engine_list():
    for off in ("0", "false", "no", "off"):
        env = {"ENABLE_VORMWEB": off}
        assert onions.is_engine_kill_switched("vormweb", env) is True
        assert onions.enabled_engines(env) == ["ahmia"]
    # A category-only (no explicit engine) confirmed search then runs Ahmia only.
    action, payload = onions.onion_decision(
        "searxng_web_search",
        {"query": "x", "categories": "onion index", "onion_confirm": True},
        {"ENABLE_VORMWEB": "0"},
    )
    assert action == onions.RUN
    assert payload[0]["engines"] == "ahmia"


def test_vormweb_kill_switch_refuses_an_explicit_vormweb_request():
    for engines in ("vormweb", "ahmia,vormweb", ["vormweb", "google"]):
        for confirmed in (False, True):
            args = {"query": "x", "engines": engines}
            if confirmed:
                args["onion_confirm"] = True
            action, payload = onions.onion_decision(
                "searxng_web_search", args, {"ENABLE_VORMWEB": "0"}
            )
            assert action == onions.KILLED, (engines, confirmed)
            # Truthful: names the engine, the flag, and what still works.
            assert "vormweb" in payload and "ENABLE_VORMWEB=0" in payload
            assert "ahmia" in payload and onions.ENVELOPE_DOC in payload
    # Explicit Ahmia is untouched by the VormWeb switch.
    action, _ = onions.onion_decision(
        "searxng_web_search",
        {"query": "x", "engines": "ahmia"},
        {"ENABLE_VORMWEB": "0"},
    )
    assert action == onions.ASK


def test_enable_onions_zero_still_kills_the_whole_lane_including_vormweb():
    for engines in ("vormweb", "ahmia,vormweb"):
        action, payload = onions.onion_decision(
            "searxng_web_search",
            {"query": "x", "engines": engines, "onion_confirm": True},
            {"ENABLE_ONIONS": "0", "ENABLE_VORMWEB": "1"},
        )
        assert action == onions.KILLED
        assert "ENABLE_ONIONS=0" in payload


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
        {"query": "x", "engines": "vormweb"},  # VormWeb alone = same gate
        {"query": "x", "engines": "ahmia,vormweb"},
        {"query": "x", "categories": "onions"},
        {"query": "x", "categories": "onion index"},
    ):
        action, payload = onions.onion_decision("searxng_web_search", args, {})
        assert action == onions.ASK, args
        assert payload["onion_confirmation_required"] is True
        assert "ask the human" in payload["action_required"].lower()
        assert {m["mode"] for m in payload["modes"]} == set(onions.MODES)
        assert onions.ENVELOPE_DOC in payload["envelope_doc"]


def test_confirmation_request_names_the_engines_it_will_query():
    ask = onions.onion_decision(
        "searxng_web_search", {"query": "x", "categories": "onion index"}, {}
    )[1]
    assert ask["engines"] == ["ahmia", "vormweb"]  # default set, lane order
    assert "VormWeb" in ask["scope"] and "Ahmia" in ask["scope"]
    ask = onions.onion_decision(
        "searxng_web_search", {"query": "x", "engines": "vormweb"}, {}
    )[1]
    assert ask["engines"] == ["vormweb"]
    ask = onions.onion_decision(
        "searxng_web_search",
        {"query": "x", "categories": "onion index"},
        {"ENABLE_VORMWEB": "0"},
    )[1]
    assert ask["engines"] == ["ahmia"]
    assert "VormWeb" not in ask["scope"]  # Ahmia-only ask carries no VormWeb text


def test_confirmation_request_carries_the_vormweb_caveats_when_it_will_query_it():
    # G-7 caveats: documented at the point of use, never silent.
    for args in (
        {"query": "x", "engines": "vormweb"},
        {"query": "x", "categories": "onion index"},
    ):
        ask = onions.onion_decision("searxng_web_search", args, {})[1]
        assert "consent unresolved" in ask["scope"], args
        assert "self-declared" in ask["scope"], args
        assert "engines=vormweb" in ask["how_to_confirm"]


def test_confirmed_vormweb_search_runs_pinned_to_vormweb_only():
    action, payload = onions.onion_decision(
        "searxng_web_search",
        {
            "query": "privacy",
            "engines": "vormweb",
            "onion_confirm": True,
            "onion_mode": "medium",
        },
        {},
    )
    assert action == onions.RUN
    searxng_args, mode = payload
    assert mode == "medium"
    # Requesting ONE engine pins that engine only; same category + breadth rules.
    assert searxng_args["engines"] == "vormweb"
    assert searxng_args["categories"] == onions.ONION_CATEGORY
    assert searxng_args["num_results"] == onions.MODES["medium"]["num_results"]
    assert "onion_confirm" not in searxng_args and "onion_mode" not in searxng_args


def test_confirmed_category_only_search_runs_both_engines_in_lane_order():
    action, payload = onions.onion_decision(
        "searxng_web_search",
        {"query": "x", "categories": "onion index", "onion_confirm": True},
        {},
    )
    assert action == onions.RUN
    assert payload[0]["engines"] == "ahmia,vormweb"
    # Naming both explicitly (any order) is the same as the default set.
    action, payload = onions.onion_decision(
        "searxng_web_search",
        {"query": "x", "engines": "vormweb,ahmia", "onion_confirm": True},
        {},
    )
    assert action == onions.RUN and payload[0]["engines"] == "ahmia,vormweb"


def test_non_onion_engines_are_dropped_from_a_confirmed_onion_search():
    # As before with ahmia: the lane pins to its INDEX engines, never mixes in
    # clearnet general engines under the onion banner.
    action, payload = onions.onion_decision(
        "searxng_web_search",
        {"query": "x", "engines": "vormweb,google", "onion_confirm": True},
        {},
    )
    assert action == onions.RUN and payload[0]["engines"] == "vormweb"


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
    # Unchanged by the VormWeb addition: no flag combination opens a .onion fetch.
    for env in (
        {},
        {"ENABLE_ONIONS": "1"},
        {"ENABLE_ONIONS": "0"},
        {"ENABLE_VORMWEB": "1"},
        {"ENABLE_VORMWEB": "0"},
        {"ENABLE_ONIONS": "1", "ENABLE_VORMWEB": "1"},
    ):
        action, payload = onions.onion_decision(
            "web_url_read", {"url": "http://abc.onion/x"}, env
        )
        assert action == onions.FORBID, env
        assert "FORBIDDEN" in payload and onions.ENVELOPE_DOC in payload
    # A VormWeb-shaped index hit (a v3 https .onion URL string) is refused too.
    v3_host = "protonmailrmez3lotccipshtkleegetolb73fuirgj7r4o4vfu7ozyd.onion"
    action, _ = onions.onion_decision(
        "web_url_read", {"url": f"https://{v3_host}/"}, {}
    )
    assert action == onions.FORBID


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
    tagged = onions.tag_onion_response(child, "deepest", {"engines": "ahmia"})
    banner = tagged["result"]["content"][0]["text"]
    assert "DARK-WEB INDEX RESULTS" in banner and "mode=deepest" in banner
    assert "NOT fetched" in banner
    assert tagged["result"]["_onion"]["tor"] is True
    assert tagged["result"]["_onion"]["onion_fetched"] is False
    assert tagged["result"]["_onion"]["mode"] == "deepest"
    assert tagged["result"]["_onion"]["lane"] == "ahmia-index"  # unchanged value
    assert tagged["result"]["_onion"]["engines"] == ["ahmia"]
    # original content preserved after the banner
    assert tagged["result"]["content"][1]["text"] == "results..."
    # input not mutated
    assert child["result"]["content"][0]["text"] == "results..."


def _child_response() -> dict:
    return {
        "jsonrpc": "2.0",
        "id": 6,
        "result": {"content": [{"type": "text", "text": "hits"}], "isError": False},
    }


def test_tag_onion_response_lane_follows_the_engines_searched():
    # The forwarded (pinned) SearXNG args tell the tagger which INDEX answered.
    tagged = onions.tag_onion_response(_child_response(), "low", {"engines": "vormweb"})
    marker = tagged["result"]["_onion"]
    assert marker["lane"] == "vormweb-index"  # mirrors "ahmia-index"
    assert marker["engines"] == ["vormweb"]
    assert marker["tor"] is True and marker["onion_fetched"] is False
    assert marker["verified"] is False  # VormWeb's own "Verified" badge is NOT ours
    banner = tagged["result"]["content"][0]["text"]
    assert "DARK-WEB INDEX RESULTS" in banner and "VormWeb" in banner
    assert "NOT fetched" in banner

    tagged = onions.tag_onion_response(
        _child_response(), "high", {"engines": "ahmia,vormweb"}
    )
    assert tagged["result"]["_onion"]["lane"] == "ahmia+vormweb-index"
    assert tagged["result"]["_onion"]["engines"] == ["ahmia", "vormweb"]
    banner = tagged["result"]["content"][0]["text"]
    assert "Ahmia" in banner and "VormWeb" in banner


def test_tag_onion_response_without_args_is_truthfully_generic():
    # No forwarded args (legacy caller): never claim a specific index.
    tagged = onions.tag_onion_response(_child_response(), "low")
    assert tagged["result"]["_onion"]["lane"] == "onion-index"
    assert tagged["result"]["_onion"]["engines"] == []
    assert "DARK-WEB INDEX RESULTS" in tagged["result"]["content"][0]["text"]


def test_lane_label():
    assert onions.lane_label(["ahmia"]) == "ahmia-index"
    assert onions.lane_label(["vormweb"]) == "vormweb-index"
    assert onions.lane_label(["ahmia", "vormweb"]) == "ahmia+vormweb-index"
    assert onions.lane_label([]) == "onion-index"


def test_prepare_onion_args_defaults_low_mode_and_both_engines():
    args = onions.prepare_onion_args({"query": "q", "onion_confirm": True})
    assert args["num_results"] == onions.MODES["low"]["num_results"]
    # No explicit engine -> the DEFAULT set (G-7: VormWeb default-on), lane order.
    assert args["engines"] == "ahmia,vormweb"
    # An explicit resolved list is honoured verbatim (what onion_decision passes).
    args = onions.prepare_onion_args({"query": "q"}, ["vormweb"])
    assert args["engines"] == "vormweb"
