"""Source-confidence grading for the deep-research harness (M-16).

Closes the gap the base deep-research report template leaves open (it cites but
never *grades*). Every source/claim gets a deterministic confidence tier from
three signals:

    confidence = f(source_tier, corroboration_count, recency)

  * source_tier  - A primary/authoritative, B reputable secondary, C community.
                   Derived as the *best* of a domain-authority prior and the
                   routing provider prior.
  * corroboration - how many independent sources assert the claim. A single
                    source is flagged UNVERIFIED (base skill cross-ref rule).
  * recency       - within ~12 months boosts (base skill recency rule).

Output per source: a tier, a High/Medium/Low confidence, and a compact
provenance tag such as ``[A.corrob x2.2026]`` or
``[C.single.2024 - UNVERIFIED]``.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.parse import urlparse

TIER_A = "A"
TIER_B = "B"
TIER_C = "C"

_TIER_RANK = {TIER_A: 2, TIER_B: 1, TIER_C: 0}
_RANK_TIER = {2: TIER_A, 1: TIER_B, 0: TIER_C}

# Domain substrings that imply a primary/authoritative (A) source.
_TIER_A_DOMAINS = (
    ".gov",
    ".edu",
    "doi.org",
    "ncbi.nlm.nih.gov",
    "pubmed",
    "arxiv.org",
    "nature.com",
    "sciencedirect.com",
    "springer.com",
    "nih.gov",
    "who.int",
    "europa.eu",
    "ietf.org",
    "rfc-editor.org",
    # Authoritative vulnerability / security data sources (vuln capability).
    "nvd.nist.gov",
    "cisa.gov",
    "first.org",
    "osv.dev",
    "exploit-db.com",
)
# Domain substrings that imply a reputable secondary (B) source.
_TIER_B_DOMAINS = (
    "wikipedia.org",
    "github.com",
    "stackoverflow.com",
    "reuters.com",
    "bbc.co",
    "bbc.com",
    "nytimes.com",
    "theguardian.com",
    "bloomberg.com",
    "techcrunch.com",
    "arstechnica.com",
    "docs.",
    "developer.",
)

# Provider prior: best tier a provider's results can claim before domain signal.
_PROVIDER_PRIOR = {
    "scholarly-access": TIER_A,
    "context7": TIER_A,
    "tooluniverse": TIER_A,
    "cve-mcp": TIER_A,  # authoritative NVD/CIRCL/OSV/CISA-KEV vulnerability data
    "firecrawl": TIER_B,
    "exa": TIER_B,
    "tavily": TIER_B,
    "huggingface": TIER_B,
    "searxng": TIER_B,  # reputable key-free metasearch aggregator
}

# A source whose host is a Tor/onion (dark-web) address can never be treated as
# corroborated/verified, regardless of how many other sources echo it. Such a
# source is force-flagged UNVERIFIED and capped at Low confidence.
_DARK_WEB_MARKERS = (".onion",)


@dataclass(frozen=True, slots=True)
class Source:
    """A single research source to be graded."""

    title: str
    url: str
    provider: str  # provider key OR bare server name
    published_year: int | None = None


@dataclass(frozen=True, slots=True)
class Grade:
    """Deterministic grade for one source/claim."""

    tier: str
    confidence: str  # "High" | "Medium" | "Low"
    corroboration_count: int
    recent: bool
    unverified: bool
    provenance: str


def _domain_tier(url: str) -> str:
    host = (urlparse(url).hostname or "").lower()
    if any(token in host for token in _TIER_A_DOMAINS):
        return TIER_A
    if any(token in host for token in _TIER_B_DOMAINS):
        return TIER_B
    return TIER_C


def _provider_tier(provider: str) -> str:
    server = provider.split(".", 1)[0]
    return _PROVIDER_PRIOR.get(server, TIER_C)


def is_dark_web(url: str) -> bool:
    """True if the URL points at a Tor/onion (dark-web) host.

    Such sources are force-flagged UNVERIFIED in ``grade_source`` no matter how
    many other sources echo them (the dark-web-forced-UNVERIFIED guardrail).
    """
    host = (urlparse(url).hostname or "").lower()
    return any(marker in host for marker in _DARK_WEB_MARKERS)


def source_tier(source: Source) -> str:
    """Best of the domain-authority prior and the provider prior."""
    rank = max(_TIER_RANK[_domain_tier(source.url)], _TIER_RANK[_provider_tier(source.provider)])
    return _RANK_TIER[rank]


def _current_year() -> int:
    return datetime.now(timezone.utc).year


def grade_source(
    source: Source,
    *,
    corroboration_count: int = 1,
    reference_year: int | None = None,
) -> Grade:
    """Grade a source from tier x corroboration x recency. Fully deterministic.

    Scoring: tier(A=2,B=1,C=0) + corroborated(+1 if >=2 sources) +
    recent(+1 if within ~12 months). score>=3 -> High, ==2 -> Medium,
    <=1 -> Low. A single source is always flagged UNVERIFIED.
    """
    ref = _current_year() if reference_year is None else reference_year
    tier = source_tier(source)
    dark = is_dark_web(source.url)
    corroborated = corroboration_count >= 2
    recent = source.published_year is not None and source.published_year >= ref - 1

    score = _TIER_RANK[tier] + (1 if corroborated else 0) + (1 if recent else 0)
    if dark:
        # Dark-web sources are force-flagged UNVERIFIED and capped at Low,
        # regardless of corroboration/recency/tier.
        confidence = "Low"
        unverified = True
    elif score >= 3:
        confidence = "High"
        unverified = not corroborated
    elif score == 2:
        confidence = "Medium"
        unverified = not corroborated
    else:
        confidence = "Low"
        unverified = not corroborated

    return Grade(
        tier=tier,
        confidence=confidence,
        corroboration_count=corroboration_count,
        recent=recent,
        unverified=unverified,
        provenance=_format_provenance(
            tier, corroboration_count, source.published_year, unverified, dark=dark
        ),
    )


def _format_provenance(
    tier: str,
    corroboration_count: int,
    year: int | None,
    unverified: bool,
    *,
    dark: bool = False,
) -> str:
    corrob = f"corrob x{corroboration_count}" if corroboration_count >= 2 else "single"
    year_label = str(year) if year is not None else "n.d."
    if dark:
        suffix = " - UNVERIFIED (dark-web)"
    elif unverified:
        suffix = " - UNVERIFIED"
    else:
        suffix = ""
    return f"[{tier}.{corrob}.{year_label}{suffix}]"


def overall_confidence(grades: list[Grade]) -> str:
    """Report-level confidence derived from the distribution of claim grades."""
    if not grades:
        return "Low"
    total = len(grades)
    highs = sum(1 for g in grades if g.confidence == "High")
    lows = sum(1 for g in grades if g.confidence == "Low")
    if highs * 2 > total:
        return "High"
    if lows * 2 > total:
        return "Low"
    return "Medium"
