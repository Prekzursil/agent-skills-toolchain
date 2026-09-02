#!/usr/bin/env python3
"""Probe 2: independent recount, two-signal ablation, length/label not the measure.

Re-derives coverage from fixture JSON (set of restates ids + content-token
overlap) without trusting detector.reasons. Confirms S1 and S2 can fail
independently. Confirms padded length still FIRES. Confirms the artifact
schema rejects garbage and the live artifact is SUCCESS:CNL-0049.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import detector as D  # noqa: E402

FIX = HERE / "fixtures"
OUT = (
    "command-center/design/council/"
    "CNL-0049-steelman-enforcement-how-do-you-measure-that-a-steelman-ha.md"
)
SCHEMA = "command-center/schema/council-detector-spec.schema.json"
RAW = HERE / "probe2-independent.raw.json"


def fail(msg: str) -> int:
    print(f"FAILED:CNL-0049-probe2 {msg}")
    return 1


def restates_ids(doc: dict) -> set[str]:
    ids: set[str] = set()
    for turn in doc.get("turns") or []:
        for r in turn.get("restatements") or []:
            if isinstance(r, dict) and r.get("restates"):
                ids.add(str(r["restates"]))
        for ev in turn.get("events") or []:
            if isinstance(ev, dict) and ev.get("kind") == "restatement" and ev.get("restates"):
                ids.add(str(ev["restates"]))
    return ids


def mean_jaccard(doc: dict) -> float:
    claims = D.load_bearing_claims(doc)
    bodies: list[str] = []
    for turn in doc.get("turns") or []:
        for r in turn.get("restatements") or []:
            if isinstance(r, dict):
                bodies.append(str(r.get("text") or ""))
        for ev in turn.get("events") or []:
            if isinstance(ev, dict) and ev.get("kind") == "restatement":
                bodies.append(str(ev.get("text") or ""))
    if not claims:
        return 0.0
    scores = []
    for c in claims:
        src = D.content_tokens(str(c.get("text") or ""))
        best = 0.0
        for body in bodies:
            rst = D.content_tokens(body)
            union = src | rst
            if not union:
                continue
            best = max(best, len(src & rst) / len(union))
        scores.append(best)
    return sum(scores) / len(scores)


def main() -> int:
    genuine_doc = json.loads((FIX / "genuine.json").read_text(encoding="utf-8"))
    fake_doc = json.loads((FIX / "fake_token.json").read_text(encoding="utf-8"))
    padded = D.evaluate_path(FIX / "fake_padded.json")
    cov_ab = D.evaluate_path(FIX / "ablation_coverage.json")
    ord_ab = D.evaluate_path(FIX / "ablation_ordering.json")

    g_ids = restates_ids(genuine_doc)
    f_ids = restates_ids(fake_doc)
    g_j = mean_jaccard(genuine_doc)
    f_j = mean_jaccard(fake_doc)
    claim_ids = {c["id"] for c in D.load_bearing_claims(genuine_doc)}

    if g_ids != claim_ids:
        return fail(f"independent restates ids {g_ids} != {claim_ids}")
    if f_ids:
        return fail(f"token concession restates ids should be empty, got {f_ids}")
    if g_j < 0.2:
        return fail(f"genuine mean Jaccard too low: {g_j}")
    if f_j != 0.0:
        return fail(f"token concession Jaccard should be 0, got {f_j}")

    if not padded["fired"]:
        return fail("padded-length fake did not fire — length is not the measure")
    padded_bytes = (FIX / "fake_padded.json").stat().st_size
    genuine_bytes = (FIX / "genuine.json").stat().st_size
    if padded_bytes <= 200:
        return fail("padded fixture too small to be a length control")

    # Two-signal independence: coverage can fail while ordering is ok, and vice versa.
    if not (not cov_ab["coverage_ok"] and cov_ab["ordering_ok"] and cov_ab["fired"]):
        return fail(f"coverage ablation not independent: {cov_ab}")
    if not (ord_ab["coverage_ok"] and not ord_ab["ordering_ok"] and ord_ab["fired"]):
        return fail(f"ordering ablation not independent: {ord_ab}")

    schema = json.loads((REPO / SCHEMA).read_text(encoding="utf-8"))
    validator = jsonschema.Draft7Validator(schema)
    garbage = [{}, {"totally": "unrelated", "passing_tests": 999}, {"unit_id": "CNL-0049"}]
    rejected = 0
    for g in garbage:
        if list(validator.iter_errors(g)):
            rejected += 1
    if rejected != 3:
        return fail(f"schema garbage rejection {rejected}/3")

    art_path = REPO / OUT
    if not art_path.is_file():
        return fail(f"artifact missing {OUT}")
    artifact = json.loads(art_path.read_text(encoding="utf-8"))
    art_errs = sorted(validator.iter_errors(artifact), key=lambda e: list(e.path))
    if art_errs:
        return fail(f"artifact schema errors: {art_errs[0].message}")
    if artifact.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"artifact self-declared {artifact.get('state')}")
    if "SUCCESS:CNL-0049" not in art_path.read_text(encoding="utf-8"):
        return fail("sentinel absent")
    if artifact.get("both_states", {}).get("fired_on_bad") is not True:
        return fail("artifact both_states.fired_on_bad not true")
    if artifact.get("both_states", {}).get("silent_on_good") is not True:
        return fail("artifact both_states.silent_on_good not true")

    doc = {
        "genuine_restates_ids": sorted(g_ids),
        "fake_restates_ids": sorted(f_ids),
        "genuine_mean_jaccard": round(g_j, 4),
        "fake_mean_jaccard": round(f_j, 4),
        "padded_fired": True,
        "padded_bytes": padded_bytes,
        "genuine_bytes": genuine_bytes,
        "coverage_ablation": {
            "coverage_ok": cov_ab["coverage_ok"],
            "ordering_ok": cov_ab["ordering_ok"],
            "fired": cov_ab["fired"],
        },
        "ordering_ablation": {
            "coverage_ok": ord_ab["coverage_ok"],
            "ordering_ok": ord_ab["ordering_ok"],
            "fired": ord_ab["fired"],
        },
        "schema_garbage_rejected": 3,
        "pass": True,
    }
    RAW.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        f"independent_restates genuine={sorted(g_ids)} fake={sorted(f_ids)} "
        f"jaccard_g={g_j:.3f} jaccard_f={f_j:.3f}"
    )
    print(
        "ablation coverage_ok/ordering_ok "
        f"cov={cov_ab['coverage_ok']}/{cov_ab['ordering_ok']} "
        f"ord={ord_ab['coverage_ok']}/{ord_ab['ordering_ok']} "
        f"padded_fired=True schema_garbage_rejected=3/3"
    )
    print("SUCCESS:CNL-0049-probe2 independent recount two-signal ablation")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
