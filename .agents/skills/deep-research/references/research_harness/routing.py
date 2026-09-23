"""Capability -> provider routing for the deep-research harness (M-16).

A *data-driven* table maps a research *capability* (not a tool name) to an
ordered list of providers (primary -> fallbacks). Sub-questions from the
deep-research workflow are each classified to a capability, then dispatched to
the highest-ranked provider that is currently *live* (see ``preflight``).

The table is the single choke-point to update when MCP tool names/quotas drift
(see the deep-research drift warning). It encodes the standing routing policy:

    web           -> firecrawl (primary) -> perplexity -> searxng -> exa -> tavily
    synthesis     -> perplexity (primary) -> exa -> firecrawl
    neural        -> exa (primary) -> firecrawl
    academic      -> scholarly-access (OA) -> huggingface -> searxng(science)
    bio / pharma  -> tooluniverse -> scholarly-access
    code / repos  -> exa -> firecrawl(github) -> context7
    library docs  -> context7 -> exa
    deep_read     -> firecrawl(scrape) -> exa(fetch) -> tavily(extract)
    vuln          -> cve-mcp(nvd_get) -> cve-mcp(nvd_search) -> cve-mcp(kev_search)
    longtail      -> searxng (key-free metasearch) -> exa
    deep_research -> perplexity(deep_research) -> exa(agent) -> firecrawl(agent)
                     -> tavily(research)   [then the academic -> web chains]
    council       -> perplexity(council) -> exa(agent) -> firecrawl(agent)
                     [then the synthesis -> web chains]

Capability fallbacks (``CAPABILITY_FALLBACKS`` / ``resolve_with_fallback``):
when every provider on a capability's own chain is down, the router walks the
listed fallback capabilities in order instead of returning an empty list, and
reports which capability actually answered so the Methodology section can say
so. ``vuln`` falls back to ``web`` (the caller convention it always had).

Academic SearXNG lane (Lens 14 #2, ENABLE not build): the third ``academic``
entry is the *existing* ``searxng_web_search`` tool with ``categories=science``
(arxiv, crossref, google scholar, openalex, pubmed, semantic scholar ...) as a
default parameter — pure parameter routing, ranked after the keyed academic
providers. Several science engines ignore ``time_range``; verify which engines
the instance has enabled with ``searxng_instance_info`` before trusting recency.

Perplexity deep-research routing (G-5b): ``pplx_deep_research`` (sync; the
async pair ``pplx_deep_research_start`` / ``pplx_research_status`` is recorded
in ``ASYNC_COMPANIONS`` because this harness models providers as single tools)
and ``pplx_council`` are METERED (``METERED_TOOLS``, mirroring the harness's
metered-MCP advisory): check ``pplx_usage`` before spending and only spend them
in the budget's ``explore`` regime. Exa's ``deep_researcher_*`` pair is
deprecated upstream and deliberately NOT routed; ``agent_create_run`` (+ its
``agent_wait_for_run`` / ``agent_get_run_output`` companions) is the Exa lane.

Key-free additions (M-16c, no API key / no quota):
  * ``searxng`` — a self-hosted SearXNG metasearch instance aggregating many
    upstream engines. Inserted as the high-priority **key-free corroborator** on
    ``web`` (ahead of the keyed exa/tavily) and as the primary for ``longtail``
    (obscure / rarely-documented queries where a metasearch beats a single index).
  * ``cve-mcp`` — authoritative vulnerability lookup (NVD / CIRCL / OSV / CISA-KEV
    / ExploitDB backed). Drives the new ``vuln`` capability for CVE / exploit /
    CVSS / KEV questions. Tier A primary security data, key-free local MCP.

Provider-strength split (the Perplexity correlation, M-16b):
  * ``synthesis`` is for "explain / compare / what's-the-consensus"-style
    sub-questions whose ideal answer is a *synthesized, cited* paragraph.
    Those route to Perplexity first (it drives the user's Pro/Max plan via a
    session cookie and returns an answer with inline citations).
  * Raw link discovery / page extraction stays on firecrawl + exa: ``web`` keeps
    firecrawl as primary, with Perplexity inserted as the high-priority #2
    corroborator (a cited second opinion) ahead of exa/tavily.

OpenRouter is not in this table. T0 summarization of already-fetched sources
MAY use the ``openrouter-routing`` sidecar (free/cheap chat). Search and
``deep_read`` stay on the MCP providers below. Do not route via ``:online``
(deprecated) or OpenRouter ``openrouter:web_search``.

Hard guardrails baked in:
  * Sci-Hub is never routed to (``mcp__sci-hub__*``).
  * ``scholarly-access.paper_find_oa_pdf`` is excluded pending the standing
    regression revert.
  * Parked servers (``scrapegraph``, ``apify`` in ~/.mcp.disabled.json) are
    never routed to.
  * No dark-web / onion provider is in the table. If a ``.onion`` source ever
    reaches grading it is force-flagged UNVERIFIED regardless of corroboration
    (see ``grading.grade_source`` / ``grading.is_dark_web``).

Compliance note: Perplexity here is a *cookie/session-auth* MCP (no paid API
key) — a gray-area approach like the IG/FB cookie MCPs. The secret cookie is
supplied to the MCP *server* via the ``PERPLEXITY_SESSION_TOKEN`` env var; it is
never stored in this routing table. Its session cookie can rate-limit/expire
(~30 days); preflight + the live-server filter route around it when it is down
and it is never retried within a run (``preflight.retry_allowed``).
"""

from dataclasses import dataclass

# Source-tier priors (consumed by grading.py). A = primary/authoritative,
# B = reputable secondary, C = community.
TIER_A = "A"
TIER_B = "B"
TIER_C = "C"


@dataclass(frozen=True, slots=True)
class Provider:
    """A routable MCP provider: an MCP server key plus a tool on it.

    ``params`` are default tool arguments baked into the route (a tuple of
    ``(name, value)`` pairs so the dataclass stays hashable). They let one
    tool serve two capabilities — e.g. ``searxng_web_search`` plain on ``web``
    and with ``categories=science`` on ``academic`` — without a new provider.
    """

    server: str
    tool: str
    source_tier: str
    params: tuple[tuple[str, str], ...] = ()

    @property
    def key(self) -> str:
        """Stable dotted identifier, e.g. ``firecrawl.firecrawl_search``."""
        return f"{self.server}.{self.tool}"

    @property
    def default_params(self) -> dict[str, str]:
        """Route-level default tool arguments (merge under the caller's own)."""
        return dict(self.params)

    @property
    def label(self) -> str:
        """``key`` plus the baked-in params, e.g. ``x.tool(categories=science)``."""
        if not self.params:
            return self.key
        inner = ",".join(f"{name}={value}" for name, value in self.params)
        return f"{self.key}({inner})"


# --- Provider catalogue (active MCP servers only) -------------------------
FIRECRAWL_SEARCH = Provider("firecrawl", "firecrawl_search", TIER_B)
FIRECRAWL_SCRAPE = Provider("firecrawl", "firecrawl_scrape", TIER_B)
FIRECRAWL_GITHUB = Provider("firecrawl", "firecrawl_research_search_github", TIER_B)
EXA_SEARCH = Provider("exa", "web_search_exa", TIER_B)
EXA_FETCH = Provider("exa", "web_fetch_exa", TIER_B)
TAVILY_SEARCH = Provider("tavily", "tavily_search", TIER_B)
TAVILY_EXTRACT = Provider("tavily", "tavily_extract", TIER_B)
SCHOLARLY_RESOLVE = Provider("scholarly-access", "paper_resolve", TIER_A)
HF_PAPER_SEARCH = Provider("huggingface", "paper_search", TIER_B)
TU_FIND_TOOLS = Provider("tooluniverse", "find_tools", TIER_A)
CONTEXT7_DOCS = Provider("context7", "query-docs", TIER_A)
# Perplexity cookie/session-auth web MCP (jacob-bd/perplexity-web-mcp).
# ``pplx_smart_query`` is the maintainer's RECOMMENDED, quota-aware default: it
# checks the plan's remaining limits and auto-picks the best model, returning a
# synthesized answer *with inline citations*. Tier B = reputable aggregator
# (a synthesis layer over web sources, not itself a primary source).
PERPLEXITY_SMART = Provider("perplexity", "pplx_smart_query", TIER_B)
# Perplexity long-form lanes (G-5b). Both are METERED (a Pro/Max deep-research
# pool): the harness's metered-MCP advisory names exactly these tools. Tier B =
# synthesis layer over web sources. ``pplx_deep_research`` is the synchronous
# form; its async pair is recorded in ``ASYNC_COMPANIONS`` below.
PERPLEXITY_DEEP_RESEARCH = Provider("perplexity", "pplx_deep_research", TIER_B)
PERPLEXITY_COUNCIL = Provider("perplexity", "pplx_council", TIER_B)
# Long-form research agents on the keyed providers — the fallback chain behind
# Perplexity's deep-research lanes. Exa ``agent_create_run`` supersedes the
# deprecated ``deep_researcher_start``/``_check`` pair (Lens 14); Firecrawl's
# ``firecrawl_agent`` and Tavily's ``tavily_research`` are their research agents.
# All three spend credits, so they are METERED too.
EXA_AGENT_RUN = Provider("exa", "agent_create_run", TIER_B)
FIRECRAWL_AGENT = Provider("firecrawl", "firecrawl_agent", TIER_B)
TAVILY_RESEARCH = Provider("tavily", "tavily_research", TIER_B)
# SearXNG key-free self-hosted metasearch (mcp-searxng, ``SEARXNG_URL`` env). No
# API key, no quota. Tier B = reputable aggregator (a metasearch layer over many
# engines, not itself a primary source). Key-free corroborator on ``web`` and the
# primary for ``longtail`` (obscure / rarely-documented queries).
SEARXNG_SEARCH = Provider("searxng", "searxng_web_search", TIER_B)
# The SAME tool with ``categories=science`` baked in: SearXNG's science category
# (arxiv, crossref, google scholar, openalex, pubmed, semantic scholar, ...) as
# a keyless academic lane (Lens 14 #2 — ENABLE, not build). Alternative spelling
# for an instance with the category renamed: ``engines="arxiv,google scholar,
# pubmed,semantic scholar,openalex,crossref"``. Several science engines ignore
# ``time_range``; ``searxng_instance_info`` shows which engines are enabled.
SEARXNG_SCIENCE = Provider(
    "searxng", "searxng_web_search", TIER_B, params=(("categories", "science"),)
)
# cve-mcp authoritative vulnerability lookup (NVD/CIRCL/OSV/CISA-KEV/ExploitDB).
# Tier A = primary/authoritative security data; key-free local MCP. Three tools
# drive the ``vuln`` capability: by-id NVD lookup, keyword NVD search, and the
# CISA Known-Exploited-Vulnerabilities catalog search. Names are the exact
# cve-mcp@0.2.0 schemas (hacktricks/references/security-mcp-routing.md); the
# earlier ``cve_lookup``/``cve_search``/``cve_kev_list`` never existed upstream.
CVE_NVD_GET = Provider("cve-mcp", "nvd_get", TIER_A)
CVE_NVD_SEARCH = Provider("cve-mcp", "nvd_search", TIER_A)
CVE_KEV_SEARCH = Provider("cve-mcp", "kev_search", TIER_A)


# --- Capability -> ordered providers (primary first) ----------------------
ROUTING_TABLE: dict[str, tuple[Provider, ...]] = {
    # Raw web discovery: firecrawl primary (best for raw links/extraction),
    # Perplexity as the high-priority cited-corroborator #2, SearXNG as the
    # high-priority KEY-FREE corroborator #3 (ahead of the keyed exa/tavily).
    "web": (
        FIRECRAWL_SEARCH,
        PERPLEXITY_SMART,
        SEARXNG_SEARCH,
        EXA_SEARCH,
        TAVILY_SEARCH,
    ),
    # Synthesis ("explain/compare/consensus"): Perplexity primary (cited
    # synthesized answer), exa/firecrawl as raw-source fallbacks.
    "synthesis": (PERPLEXITY_SMART, EXA_SEARCH, FIRECRAWL_SEARCH),
    "neural": (EXA_SEARCH, FIRECRAWL_SEARCH),
    # Academic: keyed OA resolvers first, then the keyless SearXNG science lane
    # (same tool as ``web``'s searxng entry, ``categories=science`` baked in).
    "academic": (SCHOLARLY_RESOLVE, HF_PAPER_SEARCH, SEARXNG_SCIENCE),
    "bio": (TU_FIND_TOOLS, SCHOLARLY_RESOLVE),
    "code": (EXA_SEARCH, FIRECRAWL_GITHUB, CONTEXT7_DOCS),
    "library_docs": (CONTEXT7_DOCS, EXA_SEARCH),
    "deep_read": (FIRECRAWL_SCRAPE, EXA_FETCH, TAVILY_EXTRACT),
    # Vulnerability / exploit intel: authoritative CVE lookup first, then
    # keyword CVE search, then the CISA Known-Exploited-Vulnerabilities catalog.
    "vuln": (CVE_NVD_GET, CVE_NVD_SEARCH, CVE_KEV_SEARCH),
    # Long-tail / obscure queries: key-free SearXNG metasearch (aggregates many
    # engines) primary, exa neural as the fallback.
    "longtail": (SEARXNG_SEARCH, EXA_SEARCH),
    # Long-form deep research (G-5b): Perplexity's deep-research lane first,
    # then the keyed research agents. All metered; budget-gated to ``explore``.
    "deep_research": (
        PERPLEXITY_DEEP_RESEARCH,
        EXA_AGENT_RUN,
        FIRECRAWL_AGENT,
        TAVILY_RESEARCH,
    ),
    # Multi-model deliberation: Perplexity council first, then the research
    # agents as the nearest deliberative substitutes.
    "council": (PERPLEXITY_COUNCIL, EXA_AGENT_RUN, FIRECRAWL_AGENT),
}

DEFAULT_CAPABILITY = "web"

# When a capability's own chain has no live provider, walk these capabilities
# in order (``resolve_with_fallback``). Kept explicit so the fallback is visible
# in the Methodology section rather than a silent downgrade.
CAPABILITY_FALLBACKS: dict[str, tuple[str, ...]] = {
    "deep_research": ("academic", "web"),
    "council": ("synthesis", "web"),
    "vuln": ("web",),
}

# Tools that spend a scarce quota (a Pro/Deep-Research pool or provider
# credits). Mirrors the harness's metered-MCP advisory: check the quota
# protocol (``pplx_usage`` / ``search_usage``) before spending, prefer the
# cheapest sufficient tier, and only spend in the budget's ``explore`` regime.
METERED_TOOLS = frozenset(
    {
        "pplx_deep_research",
        "pplx_deep_research_start",
        "pplx_council",
        "agent_create_run",
        "firecrawl_agent",
        "tavily_research",
    }
)

# Async companions of a routed tool: (start-or-poll, fetch). The harness models
# a provider as one tool, so the long-running forms are recorded here — NOT
# routed — and documented in SKILL.md next to the routed tool.
ASYNC_COMPANIONS: dict[str, tuple[str, ...]] = {
    "perplexity.pplx_deep_research": (
        "pplx_deep_research_start",
        "pplx_research_status",
    ),
    "exa.agent_create_run": ("agent_wait_for_run", "agent_get_run_output"),
}

# Tools that must never be routed to (standing guardrails).
EXCLUDED_TOOLS = frozenset(
    {
        "scholarly-access.paper_find_oa_pdf",
    }
)
EXCLUDED_SERVERS = frozenset({"sci-hub"})

# Servers parked in ~/.mcp.disabled.json — route around them.
PARKED_SERVERS = frozenset({"scrapegraph", "apify"})


# Keyword -> capability classifier. First capability whose keywords match the
# (lowercased) sub-question wins; order is significant (most specific first).
_CLASSIFIER_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    # Vulnerability / exploit intel FIRST: its keywords are highly
    # security-specific and don't collide with the other domains. ``rce`` and
    # ``kev`` are space-padded so they don't false-match inside "source"/
    # "resource"/"kevin"; the spelled-out phrases catch the abbreviations safely.
    (
        "vuln",
        (
            "cve",
            "cvss",
            "vulnerabilit",
            "exploit",
            "0-day",
            "zero-day",
            "remote code execution",
            " rce ",
            " kev ",
            "kev catalog",
            "known exploited",
        ),
    ),
    (
        "bio",
        (
            "gene",
            "protein",
            "pdb",
            "drug",
            "pharma",
            "compound",
            "molecule",
            "admet",
            "smiles",
            "clinical trial",
            "pathway",
            "enzyme",
            "receptor",
            "dosage",
        ),
    ),
    (
        "academic",
        (
            "paper",
            "study",
            "doi",
            "preprint",
            "arxiv",
            "peer-reviewed",
            "peer reviewed",
            "citation",
            "journal",
            "pubmed",
            "literature",
            "meta-analysis",
        ),
    ),
    (
        "library_docs",
        (
            "api docs",
            "api reference",
            "sdk",
            "documentation",
            "reference docs",
            "how to use the",
            "library docs",
        ),
    ),
    (
        "code",
        (
            # Whole-token: a bare "repo" substring-matched "report"/"reported"
            # and sent every "comprehensive report" question to the code lane.
            " repo ",
            " repos ",
            "repository",
            "github",
            "code example",
            "implementation",
            "snippet",
            "source code",
            "open source",
        ),
    ),
    (
        "neural",
        (
            "semantic search",
            "neural search",
            "similar to",
            "find similar",
        ),
    ),
    # Deliberation / long-form MODES come after the domain rules (a "deep
    # research on CVE-…" question is still a vuln question) and before the
    # generic longtail/synthesis phrasings. Both route to METERED tools, so the
    # keywords are deliberately explicit rather than broad.
    (
        "council",
        (
            "council",
            "multi-model",
            "multiple models",
            "panel of models",
            "model panel",
        ),
    ),
    (
        "deep_research",
        (
            "deep research",
            "deep-research",
            "comprehensive report",
            "exhaustive report",
            "in-depth report",
            "in depth report",
            "long-form report",
            "full landscape",
        ),
    ),
    # Long-tail: obscure / rarely-documented queries where a key-free metasearch
    # (SearXNG, many engines) beats any single index. Kept above synthesis so an
    # "obscure" intent isn't swallowed by a generic explain/compare phrasing.
    (
        "longtail",
        (
            "obscure",
            "long-tail",
            "long tail",
            "hard to find",
            "rarely documented",
            "little-known",
            "metasearch",
            "many search engines",
        ),
    ),
    # Synthesis must stay LAST among the rules so domain-specific routing
    # (bio/academic/library_docs/code/neural) still wins for a domain question
    # phrased as "explain/compare …". Only otherwise-general explain/compare/
    # consensus questions — whose ideal answer is a synthesized cited paragraph
    # — fall through to here and route to Perplexity.
    (
        "synthesis",
        (
            "explain",
            "compare",
            "comparison",
            "difference between",
            "versus",
            " vs ",
            "consensus",
            "what is the best",
            "what's the best",
            "pros and cons",
            "trade-off",
            "tradeoff",
            "tradeoffs",
            "overview of",
            "summarize",
            "summary of",
            "best practices",
            "how does",
            "why does",
            "why is",
        ),
    ),
)


def classify_capability(subquestion: str) -> str:
    """Heuristically tag a sub-question with a routing capability.

    Cheap, conservative keyword match. Falls back to ``web`` (the safest
    general capability) when nothing specific matches.
    """
    text = subquestion.lower()
    for capability, keywords in _CLASSIFIER_RULES:
        if any(keyword in text for keyword in keywords):
            return capability
    return DEFAULT_CAPABILITY


def is_excluded(provider: Provider) -> bool:
    """True if a provider is barred by a standing guardrail or is parked."""
    return (
        provider.key in EXCLUDED_TOOLS
        or provider.server in EXCLUDED_SERVERS
        or provider.server in PARKED_SERVERS
    )


def is_metered(provider: Provider) -> bool:
    """True if calling this tool spends a scarce quota (see ``METERED_TOOLS``)."""
    return provider.tool in METERED_TOOLS


def all_provider_specs() -> tuple[Provider, ...]:
    """Every distinct routed provider (server, tool, params), first-seen order.

    The SKILL.md consistency test iterates this so every routed *exact* tool
    name is documented; a tool that drifts out of the table also drifts out of
    the docs contract.
    """
    seen: dict[Provider, None] = {}
    for providers in ROUTING_TABLE.values():
        for provider in providers:
            seen.setdefault(provider, None)
    return tuple(seen)


def resolve_providers(
    capability: str,
    live_servers: set[str] | None = None,
    top_n: int | None = None,
) -> list[Provider]:
    """Return ordered providers for a capability, filtered for safety/liveness.

    Args:
        capability: a key of ``ROUTING_TABLE`` (unknown -> ``web``).
        live_servers: if given, only providers whose server is in this set are
            returned (graceful degradation around a down/quota provider). When
            ``None`` no liveness filter is applied.
        top_n: optionally cap the list (e.g. ``2`` for cross-provider
            corroboration diversity on a high-stakes sub-question).
    """
    providers = ROUTING_TABLE.get(capability, ROUTING_TABLE[DEFAULT_CAPABILITY])
    resolved = [p for p in providers if not is_excluded(p)]
    if live_servers is not None:
        resolved = [p for p in resolved if p.server in live_servers]
    if top_n is not None:
        resolved = resolved[:top_n]
    return resolved


def resolve_with_fallback(
    capability: str,
    live_servers: set[str] | None = None,
    top_n: int | None = None,
) -> tuple[list[Provider], str | None]:
    """``resolve_providers`` that walks ``CAPABILITY_FALLBACKS`` on an empty chain.

    Returns ``(providers, fallback_capability)``: ``fallback_capability`` is
    ``None`` when the capability's own chain answered, else the name of the
    fallback capability that did. An empty list means nothing anywhere is live.
    """
    providers = resolve_providers(capability, live_servers, top_n)
    if providers:
        return providers, None
    for fallback in CAPABILITY_FALLBACKS.get(capability, ()):
        providers = resolve_providers(fallback, live_servers, top_n)
        if providers:
            return providers, fallback
    return [], None


def route_subquestion(
    subquestion: str,
    live_servers: set[str] | None = None,
    top_n: int | None = None,
) -> tuple[str, list[Provider]]:
    """Classify a sub-question then resolve its ordered live providers."""
    capability = classify_capability(subquestion)
    return capability, resolve_providers(capability, live_servers, top_n)
