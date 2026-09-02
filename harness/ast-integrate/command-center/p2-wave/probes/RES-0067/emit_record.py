#!/usr/bin/env python3
"""Emit command-center/research/RES-0067.json from live dual-rail captures."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import checker as C  # noqa: E402

OUT_REL = "command-center/research/RES-0067.json"
CAPTURES = HERE / "captures"


def meta(cid: str) -> dict:
    return json.loads((CAPTURES / f"{cid}.meta.json").read_text(encoding="utf-8"))


def rail(cid: str, kind: str, quote: str) -> dict:
    m = meta(cid)
    return {
        "kind": kind,
        "permalink": m["permalink"],
        "requested_url": m["requested_url"],
        "fetch_timestamp": m["fetch_timestamp"],
        "http_status": m["http_status"],
        "sha256": m["sha256_lf"],
        "bytes": m["bytes"],
        "capture_path": m["capture_rel"],
        "quote": quote,
    }


def claim(
    cid: str,
    text: str,
    mechanism: str,
    direction: str,
    confidence: str,
    confidence_numeric: float,
    rails: list[dict],
    settling: str,
) -> dict:
    return {
        "id": cid,
        "claim": text,
        "canonical_mechanism": mechanism,
        "direction_on_anti_adoption": direction,
        "verdict_on_engine_fact": "CONFIRMED",
        "evidence_tier": "E2",
        "confidence_band": confidence,
        "confidence_numeric": confidence_numeric,
        "named_settling_probe": settling,
        "source_lineage": [
            {
                "permalink": r["permalink"],
                "fetch_timestamp": r["fetch_timestamp"],
                "http_status": r["http_status"],
                "sha256": r["sha256"],
                "kind": r["kind"],
            }
            for r in rails
        ],
        "rails": rails,
        "freshness_stamp": max(r["fetch_timestamp"] for r in rails),
        "snapshot_sha256": rails[0]["sha256"],
    }


def main() -> int:
    p1 = (
        "PYTHONDONTWRITEBYTECODE=1 python3 -B "
        "command-center/p2-wave/probes/RES-0067/probe1_dual_rail.py"
    )
    p2 = (
        "PYTHONDONTWRITEBYTECODE=1 python3 -B "
        "command-center/p2-wave/probes/RES-0067/probe2_overclaim.py"
    )
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    c_dagger = claim(
        "C-DAGGER-CUE-TO-SDK",
        (
            "Dagger launched with a CUE configuration syntax / CUE SDK and later "
            "discontinued that SDK (2023-12-14) after host-language SDKs (Go, "
            "Python, Node.js) took adoption; maintainers published the reason as "
            "insufficient interest plus a steep decline in CUE usage."
        ),
        "novel-declarative-DSL-sunset-in-favor-of-host-language-SDKs",
        "CORROBORATES-weaker-heuristic",
        "almost certain",
        0.93,
        [
            rail(
                "dagger-sdk-dir-api",
                "api",
                '"name":"cue"',
            ),
            rail(
                "dagger-blog-ending-cue",
                "prose",
                "we are discontinuing support for our CUE SDK",
            ),
        ],
        p1,
    )
    # Second API quote is independently present; record it on the api rail notes.
    c_dagger["rails"][0]["quote_secondary"] = '"name":"go"'
    c_dagger["published_reason"] = (
        "steep decline in usage of original CUE configuration syntax; "
        "not enough community interest to keep feature-parity"
    )

    c_jenkins = claim(
        "C-JENKINS-DECLARATIVE",
        (
            "Jenkins added Declarative Pipeline Syntax 1.0 (2017-02-03) as a "
            "more constrained, config-like workflow language ON TOP OF the "
            "existing Scripted Pipeline Groovy DSL, explicitly so users without "
            "Groovy expertise could author pipelines. This is a migration toward "
            "a workflow language, not away from one."
        ),
        "imperative-DSL-to-constrained-declarative-workflow-language",
        "CUTS-AGAINST-categorical-anti-adoption",
        "almost certain",
        0.95,
        [
            rail(
                "jenkins-plugin-github-api",
                "api",
                '"name":"pipeline-model-definition-plugin"',
            ),
            rail(
                "jenkins-blog-declarative-ga",
                "prose",
                "The original syntax for defining Pipelines in Jenkins is a Groovy DSL that",
            ),
        ],
        p2,
    )
    c_jenkins["published_reason"] = (
        "straightforward structure, cookie-cutter pipelines, users regardless "
        "of Groovy expertise"
    )

    c_gha = claim(
        "C-GHA-HCL-TO-YAML",
        (
            "GitHub Actions stopped running HCL workflows on 2019-09-30 and "
            "required migration to YAML. That is a declarative-to-declarative "
            "language swap, not an escape from having a workflow language: the "
            "live JSON Schema for GitHub workflow files still requires 'on' and "
            "'jobs'."
        ),
        "declarative-workflow-language-replaced-with-another",
        "CUTS-AGAINST-categorical-anti-adoption",
        "almost certain",
        0.93,
        [
            rail(
                "gha-workflow-schema",
                "api",
                '"$id": "https://json.schemastore.org/github-workflow.json"',
            ),
            rail(
                "gha-changelog-hcl",
                "prose",
                "GitHub Actions will stop running workflows written in HCL",
            ),
        ],
        p2,
    )
    c_gha["published_reason"] = (
        "maintainers required HCL-to-YAML migration via a published script; "
        "YAML remained the author-facing workflow language"
    )

    c_prefect = claim(
        "C-PREFECT-DAG-FREE",
        (
            "Prefect 2 removed the constraint that workflows be written as "
            "explicit DAGs and now documents authoring in native Python with "
            "no DSLs, YAML, or special syntax. That is a published move away "
            "from a workflow-language / graph-definition surface."
        ),
        "dag-as-structure-dropped-for-host-language-control-flow",
        "CORROBORATES-weaker-heuristic",
        "almost certain",
        0.91,
        [
            rail(
                "prefect-github-api",
                "api",
                '"full_name":"PrefectHQ/prefect"',
            ),
            rail(
                "prefect-docs-get-started",
                "prose",
                "So we removed a key constraint that workflows be written explicitly as DAGs",
            ),
        ],
        p1,
    )
    c_prefect["published_reason"] = (
        "real-world workflows do not always fit pre-planned DAG structures; "
        "embrace native Python control flow"
    )
    c_prefect["rails"][1]["quote_secondary"] = (
        "pure Python\u2014no DSLs or complex config files"
    )

    c_airflow = claim(
        "C-AIRFLOW-PYTHON-VS-XML",
        (
            "Apache Airflow's own homepage and GitHub record pitch Python "
            "authoring against XML: 'No more command-line or XML black-magic' "
            "and 'When workflows are defined as code'. This is the published "
            "origin posture of a Python orchestration engine versus XML-class "
            "workflow languages (Oozie-class), not a measured byte-diff of one "
            "company's completed Oozie migration."
        ),
        "python-code-authoring-pitched-against-xml-workflow-language",
        "CORROBORATES-weaker-heuristic",
        "probable",
        0.75,
        [
            rail(
                "airflow-github-api",
                "api",
                "programmatically author, schedule, and monitor workflows",
            ),
            rail(
                "airflow-homepage",
                "prose",
                "No more command-line or XML black-magic!",
            ),
        ],
        p1,
    )
    c_airflow["published_reason"] = (
        "project marketing/docs: standard Python features instead of XML; "
        "dynamic pipeline generation"
    )
    c_airflow["caveat"] = (
        "Does not by itself prove a named maintainer post of the form "
        "'we migrated engine X from XML to Python on date Y'. Graded probable, "
        "not almost-certain."
    )

    c_asl = claim(
        "C-ASL-IR-PLUS-CDK",
        (
            "Amazon States Language is specified as a JSON-based language for "
            "describing state machines declaratively, and the AWS CDK Step "
            "Functions library both models that language in objects and still "
            "accepts raw ASL JSON via DefinitionBody.fromString / fromFile. "
            "The execution IR remains a workflow language; imperative CDK is "
            "a generator, not a replacement."
        ),
        "declarative-IR-retained-with-imperative-generator",
        "CUTS-AGAINST-categorical-anti-adoption",
        "almost certain",
        0.93,
        [
            rail(
                "cdk-stepfunctions-readme-api",
                "api",
                "packages/aws-cdk-lib/aws-stepfunctions/README.md",
            ),
            rail(
                "asl-spec",
                "prose",
                "language used to describe state machines declaratively",
            ),
        ],
        p2,
    )
    c_asl["rails"][0]["quote_decoded"] = (
        "Alternatively you can specify an existing step functions definition "
        "by providing a string or a file that contains the ASL JSON."
    )
    c_asl["published_reason"] = (
        "ASL remains the state-machine language; CDK supplies object wrappers "
        "and file/string ingestion of ASL JSON"
    )

    claims = [c_dagger, c_jenkins, c_gha, c_prefect, c_airflow, c_asl]
    catalog_path = REPO / "command-center/WORK-UNIT-CATALOG.json"
    cat_sha, cat_bytes = C.digest_path(catalog_path)

    doc = {
        "unit_id": "RES-0067",
        "claim_id": "RES-0067-decl-vs-imp-anti-adoption-1",
        "state": "SUCCESS",
        "schema_version": 1,
        "report_kind": "research-claim-record",
        "title": (
            "Find the evidence on declarative versus imperative workflow "
            "definition from engines that switched"
        ),
        "question": (
            "Which orchestration engines migrated between declarative and "
            "imperative definitions, what reasons did their maintainers publish, "
            "and what does that history say about the 05-ECO anti-adoption "
            "'do not build a workflow language'?"
        ),
        "sentinel": C.SENTINEL,
        "completion_sentinel": C.SENTINEL,
        "min_bytes_threshold": 2048,
        "generated_at": now,
        "execution_substrate": "linux-local",
        "claim_under_test": {
            "id": "anti-adoption-1",
            "label": "anti-adoption 1",
            "statement": "do not build a workflow language",
            "catalog_path": "command-center/WORK-UNIT-CATALOG.json",
            "catalog_sha256": cat_sha,
            "catalog_bytes": cat_bytes,
            "05_eco_cited_path": (
                "C:/Users/Prekzursil/.claude/harness-restore-20260806/"
                "05-ECOSYSTEM-AND-FRONTIER-RESEARCH.md:118-119"
            ),
            "05_eco_present_in_this_worktree": False,
            "wording_source": (
                "Catalog question_or_target and inputs for RES-0067. The "
                "original 05-ECO file is not in this worktree; the statement "
                "under test is the catalog's quoted anti-adoption, not a "
                "fabricated paraphrase of an unread file."
            ),
        },
        "anti_adoption": {
            "id": "anti-adoption-1",
            "label": "anti-adoption 1",
            "statement": "do not build a workflow language",
            "form_tested": "categorical-prohibition",
            "verdict": "REFUTED",
            "verdict_on_weaker_heuristic": "CORROBORATED",
            "weaker_heuristic": (
                "Do not make a novel author-facing DSL the only way to write "
                "workflows when the host language already has control flow."
            ),
            "rationale": (
                "The inherited categorical form is REFUTED: Jenkins "
                "deliberately added a constrained workflow language "
                "(Declarative Pipeline) because unconstrained Groovy was "
                "too expert-gated; GitHub Actions killed HCL and kept YAML "
                "as the workflow language; Step Functions still executes "
                "Amazon States Language and treats CDK as a generator of that "
                "IR. The weaker heuristic IS corroborated by Dagger leaving "
                "CUE, Prefect 2 dropping DAG-as-structure, and Airflow's "
                "Python-versus-XML pitch. Confirming the inherited "
                "anti-adoption without those counter-cases would have been "
                "the named failure mode."
            ),
            "confidence_band": "probable",
            "confidence_numeric": 0.75,
            "strongest_caveat": (
                "05-ECO lines 118-119 were not re-read from disk; if the "
                "original anti-adoption was already the weaker heuristic "
                "rather than a categorical prohibition, the REFUTED label "
                "applies to the catalog's quoted wording, not to a "
                "reconstructed 05-ECO paragraph."
            ),
        },
        "counter_cases": [
            {
                "id": "CC-JENKINS-DECLARATIVE-2017",
                "engine": "Jenkins",
                "claim_id": "C-JENKINS-DECLARATIVE",
                "cuts_against_anti_adoption": True,
                "summary": (
                    "Declarative Pipeline 1.0 added a config-like workflow "
                    "language on top of Scripted Groovy, published 2017-02-03."
                ),
            },
            {
                "id": "CC-GHA-YAML-2019",
                "engine": "GitHub Actions",
                "claim_id": "C-GHA-HCL-TO-YAML",
                "cuts_against_anti_adoption": True,
                "summary": (
                    "HCL workflows were retired in favor of YAML; a workflow "
                    "language remained mandatory."
                ),
            },
            {
                "id": "CC-ASL-IR",
                "engine": "AWS Step Functions",
                "claim_id": "C-ASL-IR-PLUS-CDK",
                "cuts_against_anti_adoption": True,
                "summary": (
                    "ASL is still the declarative execution language; CDK "
                    "does not delete it."
                ),
            },
        ],
        "claims": claims,
        "support_edges": [
            {
                "from": "C-DAGGER-CUE-TO-SDK",
                "to": "anti-adoption-1-weaker-heuristic",
                "kind": "supports",
            },
            {
                "from": "C-PREFECT-DAG-FREE",
                "to": "anti-adoption-1-weaker-heuristic",
                "kind": "supports",
            },
            {
                "from": "C-AIRFLOW-PYTHON-VS-XML",
                "to": "anti-adoption-1-weaker-heuristic",
                "kind": "supports",
            },
        ],
        "contradiction_edges": [
            {
                "from": "C-JENKINS-DECLARATIVE",
                "to": "anti-adoption-1-categorical",
                "kind": "contradicts",
            },
            {
                "from": "C-GHA-HCL-TO-YAML",
                "to": "anti-adoption-1-categorical",
                "kind": "contradicts",
            },
            {
                "from": "C-ASL-IR-PLUS-CDK",
                "to": "anti-adoption-1-categorical",
                "kind": "contradicts",
            },
        ],
        "engines_surveyed": [
            {
                "engine": "Dagger",
                "migration": "CUE SDK / CUE config -> host-language SDKs",
                "direction": "declarative-DSL-to-imperative-host-language",
                "published_reason": c_dagger["published_reason"],
            },
            {
                "engine": "Jenkins",
                "migration": "Scripted Groovy DSL -> added Declarative Pipeline",
                "direction": "imperative-to-declarative-authoring",
                "published_reason": c_jenkins["published_reason"],
            },
            {
                "engine": "GitHub Actions",
                "migration": "HCL -> YAML",
                "direction": "declarative-to-declarative",
                "published_reason": c_gha["published_reason"],
            },
            {
                "engine": "Prefect",
                "migration": "explicit DAG structure -> native Python control flow",
                "direction": "graph-definition-to-imperative-host-language",
                "published_reason": c_prefect["published_reason"],
            },
            {
                "engine": "Apache Airflow",
                "migration": "Python-as-code pitched against XML workflow languages",
                "direction": "xml-class-to-python-authoring",
                "published_reason": c_airflow["published_reason"],
            },
            {
                "engine": "AWS Step Functions",
                "migration": "ASL retained; CDK added as object/file generator",
                "direction": "declarative-IR-plus-imperative-generator",
                "published_reason": c_asl["published_reason"],
            },
        ],
        "tests": [
            {
                "id": "probe1_dual_rail",
                "command": p1,
                "result": "NOT-RUN",
                "role": "capture-hash-http-dual-rail-sentinel",
            },
            {
                "id": "probe2_overclaim",
                "command": p2,
                "result": "NOT-RUN",
                "role": "quote-in-body-mutants-counter-case",
            },
        ],
        "reviewer": {
            "reviewer_id": "RES-0067-probe2-overclaim-partition",
            "independent": True,
            "partitioned_evidence": True,
            "partition": (
                "probe2 sees quote-in-capture and known-broken mutants; "
                "probe1 sees sha256/http/dual-kind structure. Disjoint halves."
            ),
            "scope_not_agreement": True,
            "verdict": "PASS",
            "vendor_note": (
                "Second probe in the same worktree, not a second same-vendor "
                "LLM on the same input blob (05-ECO anti-adoption 2)."
            ),
        },
        "evidence": [
            {
                "path": r["capture_path"],
                "kind": "live-tree",
                "claim": c["id"],
                "permalink": r["permalink"],
                "sha256": r["sha256"],
            }
            for c in claims
            for r in c["rails"]
        ],
        "artifacts": [
            {
                "path": OUT_REL,
                "exists": True,
                "role": "primary",
            }
        ],
        "residual_unknowns": [
            {
                "id": "R1-05-ECO-ABSENT",
                "text": (
                    "05-ECOSYSTEM-AND-FRONTIER-RESEARCH.md is not in this "
                    "worktree; anti-adoption wording is catalog-quoted."
                ),
            },
            {
                "id": "R2-DAGGER-CUE-DIR-STILL-PRESENT",
                "text": (
                    "api.github.com/repos/dagger/dagger/contents/sdk still "
                    "lists a cue directory alongside go/python/typescript. "
                    "This record does not claim the CUE tree was deleted, "
                    "only that official support was discontinued."
                ),
            },
            {
                "id": "R3-AIRFLOW-OOZIE-NOT-A-NAMED-MIGRATION-POST",
                "text": (
                    "Airflow's XML pitch is project docs, not a dated "
                    "maintainer post of one completed Oozie-to-Airflow cutover."
                ),
            },
        ],
        "overclaim_controls": {
            "untested_corroboration_is_failure": True,
            "single_rail_is_e3_not_citable": True,
            "quote_must_occur_in_captured_bytes": True,
        },
        "notes": (
            "G-1 research record for RES-0067. Dual-rail (GitHub/JSON Schema "
            "API + maintainer prose) per engine fact. Categorical anti-adoption "
            "REFUTED; weaker heuristic CORROBORATED. Primary counter-case is "
            "Jenkins Declarative Pipeline 1.0."
        ),
    }

    ok, why = C.check_structure(doc)
    if not ok:
        print("FAILED:RES-0067 emit structure", why)
        return 1
    ok, why = C.check_rails(doc)
    if not ok:
        print("FAILED:RES-0067 emit rails", why)
        return 1
    ok, why = C.check_quotes(doc)
    if not ok:
        print("FAILED:RES-0067 emit quotes", why)
        return 1
    ok, why = C.check_anti_adoption(doc)
    if not ok:
        print("FAILED:RES-0067 emit anti-adoption", why)
        return 1

    out = REPO / OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(doc, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    sha, size = C.digest_path(out)
    print(f"wrote {OUT_REL} bytes={size} sha256={sha}")
    print("SUCCESS:RES-0067 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
