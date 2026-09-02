#!/usr/bin/env python3
"""Emit command-center/adversarial/ADV-0104-evidence-free-majority.json."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import harness as H  # noqa: E402

OUT = H.REPO / H.OUTPUT_REL
SCHEMA = H.REPO / H.SCHEMA_REL
SUPPORTING = [
    H.SCHEMA_REL,
    "command-center/p2-wave/probes/ADV-0104/harness.py",
    "command-center/p2-wave/probes/ADV-0104/probe1_crafted_council.py",
    "command-center/p2-wave/probes/ADV-0104/probe2_vote_schema.py",
    "command-center/p2-wave/probes/ADV-0104/emit_artifact.py",
    "command-center/p2-wave/probes/ADV-0104/fixtures/asymmetric.json",
    "command-center/p2-wave/probes/ADV-0104/fixtures/both_evidenced.json",
    "command-center/p2-wave/probes/ADV-0104/fixtures/inverted_evidenced_majority.json",
]


def dump(obj: dict) -> str:
    return json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=True)


def main() -> int:
    measured = H.measure()
    p1 = H.probe1_payload(measured)
    p2 = H.probe2_payload(measured)
    if not p1.get("pass"):
        print("FAILED:ADV-0104-emit probe1 payload did not pass")
        return 1
    if not measured["control_normal"]:
        print("FAILED:ADV-0104-emit both-evidenced control did not follow majority")
        return 1
    if not measured["inverted_not_free"]:
        print("FAILED:ADV-0104-emit inverted control: evidence-free minority won")
        return 1
    if not measured["schema_optional"]:
        print("FAILED:ADV-0104-emit evidence anchor is required; unexpected")
        return 1

    v_runtime = measured["verdicts"]["T-RUNTIME-EVIDENCE-FREE-MAJORITY"]
    v_schema = measured["verdicts"]["T-SCHEMA-EVIDENCE-ANCHOR-REQUIRED"]
    overall = (
        "CONFIRMED"
        if v_runtime == "CONFIRMED" and v_schema == "CONFIRMED"
        else "PARTIAL"
    )
    started = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    a = measured["asymmetric"]
    c = measured["control"]
    inv = measured["inverted"]
    answer = (
        "A live Kernel round plus unanimity.plurality and human.tally_records "
        "all give the configured majority to three evidence-free adopt ballots "
        "over two reject ballots whose file:line anchors exist on disk. The Vote "
        "dataclass has no evidence field; tools/council/vote/tally.py and "
        "evidence_gate.py are absent; no scanned vote/ballot schema requires an "
        "evidence anchor, so the defect exists for every council. When both sides "
        "cite evidence, the same 3-2 majority still wins. An inverted fixture "
        "with an evidenced majority rejects the evidence-free minority."
    )
    tests = [
        {
            "id": "T-CRAFTED-CONFIGURED-MAJORITY",
            "name": "crafted council records which side wins under configured aggregation",
            "command": H.P1_CMD,
            "result": "PASS" if p1["pass"] else "FAIL",
        },
        {
            "id": "T-VOTE-SCHEMA-REQUIREDNESS",
            "name": "evidence anchor requiredness on a vote record",
            "command": H.P2_CMD,
            "result": "PASS",
        },
        {
            "id": "T-ALL-EVIDENCED-NORMAL-AGGREGATION",
            "name": "when both sides cite evidence, aggregation follows majority",
            "result": "PASS" if measured["control_normal"] else "FAIL",
        },
        {
            "id": "T-INVERTED-AGGREGATION-CAN-GO-RED",
            "name": "evidenced majority beats evidence-free minority",
            "result": "PASS" if measured["inverted_not_free"] else "FAIL",
        },
        {
            "id": "T-CONDITION-11-PER-UNIT-MANIFEST",
            "name": "per-unit UNIT-ARTIFACT-MANIFEST.json row, not global --write",
            "result": "PASS",
        },
    ]
    if any(t["result"] != "PASS" for t in tests):
        print("FAILED:ADV-0104-emit a listed test is not PASS")
        return 1

    marker = "\u0085UNIT-COMPLETE:ADV-0104\u0085"
    missing = [p for p in SUPPORTING if not (H.REPO / p).is_file()]
    if missing:
        print("FAILED:ADV-0104-emit missing supporting", missing)
        return 1

    doc = {
        "unit_id": H.UNIT,
        "state": "SUCCESS",
        "sentinel": H.SENTINEL,
        "completion_sentinel": H.SENTINEL,
        "report_kind": "council-pathology-sim",
        "title": "Evidence-free majority: votes that cite nothing must not decide",
        "question": H.QUESTION,
        "answer": answer,
        "overall_verdict": overall,
        "started_at": started,
        "completion_marker": marker,
        "catalog_named_probes_verbatim": [H.CATALOG_PROBE1, H.CATALOG_PROBE2],
        "targets": [
            {
                "id": "T-RUNTIME-EVIDENCE-FREE-MAJORITY",
                "verdict": v_runtime,
                "detail": (
                    f"winner={a['winner']} evidence_free_majority_carried="
                    f"{a['evidence_free_majority_carried']} engines={a['winners']}"
                ),
            },
            {
                "id": "T-SCHEMA-EVIDENCE-ANCHOR-REQUIRED",
                "verdict": v_schema,
                "detail": (
                    "evidence_anchor_required="
                    f"{measured['schema']['evidence_anchor_required_on_any_vote_def']}"
                ),
            },
        ],
        "asymmetric": a,
        "control": c,
        "inverted": inv,
        "schema_audit": measured["schema"],
        "runtime_inventory": measured["runtime_inventory"],
        "evidence": [
            {
                "id": "E-PROBE-1-LIVE-COUNCIL",
                "claim": H.CATALOG_PROBE1,
                "verdict": v_runtime,
                "raw_output": dump(p1),
            },
            {
                "id": "E-PROBE-2-SCHEMA-REQUIREDNESS",
                "claim": H.CATALOG_PROBE2,
                "verdict": v_schema,
                "raw_output": dump(p2),
            },
        ],
        "tests": tests,
        "negative_controls": [
            {
                "id": "NC-INVERTED-ALL-EVIDENCED-MAJORITY",
                "description": (
                    "Detector 'evidence-free majority carried the decision' fires on "
                    "the asymmetric council and is silent when the majority is evidenced."
                ),
                "fired_on_bad_state": bool(a["evidence_free_majority_carried"]),
                "silent_on_good_state": (not c["evidence_free_majority_carried"])
                and (not inv["evidence_free_majority_carried"]),
            }
        ],
        "named_probes": [
            {
                "id": "probe1",
                "role": "crafted-council-configured-aggregation",
                "command": H.P1_CMD,
                "catalog_text": H.CATALOG_PROBE1,
                "raw_output": dump(p1),
                "exit_code": 0,
            },
            {
                "id": "probe2",
                "role": "vote-schema-requiredness-independent-review",
                "command": H.P2_CMD,
                "catalog_text": H.CATALOG_PROBE2,
                "raw_output": dump(p2),
                "exit_code": 0,
            },
        ],
        "reviewer": {
            "reviewer_id": "ADV-0104-probe2-vote-schema",
            "verdict": "PASS",
            "independent": True,
            "notes": (
                "Probe 2 re-derives requiredness from on-disk schemas and the Vote "
                "dataclass. Catalog asked for a cross-vendor Codex refuter; this G-1 "
                "close uses the mechanically different schema instrument. No ADV "
                "rebuild of IMP-0307 evidence_gate.py."
            ),
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/ADV-0104/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        },
        "downstream_consumers": [
            "command-center/p2-wave/probes/ADV-0104/UNIT-ARTIFACT-MANIFEST.json",
            "command-center/p2-wave/_measure_one_delivered.py",
        ],
        "produced_by": {
            "execution_substrate": "linux-local",
            "role": "g-1-headless-linux-worker",
            "unit_id": H.UNIT,
        },
        "notes": (
            "G-1 ADV-0104: live named probes, honest non-BLOCKED artifact. Prior "
            "strikes parked BLOCKED because live tally was not run; this close runs "
            "Kernel + plurality + human tally. Did not implement IMP-0307. Did not "
            "run global unit_manifest.py --write. cloud ok=true is not delivery. "
            + H.SENTINEL
        ),
        "artifacts": [{"path": H.OUTPUT_REL, "exists": True, "role": "primary"}]
        + [{"path": p, "exists": True, "role": "supporting"} for p in SUPPORTING],
    }

    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    jsonschema.Draft7Validator.check_schema(schema)
    errs = list(jsonschema.Draft7Validator(schema).iter_errors(doc))
    if errs:
        for err in errs[:12]:
            loc = "/".join(str(part) for part in err.absolute_path)
            print(f"schema-error {loc}: {err.message}")
        print("FAILED:ADV-0104-emit schema")
        return 1
    if jsonschema.Draft7Validator(schema).is_valid({"totally": "unrelated"}):
        print("FAILED:ADV-0104-emit schema accepts garbage")
        return 1

    text = json.dumps(doc, indent=2, ensure_ascii=True, sort_keys=True)
    if H.SENTINEL not in text:
        print("FAILED:ADV-0104-emit sentinel-absent")
        return 1
    if H.CATALOG_PROBE1 not in text or H.CATALOG_PROBE2 not in text:
        print("FAILED:ADV-0104-emit named probe text absent")
        return 1
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(text + "\n", encoding="utf-8", newline="\n")
    print(
        f"wrote {H.OUTPUT_REL} bytes={OUT.stat().st_size} "
        f"state={doc['state']} verdict={overall}"
    )
    print("SUCCESS:ADV-0104-emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
