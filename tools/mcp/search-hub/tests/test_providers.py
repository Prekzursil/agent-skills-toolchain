#!/usr/bin/env python3
"""Tests for provider specs + the exhaustion-signal classifier (402 vs 429).

Pure, mocked: no live keys, no network -- just canned child response dicts fed
through ``providers.classify`` for each provider's rules, plus the environ-aware
provider list (default-ON keyless remotes with kill switches, opt-in heavies)
and its hub wiring against the fake stdio backend.
"""

from __future__ import annotations

import json
import os
import sys

import pytest

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
    assert specs["searxng"].key_env == ""
    # Exa's npm stdio server hardcodes only 2 tools, so we bridge the FULL-surface
    # HTTP endpoint via mcp-remote, injecting the per-rotation EXA_API_KEY into the
    # x-api-key header (mcp-remote does the ${VAR} substitution).
    exa_cmd = specs["exa"].cmd
    assert exa_cmd[:5] == ("cmd", "/c", "npx", "-y", "mcp-remote")
    assert exa_cmd[5].startswith("https://mcp.exa.ai/mcp?tools=")
    assert "web_search_advanced_exa" in exa_cmd[5] and "agent_run" in exa_cmd[5]
    assert exa_cmd[6:] == ("--header", "x-api-key:${EXA_API_KEY}")
    assert specs["tavily"].cmd == ("cmd", "/c", "npx", "-y", "tavily-mcp@latest")
    assert specs["firecrawl"].cmd == ("cmd", "/c", "npx", "-y", "firecrawl-mcp@latest")
    assert specs["searxng"].cmd == (
        "cmd",
        "/c",
        "npx",
        "-y",
        "mcp-searxng@1.8.0",
    )
    assert {s.prefix for s in specs.values()} == {"ex", "tv", "fc", "sx"}
    assert specs["searxng"].keyless
    assert dict(specs["searxng"].env_defaults) == {
        "SEARXNG_URL": "http://127.0.0.1:8890"
    }
    assert specs["searxng"].exhaust_patterns == ()
    assert specs["searxng"].rate_patterns == ()
    assert not any(specs[p].keyless for p in ("exa", "tavily", "firecrawl"))
    # Exa is error-driven; keyless SearXNG has no usage endpoint or balance.
    assert specs["exa"].usage_url == "" and specs["exa"].usage_kind == ""
    assert specs["searxng"].usage_url == "" and specs["searxng"].usage_kind == ""
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
    for platform in ("exa", "tavily", "firecrawl", "searxng"):
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


# --------------------------------------------------------------------------- #
# Exa cleanup (Lens 14): deprecated deep_researcher_* dropped, agent_run adopted
# --------------------------------------------------------------------------- #
def test_exa_tool_selector_drops_deprecated_and_uses_agent_run():
    """Live tools/list 2026-09-02: deep_researcher_start/check carry
    "[Deprecated]" and the four agent_* names all resolve to ONE tool named
    agent_run, so the ?tools= selector must name what the server serves."""
    selected = set(providers._EXA_TOOLS.split(","))
    assert "deep_researcher_start" not in selected
    assert "deep_researcher_check" not in selected
    assert not any(
        name.startswith("agent_") and name != "agent_run" for name in selected
    )
    assert "agent_run" in selected
    assert {"web_search_exa", "web_search_advanced_exa", "web_fetch_exa"} <= selected
    assert "" not in selected  # no stray comma


def test_exa_cache_matches_tool_selector():
    """The committed cache was regenerated from the live list with this exact
    selector; every cached name must be selected and vice versa."""
    with open(os.path.join(HUB_DIR, "caches", "exa.json"), encoding="utf-8") as fh:
        cached = {t["name"] for t in json.load(fh)["tools"]["tools"]}
    assert cached == set(providers._EXA_TOOLS.split(","))


# --------------------------------------------------------------------------- #
# environ-aware provider list: default_providers() stays the historical four,
# enabled_providers(environ) adds the gated remotes / opt-ins
# --------------------------------------------------------------------------- #
HISTORICAL = ["exa", "tavily", "firecrawl", "searxng"]
DEFAULT_ON_EXTRAS = ["parallel", "grepapp"]
OPT_IN_EXTRAS = ["corroborate", "openwebsearch", "ldr"]


def _platforms(specs) -> list[str]:
    return [s.platform for s in specs]


def test_default_providers_still_the_historical_four_in_order():
    assert _platforms(providers.default_providers()) == HISTORICAL


def test_enabled_providers_with_empty_environment():
    # Keyless remotes are DEFAULT ON; heavy / trial providers are OPT-IN.
    assert _platforms(providers.enabled_providers({})) == HISTORICAL + DEFAULT_ON_EXTRAS


def test_enabled_providers_defaults_to_os_environ(monkeypatch):
    for name in ("ENABLE_PARALLEL", "ENABLE_GREPAPP", "ENABLE_LDR", "LDR_URL"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("ENABLE_PARALLEL", "0")
    monkeypatch.setenv("ENABLE_LDR", "1")
    got = _platforms(providers.enabled_providers())
    assert "parallel" not in got and "ldr" in got and "grepapp" in got


@pytest.mark.parametrize("off", ["0", "false", "no", "off", " OFF "])
def test_kill_switch_removes_a_default_on_remote(off):
    got = _platforms(providers.enabled_providers({"ENABLE_PARALLEL": off}))
    assert "parallel" not in got and "grepapp" in got
    got = _platforms(providers.enabled_providers({"ENABLE_GREPAPP": off}))
    assert "grepapp" not in got and "parallel" in got


@pytest.mark.parametrize("on", ["", "1", "true", "yes", "anything"])
def test_default_on_remote_survives_unset_or_truthy_flag(on):
    env = {"ENABLE_PARALLEL": on, "ENABLE_GREPAPP": on}
    assert DEFAULT_ON_EXTRAS == [
        p
        for p in _platforms(providers.enabled_providers(env))
        if p in DEFAULT_ON_EXTRAS
    ]


@pytest.mark.parametrize(
    "flag,platform",
    [
        ("ENABLE_CORROBORATE", "corroborate"),
        ("ENABLE_OPENWEBSEARCH", "openwebsearch"),
        ("ENABLE_LDR", "ldr"),
    ],
)
def test_opt_in_provider_wired_only_when_explicitly_truthy(flag, platform):
    for off in ({}, {flag: ""}, {flag: "0"}, {flag: "false"}, {flag: "off"}):
        assert platform not in _platforms(providers.enabled_providers(off)), off
    for on in ("1", "true", "yes", "on"):
        assert platform in _platforms(providers.enabled_providers({flag: on})), on


def test_enabled_providers_order_is_stable_and_complete():
    every = {
        f: "1" for f in ("ENABLE_CORROBORATE", "ENABLE_OPENWEBSEARCH", "ENABLE_LDR")
    }
    assert _platforms(providers.enabled_providers(every)) == (
        HISTORICAL + DEFAULT_ON_EXTRAS + OPT_IN_EXTRAS
    )


def test_all_providers_ignores_flags_for_explicit_refresh():
    """`--refresh <id>` must reach an opt-in provider without enabling it."""
    every = _platforms(providers.all_providers({}))
    assert every == HISTORICAL + DEFAULT_ON_EXTRAS + OPT_IN_EXTRAS
    assert every == _platforms(providers.all_providers({"ENABLE_PARALLEL": "0"}))


def test_is_enabled_semantics():
    always = providers.ProviderSpec("x", "X", "xx", "", ("cmd",), "x.json")
    assert providers.is_enabled(always, {}) and providers.is_enabled(always, {"E": "0"})
    kill = providers.ProviderSpec(
        "k", "K", "kk", "", ("cmd",), "k.json", enable_env="E", opt_in=False
    )
    assert providers.is_enabled(kill, {}) and providers.is_enabled(kill, {"E": ""})
    assert not providers.is_enabled(kill, {"E": "0"})
    opt = providers.ProviderSpec(
        "o", "O", "oo", "", ("cmd",), "o.json", enable_env="E", opt_in=True
    )
    assert not providers.is_enabled(opt, {}) and not providers.is_enabled(
        opt, {"E": ""}
    )
    assert providers.is_enabled(opt, {"E": "1"}) and not providers.is_enabled(
        opt, {"E": "no"}
    )


def test_prefixes_and_caches_unique_across_every_known_provider():
    specs = providers.all_providers({})
    assert len({s.prefix for s in specs}) == len(specs)
    assert len({s.cache for s in specs}) == len(specs)
    assert len({s.platform for s in specs}) == len(specs)


# --------------------------------------------------------------------------- #
# the new specs: keyless (no account tools / rotation), verified launch argv
# --------------------------------------------------------------------------- #
def _all() -> dict[str, providers.ProviderSpec]:
    return {s.platform: s for s in providers.all_providers({})}


@pytest.mark.parametrize("platform", DEFAULT_ON_EXTRAS + OPT_IN_EXTRAS)
def test_new_providers_are_keyless_like_searxng(platform):
    spec = _all()[platform]
    assert spec.keyless and spec.key_env == "" and spec.max_backup_keys == 0
    assert spec.usage_url == "" and spec.usage_kind == ""
    # Mirror SearXNG: no classifier patterns -> always PASS, never cooled, and a
    # 429 / 403 from the origin is relayed verbatim (fail closed, never faked).
    assert spec.exhaust_patterns == () and spec.rate_patterns == ()
    sig, _ = providers.classify(spec, _iserror("HTTP 402 payment required"))
    assert sig == providers.PASS
    sig, _ = providers.classify(
        spec, _iserror("HTTP 429 Too Many Requests: Vercel Security Checkpoint")
    )
    assert sig == providers.PASS
    assert spec.enable_env.startswith("ENABLE_")


def test_remote_keyless_bridges_follow_the_exa_pattern():
    specs = _all()
    assert specs["parallel"].cmd == (
        "cmd",
        "/c",
        "npx",
        "-y",
        "mcp-remote",
        "https://search.parallel.ai/mcp",
    )
    assert (
        specs["parallel"].prefix == "pl" and specs["parallel"].cache == "parallel.json"
    )
    assert (
        specs["parallel"].enable_env == "ENABLE_PARALLEL"
        and not specs["parallel"].opt_in
    )
    # grep.app serves MCP at the host root (/mcp answers 404 "Invalid MCP endpoint").
    assert specs["grepapp"].cmd == (
        "cmd",
        "/c",
        "npx",
        "-y",
        "mcp-remote",
        "https://mcp.grep.app",
    )
    assert specs["grepapp"].prefix == "ga" and specs["grepapp"].cache == "grepapp.json"
    assert (
        specs["grepapp"].enable_env == "ENABLE_GREPAPP" and not specs["grepapp"].opt_in
    )
    # Keyless bridges carry no --header (nothing to interpolate).
    assert "--header" not in specs["parallel"].cmd + specs["grepapp"].cmd


def test_pinned_npx_stdio_children():
    specs = _all()
    assert specs["corroborate"].cmd == (
        "cmd",
        "/c",
        "npx",
        "-y",
        "corroborate-mcp@0.1.3",
    )
    assert specs["corroborate"].prefix == "cb" and specs["corroborate"].opt_in
    assert specs["corroborate"].enable_env == "ENABLE_CORROBORATE"
    assert specs["openwebsearch"].cmd == (
        "cmd",
        "/c",
        "npx",
        "-y",
        "open-websearch@2.1.11",
    )
    assert specs["openwebsearch"].prefix == "ow" and specs["openwebsearch"].opt_in
    assert specs["openwebsearch"].enable_env == "ENABLE_OPENWEBSEARCH"
    # MODE defaults to `both` upstream (binds HTTP :3000); the hub forces stdio
    # and HTTP-request search (never Playwright). Operator env still wins.
    assert dict(specs["openwebsearch"].env_defaults) == {
        "MODE": "stdio",
        "SEARCH_MODE": "request",
    }


def test_ldr_launches_local_uvx_or_bridges_to_ldr_url():
    local = {s.platform: s for s in providers.all_providers({"ENABLE_LDR": "1"})}["ldr"]
    assert local.cmd == (
        "uvx",
        "--from",
        "local-deep-research[mcp]==1.10.7",
        "ldr-mcp",
    )
    assert local.prefix == "ld" and local.cache == "ldr.json" and local.opt_in
    remote_env = {"ENABLE_LDR": "1", "LDR_URL": "http://10.0.0.7:8811/mcp"}
    remote = {s.platform: s for s in providers.enabled_providers(remote_env)}["ldr"]
    assert remote.cmd == (
        "cmd",
        "/c",
        "npx",
        "-y",
        "mcp-remote",
        "http://10.0.0.7:8811/mcp",
    )
    # A blank LDR_URL means "local", not "bridge to nowhere".
    blank = {
        s.platform: s
        for s in providers.enabled_providers({"ENABLE_LDR": "1", "LDR_URL": "  "})
    }
    assert blank["ldr"].cmd[0] == "uvx"
    # The URL alone never wires LDR: the flag is the only switch.
    assert "ldr" not in _platforms(
        providers.enabled_providers({"LDR_URL": "http://x/mcp"})
    )


# --------------------------------------------------------------------------- #
# hub wiring of the environ-aware list, against the fake stdio backend
# (no network): default-ON remotes are listed from cache with zero children,
# keyless providers get no account tools, and an origin 429 "Vercel Security
# Checkpoint" is relayed as a truthful isError -- never fabricated results.
# --------------------------------------------------------------------------- #
PY = sys.executable
FAKE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "fake_search_backend.py"
)


class _Capture:
    def __init__(self) -> None:
        self.msgs: list[dict] = []

    def __call__(self, line: str) -> None:
        self.msgs.append(json.loads(line))


def _fake_keyless(platform: str, prefix: str, tool: str, sentinel_value: str):
    sentinel = f"{platform.upper()}_TEST_SENTINEL"
    return providers.ProviderSpec(
        platform=platform,
        label=platform,
        prefix=prefix,
        key_env="",
        cmd=(PY, FAKE, platform, tool, sentinel),
        cache=f"{platform}.json",
        keyless=True,
        env_defaults=((sentinel, sentinel_value),),
        enable_env=f"ENABLE_{platform.upper()}",
        max_backup_keys=0,
    ).compiled()


def _hub_with(tmp_path, specs, environ):
    import accounts
    import hub
    import rotation

    old = hub.CACHE_DIR
    hub.CACHE_DIR = str(tmp_path)
    for spec in specs:
        ok, _n, msg = hub.refresh_provider(spec)
        assert ok, msg
    keyed = [s for s in specs if not s.keyless]
    store = accounts.AccountStore(
        str(tmp_path / "acc.json"),
        [hub._account_policy(s) for s in keyed],
        environ=environ,
    )
    rot = rotation.Rotator.from_specs(keyed, store, environ=environ)
    cap = _Capture()
    server = hub.SearchHub(
        specs, emit=cap, store=store, rotator=rot, environ=environ, self_hosted=[]
    )
    return server, cap, rot, old


def _call(mid, name, arguments=None):
    return {
        "jsonrpc": "2.0",
        "id": mid,
        "method": "tools/call",
        "params": {"name": name, "arguments": arguments or {}},
    }


def test_hub_lists_keyless_remote_tools_from_cache_without_spawning(tmp_path):
    import hub

    specs = [
        _fake_keyless("grepapp", "ga", "searchGitHub", "ok"),
        _fake_keyless("parallel", "pl", "web_search", "ok"),
    ]
    server, cap, _rot, old = _hub_with(tmp_path, specs, {})
    try:
        server.dispatch(
            {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}
        )
        names = {t["name"] for t in cap.msgs[0]["result"]["tools"]}
        assert {"searchGitHub", "web_search", "search_usage"} <= names
        assert not any("_account_" in n for n in names)  # keyless: no account tools
        assert server._children == {}
        assert server.keyed_specs == []
    finally:
        hub.CACHE_DIR = old


def test_hub_relays_origin_429_checkpoint_as_truthful_error(tmp_path, monkeypatch):
    """Lens 7 saw HTTP 429 "Vercel Security Checkpoint" from a datacenter IP.
    The keyless route must surface that verbatim as isError: no rotator, no
    cooldown state, and never a fabricated result."""
    import hub

    spec = _fake_keyless("grepapp", "ga", "searchGitHub", "checkpoint")
    server, cap, rot, old = _hub_with(tmp_path, [spec], {})
    try:

        def reject(*_a, **_k):
            raise AssertionError("keyless provider entered the rotator")

        monkeypatch.setattr(rot, "route_call", reject)
        server.dispatch(_call(7, "searchGitHub", {"query": "def x("}))
        reply = cap.msgs[-1]
        assert reply["id"] == 7
        assert reply["result"]["isError"] is True
        text = reply["result"]["content"][0]["text"]
        assert "429" in text and "Vercel Security Checkpoint" in text
        assert rot._health == {}  # no cooldown record was ever created
    finally:
        hub.CACHE_DIR = old
        for child in server._children.values():
            child._terminate()


def test_hub_serves_keyless_remote_hit_when_origin_answers(tmp_path):
    import hub

    spec = _fake_keyless("parallel", "pl", "web_search", "ok")
    server, cap, _rot, old = _hub_with(tmp_path, [spec], {})
    try:
        server.dispatch(_call(8, "web_search", {"objective": "mcp transports"}))
        reply = cap.msgs[-1]
        payload = json.loads(reply["result"]["content"][0]["text"])
        assert payload["backend"] == "parallel"
        assert payload["received_name"] == "web_search"
        assert payload["arguments"] == {"objective": "mcp transports"}
        assert ("parallel", "keyless") in server._children
    finally:
        hub.CACHE_DIR = old
        for child in server._children.values():
            child._terminate()


def test_real_enabled_providers_build_a_hub_from_committed_caches(tmp_path):
    """The committed caches + real specs must route without spawning: the
    default-ON remotes are advertised, opt-ins are absent, and an opt-in with
    no committed cache is reported as degraded rather than invented."""
    import accounts
    import hub

    environ = {"ENABLE_LDR": "1"}
    specs = providers.enabled_providers(environ)
    keyed = [s for s in specs if not s.keyless]
    store = accounts.AccountStore(
        str(tmp_path / "acc.json"),
        [hub._account_policy(s) for s in keyed],
        environ=environ,
    )
    cap = _Capture()
    server = hub.SearchHub(
        specs, emit=cap, store=store, environ=environ, self_hosted=[]
    )
    server.dispatch({"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}})
    names = {t["name"] for t in cap.msgs[0]["result"]["tools"]}
    assert {"web_search", "web_fetch", "searchGitHub"} <= names  # parallel + grep.app
    assert "agent_run" in names and "deep_researcher_start" not in names  # Exa cleanup
    assert not any(
        n.startswith(("pl_account_", "ga_account_", "ld_account_")) for n in names
    )
    assert server.routes["web_search"].platform == "parallel"
    assert server.routes["searchGitHub"].platform == "grepapp"
    assert server._children == {}
    cached = {os.path.splitext(f)[0] for f in os.listdir(hub.CACHE_DIR)}
    if "ldr" in cached:
        assert "ldr" not in server.degraded
    else:
        assert server.degraded.get("ldr", "").startswith("no cached tool list")


# --------------------------------------------------------------------------- #
# hub.py wiring (fakes only): the runtime + --print-plan build from
# enabled_providers(); an explicit `--refresh <id>` reaches an opt-in spec
# WITHOUT switching it on; a bare `--refresh` touches only what is wired.
# --------------------------------------------------------------------------- #
ALL_FLAGS = (
    "ENABLE_PARALLEL",
    "ENABLE_GREPAPP",
    "ENABLE_CORROBORATE",
    "ENABLE_OPENWEBSEARCH",
    "ENABLE_LDR",
    "LDR_URL",
)


def _clear_flags(monkeypatch) -> None:
    for name in ALL_FLAGS:
        monkeypatch.delenv(name, raising=False)


def _record_refresh(into: list[str]):
    def fake(spec, timeout=0.0):
        into.append(spec.platform)
        return True, 1, "ok (fake)"

    return fake


def test_main_runs_the_hub_over_enabled_providers(monkeypatch):
    import hub

    _clear_flags(monkeypatch)
    monkeypatch.setenv("ENABLE_GREPAPP", "0")
    monkeypatch.setenv("ENABLE_CORROBORATE", "1")
    seen: list[list[str]] = []

    class FakeHub:
        def __init__(self, specs, *args, **kwargs):
            seen.append(_platforms(specs))

        def run(self) -> int:
            return 0

    monkeypatch.setattr(hub, "SearchHub", FakeHub)
    assert hub.main([]) == 0
    assert seen == [HISTORICAL + ["parallel", "corroborate"]]


def test_refresh_by_name_reaches_an_opt_in_without_enabling_it(monkeypatch):
    import hub

    _clear_flags(monkeypatch)
    refreshed: list[str] = []
    monkeypatch.setattr(hub, "refresh_provider", _record_refresh(refreshed))
    assert hub._cmd_refresh(["ldr", "parallel"]) == 0
    assert refreshed == ["parallel", "ldr"]  # list order, flags ignored


def test_bare_refresh_touches_only_wired_providers(monkeypatch):
    import hub

    _clear_flags(monkeypatch)
    monkeypatch.setenv("ENABLE_PARALLEL", "0")
    refreshed: list[str] = []
    monkeypatch.setattr(hub, "refresh_provider", _record_refresh(refreshed))
    assert hub._cmd_refresh([]) == 0
    assert refreshed == HISTORICAL + ["grepapp"]  # no opt-in, no killed remote


def test_print_plan_counts_enabled_providers(monkeypatch, capsys):
    import hub

    _clear_flags(monkeypatch)
    monkeypatch.setenv("ENABLE_LDR", "1")
    monkeypatch.setattr(hub, "build_routes", lambda specs, cache_dir: ([], {}, {}))
    monkeypatch.setattr(hub.lanes, "extra_adapters", lambda environ: ([], {}))
    monkeypatch.setattr(hub.adapters, "wired_adapters", lambda environ: [])
    assert hub._cmd_print_plan() == 0
    plan = json.loads(capsys.readouterr().out)
    assert list(plan["per_provider"]) == HISTORICAL + DEFAULT_ON_EXTRAS + ["ldr"]
    # Only the three keyed providers carry account tools; keyless ones never do.
    assert plan["account_tools"] == 3 * len(hub.accounts.ACCOUNT_OPS)


def test_usage_tool_description_enumerates_every_known_platform():
    import hub

    text = json.dumps(hub._usage_tool_def())
    for spec in providers.all_providers({}):
        assert spec.platform in text, spec.platform
