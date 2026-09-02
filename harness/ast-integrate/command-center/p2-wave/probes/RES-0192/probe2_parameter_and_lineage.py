#!/usr/bin/env python3
"""Probe 2: independent recompute of diffs, fingerprints, lineage, schema."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from catalog import CLAIMS, RAPID_PARAMS, SENTINEL, SYSTEMATIC_PARAMS, UNIT  # noqa: E402
from capture import body_bytes, load_index  # noqa: E402
from measure import run  # noqa: E402
from protocol import extract_claims, params_fingerprint  # noqa: E402

ART = (
    REPO
    / "command-center/research/deep-research-design/"
    / "RES-0192-rapid-versus-systematic-review-protocol.json"
)
SCHEMA = REPO / "command-center/schema/measurement-run.schema.json"


def fail(msg: str) -> int:
    print(f"FAILED:RES-0192-probe2 {msg}")
    return 1


def main() -> int:
    idx = load_index()
    live = run(idx)
    fp_r = params_fingerprint(RAPID_PARAMS)
    fp_s = params_fingerprint(SYSTEMATIC_PARAMS)
    if fp_r == fp_s:
        return fail("rapid and systematic fingerprints identical")

    rails = {r["id"]: r for r in (idx.get("rails") or [])}
    for rid, rec in rails.items():
        raw = body_bytes(rid)
        got = hashlib.sha256(raw).hexdigest()
        if got != rec.get("sha256"):
            return fail(f"index sha256 drift {rid}")
        if rec.get("http_status") != 200:
            return fail(f"{rid} http_status {rec.get('http_status')}")

    for q in live["questions"]:
        qid = q["question_id"]
        rapid_ids = {c["id"] for c in extract_claims(qid, RAPID_PARAMS, idx)}
        sys_ids = {c["id"] for c in extract_claims(qid, SYSTEMATIC_PARAMS, idx)}
        if rapid_ids != set(q["diff"]["rapid_claim_ids"]):
            return fail(f"{qid} rapid claim-set drift")
        if sys_ids != set(q["diff"]["systematic_claim_ids"]):
            return fail(f"{qid} systematic claim-set drift")
        for claim in q["systematic_claims"]:
            lin = claim.get("lineage") or {}
            sid = claim["source_id"]
            rec = rails.get(sid) or {}
            if lin.get("sha256") != rec.get("sha256"):
                return fail(f"{claim['id']} lineage sha256 != snapshot")
            if not lin.get("resolved_url"):
                return fail(f"{claim['id']} missing resolved_url")
            if not lin.get("fetch_timestamp"):
                return fail(f"{claim['id']} missing fetch_timestamp")
            if len(claim.get("signals") or []) < 1:
                return fail(f"{claim['id']} missing signals")
            kinds = {s.get("kind") for s in claim["signals"]}
            spec = next(c for c in CLAIMS if c["id"] == claim["id"])
            if spec.get("structured_source_id"):
                if "prose-source" not in kinds or "structured-api" not in kinds:
                    return fail(f"{claim['id']} missing dual rails")
            if not claim.get("sherman_kent_band"):
                return fail(f"{claim['id']} missing Sherman-Kent band")
            if not claim.get("independent_verification_path"):
                return fail(f"{claim['id']} missing independent verification path")

    if not ART.is_file():
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if SENTINEL not in text:
        return fail("sentinel absent")
    if doc.get("unit_id") != UNIT:
        return fail("unit_id")
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    jsonschema.Draft7Validator(schema).validate(doc)
    for garbage in ({"nope": True}, {"measurements": 1}, {}):
        if not list(jsonschema.Draft7Validator(schema).iter_errors(garbage)):
            return fail(f"schema accepted garbage {garbage}")

    stored_fp = (doc.get("protocol_parameters") or {}).get("fingerprints") or {}
    if stored_fp.get("rapid") != fp_r or stored_fp.get("systematic") != fp_s:
        return fail("artifact fingerprints drifted")

    stored_qs = (doc.get("recorded_runs") or {}).get("questions") or []
    live_by = {q["question_id"]: q for q in live["questions"]}
    for sq in stored_qs:
        lq = live_by[sq["question_id"]]
        stored_miss = {
            m["id"]
            for m in (sq.get("diff") or {}).get("decision_relevant_misses") or []
        }
        live_miss = {m["id"] for m in lq["diff"]["decision_relevant_misses"]}
        if stored_miss != live_miss:
            return fail(
                f"{sq['question_id']} stored miss-set drifted {stored_miss} vs {live_miss}"
            )

    print(
        json.dumps(
            {
                "rapid_fp": fp_r,
                "systematic_fp": fp_s,
                "n_rails": len(rails),
                "schema_ok": True,
                "pass": True,
            },
            sort_keys=True,
        )
    )
    print("SUCCESS:RES-0192-probe2 fingerprints + lineage + schema")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
