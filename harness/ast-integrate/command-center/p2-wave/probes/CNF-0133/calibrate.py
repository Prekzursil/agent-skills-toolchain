#!/usr/bin/env python3
"""Plant two disjoint labelled sets and run the CNF-0133 confirmation pipeline."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pipeline import (
    apply_mutant,
    blinding_hash,
    claim_form_ok,
    classify_mutant,
    confirm_claim,
    confusion,
    false_pass_rate,
    inventory_report,
    make_claim,
    naive_confirm,
    opaque_id,
    oracle_verdict,
    scan_leakage,
    snapshot_of,
    unsourced_confirmed_rejected,
    validate_record_shape,
    wilson_interval,
)

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]

# Disjoint planted sets. Each false claim is the baseline snapshot asserted
# against a mutated subject. True claims assert the baseline against baseline.
SET_PLANTS: dict[str, dict[str, Any]] = {
    "set_a": {
        "fixture": HERE / "fixtures" / "set_a",
        "true_n": 4,
        "false_mutants": [
            "count_plus_one",
            "status_forced_empty",
            "hash_xor",
            "names_reversed",
        ],
    },
    "set_b": {
        "fixture": HERE / "fixtures" / "set_b",
        "true_n": 4,
        "false_mutants": [
            "count_minus_one",
            "zero_count",
            "hash_upper",
            "names_reversed",
        ],
    },
}

ALL_OPERATORS = (
    "count_plus_one",
    "count_minus_one",
    "zero_count",
    "status_forced_empty",
    "hash_xor",
    "hash_upper",
    "names_reversed",
    "names_by_length",
)


def load_schema(rel: str) -> dict[str, Any]:
    return json.loads((REPO / rel).read_text(encoding="utf-8"))


def corpus_for(fixture: Path) -> dict[str, Any]:
    baseline = inventory_report(fixture)
    rows = []
    for mutant in ALL_OPERATORS:
        produced = apply_mutant(baseline, mutant)
        klass = classify_mutant(baseline, mutant)
        oracle = oracle_verdict(produced, baseline)
        rows.append(
            {
                "operator": mutant,
                "class": klass,
                "oracle_diff_fields": [d["field"] for d in oracle["failures"]],
            }
        )
    return {
        "fixture": fixture.relative_to(REPO).as_posix() if fixture.is_relative_to(REPO) else str(fixture),
        "baseline": snapshot_of(baseline),
        "mutants": rows,
        "killed": [r["operator"] for r in rows if r["class"] == "killed"],
        "surviving": [r["operator"] for r in rows if r["class"] == "surviving"],
        "equivalent": [r["operator"] for r in rows if r["class"] == "equivalent"],
    }


def plant_set(set_id: str) -> dict[str, Any]:
    spec = SET_PLANTS[set_id]
    fixture: Path = spec["fixture"]
    baseline = inventory_report(fixture)
    subjects: dict[str, dict[str, Any]] = {}
    claims: list[dict[str, Any]] = []
    labels: dict[str, dict[str, Any]] = {}

    base_sid = opaque_id("SUBJ-", set_id, "baseline", baseline["sha256"])
    subjects[base_sid] = snapshot_of(baseline)

    for i in range(int(spec["true_n"])):
        sid = base_sid if i == 0 else opaque_id("SUBJ-", set_id, "baseline", str(i), baseline["sha256"])
        subjects[sid] = snapshot_of(baseline)
        claim = make_claim(set_id=set_id, subject_id=sid, claimed=baseline, produced=baseline)
        claims.append(claim)
        labels[claim["claim_id"]] = {
            "oracle_label": "true",
            "role": "planted-true",
            "set_id": set_id,
            "operator": "baseline",
            "operator_class": "none",
            "subject_id": sid,
        }

    for mutant in spec["false_mutants"]:
        produced = apply_mutant(baseline, mutant)
        klass = classify_mutant(baseline, mutant)
        if klass == "equivalent":
            raise RuntimeError(f"{set_id} operator {mutant} is equivalent; cannot plant a false claim")
        sid = opaque_id("SUBJ-", set_id, mutant, produced["sha256"])
        subjects[sid] = snapshot_of(produced)
        claim = make_claim(set_id=set_id, subject_id=sid, claimed=baseline, produced=produced)
        claims.append(claim)
        labels[claim["claim_id"]] = {
            "oracle_label": "false",
            "role": "planted-false",
            "set_id": set_id,
            "operator": mutant,
            "operator_class": klass,
            "subject_id": sid,
        }

    # Mix two unlabelled "real" baseline claims (same form; excluded from 2x2).
    for i in range(2):
        sid = opaque_id("SUBJ-", set_id, "real", str(i), baseline["sha256"])
        subjects[sid] = snapshot_of(baseline)
        claim = make_claim(set_id=set_id + "-real", subject_id=sid, claimed=baseline, produced=baseline)
        claims.append(claim)
        labels[claim["claim_id"]] = {
            "oracle_label": "true",
            "role": "real",
            "set_id": set_id,
            "operator": "baseline",
            "operator_class": "none",
            "subject_id": sid,
        }

    return {
        "set_id": set_id,
        "fixture": fixture.relative_to(HERE).as_posix(),
        "baseline": snapshot_of(baseline),
        "subjects": subjects,
        "claims": claims,
        "labels": labels,
        "corpus": corpus_for(fixture),
    }


def run_confirmer(plant: dict[str, Any]) -> dict[str, Any]:
    claims = plant["claims"]
    subjects = plant["subjects"]
    labels = plant["labels"]
    bhash = blinding_hash(claims)
    records = []
    naive_records = []
    planted_rows = []
    inbox_blobs = [json.dumps(c, sort_keys=True) for c in claims]
    inbox_blobs.extend(json.dumps(subjects[s], sort_keys=True) for s in subjects)
    leaks = scan_leakage(inbox_blobs)
    form_ok, form_why = claim_form_ok(claims)

    rec_schema = load_schema("command-center/schema/confirmation-record.schema.json")
    for claim in claims:
        rec = confirm_claim(claim, subjects, blinding_hash=bhash)
        errs = validate_record_shape(rec, rec_schema)
        if errs:
            raise RuntimeError(f"record schema {claim['claim_id']}: {errs[:3]}")
        if rec["source_probe"]["fingerprint"] == rec["verifier_probe"]["fingerprint"]:
            raise RuntimeError("same-probe-rerun slipped through")
        records.append(rec)
        naive_records.append(naive_confirm(claim, blinding_hash=bhash))
        lab = labels[claim["claim_id"]]
        if lab["role"] in {"planted-true", "planted-false"}:
            planted_rows.append(
                {
                    "claim_id": claim["claim_id"],
                    "subject_id": claim["subject_id"],
                    "set_id": lab["set_id"],
                    "oracle_label": lab["oracle_label"],
                    "confirmer_verdict": rec["verdict"],
                    "naive_verdict": naive_records[-1]["verdict"],
                    "operator": lab["operator"],
                    "operator_class": lab["operator_class"],
                    "role": lab["role"],
                    "source_probe_fingerprint": rec["source_probe"]["fingerprint"],
                    "verifier_probe_fingerprint": rec["verifier_probe"]["fingerprint"],
                }
            )

    matrix = confusion(planted_rows)
    fpr = false_pass_rate(matrix)
    naive_fp = sum(1 for r in planted_rows if r["oracle_label"] == "false" and r["naive_verdict"] == "CONFIRMED")
    n_false = sum(1 for r in planted_rows if r["oracle_label"] == "false")
    return {
        "blinding_attestation_hash": bhash,
        "records": records,
        "naive_records": naive_records,
        "planted_items": planted_rows,
        "confusion_matrix": matrix,
        "false_pass_rate": fpr,
        "wilson": wilson_interval(fpr["numerator"], fpr["denominator"]),
        "leakage_tokens_found": leaks,
        "form_ok": form_ok,
        "form_why": form_why,
        "naive_false_pass": {"numerator": naive_fp, "denominator": n_false},
        "unsourced_confirmed_rejected": unsourced_confirmed_rejected(rec_schema),
        "inbox_claim_ids": [c["claim_id"] for c in claims],
    }


def both_states(rows: list[dict[str, Any]]) -> dict[str, Any]:
    tp = any(r["oracle_label"] == "true" and r["confirmer_verdict"] == "CONFIRMED" for r in rows)
    tn = any(r["oracle_label"] == "false" and r["confirmer_verdict"] == "REFUTED" for r in rows)
    return {"planted_true_confirmed": tp, "planted_false_refuted": tn, "pass": bool(tp and tn)}


def run_calibration() -> dict[str, Any]:
    plants = {sid: plant_set(sid) for sid in ("set_a", "set_b")}
    runs = {sid: run_confirmer(plants[sid]) for sid in plants}

    combined_rows = runs["set_a"]["planted_items"] + runs["set_b"]["planted_items"]
    combined_matrix = confusion(combined_rows)
    combined_fpr = false_pass_rate(combined_matrix)
    bs_a = both_states(runs["set_a"]["planted_items"])
    bs_b = both_states(runs["set_b"]["planted_items"])
    bs_all = both_states(combined_rows)

    leaks = sorted(set(runs["set_a"]["leakage_tokens_found"] + runs["set_b"]["leakage_tokens_found"]))
    form_ok = runs["set_a"]["form_ok"] and runs["set_b"]["form_ok"]

    fpr_a = runs["set_a"]["false_pass_rate"]["value"]
    fpr_b = runs["set_b"]["false_pass_rate"]["value"]
    stable = fpr_a is not None and fpr_b is not None and fpr_a == fpr_b

    naive_fp_all = (
        runs["set_a"]["naive_false_pass"]["numerator"] + runs["set_b"]["naive_false_pass"]["numerator"]
    )
    n_false_all = (
        runs["set_a"]["naive_false_pass"]["denominator"] + runs["set_b"]["naive_false_pass"]["denominator"]
    )

    tests = [
        {
            "id": "blind-form",
            "name": "Planted-false claims share form with real/true claims",
            "result": "PASS" if form_ok else "FAIL",
            "detail": {"set_a": runs["set_a"]["form_why"], "set_b": runs["set_b"]["form_why"]},
        },
        {
            "id": "both-states",
            "name": "At least one planted-true CONFIRMED and one planted-false REFUTED",
            "result": "PASS" if bs_all["pass"] else "FAIL",
            "detail": {"combined": bs_all, "set_a": bs_a, "set_b": bs_b},
        },
        {
            "id": "leakage-control",
            "name": "Confirmer inbox contains no plant-list tokens",
            "result": "PASS" if not leaks else "FAIL",
            "detail": {"tokens_found": leaks},
        },
        {
            "id": "rerun-stability",
            "name": "False-pass rate re-measured on disjoint set_b",
            "result": "PASS" if stable else "FAIL",
            "detail": {
                "set_a": runs["set_a"]["false_pass_rate"],
                "set_b": runs["set_b"]["false_pass_rate"],
            },
        },
        {
            "id": "naive-hazard",
            "name": "Naive confirmer false-passes every planted-false claim (plants are real hazards)",
            "result": "PASS" if naive_fp_all == n_false_all and n_false_all > 0 else "FAIL",
            "detail": {"naive_false_pass": naive_fp_all, "n_false": n_false_all},
        },
        {
            "id": "unsourced-confirmed-unrepresentable",
            "name": "CONFIRMED with empty source_probe is schema-invalid",
            "result": "PASS" if runs["set_a"]["unsourced_confirmed_rejected"] else "FAIL",
        },
    ]

    return {
        "plants": plants,
        "runs": runs,
        "combined_rows": combined_rows,
        "combined_matrix": combined_matrix,
        "combined_fpr": combined_fpr,
        "combined_wilson": wilson_interval(combined_fpr["numerator"], combined_fpr["denominator"]),
        "both_states": {"combined": bs_all, "set_a": bs_a, "set_b": bs_b},
        "leakage_tokens_found": leaks,
        "form_ok": form_ok,
        "stability_equal": stable,
        "tests": tests,
        "corpus": {"set_a": plants["set_a"]["corpus"], "set_b": plants["set_b"]["corpus"]},
    }


def tests_pass(cal: dict[str, Any]) -> bool:
    return all(t.get("result") == "PASS" for t in cal["tests"])
