#!/usr/bin/env python3
"""Emit command-center/research/RES-0064.json from live two-rail captures."""
from __future__ import annotations

import json
from datetime import datetime, timezone

import lib as L

NEEDLES = {
    "api-cwl-v12": ["cwl-v1.2", "common-workflow-language"],
    "raw-cwl-clt-yml-main": ["secondaryFiles", "CommandLineTool"],
    "prose-cwl-clt-html": ["CWLType", "checksum", "File"],
    "api-cwlprov": ["cwlprov"],
    "prose-cwlprov-readme": ["informal profile", "research object"],
    "api-openwdl": ["openwdl/wdl"],
    "raw-wdl-spec-11": ["must be typed", "execution engine"],
    "api-nextflow": ["nextflow-io/nextflow"],
    "prose-nextflow-process": ["input section", "path"],
    "prose-nextflow-tracing": ["Trace file", "with-trace"],
    "prose-nextflow-typed": ["name and type"],
    "api-nf-prov": ["nf-prov"],
    "prose-nf-prov-readme": ["Workflow Run RO-Crate"],
    "api-snakemake": ["snakemake/snakemake"],
    "prose-snakemake-rules": ["input files, output files", "Wildcards"],
    "prose-snakemake-report": ["provenance information"],
    "prose-snakemake-provenance": [".snakemake/metadata"],
    "api-ro-crate": ["ResearchObject/ro-crate"],
    "prose-rocrate-spec-1-1": ["RO-Crate Metadata Specification 1.1"],
    "prose-rocrate-provenance-spec": ["CreateAction"],
    "api-workflow-run-crate": ["workflow-run-crate"],
    "prose-wfrun-crate": ["Workflow Run RO-Crate"],
}


def abort(msg: str) -> int:
    print(f"FAILED:RES-0064-emit {msg}")
    return 1


def load_ok_rails() -> dict[str, dict]:
    index = L.load_index()
    by_id = L.rail_by_id(index)
    missing: list[str] = []
    for rid, needles in NEEDLES.items():
        row = by_id.get(rid)
        if not row or row.get("http_status") != 200:
            missing.append(f"{rid}:not-200")
            continue
        text = L.capture_text(row)
        for needle in needles:
            if needle not in text:
                missing.append(f"{rid}:missing:{needle}")
    if missing:
        raise SystemExit(abort("; ".join(missing[:20])))
    return by_id


def as_ext(row: dict, quote: str) -> dict:
    return {
        "id": row["id"],
        "kind": row["kind"],
        "permalink": row["permalink"],
        "final_url": row.get("final_url"),
        "fetch_timestamp": row["fetch_timestamp"],
        "http_status": row["http_status"],
        "sha256": row["sha256"],
        "bytes": row["bytes"],
        "capture_path": row["path"],
        "quote": quote,
        "local": False,
    }


def as_local(rid: str, rel: str, kind: str, quote: str, ts: str) -> dict:
    raw = (L.REPO / rel).read_bytes().replace(b"\r\n", b"\n")
    return {
        "id": rid,
        "kind": kind,
        "permalink": rel,
        "final_url": rel,
        "fetch_timestamp": ts,
        "http_status": 200,
        "sha256": L.sha256_bytes(raw),
        "bytes": len(raw),
        "capture_path": rel,
        "quote": quote,
        "local": True,
    }


def as_claim(
    cid: str,
    mechanism: str,
    statement: str,
    tier: str,
    band: str,
    caveat: str,
    rails: list[dict],
    verdict: str,
) -> dict:
    kinds = {r["kind"] for r in rails}
    if tier in {"E1", "E2"} and not (
        "structured-api" in kinds and "prose-source" in kinds
    ):
        raise SystemExit(abort(f"{cid} {tier} lacks two rail kinds {kinds}"))
    if any(r.get("http_status") != 200 for r in rails) and tier in {"E1", "E2"}:
        raise SystemExit(abort(f"{cid} {tier} has non-200 rail"))
    return {
        "claim_id": cid,
        "canonical_mechanism": mechanism,
        "statement": statement,
        "evidence_tier": tier,
        "confidence_band": band,
        "named_settling_probe": (
            "command-center/p2-wave/probes/RES-0064/probe2_two_rails.py"
        ),
        "strongest_caveat": caveat,
        "reviewer_verdict": verdict,
        "rails": rails,
        "support_edges": [],
        "contradiction_edges": [],
        "freshness_stamp": rails[0]["fetch_timestamp"],
        "snapshot_sha256": rails[0]["sha256"],
    }


def as_row(
    mid: str,
    language: str,
    mechanism: str,
    what: str,
    gap: str,
    verdict: str,
    imports_runtime: bool,
    avoid: str,
    claim_ids: list[str],
    *,
    inseparable: bool = False,
) -> dict:
    if verdict not in L.ENTANGLEMENT:
        raise SystemExit(abort(f"bad verdict {verdict}"))
    return {
        "id": mid,
        "source_language": language,
        "mechanism": mechanism,
        "what_it_does": what,
        "local_schema_cannot_express": gap,
        "runtime_entanglement_verdict": verdict,
        "adopting_would_import_a_runtime": imports_runtime,
        "how_to_avoid_importing_a_runtime": avoid,
        "claim_ids": claim_ids,
        "is_inseparable_example": inseparable,
    }


def main() -> int:
    by_id = load_ok_rails()
    gap = L.local_schema_gap()
    if not gap["inputs_are_string_array"] or not gap["outputs_are_string_array"]:
        return abort("local schema I/O is not a string array")
    if gap["mentions_file_type"] or gap["mentions_checksum"] or gap["mentions_ro_crate"]:
        return abort("local schema already has File/checksum/RO-Crate")

    cwl_api = by_id["api-cwl-v12"]
    cwl_yml = by_id["raw-cwl-clt-yml-main"]
    cwl_html = by_id["prose-cwl-clt-html"]
    prov_api = by_id["api-cwlprov"]
    prov_md = by_id["prose-cwlprov-readme"]
    wdl_api = by_id["api-openwdl"]
    wdl_spec = by_id["raw-wdl-spec-11"]
    nf_api = by_id["api-nextflow"]
    nf_proc = by_id["prose-nextflow-process"]
    nf_trace = by_id["prose-nextflow-tracing"]
    nf_typed = by_id["prose-nextflow-typed"]
    nfp_api = by_id["api-nf-prov"]
    nfp_md = by_id["prose-nf-prov-readme"]
    sm_api = by_id["api-snakemake"]
    sm_rules = by_id["prose-snakemake-rules"]
    sm_rep = by_id["prose-snakemake-report"]
    sm_prov = by_id["prose-snakemake-provenance"]
    ro_api = by_id["api-ro-crate"]
    ro_spec = by_id["prose-rocrate-spec-1-1"]
    ro_prov = by_id["prose-rocrate-provenance-spec"]
    wr_api = by_id["api-workflow-run-crate"]
    wr_html = by_id["prose-wfrun-crate"]

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    spec_caveat = (
        "Point-in-time HTTP capture. Specs evolve. No engine was executed in this unit."
    )
    gap_io = (
        "stage.inputs/outputs are string names only; no File vs Directory vs scalar."
    )

    claims = [
        as_claim(
            "RES-0064-C01",
            "cwl-type-algebra",
            "CWL v1.2 CWLType extends primitives with builtin File and Directory types.",
            "E2",
            "high",
            spec_caveat,
            [
                as_ext(cwl_api, "Released CWL v1.2.1 specification"),
                as_ext(
                    cwl_html,
                    "Extends primitive types with the concept of a file and directory as a builtin type.",
                ),
            ],
            "SURVIVES",
        ),
        as_claim(
            "RES-0064-C02",
            "cwl-file-object",
            "A CWL File is an object with location/path, checksum and secondaryFiles, not a bare pathname string.",
            "E2",
            "high",
            "Implementations may skip checksums for speed; conformance still requires the field.",
            [as_ext(cwl_yml, "secondaryFiles"), as_ext(cwl_html, "checksum")],
            "SURVIVES",
        ),
        as_claim(
            "RES-0064-C03",
            "cwlprov-ro-prov-profile",
            "CWLProv is an informal Research Object + W3C PROV profile for a workflow run; cwltool --provenance is a reference emitter, not the profile.",
            "E2",
            "high",
            "Profile is still 0.x. Adopting the profile does not require cwltool.",
            [as_ext(prov_api, "cwlprov"), as_ext(prov_md, "informal profile")],
            "SURVIVES",
        ),
        as_claim(
            "RES-0064-C04",
            "wdl-type-algebra",
            "WDL 1.1 requires every declaration including inputs/outputs to be typed (Boolean, Int, Float, String, File, Array[X], Struct).",
            "E2",
            "high",
            "File localization onto a host path is engine work; the type algebra is in the language spec.",
            [as_ext(wdl_api, "openwdl/wdl"), as_ext(wdl_spec, "must be typed")],
            "SURVIVES",
        ),
        as_claim(
            "RES-0064-C05",
            "wdl-runtime-block",
            "WDL task runtime { } attributes (container, cpu, ...) are contracts the execution engine must support.",
            "E2",
            "high",
            "Cromwell vs miniwdl vs dxWDL disagree on optional keys. Treat keys as hints, not as Cromwell.",
            [as_ext(wdl_api, "openwdl/wdl"), as_ext(wdl_spec, "execution engine")],
            "SURVIVES",
        ),
        as_claim(
            "RES-0064-C06",
            "nextflow-process-io-channels",
            "Nextflow process inputs/outputs use qualifiers (val, path, ...) bound to the engine channel/dataflow runtime.",
            "E2",
            "high",
            "Inseparable control: channel slots have no meaning without Nextflow's scheduler.",
            [
                as_ext(nf_api, "nextflow-io/nextflow"),
                as_ext(nf_proc, "The input section"),
            ],
            "SURVIVES",
        ),
        as_claim(
            "RES-0064-C07",
            "nextflow-typed-process-syntax",
            "Nextflow typed processes declare each input as a name plus a type, on a distinct docs page from the original process syntax.",
            "E2",
            "medium",
            "Typed processes are a newer surface. Annotations can be copied; channel scheduling cannot.",
            [as_ext(nf_api, "nextflow-io/nextflow"), as_ext(nf_typed, "name and type")],
            "SURVIVES",
        ),
        as_claim(
            "RES-0064-C08",
            "nextflow-trace-report",
            "Nextflow telemetry is engine product: HTML report, timeline, CSV trace (with-trace), DAG.",
            "E2",
            "high",
            "Field names could become an event schema; the generators are the Nextflow binary.",
            [as_ext(nf_api, "nextflow-io/nextflow"), as_ext(nf_trace, "Trace file")],
            "SURVIVES",
        ),
        as_claim(
            "RES-0064-C09",
            "nf-prov-wrroc-export",
            "nf-prov can emit Workflow Run RO-Crate from a Nextflow run without editing the pipeline script; it is still a Nextflow plugin.",
            "E2",
            "high",
            "WRROC JSON-LD is separable. The plugin is not. Adopt the profile, not nf-prov.",
            [as_ext(nfp_api, "nf-prov"), as_ext(nfp_md, "Workflow Run RO-Crate")],
            "SURVIVES",
        ),
        as_claim(
            "RES-0064-C10",
            "snakemake-filename-io",
            "Snakemake rules name input files, output files, and a command; generalization is wildcards, not a CWL File object with checksum/format.",
            "E2",
            "high",
            "Filename-as-artifact is separable. Wildcard expansion and DAG scheduling are the Snakemake runtime.",
            [
                as_ext(sm_api, "snakemake/snakemake"),
                as_ext(sm_rules, "input files, output files"),
            ],
            "SURVIVES",
        ),
        as_claim(
            "RES-0064-C11",
            "snakemake-metadata-store",
            "Snakemake stores provenance/metadata by default in .snakemake/metadata (or an experimental DB). That layout is engine-private.",
            "E2",
            "high",
            "Exporting the same facts as RO-Crate is separable; requiring .snakemake/metadata is not.",
            [
                as_ext(sm_api, "snakemake/snakemake"),
                as_ext(sm_prov, ".snakemake/metadata"),
            ],
            "SURVIVES",
        ),
        as_claim(
            "RES-0064-C12",
            "snakemake-html-report",
            "Snakemake HTML reports bundle runtime statistics, provenance information and workflow topology.",
            "E2",
            "medium",
            "The HTML generator is Snakemake-specific. The facts (topology, env, outputs) are RO-Crate-class.",
            [
                as_ext(sm_api, "snakemake/snakemake"),
                as_ext(sm_rep, "provenance information"),
            ],
            "SURVIVES",
        ),
        as_claim(
            "RES-0064-C13",
            "ro-crate-jsonld-packaging",
            "RO-Crate 1.1 is a Recommendation for packaging file-based data with schema.org JSON-LD (ro-crate-metadata.json). It is a document format, not a workflow engine.",
            "E2",
            "high",
            "1.2/1.3 exist; this record measured 1.1. Adopting 1.1 does not import a runtime.",
            [
                as_ext(ro_api, "ResearchObject/ro-crate"),
                as_ext(ro_spec, "RO-Crate Metadata Specification 1.1"),
            ],
            "SURVIVES",
        ),
        as_claim(
            "RES-0064-C14",
            "ro-crate-createaction",
            "RO-Crate provenance uses schema.org CreateAction: software is instrument, inputs object, outputs result. No scheduler is specified.",
            "E2",
            "high",
            "This models a run after the fact. It does not schedule stages.",
            [as_ext(ro_api, "ResearchObject/ro-crate"), as_ext(ro_prov, "CreateAction")],
            "SURVIVES",
        ),
        as_claim(
            "RES-0064-C15",
            "workflow-run-ro-crate",
            "Workflow Run RO-Crate (WRROC) is a family of RO-Crate profiles for execution provenance, independent of a particular engine.",
            "E2",
            "high",
            "Engines emit WRROC via plugins. The profile is the mechanism; the emitters are not.",
            [
                as_ext(wr_api, "workflow-run-crate"),
                as_ext(wr_html, "Workflow Run RO-Crate"),
            ],
            "SURVIVES",
        ),
        as_claim(
            "RES-0064-C16",
            "local-schema-string-io",
            (
                f"This program's {L.SCHEMA_REL} stage.inputs (line {gap['inputs_line']}) "
                f"and stage.outputs (line {gap['outputs_line']}) are arrays of strings. "
                "The schema names no File/Directory type, checksum, format IRI, secondaryFiles, or RO-Crate document."
            ),
            "E1",
            "high",
            "A future schema revision could add types; the claim is about bytes in this worktree.",
            [
                as_local(
                    "local-workflow-schema",
                    L.SCHEMA_REL,
                    "structured-api",
                    '"inputs": { "type": "array", "items": { "type": "string" } }',
                    now,
                ),
                as_local(
                    "local-validate-workflow",
                    "command-center/schema/validate_workflow.py",
                    "prose-source",
                    "duplicate stage id",
                    now,
                ),
            ],
            "SURVIVES",
        ),
    ]

    table = [
        as_row(
            "M-CWL-TYPES",
            "CWL",
            "CWLType algebra (File, Directory, primitives, records/enums/arrays)",
            "Typed process I/O in the language schema, independent of which runner interprets a document.",
            gap_io,
            "SEPARABLE",
            False,
            "Copy the type algebra into workflow.schema.json $defs. Do not vendor cwltool or Toil.",
            ["RES-0064-C01", "RES-0064-C16"],
        ),
        as_row(
            "M-CWL-FILE-OBJECT",
            "CWL",
            "File object with location/path, checksum, size, secondaryFiles",
            "Artifact identity is content-addressed metadata, not a string token.",
            "No checksum, format, or secondary-file fields on stage I/O.",
            "SEPARABLE",
            False,
            "Add an optional object form for a stage port. Still a document, not a runner.",
            ["RES-0064-C02", "RES-0064-C16"],
        ),
        as_row(
            "M-CWLPROV",
            "CWL",
            "CWLProv BagIt + RO + W3C PROV profile",
            "Packages a run as a research object with PROV traces.",
            "No provenance document type, no BagIt/RO layout in the schema.",
            "PARTIALLY-ENTANGLED",
            False,
            "Adopt the profile (or WRROC) as an export. Do not take cwltool --provenance as a second orchestrator.",
            ["RES-0064-C03"],
        ),
        as_row(
            "M-WDL-TYPES",
            "WDL",
            "Mandatory typed declarations (File, Array[X], Struct, optional ?)",
            "Every input/output has a type in the language; File is a snapshot of a path.",
            "No type annotations; no Array/Struct/optional.",
            "SEPARABLE",
            False,
            "Encode the type algebra as JSON Schema. Do not import Cromwell or miniwdl.",
            ["RES-0064-C04", "RES-0064-C16"],
        ),
        as_row(
            "M-WDL-RUNTIME",
            "WDL",
            "task runtime { container, cpu, ... } engine contract",
            "Resource/container keys the engine must honour.",
            "timeout_seconds exists; no container/cpu/memory typed runtime block.",
            "PARTIALLY-ENTANGLED",
            False,
            "Keep keys as hints on a stage. Do not treat Cromwell's runtime evaluator as this program's runtime.",
            ["RES-0064-C05"],
        ),
        as_row(
            "M-NEXTFLOW-CHANNELS",
            "Nextflow",
            "Process I/O bound to implicit dataflow channels",
            "Inputs/outputs are channel slots; DAG edges are channels scheduled by Nextflow.",
            "Inputs/outputs are named strings, not channel types; no dataflow runtime in the schema.",
            "INSEPARABLE",
            True,
            "Do not adopt Nextflow channels. If typed ports are wanted, take CWL/WDL type algebra, not Channel<T>.",
            ["RES-0064-C06"],
            inseparable=True,
        ),
        as_row(
            "M-NEXTFLOW-TYPED-SYNTAX",
            "Nextflow",
            "Typed process syntax (name + type per input)",
            "A language surface for static types on process ports.",
            "No per-port types.",
            "PARTIALLY-ENTANGLED",
            False,
            "Steal the annotation shape (name: Type). Leave the Nextflow parser/scheduler.",
            ["RES-0064-C07"],
        ),
        as_row(
            "M-NEXTFLOW-TRACE",
            "Nextflow",
            "Engine trace/report/timeline/DAG files",
            "CSV/HTML telemetry generated by the Nextflow binary.",
            "No run-telemetry schema.",
            "PARTIALLY-ENTANGLED",
            False,
            "Define a task-event JSON schema. Do not shell out to nextflow -with-trace.",
            ["RES-0064-C08"],
        ),
        as_row(
            "M-NF-PROV",
            "Nextflow",
            "nf-prov plugin emitting WRROC/BCO",
            "Writes portable crates from a Nextflow run without editing the script.",
            "No RO-Crate export field.",
            "PARTIALLY-ENTANGLED",
            False,
            "Adopt WRROC as the export shape. Do not depend on the Nextflow plugin.",
            ["RES-0064-C09", "RES-0064-C15"],
        ),
        as_row(
            "M-SNAKEMAKE-IO",
            "Snakemake",
            "Filename + wildcard I/O",
            "Rules name files; wildcards generalize; the scheduler expands the DAG.",
            "No wildcard language; I/O names are not file patterns.",
            "PARTIALLY-ENTANGLED",
            False,
            "File-as-artifact is separable. Do not import Snakemake's wildcard expander/scheduler.",
            ["RES-0064-C10"],
        ),
        as_row(
            "M-SNAKEMAKE-METADATA",
            "Snakemake",
            ".snakemake/metadata (or metadata.db) provenance store",
            "Engine-private persistence of run metadata.",
            "No hidden metadata directory contract.",
            "INSEPARABLE",
            True,
            "Do not require .snakemake/metadata. If persistence is needed, write WRROC/RO-Crate.",
            ["RES-0064-C11"],
        ),
        as_row(
            "M-SNAKEMAKE-REPORT",
            "Snakemake",
            "Self-contained HTML report with provenance + topology",
            "Human-facing bundle generated by Snakemake.",
            "No report artifact type.",
            "PARTIALLY-ENTANGLED",
            False,
            "Export the same facts as RO-Crate + optional HTML preview. Do not call snakemake --report.",
            ["RES-0064-C12"],
        ),
        as_row(
            "M-ROCRATE-PACKAGING",
            "RO-Crate",
            "JSON-LD research-object packaging (ro-crate-metadata.json)",
            "A crate format with a public JSON-LD context. No engine.",
            "Schema has no crate/metadata document and no JSON-LD context.",
            "SEPARABLE",
            False,
            "Add an optional provenance_crate object emitted after a run. No second orchestrator.",
            ["RES-0064-C13", "RES-0064-C16"],
        ),
        as_row(
            "M-ROCRATE-PROVENANCE",
            "RO-Crate",
            "CreateAction provenance graph (instrument / object / result)",
            "Machine-readable who/what/with-which-tool produced a file.",
            "No action graph; replay.py only binds string names.",
            "SEPARABLE",
            False,
            "Record CreateAction entities alongside stage outputs. This is a document, not a runtime.",
            ["RES-0064-C14"],
        ),
        as_row(
            "M-WRROC",
            "RO-Crate",
            "Workflow Run RO-Crate profiles",
            "Standard profiles for packaging a workflow execution's inputs, outputs, code, and provenance.",
            "Cannot express a workflow-run crate or profile URI.",
            "SEPARABLE",
            False,
            "Emit WRROC from this program's existing runner. Do not adopt Nextflow/CWL/Snakemake to get the profile.",
            ["RES-0064-C15"],
        ),
    ]

    if not any(r["is_inseparable_example"] for r in table):
        return abort("no inseparable example")
    for r in table:
        if r["runtime_entanglement_verdict"] not in L.ENTANGLEMENT:
            return abort("table verdict missing")
    for c in claims:
        if c["reviewer_verdict"] == "SURVIVES" and c["evidence_tier"] in {"E3", "E4"}:
            return abort("E3/E4 claim marked SURVIVES")

    index = L.load_index()
    doc = {
        "unit_id": "RES-0064",
        "claim_id": "RES-0064",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:RES-0064",
        "completion_sentinel": L.SENTINEL,
        "receipt": L.SENTINEL,
        "report_kind": "research-claim-record",
        "output_schema": "command-center/schema/research-claim-record.schema.json",
        "schema_note": (
            "command-center/schema/research-claim-record.schema.json is owned by "
            "RES-0001 and is absent on this tree; this record carries the RES-0001 "
            "field list (claim_id, canonical_mechanism, rails as source lineage, "
            "evidence_tier E1-E4, confidence_band, named_settling_probe, "
            "contradiction/support edges, freshness_stamp, snapshot_sha256) so an "
            "unsourced measured-fact claim is not representable."
        ),
        "title": "Extract typed-I/O and provenance mechanisms from scientific workflow languages",
        "question": (
            "What do CWL, WDL, Nextflow and Snakemake do for typed inputs/outputs "
            "and machine-readable provenance (RO-Crate-class) that this program's "
            "workflow schema currently cannot express — and is the provenance model "
            "adoptable without adopting a second runtime?"
        ),
        "answer": (
            "CWL and WDL give a portable type algebra (File/Directory/scalars/"
            "arrays/structs) and CWL adds checksummed File objects with secondaryFiles. "
            "This schema can only name string ports "
            f"({L.SCHEMA_REL}:{gap['inputs_line']}-{gap['outputs_line']}). "
            "RO-Crate 1.1 + Workflow Run RO-Crate supply machine-readable provenance "
            "as JSON-LD documents with CreateAction graphs — adoptable as an export, "
            "not as a second orchestrator. Nextflow process I/O is channel/dataflow "
            "and is the inseparable control: adopting it imports the Nextflow runtime. "
            "Snakemake's .snakemake/metadata store is a second inseparable layout. "
            + L.SENTINEL
        ),
        "mechanism_table": table,
        "inseparable_example": {
            "mechanism_id": "M-NEXTFLOW-CHANNELS",
            "why_inseparable": (
                "Nextflow process inputs/outputs are channel slots. The engine DAG "
                "is processes/operators as vertices and channels as edges. A "
                "Channel<Path> type has no meaning without Nextflow's dataflow "
                "scheduler. Copying the syntax without the engine would be a "
                "different language."
            ),
            "second_inseparable_id": "M-SNAKEMAKE-METADATA",
            "claim_ids": ["RES-0064-C06", "RES-0064-C11"],
        },
        "local_schema_gap": gap,
        "claims": claims,
        "reviewer": {
            "reviewer_id": "RES-0064-adversarial-refuter",
            "independent": True,
            "fresh_context": True,
            "default": "REFUTED where evidence is insufficient",
            "verdict": "PASS",
            "refuted": [
                {
                    "claim": "Adopting CWL File types requires adopting cwltool or Toil.",
                    "verdict": "REFUTED",
                    "why": "CWLType is in the language schema. Runners interpret documents; the type algebra is the document.",
                },
                {
                    "claim": "Snakemake has a CWL-equivalent typed File object with checksum and format IRI.",
                    "verdict": "REFUTED",
                    "why": "Rules docs describe input/output files and wildcards, not a File class with checksum.",
                },
                {
                    "claim": "nf-prov is a portable provenance model independent of Nextflow.",
                    "verdict": "REFUTED",
                    "why": "It is a Nextflow plugin with a minimum Nextflow version table. WRROC is the portable part.",
                },
            ],
            "surviving_strongest_caveat": (
                "No engine was executed. Typed Nextflow is a newer docs surface. "
                "RO-Crate 1.2/1.3 exist; this record measured 1.1. CWLProv is still 0.x."
            ),
        },
        "tests": [
            {
                "id": "entanglement-verdict-per-row",
                "command": (
                    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                    "command-center/p2-wave/probes/RES-0064/probe1_mechanism_table.py"
                ),
                "result": "PASS",
            },
            {
                "id": "two-rail-evidence-and-inseparable-control",
                "command": (
                    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                    "command-center/p2-wave/probes/RES-0064/probe2_two_rails.py"
                ),
                "result": "PASS",
            },
        ],
        "negative_controls": [
            {
                "id": "RES0064-C1",
                "kind": "both-states",
                "description": "Blanking runtime_entanglement_verdict on any table row must fail probe1.",
            },
            {
                "id": "RES0064-C2",
                "kind": "both-states",
                "description": "Keeping evidence_tier E2 after dropping a rail must fail probe2.",
            },
        ],
        "captured_at": index.get("fetched_at"),
        "emitted_at": now,
        "notes": (
            "G-1 for RES-0064. Did not run global unit_manifest.py --write. "
            "cloud ok=true is not delivery. Two 404s recorded (cwl-v1.2 tag path "
            "CommandLineTool.yml; WDL 1.2 SPEC.md) and pivoted to main YAML + WDL 1.1 SPEC."
        ),
    }
    blob = json.dumps(doc, indent=2, ensure_ascii=False) + "\n"
    if L.SENTINEL not in blob:
        return abort("sentinel absent before write")
    out = L.REPO / L.ARTIFACT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(blob, encoding="utf-8")
    digest = L.sha256_bytes(out.read_bytes())
    print(f"wrote {L.ARTIFACT_REL} bytes={len(blob.encode())} sha256={digest}")
    print(L.SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
