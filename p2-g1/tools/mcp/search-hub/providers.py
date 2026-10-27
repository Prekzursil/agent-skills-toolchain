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
"""

from __future__ import annotations

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


# Exa's npm stdio server (``exa-mcp-server``) HARDCODES only web_search_exa +
# web_fetch_exa (verified 2026-07-07: no --tools/env/config flag expands it). The
# FULL 14-tool surface — advanced search, company/linkedin/people research,
# code-context, crawling, deep-researcher, and the agent-run deep-research tools —
# is only available on Exa's HTTP endpoint via ``?tools=``. We bridge that endpoint
# stdio<-HTTP with ``mcp-remote``, which interpolates the per-rotation key from the
# EXA_API_KEY env var into the ``x-api-key`` header (verified: 14 tools exposed,
# per-key rotation preserved because the hub still sets EXA_API_KEY per child).
_EXA_TOOLS = (
    "web_search_exa,web_search_advanced_exa,web_fetch_exa,company_research_exa,"
    "linkedin_search_exa,people_search_exa,get_code_context_exa,crawling_exa,"
    "deep_researcher_start,deep_researcher_check,"
    "agent_create_run,agent_wait_for_run,agent_get_run_output,agent_cancel_run"
)


def _exa_remote() -> tuple[str, ...]:
    """Stdio->HTTP bridge to Exa's FULL-surface endpoint; key from EXA_API_KEY env.

    mcp-remote substitutes ``${EXA_API_KEY}`` from its own environment (cmd.exe
    would not — it uses %VAR%), so the hub's per-key env injection still drives
    rotation while unlocking every Exa tool the neutered npm server dropped.
    """
    return (
        "cmd",
        "/c",
        "npx",
        "-y",
        "mcp-remote",
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
