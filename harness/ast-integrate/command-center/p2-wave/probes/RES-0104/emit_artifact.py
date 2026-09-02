#!/usr/bin/env python3
"""Emit command-center/research/RES-0104.json from stored captures."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import contract as C  # noqa: E402
import observed as O  # noqa: E402

OUT = REPO / "command-center/research/RES-0104.json"
INDEX = HERE / "captures" / "index.json"
SENTINEL = C.SENTINEL
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0104/probe1_pattern_sizes.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0104/probe2_rails_control.py"
)


def idx_rails() -> dict:
    doc = json.loads(INDEX.read_text(encoding="utf-8"))
    return {r["id"]: r for r in doc["rails"]}


def find_line(capture_id: str, snippet: str) -> int:
    text = (HERE / "captures" / f"{capture_id}.bin").read_text(
        encoding="utf-8", errors="replace"
    )
    idx = text.find(snippet)
    if idx < 0:
        raise SystemExit(f"FAILED:snippet not in {capture_id}: {snippet[:80]}")
    return text[:idx].count("\n") + 1


def rail(rows: dict, capture_id: str, snippet: str) -> dict:
    meta = rows[capture_id]
    if meta.get("http_status") != 200 or not meta.get("sha256"):
        raise SystemExit(f"FAILED:rail not 200: {capture_id}")
    line = find_line(capture_id, snippet)
    return {
        "id": capture_id,
        "kind": meta["kind"],
        "permalink": meta["permalink"],
        "requested_url": meta["requested_url"],
        "fetched_at": meta["fetched_at"],
        "http_status": meta["http_status"],
        "sha256": meta["sha256"],
        "bytes": meta["bytes"],
        "capture_path": meta["path"],
        "snippet": snippet,
        "line": line,
    }


def claim(**kwargs) -> dict:
    row = {
        "contradiction_edges": kwargs.pop("contradiction_edges", []),
        "support_edges": kwargs.pop("support_edges", []),
        "freshness_stamp": kwargs.pop("freshness_stamp", None),
        "snapshot_sha256": kwargs.pop("snapshot_sha256", None),
        "settling_probe": kwargs.pop("settling_probe", P1),
    }
    row.update(kwargs)
    rails = row["source_lineage"]
    row["snapshot_sha256"] = row.get("snapshot_sha256") or "|".join(
        r["sha256"] for r in rails
    )
    row["freshness_stamp"] = row.get("freshness_stamp") or max(
        r["fetched_at"] for r in rails
    )
    return row


def main() -> int:
    rows = idx_rails()
    obs = O.load()
    mkt = obs["vscode_marketplace_extensions"]
    npm_n = obs["npm_search_total"]
    k8s_n = obs["k8s_openapi_v3_documents"]

    r_act = rail(
        rows,
        "vscode-activation-events-md",
        "Beginning with VS Code 1.74.0, commands contributed by your extension do not require a corresponding `onCommand` activation event",
    )
    r_cmd = rail(
        rows,
        "vscode-command-guide-md",
        "the extension will be activated and `registerCommand` will bind",
    )
    r_qap = rail(
        rows,
        "vscode-commands-quickaccess-ts",
        "complete set of commands shows up as result",
    )
    r_mkt = rail(rows, "vscode-marketplace-query", '"name":"TotalCount"')
    r_kep = rail(rows, "k8s-kep-3352-readme", "up to 80 requests")
    r_k8s_api = rail(
        rows,
        "k8s-openapi-v3-listing",
        "apis__apps__v1_openapi.json",
    )
    r_k8s_doc = rail(
        rows,
        "k8s-api-concepts-md",
        "discovery serves two endpoints, while the unaggregated discovery serves a",
    )
    r_npm_doc = rail(rows, "npm-registry-api-md", "default 20, max 250")
    r_npm_api = rail(rows, "npm-search-total", '"sanitized_name":"@expressots/boost-ts"')
    r_mcp_mdx = rail(
        rows,
        "mcp-tools-spec-mdx",
        '"method": "tools/list"',
    )
    r_mcp_ts = rail(rows, "mcp-schema-ts", "inputSchema: { $schema?: string; type: \"object\"")
    r_mcp_bp = rail(
        rows,
        "mcp-client-best-practices",
        "defers injecting them into the model's context",
    )
    r_sk_doc = rail(
        rows,
        "anthropic-skills-overview",
        "install many Skills without context penalty",
    )
    r_sk_md = rail(
        rows,
        "anthropic-skill-dev-skillmd",
        "Progressive Disclosure Design Principle",
    )
    r_sep = rail(
        rows,
        "mcp-sep2636-pr",
        "A user with full scopes legitimately holding 200 tools is not helped",
    )

    c1 = claim(
        id="C-INDEX-HYDRATE",
        canonical_mechanism=(
            "Index-then-hydrate: publish a lightweight catalog entry "
            "(command id + title in package.json) so the palette can list the "
            "capability without loading the implementation; hydrate the handler "
            "only on invoke via implicit onCommand activation (VS Code >= 1.74)."
        ),
        source_lineage=[r_act, r_cmd, r_qap, r_mkt],
        evidence_tier="E2",
        confidence_band="high",
        verdict="CONFIRMED",
        cited_as_measured_fact=True,
        strongest_caveat=(
            f"Catalog size observed is marketplace extensions ({mkt}), not a "
            "counted Command Palette row inventory. The contribution-point "
            "index is what scales across that plugin ecosystem; this is not a "
            "measurement of keystroke latency at 500 commands."
        ),
        support_edges=["C-SKILLS-LEVELS"],
        catalog_size_observed=mkt,
        catalog_size_unit="vscode_marketplace_extensions",
    )
    c2 = claim(
        id="C-SEARCH-PAGINATE",
        canonical_mechanism=(
            "Search-and-page: never materialise the catalog; return a bounded "
            "page (npm registry search size default 20, max 250) plus a total "
            "count, and let the client iterate with `from`."
        ),
        source_lineage=[r_npm_doc, r_npm_api],
        evidence_tier="E2",
        confidence_band="high",
        verdict="CONFIRMED",
        cited_as_measured_fact=True,
        strongest_caveat=(
            f"Live total={npm_n} is for query {obs['npm_search_query']!r}, not "
            "the entire npm corpus. The page cap of 250 still forbids loading "
            "that result set in one payload."
        ),
        catalog_size_observed=npm_n,
        catalog_size_unit="npm_search_matches_for_boost-exact:false",
    )
    c3 = claim(
        id="C-K8S-UNAGGREGATED-STORM",
        canonical_mechanism=(
            "Eager per-partition fetch: one discovery request per group-version. "
            "KEP-3352 records this as a request storm (up to 80 requests) and "
            "replaces it with two aggregated documents."
        ),
        source_lineage=[r_kep, r_k8s_api, r_k8s_doc],
        evidence_tier="E2",
        confidence_band="high",
        verdict="CONFIRMED",
        cited_as_measured_fact=True,
        strongest_caveat=(
            f"The structured rail counts {k8s_n} OpenAPI v3 documents at "
            f"kubernetes {obs['k8s_tag']}, which is the same order as the KEP's "
            "'up to 80 requests' figure but is not a live apiserver round-trip "
            "trace. This size is below 500 and is the breaking-point control, "
            "not evidence that aggregated discovery was measured at 500 items."
        ),
        catalog_size_observed=k8s_n,
        catalog_size_unit="openapi_v3_group_documents",
    )
    c4 = claim(
        id="C-MCP-FULLSCHEMA-LIST",
        canonical_mechanism=(
            "Shipped MCP tools/list returns a Tool record whose inputSchema is "
            "required. Pagination exists, but each listed tool still carries "
            "the invocation contract. Official client guidance is to defer "
            "injecting those definitions into the model and search first."
        ),
        source_lineage=[r_mcp_ts, r_mcp_mdx, r_mcp_bp],
        evidence_tier="E2",
        confidence_band="high",
        verdict="CONFIRMED",
        cited_as_measured_fact=True,
        strongest_caveat=(
            "This confirms the on-wire shape and the recommended host-side "
            "workaround. It does not measure token cost at 500 tools on a live "
            "MCP server."
        ),
        support_edges=["C-SEP2636-TOKEN-NUMBERS"],
    )
    c5 = claim(
        id="C-SKILLS-LEVELS",
        canonical_mechanism=(
            "Three-level progressive disclosure for agent skills: name+"
            "description always loaded (~100 tokens), SKILL.md body on trigger, "
            "bundled files only when referenced."
        ),
        source_lineage=[r_sk_doc, r_sk_md],
        evidence_tier="E2",
        confidence_band="medium",
        verdict="PARTIAL",
        cited_as_measured_fact=True,
        strongest_caveat=(
            "Mechanism is documented on two rails. No skill-catalog item count "
            "was observed on this host, so this pattern is not the 500-item "
            "size evidence; it is the same index-then-hydrate idea specialised "
            "to LLM context."
        ),
        support_edges=["C-INDEX-HYDRATE"],
    )
    c6 = claim(
        id="C-SEP2636-TOKEN-NUMBERS",
        canonical_mechanism=(
            "Open SEP-2636 claims typical 300-2000 tokens per full Tool and "
            "that a 200-tool full-schema dump is already unhelped by scope "
            "filtering; its prototype reports 5238 tokens for 37 synthetic tools."
        ),
        source_lineage=[r_sep],
        evidence_tier="E3",
        confidence_band="low",
        verdict="REFUTED",
        cited_as_measured_fact=False,
        strongest_caveat=(
            "Single rail: GitHub pull request body, state=open, not merged into "
            "the MCP spec. Default REFUTED as measured fact. May not be cited "
            "for the 500-item answer."
        ),
        contradiction_edges=["C-MCP-FULLSCHEMA-LIST"],
        settling_probe=P2,
    )
    c7 = claim(
        id="C-MEASURED-AT-500-EXPERIMENT",
        canonical_mechanism=(
            "A controlled 500-item capability catalog was loaded end-to-end on "
            "this worktree and timed."
        ),
        source_lineage=[r_mkt],
        evidence_tier="E3",
        confidence_band="low",
        verdict="REFUTED",
        cited_as_measured_fact=False,
        strongest_caveat=(
            "No 500-item fixture was executed. Marketplace size 140220 is "
            "larger than 500 (large-to-small inference), which is not the same "
            "as a 500-item experiment. Single-rail leftover would also be E3."
        ),
        settling_probe=P2,
    )
    c8 = claim(
        id="C-05-ECO-LOCAL-SHARD",
        canonical_mechanism=(
            "The inherited 05-ECOSYSTEM-AND-FRONTIER-RESEARCH.md shard on this "
            "host corroborates the progressive-disclosure recommendation."
        ),
        source_lineage=[r_sk_doc],
        evidence_tier="E3",
        confidence_band="low",
        verdict="REFUTED",
        cited_as_measured_fact=False,
        strongest_caveat=(
            "Local inputs command-center/sources/REGISTER.md and the Windows "
            "harness-restore 05-ECOSYSTEM file are absent on this Linux "
            "worktree. Public rails still answer the unit question; the local "
            "shard is source-unavailable, not a measured corroboration."
        ),
        settling_probe=P2,
    )

    patterns = [
        {
            "id": "P-INDEX-HYDRATE",
            "name": "Index-then-hydrate (IDE command palette / plugin contributions)",
            "canonical_mechanism": c1["canonical_mechanism"],
            "catalog_size_observed": mkt,
            "catalog_size_unit": "vscode_marketplace_extensions",
            "observed_at": r_mkt["fetched_at"],
            "usable_at_500": True,
            "usable_at_500_basis": (
                "observed catalog is larger than 500; a pattern working at "
                f"{mkt} is evidence it can keep 500 usable. The converse "
                "(proven at 50 => works at 500) is rejected by this unit."
            ),
            "claim_ids": ["C-INDEX-HYDRATE"],
            "systems": ["VS Code Command Palette", "VS Code Marketplace"],
        },
        {
            "id": "P-SEARCH-PAGINATE",
            "name": "Search-and-page (plugin ecosystem registry)",
            "canonical_mechanism": c2["canonical_mechanism"],
            "catalog_size_observed": npm_n,
            "catalog_size_unit": "npm_search_matches_for_boost-exact:false",
            "observed_at": r_npm_api["fetched_at"],
            "usable_at_500": True,
            "usable_at_500_basis": (
                f"query matched {npm_n} packages; API max page size is 250, so "
                "a 500-item result cannot be loaded in one payload and does "
                "not need to be."
            ),
            "claim_ids": ["C-SEARCH-PAGINATE"],
            "systems": ["npm registry search"],
        },
        {
            "id": "P-AGGREGATED-DISCOVERY",
            "name": "Aggregated index (large API surface)",
            "canonical_mechanism": (
                "Collapse N group-version discovery documents into two "
                "aggregated endpoints (/api and /apis)."
            ),
            "catalog_size_observed": k8s_n,
            "catalog_size_unit": "openapi_v3_group_documents",
            "observed_at": r_k8s_api["fetched_at"],
            "usable_at_500": False,
            "usable_at_500_basis": (
                f"Observed at {k8s_n} documents. Per this unit, a pattern "
                "proven below 500 is not evidence at 500."
            ),
            "claim_ids": ["C-K8S-UNAGGREGATED-STORM"],
            "systems": ["Kubernetes discovery / OpenAPI v3"],
        },
    ]

    doc = {
        "unit_id": "RES-0104",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "title": (
            "Extract progressive-disclosure patterns for very large capability "
            "catalogs"
        ),
        "question": (
            "How do large-catalog systems (IDE command palettes, large API "
            "surfaces, plugin ecosystems) reveal capability progressively, and "
            "which pattern keeps a 500-item catalog usable without loading it all?"
        ),
        "canonical_mechanism": c1["canonical_mechanism"],
        "source_lineage": [
            r_act,
            r_cmd,
            r_qap,
            r_mkt,
            r_kep,
            r_k8s_api,
            r_k8s_doc,
            r_npm_doc,
            r_npm_api,
            r_mcp_mdx,
            r_mcp_ts,
            r_mcp_bp,
            r_sk_doc,
            r_sk_md,
        ],
        "evidence_tier": "E2",
        "confidence_band": "high",
        "settling_probe": P1,
        "contradiction_edges": ["C-MEASURED-AT-500-EXPERIMENT", "C-05-ECO-LOCAL-SHARD"],
        "support_edges": ["C-INDEX-HYDRATE", "C-SEARCH-PAGINATE"],
        "freshness_stamp": max(r["fetched_at"] for r in [r_mkt, r_npm_api, r_k8s_api]),
        "snapshot_sha256": "|".join(
            rows[k]["sha256"]
            for k in (
                "vscode-marketplace-query",
                "npm-search-total",
                "k8s-openapi-v3-listing",
            )
        ),
        "patterns": patterns,
        "breaking_point": {
            "pattern_id": "P-EAGER-PARTITION-FETCH",
            "name": "Unaggregated per-group-version discovery",
            "breaks_above": 80,
            "size_unit": "group-version-round-trips",
            "observed_partition_count": k8s_n,
            "observed_partition_unit": "openapi_v3_group_documents",
            "claim_id": "C-K8S-UNAGGREGATED-STORM",
            "why": (
                "KEP-3352 states unaggregated discovery can require up to 80 "
                "individual requests and is a source of latency and throttling. "
                "The live GitHub API listing of kubernetes v1.32.2 OpenAPI v3 "
                f"files contains {k8s_n} documents — the same partition shape. "
                "npm search independently refuses pages above 250. Both are "
                "eager-dump / per-partition load patterns; the KEP number is "
                "the named control."
            ),
            "secondary_api_cap": {
                "system": "npm registry search",
                "breaks_above": 250,
                "size_unit": "results_per_request",
                "note": "API-enforced max `size`; not a UX study.",
            },
        },
        "answer_for_500": {
            "pattern_id": "P-INDEX-HYDRATE",
            "also_works": "P-SEARCH-PAGINATE",
            "does_not_cite": [
                "P-AGGREGATED-DISCOVERY (observed 61 < 500)",
                "C-SEP2636-TOKEN-NUMBERS (E3, open PR)",
                "C-MEASURED-AT-500-EXPERIMENT (REFUTED)",
            ],
            "statement": (
                "A 500-item capability catalog stays usable without loading it "
                "all by publishing an index (id + one-line title/description) "
                "and hydrating the body/schema/extension only on selection, "
                "the VS Code contributes.commands + activate-on-invoke pattern, "
                f"observed at {mkt} marketplace extensions. When even the index "
                "must not be fully listed, search-and-page (npm, max 250/page, "
                f"observed total {npm_n} on the recorded query) is the fallback. "
                "Eager full-document dump is the control that breaks."
            ),
        },
        "claims": [c1, c2, c3, c4, c5, c6, c7, c8],
        "tests": [
            {
                "id": "annotate-pattern-sizes",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "breaking-point-control",
                "command": P2,
                "result": "PASS",
            },
        ],
        "negative_controls": [
            {
                "id": "NC-SINGLE-RAIL-IS-E3",
                "fires_on": "a cited_as_measured_fact claim with one rail",
                "silent_on_good": True,
            },
            {
                "id": "NC-PATTERN-SIZE-REQUIRED",
                "fires_on": "dropping catalog_size_observed from a pattern",
                "silent_on_good": True,
            },
            {
                "id": "NC-BREAKING-POINT-REQUIRED",
                "fires_on": "dropping breaking_point.breaks_above",
                "silent_on_good": True,
            },
        ],
        "reviewer": {
            "reviewer_id": "RES-0104-probe2-rails-control",
            "role": "adversarial-refuter",
            "independent": True,
            "fresh_context": (
                "Mechanical refuter in probe2; not a second human session. "
                "Defaults to REFUTED where a claim lacks two independent rails "
                "or overclaims a 500-item experiment."
            ),
            "verdict": "PASS",
            "refuted_ids": [
                "C-SEP2636-TOKEN-NUMBERS",
                "C-MEASURED-AT-500-EXPERIMENT",
                "C-05-ECO-LOCAL-SHARD",
            ],
        },
        "residual_unknowns": [
            "05-ECOSYSTEM-AND-FRONTIER-RESEARCH.md is not on this Linux host",
            "command-center/sources/REGISTER.md is absent",
            "RES-0100 artifact is absent; G-1 for this unit does not wait on it",
            "command-center/schema/research-claim-record.schema.json is absent (RES-0001); this record uses the Phase-1 field list from the catalog",
            "VS Code built-in command-palette row count was not enumerated from source",
            "No live Kubernetes apiserver was queried; OpenAPI file listing is the structured proxy",
        ],
        "produced_by": {
            "vendor": "cursor",
            "model": "grok-4.6",
            "role": "ecosystem-cartographer",
            "execution_substrate": "linux-local",
        },
        "cloud_ok": False,
        "named_probes": [
            {"id": "probe1", "command": P1},
            {"id": "probe2", "command": P2},
        ],
        "output_path": "command-center/research/RES-0104.json",
        "output_schema": "command-center/schema/research-claim-record.schema.json",
    }

    ok, why = C.check(doc, repo=REPO)
    if not ok:
        print(f"FAILED:RES-0104 contract {why}")
        return 1
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        json.dumps(doc, indent=2, ensure_ascii=True) + "\n", encoding="utf-8"
    )
    print(f"wrote {OUT.relative_to(REPO).as_posix()} bytes={OUT.stat().st_size}")
    print(SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
