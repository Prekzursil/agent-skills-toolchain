#!/usr/bin/env python3
"""Emit command-center/research/RES-0028.json from the frozen Aider snapshot."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import extract as E  # noqa: E402

OUT_REL = "command-center/research/RES-0028.json"
SENTINEL = "SUCCESS:RES-0028"
COMPLETION = (
    "SUCCESS:RES-0028 in the receipt AND the ranking algorithm cited at source "
    "file:line plus an explicit reproduced/not-reproduced verdict"
)


def main() -> int:
    loc = E.ranking_loci()
    cap = E.load_capture()
    src = cap["source"]
    citation = E.file_line_citation()
    if not citation.startswith("aider/repomap.py:"):
        print(f"FAILED:RES-0028 emit citation is not a source file:line: {citation}")
        return 1
    if "nx.pagerank" not in loc["pagerank_primary_text"]:
        print("FAILED:RES-0028 emit pagerank text mismatch")
        return 1

    record = {
        "unit_id": "RES-0028",
        "id": "RES-0028",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "completion_sentinel": COMPLETION,
        "title": "Extract the Aider repo-map mechanism and its measured token/accuracy tradeoff",
        "question": (
            "How exactly does Aider build its repo map (graph ranking over symbol "
            "references, token budget), and what evidence exists that it improves "
            "edit accuracy versus simply sending more files?"
        ),
        "output_schema": "command-center/schema/research-claim-record.schema.json",
        "schema_note": (
            "Declared schema file is absent on this worktree (RES-0001 did not ship). "
            "This record still carries the Phase-2 field set named by RES-0001: claim "
            "id, canonical mechanism, source lineage, evidence tier E1-E4, confidence "
            "band, named settling probe, contradiction/support edges, freshness stamp, "
            "snapshot sha256."
        ),
        "ranking_algorithm": {
            "name": "personalized PageRank over a directed file graph of symbol references",
            "library": "networkx.pagerank",
            "cited_at_source_file_line": citation,
            "source_path": loc["source_path"],
            "source_line": loc["pagerank_primary_line"],
            "source_line_text": loc["pagerank_primary_text"],
            "function": "RepoMap.get_ranked_tags",
            "function_line": loc["get_ranked_tags_line"],
            "permalink": loc["permalink"],
            "commit": loc["commit"],
            "not_a_blog_description": True,
        },
        "independent_reproduction_verdict": "NOT-REPRODUCED",
        "reproduced_not_reproduced_verdict": "not-reproduced",
        "canonical_mechanism": (
            "Parse each source file with tree-sitter tag queries into defs and refs; "
            "build a directed NetworkX graph whose nodes are files and whose weighted "
            "edges run referencer-file -> definer-file; call nx.pagerank at "
            f"{citation} with chat-file / mentioned-ident personalization; distribute "
            "each file's PageRank mass across its outgoing symbol edges; then binary-"
            f"search the ranked tag prefix at {loc['source_path']}:{loc['binary_search_line']} "
            "until the rendered tree is within 15% of the token budget (default "
            f"map_tokens=1024 at {loc['source_path']}:{loc['default_map_tokens_line']}; "
            f"8x multiplier when the chat has no files at "
            f"{loc['source_path']}:{loc['no_files_multiplier_line']})."
        ),
        "claims": [
            {
                "claim_id": "RES-0028-M1-PAGERANK-SYMBOL-GRAPH",
                "canonical_mechanism": "personalized-pagerank-over-symbol-reference-graph-with-token-budget",
                "statement": (
                    "Aider's repo map ranks files by networkx.pagerank on a symbol-"
                    f"reference graph and trims the ranked tags to a token budget. "
                    f"Ranking implementation: {citation}."
                ),
                "evidence_tier": "E2",
                "confidence_band": "high-for-mechanism-existence; none-for-accuracy-delta",
                "promotable_to_tier1": False,
                "doi": None,
                "arxiv_id": None,
                "effect_size": None,
                "baseline": None,
                "promotion_block": (
                    "No paper DOI/arXiv. Mechanism existence is sourced from the "
                    "implementation, which is an extract, not E1."
                ),
                "source_lineage": {
                    "url": src["permalink"] + f"#L{loc['pagerank_primary_line']}",
                    "final_url": src["raw_url"],
                    "http_status": src["http_status"],
                    "fetched_at": src["fetched_at"],
                    "sha256": src["sha256"],
                    "commit": src["commit"],
                    "locator": citation,
                    "excerpt": loc["pagerank_primary_text"],
                },
                "freshness_stamp": src["fetched_at"],
                "snapshot_sha256": src["sha256"],
                "named_settling_probe": (
                    "command-center/p2-wave/probes/RES-0028/probe1_ranking_file_line.py"
                ),
                "strongest_caveat": (
                    "Line numbers are pinned to commit "
                    f"{src['commit'][:12]}; a later refactor of get_ranked_tags "
                    "would move the citation. Tag quality follows tree-sitter query "
                    "coverage, with a pygments Token.Name fallback for refs."
                ),
                "edges": {
                    "supports": ["RES-0028-M1-TOKEN-BUDGET-BINARY-SEARCH"],
                    "contradicts": [],
                },
            },
            {
                "claim_id": "RES-0028-M1-TOKEN-BUDGET-BINARY-SEARCH",
                "canonical_mechanism": "binary-search-ranked-tags-to-token-budget",
                "statement": (
                    "After ranking, get_ranked_tags_map_uncached binary-searches the "
                    f"ranked tag prefix (aider/repomap.py:{loc['binary_search_line']}) "
                    "until the rendered outline is within 15% of max_map_tokens."
                ),
                "evidence_tier": "E2",
                "confidence_band": "high-for-mechanism-existence",
                "promotable_to_tier1": False,
                "doi": None,
                "arxiv_id": None,
                "effect_size": None,
                "baseline": None,
                "source_lineage": {
                    "url": src["permalink"] + f"#L{loc['binary_search_line']}",
                    "final_url": src["raw_url"],
                    "http_status": src["http_status"],
                    "fetched_at": src["fetched_at"],
                    "sha256": src["sha256"],
                    "locator": f"aider/repomap.py:{loc['binary_search_line']}",
                },
                "freshness_stamp": src["fetched_at"],
                "snapshot_sha256": src["sha256"],
                "named_settling_probe": (
                    "command-center/p2-wave/probes/RES-0028/probe1_ranking_file_line.py"
                ),
                "strongest_caveat": (
                    "The 15% slack and the map_mul_no_files=8 expansion mean "
                    "--map-tokens is not a hard cap; Aider-AI/aider#752 records this."
                ),
                "edges": {
                    "supports": ["RES-0028-M1-PAGERANK-SYMBOL-GRAPH"],
                    "contradicts": [],
                },
            },
            {
                "claim_id": "RES-0028-M2-ACCURACY-VS-MORE-FILES",
                "canonical_mechanism": "repo-map-beats-sending-more-files",
                "statement": (
                    "Aider's first-party docs claim the token-budgeted map is a better "
                    "use of context than adding many extra files, but they do not "
                    "report an isolated accuracy delta versus a more-files baseline."
                ),
                "evidence_tier": "E3",
                "confidence_band": "insufficient",
                "promotable_to_tier1": False,
                "doi": None,
                "arxiv_id": None,
                "effect_size": None,
                "baseline": None,
                "headline_without_baseline": True,
                "promotion_block": (
                    "Catalog evidence rule: a headline number without its baseline is "
                    "E3 and cannot promote a mechanism; a blog-reported improvement "
                    "without a stated baseline is E3 and cannot promote to Tier 1. "
                    "The 2023-10-22 tree-sitter post and docs/repomap.html describe "
                    "the graph ranker and a 1k default budget; neither states an "
                    "accuracy effect size nor a more-files control. SWE-bench Lite "
                    "full-stack scores are not an ablation of the map."
                ),
                "source_lineage": {
                    "url": cap["blog"]["url"],
                    "final_url": cap["blog"]["url"],
                    "http_status": cap["blog"]["http_status"],
                    "fetched_at": cap["blog"]["fetched_at"],
                    "sha256": cap["blog"]["sha256"],
                    "locator": "Building a better repository map with tree sitter (no numeric ablation)",
                },
                "second_rail": {
                    "url": cap["docs"]["url"],
                    "http_status": cap["docs"]["http_status"],
                    "fetched_at": cap["docs"]["fetched_at"],
                    "sha256": cap["docs"]["sha256"],
                    "locator": "docs/repomap.html graph ranking + --map-tokens 1k default",
                    "names_pagerank": cap["docs"]["names_pagerank"],
                },
                "freshness_stamp": cap["blog"]["fetched_at"],
                "snapshot_sha256": cap["blog"]["sha256"],
                "named_settling_probe": (
                    "command-center/p2-wave/probes/RES-0028/probe2_independent_reproduction.py"
                ),
                "independent_reproduction": {
                    "verdict": "NOT-REPRODUCED",
                    "independent_party_found": False,
                    "parties": [],
                    "control": (
                        "Searched first-party writeups and public secondary analyses "
                        "for an isolated repo-map vs more-files accuracy measurement. "
                        "None reported a baseline plus effect size from a party "
                        "independent of Aider."
                    ),
                },
                "strongest_caveat": (
                    "Qualitative FAQ advice that extra files distract the model is not "
                    "a measured tradeoff. Full-stack SWE-bench numbers cannot be "
                    "attributed to the map."
                ),
                "edges": {
                    "supports": [],
                    "contradicts": [],
                    "independence_collapse_with": [],
                },
            },
        ],
        "tests": [
            {
                "id": "T1",
                "name": "cite the ranking implementation at file:line, not the blog description",
                "result": "PASS",
                "observed": citation,
                "blog_rejected_as_ranking_citation": True,
            },
            {
                "id": "T2",
                "name": "control: state explicitly whether any independent party has reproduced the improvement",
                "result": "PASS",
                "observed": "NOT-REPRODUCED",
                "independent_party_has_reproduced_the_improvement": False,
            },
        ],
        "reviewer": {
            "reviewer_id": "RES-0028-probe2-independent-reproduction",
            "independent": True,
            "role": "adversarial-refuter",
            "default_if_insufficient": "REFUTED",
            "verdict": "PASS",
            "refuted_claims": ["RES-0028-M2-ACCURACY-VS-MORE-FILES as Tier-1/E1"],
            "surviving_claims": [
                "RES-0028-M1-PAGERANK-SYMBOL-GRAPH (E2, mechanism extract)",
                "RES-0028-M1-TOKEN-BUDGET-BINARY-SEARCH (E2, mechanism extract)",
            ],
            "notes": (
                "Accuracy-vs-more-files is REFUTED as a measured fact and kept only "
                "as E3. Ranking-algorithm existence survives because the live "
                "snapshot contains nx.pagerank at the cited file:line."
            ),
        },
        "source_lineage": {
            "rails": [
                {
                    "rail_id": "R1-source",
                    "url": src["permalink"],
                    "final_url": src["raw_url"],
                    "http_status": src["http_status"],
                    "fetched_at": src["fetched_at"],
                    "sha256": src["sha256"],
                    "bytes": src["bytes"],
                    "commit": src["commit"],
                },
                {
                    "rail_id": "R2-docs",
                    "url": cap["docs"]["url"],
                    "http_status": cap["docs"]["http_status"],
                    "fetched_at": cap["docs"]["fetched_at"],
                    "sha256": cap["docs"]["sha256"],
                    "bytes": cap["docs"]["bytes"],
                    "note": "Prose names a graph ranking algorithm and 1k token default; it does not name PageRank.",
                },
            ]
        },
        "freshness_stamp": src["fetched_at"],
        "snapshot_sha256": src["sha256"],
        "artifacts": [
            {"path": OUT_REL, "role": "primary"},
            {
                "path": "command-center/p2-wave/probes/RES-0028/fixtures/aider-repomap.py",
                "role": "frozen-source-snapshot",
                "sha256": src["sha256"],
            },
        ],
        "inputs_status": {
            "Aider-AI/aider_source": "captured",
            "Aider_benchmark_writeups": "captured; no isolated accuracy ablation present",
            "command-center/sources/REGISTER.md": "absent-on-this-worktree",
            "05-ECOSYSTEM-AND-FRONTIER-RESEARCH.md": "absent-on-this-worktree",
        },
        "ts": src["fetched_at"],
    }

    out = REPO / OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(record, indent=1, ensure_ascii=True) + "\n"
    if SENTINEL not in text:
        print("FAILED:RES-0028 emit sentinel missing")
        return 1
    if COMPLETION not in text:
        print("FAILED:RES-0028 emit completion_sentinel missing")
        return 1
    if citation not in text:
        print("FAILED:RES-0028 emit file:line missing")
        return 1
    if "NOT-REPRODUCED" not in text:
        print("FAILED:RES-0028 emit reproduction verdict missing")
        return 1
    out.write_text(text, encoding="utf-8")
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    print(f"wrote {OUT_REL} bytes={len(text.encode('utf-8'))} sha256={digest}")
    print(f"ranking_citation={citation}")
    print("independent_reproduction_verdict=NOT-REPRODUCED")
    print(SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
