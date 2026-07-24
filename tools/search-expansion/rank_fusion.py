"""Reciprocal Rank Fusion over several search providers — rank-only, stdlib-only.

WHY RANK-ONLY, AND NOT SCORE NORMALISATION
------------------------------------------
Exa returns a relevance score, Tavily returns a score, SearXNG returns its own internal
score, Firecrawl returns none at all. Those numbers are produced by different models over
different corpora and are **not comparable quantities**. Min-max or z-scoring them does not
make them comparable — it invents a shared scale that never existed, and the fused ranking
then silently reflects which provider happened to have the widest spread.

Reciprocal Rank Fusion (Cormack, Clarke & Buettcher, SIGIR 2009) uses only the ordinal each
provider assigned: ``score(d) = sum over providers of 1 / (k + rank(d))``, rank 1-based.
Rank ordinals ARE comparable across providers — "this engine's best hit" means the same
thing everywhere. RRF needs no training, no tuning per corpus, and no new dependency, and
it beat the score-combination methods it was benchmarked against.

The single parameter ``k`` (default 60, the paper's value) damps the top of the curve: it
decides how much better rank 1 is than rank 2. Small ``k`` sharpens that gap; large ``k``
flattens it toward a plain vote count.

WHAT THIS ADDS OVER SEARXNG'S OWN MERGE
---------------------------------------
SearXNG already fuses the engines *inside one instance* (measured: a Yandex + DuckDuckGo
query returned 20 engine attributions across 19 results — one URL merged). It cannot see
Exa, Tavily or Firecrawl. This module fuses one level up, **across providers**, which is
where the independent-signal value is.

Everything here is a pure function: no I/O, no clock, no global state, no randomness. The
same inputs always produce the same ranking, and provider ordering cannot change it.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Iterable, Mapping, Sequence
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

__all__ = [
    "DEFAULT_K",
    "FusedResult",
    "extract_results",
    "fuse_provider_payloads",
    "normalize_url",
    "reciprocal_rank_fusion",
]

#: The value from the original RRF paper. Kept as the default so results are reproducible.
DEFAULT_K = 60.0

#: Query parameters that identify a *referral*, never a document. Stripping them stops the
#: same page arriving from three providers from being counted as three distinct documents.
#: ``yclid`` (Yandex) and ``spm``/``scm`` (Alibaba, i.e. Quark results) are here because the
#: regional engines this harness enables are exactly the ones that emit them.
_TRACKING_PARAMS = frozenset(
    {
        "fbclid",
        "gclid",
        "igshid",
        "mc_cid",
        "mc_eid",
        "msclkid",
        "ref_src",
        "scm",
        "spm",
        "yclid",
        "_ga",
    }
)
_TRACKING_PREFIXES = ("utm_",)

#: Payload keys that hold a result list, in the order they are tried.
_RESULT_KEYS = ("results", "data", "items", "hits", "web")
#: Keys tried inside a nested container (Firecrawl v2 returns ``data: {web: [...]}``).
_NESTED_KEYS = ("web", "results", "items")
_URL_KEYS = ("url", "link", "href")
_TITLE_KEYS = ("title", "name", "heading")


@dataclass(frozen=True)
class FusedResult:
    """One document in the fused ranking, with the provenance that produced it."""

    url: str
    """Normalised URL — the identity used for deduplication."""

    display_url: str
    """The original URL exactly as the first provider returned it."""

    title: str
    """First non-empty title seen across providers; ``""`` if none supplied one."""

    score: float
    """Summed reciprocal rank. Comparable only within one fusion run."""

    sources: tuple[str, ...]
    """Providers that returned this document, in the order they were consulted."""

    ranks: Mapping[str, int]
    """Provider -> the best (lowest, 1-based) rank it gave this document."""


def _is_tracking_param(key: str) -> bool:
    lowered = key.lower()
    return lowered in _TRACKING_PARAMS or lowered.startswith(_TRACKING_PREFIXES)


def normalize_url(url: str) -> str:
    """Reduce a URL to a stable identity for cross-provider deduplication.

    Normalises only what provably cannot distinguish two documents: scheme/host case, a
    leading ``www.``, a default port, a fragment, a trailing slash, and tracking
    parameters. Path case and remaining query parameters are preserved, because
    ``/A`` and ``/a`` genuinely can be different pages.

    Returns ``""`` for input that carries no usable URL, so callers can skip it.
    """
    if not url or not url.strip():
        return ""
    raw = url.strip()
    if "://" not in raw:
        raw = f"https://{raw}"

    parts = urlsplit(raw)
    scheme = parts.scheme.lower()
    netloc = parts.netloc.lower()

    if netloc.startswith("www."):
        netloc = netloc[4:]
    if scheme == "https" and netloc.endswith(":443"):
        netloc = netloc[: -len(":443")]
    elif scheme == "http" and netloc.endswith(":80"):
        netloc = netloc[: -len(":80")]

    path = parts.path.rstrip("/")

    kept = [
        (key, value)
        for key, value in parse_qsl(parts.query, keep_blank_values=True)
        if not _is_tracking_param(key)
    ]
    query = urlencode(sorted(kept))

    return urlunsplit((scheme, netloc, path, query, ""))


def _coerce_entry(entry: Any) -> dict[str, str] | None:
    """Turn one provider entry into ``{"url", "title"}``, or ``None`` if unusable."""
    if isinstance(entry, str):
        return {"url": entry, "title": ""} if entry.strip() else None
    if not isinstance(entry, Mapping):
        return None
    url = ""
    for key in _URL_KEYS:
        candidate = entry.get(key)
        if isinstance(candidate, str) and candidate.strip():
            url = candidate
            break
    if not url:
        return None
    title = ""
    for key in _TITLE_KEYS:
        candidate = entry.get(key)
        if isinstance(candidate, str) and candidate:
            title = candidate
            break
    return {"url": url, "title": title}


def _candidate_lists(payload: Any) -> Iterable[Sequence[Any]]:
    """Yield every plausible result list inside a provider payload."""
    if isinstance(payload, Sequence) and not isinstance(payload, (str, bytes)):
        yield payload
        return
    if not isinstance(payload, Mapping):
        return
    for key in _RESULT_KEYS:
        value = payload.get(key)
        if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
            yield value
            return
        if isinstance(value, Mapping):
            for nested in _NESTED_KEYS:
                inner = value.get(nested)
                if isinstance(inner, Sequence) and not isinstance(inner, (str, bytes)):
                    yield inner
                    return


def extract_results(payload: Any) -> list[dict[str, str]]:
    """Pull an ordered ``[{"url", "title"}]`` list out of any provider payload shape.

    Deliberately shape-agnostic rather than one adapter per vendor: provider response
    schemas drift, and a hard-coded schema fails closed (silently returning nothing) when
    it does. Handles Exa/Tavily/SearXNG (``results``), Firecrawl (``data`` and the nested
    ``data.web``), a bare list, and a list of plain URL strings. Anything unrecognised
    yields ``[]`` — an error payload is simply a provider that contributed nothing.
    """
    out: list[dict[str, str]] = []
    for items in _candidate_lists(payload):
        for entry in items:
            coerced = _coerce_entry(entry)
            if coerced is not None:
                out.append(coerced)
    return out


def reciprocal_rank_fusion(
    rankings: Mapping[str, Sequence[Any]],
    *,
    k: float = DEFAULT_K,
    limit: int | None = None,
) -> list[FusedResult]:
    """Fuse per-provider ranked lists into one ranking.

    ``rankings`` maps a provider name to its ordered results — each entry either a URL
    string or a mapping carrying a url-ish and (optionally) a title-ish key.

    Ranks are assigned over *usable* entries only, so a provider returning a blank URL
    does not push its real results down. A URL repeated within one provider's list counts
    once, at its best rank, so no provider can inflate a document by repeating it.

    Ties break lexicographically by normalised URL, which makes the ordering deterministic
    and independent of the order the providers were consulted.
    """
    if k <= 0:
        raise ValueError("k must be > 0")
    if limit is not None and limit < 0:
        raise ValueError("limit must be >= 0")

    display: dict[str, str] = {}
    titles: dict[str, str] = {}
    sources: dict[str, list[str]] = {}
    ranks: dict[str, dict[str, int]] = {}

    for provider, entries in rankings.items():
        position = 0
        for entry in entries:
            coerced = _coerce_entry(entry)
            if coerced is None:
                continue
            # `_coerce_entry` already rejected blank URLs, so `normalize_url` cannot
            # return "" here; no second blank guard (it would be unreachable).
            key = normalize_url(coerced["url"])
            position += 1
            if key not in display:
                display[key] = coerced["url"]
                titles[key] = coerced["title"]
                sources[key] = []
                ranks[key] = {}
            if not titles[key] and coerced["title"]:
                titles[key] = coerced["title"]
            if provider not in ranks[key]:
                ranks[key][provider] = position
                sources[key].append(provider)

    fused = [
        FusedResult(
            url=key,
            display_url=display[key],
            title=titles[key],
            score=sum(1.0 / (k + rank) for rank in per_provider.values()),
            sources=tuple(sources[key]),
            ranks=MappingProxyType(dict(per_provider)),
        )
        for key, per_provider in ranks.items()
    ]
    fused.sort(key=lambda r: (-r.score, r.url))
    return fused if limit is None else fused[:limit]


def fuse_provider_payloads(
    payloads: Mapping[str, Any],
    *,
    k: float = DEFAULT_K,
    limit: int | None = None,
) -> list[FusedResult]:
    """Fuse raw provider responses end-to-end: shape adaptation, then RRF.

    Convenience wrapper for the common case of holding whatever each provider's client
    returned. A provider whose payload is an error object contributes nothing rather than
    failing the fusion — partial reach beats no reach.
    """
    return reciprocal_rank_fusion(
        {name: extract_results(payload) for name, payload in payloads.items()},
        k=k,
        limit=limit,
    )
