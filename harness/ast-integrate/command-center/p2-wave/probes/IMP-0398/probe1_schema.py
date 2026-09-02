#!/usr/bin/env python3
"""Probe 1: corpus schema test + 25% negatives + kappa recompute."""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import kappa as K  # noqa: E402
import schema_util as SU  # noqa: E402

ART = REPO / "command-center/receipts/IMP-0398.json"
SENTINEL = "SENTINEL:IMP-0398:ROUTER-CORPUS-BASELINE-DEFEATING"


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0398-probe1 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    if SENTINEL not in text:
        return fail("sentinel-absent")
    doc = json.loads(text)
    if doc.get("unit_id") != "IMP-0398":
        return fail(f"unit_id={doc.get('unit_id')}")
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared:{st}")
    if not SU.shim_is_generated():
        return fail("catalog shim grew local constraints (ADV rebuild)")

    env = SU.envelope_validator()
    pay = SU.payload_validator()
    env_errs = SU.error_messages(env, doc)
    if env_errs:
        print(env_errs[0])
        return fail(f"envelope-invalid {len(env_errs)} errors")

    try:
        report = SU.report_of(doc)
    except ValueError as exc:
        return fail(str(exc))
    pay_errs = SU.error_messages(pay, report)
    if pay_errs:
        print(pay_errs[0])
        return fail(f"payload-invalid {len(pay_errs)} errors")

    garbage_rejected = 0
    for garbage in (
        {},
        {"totally": "unrelated", "passing_tests": 999999},
        {"blob": "x" * 2000},
    ):
        if not SU.error_messages(env, garbage):
            return fail("schema accepted garbage")
        garbage_rejected += 1

    queries = list(report.get("queries") or [])
    if len(queries) < 20:
        return fail(f"n={len(queries)} < 20")
    n_neg = 0
    for q in queries:
        exp = q.get("expected_capability_ids") or []
        pol = str(q.get("polarity") or "").upper()
        if pol == "NEGATIVE":
            n_neg += 1
            if exp:
                return fail(f"{q.get('id')} NEGATIVE but expected={exp}")
        elif pol == "POSITIVE":
            if not exp:
                return fail(f"{q.get('id')} POSITIVE but empty expected")
        else:
            return fail(f"{q.get('id')} polarity={pol}")
        if not str(q.get("rationale") or "").strip():
            return fail(f"{q.get('id')} missing rationale")
    frac = n_neg / len(queries)
    declared = float((report.get("corpus_stats") or {}).get("negative_fraction") or 0)
    if abs(frac - declared) > 1e-9:
        return fail(f"stats lie declared={declared} live={frac}")
    if frac < 0.25:
        return fail(f"negative_fraction={frac} < 0.25")

    thin = copy.deepcopy(doc)
    trep = thin["report"]
    for q in trep["queries"]:
        if q.get("polarity") == "NEGATIVE":
            q["polarity"] = "POSITIVE"
            q["expected_capability_ids"] = ["skill.web.search"]
            q["rationale"] = "mutated to drop negatives for schema control"
    trep["corpus_stats"] = {
        "n": len(trep["queries"]),
        "n_negative": 0,
        "negative_fraction": 0.0,
        "n_positive": len(trep["queries"]),
    }
    if not SU.error_messages(pay, trep):
        return fail("schema accepted 0% negative corpus")
    # Catalog shim must NOT be the thing that rejects 0% negatives (it cannot).
    if SU.error_messages(env, thin):
        return fail("catalog shim rejected a structurally-valid 0% envelope")

    kap = K.relabel_and_kappa(queries, seed=398, fraction=0.10)
    declared_k = float((report.get("kappa") or {}).get("value") or -9)
    if abs(kap["value"] - declared_k) > 1e-9:
        return fail(f"kappa mismatch live={kap['value']} declared={declared_k}")
    if kap["value"] < 0.7:
        return fail(f"kappa={kap['value']} < 0.7")
    if set(kap["sample_ids"]) != set((report.get("kappa") or {}).get("sample_ids") or []):
        return fail("kappa sample_ids drifted")

    out = {
        "pass": True,
        "probe": "probe1-schema",
        "unit_id": "IMP-0398",
        "n": len(queries),
        "n_negative": n_neg,
        "negative_fraction": frac,
        "kappa": kap["value"],
        "garbage_rejected": garbage_rejected,
        "zero_negative_rejected": True,
    }
    print(json.dumps(out, sort_keys=True))
    print(
        f"n={len(queries)} neg={n_neg} frac={frac:.4f} kappa={kap['value']:.4f} "
        f"garbage_rejected={garbage_rejected}"
    )
    print("SUCCESS:IMP-0398-probe1 corpus schema and negative-query floor")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
