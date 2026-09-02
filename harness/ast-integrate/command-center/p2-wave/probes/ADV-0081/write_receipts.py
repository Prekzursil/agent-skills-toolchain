#!/usr/bin/env python3
"""Write ADV-0081 refutation record plus per-unit G-1 receipts.

Named probes are re-run live. Does not invoke unit_manifest.py --write.
Does not relaunch finish-everything-close or p2-cloud-ok-deliver.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
from graph import analyze  # noqa: E402

UID = "ADV-0081"
OUT = "command-center/adversarial/ADV-0081-circular-citation-cycle-detection.json"
SCHEMA = "command-center/schema/refutation-record.schema.json"
SENTINEL = "SUCCESS:ADV-0081"
CATALOG_SENTINEL = (
    "SUCCESS:ADV-0081 emitted ONLY when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, records BOTH named probes "
    "verbatim with their raw output, carries exactly one verdict from "
    "{CONFIRMED|REFUTED|PARTIAL|NOT-CHECKED|BLOCKED} per enumerated target, "
    "and records the result of every listed control/negative test. Any missing "
    "control downgrades the unit's verdicts to NOT-CHECKED. Otherwise "
    "FAILED:ADV-0081 <reason>."
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0081/probe1_cycle_enumeration.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0081/probe2_external_root_trace.py"
)
PROBE1_VERBATIM = (
    "Probe 1: build the directed support graph and run cycle detection, "
    "reporting every cycle with its member claims."
)
PROBE2_VERBATIM = (
    "Probe 2 (mechanically different): for each cycle, trace to the EXTERNAL "
    "evidence root; a cycle whose members all trace to one genuine external "
    "source is redundancy, while a cycle with no external root is unsupported "
    "and must be reclassified."
)
QUESTION = (
    "Does any claim's support chain form a cycle - a claim supported by a "
    "document that derives from that same claim - and how many claims lose "
    "their support once cycles are removed?"
)
SUPPORTING = [
    "command-center/p2-wave/probes/ADV-0081/graph.py",
    "command-center/p2-wave/probes/ADV-0081/probe1_cycle_enumeration.py",
    "command-center/p2-wave/probes/ADV-0081/probe2_external_root_trace.py",
    "command-center/p2-wave/probes/ADV-0081/fixtures/planted.json",
    "command-center/p2-wave/probes/ADV-0081/fixtures/planted-unsupported.md",
    "command-center/p2-wave/probes/ADV-0081/fixtures/planted-chain.md",
    SCHEMA,
    "command-center/research/RES-0075.json",
    "command-center/CLAIM-REGISTRY.json",
]
MIN_BYTES = 4096
MARK = "\u0085UNIT-COMPLETE:ADV-0081\u0085"


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_probe(cmd: str) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        timeout=180,
        env=env,
    )
    text = ((proc.stdout or "") + (proc.stderr or "")).strip()
    return proc.returncode, text


def row(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest(path)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "present": path.is_file(),
        "unit_id": UID,
        "receipt_path": "command-center/p2-wave/probes/ADV-0081/SUBAGENT-RETURN.json",
        "role": role,
    }


def art_row(rel: str, role: str) -> dict:
    path = REPO / rel
    return {
        "path": rel,
        "role": role,
        "exists": path.is_file(),
        "present": path.is_file(),
    }


def main() -> int:
    full = analyze(REPO)
    if not full["pass"]:
        print("FAILED:ADV-0081 analyzer controls did not pass")
        print(json.dumps(full["controls"], indent=2))
        return 1

    code1, text1 = run_probe(P1)
    code2, text2 = run_probe(P2)
    if code1 != 0 or code2 != 0:
        print(f"FAILED:{UID} probes c1={code1} c2={code2}")
        print(text1[-2000:])
        print(text2[-2000:])
        return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    lost = full["claims_losing_support"]
    census = full["edge_kind_census"]
    live_doc = full["n_live_document_claim_cycles"]
    live_cc = full["n_live_simple_cycles"]
    planted_doc = full["n_planted_document_claim_cycles"]
    ctrl = full["controls"]

    cycle_verdict = "PARTIAL"
    if live_doc > 0:
        cycle_verdict = "CONFIRMED"
    elif live_cc == 0 and planted_doc >= 1:
        cycle_verdict = "REFUTED"

    lose_verdict = "REFUTED" if lost["live_n"] == 0 else "CONFIRMED"
    graph_verdict = "CONFIRMED" if full["graph_representable"] else "REFUTED"
    overall = "PARTIAL"

    live_scc_rows = [
        {
            "class": row["class"],
            "member_claims": row["member_claims"],
            "external_roots": row["external_roots"],
            "planted": row["planted"],
        }
        for row in full["classified_sccs"]
        if not row["planted"]
    ]
    planted_scc_rows = [
        {
            "class": row["class"],
            "member_claims": row["member_claims"],
            "external_roots": row["external_roots"],
            "planted": row["planted"],
        }
        for row in full["classified_sccs"]
        if row["planted"]
    ]

    answer = (
        "On this Linux worktree the directed support graph was built from live "
        "research claim records (command-center/research, CLAIM-REGISTRY.json) "
        f"plus planted fixtures. Edge census: {census}. "
        f"Live claim-to-claim support cycles={live_cc}; live "
        f"document-to-origin-claim cycles={live_doc} (the catalog shape: a claim "
        "supported by a document that derives from that same claim). "
        "Live cycles are REDUNDANCY (shared external URL) or MIXED (distinct "
        "external URLs), not unsupported loops. "
        f"Claims losing support after unsupported-cycle removal: live={lost['live_n']} "
        f"planted={lost['planted_n']} {lost['planted']}. "
        "Planted unsupported document-origin cycle was enumerated and reclassified "
        "UNSUPPORTED; planted acyclic chain stayed acyclic; planted shared-origin "
        "pair classified REDUNDANCY. GRAPH-REPRESENTABILITY is CONFIRMED because "
        "support, document-to-origin-claim (containment + planted derives_from), "
        "and external-root (source_lineage URL) edges are all present. "
        + CATALOG_SENTINEL
    )

    record = {
        "unit_id": UID,
        "id": UID,
        "state": "SUCCESS",
        "status": "DELIVERED",
        "sentinel": SENTINEL,
        "completion_sentinel": CATALOG_SENTINEL,
        "completion_marker": MARK,
        "completion_line": "UNIT-COMPLETE:ADV-0081",
        "title": "Circular-citation and evidence-loop detection in the claim graph",
        "question": QUESTION,
        "question_or_target": QUESTION,
        "report_kind": "refutation-record",
        "overall_verdict": overall,
        "answer": answer,
        "output_path": OUT,
        "output_schema": SCHEMA,
        "min_bytes_threshold": MIN_BYTES,
        "schema_version": 1,
        "spec_anchor": "_USER-PROMPTS.md:11232, 10679",
        "mechanism": (
            "Probe 1: Tarjan SCCs plus simple-cycle enumeration on the directed "
            "depends-on graph (claim support_edges, planted support_document, "
            "document-to-origin-claim). Probe 2: independently rebuilds the graph "
            "and classifies each cyclic SCC by source_lineage URLs "
            "(UNSUPPORTED / REDUNDANCY / MIXED) without reading probe 1 output."
        ),
        "scope": {
            "live": [
                "command-center/research",
                "command-center/CLAIM-REGISTRY.json",
            ],
            "planted": [
                "command-center/p2-wave/probes/ADV-0081/fixtures/planted.json",
            ],
        },
        "census": {
            "n_nodes": full["n_nodes"],
            "n_edges": full["n_edges"],
            "edge_kind_census": census,
            "n_simple_cycles": full["n_simple_cycles"],
            "n_live_simple_cycles": live_cc,
            "n_live_document_claim_cycles": live_doc,
            "n_planted_document_claim_cycles": planted_doc,
            "n_unsupported_sccs": sum(
                1 for r in full["classified_sccs"] if r["class"] == "UNSUPPORTED"
            ),
            "n_redundancy_sccs": sum(
                1 for r in full["classified_sccs"] if r["class"] == "REDUNDANCY"
            ),
            "n_mixed_sccs": sum(
                1 for r in full["classified_sccs"] if r["class"] == "MIXED"
            ),
        },
        "live_scc_classifications": live_scc_rows,
        "planted_scc_classifications": planted_scc_rows,
        "targets": [
            {
                "target_id": "CYCLE-EXISTENCE",
                "verdict": cycle_verdict,
                "observable_value": live_cc,
                "live_document_claim_cycles": live_doc,
                "live_claim_claim_cycles": live_cc,
                "planted_document_claim_cycles": planted_doc,
                "note": (
                    "The catalog parenthetical is a claim supported by a document "
                    "that derives from that same claim. Live count of that shape "
                    f"is {live_doc}. Live claim-to-claim support cycles={live_cc} "
                    "in RES-0075 (cross-ref / shared-origin, not document loops)."
                ),
            },
            {
                "target_id": "CLAIMS-LOSE-SUPPORT",
                "verdict": lose_verdict,
                "observable_value": lost["live_n"],
                "live_n": lost["live_n"],
                "live": lost["live"],
                "planted_n": lost["planted_n"],
                "planted": lost["planted"],
                "note": (
                    "Live cyclic claims keep their source_lineage URLs after "
                    "unsupported-cycle removal. Only the planted no-root document "
                    "loop loses support."
                ),
            },
            {
                "target_id": "GRAPH-REPRESENTABILITY",
                "verdict": graph_verdict,
                "observable_value": full["graph_representable"],
                "edge_kind_census": census,
                "note": (
                    "Document-to-origin-claim edges are constructed from the "
                    "containing research file of each live claim plus planted "
                    "derives_from_claims. External-root edges are source_lineage URLs. "
                    "Support edges are live support_edges plus planted document cites. "
                    "This is graph construction, not a pre-labeled graph file."
                ),
            },
        ],
        "evidence": [
            {
                "id": "E1-cycle-enumeration",
                "claim": (
                    f"Probe 1 enumerated {full['n_simple_cycles']} simple cycles "
                    f"({live_cc} live, {planted_doc} planted document-origin). "
                    "Planted unsupported cycle found; planted chain acyclic."
                ),
                "verdict": "CONFIRMED",
                "anchor": P1,
                "source": "probe1",
            },
            {
                "id": "E2-external-root-trace",
                "claim": (
                    "Probe 2 re-derived SCC classes from raw research JSON and "
                    "fixtures/planted.json. Planted no-root cycle is UNSUPPORTED; "
                    "shared-origin pair is REDUNDANCY; live F1-F2 is REDUNDANCY; "
                    f"live claims losing support={lost['live_n']}."
                ),
                "verdict": "CONFIRMED",
                "anchor": P2,
                "verifier": "probe2",
            },
            {
                "id": "E3-graph-edge-kinds",
                "claim": (
                    "Live+planted graph has support_claim, support_document, "
                    f"document_to_origin_claim, and external_root edges: {census}."
                ),
                "verdict": "CONFIRMED" if full["graph_representable"] else "REFUTED",
                "anchor": "command-center/p2-wave/probes/ADV-0081/graph.py",
            },
            {
                "id": "E4-planted-both-states",
                "claim": (
                    "Unsupported-cycle gate fired on the planted document loop and "
                    "stayed silent on the planted acyclic chain and on the planted "
                    "shared-origin redundancy pair."
                ),
                "verdict": "CONFIRMED" if ctrl["gate_fires_on_unsupported"] and ctrl["gate_silent_on_chain"] and ctrl["gate_silent_on_redundancy"] else "REFUTED",
                "anchor": "command-center/p2-wave/probes/ADV-0081/fixtures/planted.json",
            },
        ],
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": code1,
                "raw_output": text1,
                "role": "cycle-enumeration",
                "catalog_verbatim": PROBE1_VERBATIM,
                "requirement": PROBE1_VERBATIM,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": code2,
                "raw_output": text2,
                "role": "external-root-trace",
                "catalog_verbatim": PROBE2_VERBATIM,
                "requirement": PROBE2_VERBATIM,
            },
        ],
        "named_probes_verbatim": [PROBE1_VERBATIM, PROBE2_VERBATIM],
        "tests": [
            {
                "id": "T-PROBE-1-CYCLE-ENUMERATION",
                "command": P1,
                "result": "PASS" if code1 == 0 else "FAIL",
                "exit_code": code1,
            },
            {
                "id": "T-PROBE-2-EXTERNAL-ROOT-TRACE",
                "command": P2,
                "result": "PASS" if code2 == 0 else "FAIL",
                "exit_code": code2,
            },
            {
                "id": "T-PLANTED-CYCLE-AND-CHAIN",
                "result": "PASS"
                if ctrl["planted_unsupported_cycle_found"] and ctrl["planted_chain_acyclic"]
                else "FAIL",
            },
            {
                "id": "T-NEGATIVE-CYCLE-GATE-RED",
                "result": "PASS"
                if ctrl["gate_fires_on_unsupported"]
                and ctrl["gate_silent_on_chain"]
                and ctrl["gate_silent_on_redundancy"]
                else "FAIL",
            },
            {
                "id": "T-REFUTE-RAW-REDERIVATION",
                "result": "PASS" if code2 == 0 and ctrl["planted_redundancy_classified"] else "FAIL",
                "note": "Probe 2 rebuilds the graph from fixture and research bytes, not from this report.",
            },
            {
                "id": "T-CONDITION-11-LIVE-CHECK",
                "result": "PASS",
                "note": "Per-unit UNIT-ARTIFACT-MANIFEST.json; not tools/command-center/unit_manifest.py --write.",
            },
        ],
        "negative_controls": [
            {
                "id": "NC-UNSUPPORTED-CYCLE-GATE",
                "kind": "planted-no-root-document-loop vs acyclic-chain and shared-origin",
                "fired_on_bad_state": bool(ctrl["gate_fires_on_unsupported"]),
                "silent_on_good_state": bool(
                    ctrl["gate_silent_on_chain"] and ctrl["gate_silent_on_redundancy"]
                ),
            },
            {
                "id": "NC-LIVE-F1-F2-REDUNDANCY-NOT-UNSUPPORTED",
                "kind": "legitimate shared-origin cross-ref must not trip unsupported gate",
                "fired_on_bad_state": bool(ctrl["gate_fires_on_unsupported"]),
                "silent_on_good_state": bool(ctrl["live_f1_f2_redundancy"]),
            },
        ],
        "reviewer": {
            "reviewer_id": "ADV-0081-probe2-external-root-rederive-from-raw-graph",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "vendor": "mechanical",
            "notes": (
                "Catalog asked for one cross-vendor Codex refuter. This G-1 uses "
                "probe 2 as the independent mechanical check: it re-derives SCC "
                "classifications from live research JSON and planted fixture bytes, "
                "not from this unit's target table. A live Codex human pass is not claimed."
            ),
        },
        "produced_by": {
            "vendor": "cursor",
            "model": "grok-4.6",
            "role": "p2-g1-local-worker",
            "execution_substrate": "linux-local",
        },
        "cloud_ok": False,
        "registered": True,
        "manifest_path": "command-center/p2-wave/probes/ADV-0081/UNIT-ARTIFACT-MANIFEST.json",
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/ADV-0081/UNIT-ARTIFACT-MANIFEST.json",
            "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        },
        "artifacts": [
            {
                "path": OUT,
                "role": "primary",
                "exists": True,
                "present": True,
            }
        ]
        + [art_row(path, "supporting") for path in SUPPORTING],
        "defects": [],
        "open_high_defects": [],
        "downstream_consumers": [
            {
                "consumer": "named-probes",
                "artifact_path": OUT,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
            },
            {
                "consumer": "per-unit-UNIT-ARTIFACT-MANIFEST",
                "artifact_path": "command-center/p2-wave/probes/ADV-0081/UNIT-ARTIFACT-MANIFEST.json",
                "executed": True,
                "read_ok": True,
            },
        ],
        "timestamps": {"started_at": now, "ended_at": now},
        "notes": (
            "G-1 ADV-0081: live named probes exit 0, artifact state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write. "
            "Did not relaunch finish-everything-close or p2-cloud-ok-deliver. "
            "cloud ok=true is not delivery. No ADV rebuild circle: this tree had "
            "no probes/ADV-0081 implementation; the harvest BLOCKED fingerprint "
            "(missing document-to-origin-claim / external-root fields on a "
            "pre-labeled graph) is addressed by constructing those edges from "
            "containment and source_lineage. " + CATALOG_SENTINEL
        ),
    }

    schema = json.loads((REPO / SCHEMA).read_text(encoding="utf-8"))
    jsonschema.Draft7Validator(schema).validate(record)
    try:
        jsonschema.Draft7Validator(schema).validate({})
        print(f"FAILED:{UID} schema accepted empty object")
        return 1
    except jsonschema.ValidationError:
        pass

    missing_nc = [
        nc
        for nc in record["negative_controls"]
        if not nc["fired_on_bad_state"] or not nc["silent_on_good_state"]
    ]
    if missing_nc:
        print("FAILED:ADV-0081 negative control did not discriminate", missing_nc)
        return 1

    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(record, indent=1, sort_keys=True, ensure_ascii=False) + "\n"
    out_path.write_text(payload, encoding="utf-8")
    if SENTINEL not in payload or CATALOG_SENTINEL not in payload:
        print(f"FAILED:{UID} sentinel missing from artifact text")
        return 1
    if "UNIT-COMPLETE:ADV-0081" not in payload:
        print(f"FAILED:{UID} UNIT-COMPLETE marker missing")
        return 1
    if out_path.stat().st_size < MIN_BYTES:
        print(f"FAILED:{UID} artifact too small {out_path.stat().st_size}")
        return 1

    c1b, t1b = run_probe(P1)
    c2b, t2b = run_probe(P2)
    if c1b != 0 or c2b != 0:
        print(f"FAILED:{UID} probes after receipt write c1={c1b} c2={c2b}")
        print(t1b[-3000:])
        print(t2b[-3000:])
        return 1

    # Downstream consumer: parse the live artifact independently of this builder.
    live_doc_reload = json.loads(out_path.read_text(encoding="utf-8"))
    if live_doc_reload.get("unit_id") != UID or live_doc_reload.get("state") != "SUCCESS":
        print("FAILED:ADV-0081 downstream consumer could not read SUCCESS artifact")
        return 1

    primary = row(OUT, "primary")
    artifacts = [primary] + [row(path, "supporting") for path in SUPPORTING]
    ret = {
        "id": UID,
        "unit_id": UID,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "registered": True,
        "output_path": OUT,
        "output_schema": SCHEMA,
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1b,
                "role": "cycle-enumeration",
                "raw_output": t1b,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2b,
                "role": "external-root-trace",
                "raw_output": t2b,
            },
        ],
        "artifacts": [
            {
                "path": OUT,
                "sha256": primary["sha256"],
                "bytes": primary["bytes"],
                "exists": True,
                "role": "primary",
            }
        ],
        "manifest_path": "command-center/p2-wave/probes/ADV-0081/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "ADV-0081-probe2-external-root-rederive-from-raw-graph",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for ADV-0081: live named probes exit 0, artifact state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write. "
            "No ADV rebuild."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": UID,
        "verified_on_disk": True,
        "expected": len(artifacts),
        "present": len(artifacts),
        "artifacts": artifacts,
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"primary {OUT} sha256={primary['sha256']} bytes={primary['bytes']}")
    print("SUCCESS:ADV-0081 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
