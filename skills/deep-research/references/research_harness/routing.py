"""Capability -> provider routing for the deep-research harness (M-16).

A *data-driven* table maps a research *capability* (not a tool name) to an
ordered list of providers (primary -> fallbacks). Sub-questions from the
deep-research workflow are each classified to a capability, then dispatched to
the highest-ranked provider that is currently *live* (see ``preflight``).

The table is the single choke-point to update when MCP tool names/quotas drift
(see the deep-research drift warning). It encodes the standing routing policy:

    web           -> firecrawl (primary) -> perplexity -> exa -> tavily
    synthesis     -> perplexity (primary) -> exa -> firecrawl
    neural        -> exa (primary) -> firecrawl
    academic      -> scholarly-access (OA) -> huggingface
    bio / pharma  -> tooluniverse -> scholarly-access
    code / repos  -> exa -> firecrawl(github) -> context7
    library docs  -> context7 -> exa
    deep_read     -> firecrawl(scrape) -> exa(fetch) -> tavily(extract)

Provider-strength split (the Perplexity correlation, M-16b):
  * ``synthesis`` is for "explain / compare / what's-the-consensus"-style
    sub-questions whose ideal answer is a *synthesized, cited* paragraph.
    Those route to Perplexity first (it drives the user's Pro/Max plan via a
    session cookie and returns an answer with inline citations).
  * Raw link discovery / page extraction stays on firecrawl + exa: ``web`` keeps
    firecrawl as primary, with Perplexity inserted as the high-priority #2
    corroborator (a cited second opinion) ahead of exa/tavily.

Hard guardrails baked in:
  * Sci-Hub is never routed to (``mcp__sci-hub__*``).
  * ``scholarly-access.paper_find_oa_pdf`` is excluded pending the standing
    regression revert.
  * Parked servers (``scrapegraph``, ``apify`` in ~/.mcp.disabled.json) are
    never routed to.

Compliance note: Perplexity here is a *cookie/session-auth* MCP (no paid API
key) — a gray-area approach like the IG/FB cookie MCPs. The secret cookie is
supplied to the MCP *server* via the ``PERPLEXITY_SESSION_TOKEN`` env var; it is
never stored in this routing table. Its session cookie can rate-limit/expire
(~30 days); preflight + the live-server filter route around it when it is down.
"""

from dataclasses import dataclass

# Source-tier priors (consumed by grading.py). A = primary/authoritative,
# B = reputable secondary, C = community.
TIER_A = "A"
TIER_B = "B"
TIER_C = "C"


@dataclass(frozen=True, slots=True)
class Provider:
    """A routable MCP provider: an MCP server key plus a tool on it."""

    server: str
    tool: str
    source_tier: str

    @property
    def key(self) -> str:
        """Stable dotted identifier, e.g. ``firecrawl.firecrawl_search``."""
        return f"{self.server}.{self.tool}"


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


# --- Capability -> ordered providers (primary first) ----------------------
ROUTING_TABLE: dict[str, tuple[Provider, ...]] = {
    # Raw web discovery: firecrawl primary (best for raw links/extraction),
    # Perplexity as the high-priority cited-corroborator #2, then exa/tavily.
    "web": (FIRECRAWL_SEARCH, PERPLEXITY_SMART, EXA_SEARCH, TAVILY_SEARCH),
    # Synthesis ("explain/compare/consensus"): Perplexity primary (cited
    # synthesized answer), exa/firecrawl as raw-source fallbacks.
    "synthesis": (PERPLEXITY_SMART, EXA_SEARCH, FIRECRAWL_SEARCH),
    "neural": (EXA_SEARCH, FIRECRAWL_SEARCH),
    "academic": (SCHOLARLY_RESOLVE, HF_PAPER_SEARCH),
    "bio": (TU_FIND_TOOLS, SCHOLARLY_RESOLVE),
    "code": (EXA_SEARCH, FIRECRAWL_GITHUB, CONTEXT7_DOCS),
    "library_docs": (CONTEXT7_DOCS, EXA_SEARCH),
    "deep_read": (FIRECRAWL_SCRAPE, EXA_FETCH, TAVILY_EXTRACT),
}

DEFAULT_CAPABILITY = "web"

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
            "repo",
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


def route_subquestion(
    subquestion: str,
    live_servers: set[str] | None = None,
    top_n: int | None = None,
) -> tuple[str, list[Provider]]:
    """Classify a sub-question then resolve its ordered live providers."""
    capability = classify_capability(subquestion)
    return capability, resolve_providers(capability, live_servers, top_n)
