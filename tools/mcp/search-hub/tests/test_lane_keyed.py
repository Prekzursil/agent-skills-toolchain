#!/usr/bin/env python3
"""Unit tests for ``lane_keyed``: the keyed search-API lane (platform ``keyed``,
twelve vendors behind ONE ``KeyedSearchAdapter`` base, opt-in per vendor, hard
spend cap, secrets by env NAME only).

Network-free: the ``adapters.HeaderCaller`` is the stdlib fake router in
``fake_keyed_backends`` (one fake for all twelve vendors, keyed on the first path
segment; the synthetic keys are ``X-Fake-Key-<vendor>``, never real). Pins: the
opt-in contract (flag AND key, per vendor; DataForSEO needs login AND password),
``lanes.build_lane`` wiring and the ValueError degradation for a bad cap value,
the auth PLACEMENT per vendor as seen on the wire (header / query / basic) and
that the key is nowhere else, the scrubbing of a key a vendor echoes back in a
401/403 body, one happy-path normalisation per tool, the 402 / 429 (Retry-After
relayed) / 5xx / non-JSON / unrecognised-200 mappings, argument validation with
NO request and NO reservation, the daily budget and the GLOBAL monthly cap with
their reset times, the atomic ledger write, corrupt-ledger recovery (renamed
aside, reported once) and the unwritable-ledger refusal. One test uses a real
loopback socket with the default header-aware urllib caller.
"""

from __future__ import annotations

import ast
import base64
import json
import os
import sys
import threading
from datetime import datetime, timedelta, timezone

import pytest

HUB_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HUB_DIR)
sys.path.insert(0, TESTS_DIR)

import adapters  # noqa: E402
import lane_keyed as lk  # noqa: E402
import lanes  # noqa: E402

import fake_keyed_backends as fake  # noqa: E402

NOW = datetime(2026, 9, 2, 7, 15, 0, tzinfo=timezone.utc)
DAILY_RESET = "2026-09-03T00:00:00Z"
MONTHLY_RESET = "2026-10-01T00:00:00Z"
FAKE_BASE = "http://fake.keyed.invalid"

SAMPLE_CALLS: dict[str, tuple[str, dict]] = {
    "brave": ("brave_web_search", {"q": "mcp servers"}),
    "kagi": ("kagi_search", {"q": "mcp servers"}),
    "linkup": ("linkup_search", {"q": "mcp servers"}),
    "mojeek": ("mojeek_search", {"q": "mcp servers"}),
    "youcom": ("youcom_search", {"q": "mcp servers"}),
    "perplexity": ("perplexity_search", {"q": "mcp servers"}),
    "marginalia": ("marginalia_search", {"q": "mcp servers"}),
    "serper": ("serper_search", {"q": "mcp servers"}),
    "serpapi": ("serpapi_search", {"q": "mcp servers"}),
    "dataforseo": ("dataforseo_serp", {"q": "mcp servers"}),
    "zenserp": ("zenserp_search", {"q": "mcp servers"}),
    "scrapingbee": ("scrapingbee_google", {"q": "mcp servers"}),
}
ALL_VENDORS = list(SAMPLE_CALLS)
SERP_SCRAPERS = ("serper", "serpapi", "dataforseo", "zenserp", "scrapingbee")
ALL_TOOLS = [
    "brave_web_search",
    "brave_llm_context",
    "kagi_search",
    "kagi_enrich_web",
    "kagi_enrich_news",
    "linkup_search",
    "mojeek_search",
    "youcom_search",
    "perplexity_search",
    "marginalia_search",
    "serper_search",
    "serpapi_search",
    "dataforseo_serp",
    "zenserp_search",
    "scrapingbee_google",
]
# (kind, wire name, prefix) -- where each vendor documents its credential.
PLACEMENT: dict[str, tuple[str, str, str]] = {
    "brave": ("header", "x-subscription-token", ""),
    # v1 /search is an HTTP-bearer scheme in Kagi's OpenAPI; the v0 Enrich tools
    # keep the documented "Bot" scheme (asserted in the enrich test below).
    "kagi": ("header", "authorization", "Bearer "),
    "linkup": ("header", "authorization", "Bearer "),
    "mojeek": ("query", "api_key", ""),
    "youcom": ("header", "x-api-key", ""),
    "perplexity": ("header", "authorization", "Bearer "),
    "marginalia": ("header", "api-key", ""),
    "serper": ("header", "x-api-key", ""),
    "serpapi": ("query", "api_key", ""),
    "dataforseo": ("basic", "authorization", "Basic "),
    "zenserp": ("header", "apikey", ""),
    "scrapingbee": ("header", "authorization", "Bearer "),
}


# --------------------------------------------------------------------------- #
# helpers / fixtures
# --------------------------------------------------------------------------- #
def _key_env(vendor: str, key: str | None = None) -> dict[str, str]:
    """The env entries that carry ``vendor``'s credential (fake values only)."""
    if vendor == "dataforseo":
        login, _, password = (key or fake.VALID_KEYS[vendor]).partition(":")
        return {"DATAFORSEO_LOGIN": login, "DATAFORSEO_PASSWORD": password}
    cls = lk.VENDOR_BY_NAME[vendor]
    return {cls.key_envs[0]: key or fake.VALID_KEYS[vendor]}


def _env(*vendors: str, ledger: str, keys: dict | None = None, **extra) -> dict:
    env = {"KEYED_LEDGER_PATH": ledger}
    for vendor in vendors:
        cls = lk.VENDOR_BY_NAME[vendor]
        env[cls.flag_env()] = "1"
        env.update(_key_env(vendor, (keys or {}).get(vendor)))
        env[cls.url_env()] = f"{FAKE_BASE}/{vendor}"
    env.update(extra)
    return env


def _payload(result: dict) -> dict:
    assert result["isError"] is False, result
    return json.loads(result["content"][0]["text"])


def _error_text(result: dict, vendor: str) -> str:
    assert result["isError"] is True, result
    text = result["content"][0]["text"]
    assert text.startswith(f"[search-hub:keyed:{vendor}] "), text
    return text


def _ledger_json(path: str) -> dict:
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


@pytest.fixture(autouse=True)
def _reset_fake():
    fake.reset()
    yield
    fake.reset()


@pytest.fixture
def ledger_path(tmp_path) -> str:
    return str(tmp_path / "ledger" / "keyed-ledger.json")


@pytest.fixture
def frozen_now(monkeypatch):
    monkeypatch.setattr(lk, "_utc_now", lambda: NOW)
    return NOW


@pytest.fixture
def fake_transport(monkeypatch):
    """Make the DEFAULT header-aware caller the fake, so ``build`` needs no hook."""
    monkeypatch.setattr(adapters, "_default_header_caller", fake.fake_caller)


@pytest.fixture
def make(ledger_path, frozen_now):
    """Factory for a directly constructed adapter on the fake transport."""
    ledger = lk.Ledger(ledger_path, now=lambda: NOW)

    def _make(vendor: str, key: str | None = None, ledger_=None, **kwargs):
        cls = lk.VENDOR_BY_NAME[vendor]
        return cls(
            f"{FAKE_BASE}/{vendor}",
            key if key is not None else fake.VALID_KEYS[vendor],
            ledger_ or ledger,
            caller=kwargs.pop("caller", fake.fake_caller),
            **kwargs,
        )

    _make.ledger = ledger
    return _make


def _build(env: dict) -> list:
    return lanes.build_lane("lane_keyed", env)


def _one(env: dict, vendor: str):
    matches = [a for a in _build(env) if a.vendor == vendor]
    assert len(matches) == 1, matches
    return matches[0]


# --------------------------------------------------------------------------- #
# module purity + opt-in contract
# --------------------------------------------------------------------------- #
def test_module_is_stdlib_only_and_import_safe():
    with open(lk.__file__, encoding="utf-8") as fh:
        tree = ast.parse(fh.read())
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    allowed = set(sys.stdlib_module_names) | {"adapters"}
    assert imported <= allowed, imported - allowed
    assert callable(lk.build)
    assert lk.build({}) == []
    assert fake.RECEIVED == []


def test_every_vendor_has_a_flag_a_key_env_and_a_url_env():
    assert [cls.vendor for cls in lk.VENDORS] == ALL_VENDORS
    for cls in lk.VENDORS:
        assert cls.flag_env() == f"ENABLE_KEYED_{cls.vendor.upper()}"
        assert cls.url_env() == f"{cls.vendor.upper()}_API_URL"
        assert cls.key_envs, cls
        assert cls.default_url.startswith("https://"), cls
    assert lk.DataForSEOAdapter.key_envs == ("DATAFORSEO_LOGIN", "DATAFORSEO_PASSWORD")


@pytest.mark.parametrize("vendor", ALL_VENDORS)
def test_flag_without_key_and_key_without_flag_wire_nothing(vendor, ledger_path):
    cls = lk.VENDOR_BY_NAME[vendor]
    flag_only = {cls.flag_env(): "1", "KEYED_LEDGER_PATH": ledger_path}
    assert lk.build(flag_only) == []
    empty_key = dict(flag_only, **{name: "   " for name in cls.key_envs})
    assert lk.build(empty_key) == []
    key_only = dict(_key_env(vendor), KEYED_LEDGER_PATH=ledger_path)
    assert lk.build(key_only) == []
    falsey_flag = dict(key_only, **{cls.flag_env(): "0"})
    assert lk.build(falsey_flag) == []
    assert fake.RECEIVED == []


@pytest.mark.parametrize("vendor", ALL_VENDORS)
def test_flag_and_key_wire_exactly_that_vendor(vendor, ledger_path):
    built = lk.build(_env(vendor, ledger=ledger_path))
    assert [a.vendor for a in built] == [vendor]
    adapter = built[0]
    assert isinstance(adapter, lk.KeyedSearchAdapter)
    assert adapter.platform == "keyed"
    assert adapter.authenticated is True
    assert adapter.base_url == f"{FAKE_BASE}/{vendor}"
    assert set(adapter.tool_names()) <= set(ALL_TOOLS)
    assert fake.RECEIVED == []


def test_dataforseo_needs_both_login_and_password(ledger_path):
    base = {
        "ENABLE_KEYED_DATAFORSEO": "1",
        "KEYED_LEDGER_PATH": ledger_path,
    }
    assert lk.build(dict(base, DATAFORSEO_LOGIN="fake-login")) == []
    assert lk.build(dict(base, DATAFORSEO_PASSWORD="X-Fake-Key-dataforseo")) == []
    both = dict(base, DATAFORSEO_LOGIN="fake-login", DATAFORSEO_PASSWORD="X-Fake-Key-d")
    [adapter] = lk.build(both)
    assert adapter.vendor == "dataforseo" and adapter.authenticated is True


def test_all_twelve_wire_through_lanes_build_lane(ledger_path):
    env = _env(*ALL_VENDORS, ledger=ledger_path)
    built = lanes.build_lane("lane_keyed", env)
    assert [a.vendor for a in built] == ALL_VENDORS
    names = [n for a in built for n in a.tool_names()]
    assert names == ALL_TOOLS
    assert len(set(names)) == len(names)
    extra, degraded = lanes.extra_adapters(env, modules=("lane_keyed",))
    assert [a.vendor for a in extra] == ALL_VENDORS and degraded == {}
    # one shared ledger => the monthly cap is global across vendors
    assert len({id(a._ledger) for a in built}) == 1
    assert all(a._ledger.path == ledger_path for a in built)


def test_default_url_used_when_no_override_and_trailing_slash_stripped(ledger_path):
    env = _env("brave", ledger=ledger_path)
    del env["BRAVE_API_URL"]
    [adapter] = lk.build(env)
    assert adapter.base_url == "https://api.search.brave.com"
    env["BRAVE_API_URL"] = "http://127.0.0.1:9/brave/"
    [adapter] = lk.build(env)
    assert adapter.base_url == "http://127.0.0.1:9/brave"


def test_cap_env_values_are_honoured_and_bad_ones_degrade_the_lane(ledger_path):
    env = _env(
        "brave",
        ledger=ledger_path,
        KEYED_MAX_CALLS_PER_DAY="3",
        KEYED_SPEND_CAP_USD="0.5",
    )
    [adapter] = lk.build(env)
    assert adapter.max_calls_per_day == 3 and adapter.spend_cap_usd == 0.5
    for bad in (
        {"KEYED_MAX_CALLS_PER_DAY": "many"},
        {"KEYED_MAX_CALLS_PER_DAY": "-1"},
        {"KEYED_SPEND_CAP_USD": "five dollars"},
        {"KEYED_SPEND_CAP_USD": "-2"},
    ):
        with pytest.raises(ValueError):
            lk.build(_env("brave", ledger=ledger_path, **bad))
        built, degraded = lanes.extra_adapters(
            _env("brave", ledger=ledger_path, **bad), modules=("lane_keyed",)
        )
        assert built == []
        assert degraded["lane:lane_keyed"].startswith("ValueError: KEYED_")


def test_default_ledger_path_is_git_ignored_under_caches():
    assert lk.DEFAULT_LEDGER_PATH == os.path.join(
        HUB_DIR, "caches", "keyed-ledger.json"
    )
    with open(os.path.join(HUB_DIR, ".gitignore"), encoding="utf-8") as fh:
        ignored = fh.read()
    assert "caches/keyed-ledger.json" in ignored
    assert lk.ledger_path({}) == lk.DEFAULT_LEDGER_PATH
    assert lk.ledger_path({"KEYED_LEDGER_PATH": " /tmp/x.json "}) == "/tmp/x.json"


# --------------------------------------------------------------------------- #
# advertised surface
# --------------------------------------------------------------------------- #
def test_tool_defs_are_hub_shaped_and_descriptions_carry_the_contract(ledger_path):
    built = _build(_env(*ALL_VENDORS, ledger=ledger_path))
    for adapter in built:
        for tool in adapter.tools():
            definition = tool.definition()
            assert set(definition) == {"name", "description", "inputSchema"}
            assert definition["inputSchema"]["required"] == ["q"]
            assert "q" in definition["inputSchema"]["properties"]
            text = definition["description"]
            assert text.startswith("KEYED: bills the owner's ")
            assert adapter.flag_env() in text
            assert adapter.key_envs[0] in text
            assert "KEYED_MAX_CALLS_PER_DAY" in text and "KEYED_SPEND_CAP_USD" in text
            assert "never fabricated" in text
            if adapter.vendor in SERP_SCRAPERS:
                assert adapter.legal_shadow is True
                assert "LEGAL SHADOW" in text and "Google v. SerpApi" in text
                assert "searxng_web_search" in text
            else:
                assert adapter.legal_shadow is False
                assert "LEGAL SHADOW" not in text


def test_capabilities_report_configuration_and_never_probe(make):
    adapter = make("brave", key="X-Fake-Key-brave-SECRET-VALUE")
    for probe in (False, True):
        report = adapter.capabilities(probe=probe)
        assert report["provider"] == "keyed" and report["vendor"] == "brave"
        assert report["keyless"] is False and report["self_hosted"] is False
        assert report["authenticated"] is True
        assert report["probed"] is False
        assert "not probed" in report["probe_note"] and "bill" in report["probe_note"]
        assert report["auth_env"] == "BRAVE_API_KEY (value never shown)"
        assert report["auth_placement"] == "header X-Subscription-Token: <key>"
        assert report["flag_env"] == "ENABLE_KEYED_BRAVE"
        assert report["url_env"] == "BRAVE_API_URL"
        assert report["legal_shadow"] is False
        assert report["price_per_1k_usd"] == {
            "brave_web_search": 5.0,
            "brave_llm_context": 5.0,
        }
        assert report["spend"]["today"] == {
            "date": "2026-09-02",
            "calls": 0,
            "budget": lk.DEFAULT_MAX_CALLS_PER_DAY,
            "remaining": lk.DEFAULT_MAX_CALLS_PER_DAY,
            "resets": DAILY_RESET,
        }
        assert report["spend"]["month"]["cap_usd"] == lk.DEFAULT_SPEND_CAP_USD
        assert report["spend"]["month"]["resets"] == MONTHLY_RESET
        assert [t["state"] for t in report["tools"]] == ["native", "native"]
        assert "X-Fake-Key-brave-SECRET-VALUE" not in json.dumps(report)
    assert adapter.probe() == (True, adapter.probe()[1])
    assert (
        fake.RECEIVED == []
    )  # neither capabilities(probe=True) nor probe() called out
    assert "X-Fake-Key-brave-SECRET-VALUE" not in json.dumps(adapter.tool_defs())


def test_auth_placement_described_per_kind(make):
    assert make("kagi").capabilities()["auth_placement"] == (
        "header Authorization: Bearer <key> for /api/v1/search; "
        "header Authorization: Bot <key> for /api/v0/enrich/*"
    )
    assert make("brave").capabilities()["auth_placement"] == (
        "header X-Subscription-Token: <key>"
    )
    assert make("serpapi").capabilities()["auth_placement"] == (
        "query parameter api_key=<key> (never echoed)"
    )
    assert (
        make("dataforseo")
        .capabilities()["auth_placement"]
        .startswith("HTTP basic auth")
    )
    assert make("dataforseo").capabilities()["auth_env"] == (
        "DATAFORSEO_LOGIN + DATAFORSEO_PASSWORD (value never shown)"
    )


# --------------------------------------------------------------------------- #
# secrets: placement on the wire, never anywhere else, scrubbed when echoed
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("vendor", ALL_VENDORS)
def test_key_travels_only_at_the_documented_place(vendor, make):
    adapter = make(vendor)
    tool, args = SAMPLE_CALLS[vendor]
    payload = _payload(adapter.handle_call(tool, args))  # the fake 200s ONLY on it
    assert payload["authenticated"] is True and payload["count"] >= 1
    [rec] = fake.RECEIVED
    assert rec["vendor"] == vendor
    kind, name, prefix = PLACEMENT[vendor]
    secret = fake.VALID_KEYS[vendor]
    header_blob = json.dumps(rec["headers"])
    body_blob = json.dumps(rec["body"])
    if kind == "header":
        assert rec["headers"][name] == f"{prefix}{secret}"
        assert secret not in rec["raw_path"] and secret not in body_blob
        assert header_blob.count(secret) == 1
    elif kind == "query":
        assert rec["query"][name] == secret
        assert secret not in header_blob and secret not in body_blob
    else:
        token = base64.b64encode(secret.encode()).decode()
        assert rec["headers"]["authorization"] == f"Basic {token}"
        assert fake.DATAFORSEO_PASSWORD not in rec["raw_path"]
        assert fake.DATAFORSEO_PASSWORD not in body_blob
    assert secret not in json.dumps(payload)


@pytest.mark.parametrize("vendor", ALL_VENDORS)
def test_rejected_key_echoed_by_the_vendor_is_scrubbed(vendor, make):
    if vendor == "dataforseo":
        key, secrets = (
            "fake-login:WRONG-password-XYZ",
            ("WRONG-password-XYZ", "fake-login"),
        )
    else:
        key, secrets = (
            f"X-Fake-Key-{vendor}-REJECTED-abc",
            (f"X-Fake-Key-{vendor}-REJECTED-abc",),
        )
    adapter = make(vendor, key=key)
    tool, args = SAMPLE_CALLS[vendor]
    text = _error_text(adapter.handle_call(tool, args), vendor)
    [rec] = fake.RECEIVED  # the request WAS made and the fake DID echo the key
    assert rec["vendor"] == vendor
    assert "[redacted]" in text
    for secret in secrets:
        assert secret not in text
        assert base64.b64encode(secret.encode()).decode() not in text
    expected_status = "HTTP 403" if vendor in ("serper", "zenserp") else "HTTP 401"
    assert expected_status in text
    assert "value never shown" in text or "lacks access" in text
    assert "no results are fabricated" in text.lower()
    assert lk.VENDOR_BY_NAME[vendor].key_envs[0] in text  # names the env, not the value


def test_scrub_covers_url_encoded_and_json_escaped_forms(make):
    key = 'X-Fake "quoted" key/with spaces&more'
    adapter = make("brave", key=key)
    assert adapter.authenticated is True
    text = adapter._scrub(
        f"plain {key} | encoded {lk.quote(key, safe='')} | json {json.dumps(key)}"
    )
    assert key not in text and lk.quote(key, safe="") not in text
    assert text.count("[redacted]") == 3


def test_degenerate_short_key_does_not_shred_the_payload(make):
    adapter = make("brave", key="123")
    assert adapter._scrub_terms == ()
    _ = _error_text(adapter.handle_call("brave_web_search", {"q": "x"}), "brave")
    # a 3-char "key" is not a credential; the fake rejected it, output stays readable
    assert fake.RECEIVED[0]["headers"]["x-subscription-token"] == "123"


def test_not_configured_adapter_names_the_envs_and_makes_no_request(make):
    adapter = make("brave", key="")
    assert adapter.authenticated is False
    text = _error_text(adapter.handle_call("brave_web_search", {"q": "x"}), "brave")
    assert "ENABLE_KEYED_BRAVE=1 AND a non-empty BRAVE_API_KEY" in text
    assert "No request was made" in text
    assert fake.RECEIVED == []
    assert not os.path.exists(make.ledger.path)


def test_unknown_tool_is_a_truthful_error(make):
    text = _error_text(make("brave").handle_call("brave_nope", {"q": "x"}), "brave")
    assert "unknown keyed tool 'brave_nope'" in text
    assert fake.RECEIVED == []


# --------------------------------------------------------------------------- #
# happy paths: one per tool, request composition + normalisation
# --------------------------------------------------------------------------- #
def _common_checks(payload: dict, vendor: str, tool: str) -> None:
    assert payload["tool"] == tool and payload["vendor"] == vendor
    assert payload["count"] == len(payload["results"])
    assert isinstance(payload["raw_count"], int)
    assert isinstance(payload["latency_ms"], int) and payload["latency_ms"] >= 0
    assert payload["authenticated"] is True
    assert payload["spend"]["vendor"] == vendor and payload["spend"]["tool"] == tool
    assert payload["spend"]["resets"] == {
        "daily": DAILY_RESET,
        "monthly": MONTHLY_RESET,
    }
    for hit in payload["results"]:
        assert set(hit) >= {"title", "url", "snippet", "vendor"}
        assert hit["vendor"] == vendor
        assert "<" not in (hit["title"] or "") and "<" not in (hit["snippet"] or "")


def test_brave_web_search_request_and_normalisation(make):
    adapter = make("brave")
    payload = _payload(
        adapter.handle_call(
            "brave_web_search",
            {
                "q": "mcp servers",
                "count": 5,
                "offset": 1,
                "country": "us",
                "search_lang": "en",
                "freshness": "pw",
            },
        )
    )
    [rec] = fake.RECEIVED
    assert rec["method"] == "GET" and rec["path"] == "/res/v1/web/search"
    assert rec["query"] == {
        "q": "mcp servers",
        "count": "5",
        "offset": "1",
        "freshness": "pw",
        "country": "US",
        "search_lang": "en",
    }
    assert rec["headers"]["accept"] == "application/json"
    assert rec["body"] is None
    _common_checks(payload, "brave", "brave_web_search")
    assert payload["q"] == "mcp servers" and payload["count"] == 2
    assert payload["offset"] == 1 and payload["freshness"] == "pw"
    assert payload["raw_count"] == 2 and payload["shape"] == "web.results"
    first, second = payload["results"]
    assert first == {
        "title": "Brave hit one",
        "url": "https://example.com/one",
        "snippet": "First brave result & more",
        "vendor": "brave",
        "published": "2026-08-30T10:00:00",
        "age": "3 days ago",
        "extra_snippets": ["extra one", "extra two"],
    }
    assert "published" not in second and second["title"] == "Brave hit two"
    assert payload["credits_hint"]["x-ratelimit-remaining"] == "0, 1999"
    assert payload["credits_hint"]["x-ratelimit-limit"] == "1, 2000"
    assert payload["query_info"]["more_results_available"] is True
    assert payload["spend"]["price_per_1k_usd"] == 5.0
    assert payload["spend"]["estimated_usd"] == 0.005
    assert payload["spend"]["calls_today"] == 1
    assert payload["spend"]["month_usd_estimated"] == 0.005


def test_brave_date_range_freshness_and_all_country_pass_through(make):
    adapter = make("brave")
    _payload(
        adapter.handle_call(
            "brave_web_search",
            {"q": "x", "freshness": "2026-01-01to2026-02-01", "country": "ALL"},
        )
    )
    assert fake.RECEIVED[0]["query"]["freshness"] == "2026-01-01to2026-02-01"
    assert fake.RECEIVED[0]["query"]["country"] == "ALL"
    assert "offset" not in fake.RECEIVED[0]["query"]


def test_brave_empty_web_block_is_zero_hits_not_an_error(make):
    payload = _payload(
        make("brave").handle_call("brave_web_search", {"q": "empty set"})
    )
    assert payload["count"] == 0 and payload["results"] == []
    assert payload["raw_count"] == 0
    assert "no web block" in payload["note"]


def test_brave_llm_context_grounding_shape(make):
    payload = _payload(
        make("brave").handle_call("brave_llm_context", {"q": "grounding"})
    )
    [rec] = fake.RECEIVED
    assert rec["path"] == "/res/v1/llm/context" and rec["query"] == {"q": "grounding"}
    _common_checks(payload, "brave", "brave_llm_context")
    # generic (2 entries, a list) + poi (ONE object, per the docs' local response)
    assert payload["shape"] == "grounding" and payload["raw_count"] == 3
    assert payload["results"][0] == {
        "title": "Context for grounding",
        "url": "https://example.com/ctx",
        "snippet": "grounding snippet A",
        "vendor": "brave",
        "section": "generic",
        "snippets": ["grounding snippet A", "grounding snippet B"],
    }
    assert payload["results"][2] == {
        "title": "Title of business.example",
        "url": "https://business.example/",
        "snippet": "Business details",
        "vendor": "brave",
        "section": "poi",
        "name": "Fake Business",
        "snippets": ["Business details"],
    }
    assert payload["spend"]["price_per_1k_usd"] == 5.0


def test_kagi_search_v1_post_bearer_sections_related_and_trace(make):
    """v1 (OpenAPI at kagi.com/api/docs): POST JSON ``{query, limit}``, HTTP bearer,
    results under ``data.<section>[]`` with ``time``; ``error[]`` envelope."""
    payload = _payload(
        make("kagi").handle_call("kagi_search", {"q": "mcp servers", "limit": 3})
    )
    [rec] = fake.RECEIVED
    assert rec["method"] == "POST" and rec["path"] == "/api/v1/search"
    assert rec["query"] == {}  # nothing in the URL: the v1 request is a JSON body
    assert rec["body"] == {"query": "mcp servers", "limit": 3}  # page 1 is omitted
    assert rec["headers"]["authorization"] == "Bearer X-Fake-Key-kagi"
    assert rec["headers"]["content-type"] == "application/json"
    _common_checks(payload, "kagi", "kagi_search")
    assert payload["limit"] == 3 and payload["page"] == 1
    # search (2) + news (1) + adjacent_question (1) become hits, in that order;
    # related_search entries are counted but surfaced as related_searches.
    assert payload["count"] == 4 and payload["raw_count"] == 6
    assert payload["results"][0] == {
        "title": "Kagi mcp servers one",
        "url": "https://example.com/kagi-one",
        "snippet": "Kagi snippet one",
        "vendor": "kagi",
        "published": "2026-08-01T00:00:00Z",
        "section": "search",
    }
    assert payload["results"][2]["section"] == "news"
    assert payload["results"][3] == {
        "title": "Kagi adjacent",
        "url": "https://example.net/adjacent",
        "snippet": "adjacent snippet",
        "vendor": "kagi",
        "section": "adjacent_question",
        "question": "what is an mcp server?",
    }
    assert payload["sections"] == {
        "search": 2,
        "news": 1,
        "adjacent_question": 1,
        "related_search": 2,
    }
    assert payload["related_searches"] == ["related a", "related b"]
    assert payload["credits_hint"] is None  # v1 meta carries trace/node/ms only
    assert payload["upstream_trace"] == "fake-kagi-trace"
    assert payload["upstream_ms"] == 152
    assert payload["spend"]["price_per_1k_usd"] == 12.0
    assert payload["spend"]["estimated_usd"] == 0.012


def test_kagi_search_page_is_sent_only_past_page_one(make):
    payload = _payload(
        make("kagi").handle_call("kagi_search", {"q": "mcp servers", "page": 2})
    )
    [rec] = fake.RECEIVED
    assert rec["body"] == {"query": "mcp servers", "limit": 10, "page": 2}
    assert payload["page"] == 2 and payload["limit"] == 10


def test_kagi_v1_error_envelope_message_is_relayed_and_scrubbed(make):
    adapter = make("kagi", key="X-Fake-Key-kagi-REJECTED-abc")
    text = _error_text(adapter.handle_call("kagi_search", {"q": "x"}), "kagi")
    assert "HTTP 401" in text and "Invalid API key" in text
    assert "X-Fake-Key-kagi-REJECTED-abc" not in text and "[redacted]" in text


@pytest.mark.parametrize(
    "tool, path",
    [
        ("kagi_enrich_web", "/api/v0/enrich/web"),
        ("kagi_enrich_news", "/api/v0/enrich/news"),
    ],
)
def test_kagi_enrich_v0_get_bot_auth_paths_and_price(make, tool, path):
    """Enrich stays on the documented v0 contract: GET ``?q=``, ``Authorization:
    Bot``, ``data`` as a list of ``{t: 0, rank, url, title, snippet, published}``."""
    payload = _payload(make("kagi").handle_call(tool, {"q": "small web"}))
    [rec] = fake.RECEIVED
    assert rec["method"] == "GET" and rec["body"] is None
    assert rec["path"] == path and rec["query"] == {"q": "small web"}
    assert rec["headers"]["authorization"] == "Bot X-Fake-Key-kagi"
    _common_checks(payload, "kagi", tool)
    assert payload["count"] == 2 and payload["raw_count"] == 2
    assert "related_searches" not in payload and "sections" not in payload
    assert payload["results"][0] == {
        "title": "Kagi small web one",
        "url": "https://example.com/kagi-one",
        "snippet": "Kagi snippet one",
        "vendor": "kagi",
        "published": "2026-08-01T00:00:00Z",
        "position": 0,
    }
    assert payload["credits_hint"] == {"api_balance": 4.87}
    assert payload["upstream_ms"] == 152
    assert payload["spend"]["price_per_1k_usd"] == 2.0
    assert payload["spend"]["estimated_usd"] == 0.002


def test_linkup_search_results_and_sourced_answer(make):
    adapter = make("linkup")
    payload = _payload(adapter.handle_call("linkup_search", {"q": "mcp servers"}))
    [rec] = fake.RECEIVED
    assert rec["method"] == "POST" and rec["path"] == "/v1/search"
    assert rec["headers"]["authorization"] == "Bearer X-Fake-Key-linkup"
    assert rec["headers"]["content-type"] == "application/json"
    assert rec["body"] == {
        "q": "mcp servers",
        "depth": "standard",
        "outputType": "searchResults",
        "includeImages": False,
    }
    _common_checks(payload, "linkup", "linkup_search")
    assert payload["shape"] == "searchResults" and payload["count"] == 2
    assert payload["results"][0] == {
        "title": "Linkup result one",
        "url": "https://example.com/l1",
        "snippet": "linkup content one",
        "vendor": "linkup",
        "type": "text",
    }
    assert payload["spend"]["price_per_1k_usd"] == 5.0
    answer = _payload(
        adapter.handle_call(
            "linkup_search",
            {
                "q": "why",
                "depth": "deep",
                "output_type": "sourcedAnswer",
                "include_images": "true",
            },
        )
    )
    assert fake.RECEIVED[1]["body"] == {
        "q": "why",
        "depth": "deep",
        "outputType": "sourcedAnswer",
        "includeImages": True,
    }
    assert answer["shape"] == "sourcedAnswer"
    assert answer["answer"] == "Fake answer about why."
    assert [h["url"] for h in answer["results"]] == [
        "https://example.com/src1",
        "https://example.org/src2",
    ]
    assert answer["results"][0]["snippet"] == "supporting snippet one"
    assert answer["spend"]["price_per_1k_usd"] == 6.0  # deep surcharge


def test_mojeek_query_param_key_and_json_format(make):
    payload = _payload(
        make("mojeek").handle_call("mojeek_search", {"q": "mcp servers", "count": 2})
    )
    [rec] = fake.RECEIVED
    assert rec["method"] == "GET" and rec["path"] == "/search"
    assert rec["query"] == {
        "q": "mcp servers",
        "fmt": "json",
        "t": "2",
        "api_key": "X-Fake-Key-mojeek",
    }
    assert "x-fake-key-mojeek" not in json.dumps(rec["headers"]).lower()
    _common_checks(payload, "mojeek", "mojeek_search")
    assert payload["count"] == 2
    assert payload["results"][0] == {
        "title": "Mojeek one",
        "url": "https://example.com/mj1",
        "snippet": "mojeek description one",
        "vendor": "mojeek",
        "published": "2026-07-02",
    }
    assert payload["total_results"] == 1234 and payload["upstream_status"] == "OK"
    assert payload["credits_hint"] is None
    assert payload["spend"]["price_per_1k_usd"] == 2.7


def test_mojeek_count_above_ten_is_estimated_at_the_business_rate(make):
    """The plan table caps results per request (Startup 10, Business 40): more
    than 10 can only come from the dearer GBP 3 CPM plan, so that is what the
    estimate assumes -- erring high, never low."""
    adapter = make("mojeek")
    payload = _payload(adapter.handle_call("mojeek_search", {"q": "x", "count": 11}))
    assert fake.RECEIVED[-1]["query"]["t"] == "11"
    assert payload["spend"]["price_per_1k_usd"] == 4.05
    assert payload["spend"]["estimated_usd"] == 0.00405
    payload = _payload(adapter.handle_call("mojeek_search", {"q": "x", "count": 10}))
    assert payload["spend"]["price_per_1k_usd"] == 2.7
    # capabilities() prices the default call (count 10), as for every vendor
    assert adapter.capabilities()["price_per_1k_usd"] == {"mojeek_search": 2.7}


def test_youcom_post_body_and_web_plus_news_sections(make):
    payload = _payload(
        make("youcom").handle_call(
            "youcom_search",
            {"q": "mcp servers", "count": 5, "country": "gb", "language": "en"},
        )
    )
    [rec] = fake.RECEIVED
    assert rec["method"] == "POST" and rec["path"] == "/v1/search"
    assert rec["headers"]["x-api-key"] == "X-Fake-Key-youcom"
    assert rec["body"] == {
        "query": "mcp servers",
        "count": 5,
        "country": "GB",
        "language": "en",
    }
    _common_checks(payload, "youcom", "youcom_search")
    assert payload["count"] == 3 and payload["raw_count"] == 3
    assert payload["web_count"] == 2 and payload["news_count"] == 1
    assert payload["results"][0]["section"] == "web"
    assert payload["results"][0]["snippets"] == ["you snippet a", "you snippet b"]
    assert payload["results"][0]["published"] == "2026-08-01T00:00:00"
    assert payload["results"][2]["section"] == "news"
    assert payload["results"][2]["url"] == "https://news.example.com/n1"


def test_perplexity_search_api_post_body_and_results(make):
    payload = _payload(
        make("perplexity").handle_call(
            "perplexity_search", {"q": "mcp servers", "max_results": 1, "country": "us"}
        )
    )
    [rec] = fake.RECEIVED
    assert rec["method"] == "POST" and rec["path"] == "/search"
    assert rec["headers"]["authorization"] == "Bearer X-Fake-Key-perplexity"
    assert rec["body"] == {"query": "mcp servers", "max_results": 1, "country": "US"}
    _common_checks(payload, "perplexity", "perplexity_search")
    assert payload["count"] == 1 and payload["max_results"] == 1
    assert payload["results"][0] == {
        "title": "Perplexity one",
        "url": "https://example.com/p1",
        "snippet": "perplexity snippet about mcp servers",
        "vendor": "perplexity",
        "published": "2026-08-15",
        "last_updated": "2026-08-20",
    }
    assert payload["request_id"] == "fake-pplx-request"
    assert payload["spend"]["price_per_1k_usd"] == 5.0


def test_marginalia_api2_header_key_unpriced_and_public_key_refused(make):
    payload = _payload(
        make("marginalia").handle_call("marginalia_search", {"q": "mcp", "count": 7})
    )
    [rec] = fake.RECEIVED
    assert rec["method"] == "GET" and rec["path"] == "/search"
    assert rec["query"] == {"query": "mcp", "count": "7"}
    assert rec["headers"]["api-key"] == "X-Fake-Key-marginalia"
    _common_checks(payload, "marginalia", "marginalia_search")
    assert payload["count"] == 2 and payload["license"] == "CC-BY-SA 4.0"
    assert payload["results"][0]["snippet"] == "small-web description one"
    assert payload["credits_hint"] is None
    assert payload["spend"]["price_per_1k_usd"] is None
    assert payload["spend"]["estimated_usd"] is None
    assert payload["spend"]["month_usd_estimated"] == 0.0  # counted, not priced
    assert payload["spend"]["calls_today"] == 1
    public = make("marginalia", key="public")
    assert public.authenticated is False
    text = _error_text(
        public.handle_call("marginalia_search", {"q": "mcp"}), "marginalia"
    )
    assert "shared keyless 'public' key" in text and "SearXNG" in text
    assert "No request was made" in text
    assert len(fake.RECEIVED) == 1  # nothing new
    assert public.capabilities()["authenticated"] is False


def test_serper_post_body_credits_and_num_surcharge(make):
    adapter = make("serper")
    payload = _payload(
        adapter.handle_call(
            "serper_search", {"q": "mcp servers", "gl": "US", "hl": "en"}
        )
    )
    [rec] = fake.RECEIVED
    assert rec["method"] == "POST" and rec["path"] == "/search"
    assert rec["headers"]["x-api-key"] == "X-Fake-Key-serper"
    assert rec["body"] == {"q": "mcp servers", "num": 10, "gl": "us", "hl": "en"}
    _common_checks(payload, "serper", "serper_search")
    assert payload["results"][0] == {
        "title": "Serper one",
        "url": "https://example.com/s1",
        "snippet": "serper snippet one",
        "vendor": "serper",
        "published": "Aug 30, 2026",
        "position": 1,
    }
    assert payload["credits_hint"] == {"credits": 1}
    assert payload["spend"]["price_per_1k_usd"] == 1.0
    big = _payload(
        adapter.handle_call("serper_search", {"q": "mcp servers", "num": 20})
    )
    assert big["credits_hint"] == {"credits": 2}
    assert big["spend"]["price_per_1k_usd"] == 2.0


def test_serpapi_query_param_key_start_paging_and_no_results_envelope(make):
    adapter = make("serpapi")
    payload = _payload(adapter.handle_call("serpapi_search", {"q": "mcp servers"}))
    [rec] = fake.RECEIVED
    assert rec["method"] == "GET" and rec["path"] == "/search.json"
    # No ``num``: Google dropped it in 2025 and SerpApi's docs no longer list it;
    # paging is ``start`` only, and page one sends none.
    assert rec["query"] == {
        "engine": "google",
        "q": "mcp servers",
        "api_key": "X-Fake-Key-serpapi",
    }
    _common_checks(payload, "serpapi", "serpapi_search")
    assert payload["count"] == 2 and payload["start"] == 0
    assert payload["results"][1] == {
        "title": "SerpApi two",
        "url": "https://example.org/sa2",
        "snippet": "serpapi snippet two",
        "vendor": "serpapi",
        "position": 2,
    }
    assert payload["search_metadata"] == {
        "id": "fake-serpapi-id",
        "status": "Success",
        "total_time_taken": 1.23,
    }
    assert payload["spend"]["price_per_1k_usd"] == 25.0  # Starter $25 / 1,000
    none = _payload(adapter.handle_call("serpapi_search", {"q": "noresults please"}))
    assert none["count"] == 0 and none["raw_count"] == 0
    assert none["note"].startswith("SerpApi said: Google hasn't returned any results")


def test_dataforseo_basic_auth_task_body_and_organic_filter(make):
    adapter = make("dataforseo")
    payload = _payload(adapter.handle_call("dataforseo_serp", {"q": "mcp servers"}))
    [rec] = fake.RECEIVED
    assert rec["method"] == "POST"
    assert rec["path"] == "/v3/serp/google/organic/live/advanced"
    token = base64.b64encode(b"fake-login:X-Fake-Key-dataforseo").decode()
    assert rec["headers"]["authorization"] == f"Basic {token}"
    assert rec["body"] == [
        {
            "keyword": "mcp servers",
            "location_code": 2840,
            "language_code": "en",
            "depth": 10,
        }
    ]
    _common_checks(payload, "dataforseo", "dataforseo_serp")
    assert (
        payload["count"] == 2 and payload["raw_count"] == 3
    )  # PAA block counted, not a hit
    assert payload["results"][0] == {
        "title": "DataForSEO one",
        "url": "https://example.com/d1",
        "snippet": "dataforseo description one",
        "vendor": "dataforseo",
        "published": "2026-08-30 10:00:00 +00:00",
        "position": 1,
    }
    assert payload["results"][1]["position"] == 3
    assert payload["credits_hint"] == {"cost": 0.002}
    assert payload["items_count"] == 3 and payload["se_results_count"] == 987654
    assert payload["spend"]["price_per_1k_usd"] == 2.0
    text = _error_text(
        adapter.handle_call("dataforseo_serp", {"q": "badtask"}), "dataforseo"
    )
    assert "task status 40501" in text and "Invalid Field" in text
    assert "no results are fabricated" in text


def test_zenserp_apikey_header_and_non_organic_blocks_counted_only(make):
    payload = _payload(
        make("zenserp").handle_call(
            "zenserp_search",
            {"q": "mcp servers", "location": "Paris,France", "gl": "fr", "hl": "fr"},
        )
    )
    [rec] = fake.RECEIVED
    assert rec["method"] == "GET" and rec["path"] == "/api/v2/search"
    assert rec["headers"]["apikey"] == "X-Fake-Key-zenserp"
    assert rec["query"] == {
        "q": "mcp servers",
        "num": "10",
        "location": "Paris,France",
        "gl": "fr",
        "hl": "fr",
    }
    _common_checks(payload, "zenserp", "zenserp_search")
    assert payload["count"] == 2 and payload["raw_count"] == 3
    assert payload["results"][0]["url"] == "https://example.com/z1"
    assert payload["results"][1] == {
        "title": "ZenSerp two",
        "url": "https://example.org/z2",
        "snippet": "zenserp description two",
        "vendor": "zenserp",
        "published": "Aug 30, 2026",
        "position": 2,
    }
    assert payload["spend"]["price_per_1k_usd"] == 2.0


def test_scrapingbee_bearer_header_light_default_and_regular_surcharge(make):
    adapter = make("scrapingbee")
    payload = _payload(
        adapter.handle_call(
            "scrapingbee_google", {"q": "mcp servers", "country_code": "US"}
        )
    )
    [rec] = fake.RECEIVED
    assert rec["method"] == "GET" and rec["path"] == "/api/v1/google"
    # Bearer header, NOT the deprecated ?api_key= query form; page one sends no
    # ``page``; the vendor default light_request=true is sent explicitly.
    assert rec["headers"]["authorization"] == "Bearer X-Fake-Key-scrapingbee"
    assert rec["query"] == {
        "search": "mcp servers",
        "light_request": "true",
        "country_code": "us",
    }
    _common_checks(payload, "scrapingbee", "scrapingbee_google")
    assert payload["count"] == 2
    assert payload["page"] == 1 and payload["light_request"] is True
    assert payload["results"][0] == {
        "title": "ScrapingBee one",
        "url": "https://example.com/b1",
        "snippet": "scrapingbee description one",
        "vendor": "scrapingbee",
        "published": "Aug 30, 2026",
        "position": 1,
    }
    assert payload["credits_hint"]["spb-cost"] == "10"
    assert payload["meta_data"] == {
        "number_of_results": 1234567,
        "number_of_organic_results": 2,
        "number_of_page": 1,
    }
    # 10 credits at the Hobby plan ($19 / 75,000 credits), rounded up to the cent.
    assert payload["spend"]["price_per_1k_usd"] == 2.54
    regular = _payload(
        adapter.handle_call(
            "scrapingbee_google",
            {"q": "x", "light_request": False, "page": 3, "date_range": "past_week"},
        )
    )
    assert fake.RECEIVED[1]["query"] == {
        "search": "x",
        "light_request": "false",
        "page": "3",
        "date_range": "past_week",
    }
    assert regular["credits_hint"]["spb-cost"] == "15"
    assert regular["spend"]["price_per_1k_usd"] == 3.8  # 15 credits, not 10
    assert regular["light_request"] is False and regular["page"] == 3
    assert regular["meta_data"]["number_of_page"] == 3


def test_serpapi_start_paging_is_sent_only_past_page_one(make):
    payload = _payload(
        make("serpapi").handle_call(
            "serpapi_search", {"q": "mcp servers", "start": 10, "gl": "GB", "hl": "en"}
        )
    )
    [rec] = fake.RECEIVED
    assert rec["query"] == {
        "engine": "google",
        "q": "mcp servers",
        "start": "10",
        "gl": "gb",
        "hl": "en",
        "api_key": "X-Fake-Key-serpapi",
    }
    assert payload["start"] == 10 and "num" not in payload
    assert payload["spend"]["price_per_1k_usd"] == 25.0  # flat: paging costs no more


@pytest.mark.parametrize(
    "args, price",
    [
        ({"q": "mcp servers"}, 2.0),
        ({"q": "mcp servers", "depth": 10}, 2.0),
        ({"q": "mcp servers", "depth": 11}, 4.0),  # rounds UP to 2 pages
        ({"q": "mcp servers", "depth": 100}, 20.0),
        ({"q": "site:example.com mcp"}, 10.0),  # one operator: x5
        ({"q": "site:example.com intitle:mcp", "depth": 20}, 100.0),  # 2 pages x25
        ({"q": "definition of site colon"}, 2.0),  # no operator syntax, no surcharge
    ],
)
def test_dataforseo_estimate_follows_depth_pages_and_operator_multipliers(
    make, args, price
):
    adapter = make("dataforseo")
    tool = adapter._tool("dataforseo_serp")
    assert adapter._price_per_1k(tool, args) == price
    payload = _payload(adapter.handle_call("dataforseo_serp", args))
    assert payload["spend"]["price_per_1k_usd"] == price
    assert payload["spend"]["estimated_usd"] == round(price / 1000, 6)
    assert fake.RECEIVED[0]["body"][0]["depth"] == args.get("depth", 10)


def test_dataforseo_capabilities_price_is_the_base_page_rate(make):
    adapter = make("dataforseo")
    assert adapter.capabilities()["price_per_1k_usd"] == {"dataforseo_serp": 2.0}
    [definition] = adapter.tool_defs()
    assert "site:" in definition["description"]  # the surcharge is disclosed


# --------------------------------------------------------------------------- #
# truthful degradation
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("vendor", ALL_VENDORS)
def test_429_relays_retry_after_and_counts_the_attempt(vendor, make):
    adapter = make(vendor)
    tool, _ = SAMPLE_CALLS[vendor]
    text = _error_text(adapter.handle_call(tool, {"q": "ratelimited query"}), vendor)
    assert "HTTP 429" in text and "retry-after 17s" in text
    assert '"x-ratelimit-remaining": "0"' in text
    assert "rate limit exceeded" in text
    assert "counted against the daily budget" in text
    assert "No results are fabricated" in text
    snap = adapter.capabilities()["spend"]["today"]
    assert snap["calls"] == 1 and snap["remaining"] == lk.DEFAULT_MAX_CALLS_PER_DAY - 1


def test_402_is_payment_required(make):
    text = _error_text(
        make("brave").handle_call("brave_web_search", {"q": "nocredit"}), "brave"
    )
    assert "HTTP 402 payment required" in text and "BRAVE_API_KEY" in text
    assert "insufficient credit" in text


def test_5xx_is_relayed_with_the_vendor_message(make):
    text = _error_text(
        make("serper").handle_call("serper_search", {"q": "boom"}), "serper"
    )
    assert "upstream failure: HTTP 500 for /search" in text
    assert "simulated upstream failure" in text and "No results are fabricated" in text


@pytest.mark.parametrize("vendor", ["brave", "linkup", "serpapi", "dataforseo"])
def test_non_json_200_is_an_error(vendor, make):
    tool, _ = SAMPLE_CALLS[vendor]
    text = _error_text(make(vendor).handle_call(tool, {"q": "notjson"}), vendor)
    assert "HTTP 200" in text and "body is not JSON" in text
    assert "upstream returned HTML" in text


@pytest.mark.parametrize("vendor", ALL_VENDORS)
def test_unrecognised_200_shape_is_an_error_not_an_empty_success(vendor, make):
    tool, _ = SAMPLE_CALLS[vendor]
    text = _error_text(make(vendor).handle_call(tool, {"q": "weirdshape"}), vendor)
    assert "not the documented shape" in text
    assert "top-level keys ['unexpected']" in text
    assert "no results are fabricated" in text


def test_transport_failure_is_truthful_and_counted(make):
    def down(method, url, body, headers, timeout):
        return 0, None, "request failed: [Errno 111] Connection refused", {}

    adapter = make("kagi", caller=down)
    text = _error_text(adapter.handle_call("kagi_search", {"q": "x"}), "kagi")
    assert "not reachable" in text and "Connection refused" in text
    assert "counted against the daily budget" in text
    assert _ledger_json(make.ledger.path)["daily"]["2026-09-02"]["kagi"] == 1


def test_transport_failure_text_is_scrubbed_for_query_keyed_vendors(make):
    def leaky(method, url, body, headers, timeout):
        return 0, None, f"request failed: bad url {url}", {}

    adapter = make("serpapi", caller=leaky)
    text = _error_text(adapter.handle_call("serpapi_search", {"q": "x"}), "serpapi")
    assert "X-Fake-Key-serpapi" not in text and "[redacted]" in text


@pytest.mark.parametrize(
    "vendor, tool, args, needle",
    [
        ("brave", "brave_web_search", {"q": ""}, "'q' is required"),
        ("brave", "brave_web_search", {}, "'q' is required"),
        ("brave", "brave_web_search", {"q": "a\x00b"}, "control characters"),
        ("brave", "brave_web_search", {"q": "x" * 401}, "401 characters"),
        (
            "brave",
            "brave_web_search",
            {"q": "x", "count": 0},
            "'count' must be an integer",
        ),
        (
            "brave",
            "brave_web_search",
            {"q": "x", "count": 21},
            "'count' must be an integer",
        ),
        (
            "brave",
            "brave_web_search",
            {"q": "x", "count": "ten"},
            "'count' must be an integer",
        ),
        (
            "brave",
            "brave_web_search",
            {"q": "x", "offset": 10},
            "'offset' must be an integer",
        ),
        (
            "brave",
            "brave_web_search",
            {"q": "x", "freshness": "yesterday"},
            "'freshness' must be",
        ),
        (
            "brave",
            "brave_web_search",
            {"q": "x", "country": "USA"},
            "'country' must match",
        ),
        (
            "brave",
            "brave_llm_context",
            {"q": "x", "search_lang": "e"},
            "'search_lang' must match",
        ),
        ("kagi", "kagi_search", {"q": "x", "limit": 101}, "'limit' must be an integer"),
        ("kagi", "kagi_search", {"q": "x", "page": 11}, "'page' must be an integer"),
        (
            "linkup",
            "linkup_search",
            {"q": "x", "depth": "shallow"},
            "'depth' must be one of",
        ),
        (
            "linkup",
            "linkup_search",
            {"q": "x", "output_type": "html"},
            "'output_type' must be one of",
        ),
        (
            "linkup",
            "linkup_search",
            {"q": "x", "include_images": "maybe"},
            "'include_images' must be a boolean",
        ),
        (
            "mojeek",
            "mojeek_search",
            {"q": "x", "count": 41},
            "'count' must be an integer",
        ),
        (
            "youcom",
            "youcom_search",
            {"q": "x", "language": "english!"},
            "'language' must match",
        ),
        (
            "perplexity",
            "perplexity_search",
            {"q": "x", "max_results": 21},
            "'max_results' must be",
        ),
        (
            "marginalia",
            "marginalia_search",
            {"q": "x", "count": 0},
            "'count' must be an integer",
        ),
        ("serper", "serper_search", {"q": "x", "num": 101}, "'num' must be an integer"),
        ("serper", "serper_search", {"q": "x", "gl": "usa"}, "'gl' must match"),
        (
            "serpapi",
            "serpapi_search",
            {"q": "x", "start": 991},
            "'start' must be an integer",
        ),
        (
            "dataforseo",
            "dataforseo_serp",
            {"q": "x", "location_code": 0},
            "'location_code' must be",
        ),
        (
            "dataforseo",
            "dataforseo_serp",
            {"q": "x", "depth": 101},
            "'depth' must be an integer",
        ),
        (
            "zenserp",
            "zenserp_search",
            {"q": "x", "location": "a\x01b"},
            "'location' is not a valid",
        ),
        (
            "scrapingbee",
            "scrapingbee_google",
            {"q": "x", "light_request": "sometimes"},
            "must be a boolean",
        ),
        (
            "scrapingbee",
            "scrapingbee_google",
            {"q": "x", "page": 11},
            "'page' must be an integer",
        ),
        (
            "scrapingbee",
            "scrapingbee_google",
            {"q": "x", "date_range": "yesterday"},
            "'date_range' must be one of",
        ),
    ],
)
def test_bad_arguments_fail_before_any_request_or_reservation(
    vendor, tool, args, needle, make
):
    adapter = make(vendor)
    text = _error_text(adapter.handle_call(tool, args), vendor)
    assert needle in text, text
    assert fake.RECEIVED == []
    assert not os.path.exists(make.ledger.path)  # nothing reserved, nothing written


# --------------------------------------------------------------------------- #
# the hard spend cap (G-2)
# --------------------------------------------------------------------------- #
def test_daily_budget_is_per_vendor_and_names_the_reset(
    ledger_path, frozen_now, fake_transport
):
    env = _env("brave", "kagi", ledger=ledger_path, KEYED_MAX_CALLS_PER_DAY="2")
    brave, kagi = _build(env)
    first = _payload(brave.handle_call("brave_web_search", {"q": "one"}))
    assert first["spend"]["calls_today"] == 1 and first["spend"]["daily_budget"] == 2
    second = _payload(brave.handle_call("brave_web_search", {"q": "two"}))
    assert second["spend"]["calls_today"] == 2
    text = _error_text(brave.handle_call("brave_llm_context", {"q": "three"}), "brave")
    assert "daily call budget for brave reached: 2/2" in text
    assert "KEYED_MAX_CALLS_PER_DAY=2" in text
    assert f"resets at {DAILY_RESET}" in text
    assert "No request was made and nothing was billed" in text
    assert len(fake.RECEIVED) == 2  # the refused call never hit the wire
    other = _payload(kagi.handle_call("kagi_search", {"q": "still fine"}))  # per vendor
    assert other["spend"]["calls_today"] == 1
    assert len(fake.RECEIVED) == 3
    snap = brave.capabilities()["spend"]["today"]
    assert snap == {
        "date": "2026-09-02",
        "calls": 2,
        "budget": 2,
        "remaining": 0,
        "resets": DAILY_RESET,
    }


def test_monthly_cap_is_global_across_vendors_and_names_the_reset(
    ledger_path, frozen_now, fake_transport
):
    env = _env(
        "brave", "kagi", "marginalia", ledger=ledger_path, KEYED_SPEND_CAP_USD="0.006"
    )
    brave, kagi, marginalia = _build(env)
    first = _payload(brave.handle_call("brave_web_search", {"q": "one"}))  # $0.005
    assert first["spend"]["month_usd_estimated"] == 0.005
    assert first["spend"]["monthly_cap_usd"] == 0.006
    text = _error_text(brave.handle_call("brave_web_search", {"q": "two"}), "brave")
    assert "monthly spend cap reached" in text
    assert "$0.0050 is already spent across keyed vendors this month" in text
    assert "~$0.0050 at $5.00/1k" in text
    assert "KEYED_SPEND_CAP_USD=0.006" in text
    assert f"resets at {MONTHLY_RESET}" in text
    assert "No request was made and nothing was billed" in text
    other = _error_text(kagi.handle_call("kagi_search", {"q": "two"}), "kagi")  # global
    assert "monthly spend cap reached" in other and "$12.00/1k" in other
    assert len(fake.RECEIVED) == 1
    # an unpriced vendor is counted, not priced: the cap cannot refuse it
    free = _payload(marginalia.handle_call("marginalia_search", {"q": "small web"}))
    assert free["spend"]["estimated_usd"] is None
    assert free["spend"]["month_usd_estimated"] == 0.005
    assert len(fake.RECEIVED) == 2
    month = brave.capabilities()["spend"]["month"]
    assert month["calls_all_vendors"] == 2
    assert month["usd_estimated_all_vendors"] == 0.005
    assert month["remaining_usd"] == 0.001


def test_zero_cap_blocks_every_priced_call_before_the_first_request(make):
    adapter = make("brave", spend_cap_usd=0.0)
    text = _error_text(adapter.handle_call("brave_web_search", {"q": "x"}), "brave")
    assert "monthly spend cap reached" in text and "KEYED_SPEND_CAP_USD=0.00" in text
    assert fake.RECEIVED == []


def test_failed_attempts_count_against_the_budget(make):
    adapter = make("brave", key="X-Fake-Key-brave-WRONG-1234", max_calls_per_day=1)
    _error_text(adapter.handle_call("brave_web_search", {"q": "x"}), "brave")  # 401
    text = _error_text(adapter.handle_call("brave_web_search", {"q": "y"}), "brave")
    assert "daily call budget for brave reached: 1/1" in text
    assert len(fake.RECEIVED) == 1


def test_budget_and_cap_reset_on_rollover(ledger_path):
    clock = {"now": NOW}
    ledger = lk.Ledger(ledger_path, now=lambda: clock["now"])
    adapter = lk.BraveAdapter(
        f"{FAKE_BASE}/brave",
        fake.VALID_KEYS["brave"],
        ledger,
        caller=fake.fake_caller,
        max_calls_per_day=1,
        spend_cap_usd=0.005,
    )
    _payload(adapter.handle_call("brave_web_search", {"q": "day one"}))
    assert "daily call budget" in _error_text(
        adapter.handle_call("brave_web_search", {"q": "day one again"}), "brave"
    )
    clock["now"] = NOW + timedelta(
        days=1
    )  # new day, same month: budget resets, cap holds
    text = _error_text(
        adapter.handle_call("brave_web_search", {"q": "day two"}), "brave"
    )
    assert "monthly spend cap reached" in text and "daily call budget" not in text
    clock["now"] = datetime(2026, 10, 1, 0, 0, 1, tzinfo=timezone.utc)  # new month
    payload = _payload(adapter.handle_call("brave_web_search", {"q": "october"}))
    assert payload["spend"]["month_usd_estimated"] == 0.005
    assert payload["spend"]["resets"] == {
        "daily": "2026-10-02T00:00:00Z",
        "monthly": "2026-11-01T00:00:00Z",
    }
    data = _ledger_json(ledger_path)
    assert data["daily"] == {"2026-09-02": {"brave": 1}, "2026-10-01": {"brave": 1}}
    assert set(data["monthly"]) == {"2026-09", "2026-10"}
    assert data["monthly"]["2026-09"]["vendors"] == {
        "brave": {"calls": 1, "usd": 0.005}
    }


def test_ledger_file_is_valid_json_holds_no_key_and_leaves_no_temp_files(make):
    adapter = make("serpapi")
    for q in ("one", "two"):
        _payload(adapter.handle_call("serpapi_search", {"q": q}))
    directory = os.path.dirname(make.ledger.path)
    assert os.listdir(directory) == ["keyed-ledger.json"]
    raw = open(make.ledger.path, encoding="utf-8").read()
    assert "X-Fake-Key-serpapi" not in raw and "api_key" not in raw
    data = json.loads(raw)
    assert data["version"] == lk.LEDGER_VERSION
    assert data["daily"] == {"2026-09-02": {"serpapi": 2}}
    assert data["monthly"]["2026-09"] == {
        "calls": 2,
        "usd": 0.05,  # 2 x $25/1k
        "vendors": {"serpapi": {"calls": 2, "usd": 0.05}},
    }
    assert data["updated"] == "2026-09-02T07:15:00Z"
    assert "never holds a key" in data["note"]


def test_ledger_write_is_atomic_a_failed_replace_leaves_the_old_file_intact(
    make, monkeypatch
):
    adapter = make("brave")
    _payload(adapter.handle_call("brave_web_search", {"q": "one"}))
    before = open(make.ledger.path, encoding="utf-8").read()
    real_replace = os.replace

    def failing_replace(src, dst):
        if dst == make.ledger.path:
            raise OSError(28, "No space left on device")
        return real_replace(src, dst)

    monkeypatch.setattr(os, "replace", failing_replace)
    text = _error_text(adapter.handle_call("brave_web_search", {"q": "two"}), "brave")
    assert "cannot persist the keyed spend ledger" in text
    assert "No space left on device" in text and "KEYED_LEDGER_PATH" in text
    assert "No request was made" in text
    assert len(fake.RECEIVED) == 1
    assert open(make.ledger.path, encoding="utf-8").read() == before
    assert os.listdir(os.path.dirname(make.ledger.path)) == ["keyed-ledger.json"]


def test_unwritable_ledger_path_refuses_the_call_instead_of_skipping_the_cap(
    tmp_path, frozen_now
):
    blocker = tmp_path / "not-a-dir"
    blocker.write_text("i am a file", encoding="utf-8")
    ledger = lk.Ledger(str(blocker / "ledger.json"), now=lambda: NOW)
    adapter = lk.BraveAdapter(
        f"{FAKE_BASE}/brave", fake.VALID_KEYS["brave"], ledger, caller=fake.fake_caller
    )
    text = _error_text(adapter.handle_call("brave_web_search", {"q": "x"}), "brave")
    assert "cannot persist the keyed spend ledger" in text
    assert "refusing to call brave" in text
    assert fake.RECEIVED == []


@pytest.mark.parametrize(
    "garbage, reason",
    [
        ("{not json at all", "JSONDecodeError"),
        ('{"version": 99, "daily": []}', "unexpected shape"),
        ("[1, 2, 3]", "unexpected shape"),
    ],
)
def test_corrupt_ledger_is_renamed_aside_started_fresh_and_reported_once(
    garbage, reason, make
):
    os.makedirs(os.path.dirname(make.ledger.path), exist_ok=True)
    with open(make.ledger.path, "w", encoding="utf-8") as fh:
        fh.write(garbage)
    adapter = make("brave")
    payload = _payload(adapter.handle_call("brave_web_search", {"q": "one"}))
    [note] = payload["ledger_notes"]
    assert "was unreadable" in note and reason in note
    assert "renamed aside to" in note and "fresh ledger was started" in note
    assert "counts before this point are not enforced" in note
    listing = sorted(os.listdir(os.path.dirname(make.ledger.path)))
    assert listing == [
        "keyed-ledger.json",
        "keyed-ledger.json.corrupt-20260902T071500Z",
    ]
    with open(
        os.path.join(os.path.dirname(make.ledger.path), listing[1]), encoding="utf-8"
    ) as fh:
        assert fh.read() == garbage  # preserved, not destroyed
    assert _ledger_json(make.ledger.path)["daily"] == {"2026-09-02": {"brave": 1}}
    again = _payload(adapter.handle_call("brave_web_search", {"q": "two"}))
    assert "ledger_notes" not in again  # reported once
    assert again["spend"]["calls_today"] == 2


def test_old_days_and_months_are_pruned(ledger_path, frozen_now):
    os.makedirs(os.path.dirname(ledger_path), exist_ok=True)
    seed = lk.Ledger._fresh()
    seed["daily"] = {f"2026-08-{d:02d}": {"brave": 1} for d in range(10, 30)}
    seed["monthly"] = {
        f"2026-{m:02d}": {"calls": 1, "usd": 0.0, "vendors": {}} for m in range(1, 9)
    }
    with open(ledger_path, "w", encoding="utf-8") as fh:
        json.dump(seed, fh)
    ledger = lk.Ledger(ledger_path, now=lambda: NOW)
    granted, refusal = ledger.reserve("brave", "brave_web_search", 5.0, 200, 5.0)
    assert refusal is None and granted["calls_today"] == 1
    data = _ledger_json(ledger_path)
    assert len(data["daily"]) == lk.LEDGER_KEEP_DAYS and "2026-09-02" in data["daily"]
    assert min(data["daily"]) == "2026-08-24"
    assert sorted(data["monthly"]) == ["2026-07", "2026-08", "2026-09"]
    assert ledger.pop_notes() == []  # a valid old ledger is not "corrupt"


def test_reserve_is_thread_safe_under_the_daily_budget(ledger_path, frozen_now):
    ledger = lk.Ledger(ledger_path, now=lambda: NOW)
    outcomes: list[bool] = []
    lock = threading.Lock()

    def worker():
        granted, _refusal = ledger.reserve("brave", "brave_web_search", 5.0, 25, 100.0)
        with lock:
            outcomes.append(granted is not None)

    threads = [threading.Thread(target=worker) for _ in range(40)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert outcomes.count(True) == 25 and outcomes.count(False) == 15
    assert _ledger_json(ledger_path)["daily"]["2026-09-02"]["brave"] == 25


# --------------------------------------------------------------------------- #
# real loopback socket with the default header-aware urllib caller
# --------------------------------------------------------------------------- #
def test_real_loopback_socket_get_post_401_scrub_and_429(ledger_path, frozen_now):
    server = fake.make_server()
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        env = _env("brave", "serper", "dataforseo", ledger=ledger_path)
        for vendor in ("brave", "serper", "dataforseo"):
            env[f"{vendor.upper()}_API_URL"] = f"http://127.0.0.1:{port}/{vendor}"
        brave, serper, dataforseo = _build(env)  # default caller: real urllib
        assert brave._hcaller is adapters._default_header_caller
        web = _payload(brave.handle_call("brave_web_search", {"q": "over the wire"}))
        assert (
            web["count"] == 2
            and web["credits_hint"]["x-ratelimit-remaining"] == "0, 1999"
        )
        assert (
            fake.RECEIVED[-1]["headers"]["x-subscription-token"] == "X-Fake-Key-brave"
        )
        organic = _payload(
            serper.handle_call("serper_search", {"q": "posted", "num": 20})
        )
        assert organic["count"] == 2 and organic["credits_hint"] == {"credits": 2}
        assert fake.RECEIVED[-1]["body"]["num"] == 20
        serp = _payload(dataforseo.handle_call("dataforseo_serp", {"q": "basic auth"}))
        assert serp["count"] == 2 and serp["credits_hint"] == {"cost": 0.002}
        limited = _error_text(
            brave.handle_call("brave_web_search", {"q": "ratelimited"}), "brave"
        )
        assert "HTTP 429" in limited and "retry-after 17s" in limited
        env["BRAVE_API_KEY"] = "X-Fake-Key-brave-REJECTED-on-wire"
        [rejected] = [a for a in _build(env) if a.vendor == "brave"]
        text = _error_text(
            rejected.handle_call("brave_web_search", {"q": "x"}), "brave"
        )
        assert "HTTP 401" in text and "[redacted]" in text
        assert "X-Fake-Key-brave-REJECTED-on-wire" not in text
        assert (
            fake.RECEIVED[-1]["headers"]["x-subscription-token"]
            == "X-Fake-Key-brave-REJECTED-on-wire"
        )
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
