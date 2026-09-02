#!/usr/bin/env python3
"""Provider specs + the exhaustion-signal classifier for the search-hub rotator.

Each ``ProviderSpec`` describes ONE fronted search MCP (Exa, Tavily, Firecrawl,
SearXNG): its short id/prefix, the exact STDIO launch argv of the official
server, the API-key env-var name (empty for a keyless provider), the
per-provider tool-cache filename, the on-demand usage endpoint, and the
data-driven classifier that turns a child's error RESPONSE into a rotation
``Signal``.

The classifier is a PURE function of the child's JSON-RPC response text, so the
"402-exhaust vs 429-rate" decision per provider is unit-testable without a live
key or network. The reactive rotation policy (SG-2/SG-3 from the grill) is:

* ``EXHAUSTED``    -- a hard, billing-period exhaustion (Firecrawl/Exa HTTP 402,
  Exa ``NO_MORE_CREDITS``/``API_KEY_BUDGET_EXCEEDED``, an explicit Tavily usage
  cap): rotate to the next non-cooled key and cool this one LONG (paid keys only,
  so "cool until the billing period resets").
* ``RATE_LIMITED`` -- an HTTP 429: honour ``Retry-After`` and do NOT cool the key
  (SG-3). The hub returns the provider's native 429 unchanged; no rotation.
* ``AMBIGUOUS``    -- Tavily only: a 429 whose meaning (transient rate vs. quota
  exhaustion) is ambiguous, so the rotator probes ``/usage`` to decide.
* ``PASS``         -- not an exhaustion/rate signal; the response is returned
  verbatim.

Reusing a provider's OFFICIAL stdio server verbatim (no reimplementation) means
the fronted tool surface is exactly whatever that server advertises; the hub only
adds rotation + on-demand usage on top.

Gated providers (gem-hunt waves 2-3) join the four through ``enabled_providers``:
a ``ProviderSpec.enable_env`` flag is either a KILL SWITCH for a default-ON
keyless remote (Parallel, grep.app) or an OPT-IN for a trial / heavy child
(corroborate, open-websearch, local-deep-research). ``default_providers`` keeps
returning the historical four for existing callers; a keyless gated provider gets
no account tools, no rotation and no classifier, exactly like SearXNG, so an
origin 429/403 is relayed verbatim as a truthful error and never cools anything.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field

# Rotation signals a classified child response maps to.
PASS = "pass"
EXHAUSTED = "exhausted"
RATE_LIMITED = "rate_limited"
AMBIGUOUS = "ambiguous"

# ``Retry-After: <seconds>`` (or "retry after 30 seconds") anywhere in the text.
_RETRY_AFTER = re.compile(r"retry[\s_-]*after[\"'\s:=]*([0-9]+)", re.IGNORECASE)


@dataclass(frozen=True)
class ProviderSpec:
    """Immutable description of one fronted search provider + its rotation rules."""

    platform: str  # "exa" | "tavily" | "firecrawl" | "searxng"
    label: str
    prefix: str  # unique collision/account-tool prefix: ex | tv | fc | sx
    key_env: str  # API-key env var; empty for a keyless provider
    cmd: tuple[str, ...]  # stdio launch argv of the official MCP server
    cache: str  # committed tools/list cache filename
    keyless: bool = False  # direct route; no key store, cooldown, or account tools
    env_defaults: tuple[tuple[str, str], ...] = ()  # non-secret launch defaults
    usage_url: str = ""  # on-demand usage endpoint (empty => no balance API)
    usage_kind: str = ""  # "firecrawl" | "tavily" | "" (Exa: error-driven only)
    exhaust_patterns: tuple[str, ...] = ()  # hard-exhaustion signatures
    rate_patterns: tuple[str, ...] = ()  # 429 / rate-limit signatures
    ambiguous_on_rate: bool = False  # Tavily: a 429 needs a /usage probe
    max_backup_keys: int = 8  # how many numbered backups (KEY_2..) to seed
    enable_env: str = ""  # ENABLE_<X> flag; "" = always wired (the historical four)
    opt_in: bool = False  # True: wired only if enable_env is truthy; False: kill switch
    _exhaust_re: re.Pattern = field(default=None, compare=False, repr=False)
    _rate_re: re.Pattern = field(default=None, compare=False, repr=False)

    def compiled(self) -> "ProviderSpec":
        """Return a copy with the classifier regexes compiled (case-insensitive)."""
        exhaust = _compile_any(self.exhaust_patterns)
        rate = _compile_any(self.rate_patterns)
        object.__setattr__(self, "_exhaust_re", exhaust)
        object.__setattr__(self, "_rate_re", rate)
        return self


def _compile_any(patterns: tuple[str, ...]) -> re.Pattern | None:
    """Compile a case-insensitive OR of literal signatures, or None if empty."""
    if not patterns:
        return None
    return re.compile("|".join(re.escape(p) for p in patterns), re.IGNORECASE)


def error_text(response: dict) -> str:
    """Extract the human error text from a child's tools/call response.

    Handles both MCP shapes: a JSON-RPC ``error`` object and a ``result`` that
    carries ``isError`` with ``content[].text`` (how the exa/tavily/firecrawl TS
    servers surface an upstream HTTP failure). Returns "" for a clean result so
    the classifier reports ``PASS``.
    """
    parts: list[str] = []
    err = response.get("error")
    if isinstance(err, dict):
        msg = err.get("message")
        if isinstance(msg, str):
            parts.append(msg)
        data = err.get("data")
        if isinstance(data, str):
            parts.append(data)
        elif data is not None:
            parts.append(str(data))
    result = response.get("result")
    if isinstance(result, dict) and result.get("isError"):
        for item in result.get("content") or []:
            if isinstance(item, dict) and isinstance(item.get("text"), str):
                parts.append(item["text"])
    return "\n".join(parts)


def retry_after_seconds(text: str) -> int | None:
    """Parse a ``Retry-After`` hint (seconds) from the error text, if present."""
    match = _RETRY_AFTER.search(text or "")
    return int(match.group(1)) if match else None


def classify(spec: ProviderSpec, response: dict) -> tuple[str, int | None]:
    """Classify a child response into a rotation ``Signal`` + optional retry-after.

    Order matters: a HARD exhaustion signature wins over a rate signature (a
    single message may mention both), because rotating off a truly exhausted key
    is always correct, whereas a 429 must NOT rotate/cool (SG-3).
    """
    text = error_text(response)
    if not text:
        return PASS, None
    if spec._exhaust_re is not None and spec._exhaust_re.search(text):
        return EXHAUSTED, retry_after_seconds(text)
    if spec._rate_re is not None and spec._rate_re.search(text):
        signal = AMBIGUOUS if spec.ambiguous_on_rate else RATE_LIMITED
        return signal, retry_after_seconds(text)
    return PASS, None


def _npx(pkg: str) -> tuple[str, ...]:
    """Windows-safe stdio launch of an npm MCP server (npx is a .cmd shim)."""
    return ("cmd", "/c", "npx", "-y", pkg)


def _mcp_remote(url: str, *extra: str) -> tuple[str, ...]:
    """Stdio<-Streamable-HTTP bridge to a remote MCP endpoint via ``mcp-remote``.

    ``extra`` carries optional ``--header name:${ENV}`` pairs; mcp-remote does the
    ``${VAR}`` substitution from its own environment, so a key never appears in
    argv. Keyless remotes pass no header at all. Verified 2026-09-02 from the
    cloud VM with mcp-remote@0.8.3 against Parallel, grep.app and Exa (the
    bridged tools/list matched a direct HTTP probe byte-for-byte per tool).
    """
    return ("cmd", "/c", "npx", "-y", "mcp-remote", url, *extra)


# Exa's npm stdio server (``exa-mcp-server``) HARDCODES only web_search_exa +
# web_fetch_exa (verified 2026-07-07: no --tools/env/config flag expands it). The
# wider surface is only available on Exa's HTTP endpoint via ``?tools=``. We
# bridge that endpoint stdio<-HTTP with ``mcp-remote``, which interpolates the
# per-rotation key from the EXA_API_KEY env var into the ``x-api-key`` header
# (per-key rotation preserved because the hub still sets EXA_API_KEY per child).
#
# Re-probed live 2026-09-02 (server "exa-search-server" 3.2.1; Lens 14 cleanup):
# deep_researcher_start/check are served with a "[Deprecated]" description and
# the four agent_create_run/agent_wait_for_run/agent_get_run_output/agent_cancel_run
# names all resolve to ONE tool, ``agent_run`` (the only name Exa's docs list).
# So the deprecated pair is dropped and the quartet is replaced by ``agent_run``:
# 9 tools. company_research_exa / people_search_exa / linkedin_search_exa are
# ALSO flagged deprecated upstream ("use web_search_advanced_exa") but still
# work; they stay until a caller-facing removal is decided.
_EXA_TOOLS = (
    "web_search_exa,web_search_advanced_exa,web_fetch_exa,company_research_exa,"
    "linkedin_search_exa,people_search_exa,get_code_context_exa,crawling_exa,"
    "agent_run"
)


def _exa_remote() -> tuple[str, ...]:
    """Stdio->HTTP bridge to Exa's FULL-surface endpoint; key from EXA_API_KEY env.

    mcp-remote substitutes ``${EXA_API_KEY}`` from its own environment (cmd.exe
    would not — it uses %VAR%), so the hub's per-key env injection still drives
    rotation while unlocking every Exa tool the neutered npm server dropped.
    """
    return _mcp_remote(
        "https://mcp.exa.ai/mcp?tools=" + _EXA_TOOLS,
        "--header",
        "x-api-key:${EXA_API_KEY}",
    )


def default_providers() -> list[ProviderSpec]:
    """The four fronted search providers (order = tool-merge order).

    Package names + env vars verified live 2026-07 against the npm registry and
    each project's README: Exa's HTTP MCP via ``mcp-remote`` (EXA_API_KEY),
    ``tavily-mcp`` (TAVILY_API_KEY), ``firecrawl-mcp`` (FIRECRAWL_API_KEY), and
    ``mcp-searxng`` (keyless; SEARXNG_URL is inherited runtime configuration).
    """
    return [
        ProviderSpec(
            platform="exa",
            label="Exa",
            prefix="ex",
            key_env="EXA_API_KEY",
            cmd=_exa_remote(),  # full 14-tool HTTP surface (npm server only had 2)
            cache="exa.json",
            usage_url="",  # Exa has NO per-key balance API -> error-driven only
            usage_kind="",
            # Exa hard-exhaustion tags (HTTP 402) per the grill's provider facts.
            exhaust_patterns=(
                "NO_MORE_CREDITS",
                "API_KEY_BUDGET_EXCEEDED",
                "payment required",
                "insufficient credit",
                "out of credits",
                "402",
            ),
            rate_patterns=("429", "rate limit", "rate-limit", "too many requests"),
            ambiguous_on_rate=False,  # Exa 429 = pure rate limit; never rotate
        ).compiled(),
        ProviderSpec(
            platform="tavily",
            label="Tavily",
            prefix="tv",
            key_env="TAVILY_API_KEY",
            cmd=_npx("tavily-mcp@latest"),
            cache="tavily.json",
            usage_url="https://api.tavily.com/usage",
            usage_kind="tavily",
            # Explicit Tavily quota exhaustion (rotate immediately); a bare 429 is
            # AMBIGUOUS and resolved by probing /usage (ambiguous_on_rate).
            exhaust_patterns=(
                "usage limit",
                "plan limit",
                "quota exceeded",
                "out of credits",
                "insufficient credits",
                "payment required",
                "432",
                "402",
            ),
            rate_patterns=("429", "rate limit", "rate-limit", "too many requests"),
            ambiguous_on_rate=True,  # a Tavily 429 -> probe /usage to decide
        ).compiled(),
        ProviderSpec(
            platform="firecrawl",
            label="Firecrawl",
            prefix="fc",
            key_env="FIRECRAWL_API_KEY",
            cmd=_npx("firecrawl-mcp@latest"),
            cache="firecrawl.json",
            usage_url="https://api.firecrawl.dev/v2/team/credit-usage",
            usage_kind="firecrawl",
            # Firecrawl exhaustion = HTTP 402 "Insufficient credits".
            exhaust_patterns=(
                "insufficient credits",
                "insufficient credit",
                "payment required",
                "out of credits",
                "upgrade your plan",
                "402",
            ),
            rate_patterns=("429", "rate limit", "rate-limit", "too many requests"),
            ambiguous_on_rate=False,  # Firecrawl 429 carries Retry-After; no rotate
        ).compiled(),
        ProviderSpec(
            platform="searxng",
            label="SearXNG",
            prefix="sx",
            key_env="",
            cmd=_npx("mcp-searxng@1.8.0"),
            cache="searxng.json",
            keyless=True,
            env_defaults=(("SEARXNG_URL", "http://127.0.0.1:8890"),),
            usage_url="",
            usage_kind="",
            # A self-hosted, keyless fallback has no billing exhaustion signal.
            # With no classifier patterns it always PASSes and is never cooled.
            exhaust_patterns=(),
            rate_patterns=(),
            max_backup_keys=0,
        ).compiled(),
    ]


# --------------------------------------------------------------------------- #
# gated providers (waves 2-3) + the environ-aware list
# --------------------------------------------------------------------------- #
_FALSEY = ("0", "false", "no", "off")

# Pins verified on the npm registry / PyPI 2026-09-02 (see README "Providers").
CORROBORATE_PKG = "corroborate-mcp@0.1.3"  # MIT; 2 tools; keyless (RSS/GDELT/HN)
OPENWEBSEARCH_PKG = "open-websearch@2.1.11"  # Apache-2.0 upstream; 6 tools
LDR_PIP_SPEC = "local-deep-research[mcp]==1.10.7"  # MIT; `ldr-mcp` console script
LDR_URL_ENV = "LDR_URL"  # optional Streamable-HTTP MCP endpoint of a resident LDR


def is_enabled(spec: ProviderSpec, environ) -> bool:
    """Whether ``environ`` wires this spec (pure; mirrors the adapter lanes).

    * no ``enable_env``      -> always (the historical four);
    * kill switch (default ON) -> off only on an explicit falsey value
      (``0``/``false``/``no``/``off``); unset and "" both mean ON;
    * opt-in (default OFF)   -> on only on an explicit truthy value.
    """
    if not spec.enable_env:
        return True
    value = environ.get(spec.enable_env)
    normalized = value.strip().lower() if isinstance(value, str) else None
    if spec.opt_in:
        return normalized is not None and normalized not in ("",) + _FALSEY
    return normalized not in _FALSEY


def _keyless(**kw) -> ProviderSpec:
    """A gated keyless spec: no key store, rotation, account tools or classifier.

    Like SearXNG the classifier has NO patterns, so a child's 402/429/403 text
    can never create cooldown state; the hub relays the child's own error
    (``isError``) verbatim -- fail closed, never a fabricated hit.
    """
    return ProviderSpec(
        key_env="",
        keyless=True,
        usage_url="",
        usage_kind="",
        exhaust_patterns=(),
        rate_patterns=(),
        max_backup_keys=0,
        **kw,
    ).compiled()


def _ldr_cmd(environ) -> tuple[str, ...]:
    """LDR launch: upstream ships ``ldr-mcp`` as a STDIO-only console script of
    ``local-deep-research[mcp]`` (FastMCP, engine in-process; no HTTP MCP
    endpoint exists upstream -- verified in ``src/local_deep_research/mcp/`` +
    ``docs/mcp-server.md``, 2026-09-02). Default = run it locally via ``uvx``
    (enumerated live from the cloud VM: 8 tools in 21.5 s). When ``LDR_URL`` is
    set, the operator has fronted a RESIDENT ``ldr-mcp`` (the Wave-3 GPU/OVH box)
    with a Streamable-HTTP MCP gateway of their own, and the hub bridges to that
    URL instead -- upstream's own security note applies to that exposure. All
    ``LDR_*`` settings reach the child through the inherited environment.
    """
    url = (environ.get(LDR_URL_ENV) or "").strip()
    if url:
        return _mcp_remote(url)
    return ("uvx", "--from", LDR_PIP_SPEC, "ldr-mcp")


def optional_providers(environ=None) -> list[ProviderSpec]:
    """Every GATED spec (flag semantics on each), regardless of the flag state.

    Tool-list caches were captured live 2026-09-02 through the hub's own
    ``refresh_provider`` path (Linux argv, mcp-remote@0.8.3 / npx / uvx); see the
    README "Providers" section for the per-provider command + count.
    """
    environ = os.environ if environ is None else environ
    return [
        # Parallel Web Search MCP (server 1.27.0): web_search + web_fetch, keyless,
        # DEFAULT ON. Answered a live keyless web_search from the cloud VM.
        _keyless(
            platform="parallel",
            label="Parallel Search",
            prefix="pl",
            cmd=_mcp_remote("https://search.parallel.ai/mcp"),
            cache="parallel.json",
            enable_env="ENABLE_PARALLEL",
        ),
        # grep.app code search (Vercel-hosted; MCP at the host ROOT -- /mcp is a
        # 404 "Invalid MCP endpoint"): one tool, searchGitHub, keyless, DEFAULT
        # ON. Cross-lens caveat: Lens 6 got live snippets, Lens 7 got HTTP 429
        # "Vercel Security Checkpoint" from a datacenter IP; this VM (also a
        # datacenter IP) got live snippets 2026-09-02. Either way the child's
        # error text is relayed as isError -- there is nothing here to fake.
        _keyless(
            platform="grepapp",
            label="grep.app",
            prefix="ga",
            cmd=_mcp_remote("https://mcp.grep.app"),
            cache="grepapp.json",
            enable_env="ENABLE_GREPAPP",
        ),
        # corroborate-mcp TRIAL (single maintainer): counts independent origins
        # of a claim over Google News RSS + GDELT + Hacker News; returns an error
        # when its engines are down, never a fake UNCORROBORATED. OPT-IN.
        _keyless(
            platform="corroborate",
            label="Corroborate",
            prefix="cb",
            cmd=_npx(CORROBORATE_PKG),
            cache="corroborate.json",
            enable_env="ENABLE_CORROBORATE",
            opt_in=True,
        ),
        # open-webSearch (Aas-ee, Apache-2.0): keyless multi-engine scraper as a
        # resilience fallback when SearXNG parsers break. Upstream MODE defaults
        # to `both` (binds HTTP :3000) and SEARCH_MODE to `auto` (may pick
        # Playwright): the hub pins stdio + HTTP-request mode; operator env wins
        # (setdefault). OPT-IN.
        _keyless(
            platform="openwebsearch",
            label="open-webSearch",
            prefix="ow",
            cmd=_npx(OPENWEBSEARCH_PKG),
            cache="openwebsearch.json",
            env_defaults=(("MODE", "stdio"), ("SEARCH_MODE", "request")),
            enable_env="ENABLE_OPENWEBSEARCH",
            opt_in=True,
        ),
        # local-deep-research (MIT): the Wave-3 heavy answer engine (resident
        # 8-16 GB), so ON-DEMAND ONLY -- never spawned, never listed unless
        # ENABLE_LDR is truthy. Its own LLM/search keys are LDR_* settings, not
        # hub-rotated keys, hence keyless here.
        _keyless(
            platform="ldr",
            label="Local Deep Research",
            prefix="ld",
            cmd=_ldr_cmd(environ),
            cache="ldr.json",
            enable_env="ENABLE_LDR",
            opt_in=True,
        ),
    ]


def all_providers(environ=None) -> list[ProviderSpec]:
    """The historical four + every gated spec, flags IGNORED.

    For ``hub.py --refresh <id>``: naming a provider is explicit operator intent,
    so an opt-in cache can be (re)generated without switching the provider on.
    """
    return default_providers() + optional_providers(environ)


def enabled_providers(environ=None) -> list[ProviderSpec]:
    """What the hub wires: the four, then each gated spec ``is_enabled`` allows.

    Order = tool-merge order (a later duplicate tool name gets a ``<prefix>_``
    in ``hub.build_routes``; e.g. open-webSearch and LDR both expose ``search``).
    """
    environ = os.environ if environ is None else environ
    return default_providers() + [
        spec for spec in optional_providers(environ) if is_enabled(spec, environ)
    ]
