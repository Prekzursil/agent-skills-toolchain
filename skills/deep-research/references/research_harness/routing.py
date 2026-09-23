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
    academic      -> scholarly-access (OA) -> huggingface
    bio / pharma  -> tooluniverse -> scholarly-access
    code / repos  -> exa -> firecrawl(github) -> context7
    library docs  -> context7 -> exa
    deep_read     -> firecrawl(scrape) -> exa(fetch) -> tavily(extract)
    vuln          -> cve-mcp(nvd_get) -> cve-mcp(nvd_search) -> cve-mcp(kev_search)
    ioc           -> osint(vt_ip) -> osint(vt_domain) -> osint(vt_url)
    attack        -> mitre-attack-mcp(search_techniques) -> mitre-attack-mcp(get_technique)
    longtail      -> searxng (key-free metasearch) -> exa

Key-free additions (M-16c, no API key / no quota):
  * ``searxng`` — a self-hosted SearXNG metasearch instance aggregating many
    upstream engines. Inserted as the high-priority **key-free corroborator** on
    ``web`` (ahead of the keyed exa/tavily) and as the primary for ``longtail``
    (obscure / rarely-documented queries where a metasearch beats a single index).
  * ``cve-mcp`` — authoritative vulnerability lookup (NVD / CIRCL / OSV / CISA-KEV
    / GitHub-Advisory / ExploitDB backed). Drives the ``vuln`` capability for CVE /
    exploit / CVSS / KEV questions; per the registry (G-11) the harness ``vuln`` route
    targets ``nvd_get`` / ``nvd_search`` / ``kev_search``. Tier A primary security
    data, key-free local MCP. Metadata only: no Nuclei/Metasploit execution.

Security-intel capabilities (W-routing, TIER-0 "route the dark tools"):
  * ``ioc`` — IOC reputation *enrichment* over the ``osint-mcp-server`` VirusTotal
    tools (``vt_ip`` -> ``vt_domain`` -> ``vt_url``). PASSIVE, like the rest of the
    OSINT lane: a lookup discloses the selector to VirusTotal and never scans or
    exploits; discovered assets do not enter scope (hacktricks
    ``security-mcp-routing.md`` envelope). All three names are confirmed against the
    live ``osint-mcp-server@0.2.0`` ``tools/list`` (37 tools, provenance
    ``.provenance/.agents/agents.json.md``); the estate's VT family is
    ``vt_domain`` / ``vt_ip`` / ``vt_subdomains`` / ``vt_url`` — there is **no**
    ``vt_file`` / hash-reputation tool, so file-hash IOCs classify to ``ioc`` but have
    no backing selector tool yet (proposed ``vt_file`` tracked in the W-routing
    receipt). ``vt_subdomains`` is passive-DNS enumeration, deliberately kept out of
    this reputation lane. Key-gated: the VirusTotal tools activate only when
    ``VT_API_KEY`` is set, so ``ioc`` degrades to ``web`` when the server is down /
    unkeyed (like ``vuln``); an unexpected tool name/schema fails closed at handshake.
  * ``attack`` — MITRE ATT&CK technique intel over ``mitre-attack-mcp``
    (``search_techniques`` primary, ``get_technique`` by-ID fallback; MHaggis/
    mitre-attack-mcp 1.0.1, Apache-2.0, keyless, optional ``ATTACK_DOMAIN``). The
    server is registered **and enabled** in the SSOT (agents.json, 29 tools) but is
    still only routed to when it probes live at preflight, so ``attack`` fails closed
    to ``web`` otherwise — the same graceful degradation ``vuln`` uses.

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
(~30 days); preflight + the live-server filter route around it when it is down.
"""

import re
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
# SearXNG key-free self-hosted metasearch (mcp-searxng, ``SEARXNG_URL`` env). No
# API key, no quota. Tier B = reputable aggregator (a metasearch layer over many
# engines, not itself a primary source). Key-free corroborator on ``web`` and the
# primary for ``longtail`` (obscure / rarely-documented queries).
SEARXNG_SEARCH = Provider("searxng", "searxng_web_search", TIER_B)
# cve-mcp authoritative vulnerability lookup (NVD/CIRCL/OSV/CISA-KEV/GHSA/ExploitDB).
# Tier A = primary/authoritative security data; key-free local MCP. Three real tool
# names drive the ``vuln`` capability (registry G-11): by-id NVD lookup, keyword NVD
# search, and the CISA Known-Exploited-Vulnerabilities search.
CVE_NVD_GET = Provider("cve-mcp", "nvd_get", TIER_A)
CVE_NVD_SEARCH = Provider("cve-mcp", "nvd_search", TIER_A)
CVE_KEV_SEARCH = Provider("cve-mcp", "kev_search", TIER_A)
# osint-mcp-server VirusTotal reputation tools drive the ``ioc`` capability
# (IOC enrichment). PASSIVE lookups only — a call discloses the selector to
# VirusTotal, never scans; discovered assets do not enter scope. Tier A primary
# reputation data, key-gated on ``VT_API_KEY``. All three names are confirmed
# against the live osint-mcp-server@0.2.0 tools/list (provenance); the estate's VT
# family is vt_domain/vt_ip/vt_subdomains/vt_url — there is no vt_file/hash tool
# (see the W-routing receipt for the proposed hash-reputation extension), and
# vt_subdomains is passive-DNS enumeration kept out of this reputation lane.
OSINT_VT_IP = Provider("osint-mcp-server", "vt_ip", TIER_A)
OSINT_VT_DOMAIN = Provider("osint-mcp-server", "vt_domain", TIER_A)
OSINT_VT_URL = Provider("osint-mcp-server", "vt_url", TIER_A)
# mitre-attack-mcp (MHaggis 1.0.1, Apache-2.0, keyless, optional ATTACK_DOMAIN)
# drives the ``attack`` capability: ATT&CK technique intel. ``search_techniques``
# (keyword) primary, ``get_technique`` (by ATT&CK ID, e.g. T1059.001) fallback.
# Tier A authoritative framework data. Registered AND enabled in the SSOT (29
# tools) but only routed to when it probes live, so ``attack`` fails closed to
# ``web`` otherwise.
ATTACK_SEARCH = Provider("mitre-attack-mcp", "search_techniques", TIER_A)
ATTACK_GET = Provider("mitre-attack-mcp", "get_technique", TIER_A)


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
    "academic": (SCHOLARLY_RESOLVE, HF_PAPER_SEARCH),
    "bio": (TU_FIND_TOOLS, SCHOLARLY_RESOLVE),
    "code": (EXA_SEARCH, FIRECRAWL_GITHUB, CONTEXT7_DOCS),
    "library_docs": (CONTEXT7_DOCS, EXA_SEARCH),
    "deep_read": (FIRECRAWL_SCRAPE, EXA_FETCH, TAVILY_EXTRACT),
    # Vulnerability / exploit intel: authoritative NVD by-id lookup first, then
    # keyword NVD search, then the CISA Known-Exploited-Vulnerabilities search.
    "vuln": (CVE_NVD_GET, CVE_NVD_SEARCH, CVE_KEV_SEARCH),
    # IOC reputation enrichment (PASSIVE): osint-mcp-server VirusTotal tools by
    # indicator type (ip -> domain -> url). Degrades to web when the osint server
    # is down / unkeyed, like ``vuln``. (No vt_file/hash tool exists upstream; a
    # file-hash IOC classifies here but has no selector tool yet — see receipt.)
    "ioc": (OSINT_VT_IP, OSINT_VT_DOMAIN, OSINT_VT_URL),
    # MITRE ATT&CK technique intel: keyword technique search first, by-ID lookup
    # second. Fails closed to web until mitre-attack-mcp probes live.
    "attack": (ATTACK_SEARCH, ATTACK_GET),
    # Long-tail / obscure queries: key-free SearXNG metasearch (aggregates many
    # engines) primary, exa neural as the fallback.
    "longtail": (SEARXNG_SEARCH, EXA_SEARCH),
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
    # IOC reputation enrichment. Security-specific like vuln; guarded so the
    # tokens don't false-match everyday words: `` ioc `` is space-padded so it
    # never fires inside "biochemical"/"audiocassette"; the hash tokens require
    # the word "hash" (or "virustotal"/"reputation") so a crypto-algorithm
    # question like "is sha256 secure?" is NOT pulled in; "reputation" is only
    # used in IOC-typed phrases, never bare (so "company reputation" stays web).
    # NB: the hash tokens route here for *intent* even though the estate's VT
    # family has no file-hash tool yet — the dispatcher degrades the hash sub-type
    # to web (proposed ``vt_file`` tracked in the W-routing receipt).
    (
        "ioc",
        (
            " ioc ",
            "iocs",
            "indicator of compromise",
            "indicators of compromise",
            "virustotal",
            "virus total",
            "file hash",
            "malware hash",
            "md5 hash",
            "sha1 hash",
            "sha256 hash",
            "sha-256 hash",
            "hash reputation",
            "hash lookup",
            "ip reputation",
            "domain reputation",
            "url reputation",
            "file reputation",
            "reputation lookup",
            "defang",
            "refang",
        ),
    ),
    # MITRE ATT&CK technique intel. Guarded: bare "attack"/"technique"/"tactic"
    # are too generic (attack surface, DDoS attack, marketing tactic), so we key
    # off the distinctive "mitre"/"att&ck" tokens and two-word ATT&CK phrases;
    # `` ttp ``/`` ttps `` are space-padded so they never fire inside "http"/
    # "https". Technique IDs (T1059, T1566.001) are matched structurally by
    # ``_CLASSIFIER_REGEX`` below rather than enumerated here.
    (
        "attack",
        (
            "mitre",
            "att&ck",
            "att&ck matrix",
            "attack technique",
            "attack tactic",
            "adversary technique",
            "mitre technique",
            " ttp ",
            " ttps ",
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


# Structural (regex) matchers checked alongside a capability's keyword tuple, in
# the same rule order. Used where enumerating tokens is infeasible: MITRE ATT&CK
# technique IDs like T1059 or T1566.001. Checked only when the loop reaches that
# capability, so vuln keeps priority over attack (a "CVE + T1059" question still
# routes to vuln because the vuln keyword rule is tested first).
_CLASSIFIER_REGEX: dict[str, "re.Pattern[str]"] = {
    "attack": re.compile(r"\bt\d{4}(?:\.\d{3})?\b"),
}


def classify_capability(subquestion: str) -> str:
    """Heuristically tag a sub-question with a routing capability.

    Cheap, conservative keyword match (plus a structural matcher for ATT&CK
    technique IDs). Falls back to ``web`` (the safest general capability) when
    nothing specific matches.
    """
    text = subquestion.lower()
    for capability, keywords in _CLASSIFIER_RULES:
        if any(keyword in text for keyword in keywords):
            return capability
        regex = _CLASSIFIER_REGEX.get(capability)
        if regex is not None and regex.search(text):
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


def all_provider_specs() -> tuple[Provider, ...]:
    """Every distinct provider referenced by the routing table, in stable order.

    Deduped by ``provider.key`` so a tool reused across capabilities is listed
    once. The skill-consistency test uses this to assert SKILL.md documents each
    routed exact tool name and never reintroduces a stale one.
    """
    seen: dict[str, Provider] = {}
    for providers in ROUTING_TABLE.values():
        for provider in providers:
            seen.setdefault(provider.key, provider)
    return tuple(seen.values())
