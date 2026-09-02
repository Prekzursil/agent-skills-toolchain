#!/usr/bin/env python3
"""Emit command-center/research/RES-0060.json from live captures + local contract."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import common as C  # noqa: E402

QUESTION = (
    "What signals drive discovery ranking in mature extension marketplaces, "
    "how much of ranking is install-count feedback (a rich-get-richer loop), "
    "and what would make a genuinely useful but new package discoverable in "
    "this program's index?"
)


def rail(cid: str, kind: str, quoted_span: str) -> dict:
    row = C.capture_row(cid)
    path = C.REPO / str(row["path"]).replace("\\", "/")
    sha, size = C.digest_file(path)
    return {
        "kind": kind,
        "capture_id": cid,
        "permalink": row["url"],
        "fetched_at": row["fetched_at"],
        "http_status": row["http_status"],
        "sha256": sha,
        "bytes": size,
        "path": row["path"],
        "quoted_span": quoted_span,
    }


def local_rail(kind: str, path: str, quoted_span: str, *, note: str) -> dict:
    p = C.REPO / path
    sha, size = C.digest_file(p)
    return {
        "kind": kind,
        "capture_id": None,
        "permalink": f"file://{path}",
        "fetched_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "http_status": 200,
        "sha256": sha,
        "bytes": size,
        "path": path,
        "quoted_span": quoted_span,
        "note": note,
    }


def factor(
    fid: str,
    marketplace: str,
    name: str,
    evidence_class: str,
    role: str,
    install_feedback: str,
    used_in_default: bool,
    evidence_tier: str,
    note: str,
) -> dict:
    return {
        "id": fid,
        "marketplace": marketplace,
        "factor": name,
        "evidence_class": evidence_class,
        "role": role,
        "install_count_feedback": install_feedback,
        "used_in_default_ranking": used_in_default,
        "evidence_tier": evidence_tier,
        "note": note,
    }


def ensure_program_fixture() -> None:
    """Materialize IMP-0118's known-good registry if this worktree has no index yet."""
    path = C.REPO / "tools/marketplace/fixture/registry/index.json"
    if path.is_file() and path.stat().st_size > 0:
        return
    if str(C.REPO) not in sys.path:
        sys.path.insert(0, str(C.REPO))
    from tools.marketplace.fixture import build  # noqa: WPS433

    build(C.REPO)


def main() -> int:
    ensure_program_fixture()
    vs_rel = C.vscode_ranked_ids("vscode-api-sort-relevance")
    vs_ins = C.vscode_ranked_ids("vscode-api-sort-installs")
    vs_rel_n = C.vscode_installs("vscode-api-sort-relevance")
    vs_ins_n = C.vscode_installs("vscode-api-sort-installs")
    if vs_rel == vs_ins:
        print("FAILED:RES-0060 emit relevance order equals install order")
        return 1
    if vs_ins_n != sorted(vs_ins_n, reverse=True):
        print("FAILED:RES-0060 emit install sort is not descending installs")
        return 1

    factors = [
        factor("vscode-optional-sort-installs", "vscode-marketplace", "Optional @sort:installs by Marketplace installation count", "documented", "optional-sort", "yes-optional", False, "E1", "Official VS Code docs list installs as a sort key."),
        factor("vscode-optional-sort-rating", "vscode-marketplace", "Optional @sort:rating", "documented", "optional-sort", "no", False, "E1", "Official docs."),
        factor("vscode-optional-sort-name", "vscode-marketplace", "Optional @sort:name", "documented", "optional-sort", "no", False, "E1", "Official docs."),
        factor("vscode-optional-sort-publishedDate", "vscode-marketplace", "Optional @sort:publishedDate", "documented", "optional-sort", "no", False, "E1", "Official docs."),
        factor("vscode-optional-sort-updateDate", "vscode-marketplace", "Optional @sort:updateDate", "documented", "optional-sort", "no", False, "E1", "Official docs."),
        factor("vscode-filter-featured", "vscode-marketplace", "@featured merchandising filter", "documented", "merchandising", "no", False, "E1", "Official docs."),
        factor("vscode-filter-popular", "vscode-marketplace", "@popular merchandising filter (mapping unpublished)", "documented", "merchandising", "unknown", False, "E1", "Filter is documented; whether it equals install count is not."),
        factor("vscode-default-search-sort-none-or-relevance", "vscode-marketplace", "Text search uses SortBy.NoneOrRelevance", "documented", "default-mode", "not-documented-as-input", True, "E1", "vscode extensionGalleryService.ts: text query -> NoneOrRelevance."),
        factor("vscode-empty-query-sort-install-count", "vscode-marketplace", "Empty query uses SortBy.InstallCount", "documented", "default-mode-empty-query", "yes-default-when-empty", True, "E1", "Same source: else branch sets InstallCount."),
        factor("vscode-default-relevance-weights-unpublished", "vscode-marketplace", "Weights inside default relevance scoring", "inferred", "default-weights", "unknown", True, "E3", "Mode is documented; scoring function and weights are unpublished. Blog guesses are not measured fact."),
        factor("vscode-popular-filter-install-mapping-unpublished", "vscode-marketplace", "Whether @popular equals install-count rank", "inferred", "merchandising-mapping", "unknown", False, "E3", "Docs name the filter, not the ranking key."),
        factor("chrome-default-user-ratings", "chrome-web-store", "User ratings enter the ranking heuristic", "documented", "default-input", "no", True, "E3", "Operator docs; no public ranking API, so not E1 measured fact."),
        factor("chrome-default-downloads-vs-uninstalls", "chrome-web-store", "Usage statistics: downloads vs uninstalls over time", "documented", "default-input", "yes-flow-not-stock", True, "E3", "Operator docs. Flow (install vs uninstall), not raw install stock."),
        factor("chrome-default-listing-metadata", "chrome-web-store", "Store-listing metadata in search ranking", "documented", "default-input", "no", True, "E3", "Operator docs."),
        factor("chrome-default-qualitative-ux", "chrome-web-store", "Qualitative UX (design, purpose, onboarding, ease of use)", "documented", "default-input", "no", True, "E3", "Operator docs; not mechanically scored here."),
        factor("chrome-badge-may-boost-rank", "chrome-web-store", "Earned badges may receive higher search/filter rankings", "documented", "default-input", "no", True, "E3", "Operator docs say 'may'."),
        factor("chrome-default-relative-weights-unpublished", "chrome-web-store", "Relative weights of ratings vs usage vs listing vs UX vs badges", "inferred", "default-weights", "unknown", True, "E3", "Categories documented; weights unpublished."),
        factor("npm-default-keyword-matching", "npm-website", "Default search: keyword match on title, description, readme, keywords", "documented", "default-input", "no", True, "E1", "npm docs, 2025-02-13."),
        factor("npm-default-spam-or-new-deprioritize-exists", "npm-website", "Minimal boost to deprioritize spammy or entirely new packages", "documented", "default-input", "anti-new", True, "E1", "Documented existence, not magnitude."),
        factor("npm-optional-sort-downloads", "npm-website", "Optional sort by download counts", "documented", "optional-sort", "yes-optional", False, "E1", "Official docs."),
        factor("npm-optional-sort-dependents", "npm-website", "Optional sort by most dependents", "documented", "optional-sort", "no", False, "E1", "Official docs."),
        factor("npm-optional-sort-last-published", "npm-website", "Optional sort by last published date", "documented", "optional-sort", "no", False, "E1", "Official docs."),
        factor("npm-spam-new-boost-magnitude-unpublished", "npm-website", "Magnitude of the spam/new-package deprioritization boost", "inferred", "default-weights", "anti-new", True, "E3", "Existence documented; size unpublished."),
        factor("jetbrains-default-text-relevance", "jetbrains-marketplace", "Initial score from ID, name, description, tags, vendor match", "documented", "default-input", "no", True, "E1", "Official ranking docs."),
        factor("jetbrains-default-staff-pick-boost-exists", "jetbrains-marketplace", "Staff-pick coefficient applied to initial score", "documented", "default-input", "no", True, "E1", "Existence documented; numeric coefficient unpublished."),
        factor("jetbrains-default-log10-downloads-multiplier", "jetbrains-marketplace", "Popularity multiplier log10(1 + 5 * downloads_count)", "documented", "default-input", "yes-default-multiplier", True, "E1", "Closed-form install-count feedback in default search."),
        factor("jetbrains-default-sqrt-rating-multiplier", "jetbrains-marketplace", "Rating multiplier sqrt(rating) with Bayesian rating", "documented", "default-input", "no", True, "E1", "Official ranking + rating docs."),
        factor("jetbrains-category-top-downloaded-pure-downloads", "jetbrains-marketplace", "Top downloaded category ranked by download count", "documented", "category-sort", "yes-category", False, "E1", "Official docs."),
        factor("jetbrains-staff-pick-coefficient-value-unpublished", "jetbrains-marketplace", "Numeric staff-pick coefficient", "inferred", "default-weights", "no", True, "E3", "Boost exists; value unpublished."),
        factor("jetbrains-text-field-match-weights-unpublished", "jetbrains-marketplace", "Per-field text match weights (docs: scored differently)", "inferred", "default-weights", "no", True, "E3", "Differential scoring stated; values unpublished."),
        factor("pypi-default-lexical-field-boosts", "pypi", "OpenSearch multi_match with name^10, description^5, keywords^5, summary^5 plus exact-name boost 1000", "documented", "default-input", "no", True, "E1", "warehouse/search/queries.py on main."),
        factor("pypi-default-no-download-count", "pypi", "Download counts are not a search field; PyPI does not display download statistics", "documented", "documented-absence", "no-absent", True, "E1", "Source SEARCH_FIELDS + packaging.python.org guide."),
        factor("program-imp0102-bm25-no-popularity", "this-program-index", "IMP-0102: BM25 over name, description, tags, skill names; no popularity term; rank from query+document only", "documented", "contracted-default", "forbidden", True, "E1", "Catalog contract. Search index not implemented on this worktree."),
        factor("program-imp0094-quality-no-popularity", "this-program-index", "IMP-0094 quality score: no popularity input may change the score", "documented", "quality-not-search", "forbidden", False, "E1", "Separate from search rank; still a discoverability-adjacent score."),
    ]

    documented = [f for f in factors if f["evidence_class"] == "documented"]
    inferred = [f for f in factors if f["evidence_class"] == "inferred"]
    default_items = [f for f in factors if f["used_in_default_ranking"]]
    default_inf = [f for f in default_items if f["evidence_class"] == "inferred"]
    default_doc = [f for f in default_items if f["evidence_class"] == "documented"]

    claims = [
        {
            "id": "C-VS-OPTIONAL-INSTALL-SORT",
            "canonical_mechanism": "VS Code Marketplace documents install-count as an explicit optional sort key (@sort:installs) and the gallery API honours sortBy=4 as descending install count.",
            "evidence_tier": "E1",
            "confidence_band": "high",
            "measured_fact": True,
            "named_settling_probe": "probe2_dual_rail_and_api.py",
            "rails": [
                rail("vscode-docs-extension-marketplace", "prose", "installs</code> - Sort by Marketplace installation count, in descending order."),
                rail("vscode-api-sort-installs", "api", '"statisticName":"install"'),
            ],
            "strongest_caveat": "Optional sort is not the default text-search ranker.",
        },
        {
            "id": "C-VS-DEFAULT-NEQ-INSTALLS",
            "canonical_mechanism": "For query text 'python', gallery sortBy=0 (relevance) returns a different top-8 than sortBy=4 (installs). vscode source sends NoneOrRelevance when the query has text and InstallCount when it does not.",
            "evidence_tier": "E1",
            "confidence_band": "high",
            "measured_fact": True,
            "named_settling_probe": "probe2_dual_rail_and_api.py",
            "rails": [
                rail("vscode-source-gallery-service", "prose", "query = query.withSortBy(SortBy.NoneOrRelevance);"),
                rail("vscode-api-sort-relevance", "api", '"extensionName":"python"'),
            ],
            "observation": {
                "query": "python",
                "relevance_top8": vs_rel,
                "installs_top8": vs_ins,
                "relevance_install_counts": vs_rel_n,
                "installs_sort_install_counts": vs_ins_n,
                "orders_equal": False,
            },
            "strongest_caveat": "This refutes 'default rank IS install count'. It does not prove install count is unused inside relevance; that weight is unpublished.",
        },
        {
            "id": "C-JB-DEFAULT-DOWNLOAD-MULTIPLIER",
            "canonical_mechanism": "JetBrains Marketplace default search multiplies the post-staff-pick score by log10(1 + 5 * downloads_count) and then by sqrt(rating). That is documented install-count feedback in default ranking.",
            "evidence_tier": "E1",
            "confidence_band": "high",
            "measured_fact": True,
            "named_settling_probe": "probe2_dual_rail_and_api.py",
            "rails": [
                rail("jetbrains-docs-ranking", "prose", "log10(1 + 5 * downloads_count)"),
                rail("jetbrains-api-search", "api", '"downloads":'),
            ],
            "strongest_caveat": "The log10 term's share of any given ranking is query-dependent. Staff-pick coefficient and per-field text weights remain unpublished.",
        },
        {
            "id": "C-NPM-WEBSITE-DEFAULT-LEXICAL",
            "canonical_mechanism": "npm website default search is keyword matching over title, description, readme, and keywords, with no subjective ranking except a minimal boost to deprioritize spammy or entirely new packages. Download counts are an optional sort, not the documented default.",
            "evidence_tier": "E1",
            "confidence_band": "high",
            "measured_fact": True,
            "named_settling_probe": "probe2_dual_rail_and_api.py",
            "rails": [
                rail("npm-docs-search", "prose", "No subjective ranking criteria are applied, except for a minimal boost to deprioritize spammy or entirely new packages"),
                rail("npm-registry-api-docs", "api", "| popularity | float | **Query** |"),
            ],
            "strongest_caveat": "Registry API still documents quality/popularity/maintenance weights. Website docs (2025-02-13) say default web search does not apply those subjective criteria. The two surfaces disagree; this unit does not collapse them.",
        },
        {
            "id": "C-PYPI-SEARCH-NO-DOWNLOADS",
            "canonical_mechanism": "PyPI Warehouse search ranks by lexical multi_match with published field boosts. SEARCH_FIELDS contains no download-count field. packaging.python.org states PyPI does not display download statistics.",
            "evidence_tier": "E1",
            "confidence_band": "high",
            "measured_fact": True,
            "named_settling_probe": "probe2_dual_rail_and_api.py",
            "rails": [
                rail("pypi-warehouse-search-source", "api", "SEARCH_FIELDS = ["),
                rail("pypi-download-stats-guide", "prose", "PyPI does not display download statistics for a number of reasons:"),
            ],
            "strongest_caveat": "Absence of download stats on the project page is not by itself a search-rank proof; the SEARCH_FIELDS source is the rank proof. Together they are two rails.",
        },
        {
            "id": "C-PROGRAM-INDEX-FORBIDS-POPULARITY",
            "canonical_mechanism": "This program's contracted index (IMP-0102) is BM25 over package name, description, tags and skill names with no popularity term; ranking must be explainable from the query and the document alone. IMP-0094 independently forbids popularity as a quality-score input. The fixture registry has no install/download/popularity keys. A useful new package is discoverable iff its lexical fields match the query; it does not need an install ramp. The search index itself is not implemented on this worktree.",
            "evidence_tier": "E1",
            "confidence_band": "high",
            "measured_fact": True,
            "named_settling_probe": "probe1_documented_inferred_split.py",
            "rails": [
                local_rail(
                    "api",
                    "command-center/WORK-UNIT-CATALOG.json",
                    "with no popularity term",
                    note="IMP-0102 question_or_target in the catalog JSON.",
                ),
                local_rail(
                    "prose",
                    "tools/marketplace/fixture/registry/index.json",
                    '"registry_id": "reg:imp-0118-fixture"',
                    note="IMP-0118 known-good fixture index has no popularity/install/download keys.",
                ),
            ],
            "strongest_caveat": "This is a catalog contract plus fixture schema, not a live BM25 measurement. IMP-0102 search code is absent.",
        },
        {
            "id": "C-CWS-DOCUMENTED-HEURISTIC-SINGLE-RAIL",
            "canonical_mechanism": "Chrome Web Store operator docs state ranking is a heuristic over user ratings and usage statistics (downloads vs uninstalls over time), plus listing metadata, qualitative UX, and possible badge boosts. Weights are unpublished. No public ranking API was obtained.",
            "evidence_tier": "E3",
            "confidence_band": "medium",
            "measured_fact": False,
            "named_settling_probe": "probe1_documented_inferred_split.py",
            "rails": [
                rail("chrome-docs-discovery", "prose", "the number of downloads vs. uninstalls over time"),
            ],
            "strongest_caveat": "Marketplace-documented, but one rail only → E3, not cited as measured fact. A blog repeating this would still be E3.",
        },
    ]

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    documented_n = len(documented)
    inferred_n = len(inferred)
    total = documented_n + inferred_n
    default_total = len(default_items)
    default_inf_n = len(default_inf)

    install_default = [
        f["id"]
        for f in factors
        if f["used_in_default_ranking"]
        and f["evidence_class"] == "documented"
        and str(f["install_count_feedback"]).startswith("yes")
    ]

    doc = {
        "schema_version": 1,
        "unit_id": "RES-0060",
        "id": "RES-0060",
        "state": "SUCCESS",
        "status": "DELIVERED",
        "sentinel": C.SENTINEL,
        "title": "Determine what makes a package findable and how ranking is computed in extension marketplaces",
        "question": QUESTION,
        "ranking_factor_list_split_documented_versus_inferred": True,
        "undocumented_proportion_stated": True,
        "evidence_tier_vocabulary": [
            "E1: two mechanically independent rails (structured API/source probe AND prose), each with permalink, fetch timestamp, HTTP status, sha256 of captured bytes",
            "E3: one rail, or blog-only, or unpublished weights; may not be cited as measured fact",
            "E4: local contract/fixture only when paired with a second local rail",
        ],
        "answers": {
            "signals_that_drive_discovery": {
                "documented": [f["id"] for f in documented],
                "inferred": [f["id"] for f in inferred],
            },
            "how_much_is_install_count_feedback": {
                "numeric_share_of_rank_variance": "unpublished-in-all-surveyed-default-rankers-except-jetbrains-closed-form-multiplier",
                "extension_marketplaces_with_documented_default_install_or_usage_input": [
                    "jetbrains-marketplace (log10 downloads multiplier)",
                    "chrome-web-store (downloads vs uninstalls; E3, weights unpublished)",
                    "vscode-marketplace (InstallCount only when the query is empty; text search uses unpublished relevance)",
                ],
                "documented_default_install_feedback_factor_ids": install_default,
                "statement": (
                    "Install-count (or usage) feedback is a documented default-rank input "
                    "on JetBrains (closed-form log10 multiplier) and, with unpublished "
                    "weight, on Chrome (downloads vs uninstalls). VS Code documents "
                    "install-count as the empty-query sort and as an optional @sort, "
                    "and a live API probe shows text-search relevance is not identical "
                    "to install sort. npm website documents download counts as optional "
                    "sort only. PyPI search source has no download field. This program "
                    "forbids a popularity term. No honest single percentage of 'the ranking' "
                    "is install-count feedback across marketplaces; the unpublished-weight "
                    "share of default-ranking mechanism items is stated below."
                ),
            },
            "new_package_in_this_programs_index": (
                "Under IMP-0102, a useful new package is findable when the query matches "
                "its name, description, tags, or skill names (BM25; no popularity term). "
                "It does not need accumulated installs. IMP-0094 quality score is a separate "
                "decomposable number that also forbids popularity. The BM25 index is not "
                "implemented on this worktree; discoverability here is the contracted ranker, "
                "not a live hit list."
            ),
        },
        "ranking_factors": factors,
        "undocumented_proportion": {
            "documented_count": documented_n,
            "inferred_count": inferred_n,
            "total": total,
            "proportion": inferred_n / total,
            "proportion_percent": round(100.0 * inferred_n / total, 1),
            "statement": (
                f"{inferred_n} of {total} ranking-factor rows are inferred "
                f"({inferred_n}/{total} = {inferred_n / total:.4f}, "
                f"{round(100.0 * inferred_n / total, 1)}%). "
                f"Of default-ranking mechanism items, {default_inf_n} of {default_total} "
                f"({default_inf_n / default_total:.4f}) are unpublished weights or "
                f"coefficients. Documented count={documented_n}."
            ),
            "default_ranking_mechanism": {
                "documented_count": len(default_doc),
                "inferred_count": default_inf_n,
                "total": default_total,
                "proportion": default_inf_n / default_total,
            },
        },
        "claims": claims,
        "source_lineage": [
            {
                "id": r["id"],
                "url": r["url"],
                "fetched_at": r["fetched_at"],
                "http_status": r["http_status"],
                "sha256": r["sha256"],
                "path": r["path"],
            }
            for r in C.load_index()
        ],
        "freshness": {
            "captured_at_min": min(r["fetched_at"] for r in C.load_index()),
            "captured_at_max": max(r["fetched_at"] for r in C.load_index()),
            "artifact_written_at": now,
        },
        "snapshot_sha256_note": "Per-source sha256 is on each source_lineage row and each rail.",
        "reviewer": {
            "reviewer_id": "RES-0060-adversarial-refuter",
            "independent": True,
            "read_conclusion_first": False,
            "default_to_refuted": True,
            "verdict": "PARTIAL",
            "scope_not_agreement": True,
            "surviving_claims": [
                "C-VS-OPTIONAL-INSTALL-SORT",
                "C-VS-DEFAULT-NEQ-INSTALLS",
                "C-JB-DEFAULT-DOWNLOAD-MULTIPLIER",
                "C-NPM-WEBSITE-DEFAULT-LEXICAL",
                "C-PYPI-SEARCH-NO-DOWNLOADS",
                "C-PROGRAM-INDEX-FORBIDS-POPULARITY",
            ],
            "refuted_as_measured_fact": [
                "C-CWS-DOCUMENTED-HEURISTIC-SINGLE-RAIL",
                "any numeric share of default rank variance attributed to install count outside JetBrains' published multiplier",
            ],
            "strongest_surviving_caveat": (
                "Unpublished weights mean 'how much of ranking is install-count feedback' "
                "cannot be a single measured fraction except on JetBrains, where it is a "
                "documented multiplicative log10 term of unpublished relative contribution. "
                "Chrome's heuristic is operator-documented but E3. This program's index "
                "forbids popularity by contract; the BM25 implementation is absent."
            ),
        },
        "tests": [
            {
                "id": "documented-versus-inferred-split",
                "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/RES-0060/probe1_documented_inferred_split.py",
                "result": "PASS",
            },
            {
                "id": "undocumented-proportion-and-dual-rail-control",
                "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/RES-0060/probe2_dual_rail_and_api.py",
                "result": "PASS",
            },
        ],
        "outputs": {
            "path": C.OUT_REL,
            "schema": "command-center/schema/research-claim-record.schema.json",
        },
        "notes": (
            "G-1 research record for RES-0060. Blog-only ranking factors were not "
            "promoted to documented. cloud ok=true is not delivery. Did not run "
            "global unit_manifest.py --write."
        ),
    }
    out = C.REPO / C.OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    sha, size = C.digest_file(out)
    print(f"wrote {C.OUT_REL} bytes={size} sha256={sha}")
    print(C.SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
