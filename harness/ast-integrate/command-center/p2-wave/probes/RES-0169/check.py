#!/usr/bin/env python3
"""Recompute the matrix from captures and reject overclaim mutants."""
from __future__ import annotations

import json
from typing import Any

import jsonschema

import common as C

NOT_DELIVERING = frozenset({"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"})
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0169/probe1_both_states.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0169/probe2_lineage_and_overclaim.py"
)
NEEDLES = {
    "openalex-unfiltered": "openalex.org/W",
    "openalex-language": "openalex.org/W",
    "openalex-recency": "openalex.org/W",
    "openalex-region": "openalex.org/W",
    "openalex-domain": "openalex.org/W",
    "wikipedia-en": "pageid",
    "wikipedia-de": "pageid",
    "wikipedia-srdomain": "pageid",
    "wikipedia-region": "pageid",
    "wikipedia-srsince": "pageid",
    "crossref-unfiltered": "total-results",
    "crossref-recency": "total-results",
    "crossref-domain": "total-results",
    "crossref-language": "filter",
    "crossref-region": "region",
    "arxiv-unfiltered": "arxiv.org/abs",
    "arxiv-recency": "arxiv.org/abs",
    "arxiv-language": "arxiv.org/abs",
    "arxiv-region": "arxiv.org/abs",
    "arxiv-domain": "arxiv.org/abs",
    "pubmed-unfiltered": "esearchresult",
    "pubmed-language": "esearchresult",
    "pubmed-recency": "esearchresult",
    "pubmed-region": "esearchresult",
    "pubmed-domain": "esearchresult",
    "europepmc-unfiltered": "hitCount",
    "europepmc-language": "hitCount",
    "europepmc-recency": "hitCount",
    "europepmc-region": "hitCount",
    "europepmc-domain": "hitCount",
    "github-unfiltered": "total_count",
    "github-language": "total_count",
    "github-recency": "total_count",
    "github-domain": "total_count",
    "github-region": "total_count",
    "hn-unfiltered": "objectID",
    "hn-recency": "objectID",
    "hn-language": "language",
    "hn-region": "country",
    "hn-domain": "domain",
    "auth-tavily": "invalid API key",
    "auth-exa": "Payment required",
    "auth-brave": "x-subscription-token",
    "auth-searxng-localhost": "Connection refused",
    "auth-ddg-html-challenge": "anomaly",
    "docs-openalex-filters": "language",
    "docs-mediawiki-search-paraminfo": "query+search",
    "docs-crossref-rest-api": "from-pub-date",
    "docs-arxiv-api-manual": "search_query",
    "docs-pubmed-eutils": "esearch.fcgi",
    "docs-europepmc-restful": "Europe PMC",
    "docs-github-repo-search": "language:javascript",
    "docs-hn-algolia-api": "powered by Algolia",
    "docs-tavily-search": "include_domains",
    "docs-exa-search": "includeDomains",
    "docs-brave-web-search": "Brave Search",
    "docs-searxng-search-api": "time_range",
    "docs-ddg-lite-challenge": "anomaly",
}


def needle_for(capture_id: str, text: str) -> str:
    n = NEEDLES.get(capture_id)
    if n and n in text:
        return n
    for cand in (
        "openalex.org/W",
        "esearchresult",
        "total-results",
        "arxiv.org/abs",
        "hitCount",
        "total_count",
        "objectID",
        "pageid",
        "include_domains",
        "includeDomains",
        "query+search",
        "from-pub-date",
        "search_query",
        "numericFilters",
        "time_range",
        "Brave Search",
        "invalid API key",
        "Payment required",
        "x-subscription-token",
        "Connection refused",
        "anomaly",
        "filter",
        "language",
        "DOCTYPE",
    ):
        if cand in text:
            return cand
    raise AssertionError(f"no needle for {capture_id}")


def band(exp: dict) -> str:
    v = exp["verdict"]
    jac = exp.get("id_jaccard")
    if v == "NATIVE":
        if jac is not None and jac <= 0.1:
            return "Almost certain"
        return "Highly likely"
    if v == "IGNORED":
        if jac == 1.0:
            return "Almost certain"
        return "Highly likely"
    if v in {"REJECTED", "UNREACHABLE"}:
        return "Almost certain"
    return "Likely"


def well_formed(doc: dict[str, Any], index: dict | None = None) -> tuple[bool, str]:
    idx = index if index is not None else C.load_index()
    text = json.dumps(doc, ensure_ascii=True)
    if str(doc.get("unit_id")) != C.UNIT_ID:
        return False, "unit_id"
    if C.SENTINEL not in text:
        return False, "sentinel-absent"
    st = str(doc.get("state") or "").upper()
    if st in NOT_DELIVERING:
        return False, f"self-declared:{st}"
    schema = json.loads((C.REPO / C.SCHEMA_REL).read_text(encoding="utf-8"))
    try:
        jsonschema.validate(doc, schema)
    except jsonschema.ValidationError as exc:
        return False, f"schema:{exc.message}"

    cells = doc.get("cells") or []
    expected_n = len(C.BACKENDS) * len(C.FILTERS)
    if len(cells) != expected_n:
        return False, f"cell-count:{len(cells)}!={expected_n}"

    seen: set[tuple[str, str]] = set()
    verdicts: dict[str, int] = {}
    for cell in cells:
        be, filt = cell.get("backend"), cell.get("filter")
        if (be, filt) in seen:
            return False, f"duplicate-cell:{be}/{filt}"
        seen.add((be, filt))
        try:
            exp = C.classify_cell(idx, be, filt)
        except Exception as exc:
            return False, f"classify:{be}/{filt}:{exc}"
        if cell.get("verdict") != exp["verdict"]:
            return False, (
                f"verdict-drift:{be}/{filt} claimed={cell.get('verdict')} "
                f"live={exp['verdict']}"
            )
        diff = cell.get("differential") or {}
        if bool(diff.get("strongly_changed")) != bool(exp["strongly_changed"]):
            return False, f"changed-drift:{be}/{filt}"
        if cell.get("verdict") == "NATIVE" and not exp["strongly_changed"]:
            return False, f"native-without-change:{be}/{filt}"
        if "positive_control_changed" in diff and bool(
            diff.get("positive_control_changed")
        ) != bool(exp["positive_control_changed"]):
            return False, f"pc-drift:{be}/{filt}"
        if cell.get("verdict") == "IGNORED":
            if not exp["positive_control_changed"]:
                return False, f"ignored-without-pc:{be}/{filt}"
            # The artifact must itself record the changing positive control;
            # an IGNORED verdict whose own differential says the control did
            # not move is an overclaim regardless of what live recompute says.
            if diff.get("positive_control_changed") is not True:
                return False, f"artifact-ignored-without-pc:{be}/{filt}"
            if exp["strongly_changed"]:
                return False, f"ignored-but-changed:{be}/{filt}"
        if cell.get("evidence_basis") == "docs-only" and cell.get("verdict") == "NATIVE":
            return False, f"docs-only-native:{be}/{filt}"
        sigs = cell.get("signals") or []
        if len(sigs) < 2:
            return False, f"single-signal:{be}/{filt}"
        caps = {s.get("capture_id") for s in sigs}
        urls = {s.get("url") for s in sigs}
        if len(caps) < 2 and len(urls) < 2:
            return False, f"dependent-signals:{be}/{filt}"
        for s in sigs:
            cid = s.get("capture_id")
            snip = s.get("snippet")
            sha = s.get("sha256")
            if not cid or not snip or not sha:
                return False, f"incomplete-signal:{be}/{filt}"
            try:
                cap = C.assert_snippet(idx, cid, snip)
            except Exception as exc:
                return False, f"snippet:{be}/{filt}:{exc}"
            if cap["sha256"] != sha:
                return False, f"sha-drift:{cid}"
        verdicts[cell.get("verdict")] = verdicts.get(cell.get("verdict"), 0) + 1

    for need in ("NATIVE", "IGNORED", "REJECTED", "UNREACHABLE"):
        if verdicts.get(need, 0) < 1:
            return False, f"missing-verdict:{need}"

    wiki_dom = next(
        c for c in cells if c.get("backend") == "wikipedia" and c.get("filter") == "domain"
    )
    emu = wiki_dom.get("client_emulation") or {}
    live_emu = C.emulate_wikipedia_domain(idx)
    if live_emu["changed"] is not True:
        return False, "emulation-did-not-change"
    if emu.get("changed") is not True:
        return False, "artifact-emulation-not-changed"
    if wiki_dom.get("verdict") != "IGNORED":
        return False, "wikipedia-domain-not-ignored"

    wiki_lang = next(
        c for c in cells if c.get("backend") == "wikipedia" and c.get("filter") == "language"
    )
    if wiki_lang.get("verdict") != "NATIVE":
        return False, "wikipedia-language-not-native"

    claims = doc.get("claims") or []
    if len(claims) < 6:
        return False, "claims-short"
    inferred_ok = False
    for row in claims:
        if row.get("verdict") not in {"CONFIRMED", "REFUTED", "PARTIAL", "INFERRED"}:
            return False, f"claim-verdict:{row.get('id')}"
        if row.get("verdict") == "INFERRED":
            inferred_ok = True
        sigs = row.get("signals") or []
        if len(sigs) < 2:
            return False, f"claim-single-signal:{row.get('id')}"
        for s in sigs:
            try:
                cap = C.assert_snippet(idx, s["capture_id"], s["snippet"])
            except Exception as exc:
                return False, f"claim-snippet:{row.get('id')}:{exc}"
            if cap["sha256"] != s.get("sha256"):
                return False, f"claim-sha:{s.get('capture_id')}"
    if not inferred_ok:
        return False, "no-inferred-docs-claim"

    kinds = {t.get("kind") for t in (doc.get("tests") or [])}
    if "both-states-control" not in kinds:
        return False, "missing-both-states-test"

    revs = doc.get("reviewers") or []
    mandates = {r.get("mandate") for r in revs}
    if mandates != {"measurement", "overclaim"}:
        return False, f"reviewer-mandates:{mandates}"
    return True, "ok"
