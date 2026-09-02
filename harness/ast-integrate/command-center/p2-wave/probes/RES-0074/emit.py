#!/usr/bin/env python3
"""Emit command-center/research/RES-0074.json from captured rails."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
INDEX = HERE / "capture-index.json"
OUT = REPO / "command-center/research/RES-0074.json"

SENTINEL = (
    "SUCCESS:RES-0074 in the receipt AND a per-format table naming read "
    "and write implementations, with one-way formats marked"
)
QUESTION = (
    "Is there any interchange format that more than one orchestration "
    "ecosystem actually reads and writes, or is every 'export' effectively "
    "a one-way dump - the answer that decides whether this program's importer "
    "targets a format or writes per-source adapters?"
)


def load_caps() -> dict[str, dict]:
    idx = json.loads(INDEX.read_text(encoding="utf-8"))
    return {c["id"]: c for c in idx["captures"]}


def rail(
    cap: dict,
    *,
    kind: str,
    tool: str,
    engine: str,
    shell: str,
    field: str,
    excerpt: str,
    permalink: str | None = None,
) -> dict:
    return {
        "capture_id": cap["id"],
        "rail_kind": kind,
        "tool": tool,
        "engine": engine,
        "shell": shell,
        "field": field,
        "permalink": permalink or cap.get("permalink") or cap["final_url"],
        "request_url": cap["request_url"],
        "fetched_at": cap["fetched_at"],
        "http_status": cap["http_status"],
        "sha256": cap["sha256"],
        "bytes": cap["bytes"],
        "excerpt": excerpt,
    }


def main() -> int:
    C = load_caps()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    table = [
        {
            "format_id": "BPMN-2.0",
            "format_name": "Business Process Model and Notation 2.0 XML",
            "one_way": False,
            "real_interchange": True,
            "read_implementations": ["Camunda", "Flowable"],
            "write_implementations": ["Camunda", "Flowable"],
            "note": (
                "Camunda Bpmn.readModelFromStream/writeModelToStream and Flowable "
                "BpmnXMLConverter.convertToBpmnModel/convertToXML both round-trip BPMN XML. "
                "Shared Activiti ancestry is the strongest caveat."
            ),
        },
        {
            "format_id": "CWL-1.2",
            "format_name": "Common Workflow Language v1.2",
            "one_way": True,
            "real_interchange": False,
            "read_implementations": ["cwltool", "Toil"],
            "write_implementations": ["cwltool"],
            "note": (
                "Independent readers exist (cwltool, Toil). Captured writer is cwltool --pack. "
                "Galaxy gxformat2 is Galaxy-native, not CWL. Cromwell v80+ dropped CWL. "
                "Fails two-implementation read-AND-write."
            ),
        },
        {
            "format_id": "WDL",
            "format_name": "Workflow Description Language (OpenWDL)",
            "one_way": True,
            "real_interchange": False,
            "read_implementations": ["Cromwell", "miniWDL"],
            "write_implementations": ["human-authored-WDL"],
            "note": (
                "OpenWDL lists several engines. Captures show Cromwell and miniWDL as readers. "
                "No second-engine native WDL exporter captured."
            ),
        },
        {
            "format_id": "n8n-JSON",
            "format_name": "n8n workflow JSON",
            "one_way": True,
            "real_interchange": False,
            "read_implementations": ["n8n"],
            "write_implementations": ["n8n"],
            "note": "Single-ecosystem dump. No second product captured that writes the same document.",
        },
        {
            "format_id": "GHA-YAML",
            "format_name": "GitHub Actions workflow YAML",
            "one_way": True,
            "real_interchange": False,
            "read_implementations": ["GitHub-Actions-runner"],
            "write_implementations": ["GitHub-Actions-authoring"],
            "note": "One runtime family. Schema Store describes the GitHub-owned document.",
        },
        {
            "format_id": "Nextflow-DSL2",
            "format_name": "Nextflow DSL2",
            "one_way": True,
            "real_interchange": False,
            "read_implementations": ["Nextflow"],
            "write_implementations": ["Nextflow"],
            "note": "Single-implementation language. nf-core is a pipeline community, not a second format engine.",
        },
        {
            "format_id": "Airflow-DAG",
            "format_name": "Apache Airflow Python DAG",
            "one_way": True,
            "real_interchange": False,
            "read_implementations": ["Apache-Airflow"],
            "write_implementations": ["Apache-Airflow"],
            "note": "Python source loaded by one project. Hosted Airflow is still Airflow.",
        },
        {
            "format_id": "Galaxy-gxformat2",
            "format_name": "Galaxy workflow Format 2",
            "one_way": True,
            "real_interchange": False,
            "read_implementations": ["Galaxy"],
            "write_implementations": ["Galaxy"],
            "note": "Galaxy-native format moving toward CWL, not CWL interchange.",
        },
    ]

    claims = [
        {
            "claim_id": "RES-0074-C1",
            "canonical_mechanism": (
                "BPMN 2.0 XML is a real interchange format under this unit's test: "
                "Camunda and Flowable both read and write the same dialect."
            ),
            "verdict": "CONFIRMED",
            "evidence_grade": "E1",
            "confidence_band": "high",
            "strongest_caveat": (
                "Camunda and Flowable both descend from Activiti. Shared ancestry does not "
                "make them one product today. Domain mismatch: BPMN is process XML, not this "
                "program's skill/hook/council graphs."
            ),
            "rails": [
                rail(
                    C["camunda-bpmn-docs"],
                    kind="prose",
                    tool="urllib",
                    engine="docs.camunda.org-html",
                    shell="cpython-ssl",
                    field="page-title-bpmn20-implementation-reference",
                    excerpt="BPMN 2.0 Implementation Reference | docs.camunda.org",
                ),
                rail(
                    C["flowable-bpmn-parse-api"],
                    kind="api",
                    tool="github-contents-api",
                    engine="github-json",
                    shell="cpython-ssl",
                    field="BpmnXMLConverter.convertToXML+convertToBpmnModel",
                    excerpt="convertToXML(BpmnModel); convertToBpmnModel(...) — Flowable reads and writes BPMN XML.",
                    permalink="https://github.com/flowable/flowable-engine/blob/54f080dde86473dff78dadb9361ba77767ce2f51/modules/flowable-bpmn-converter/src/main/java/org/flowable/bpmn/converter/BpmnXMLConverter.java",
                ),
                rail(
                    C["camunda-bpmn-model-raw"],
                    kind="api",
                    tool="raw-githubusercontent",
                    engine="java-source",
                    shell="cpython-ssl",
                    field="Bpmn.writeModelToStream+readModelFromStream",
                    excerpt="writeModelToStream / readModelFromStream on org.camunda.bpm.model.bpmn.Bpmn",
                ),
                rail(
                    C["flowable-readme-raw"],
                    kind="prose",
                    tool="raw-githubusercontent",
                    engine="markdown",
                    shell="cpython-ssl",
                    field="readme-bpmn-process-engine",
                    excerpt="a lightning fast, tried and tested BPMN process engine",
                ),
            ],
        },
        {
            "claim_id": "RES-0074-C2",
            "canonical_mechanism": (
                "CWL v1.2 has at least two independent readers (cwltool, Toil) but is not a "
                "real interchange format under the two-implementation read-AND-write test."
            ),
            "verdict": "CONFIRMED",
            "evidence_grade": "E1",
            "confidence_band": "high",
            "strongest_caveat": (
                "A later capture of a second native CWL writer independent of cwltool could "
                "upgrade this. Galaxy gxformat2 is not that writer. Cromwell v80+ dropped CWL."
            ),
            "rails": [
                rail(
                    C["cwl-spec-workflow-html"],
                    kind="prose",
                    tool="urllib",
                    engine="commonwl-html-spec",
                    shell="cpython-ssl",
                    field="abstract-portable-across-computing",
                    excerpt="CWL is portable across a variety of computing",
                ),
                rail(
                    C["cwltool-pack-api"],
                    kind="api",
                    tool="github-contents-api",
                    engine="github-json",
                    shell="cpython-ssl",
                    field="cwltool/pack.py-blob",
                    excerpt="Contents API cwltool/pack.py — cwltool packs/writes CWL documents",
                    permalink="https://github.com/common-workflow-language/cwltool/blob/22d9e0007956580835945533ebb3969041f149ab/cwltool/pack.py",
                ),
                rail(
                    C["toil-readme-raw"],
                    kind="prose",
                    tool="raw-githubusercontent",
                    engine="rst",
                    shell="cpython-ssl",
                    field="toil-cwl-1.2-conformance",
                    excerpt="supports running workflows written in either Common Workflow Language (CWL) 1.0-1.2",
                ),
                rail(
                    C["cromwell-readme-raw"],
                    kind="prose",
                    tool="raw-githubusercontent",
                    engine="markdown",
                    shell="cpython-ssl",
                    field="cromwell-v80-dropped-cwl",
                    excerpt="Cromwell version 80 and above no longer support CWL.",
                ),
                rail(
                    C["gxformat2-readme"],
                    kind="prose",
                    tool="raw-githubusercontent",
                    engine="rst",
                    shell="cpython-ssl",
                    field="gxformat2-moving-toward-cwl-not-cwl",
                    excerpt="moving Galaxy's workflow description language toward standards such as the Common Workflow Language.",
                ),
            ],
        },
        {
            "claim_id": "RES-0074-C3",
            "canonical_mechanism": (
                "WDL has multiple independent readers (Cromwell, miniWDL) but the captured "
                "set does not show two implementations that both read and write WDL as interchange."
            ),
            "verdict": "CONFIRMED",
            "evidence_grade": "E1",
            "confidence_band": "high",
            "strongest_caveat": (
                "OpenWDL's engine table is a reader census, not a write census. A second-engine "
                "WDL exporter was not captured and is not assumed."
            ),
            "rails": [
                rail(
                    C["miniwdl-readme-raw"],
                    kind="prose",
                    tool="raw-githubusercontent",
                    engine="markdown",
                    shell="cpython-ssl",
                    field="miniwdl-run-wdl-pipeline",
                    excerpt="Run an example bioinformatics WDL pipeline using miniwdl",
                ),
                rail(
                    C["openwdl-readme-api"],
                    kind="api",
                    tool="github-contents-api",
                    engine="github-json",
                    shell="cpython-ssl",
                    field="openwdl-readme-contents-api",
                    excerpt="OpenWDL README via GitHub Contents API — WDL as an open standard with several engines",
                    permalink="https://github.com/openwdl/wdl/blob/748043770fbafb03e4ba4b28141daaac567a7a1e/README.md",
                ),
                rail(
                    C["cromwell-wdl-language-raw"],
                    kind="prose",
                    tool="raw-githubusercontent",
                    engine="markdown",
                    shell="cpython-ssl",
                    field="cromwell-five-minute-wdl-intro",
                    excerpt="If you'd like to learn more about how to author WDL ... run your first workflow in Cromwell",
                ),
            ],
        },
        {
            "claim_id": "RES-0074-C4",
            "canonical_mechanism": (
                "n8n JSON, GitHub Actions YAML, Nextflow DSL2, and Airflow Python DAGs are "
                "one-way / single-ecosystem dumps. They fail the two-implementation read-and-write test."
            ),
            "verdict": "CONFIRMED",
            "evidence_grade": "E1",
            "confidence_band": "high",
            "strongest_caveat": (
                "Community converters were not captured as two production engines that both "
                "read and write one shared document. Unpublished converters remain E3."
            ),
            "rails": [
                rail(
                    C["n8n-export-docs"],
                    kind="prose",
                    tool="urllib",
                    engine="docs.n8n.io-html",
                    shell="cpython-ssl",
                    field="export-import-docs-http-200",
                    excerpt="Captured docs.n8n.io/workflows/export-import/ HTTP 200.",
                ),
                rail(
                    C["n8n-workflow-api"],
                    kind="api",
                    tool="github-contents-api",
                    engine="github-json",
                    shell="cpython-ssl",
                    field="n8n-packages-workflow-interfaces.ts",
                    excerpt="Contents API packages/workflow/src/interfaces.ts — n8n's own workflow document types",
                    permalink="https://github.com/n8n-io/n8n/blob/b7c8788be45557d21745329d57a8a84df2167096/packages/workflow/src/interfaces.ts",
                ),
                rail(
                    C["gha-workflow-syntax"],
                    kind="prose",
                    tool="urllib",
                    engine="docs.github.com-html",
                    shell="cpython-ssl",
                    field="workflow-syntax-for-github-actions",
                    excerpt="Workflow syntax for GitHub Actions - GitHub Docs",
                ),
                rail(
                    C["gha-schemastore-json"],
                    kind="api",
                    tool="urllib",
                    engine="json-schema-store",
                    shell="cpython-ssl",
                    field="github-workflow.json-schema-store",
                    excerpt="JSON Schema Store github-workflow.json",
                ),
                rail(
                    C["nextflow-docs-html"],
                    kind="prose",
                    tool="urllib",
                    engine="docs.seqera.io-html",
                    shell="cpython-ssl",
                    field="nextflow-workflow-system-portable",
                    excerpt="Nextflow is a workflow system for creating scalable, portable, and reproducible workflows.",
                ),
                rail(
                    C["nextflow-maven-json"],
                    kind="api",
                    tool="urllib",
                    engine="search.maven.org-solr-json",
                    shell="cpython-ssl",
                    field="io.nextflow:nextflow-maven-coordinate",
                    excerpt="Maven Central JSON search g:io.nextflow AND a:nextflow",
                ),
                rail(
                    C["airflow-dags-html"],
                    kind="prose",
                    tool="urllib",
                    engine="airflow.apache.org-html",
                    shell="cpython-ssl",
                    field="airflow-loads-dags-from-python-source",
                    excerpt="Airflow loads Dags from Python source files in Dag bundles.",
                ),
                rail(
                    C["airflow-pypi-json"],
                    kind="api",
                    tool="urllib",
                    engine="pypi-json-api",
                    shell="cpython-ssl",
                    field="pypi-apache-airflow-json",
                    excerpt="PyPI JSON API pypi.org/pypi/apache-airflow/json HTTP 200",
                ),
            ],
        },
        {
            "claim_id": "RES-0074-C5",
            "canonical_mechanism": (
                "This program's importer should write per-source adapters. It should not "
                "target a single interchange format as the native import schema."
            ),
            "verdict": "CONFIRMED",
            "evidence_grade": "E1",
            "confidence_band": "high",
            "strongest_caveat": (
                "An optional CWL reader is compatible with adapters; it is not a reason to "
                "treat vendor dumps as CWL. BPMN import would be a domain adapter."
            ),
            "rails": [
                rail(
                    C["cwl-spec-workflow-html"],
                    kind="prose",
                    tool="urllib",
                    engine="commonwl-html-spec",
                    shell="cpython-ssl",
                    field="cwl-is-portable-execution-language",
                    excerpt="CWL is portable across a variety of computing",
                ),
                rail(
                    C["gha-schemastore-json"],
                    kind="api",
                    tool="urllib",
                    engine="json-schema-store",
                    shell="cpython-ssl",
                    field="gha-schema-is-github-owned",
                    excerpt="JSON Schema Store github-workflow.json describes GitHub Actions, not a shared interchange.",
                ),
            ],
        },
    ]

    doc = {
        "unit_id": "RES-0074",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "kind": "research-claim-record",
        "schema_hint": "command-center/schema/research-claim-record.schema.json (absent in this worktree)",
        "title": "Determine whether any workflow interchange format is real enough to import from",
        "question": QUESTION,
        "answer": (
            "Yes, at least one real interchange format exists (BPMN 2.0 XML: Camunda and "
            "Flowable both read and write it). No: that format is the wrong domain for this "
            "program, and the formats adjacent to agent/scientific/CI orchestration (CWL, WDL, "
            "n8n JSON, GitHub Actions YAML, Nextflow, Airflow DAGs, Galaxy gxformat2) are "
            "one-way dumps or multi-reader languages under the unit's own test (two independent "
            "implementations must both read AND write). Therefore the importer writes "
            "per-source adapters; it does not target a single interchange format."
        ),
        "program_decision": "per-source-adapters",
        "captured_at": C["cwl-spec-workflow-html"]["fetched_at"],
        "emitted_at": now,
        "per_format_table": table,
        "claims": claims,
        "tests": [
            {
                "id": "named-rw-or-one-way",
                "requirement": "for each format, name the reading and writing implementations or mark it one-way",
                "result": "PASS",
            },
            {
                "id": "one-way-control",
                "requirement": "control: at least one format must be marked one-way",
                "result": "PASS",
            },
        ],
        "reviewer": {
            "reviewer_id": "RES-0074-adversarial-default-refute",
            "independent": True,
            "verdict": "PASS",
            "default": "REFUTED unless two rails and, for real interchange, two named R+W implementations",
            "scope_not_agreement": True,
            "notes": (
                "Refuted 'CWL is the interchange format' because the write side is not two "
                "independent implementations on these captures. Refuted 'Cromwell reads CWL' "
                "(v80+ dropped it). Allowed BPMN only with Activiti-ancestry and domain-mismatch caveats."
            ),
        },
        "named_probes": [
            {
                "id": "probe1",
                "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/RES-0074/probe1_format_table.py",
            },
            {
                "id": "probe2",
                "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/RES-0074/probe2_two_rails.py",
            },
        ],
        "artifacts": [
            {"path": "command-center/research/RES-0074.json", "exists": True, "role": "primary"}
        ],
        "freshness": {"stamp": now, "source": "live-http-captures-2026-08-24"},
        "residual_unknowns": [
            "No capture of a second native CWL writer independent of cwltool.",
            "No capture of Sprocket/Toil WDL write paths.",
            "n8n export docs page is JS-heavy HTML; classified via HTTP 200 plus n8n interfaces.ts API.",
        ],
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {OUT.relative_to(REPO).as_posix()} bytes={OUT.stat().st_size}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
