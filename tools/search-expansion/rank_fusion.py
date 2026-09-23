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

POST-FUSION DIVERSITY (opt-in)
------------------------------
RRF ranks by agreement, and agreement clusters: three engines that all like one site put
six of its pages in the top ten, and a syndicated article arrives under four URLs with the
same title. :func:`diversify` is an MMR-style pass over the fused list — a per-host cap and
a token-Jaccard near-duplicate check, both applied only to the top ``window`` positions —
that RE-ORDERS and never drops: demoted results move below the window in their original
order and keep their RRF ``score``. Stdlib only, no model, 0 MB. It is off by default in
the fusers; callers opt in by naming a knob.

Everything here is a pure function: no I/O, no clock, no global state, no randomness. The
same inputs always produce the same ranking, and provider ordering cannot change it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Iterable, Mapping, Sequence
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

__all__ = [
    "DEFAULT_DIVERSITY_WINDOW",
    "DEFAULT_K",
    "DEFAULT_MAX_PER_HOST",
    "DEFAULT_NEAR_DUP_THRESHOLD",
    "MAX_SNIPPET_CHARS",
    "FusedResult",
    "diversify",
    "extract_results",
    "fuse_provider_payloads",
    "host_key",
    "normalize_url",
    "reciprocal_rank_fusion",
]

#: The value from the original RRF paper. Kept as the default so results are reproducible.
DEFAULT_K = 60.0

#: Upper bound on the snippet carried per result, after whitespace collapse. Exa ``text``
#: and Firecrawl ``markdown`` can be whole pages; a reranker needs a passage, not a body,
#: and a fused list of 50 results must not drag 50 pages of text along with it.
MAX_SNIPPET_CHARS = 500

#: :func:`diversify` defaults. Two per host keeps a site's best two pages while stopping a
#: single site from owning the window; 0.8 token-Jaccard is the same threshold the
#: research-reliability lens (plan doc, Lens 12 item 5) proposes for its "same query" loop
#: guard, reused here for "same text" so the harness grows one notion of near-duplicate,
#: not two; a window of ten is the first page.
DEFAULT_MAX_PER_HOST = 2
DEFAULT_NEAR_DUP_THRESHOLD = 0.8
DEFAULT_DIVERSITY_WINDOW = 10

#: Generic second-level labels under a two-letter country code (``bbc.co.uk``,
#: ``sina.com.cn``, ``kbs.co.kr``): when the TLD is two letters and the label before it is
#: one of these, the registrable host is THREE labels, not two. A short list, not the
#: public-suffix list; the miss cases are documented on :func:`host_key`.
_SECOND_LEVEL_LABELS = frozenset(
    {"ac", "co", "com", "edu", "go", "gov", "ne", "net", "or", "org"}
)
_TOKEN_RE = re.compile(r"[a-z0-9]+")

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
#: Snippet-ish keys in precedence order. The short, query-dependent field of each vendor
#: comes first (SearXNG/Tavily ``content``, Exa ``text``/``summary``, Firecrawl
#: ``description``); ``markdown`` is last because it is a page body, not a passage — the
#: cap in :func:`_clip_snippet` is what makes it safe to fall back to at all.
_SNIPPET_KEYS = ("snippet", "description", "content", "text", "summary", "markdown")


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

    snippet: str = ""
    """Passage from the provider that ranked this document BEST (lowest rank) among
    those that supplied one; ties go to the provider consulted first. Whitespace-
    collapsed and capped at :data:`MAX_SNIPPET_CHARS`; ``""`` if no provider sent one.

    Best-rank rather than first-seen because snippets are query-dependent: the engine
    that ranked a page highest is the one whose extracted passage matched the query
    best, so it is the most useful input to a downstream reranker.
    """


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


def _clip_snippet(text: str) -> str:
    """Collapse runs of whitespace and hard-cap the length.

    The cap is a plain character cut, not a word-boundary search: a reranker's tokenizer
    does not care about one clipped trailing word, and a boundary search would make the
    carried length depend on the text instead of being a fixed bound.
    """
    collapsed = " ".join(text.split())
    return collapsed[:MAX_SNIPPET_CHARS].rstrip()


def _coerce_entry(entry: Any) -> dict[str, str] | None:
    """Turn one provider entry into ``{"url", "title", "snippet"}``, or ``None`` if unusable."""
    if isinstance(entry, str):
        return {"url": entry, "title": "", "snippet": ""} if entry.strip() else None
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
    snippet = ""
    for key in _SNIPPET_KEYS:
        candidate = entry.get(key)
        if isinstance(candidate, str) and candidate.strip():
            snippet = _clip_snippet(candidate)
            break
    return {"url": url, "title": title, "snippet": snippet}


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
    """Pull an ordered ``[{"url", "title", "snippet"}]`` list out of any provider payload.

    Deliberately shape-agnostic rather than one adapter per vendor: provider response
    schemas drift, and a hard-coded schema fails closed (silently returning nothing) when
    it does. Handles Exa/Tavily/SearXNG (``results``), Firecrawl (``data`` and the nested
    ``data.web``), a bare list, and a list of plain URL strings. Anything unrecognised
    yields ``[]`` — an error payload is simply a provider that contributed nothing.

    ``snippet`` is the first non-blank of the vendor keys in :data:`_SNIPPET_KEYS`,
    whitespace-collapsed and capped at :data:`MAX_SNIPPET_CHARS`; ``""`` when absent.
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
    max_per_host: int | None = None,
    near_dup_threshold: float | None = None,
    window: int = DEFAULT_DIVERSITY_WINDOW,
) -> list[FusedResult]:
    """Fuse per-provider ranked lists into one ranking.

    ``rankings`` maps a provider name to its ordered results — each entry either a URL
    string or a mapping carrying a url-ish and (optionally) title-ish / snippet-ish keys.

    Diversity is OFF unless ``max_per_host`` or ``near_dup_threshold`` is given (the
    defaults are exactly the pre-diversify behaviour, so existing callers are unaffected).
    When either is set, :func:`diversify` runs after fusion and BEFORE ``limit``, so a
    diverse result just past the cut can be promoted into it; ``window`` is ignored unless
    one of the two knobs is set.

    Ranks are assigned over *usable* entries only, so a provider returning a blank URL
    does not push its real results down. A URL repeated within one provider's list counts
    once, at its best rank, so no provider can inflate a document by repeating it.

    Ties break lexicographically by normalised URL, which makes the ordering deterministic
    and independent of the order the providers were consulted.

    Each result's ``snippet`` is the one sent by the provider that ranked it best (ties:
    first consulted); a provider that sent none does not compete. It is decided at the
    occurrence that earned the provider's rank — a later repeat within the same list
    cannot rewrite it, just as it cannot improve the rank.
    """
    if k <= 0:
        raise ValueError("k must be > 0")
    if limit is not None and limit < 0:
        raise ValueError("limit must be >= 0")

    display: dict[str, str] = {}
    titles: dict[str, str] = {}
    snippets: dict[str, str] = {}
    snippet_rank: dict[str, int] = {}
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
                snippets[key] = ""
                sources[key] = []
                ranks[key] = {}
            if not titles[key] and coerced["title"]:
                titles[key] = coerced["title"]
            if provider not in ranks[key]:
                ranks[key][provider] = position
                sources[key].append(provider)
                best = snippet_rank.get(key)
                if coerced["snippet"] and (best is None or position < best):
                    snippets[key] = coerced["snippet"]
                    snippet_rank[key] = position

    fused = [
        FusedResult(
            url=key,
            display_url=display[key],
            title=titles[key],
            score=sum(1.0 / (k + rank) for rank in per_provider.values()),
            sources=tuple(sources[key]),
            ranks=MappingProxyType(dict(per_provider)),
            snippet=snippets[key],
        )
        for key, per_provider in ranks.items()
    ]
    fused.sort(key=lambda r: (-r.score, r.url))
    if max_per_host is not None or near_dup_threshold is not None:
        fused = diversify(
            fused,
            max_per_host=max_per_host,
            near_dup_threshold=near_dup_threshold,
            window=window,
        )
    return fused if limit is None else fused[:limit]


def fuse_provider_payloads(
    payloads: Mapping[str, Any],
    *,
    k: float = DEFAULT_K,
    limit: int | None = None,
    max_per_host: int | None = None,
    near_dup_threshold: float | None = None,
    window: int = DEFAULT_DIVERSITY_WINDOW,
) -> list[FusedResult]:
    """Fuse raw provider responses end-to-end: shape adaptation, then RRF.

    Convenience wrapper for the common case of holding whatever each provider's client
    returned. A provider whose payload is an error object contributes nothing rather than
    failing the fusion — partial reach beats no reach. The diversity keywords are passed
    straight through to :func:`reciprocal_rank_fusion` and are off unless named.
    """
    return reciprocal_rank_fusion(
        {name: extract_results(payload) for name, payload in payloads.items()},
        k=k,
        limit=limit,
        max_per_host=max_per_host,
        near_dup_threshold=near_dup_threshold,
        window=window,
    )


def host_key(url: str) -> str:
    """Approximate the registrable host a URL belongs to, for the per-host cap.

    ``www.`` and case are dropped (as :func:`normalize_url` already does — re-applied here
    so hand-built results behave the same). Then: the last two labels, or the last THREE
    when the TLD is a two-letter country code and the second-level label is a generic one
    from :data:`_SECOND_LEVEL_LABELS` (``news.bbc.co.uk`` -> ``bbc.co.uk``,
    ``finance.sina.com.cn`` -> ``sina.com.cn``). IP literals, single-label hosts and a
    missing host are used whole.

    Why fold subdomains at all, rather than use the exact host: the queries this package
    exists for — multilingual — routinely return several language editions of one site
    (``ru.`` / ``zh.`` / ``en.wikipedia.org``), and an exact-host cap would let them take
    six of the top ten. Why not the public-suffix list: it is a 200 KB dependency that
    changes monthly. The documented miss of this approximation is shared-hosting parents
    (``alice.github.io`` and ``bob.github.io`` count as ONE host). That error is in the
    safe direction for a diversity rule: at worst a distinct site is demoted below the
    window (still present, still scored), never a single site allowed to dominate it.
    """
    host = urlsplit(url).hostname or ""
    if host.startswith("www."):
        host = host[4:]
    labels = host.split(".")
    if len(labels) < 3 or host.replace(".", "").isdigit():
        return host
    if len(labels[-1]) == 2 and labels[-2] in _SECOND_LEVEL_LABELS:
        return ".".join(labels[-3:])
    return ".".join(labels[-2:])


def _tokens(text: str) -> frozenset[str]:
    """Lower-cased ``[a-z0-9]+`` runs. ASCII by design (see :func:`diversify`)."""
    return frozenset(_TOKEN_RE.findall(text.lower()))


def _jaccard(a: frozenset[str], b: frozenset[str]) -> float:
    """Set Jaccard similarity. Caller guarantees ``a`` is non-empty, so the union is too."""
    return len(a & b) / len(a | b)


def diversify(
    fused: Sequence[FusedResult],
    *,
    max_per_host: int | None = DEFAULT_MAX_PER_HOST,
    near_dup_threshold: float | None = DEFAULT_NEAR_DUP_THRESHOLD,
    window: int = DEFAULT_DIVERSITY_WINDOW,
) -> list[FusedResult]:
    """Re-order a fused ranking so its top ``window`` is host-diverse and near-dup-free.

    Single greedy pass in ranking order (MMR-style: the ranking is the relevance term, the
    two checks are the redundancy term). A result is KEPT in the window unless

    * its :func:`host_key` already has ``max_per_host`` kept results, or
    * the token-Jaccard of its ``title + " " + snippet`` against ANY kept result is
      strictly greater than ``near_dup_threshold`` (exactly 0.8 is not a duplicate; a
      result with no title and no snippet has no tokens and is never one).

    Anything not kept — demoted for either reason, or arriving after the window is full —
    follows the window in its original order. This is a RE-ORDERING ONLY: nothing is
    dropped, no object is copied or altered, and every result keeps its RRF ``score``, so a
    non-monotonic score column downstream is the visible trace of a demotion. Only kept
    results define the window: a demoted result neither spends its host's quota nor
    becomes a comparison target.

    ``None`` disables either check; ``window=0`` is the identity. Tokens are ASCII
    ``[a-z0-9]+`` runs by design — pure CJK/Cyrillic text therefore has no tokens and is
    never demoted as a duplicate (it is still host-capped); widening the tokenizer is a
    deliberate follow-up, not an accident to fix in passing.
    """
    if max_per_host is not None and max_per_host < 1:
        raise ValueError("max_per_host must be >= 1 (None disables the host cap)")
    if near_dup_threshold is not None and not 0.0 <= near_dup_threshold <= 1.0:
        raise ValueError(
            "near_dup_threshold must be within [0, 1] (None disables near-dup demotion)"
        )
    if window < 0:
        raise ValueError("window must be >= 0")

    kept: list[FusedResult] = []
    kept_tokens: list[frozenset[str]] = []
    per_host: dict[str, int] = {}
    tail: list[FusedResult] = []

    for result in fused:
        if len(kept) >= window:
            tail.append(result)
            continue
        host = host_key(result.url)
        if max_per_host is not None and per_host.get(host, 0) >= max_per_host:
            tail.append(result)
            continue
        tokens = _tokens(f"{result.title} {result.snippet}")
        if (
            near_dup_threshold is not None
            and tokens
            and any(_jaccard(tokens, seen) > near_dup_threshold for seen in kept_tokens)
        ):
            tail.append(result)
            continue
        kept.append(result)
        kept_tokens.append(tokens)
        per_host[host] = per_host.get(host, 0) + 1
    return kept + tail
