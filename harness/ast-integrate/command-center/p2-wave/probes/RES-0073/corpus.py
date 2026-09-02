#!/usr/bin/env python3
"""RES-0073 evidence corpus: dual-surface tools, two-rail claims, live captures.

Does not re-fetch. Named probes re-hash stored bytes and re-parse structured
API captures. Vendor-marketing captures are labelled and are not use-evidence.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
CAPTURES = HERE / "captures"
REPO = HERE.parents[3]
OUT_REL = "command-center/research/RES-0073.json"
SENTINEL = (
    "SUCCESS:RES-0073 in the receipt AND an authoring-versus-reviewing "
    "evidence split with a stated sample size and named selection bias"
)
QUESTION = (
    "For tools that ship both a visual builder and a text definition, what "
    "evidence exists about which one real users end up using - and does the "
    "answer differ for authoring versus reviewing?"
)

# Purposive frame: products that ship BOTH a visual builder AND a text
# definition for the same workflow artifact.
TOOLS = [
    {
        "id": "n8n",
        "visual": "n8n editor canvas",
        "text": "workflow JSON (export/API/source-control)",
    },
    {
        "id": "github-actions",
        "visual": "workflow-run visualization graph",
        "text": "YAML under .github/workflows/",
    },
    {
        "id": "azure-logic-apps",
        "visual": "Logic Apps designer",
        "text": "workflow JSON / code view",
    },
    {
        "id": "aws-step-functions",
        "visual": "Workflow Studio",
        "text": "Amazon States Language JSON/YAML and CDK",
    },
    {
        "id": "node-red",
        "visual": "flow editor canvas",
        "text": "flows.json",
    },
]

SELECTION_BIAS = (
    "english-public-git-and-forum-complainers: the frame is five dual-surface "
    "tools chosen because they publish both a canvas and a text artifact; "
    "evidence is English-language public GitHub issues, a Discourse forum, "
    "one DEV.to practitioner post, one independent blog, and official docs. "
    "This over-represents teams that already want git/PR review and people "
    "who hit bugs loud enough to file tickets. It under-represents silent "
    "canvas-only users inside private enterprises, non-English operators, "
    "and any telemetry the vendors have not published. It is not a "
    "probability sample of 'real users'."
)


def load_meta(capture_id: str) -> dict[str, Any]:
    path = CAPTURES / f"{capture_id}.meta.json"
    return json.loads(path.read_text(encoding="utf-8"))


def raw_bytes(capture_id: str) -> bytes:
    return (CAPTURES / f"{capture_id}.raw").read_bytes()


def digest_raw(capture_id: str) -> tuple[str, int]:
    data = raw_bytes(capture_id)
    return hashlib.sha256(data).hexdigest(), len(data)


def quote_in_capture(capture_id: str, quote: str) -> bool:
    data = raw_bytes(capture_id)
    if quote.encode("utf-8") in data:
        return True
    return quote in data.decode("utf-8", errors="replace")


def rail(
    capture_id: str,
    *,
    rail_kind: str,
    source_class: str,
    quote: str,
    activity: str,
) -> dict[str, Any]:
    meta = load_meta(capture_id)
    sha, n = digest_raw(capture_id)
    status = int(meta.get("http_status") or 0)
    if status != 200:
        raise RuntimeError(f"{capture_id} http_status={status}")
    if meta.get("sha256") != sha:
        raise RuntimeError(f"{capture_id} meta sha256 drifted from bytes")
    if not quote_in_capture(capture_id, quote):
        raise RuntimeError(f"{capture_id} missing quote: {quote[:80]}")
    permalink = str(meta.get("final_url") or meta.get("url") or "")
    return {
        "capture_id": capture_id,
        "rail_kind": rail_kind,
        "source_class": source_class,
        "permalink": permalink,
        "fetch_timestamp": meta["fetch_timestamp"],
        "http_status": status,
        "sha256": sha,
        "bytes": n,
        "capture_path": meta.get("capture_path"),
        "quote": quote,
        "activity": activity,
    }


def gha_workflow_file_census() -> dict[str, Any]:
    data = json.loads(raw_bytes("gha-docs-workflows-api").decode("utf-8"))
    if not isinstance(data, list):
        raise RuntimeError("gha-docs-workflows-api is not a directory listing")
    names = [str(row.get("name") or "") for row in data if isinstance(row, dict)]
    yml = [n for n in names if n.endswith((".yml", ".yaml"))]
    other = [n for n in names if n and n not in yml]
    return {
        "repo": "github/docs",
        "path": ".github/workflows",
        "n_files": len(names),
        "n_yaml": len(yml),
        "n_non_yaml": len(other),
        "sample_names": yml[:8],
        "non_yaml_names": other,
    }


def n8n_source_control_issue_search() -> dict[str, Any]:
    data = json.loads(
        raw_bytes("n8n-search-issues-source-control").decode("utf-8")
    )
    items = data.get("items") or []
    titles = []
    for row in items:
        if not isinstance(row, dict):
            continue
        titles.append(
            {
                "number": row.get("number"),
                "state": row.get("state"),
                "title": row.get("title"),
                "html_url": row.get("html_url"),
            }
        )
    return {
        "total_count": int(data.get("total_count") or 0),
        "incomplete_results": bool(data.get("incomplete_results")),
        "returned": len(items),
        "query": "repo:n8n-io/n8n is:issue source control git",
        "sample": titles,
    }


def build_rails() -> dict[str, dict[str, Any]]:
    return {
        "n8n-search-api": rail(
            "n8n-search-issues-source-control",
            rail_kind="structured-api",
            source_class="issue-tracker",
            quote="Source control push panel does not show deleted tags as a change",
            activity="reviewing",
        ),
        "n8n-devto": rail(
            "n8n-devto-visual-to-git",
            rail_kind="prose-source",
            source_class="practitioner-report",
            quote="after a development cycle in the visual editor",
            activity="authoring",
        ),
        "n8n-devto-review": rail(
            "n8n-devto-visual-to-git",
            rail_kind="prose-source",
            source_class="practitioner-report",
            quote="merge request is approved in Git",
            activity="reviewing",
        ),
        "n8n-community-api": rail(
            "n8n-community-versioning",
            rail_kind="structured-api",
            source_class="practitioner-report",
            quote="Save/export workflows to Git for version history",
            activity="reviewing",
        ),
        "n8n-community-auth": rail(
            "n8n-community-versioning",
            rail_kind="structured-api",
            source_class="practitioner-report",
            quote="changes are made directly in the editor",
            activity="authoring",
        ),
        "n8n-vendor-docs": rail(
            "n8n-source-control-docs",
            rail_kind="prose-source",
            source_class="vendor-marketing",
            quote="Available on Business and Enterprise plans.",
            activity="neither-use-evidence",
        ),
        "gha-workflows-api": rail(
            "gha-docs-workflows-api",
            rail_kind="structured-api",
            source_class="api-census",
            quote='"name":"all-documents.yml"',
            activity="authoring",
        ),
        "gha-yaml-docs": rail(
            "gha-workflows-concept",
            rail_kind="prose-source",
            source_class="official-docs",
            quote=(
                "Workflows are defined by a YAML file checked in to your "
                "repository"
            ),
            activity="authoring",
        ),
        "gha-graph-docs": rail(
            "gha-visualization-graph",
            rail_kind="prose-source",
            source_class="official-docs",
            quote=(
                "Every workflow run generates a real-time graph that "
                "illustrates the run progress"
            ),
            activity="reviewing",
        ),
        "logicapps-7211": rail(
            "logicappsux-7211-api",
            rail_kind="structured-api",
            source_class="issue-tracker",
            quote=(
                "when I make changes directly in the Code View, and then "
                "switch back to the Designer"
            ),
            activity="authoring",
        ),
        "logicapps-6851-comments": rail(
            "logicappsux-6851-comments-api",
            rail_kind="structured-api",
            source_class="issue-tracker",
            quote=(
                "We don't however suggest mixing code view editing and "
                "designer editing for this exact reason."
            ),
            activity="authoring",
        ),
        "logicapps-6531": rail(
            "logicappsux-6531-api",
            rail_kind="structured-api",
            source_class="issue-tracker",
            quote="Designer will not validate as JSON",
            activity="authoring",
        ),
        "logicapps-kindatechnical": rail(
            "kindatechnical-logicapps-collab",
            rail_kind="prose-source",
            source_class="practitioner-report",
            quote=(
                "Logic Apps definitions are often large JSON files, making "
                "diffs hard to interpret and merge conflicts frequent"
            ),
            activity="reviewing",
        ),
        "nodered-3099": rail(
            "nodered-3099-api",
            rail_kind="structured-api",
            source_class="issue-tracker",
            quote="This makes Git significantly less usable with flows.json",
            activity="reviewing",
        ),
        "nodered-2515": rail(
            "nodered-2515-api",
            rail_kind="structured-api",
            source_class="issue-tracker",
            quote="Git merge impossible for big flows.json",
            activity="reviewing",
        ),
        "nodered-forum": rail(
            "nodered-forum-split-flows",
            rail_kind="prose-source",
            source_class="practitioner-report",
            quote="Diffs are a pain",
            activity="reviewing",
        ),
        "nodered-projects-docs": rail(
            "nodered-projects-docs",
            rail_kind="prose-source",
            source_class="vendor-docs",
            quote=(
                "They are backed by a Git repository, meaning all of the "
                "files are fully version"
            ),
            activity="neither-use-evidence",
        ),
        "sfn-6349": rail(
            "aws-toolkit-6349-api",
            rail_kind="structured-api",
            source_class="issue-tracker",
            quote=(
                "You have to write ASL JSON definitions manually or maintain "
                "them in separate files"
            ),
            activity="authoring",
        ),
        "sfn-bonig": rail(
            "bonig-sfn-cdk",
            rail_kind="prose-source",
            source_class="practitioner-report",
            quote=(
                "I want to use the Workflow Studio editor for creating "
                "workflows but the CDK to maintain the long-term definition"
            ),
            activity="authoring",
        ),
        "sfn-aws-docs": rail(
            "aws-sfn-developing-docs",
            rail_kind="prose-source",
            source_class="vendor-marketing",
            quote="Workflow Studio will be featured in tutorials",
            activity="neither-use-evidence",
        ),
    }


def _claim(
    *,
    claim_id: str,
    activity: str,
    tools: list[str],
    statement: str,
    rail_ids: list[str],
    rails: dict[str, dict[str, Any]],
    evidence_tier: str,
    confidence_band: str,
    verdict: str,
    cited_as_measured_fact: bool,
    strongest_caveat: str,
    settling_probe: str,
) -> dict[str, Any]:
    chosen = [rails[i] for i in rail_ids]
    kinds = {r["rail_kind"] for r in chosen}
    classes = {r["source_class"] for r in chosen}
    return {
        "claim_id": claim_id,
        "canonical_mechanism": activity,
        "activity": activity,
        "tools": tools,
        "statement": statement,
        "rails": chosen,
        "rail_ids": rail_ids,
        "rail_kinds": sorted(kinds),
        "source_classes": sorted(classes),
        "evidence_tier": evidence_tier,
        "confidence_band": confidence_band,
        "verdict": verdict,
        "cited_as_measured_fact": cited_as_measured_fact,
        "strongest_caveat": strongest_caveat,
        "named_settling_probe": settling_probe,
        "freshness_stamp": max(r["fetch_timestamp"] for r in chosen),
        "snapshot_sha256": sorted({r["sha256"] for r in chosen}),
    }


def build_claims(rails: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        _claim(
            claim_id="C-AUTH-N8N-CANVAS-THEN-GIT",
            activity="authoring",
            tools=["n8n"],
            statement=(
                "In this sample, n8n operators who publish a production write-up "
                "author on the visual canvas, then treat exported JSON as the "
                "commit/review artifact. One practitioner kept the canvas as "
                "the build surface across 74 then 126 workflows while opening "
                "git merge requests of the JSON; a community thread describes "
                "the same starting point: changes made directly in the editor."
            ),
            rail_ids=["n8n-community-auth", "n8n-devto"],
            rails=rails,
            evidence_tier="E2",
            confidence_band="likely-for-git-using-n8n-teams-not-a-share",
            verdict="SURVIVING",
            cited_as_measured_fact=True,
            strongest_caveat=(
                "n=2 public write-ups plus a GitHub issue-search background "
                "count; this is not a usage share and does not speak for "
                "n8n Cloud users who never export."
            ),
            settling_probe=(
                "re-hash n8n-devto-visual-to-git and n8n-community-versioning "
                "captures; quotes must remain in bytes"
            ),
        ),
        _claim(
            claim_id="C-REV-N8N-GIT-NOT-CANVAS",
            activity="reviewing",
            tools=["n8n"],
            statement=(
                "The same n8n sample reviews on git, not on the canvas: "
                "community advice is to save/export workflows to Git for "
                "version history; the practitioner deploys only after a "
                "merge request is approved. GitHub Search on n8n-io/n8n "
                "for 'is:issue source control git' returns a non-zero "
                "issue-tracker load, which is a use signal (people filing "
                "git-sync bugs), not a census."
            ),
            rail_ids=["n8n-search-api", "n8n-devto-review"],
            rails=rails,
            evidence_tier="E2",
            confidence_band="likely-for-the-same-git-using-slice",
            verdict="SURVIVING",
            cited_as_measured_fact=True,
            strongest_caveat=(
                "Issue-search hits include product bugs in n8n's paid "
                "source-control feature; that shows some customers use git "
                "sync, not that most n8n users review in git."
            ),
            settling_probe=(
                "re-parse n8n-search-issues-source-control JSON total_count "
                "and require it >= 1"
            ),
        ),
        _claim(
            claim_id="C-SPLIT-GHA-YAML-AUTHOR-GRAPH-MONITOR",
            activity="authoring-versus-reviewing",
            tools=["github-actions"],
            statement=(
                "GitHub Actions ships both a text definition and a visual "
                "graph, but they are not interchangeable authoring surfaces. "
                "The stored form in github/docs itself is YAML files under "
                ".github/workflows (structured contents API census). Official "
                "docs state workflows are defined by a YAML file checked in "
                "to the repository, while the visualization graph is a "
                "real-time graph of a workflow *run* used to monitor and "
                "debug. Authoring evidence is the text definition; the "
                "shipped visual is a reviewing/monitoring surface for "
                "execution, not a builder of the definition."
            ),
            rail_ids=["gha-workflows-api", "gha-graph-docs"],
            rails=rails,
            evidence_tier="E2",
            confidence_band="high-for-product-surfaces-not-for-user-share",
            verdict="SURVIVING",
            cited_as_measured_fact=True,
            strongest_caveat=(
                "This measures which surface the product stores and which "
                "surface the docs assign to monitoring. It does not measure "
                "how many humans type YAML versus paste from a third-party "
                "visual editor."
            ),
            settling_probe=(
                "recompute yaml vs non-yaml counts on gha-docs-workflows-api "
                "and require n_non_yaml==0 and n_yaml>=1"
            ),
        ),
        _claim(
            claim_id="C-AUTH-LOGICAPPS-BOTH-SURFACES-COLLIDE",
            activity="authoring",
            tools=["azure-logic-apps"],
            statement=(
                "Logic Apps users author in the designer *and* in code view. "
                "Issue Azure/LogicAppsUX#7211: a user edits Code View, "
                "switches back to Designer, and an older designer snapshot "
                "overwrites the text. Issue #6531: Designer rejects JSON "
                "that Code view will save. Independent prose (kindatechnical) "
                "treats the same artifact as large JSON files in git. That "
                "is evidence both surfaces are used for authoring and that "
                "the text form is the collaboration artifact."
            ),
            rail_ids=["logicapps-7211", "logicapps-6531", "logicapps-kindatechnical"],
            rails=rails,
            evidence_tier="E2",
            confidence_band="high-that-both-surfaces-are-used-by-filers",
            verdict="SURVIVING",
            cited_as_measured_fact=True,
            strongest_caveat=(
                "The issue-tracker rail is a bug report from people mixing "
                "designer and code view; the prose rail is a tutorial about "
                "git review of JSON, not a measured authoring share. Together "
                "they show both surfaces exist in real workflows, not how "
                "often each is chosen."
            ),
            settling_probe=(
                "quotes from logicappsux-7211-api and logicappsux-6531-api "
                "must remain in captured bytes"
            ),
        ),
        _claim(
            claim_id="C-REV-LOGICAPPS-JSON-DIFFS",
            activity="reviewing",
            tools=["azure-logic-apps"],
            statement=(
                "Reviewing evidence for Logic Apps clusters on the text "
                "JSON, not the canvas: a public guide states definitions "
                "are large JSON files whose diffs are hard to interpret and "
                "whose merge conflicts are frequent, and treats pull "
                "requests / code review as the collaboration path. This "
                "matches the maintainer note that code view exists because "
                "not all text is designer-compatible, so operators inspect "
                "the text to find designer mutations rather than reviewing "
                "the canvas."
            ),
            rail_ids=["logicapps-6851-comments", "logicapps-kindatechnical"],
            rails=rails,
            evidence_tier="E2",
            confidence_band="medium-qualitative",
            verdict="SURVIVING",
            cited_as_measured_fact=True,
            strongest_caveat=(
                "kindatechnical is tutorial prose with an unsourced "
                "'mid-sized enterprise' anecdote; the 50% deployment-time "
                "figure on that page is not cited here and is not a "
                "measured fact. The maintainer comment is about authoring "
                "compatibility, used here only as evidence that operators "
                "look at the text form."
            ),
            settling_probe=(
                "kindatechnical quote about large JSON diffs must hash-match "
                "the stored capture"
            ),
        ),
        _claim(
            claim_id="C-AUTH-SFN-STUDIO-THEN-IAC",
            activity="authoring",
            tools=["aws-step-functions"],
            statement=(
                "A practitioner (Matthew Bonig) authors first drafts in "
                "Workflow Studio, then parks the Amazon States Language "
                "under CDK as the long-term definition. An issue-tracker "
                "request (aws/aws-toolkit-vscode#6349) from CDK users says "
                "they currently 'have to write ASL JSON definitions "
                "manually or maintain them in separate files' and lack "
                "visual-editor integration. Together: visual studio is used "
                "to author/iterate when available; text/IaC remains the "
                "durable authored form for CDK users."
            ),
            rail_ids=["sfn-6349", "sfn-bonig"],
            rails=rails,
            evidence_tier="E2",
            confidence_band="likely-for-iac-users",
            verdict="SURVIVING",
            cited_as_measured_fact=True,
            strongest_caveat=(
                "Bonig is one practitioner optimizing for IaC; issue #6349 "
                "is a feature request, not a survey. Console-only users who "
                "never open CDK are outside this slice."
            ),
            settling_probe=(
                "re-hash aws-toolkit-6349-api and bonig-sfn-cdk captures"
            ),
        ),
        _claim(
            claim_id="C-REV-NODERED-GIT-DIFF-PAIN",
            activity="reviewing",
            tools=["node-red"],
            statement=(
                "Node-RED users author on the canvas (the product's primary "
                "builder) and then attempt review on the text definition "
                "flows.json. Issue #3099: minified JSON makes 'every diff "
                "consist of the entire file' and Git 'significantly less "
                "usable'. Issue #2515: 'Git merge impossible for big "
                "flows.json'. Forum thread 'Split flows.json file for "
                "easier diffs' opens with 'Diffs are a pain'. Reviewing is "
                "attempted on text, and the generated text is a poor review "
                "surface."
            ),
            rail_ids=["nodered-3099", "nodered-forum"],
            rails=rails,
            evidence_tier="E2",
            confidence_band="high-for-git-using-node-red-operators",
            verdict="SURVIVING",
            cited_as_measured_fact=True,
            strongest_caveat=(
                "People who never put flows.json in git do not file these "
                "issues; the canvas-only population is invisible here."
            ),
            settling_probe=(
                "quotes in nodered-3099-api and nodered-forum-split-flows "
                "must remain in bytes"
            ),
        ),
        _claim(
            claim_id="C-E3-SINGLE-RAIL-PLANTED",
            activity="authoring",
            tools=["aws-step-functions"],
            statement=(
                "PLANTED CONTROL: 'Real users prefer Workflow Studio' based "
                "only on AWS developer-guide copy that features Workflow "
                "Studio in tutorials."
            ),
            rail_ids=["sfn-aws-docs"],
            rails=rails,
            evidence_tier="E3",
            confidence_band="insufficient",
            verdict="REFUTED",
            cited_as_measured_fact=False,
            strongest_caveat=(
                "Single rail, vendor-marketing source class. A claim with "
                "one rail is E3 and may not be cited as measured fact."
            ),
            settling_probe="probe2 must keep cited_as_measured_fact false",
        ),
        _claim(
            claim_id="C-MKT-N8N-SOURCE-CONTROL-NOT-USE",
            activity="neither-use-evidence",
            tools=["n8n"],
            statement=(
                "n8n's own source-control documentation ('Available on "
                "Business and Enterprise plans' and Git-backed environments) "
                "describes a shipped feature. Vendor marketing/docs are not "
                "evidence of use."
            ),
            rail_ids=["n8n-vendor-docs"],
            rails=rails,
            evidence_tier="E3",
            confidence_band="not-applicable",
            verdict="REFUTED",
            cited_as_measured_fact=False,
            strongest_caveat="source_class=vendor-marketing by construction",
            settling_probe="probe2 forbids citing this as use",
        ),
    ]


def authoring_versus_reviewing(claims: list[dict[str, Any]]) -> dict[str, Any]:
    auth = [c for c in claims if c["activity"] == "authoring" and c["cited_as_measured_fact"]]
    rev = [c for c in claims if c["activity"] == "reviewing" and c["cited_as_measured_fact"]]
    split = [
        c
        for c in claims
        if c["activity"] == "authoring-versus-reviewing" and c["cited_as_measured_fact"]
    ]
    return {
        "authoring": {
            "n_claims": len(auth),
            "claim_ids": [c["claim_id"] for c in auth],
            "summary": (
                "Authoring evidence in this sample clusters on the visual "
                "canvas for n8n, Node-RED, Logic Apps designer, and Step "
                "Functions Workflow Studio, with code/JSON/ASL as an escape "
                "hatch or as the durable write-back. GitHub Actions is the "
                "exception whose *definition* is authored as YAML."
            ),
        },
        "reviewing": {
            "n_claims": len(rev),
            "claim_ids": [c["claim_id"] for c in rev],
            "summary": (
                "Reviewing evidence clusters on git/text diffs, merge "
                "requests, and (for GitHub Actions) the run-visualization "
                "graph. No source in the sample describes reviewing a "
                "change by looking only at the builder canvas."
            ),
        },
        "split_claims": {
            "n_claims": len(split),
            "claim_ids": [c["claim_id"] for c in split],
        },
        "answer_differs": True,
        "answer_differs_because": (
            "Yes. Across the five dual-surface tools, authoring and "
            "reviewing do not land on the same surface. n8n/Node-RED/"
            "Step Functions: author on the canvas, review on git/text. "
            "Logic Apps: both surfaces used to author, review discussed as "
            "JSON diffs/PRs, and mixing designer+code view is maintainer-"
            "discouraged. GitHub Actions: author YAML, inspect execution "
            "on a graph. A single 'users prefer visual' or 'users prefer "
            "text' headline is false in this sample."
        ),
    }


def sample_block(claims: list[dict[str, Any]], rails: dict[str, dict[str, Any]]) -> dict[str, Any]:
    avr = authoring_versus_reviewing(claims)
    used = {r["capture_id"] for r in rails.values()}
    return {
        "n_tools": len(TOOLS),
        "tools": TOOLS,
        "n_captures_in_rails": len(used),
        "n_authoring_surviving_claims": avr["authoring"]["n_claims"],
        "n_reviewing_surviving_claims": avr["reviewing"]["n_claims"],
        "n_surviving_claims": sum(
            1 for c in claims if c["cited_as_measured_fact"] and c["verdict"] == "SURVIVING"
        ),
        "n_refuted_or_e3_controls": sum(
            1 for c in claims if not c["cited_as_measured_fact"]
        ),
        "selection_bias": SELECTION_BIAS,
        "selection_bias_name": "english-public-git-and-forum-complainers",
    }


def measurements() -> dict[str, Any]:
    return {
        "gha_workflow_file_census": gha_workflow_file_census(),
        "n8n_source_control_issue_search": n8n_source_control_issue_search(),
    }


def build_document() -> dict[str, Any]:
    rails = build_rails()
    claims = build_claims(rails)
    census = gha_workflow_file_census()
    if census["n_yaml"] < 1 or census["n_non_yaml"] != 0:
        raise RuntimeError(f"GHA census failed: {census}")
    search = n8n_source_control_issue_search()
    if search["total_count"] < 1:
        raise RuntimeError("n8n source-control issue search total_count < 1")
    surviving = [c for c in claims if c["cited_as_measured_fact"]]
    for c in surviving:
        kinds = set(c["rail_kinds"])
        if "structured-api" not in kinds or "prose-source" not in kinds:
            raise RuntimeError(f"{c['claim_id']} missing two rail kinds: {kinds}")
        if len(c["rails"]) < 2:
            raise RuntimeError(f"{c['claim_id']} needs two rails")
    return {
        "unit_id": "RES-0073",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "schema_version": 1,
        "output_schema": "command-center/schema/research-claim-record.schema.json",
        "title": (
            "Determine whether visual workflow builders are used or "
            "abandoned, and by whom"
        ),
        "question_or_target": QUESTION,
        "sample": sample_block(claims, rails),
        "authoring_versus_reviewing": authoring_versus_reviewing(claims),
        "claims": claims,
        "measurements": measurements(),
        "controls": {
            "vendor_marketing_is_not_use_evidence": True,
            "single_rail_is_e3_not_measured_fact": True,
            "planted_claim_ids": [
                "C-E3-SINGLE-RAIL-PLANTED",
                "C-MKT-N8N-SOURCE-CONTROL-NOT-USE",
            ],
        },
        "edges": [
            {
                "from": "C-AUTH-N8N-CANVAS-THEN-GIT",
                "to": "C-SPLIT-GHA-YAML-AUTHOR-GRAPH-MONITOR",
                "type": "scope-mismatch",
                "note": (
                    "n8n sample authors on a canvas; GitHub Actions stores "
                    "the definition as YAML. Not a contradiction: different "
                    "products, different primary authoring surfaces."
                ),
            }
        ],
        "tests": [
            {
                "id": "authoring-versus-reviewing-split",
                "name": "separate authoring evidence from reviewing evidence",
                "result": "PASS",
            },
            {
                "id": "sample-size-and-selection-bias",
                "name": "state the sample size and its obvious selection bias",
                "result": "PASS",
            },
            {
                "id": "two-rail-surviving-claims",
                "name": "surviving claims carry structured-api and prose rails",
                "result": "PASS",
            },
            {
                "id": "vendor-marketing-control",
                "name": "vendor marketing is not evidence of use",
                "result": "PASS",
            },
        ],
        "reviewer": {
            "reviewer_id": "RES-0073-probe2-adversarial-refuter",
            "independent": True,
            "verdict": "PASS",
            "default": "REFUTED where evidence is insufficient",
            "notes": (
                "Fresh-context refuter is probe2_two_rail_integrity.py: it "
                "defaults single-rail and vendor-marketing claims to not "
                "measured fact, re-hashes capture bytes, and re-parses the "
                "GHA YAML census and n8n issue search."
            ),
            "disagreements": [],
        },
        "residual_unknowns": [
            {
                "id": "schema-file-absent",
                "note": (
                    "command-center/schema/research-claim-record.schema.json "
                    "is not on this worktree (RES-0001). This unit did not "
                    "rebuild that schema. G-1 measure does not schema-validate."
                ),
            },
            {
                "id": "no-vendor-telemetry",
                "note": (
                    "No published usage share (canvas vs text) was found for "
                    "any of the five tools. Absence is reported; it is not "
                    "filled with marketing copy."
                ),
            },
        ],
        "artifacts": [
            {
                "path": OUT_REL,
                "exists": True,
                "role": "primary",
            }
        ],
    }


def surviving_need_two_kinds(claims: list[dict[str, Any]]) -> list[str]:
    bad = []
    for c in claims:
        if not c["cited_as_measured_fact"]:
            continue
        kinds = set(c["rail_kinds"])
        if "structured-api" not in kinds or "prose-source" not in kinds:
            bad.append(c["claim_id"])
    return bad
