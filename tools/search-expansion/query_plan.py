"""Enterprise-Search query planning: decompose -> translate -> re-dedup — stdlib only.

THE BORROW, AND WHERE IT STOPS
------------------------------
Enterprise search engines run one pattern: take a query, DECOMPOSE it into semantic pieces,
TRANSLATE each piece into the dialect every source speaks, run them, then DEDUP one document
that several sources returned into a single hit. `rank_fusion.py` already owns the last step
end-to-end — `normalize_url` + `reciprocal_rank_fusion` fold one URL from N providers into one
`FusedResult`. This module adds only the two stages that were missing, and REUSES the fusion
rather than reimplementing dedup:

* TRANSLATE (`translate_for_provider` / `plan_sources`) — turn one decomposed `SubQuery` into
  the concrete calls each provider should receive. Only SearXNG has a regional-routing dialect
  (`!<bang>` / `engines=<name>`), so a region-tagged sub-query fans out across the
  measured-WORKING regional engines for that region; every other provider gets one plain query.
* RE-DEDUP (`fuse_decomposed`) — each sub-query is fused across its own providers first
  (`fuse_provider_payloads`, within-sub-query dedup DONE), then this folds those rankings into
  one, treating each sub-query as a "provider" so the SAME RRF collapses a URL that several
  sub-queries surfaced. No new dedup logic exists here.

DECOMPOSE itself is a semantic split — that is LLM work and stays in the calling skill; this
module is the deterministic, unit-testable spine it hands its sub-queries to. Like its sibling
everything here is pure: no I/O, no clock, no global state, no randomness.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence

from rank_fusion import DEFAULT_K, FusedResult, reciprocal_rank_fusion
from searxng_config import REGIONAL_ENGINES, EngineSpec, enabled_specs

__all__ = [
    "DEFAULT_PROVIDERS",
    "SourcePlan",
    "SubQuery",
    "fuse_decomposed",
    "plan_sources",
    "translate_for_provider",
]

#: The search rails a sub-query is fanned out to, in a stable order. SearXNG leads because it
#: is the only one that carries the regional-engine routing the translate stage produces.
DEFAULT_PROVIDERS: tuple[str, ...] = ("searxng", "exa", "tavily", "firecrawl")

#: The one provider that speaks SearXNG's `!<bang>` / `engines=` regional dialect.
_SEARXNG = "searxng"


@dataclass(frozen=True)
class SubQuery:
    """One semantic piece of a decomposed query, with an optional locale hint.

    ``region`` matches an :class:`~searxng_config.EngineSpec` region (e.g. ``"CN"``, ``"RU"``,
    ``"independent"``); ``lang`` is a free-form language hint carried through for the caller and
    not interpreted here.
    """

    text: str
    region: str | None = None
    lang: str | None = None


@dataclass(frozen=True)
class SourcePlan:
    """A single provider call the caller should make for one sub-query.

    ``engine``/``bang`` are populated only for SearXNG regional routing and are ``None`` for a
    plain query. ``query`` never carries the bang inline, so a caller is free to send either
    ``!<bang> <query>`` or ``engines=<engine>`` without unpicking a prefix.
    """

    provider: str
    query: str
    engine: str | None = None
    bang: str | None = None


def _regional_specs(
    region: str | None, engines: tuple[EngineSpec, ...]
) -> tuple[EngineSpec, ...]:
    """Measured-working engines whose region matches, in table order.

    Returns an empty tuple for a missing/blank region or one no working engine covers, so the
    caller falls back to a plain query. Matching is case-insensitive; broken engines are
    dropped by :func:`~searxng_config.enabled_specs` before the region ever compares.
    """
    if region is None or not region.strip():
        return ()
    want = region.strip().casefold()
    return tuple(s for s in enabled_specs(engines) if s.region.casefold() == want)


def translate_for_provider(
    sq: SubQuery,
    provider: str,
    *,
    engines: tuple[EngineSpec, ...] = REGIONAL_ENGINES,
) -> tuple[SourcePlan, ...]:
    """Translate one sub-query into the concrete call(s) for ``provider``.

    For SearXNG a region-tagged sub-query fans out to every measured-WORKING engine for that
    region — one plan each, carrying the engine name and its ``!<bang>``. A sub-query with no
    region, or one whose only engines are broken, yields a single plain query. Every other
    provider yields exactly one plain query: none of them speak the SearXNG bang dialect.
    """
    if provider == _SEARXNG:
        specs = _regional_specs(sq.region, engines)
        if specs:
            return tuple(
                SourcePlan(
                    provider=provider,
                    query=sq.text,
                    engine=spec.name,
                    bang=f"!{spec.shortcut}",
                )
                for spec in specs
            )
    return (SourcePlan(provider=provider, query=sq.text),)


def plan_sources(
    sq: SubQuery,
    *,
    providers: tuple[str, ...] = DEFAULT_PROVIDERS,
    engines: tuple[EngineSpec, ...] = REGIONAL_ENGINES,
) -> tuple[SourcePlan, ...]:
    """Fan one sub-query out across every provider, concatenating each translation."""
    return tuple(
        plan
        for provider in providers
        for plan in translate_for_provider(sq, provider, engines=engines)
    )


def fuse_decomposed(
    subquery_fusions: Iterable[Sequence[FusedResult]],
    *,
    k: float = DEFAULT_K,
    limit: int | None = None,
) -> list[FusedResult]:
    """Fold already-fused per-sub-query rankings into one, re-deduping across sub-queries.

    Each element of ``subquery_fusions`` is one sub-query's result of
    :func:`~rank_fusion.fuse_provider_payloads` — so within-sub-query dedup is already done.
    This treats each sub-query as a "provider" and reuses :func:`~rank_fusion.reciprocal_rank_fusion`
    so the SAME ``normalize_url`` dedup collapses a URL that several sub-queries surfaced into a
    single :class:`~rank_fusion.FusedResult`, whose ``sources`` then name the sub-queries it came
    from. Dedup is reused, never rebuilt.
    """
    return reciprocal_rank_fusion(
        {
            f"subquery-{i}": [
                {"url": r.display_url, "title": r.title, "snippet": r.snippet}
                for r in fusion
            ]
            for i, fusion in enumerate(subquery_fusions)
        },
        k=k,
        limit=limit,
    )
