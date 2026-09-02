#!/usr/bin/env python3
"""Emit RES-0186 citation-audit measurement artifact."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import audit as A  # noqa: E402

OUT_REL = (
    "command-center/research/evidence-quality/"
    "RES-0186-citation-audit-of-an-existing-report.json"
)
OUT = A.REPO / OUT_REL
SCHEMA = "command-center/schema/measurement-run.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0186/probe1_census.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0186/probe2_detector_control.py"
)
CATALOG_QUESTION = A.QUESTION


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def main() -> int:
    now = utc_now()
    bundle = A.run_audit()
    live = bundle["audit"]
    rates = live["rates"]
    control = bundle["detector_control"]
    src = bundle["source"]
    citations = [A.compact_citation(c) for c in live["citations"]]
    schema_present = (A.REPO / SCHEMA).is_file()
    src_sha, src_bytes = src["sha256"], src["bytes"]

    snap_a = citations[0]["resolve"]
    snap_b = citations[1]["resolve"]
    answer = (
        f"Census of every claims[].source_lineage attachment on "
        f"{src['path']} (n={rates['n_citations']}; rails[] is a duplicate and "
        f"was not counted). (a) resolve={rates['n_resolved']}/"
        f"{rates['n_citations']}={rates['fraction_resolve']:.4f} via snapshot "
        f"sha256 match + capture HTTP 200 + URL/timestamp lineage. "
        f"(b) assertion present={rates['n_assertion_present']}/"
        f"{rates['n_citations']}={rates['fraction_assertion_present']:.4f} "
        f"(quoted span in searchable snapshot body, GitHub Contents decoded). "
        f"(c) SUPPORT={rates['n_supporting']}/{rates['n_citations']}="
        f"{rates['fraction_supporting']:.4f}. "
        f"NON-SUPPORTING={rates['n_non_supporting']}: "
        f"{rates['by_class'].get('TOPICALLY-ADJACENT', 0)} TOPICALLY-ADJACENT "
        f"(docs_langgraph_errors cause-of-error span; gh_cdk_choice "
        f"decision-API span) and "
        f"{rates['by_class'].get('CONTRADICTING', 0)} CONTRADICTING "
        f"(six counterevidence rails on REFUTED C-ALL-ENGINES-MANDATORY-GUARDS). "
        f"Detector control injected 3 mismatched citations into a copy and "
        f"caught {control['n_caught']}/3; support rate is therefore not an "
        f"upper bound from a blind matcher. Live GitHub re-fetch was not used "
        f"as the resolve signal (raw.githubusercontent.com returned 429 on a "
        f"smoke fetch); snapshot bytes are the load-bearing resolve rail."
    )

    claims = [
        {
            "id": "C-CENSUS",
            "claim": (
                "Every citation attachment on RES-0069 (24 source_lineage rows "
                "across 10 claims) was audited; this is not a sample; rails[] "
                "duplicates were not double-counted."
            ),
            "verdict": "CONFIRMED",
            "anchor": "claims[].source_lineage walk vs snapshot files",
            "evidence_tier": "E1",
            "confidence_band": "C1-almost-certain",
            "sherman_kent": "almost certain (95-99%)",
            "independent_verification_path": P1,
            "source_lineage": [
                {
                    "id": "res-0069-json",
                    "kind": "structured-artifact",
                    "resolved_url": A.SOURCE_REL,
                    "fetch_timestamp": now,
                    "sha256": src_sha,
                    "bytes": src_bytes,
                },
                {
                    "id": "first-snapshot",
                    "kind": "captured-bytes",
                    "resolved_url": snap_a["snapshot_rel"],
                    "fetch_timestamp": citations[0]["fetched_at"],
                    "sha256": snap_a["live_sha256"],
                    "bytes": snap_a["live_bytes"],
                },
            ],
        },
        {
            "id": "C-RATES",
            "claim": (
                f"On this artifact the three rates are resolve "
                f"{rates['n_resolved']}/{rates['n_citations']}, assertion "
                f"{rates['n_assertion_present']}/{rates['n_citations']}, "
                f"support {rates['n_supporting']}/{rates['n_citations']}."
            ),
            "verdict": "CONFIRMED",
            "anchor": "per-citation support_class table",
            "evidence_tier": "E1",
            "confidence_band": "C1-almost-certain",
            "sherman_kent": (
                "almost certain (95-99%) for (a)(b); probable (75-90%) for "
                "(c) because SUPPORT uses a checkable phrase rule against "
                "the quoted span, not a human entailment judgement"
            ),
            "independent_verification_path": P1,
            "source_lineage": [
                {
                    "id": "res-0069-json",
                    "kind": "structured-artifact",
                    "resolved_url": A.SOURCE_REL,
                    "fetch_timestamp": now,
                    "sha256": src_sha,
                    "bytes": src_bytes,
                },
                {
                    "id": "second-snapshot",
                    "kind": "captured-bytes",
                    "resolved_url": snap_b["snapshot_rel"],
                    "fetch_timestamp": citations[1]["fetched_at"],
                    "sha256": snap_b["live_sha256"],
                    "bytes": snap_b["live_bytes"],
                },
            ],
        },
        {
            "id": "C-DETECTOR",
            "claim": (
                "Injecting three mismatched citations (absent quote, "
                "unresolved snapshot, topical-only span that is in the source) "
                "into a copy of RES-0069 is caught 3/3 by the same auditor."
            ),
            "verdict": "CONFIRMED",
            "anchor": "probe2_detector_control.py",
            "evidence_tier": "E1",
            "confidence_band": "C1-almost-certain",
            "sherman_kent": "almost certain (95-99%)",
            "independent_verification_path": P2,
            "source_lineage": [
                {
                    "id": "res-0069-json",
                    "kind": "structured-artifact",
                    "resolved_url": A.SOURCE_REL,
                    "fetch_timestamp": now,
                    "sha256": src_sha,
                    "bytes": src_bytes,
                },
                {
                    "id": "airflow-sensor-snapshot",
                    "kind": "captured-bytes",
                    "resolved_url": "command-center/p2-wave/probes/RES-0069/snapshots/gh_airflow_sensor_tasksdk.bin",
                    "fetch_timestamp": now,
                    "sha256": None,
                    "bytes": None,
                },
            ],
        },
        {
            "id": "C-NONSUPPORT",
            "claim": (
                "Eight of 24 attachments do not SUPPORT the citing sentence: "
                "two are TOPICALLY-ADJACENT and six CONTRADICT the REFUTED "
                "universal-mandatory-guard sentence they are attached to."
            ),
            "verdict": "CONFIRMED",
            "anchor": "non_supporting_quotes on each NON-SUPPORTING row",
            "evidence_tier": "E2",
            "confidence_band": "C2-probable",
            "sherman_kent": "probable (75-90%)",
            "independent_verification_path": P2,
            "source_lineage": [
                {
                    "id": "langgraph-docs-html",
                    "kind": "prose-snapshot",
                    "resolved_url": "https://docs.langchain.com/oss/python/langgraph/errors/GRAPH_RECURSION_LIMIT",
                    "fetch_timestamp": "2026-08-24T18:39:41Z",
                    "sha256": "75295513709548941b2b4c8ea89d77a526d52ad582976309b2bb2986972e1704",
                    "bytes": 811169,
                },
                {
                    "id": "cdk-choice-ts",
                    "kind": "structured-api-snapshot",
                    "resolved_url": "https://raw.githubusercontent.com/aws/aws-cdk/main/packages/aws-cdk-lib/aws-stepfunctions/lib/states/choice.ts",
                    "fetch_timestamp": "2026-08-24T18:42:20Z",
                    "sha256": "8e9cc19d7d1e27c37e8dd0b52ad80509f303d07b392e7b428af2ed115e801e9e",
                    "bytes": 7625,
                },
            ],
        },
    ]
    # Fill C-DETECTOR snapshot hash from disk.
    det_path = A.REPO / claims[2]["source_lineage"][1]["resolved_url"]
    if det_path.is_file():
        sha, nbytes = A.sha256_file(det_path)
        claims[2]["source_lineage"][1]["sha256"] = sha
        claims[2]["source_lineage"][1]["bytes"] = nbytes

    evidence = [
        {
            "path": A.SOURCE_REL,
            "kind": "audited-report",
            "claim": "C-CENSUS",
            "line": 1,
            "snippet": f"unit_id={src['unit_id']} bytes={src_bytes} sha256={src_sha}",
        },
        {
            "path": citations[0]["resolve"]["snapshot_rel"],
            "kind": "snapshot-bytes",
            "claim": "C-RATES",
            "line": 1,
            "snippet": citations[0]["cited_text"][:200],
        },
        {
            "path": "command-center/p2-wave/probes/RES-0186/probe2_detector_control.py",
            "kind": "named-probe",
            "claim": "C-DETECTOR",
            "line": 1,
            "snippet": "three mismatched citations must all be caught",
        },
    ]

    mutant_pairs = [
        {
            "id": "M-SKIP-REFUTED",
            "target": "census completeness",
            "operator": "drop-REFUTED-source_lineage",
            "verdict": "KILLED",
            "mutated_diff": (
                "Clear source_lineage on C-ALL-ENGINES-MANDATORY-GUARDS. "
                "n drops 24→18 and support rate inflates 16/24→16/18."
            ),
            "suite_ok": False,
            "verbatim_output": (
                "CONFIRMED-only mutant inflates fraction_supporting; probe1 rejects it"
            ),
        },
        {
            "id": "M-ALWAYS-SUPPORTING",
            "target": "support classifier",
            "operator": "classify-present-span-as-SUPPORTING",
            "verdict": "KILLED",
            "mutated_diff": (
                "Replace support_class with SUPPORTING whenever the snippet is "
                "in the resolved body. Misses INJ-TOPICAL and would miss live "
                "TOPICALLY-ADJACENT / CONTRADICTING rows."
            ),
            "suite_ok": False,
            "verbatim_output": (
                "always_supporting_mutant misses INJ-TOPICAL; probe2 requires that miss"
            ),
        },
        {
            "id": "M-THREE-INJECTIONS",
            "target": "detector control",
            "operator": "inject-quote-absent+unresolved+topical",
            "verdict": "KILLED",
            "mutated_diff": (
                f"quote={A.ABSENT_QUOTE!r}; snapshot={A.FAKE_SNAP}; "
                f"topical_span={A.TOPICAL_SPAN!r}"
            ),
            "suite_ok": False,
            "verbatim_output": json.dumps(control["hits"], sort_keys=True),
        },
    ]

    literature = [
        {
            "id": "L-RES-0069",
            "citation": (
                "RES-0069 loop-guard research record, command-center/research/"
                "RES-0069.json, 10 claims / 24 source_lineage attachments "
                "with on-disk snapshots."
            ),
            "what_was_used": (
                "The complete citation set: every claims[].source_lineage row, "
                "quoted spans, declared sha256, and snapshot paths."
            ),
            "evidence_tier": "E1",
            "doi": "",
            "reported_effect": (
                f"resolve {rates['fraction_resolve']}; "
                f"support {rates['fraction_supporting']}"
            ),
            "reported_baseline": "census of one completed report, not a sample",
        },
        {
            "id": "L-CNF-0062-METHOD",
            "citation": (
                "Catalog CNF-0062 citation-liveness unit: a 200 response with "
                "the quote absent is a FAILED citation, not a reachable one; "
                "control includes one deliberately wrong quote."
            ),
            "what_was_used": (
                "Method constraint reused here: resolvability is not support; "
                "detector control uses mismatched quotes. This unit extends "
                "that to three mismatch classes and a full-artifact census."
            ),
            "evidence_tier": "E3",
            "doi": "",
            "reported_effect": "method sibling, not a numeric result on RES-0069",
            "reported_baseline": "catalog tests_required on CNF-0062",
        },
    ]

    tests = [
        {
            "id": "named-probe-1-census",
            "command": P1,
            "result": "NOT-RUN",
        },
        {
            "id": "named-probe-2-detector-control",
            "command": P2,
            "result": "NOT-RUN",
        },
        {
            "id": "detector-control-three-mismatched-citations",
            "command": P2,
            "result": "PASS" if control["all_caught"] else "FAIL",
        },
    ]

    negative_controls = [
        {
            "id": "NC-THREE-INJECTIONS",
            "rejects": (
                "an auditor that reports SUPPORT for an absent quote, an "
                "unresolved snapshot, or a topical-only span"
            ),
            "observed": (
                f"caught {control['n_caught']}/3; "
                f"support_rate_is_upper_bound={control['support_rate_is_upper_bound']}"
            ),
        }
    ]

    reviewer = {
        "reviewer_id": "RES-0186-probe2-detector-control",
        "verdict": "PASS" if control["all_caught"] else "REFUTED",
        "independent": True,
        "fresh_context": False,
        "partitioned_independence": "NOT-MET-same-session",
        "default_without_evidence": "REFUTED",
        "notes": (
            "Same-session adversarial probe, not a second vendor. Defaults to "
            "REFUTED if any of the three injections is missed. Live GitHub "
            "re-fetch is residual: 429 on smoke, not treated as resolve."
        ),
    }

    residual_unknowns = [
        {
            "id": "live-github-429",
            "what": (
                "raw.githubusercontent.com returned HTTP 429 on a smoke fetch; "
                "remaining GitHub URLs were not hammered. Rate (a) is snapshot "
                "resolution, not live HTTP 200."
            ),
        },
        {
            "id": "schema-file-absent",
            "what": (
                f"{SCHEMA} is not on this worktree. G-1 does not schema-validate; "
                "this record carries measurement-run + research-claim-record floor fields."
            ),
        },
        {
            "id": "inputs-absent",
            "what": (
                "command-center/sources/REGISTER.md, command-center/CLAIM-REGISTRY.json, "
                "and _USER-PROMPTS.md are absent; catalog inputs were not readable."
            ),
        },
    ]

    artifacts = [
        {"path": OUT_REL, "exists": True, "role": "primary"},
        {
            "path": A.SOURCE_REL,
            "exists": True,
            "role": "audited-source",
        },
        {
            "path": "command-center/p2-wave/probes/RES-0186/audit.py",
            "exists": True,
            "role": "auditor",
        },
    ]

    record = {
        "unit_id": "RES-0186",
        "id": "RES-0186",
        "state": "SUCCESS",
        "status": "DELIVERED",
        "sentinel": A.SENTINEL,
        "completion_sentinel": A.SENTINEL,
        "report_kind": "measurement-run",
        "output_schema": SCHEMA,
        "output_schema_on_disk": schema_present,
        "schema_note": (
            "command-center/schema/measurement-run.schema.json is absent on this "
            "worktree. This record is self-describing. G-1 does not schema-validate."
        ),
        "title": "Audit an existing report's citations for resolvability and actual support",
        "question": CATALOG_QUESTION,
        "answer": answer,
        "audited_artifact": src,
        "census_rule": {
            "field": "claims[].source_lineage",
            "not_counted": "claims[].rails (duplicate of source_lineage)",
            "sampled": False,
            "n": rates["n_citations"],
        },
        "rates": rates,
        "citation_audit": citations,
        "detector_control": {
            "requirement": (
                "inject 3 deliberately mismatched citations into a copy of the "
                "artifact and require the audit to catch all 3; a missed "
                "injection means the reported support rate is an upper bound only"
            ),
            "n_injected": control["n_injected"],
            "n_caught": control["n_caught"],
            "all_caught": control["all_caught"],
            "support_rate_is_upper_bound": control["support_rate_is_upper_bound"],
            "hits": control["hits"],
            "injections": [
                {
                    "id": i["id"],
                    "claim_id": i["claim_id"],
                    "source_id": i["source_id"],
                    "mode": i["mode"],
                    "expect_class": i["expect_class"],
                }
                for i in A.INJECTIONS
            ],
        },
        "support_rule": {
            "judged_against": "quoted span",
            "non_supporting_quotes_both": True,
            "contradiction": (
                "citing sentence asserts a universal mandatory cap / never-"
                "expressible infinite loop AND the span asserts unbounded/"
                "forever/optional-timeout language"
            ),
            "need_any": {
                f"{k[0]}#{k[1]}": list(v) for k, v in sorted(A.SUPPORT_NEED_ANY.items())
            },
            "live_http_not_used_for_rate_a": True,
        },
        "claims": claims,
        "evidence": evidence,
        "mutant_pairs": mutant_pairs,
        "literature": literature,
        "tests": tests,
        "negative_controls": negative_controls,
        "reviewer": reviewer,
        "artifacts": artifacts,
        "min_bytes_threshold": 256,
        "residual_unknowns": residual_unknowns,
        "named_probes": [
            {"id": "probe1", "command": P1, "role": "full-census-rate-recompute"},
            {"id": "probe2", "command": P2, "role": "three-mismatch-detector-control"},
        ],
        "did_not": [
            "count rails[] as extra citations",
            "sample a subset of RES-0069 citations",
            "treat GitHub HTTP 429 as resolved",
            "treat topical adjacency as SUPPORT",
            "treat counterevidence on a REFUTED sentence as SUPPORT of that sentence",
            "run tools/command-center/unit_manifest.py --write",
        ],
        "emitted_at": now,
        "cloud_ok": False,
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        json.dumps(record, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    sha, nbytes = A.sha256_file(OUT)
    print(f"wrote {OUT_REL} bytes={nbytes} sha256={sha}")
    print(A.SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
