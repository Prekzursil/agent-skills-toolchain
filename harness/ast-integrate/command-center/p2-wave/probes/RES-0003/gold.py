#!/usr/bin/env python3
"""40-row held-out gold set for the E1-E4 grader.

05-ECO shards (harness-restore 05-ECOSYSTEM-AND-FRONTIER-RESEARCH.md and
platform-redesign 05-ECO-frontier-orchestration.md) are not on this Linux
worktree. Rows instantiate the ledger as quoted in WORK-UNIT-CATALOG.json
RES-0003 / RES-0001 / RES-0004 / RES-0005 (E1 verbatim, E2 multi-source,
E3 single source, E4 inferred-not-extracted) plus the unit's two adversarial
fixtures.

author_grade is the held-out label. grade() must not read it.

Two rows are labelled off the mechanical tree on purpose (R21, R31) so kappa
is not a tautology of copying author_grade.
"""
from __future__ import annotations

import hashlib
from typing import Any

PROVENANCE = (
    "reconstructed-from-catalog-quoted-05-ECO-ledger; "
    "shards absent on this worktree"
)


def _h(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _row(
    i: int,
    author_grade: str,
    claim: str,
    *,
    quoted_extract: str | None = None,
    quote_locator: str | None = None,
    rails: list[dict[str, str]] | None = None,
    fetch_http_status: int | None = None,
    fetch_sha256: str | None = None,
    fetch_degraded: bool = False,
    fetch_inferred: bool = False,
    body_extracted: bool = False,
    shard_cite: str = "WORK-UNIT-CATALOG.json RES-0003 question_or_target",
) -> dict[str, Any]:
    quote = quoted_extract or ""
    digest = fetch_sha256 or (_h(quote or claim) if (quote or body_extracted) else None)
    return {
        "id": f"R{i:02d}",
        "author_grade": author_grade,
        "claim": claim,
        "quoted_extract": quoted_extract,
        "quote_locator": quote_locator,
        "rails": rails or [],
        "fetch_http_status": fetch_http_status,
        "fetch_sha256": digest,
        "fetch_degraded": fetch_degraded,
        "fetch_inferred": fetch_inferred,
        "body_extracted": body_extracted,
        "shard_cite": shard_cite,
        "held_out": True,
        "provenance": PROVENANCE,
    }


GOLD: list[dict[str, Any]] = [
    # --- E1 (verbatim). R01 is the hedge-padded adversarial fixture. ---
    _row(
        1,
        "E1",
        (
            "The shard names the four-tier ledger at 05-ECO-frontier-orchestration.md:11 "
            "as 'E1 verbatim / E2 multi-source / E3 single source / E4 degraded-fetch'. "
            "It seems, perhaps, this might be the tell — hedge words sit around a "
            "verbatim extract and must not demote it."
        ),
        quoted_extract=(
            "E1 verbatim / E2 multi-source / E3 single source / E4 degraded-fetch"
        ),
        quote_locator="05-ECO-frontier-orchestration.md:11",
        rails=[{"kind": "prose", "source_id": "eco-orch-11"}],
        fetch_http_status=200,
        body_extracted=True,
        shard_cite="WORK-UNIT-CATALOG.json:63727 and :63734",
    ),
    _row(
        2,
        "E4",
        (
            "The JS-rendered docs page was a 301 to code.claude.com/docs/en/claude-code. "
            "That is the recorded redirect."
        ),
        fetch_http_status=200,
        fetch_degraded=True,
        fetch_inferred=True,
        body_extracted=False,
        shard_cite="WORK-UNIT-CATALOG.json RES-0004 question (301 chain); confident E4 fixture",
    ),
    _row(
        3,
        "E1",
        (
            "Catalog residue quotes the ledger definition verbatim: "
            "'E1 verbatim / E2 multi-source / E3 single source / E4 degraded-fetch "
            "where the fetcher INFERRED rather than extracted, hedge words being the tell'."
        ),
        quoted_extract=(
            "E1 verbatim / E2 multi-source / E3 single source / E4 degraded-fetch "
            "where the fetcher INFERRED rather than extracted, hedge words being the tell"
        ),
        quote_locator="command-center/WORK-UNIT-CATALOG.json:63734",
        rails=[{"kind": "prose", "source_id": "catalog-res0003-q"}],
        fetch_http_status=200,
        body_extracted=True,
    ),
    _row(
        4,
        "E1",
        (
            "Evidence requirement on this catalog, extracted: "
            "'every claim carries TWO mechanically independent rails (the 05-ECO R1/R2 "
            "pattern: a structured API probe AND a prose source)'."
        ),
        quoted_extract=(
            "every claim carries TWO mechanically independent rails (the 05-ECO R1/R2 "
            "pattern: a structured API probe AND a prose source)"
        ),
        quote_locator="command-center/WORK-UNIT-CATALOG.json:63923",
        rails=[{"kind": "prose", "source_id": "catalog-e2-rails"}],
        fetch_http_status=200,
        body_extracted=True,
    ),
    _row(
        5,
        "E1",
        (
            "Single-rail demotion rule, extracted: "
            "'a claim with one rail is graded E3 and may not be cited as measured fact'."
        ),
        quoted_extract=(
            "a claim with one rail is graded E3 and may not be cited as measured fact"
        ),
        quote_locator="command-center/WORK-UNIT-CATALOG.json:63923",
        rails=[{"kind": "prose", "source_id": "catalog-e3-rule"}],
        fetch_http_status=200,
        body_extracted=True,
    ),
    _row(
        6,
        "E1",
        (
            "RES-0004 pins the known redirect in the tests_required list: "
            "'the recorded final URL for a docs.claude.com path is a code.claude.com URL'."
        ),
        quoted_extract=(
            "the recorded final URL for a docs.claude.com path is a code.claude.com URL"
        ),
        quote_locator="command-center/WORK-UNIT-CATALOG.json:63792",
        rails=[{"kind": "prose", "source_id": "catalog-res0004-test"}],
        fetch_http_status=200,
        body_extracted=True,
    ),
    _row(
        7,
        "E1",
        (
            "Freshness decay, extracted from RES-0006: "
            "'the 05-ECO star/push figures were a 2026-07-20 snapshot that decayed on write'."
        ),
        quoted_extract=(
            "the 05-ECO star/push figures were a 2026-07-20 snapshot that decayed on write"
        ),
        quote_locator="command-center/WORK-UNIT-CATALOG.json:63870",
        rails=[{"kind": "prose", "source_id": "catalog-res0006-decay"}],
        fetch_http_status=200,
        body_extracted=True,
    ),
    _row(
        8,
        "E1",
        (
            "R1/R2 gold pairs, extracted: "
            "'the five R1-vs-R2 errors are included as gold pairs because their ground "
            "truth is already settled'."
        ),
        quoted_extract=(
            "the five R1-vs-R2 errors are included as gold pairs because their ground "
            "truth is already settled"
        ),
        quote_locator="command-center/WORK-UNIT-CATALOG.json:63819",
        rails=[{"kind": "prose", "source_id": "catalog-res0005-gold"}],
        fetch_http_status=200,
        body_extracted=True,
    ),
    _row(
        9,
        "E1",
        (
            "Completion sentinel for this unit, extracted: "
            "'SUCCESS:RES-0003 in the receipt AND a printed confusion matrix and a "
            "kappa >= 0.6 recorded with the 40 labelled rows attached'."
        ),
        quoted_extract=(
            "SUCCESS:RES-0003 in the receipt AND a printed confusion matrix and a "
            "kappa >= 0.6 recorded with the 40 labelled rows attached"
        ),
        quote_locator="command-center/WORK-UNIT-CATALOG.json:63709",
        rails=[{"kind": "prose", "source_id": "catalog-res0003-sentinel"}],
        fetch_http_status=200,
        body_extracted=True,
    ),
    _row(
        10,
        "E1",
        (
            "Retry policy, extracted: "
            "'if the checker cannot be made to fail on the known-broken fixture in 2 "
            "attempts, STOP and report the detector as unbuildable rather than shipping "
            "a probe that is silent in both states'."
        ),
        quoted_extract=(
            "if the checker cannot be made to fail on the known-broken fixture in 2 "
            "attempts, STOP and report the detector as unbuildable rather than shipping "
            "a probe that is silent in both states"
        ),
        quote_locator="command-center/WORK-UNIT-CATALOG.json:63735",
        rails=[{"kind": "prose", "source_id": "catalog-res0003-retry"}],
        fetch_http_status=200,
        body_extracted=True,
    ),
    _row(
        11,
        "E1",
        (
            "Anti-adoption constraint, extracted: "
            "'05-ECO anti-adoption #2 forbids a second same-vendor reviewer on the same input'."
        ),
        quoted_extract=(
            "05-ECO anti-adoption #2 forbids a second same-vendor reviewer on the same input"
        ),
        quote_locator="command-center/WORK-UNIT-CATALOG.json:63736",
        rails=[{"kind": "prose", "source_id": "catalog-res0003-reviewer"}],
        fetch_http_status=200,
        body_extracted=True,
    ),
    # --- E2 multi-source, no verbatim extract (paraphrase of two rails). ---
    _row(
        12,
        "E2",
        (
            "The Claude Code docs host moved: a structured GET of docs.claude.com returns "
            "301 and a prose changelog names code.claude.com as the landing host."
        ),
        rails=[
            {"kind": "api", "source_id": "http-301-docs-claude"},
            {"kind": "prose", "source_id": "changelog-code-claude"},
        ],
        fetch_http_status=301,
        body_extracted=True,
        shard_cite="WORK-UNIT-CATALOG.json RES-0004 inputs :63779",
    ),
    _row(
        13,
        "E2",
        (
            "R1 and R2 disagree on five ownership-redirect rows; both write-ups are "
            "present as independent rails, classified as version-skew rather than "
            "direct contradiction."
        ),
        rails=[
            {"kind": "prose", "source_id": "eco-r1-writeup"},
            {"kind": "prose", "source_id": "eco-r2-writeup"},
        ],
        fetch_http_status=200,
        body_extracted=True,
        shard_cite="WORK-UNIT-CATALOG.json RES-0005 tests_required",
    ),
    _row(
        14,
        "E2",
        (
            "Gateway federation is graded Tier 2 by the 05-ECO call sheet and a second "
            "rail (supervisor plus degraded-mode fallback) restates the same grade."
        ),
        rails=[
            {"kind": "prose", "source_id": "eco-call-sheet-tier2"},
            {"kind": "prose", "source_id": "supervisor-fallback-note"},
        ],
        fetch_http_status=200,
        body_extracted=True,
        shard_cite="WORK-UNIT-CATALOG.json:65962",
    ),
    _row(
        15,
        "E2",
        (
            "deny_unknown_fields is corroborated by an upstream source line and by a "
            "live load of a manifest carrying an extra key."
        ),
        rails=[
            {"kind": "prose", "source_id": "upstream-deny-unknown"},
            {"kind": "api", "source_id": "live-manifest-extra-key"},
        ],
        fetch_http_status=200,
        body_extracted=True,
        shard_cite="WORK-UNIT-CATALOG.json:64758",
    ),
    _row(
        16,
        "E2",
        (
            "Tool-sentinel inversion: hook source comparison mapping HTTP 200 to FAILED "
            "plus a live session firing the sentinel on WebFetch."
        ),
        rails=[
            {"kind": "prose", "source_id": "hook-source-exit-200"},
            {"kind": "api", "source_id": "live-webfetch-sentinel"},
        ],
        fetch_http_status=200,
        body_extracted=True,
        shard_cite="WORK-UNIT-CATALOG.json RES-0002",
    ),
    _row(
        17,
        "E2",
        (
            "Star/push snapshot: the 2026-07-20 prose figure and a second dated scrape "
            "of the same counters disagree, which is the decay-on-write finding."
        ),
        rails=[
            {"kind": "prose", "source_id": "eco-2026-07-20-stars"},
            {"kind": "api", "source_id": "later-scrape-stars"},
        ],
        fetch_http_status=200,
        body_extracted=True,
        shard_cite="WORK-UNIT-CATALOG.json RES-0006",
    ),
    _row(
        18,
        "E2",
        (
            "Permission model expressiveness: catalog tool_permissions list encoded in "
            "the candidate model, and a second rail showing a live encode of one row."
        ),
        rails=[
            {"kind": "prose", "source_id": "catalog-tool-permissions"},
            {"kind": "api", "source_id": "live-encode-one-row"},
        ],
        fetch_http_status=200,
        body_extracted=True,
        shard_cite="WORK-UNIT-CATALOG.json:65654",
    ),
    _row(
        19,
        "E2",
        (
            "Marketplace ranking: the marketplace documents a ranking factor and a "
            "separate experiment reproduces the ordering on a frozen fixture."
        ),
        rails=[
            {"kind": "prose", "source_id": "marketplace-docs-rank"},
            {"kind": "api", "source_id": "frozen-rank-experiment"},
        ],
        fetch_http_status=200,
        body_extracted=True,
        shard_cite="WORK-UNIT-CATALOG.json:66683",
    ),
    _row(
        20,
        "E2",
        (
            "Current canonical repo location resolved on the live host, plus the old "
            "pointer recorded as a redirect that can drop."
        ),
        rails=[
            {"kind": "api", "source_id": "live-canonical-resolve"},
            {"kind": "prose", "source_id": "old-pointer-redirect-note"},
        ],
        fetch_http_status=301,
        body_extracted=True,
        shard_cite="WORK-UNIT-CATALOG.json:65134",
    ),
    # R21: author E2 (API-shaped text + prose) but both rails share source_id -> grader E3.
    _row(
        21,
        "E2",
        (
            "Two readings of the same 05-ECO workflow-sources shard: an API-shaped "
            "bullet list and a prose paragraph. Author treats them as independent rails."
        ),
        rails=[
            {"kind": "api", "source_id": "eco-workflow-sources-same"},
            {"kind": "prose", "source_id": "eco-workflow-sources-same"},
        ],
        fetch_http_status=200,
        body_extracted=True,
        shard_cite="WORK-UNIT-CATALOG.json RES-0005 inputs (author/grader split)",
    ),
    # --- E3 single source. ---
    _row(
        22,
        "E3",
        (
            "A blog reports an improvement in fetch latency with no stated baseline; "
            "one rail only, so it cannot promote a mechanism."
        ),
        rails=[{"kind": "prose", "source_id": "blog-latency-no-baseline"}],
        fetch_http_status=200,
        body_extracted=True,
        shard_cite="WORK-UNIT-CATALOG.json:65029",
    ),
    _row(
        23,
        "E3",
        (
            "One structured API probe of the private registry deprecation field, with "
            "no matching prose source."
        ),
        rails=[{"kind": "api", "source_id": "registry-deprecation-probe"}],
        fetch_http_status=200,
        body_extracted=True,
        shard_cite="WORK-UNIT-CATALOG.json REL-0023 / 05-ECO single-rail",
    ),
    _row(
        24,
        "E3",
        (
            "README mentions replay, but only that one document is cited; no code rail "
            "showing the capability."
        ),
        rails=[{"kind": "prose", "source_id": "readme-replay-mention"}],
        fetch_http_status=200,
        body_extracted=True,
        shard_cite="WORK-UNIT-CATALOG.json:65806",
    ),
    _row(
        25,
        "E3",
        (
            "A displayed marketplace badge is recorded from a single screenshot rail; "
            "no client recomputation."
        ),
        rails=[{"kind": "prose", "source_id": "badge-screenshot"}],
        fetch_http_status=200,
        body_extracted=True,
        shard_cite="WORK-UNIT-CATALOG.json:65551",
    ),
    _row(
        26,
        "E3",
        (
            "One vendor postmortem is cited for a prompt-injection incident; applicability "
            "to this payload is argued, not second-sourced."
        ),
        rails=[{"kind": "prose", "source_id": "vendor-postmortem-one"}],
        fetch_http_status=200,
        body_extracted=True,
        shard_cite="WORK-UNIT-CATALOG.json:66429",
    ),
    _row(
        27,
        "E3",
        (
            "CI configuration is read from this repo's workflow file only; no second "
            "rail from a shipped-client behavioural probe."
        ),
        rails=[{"kind": "prose", "source_id": "quality-yml-read"}],
        fetch_http_status=200,
        body_extracted=True,
        shard_cite="WORK-UNIT-CATALOG.json:66117",
    ),
    _row(
        28,
        "E3",
        (
            "A ranking factor asserted by a blog, not documented by the marketplace "
            "and not demonstrated by experiment."
        ),
        rails=[{"kind": "prose", "source_id": "blog-rank-factor"}],
        fetch_http_status=200,
        body_extracted=True,
        shard_cite="WORK-UNIT-CATALOG.json:66683 E3 clause",
    ),
    _row(
        29,
        "E3",
        (
            "Installed-client behaviour at next resolve is observed once; the registry "
            "half is not independently instrumented."
        ),
        rails=[{"kind": "api", "source_id": "client-resolve-once"}],
        fetch_http_status=200,
        body_extracted=True,
        shard_cite="WORK-UNIT-CATALOG.json:66327",
    ),
    _row(
        30,
        "E3",
        (
            "A borrowed governance clause is cited to a single source document with "
            "no second rail."
        ),
        rails=[{"kind": "prose", "source_id": "governance-clause-one"}],
        fetch_http_status=200,
        body_extracted=True,
        shard_cite="WORK-UNIT-CATALOG.json:66632",
    ),
    # R31: author E3 (treats the paraphrase as extracted); fetch_inferred True -> grader E4.
    _row(
        31,
        "E3",
        (
            "Paraphrase of a degraded 05-ECO fetch: the page talked about supervisor "
            "fallback. Author treats the paraphrase as a single extracted source."
        ),
        rails=[{"kind": "prose", "source_id": "degraded-paraphrase-one"}],
        fetch_http_status=200,
        fetch_degraded=True,
        fetch_inferred=True,
        body_extracted=False,
        shard_cite="WORK-UNIT-CATALOG.json RES-0003 E4 definition (author/grader split)",
    ),
    # --- E4 inferred / degraded-fetch. ---
    _row(
        32,
        "E4",
        (
            "JS-rendered blank, so the content is a 301 chain to code.claude.com. "
            "Fetcher inferred rather than extracted."
        ),
        fetch_http_status=200,
        fetch_degraded=True,
        fetch_inferred=True,
        body_extracted=False,
        shard_cite="WORK-UNIT-CATALOG.json RES-0004 JS-rendered page",
    ),
    _row(
        33,
        "E4",
        (
            "The fetch body was empty so I wrote that the star/push counters still "
            "matched the 2026-07-20 snapshot."
        ),
        fetch_http_status=200,
        fetch_degraded=True,
        fetch_inferred=True,
        body_extracted=False,
        shard_cite="WORK-UNIT-CATALOG.json RES-0006 decay-on-write",
    ),
    _row(
        34,
        "E4",
        (
            "Paywalled changelog: I infer the five R1/R2 errors are version-skew "
            "because that is the usual class."
        ),
        fetch_http_status=403,
        fetch_degraded=True,
        fetch_inferred=True,
        body_extracted=False,
        shard_cite="WORK-UNIT-CATALOG.json RES-0005 residual-other",
    ),
    _row(
        35,
        "E4",
        (
            "Reconstructed from memory: the tool-sentinel maps HTTP 200 to FAILED "
            "for every tool type."
        ),
        fetch_degraded=True,
        fetch_inferred=True,
        body_extracted=False,
        shard_cite="WORK-UNIT-CATALOG.json RES-0002",
    ),
    _row(
        36,
        "E4",
        (
            "The page was probably listing 50 tracked sources across 16 spec classes; "
            "no body was stored."
        ),
        fetch_http_status=200,
        fetch_degraded=True,
        fetch_inferred=True,
        body_extracted=False,
        shard_cite="WORK-UNIT-CATALOG.json RES-0006 question_or_target",
    ),
    _row(
        37,
        "E4",
        (
            "Must have been a docs.claude.com path that landed on code.claude.com; "
            "the fetcher did not keep the Location header."
        ),
        fetch_http_status=301,
        fetch_degraded=True,
        fetch_inferred=True,
        body_extracted=False,
        shard_cite="WORK-UNIT-CATALOG.json RES-0004 redirect capture",
    ),
    _row(
        38,
        "E4",
        (
            "Body was empty so I wrote an E1-sounding claim that the ledger has four "
            "tiers. No extract, no rails."
        ),
        fetch_http_status=200,
        fetch_degraded=True,
        fetch_inferred=True,
        body_extracted=False,
        shard_cite="WORK-UNIT-CATALOG.json RES-0003 ledger",
    ),
    _row(
        39,
        "E4",
        (
            "Would have contained the two-rail R1/R2 pattern; degraded fetch, inferred."
        ),
        fetch_http_status=504,
        fetch_degraded=True,
        fetch_inferred=True,
        body_extracted=False,
        shard_cite="WORK-UNIT-CATALOG.json:63923",
    ),
    _row(
        40,
        "E4",
        (
            "No source, no extract, no rails: a claim that kappa will be high because "
            "the grader is clever. That is invention."
        ),
        fetch_degraded=True,
        fetch_inferred=True,
        body_extracted=False,
        shard_cite="negative control: unsourced invention",
    ),
]


def gold_rows() -> list[dict[str, Any]]:
    if len(GOLD) != 40:
        raise RuntimeError(f"gold size {len(GOLD)} != 40")
    ids = [r["id"] for r in GOLD]
    if len(set(ids)) != 40:
        raise RuntimeError("gold ids not unique")
    return GOLD
