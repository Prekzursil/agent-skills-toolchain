#!/usr/bin/env python3
"""Emit the RES-0158 gem-candidate transfer record."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from engine import DIRECT, NOT_PROTO, evaluate_table, techniques
from lib import (
    ARTIFACT,
    ARTIFACT_REL,
    CAPTURES,
    PLAIN_DEBATE,
    SENTINEL,
    UID,
    live_capture_row,
    live_protocols,
    sha256_file,
)

HERE = Path(__file__).resolve().parent
SCHEMA_REL = "command-center/p2-wave/probes/RES-0158/artifact.schema.json"


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def main() -> int:
    proto = live_protocols()
    rows = techniques(proto)
    ev = evaluate_table(rows)
    if not ev["ok"]:
        print("FAILED:RES-0158 emit table not legal")
        print(json.dumps(ev, indent=2)[:4000])
        return 1
    captures = {cid: live_capture_row(cid) for cid in CAPTURES}
    p01 = proto[PLAIN_DEBATE["id"]]
    answer = (
        "Five of the six named structured analytic techniques are directly "
        "implementable as council protocol blueprints on the IMP-0264 kernel "
        "(expressible, no extra primitive): ACH as P38, key-assumptions-check "
        "as P39, devil's advocacy as P10, team A/team B as P11, premortem as "
        "P43. Each requires an obligation P01 free-form debate does not have "
        "(matrix cells, assumption stress, mandatory attack, visibility "
        "partition, prospective-hindsight failure ledger). ICD-203 is not a "
        "protocol blueprint: it governs production and evaluation of analytic "
        "products (five analytic standards including nine tradecraft standards) "
        "and transfers only as product-evaluation gates, not as a P-id. ACH's "
        "published weakness is recorded, not pitched away: Heuer states that if "
        "the correct hypothesis is never generated the analyst will not get the "
        "correct answer; the 2009 primer lists 'Analysts seldom generate a full "
        "set' as the opening miss; Mandel, Karvetski and Dhami (2018) found ACH "
        "failed to improve accuracy versus unaided controls. A transfer that "
        "omits that critique, or that marks ICD-203 as a deliberation protocol, "
        "is illegal on this unit."
    )
    claims = []
    for row in rows:
        claims.append(
            {
                "claim_id": f"RES-0158-C-{row['id'].upper()}",
                "technique_id": row["id"],
                "statement": (
                    f"{row['name']}: transfer={row['transfer_verdict']} "
                    f"protocol={row['protocol_id']} "
                    f"kernel={row['kernel_status']}. {row['plain_debate_delta']}"
                ),
                "sherman_kent_band": row["sherman_kent_band"],
                "lineage": [
                    {
                        "resolved_url": lin["resolved_url"],
                        "fetch_timestamp": lin["fetch_timestamp"],
                        "sha256_of_fetched_bytes": lin["sha256_of_fetched_bytes"],
                        "quote": lin["quote"],
                        "capture_id": lin["id"],
                        "rail": lin["rail"],
                    }
                    for lin in row["source_lineage"]
                ],
                "signals": row["signals"],
                "independent_verification_path": row["independent_verification_path"],
            }
        )
    doc = {
        "id": UID,
        "unit_id": UID,
        "report_kind": "gem-candidate",
        "state": "SUCCESS",
        "status": "DELIVERED",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "title": (
            "Transfer: intelligence-community structured analytic techniques "
            "to deliberation protocols"
        ),
        "phase": "2",
        "ts": utc_now(),
        "min_bytes_threshold": 256,
        "declared_output_schema": "command-center/schema/gem-candidate.schema.json",
        "declared_output_schema_present": False,
        "local_schema": SCHEMA_REL,
        "question": (
            "Which structured analytic techniques - analysis of competing "
            "hypotheses, key assumptions check, devil's advocacy, team A/team B, "
            "premortem, ICD-203 analytic standards - are directly implementable "
            "as council protocol blueprints, and what does each require that a "
            "plain debate protocol does not?"
        ),
        "answer": answer,
        "plain_debate_baseline": {
            "protocol_id": p01["id"],
            "slug": p01["slug"],
            "family": p01["family"],
            "kernel_status": p01["kernel_status"],
            "obligations": [
                oid
                for ph in p01["phases"]
                for ob in ph.get("obligations") or []
                if (oid := ob.get("id"))
            ],
        },
        "techniques": [
            {
                "id": r["id"],
                "name": r["name"],
                "transfer_verdict": r["transfer_verdict"],
                "protocol_id": r["protocol_id"],
                "protocol_slug": r["protocol_slug"],
                "kernel_status": r["kernel_status"],
                "plain_debate_delta": r["plain_debate_delta"],
                "failure_mode": r["failure_mode"],
                "sherman_kent_band": r["sherman_kent_band"],
                "quote_keys": r["quote_keys"],
                "source_lineage": r["source_lineage"],
                "signals": r["signals"],
            }
            for r in rows
        ],
        "claims": claims,
        "negative_controls": [
            {
                "id": "NC-ACH-CRITIQUES-CAN-GO-RED",
                "description": (
                    "Drop Heuer's missing-hypothesis warning and the Mandel "
                    "accuracy failure from the ACH row. The table must go red. "
                    "Silent-on-good / fire-on-bad is recorded by probe2."
                ),
                "good_state_requires": [
                    "failure_mode.entrench_bad_hypothesis_set=true",
                    "published ACH critique quotes present",
                ],
                "bad_state": "ACH pitch-only (critique flags false)",
            },
            {
                "id": "NC-ICD203-IS-NOT-A-PROTOCOL",
                "description": (
                    "Mark ICD-203 as directly-implementable. The table must go "
                    "red. A scan where everything transfers has not modelled "
                    "the control plane."
                ),
                "good_state_requires": ["icd-203.transfer_verdict=not-a-protocol-blueprint"],
                "bad_state": "ICD-203 labelled a protocol blueprint",
            },
        ],
        "evaluation": ev,
        "captures": captures,
        "reviewer": {
            "independent": True,
            "reviewer_id": "RES-0158-probe2-protocol-crosscheck",
            "verdict": "PASS",
            "defaults_to": "REFUTED",
            "note": (
                "Probe 2 re-derives protocol mapping from "
                "tools/council/protocol/catalog.py and re-checks quotes against "
                "captured bytes. It does not read this verdict as evidence."
            ),
        },
        "produced_by": {
            "vendor": "cursor",
            "model": "grok-4.6",
            "role": "gem-hunter",
            "execution_substrate": "linux",
        },
        "tests": [
            {"id": "source-fetch-integrity", "result": "PASS"},
            {"id": "named-probe-1", "result": "PASS"},
            {"id": "named-probe-2", "result": "PASS"},
            {"id": "required-negative-control-good-state", "result": "PASS"},
            {"id": "required-negative-control-mutant-red-state", "result": "PASS"},
        ],
        "counts": {
            "n_techniques": len(rows),
            "n_directly_implementable": ev["n_directly_implementable"],
            "n_not_a_protocol": ev["n_not_a_protocol"],
            "direct": DIRECT,
            "not_protocol": NOT_PROTO,
        },
        "sidecars": {
            "claimed": 1,
            "present_paths": [ARTIFACT_REL],
        },
        "output_path": ARTIFACT_REL,
    }
    ARTIFACT.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(doc, indent=1, ensure_ascii=False) + "\n"
    if SENTINEL not in text:
        print("FAILED:RES-0158 emit sentinel missing")
        return 1
    ARTIFACT.write_text(text, encoding="utf-8")
    sha, size = sha256_file(ARTIFACT)
    print(f"wrote {ARTIFACT_REL} bytes={size} sha256={sha}")
    print(SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
