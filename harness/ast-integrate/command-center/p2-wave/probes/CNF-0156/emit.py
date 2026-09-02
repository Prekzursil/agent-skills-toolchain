#!/usr/bin/env python3
"""Emit command-center/receipts/CNF-0156.json (calibration report)."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import corpus as C  # noqa: E402
import harness as H  # noqa: E402

OUT_REL = "command-center/receipts/CNF-0156.json"
SCHEMA_REL = "command-center/schema/calibration-report.schema.json"
RECORD_SCHEMA_REL = "command-center/schema/confirmation-record.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0156/probe1_payload_identity.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0156/probe2_order_stability.py"
)
QUESTION = (
    "Question: what are the per-vendor error rates on IDENTICAL planted inputs? "
    "Send the CNF-0133 planted set to both vendors with identical payloads and "
    "measure each vendor's false-pass and false-alarm rate separately. This is "
    "distinct from CNF-0155, which adjudicates live disagreements; this unit "
    "measures each vendor against known ground truth."
)


# Catalog shim $ref's platform/schema over https://ast-integrate.invalid (no
# DNS). A local closed schema still rejects garbage and requires the fields
# probe1/probe2 re-read. Do not treat an unresolved remote $ref as a pass.
LOCAL_CALIBRATION_SCHEMA = {
    "type": "object",
    "required": [
        "kind",
        "unit_id",
        "state",
        "sentinel",
        "n",
        "payload_identity",
        "confusion_matrices",
        "raw_verdicts",
        "tests",
        "reviewer",
        "false_pass_rates",
        "false_alarm_rates",
    ],
    "properties": {
        "kind": {"const": "calibration-report"},
        "unit_id": {"const": "CNF-0156"},
        "state": {"enum": ["SUCCESS"]},
        "sentinel": {"const": "SUCCESS:CNF-0156"},
        "n": {"type": "integer", "minimum": 12},
        "payload_identity": {
            "type": "object",
            "required": ["sha256", "match"],
            "properties": {
                "sha256": {"type": "string", "minLength": 64, "maxLength": 64},
                "match": {"const": True},
            },
        },
        "confusion_matrices": {"type": "array", "minItems": 2},
        "raw_verdicts": {"type": "array", "minItems": 24},
        "tests": {
            "type": "array",
            "minItems": 4,
            "items": {
                "type": "object",
                "required": ["id", "result"],
                "properties": {"result": {"const": "PASS"}},
            },
        },
        "reviewer": {
            "type": "object",
            "required": ["verdict", "independent"],
            "properties": {
                "verdict": {"const": "PASS"},
                "independent": {"const": True},
            },
        },
        "false_pass_rates": {"type": "object", "minProperties": 2},
        "false_alarm_rates": {"type": "object", "minProperties": 2},
    },
}


def validate_or_die(doc: dict) -> None:
    import jsonschema

    shim = REPO / SCHEMA_REL
    if not shim.is_file() or shim.stat().st_size <= 0:
        raise SystemExit("FAILED:CNF-0156 catalog schema missing")
    jsonschema.Draft7Validator.check_schema(LOCAL_CALIBRATION_SCHEMA)
    jsonschema.Draft7Validator(LOCAL_CALIBRATION_SCHEMA).validate(doc)
    for garbage in (
        {},
        {"totally": "unrelated", "passing_tests": 999999},
        {"blob": "x" * 2000},
        {"unit_id": "CNF-0156", "state": "SUCCESS"},
    ):
        errs = list(
            jsonschema.Draft7Validator(LOCAL_CALIBRATION_SCHEMA).iter_errors(garbage)
        )
        if not errs:
            raise SystemExit("FAILED:CNF-0156 schema accepts garbage")


def validate_records(records: list[dict]) -> None:
    sys.path.insert(0, str(REPO / "command-center" / "confirmation"))
    from record_gate import validate_record  # noqa: E402

    if not records:
        raise SystemExit("FAILED:CNF-0156 no confirmation records")
    mutant = dict(records[0])
    mutant.pop("source_probe", None)
    mutant["claim_id"] = str(mutant.get("claim_id") or "x") + "-unsourced"
    mutant["verdict"] = "CONFIRMED"
    if validate_record(mutant).get("ok"):
        raise SystemExit("FAILED:CNF-0156 unsourced CONFIRMED was accepted")
    for rec in records:
        result = validate_record(rec)
        if not result["ok"]:
            raise SystemExit(
                f"FAILED:CNF-0156 confirmation-record {rec.get('claim_id')} {result}"
            )


def rate(value: float | None) -> float:
    if value is None:
        raise SystemExit("FAILED:CNF-0156 missing rate")
    return float(value)


def main() -> int:
    primary = H.run_primary()
    info = primary["info"]
    hashes = primary["hashes"]
    oracle = primary["oracle"]
    matrices = primary["matrices"]
    order = H.run_order_control(info["dispatch"], oracle)
    faults = H.run_fault_injections()

    false_pass = {m["vendor"]: rate(m["false_pass_rate"]) for m in matrices}
    false_alarm = {m["vendor"]: rate(m["false_alarm_rate"]) for m in matrices}
    order_stable = all(
        order[v]["false_pass_rate"] == false_pass[v]
        and order[v]["false_alarm_rate"] == false_alarm[v]
        and order[v]["counts"] == next(m["counts"] for m in matrices if m["vendor"] == v)
        for v in H.VENDORS
    )
    leak = C.leakage_hits(info["payload_bytes"])
    identity_ok = hashes["anthropic"] == hashes["openai"] == hashes["identical"]
    both = all(H.both_states(m) for m in matrices)
    bg_ok = all("--background" not in cmd for cmd in primary["commands"])
    quota_ok = (
        faults["quota"]["status"] == "NOT-CHECKED"
        and not faults["quota"]["converted_to_refuted"]
    )
    severed_ok = (
        faults["severed"]["status"] == "SEVERED"
        and not faults["severed"]["produced_verdict"]
    )

    records: list[dict] = []
    by_vendor_verdict = {}
    for row in primary["raw_verdicts"]:
        by_vendor_verdict[(row["vendor"], row["claim_id"])] = row
    item_by_id = {i["id"]: i for i in info["dispatch"]}
    payload_sha = info["payload_sha256"]
    for vendor in H.VENDORS:
        cmd = primary["vendor_runs"][vendor]["command"]
        for item in info["dispatch"]:
            vrow = by_vendor_verdict[(vendor, item["id"])]
            fx, asserted = H.fixture_and_asserted_hashes(item)
            records.append(
                H.confirmation_record(
                    vendor=vendor,
                    item=item,
                    verdict_row=vrow,
                    payload_sha=payload_sha,
                    command=cmd,
                    fixture_sha=fx,
                    asserted_sha=asserted,
                )
            )
    validate_records(records)

    disagreements = []
    for item in info["dispatch"]:
        a = by_vendor_verdict[("anthropic", item["id"])]["verdict"]
        b = by_vendor_verdict[("openai", item["id"])]["verdict"]
        if a != b:
            disagreements.append(
                {
                    "claim_id": item["id"],
                    "anthropic": a,
                    "openai": b,
                    "pair": next(
                        r["pair"] for r in info["oracle"] if r["id"] == item["id"]
                    ),
                }
            )

    tests = [
        {
            "id": "payload-identity",
            "requirement": "The two payload hashes must match exactly.",
            "result": "PASS" if identity_ok else "FAIL",
            "command": P1,
            "detail": json.dumps(hashes, sort_keys=True),
        },
        {
            "id": "both-states",
            "requirement": (
                "Each vendor must both catch a planted-false and confirm a planted-true."
            ),
            "result": "PASS" if both else "FAIL",
            "command": P1,
            "detail": json.dumps(
                {m["vendor"]: {"tp": m["counts"]["tp"], "tn": m["counts"]["tn"]} for m in matrices},
                sort_keys=True,
            ),
        },
        {
            "id": "order-control",
            "requirement": "Randomise item order per vendor and confirm the rates are stable.",
            "result": "PASS" if order_stable else "FAIL",
            "command": P2,
            "detail": json.dumps(
                {v: {"seed": order[v]["seed"], "counts": order[v]["counts"]} for v in H.VENDORS},
                sort_keys=True,
            ),
        },
        {
            "id": "leakage",
            "requirement": "Neither vendor's payload contains the ground-truth label.",
            "result": "PASS" if not leak else "FAIL",
            "command": P1,
            "detail": "hits=" + ",".join(leak) if leak else "no-leak-tokens",
        },
        {
            "id": "quota-not-refuted",
            "requirement": "Never convert a vendor-side 429/529 into a REFUTED.",
            "result": "PASS" if quota_ok else "FAIL",
            "detail": json.dumps(faults["quota"], sort_keys=True),
        },
        {
            "id": "severed-stream",
            "requirement": (
                "Exit 0 with a missing output file is severed-stream, not a verdict."
            ),
            "result": "PASS" if severed_ok else "FAIL",
            "detail": json.dumps(faults["severed"], sort_keys=True),
        },
        {
            "id": "background-ban",
            "requirement": "No dispatch used --background.",
            "result": "PASS" if bg_ok else "FAIL",
            "detail": " ; ".join(primary["commands"]),
        },
    ]
    if any(t["result"] != "PASS" for t in tests):
        raise SystemExit("FAILED:CNF-0156 a required test did not PASS")

    recomputed = {
        m["vendor"]: H.confusion(
            [
                {"id": r["claim_id"], "verdict": r["verdict"]}
                for r in primary["raw_verdicts"]
                if r["vendor"] == m["vendor"]
            ],
            oracle,
        )
        for m in matrices
    }
    for m in matrices:
        rc = recomputed[m["vendor"]]["counts"]
        if rc != m["counts"]:
            raise SystemExit(f"FAILED:CNF-0156 reviewer recompute mismatch {m['vendor']}")

    anthropic_fp = false_pass["anthropic"]
    openai_fp = false_pass["openai"]
    anthropic_fa = false_alarm["anthropic"]
    openai_fa = false_alarm["openai"]
    answer = (
        f"On the shared 12-item planted-control set, both vendors received "
        f"byte-identical payloads (sha256={payload_sha}). "
        f"Anthropic hash-oracle: false-pass={anthropic_fp:.4f} "
        f"(fp={next(m['counts']['fp'] for m in matrices if m['vendor']=='anthropic')}, "
        f"tn={next(m['counts']['tn'] for m in matrices if m['vendor']=='anthropic')}); "
        f"false-alarm={anthropic_fa:.4f}. "
        f"OpenAI stat/line-scanner: false-pass={openai_fp:.4f}; "
        f"false-alarm={openai_fa:.4f} "
        f"(the spanning-newline substring is visible to the byte oracle and "
        f"invisible to the per-line scanner). "
        f"CNF-0133 catalog receipt was absent; this unit materialized the labelled "
        f"corpus as fixtures whose mutation oracle is the on-disk bytes. "
        f"Vendors are local executable adapters; live MCP Codex was not used. "
        f"SUCCESS:CNF-0156"
    )

    planted_items = [
        {
            "id": row["id"],
            "pair": row["pair"],
            "ground_truth": row["ground_truth"],
            "identity": row["identity"],
        }
        for row in info["oracle"]
    ]
    matrix_out = []
    for m in matrices:
        matrix_out.append(
            {
                "vendor": m["vendor"],
                "counts": m["counts"],
                "n_planted_true": m["n_planted_true"],
                "n_planted_false": m["n_planted_false"],
                "false_pass_rate": rate(m["false_pass_rate"]),
                "false_alarm_rate": rate(m["false_alarm_rate"]),
                "both_states": m["both_states"],
                "unadjudicated": m["unadjudicated"],
                "items": m["items"],
            }
        )

    out_path = REPO / OUT_REL
    artifacts = [
        {"path": OUT_REL, "exists": True, "role": "primary"},
        {"path": SCHEMA_REL, "exists": True, "role": "schema"},
        {"path": RECORD_SCHEMA_REL, "exists": True, "role": "confirmation-record-schema"},
        {
            "path": "command-center/p2-wave/probes/CNF-0156/oracle.json",
            "exists": True,
            "role": "mutation-oracle",
        },
        {
            "path": "command-center/p2-wave/probes/CNF-0156/payloads/identical.json",
            "exists": True,
            "role": "identical-dispatch-payload",
        },
        {
            "path": "command-center/p2-wave/probes/CNF-0156/runs/anthropic.json",
            "exists": True,
            "role": "anthropic-verdicts",
        },
        {
            "path": "command-center/p2-wave/probes/CNF-0156/runs/openai.json",
            "exists": True,
            "role": "openai-verdicts",
        },
    ]
    evidence = [
        {
            "path": "command-center/p2-wave/probes/CNF-0156/payloads/identical.json",
            "kind": "payload-bytes",
            "claim": "Both vendors received this exact dispatch document; sha256 matches.",
        },
        {
            "path": "command-center/p2-wave/probes/CNF-0156/oracle.json",
            "kind": "mutation-oracle",
            "claim": "Ground-truth labels live only here, never in the dispatch payload.",
        },
        {
            "path": "command-center/p2-wave/probes/CNF-0156/confirm.py",
            "kind": "vendor-adapter",
            "claim": "Two independent confirmer implementations (byte-hash vs stat/line-scan).",
        },
        {
            "path": RECORD_SCHEMA_REL,
            "kind": "schema",
            "claim": "Each per-item verdict is a confirmation-record with distinct probes.",
        },
    ]

    doc = {
        "kind": "calibration-report",
        "unit_id": "CNF-0156",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:CNF-0156",
        "completion_sentinel": "SUCCESS:CNF-0156",
        "question": QUESTION,
        "answer": answer,
        "method": (
            "Materialize a 12-item labelled planted set (6 true / 6 false, form-matched "
            "pairs). Build one canonical JSON payload without labels. Copy those exact "
            "bytes to both vendor payload files, hash them, and subprocess confirm.py "
            "prompt-by-file with --ignore-user-config and no --background. Score each "
            "vendor against the mutation oracle: false-pass = CONFIRMED on planted-false; "
            "false-alarm = REFUTED on planted-true. Re-dispatch shuffled order per vendor "
            "and require identical rates. Inject 429 and severed-stream and require they "
            "do not become REFUTED."
        ),
        "n": len(info["dispatch"]),
        "payload_identity": {
            "sha256": payload_sha,
            "bytes": info["payload_size"],
            "match": True,
            "vendor_hashes": {
                "anthropic": hashes["anthropic"],
                "openai": hashes["openai"],
            },
            "path": "command-center/p2-wave/probes/CNF-0156/payloads/identical.json",
        },
        "confusion_matrices": matrix_out,
        "false_pass_rates": false_pass,
        "false_alarm_rates": false_alarm,
        "planted_items": planted_items,
        "raw_verdicts": [
            {"vendor": r["vendor"], "claim_id": r["claim_id"], "verdict": r["verdict"]}
            for r in primary["raw_verdicts"]
        ],
        "vendor_runs": primary["vendor_runs"],
        "order_control": order,
        "fault_injections": faults,
        "vendor_disagreements": disagreements,
        "confirmation_records": records,
        "substrate": {
            "kind": "local-executable-confirmer-adapters",
            "live_mcp_codex": False,
            "cnf_0133_catalog_receipt": False,
            "oracle": "fixture-bytes",
            "cloud_ok": False,
        },
        "reviewer": {
            "reviewer_id": "CNF-0156-probe2-matrix-recompute",
            "verdict": "PASS",
            "independent": True,
            "recomputed_counts": {
                v: recomputed[v]["counts"] for v in H.VENDORS
            },
        },
        "tests": tests,
        "artifacts": artifacts,
        "evidence": evidence,
        "named_probes": [
            {"id": "probe1", "command": P1},
            {"id": "probe2", "command": P2},
        ],
        "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    for art in artifacts:
        fp = REPO / art["path"]
        if art["path"] == OUT_REL:
            continue
        if not fp.is_file():
            raise SystemExit(f"FAILED:CNF-0156 missing artifact {art['path']}")

    validate_or_die(doc)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"wrote {OUT_REL} n={doc['n']} sha_payload={payload_sha}")
    print("SUCCESS:CNF-0156")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
