#!/usr/bin/env python3
"""CNF-0133 confirmation pipeline, B08-style mutants, suite, oracle, confirmer.

The registered confirmation suite checks only file_count and status. The mutation
oracle compares the full inventory report (count, status, sha256, names). Surviving
mutants change fields the suite does not observe; a test-rerun confirmer false-passes
those planted-false claims. That is the quantity this unit measures.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
import re
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
LOCAL_RECORD_SCHEMA = HERE / "confirmation-record.schema.json"
SUITE_FIELDS = ("file_count", "status")
ORACLE_FIELDS = ("file_count", "status", "sha256", "names")
CLAIM_TEMPLATE = (
    "On subject {subject_id} the inventory report matches the stated snapshot."
)
CONFIRMER_ID = "mechanical-testrerun-cnf0133"
CONFIRMER_VENDOR = "local-pipeline"
LEAKAGE_TOKENS = (
    "planted",
    "ground_truth",
    "ground-truth",
    "oracle_label",
    "oracle-labels",
    "false-pass",
    "false_pass",
    "is_false",
    "is_true",
    "plant_label",
    "killed",
    "surviving",
    "mutation_id",
    "mutant_id",
    "count_plus_one",
    "count_minus_one",
    "status_forced_empty",
    "zero_count",
    "hash_xor",
    "hash_upper",
    "names_reversed",
    "names_by_length",
)


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def sha256_text(text: str) -> str:
    return sha256_bytes(text.encode("utf-8"))


def opaque_id(prefix: str, *parts: str) -> str:
    body = sha256_text("|".join(parts))[:12]
    return f"{prefix}{body}"


def iter_files(root: Path) -> list[Path]:
    files = [p for p in root.rglob("*") if p.is_file()]
    return sorted(files, key=lambda p: p.relative_to(root).as_posix())


def inventory_report(root: Path) -> dict[str, Any]:
    files = iter_files(root)
    names = [p.relative_to(root).as_posix() for p in files]
    h = hashlib.sha256()
    for p in files:
        h.update(p.relative_to(root).as_posix().encode("utf-8"))
        h.update(b"\0")
        h.update(p.read_bytes())
    return {
        "file_count": len(files),
        "sha256": h.hexdigest(),
        "status": "ok" if files else "empty",
        "names": names,
    }


def _xor_last_nibble(digest: str) -> str:
    nibble = int(digest[-1], 16) ^ 1
    return digest[:-1] + format(nibble, "x")


def apply_mutant(report: dict[str, Any], mutant: str) -> dict[str, Any]:
    out = copy.deepcopy(report)
    if mutant in {"", "baseline", "none"}:
        return out
    if mutant == "count_plus_one":
        out["file_count"] = int(out["file_count"]) + 1
    elif mutant == "count_minus_one":
        out["file_count"] = max(0, int(out["file_count"]) - 1)
    elif mutant == "zero_count":
        out["file_count"] = 0
    elif mutant == "status_forced_empty":
        out["status"] = "empty"
    elif mutant == "hash_xor":
        out["sha256"] = _xor_last_nibble(str(out["sha256"]))
    elif mutant == "hash_upper":
        out["sha256"] = str(out["sha256"]).upper()
    elif mutant == "names_reversed":
        out["names"] = list(reversed(list(out["names"])))
    elif mutant == "names_by_length":
        out["names"] = sorted(list(out["names"]), key=lambda n: (len(n), n))
    else:
        raise ValueError(f"unknown mutant {mutant}")
    return out


def reports_equal(a: dict[str, Any], b: dict[str, Any], fields: tuple[str, ...]) -> bool:
    for f in fields:
        if a.get(f) != b.get(f):
            return False
    return True


def field_diffs(a: dict[str, Any], b: dict[str, Any], fields: tuple[str, ...]) -> list[dict[str, Any]]:
    rows = []
    for f in fields:
        if a.get(f) != b.get(f):
            rows.append({"field": f, "left": a.get(f), "right": b.get(f)})
    return rows


def run_suite(produced: dict[str, Any], claimed: dict[str, Any]) -> dict[str, Any]:
    """Registered confirmation tests: count and status only."""
    diffs = field_diffs(produced, claimed, SUITE_FIELDS)
    return {
        "id": "cnf0133-count-status-suite",
        "pass": not diffs,
        "checked_fields": list(SUITE_FIELDS),
        "failures": diffs,
    }


def oracle_verdict(produced: dict[str, Any], claimed: dict[str, Any]) -> dict[str, Any]:
    """Independent mutation oracle: full report equality. Never passed to confirmer."""
    diffs = field_diffs(produced, claimed, ORACLE_FIELDS)
    return {
        "id": "cnf0133-full-report-oracle",
        "equal": not diffs,
        "checked_fields": list(ORACLE_FIELDS),
        "failures": diffs,
    }


def classify_mutant(baseline: dict[str, Any], mutant: str) -> str:
    produced = apply_mutant(baseline, mutant)
    suite = run_suite(produced, baseline)
    oracle = oracle_verdict(produced, baseline)
    if oracle["equal"]:
        return "equivalent"
    if suite["pass"]:
        return "surviving"
    return "killed"


def fingerprint_probe(probe_id: str, payload: dict[str, Any]) -> str:
    blob = json.dumps({"id": probe_id, "payload": payload}, sort_keys=True, separators=(",", ":"))
    return sha256_text(blob)


def snapshot_of(report: dict[str, Any]) -> dict[str, Any]:
    return {
        "file_count": report["file_count"],
        "status": report["status"],
        "sha256": report["sha256"],
        "names": list(report["names"]),
    }


def make_claim(
    *,
    set_id: str,
    subject_id: str,
    claimed: dict[str, Any],
    produced: dict[str, Any],
) -> dict[str, Any]:
    """Confirmer-visible claim. No oracle labels, no mutant names, no produced blob."""
    snap = snapshot_of(claimed)
    claim_id = opaque_id("CLM-0133-", set_id, subject_id, snap["sha256"], produced["sha256"])
    source_payload = {
        "subject_id": subject_id,
        "checked_fields": list(SUITE_FIELDS),
        "expect_file_count": snap["file_count"],
        "expect_status": snap["status"],
    }
    return {
        "claim_id": claim_id,
        "text": CLAIM_TEMPLATE.format(subject_id=subject_id),
        "subject_id": subject_id,
        "asserted": snap,
        "source_probe": {
            "id": "suite-count-status",
            "fingerprint": fingerprint_probe("suite-count-status", source_payload),
            "checked_fields": list(SUITE_FIELDS),
        },
    }


def confirm_claim(
    claim: dict[str, Any],
    subjects: dict[str, dict[str, Any]],
    *,
    blinding_hash: str,
) -> dict[str, Any]:
    """Test-rerun confirmer. Sees the claim and subject store; does not consult labels."""
    produced = subjects[claim["subject_id"]]
    asserted = claim["asserted"]
    suite = run_suite(produced, asserted)
    verifier_payload = {
        "subject_id": claim["subject_id"],
        "checked_fields": list(SUITE_FIELDS),
        "expect_file_count": asserted["file_count"],
        "expect_status": asserted["status"],
        "independent": True,
    }
    verifier = {
        "id": "verifier-count-status",
        "fingerprint": fingerprint_probe("verifier-count-status", verifier_payload),
        "checked_fields": list(SUITE_FIELDS),
        "pass": suite["pass"],
        "failures": suite["failures"],
    }
    source_fp = str(claim["source_probe"]["fingerprint"])
    if source_fp == verifier["fingerprint"]:
        verdict = "BLOCKED"
        residual = "same-probe-rerun: source_probe fingerprint equals verifier_probe"
        discrepancies = [{"class": "same-probe-rerun", "detail": residual}]
    elif suite["pass"]:
        verdict = "CONFIRMED"
        residual = "Registered suite observed no count/status disagreement."
        discrepancies = []
    else:
        verdict = "REFUTED"
        residual = "Registered suite observed a count/status disagreement."
        discrepancies = list(suite["failures"])
    record = {
        "schema_version": 1,
        "unit_id": "CNF-0133",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:CNF-0133",
        "claim_id": claim["claim_id"],
        "confirmer": {"id": CONFIRMER_ID, "vendor": CONFIRMER_VENDOR},
        "blinding_attestation_hash": blinding_hash,
        "baseline_repro": {
            "suite_id": suite["id"],
            "pass": suite["pass"],
            "checked_fields": suite["checked_fields"],
        },
        "corrected_repro": None,
        "rollback_repro": None,
        "regression_diff": suite["failures"],
        "discrepancies": discrepancies,
        "verdict": verdict,
        "source_probe": copy.deepcopy(claim["source_probe"]),
        "verifier_probe": verifier,
        "residual_caveat": residual,
    }
    return record


def naive_confirm(claim: dict[str, Any], *, blinding_hash: str) -> dict[str, Any]:
    """Rubber-stamp confirmer: well-formed claims are CONFIRMED. Detector control."""
    required = ("claim_id", "text", "asserted", "subject_id", "source_probe")
    ok = all(k in claim for k in required)
    return {
        "claim_id": claim["claim_id"],
        "confirmer": {"id": "naive-wellformed", "vendor": CONFIRMER_VENDOR},
        "blinding_attestation_hash": blinding_hash,
        "baseline_repro": None,
        "corrected_repro": None,
        "rollback_repro": None,
        "regression_diff": None,
        "discrepancies": [] if ok else [{"class": "malformed"}],
        "verdict": "CONFIRMED" if ok else "BLOCKED",
        "source_probe": copy.deepcopy(claim.get("source_probe") or {"id": "absent", "fingerprint": "x" * 16}),
        "verifier_probe": {"id": "none", "fingerprint": "y" * 16},
        "residual_caveat": "Naive confirmer does not re-run tests.",
    }


def scan_leakage(blobs: list[str]) -> list[str]:
    found: list[str] = []
    for blob in blobs:
        low = blob.lower()
        for tok in LEAKAGE_TOKENS:
            if tok.lower() in low:
                found.append(tok)
    return sorted(set(found))


def claim_form_ok(claims: list[dict[str, Any]]) -> tuple[bool, str]:
    if len(claims) < 2:
        return False, "need at least two claims"
    keys = None
    for c in claims:
        k = tuple(sorted(c.keys()))
        if keys is None:
            keys = k
        elif k != keys:
            return False, f"key mismatch {k} vs {keys}"
        text = str(c.get("text") or "")
        if not re.fullmatch(r"On subject SUBJ-[0-9a-f]{12} the inventory report matches the stated snapshot\.", text):
            return False, f"template mismatch: {text}"
        asserted = c.get("asserted") or {}
        for field in ORACLE_FIELDS:
            if field not in asserted:
                return False, f"asserted missing {field}"
    return True, "identical-form"


def confusion(rows: list[dict[str, Any]]) -> dict[str, int]:
    tp = fp = fn = tn = 0
    for r in rows:
        label = r["oracle_label"]
        verd = r["confirmer_verdict"]
        if verd not in {"CONFIRMED", "REFUTED"}:
            continue
        if label == "true" and verd == "CONFIRMED":
            tp += 1
        elif label == "true" and verd == "REFUTED":
            fn += 1
        elif label == "false" and verd == "CONFIRMED":
            fp += 1
        elif label == "false" and verd == "REFUTED":
            tn += 1
    return {
        "true_positive": tp,
        "false_positive": fp,
        "false_negative": fn,
        "true_negative": tn,
    }


def false_pass_rate(matrix: dict[str, int]) -> dict[str, Any]:
    num = int(matrix["false_positive"])
    den = int(matrix["false_positive"]) + int(matrix["true_negative"])
    value = (num / den) if den else None
    return {"numerator": num, "denominator": den, "value": value}


def wilson_interval(k: int, n: int, z: float = 1.96) -> dict[str, Any] | None:
    if n <= 0:
        return None
    p = k / n
    z2 = z * z
    denom = 1.0 + z2 / n
    center = (p + z2 / (2.0 * n)) / denom
    margin = z * math.sqrt((p * (1.0 - p) + z2 / (4.0 * n)) / n) / denom
    return {
        "k": k,
        "n": n,
        "z": z,
        "low": max(0.0, center - margin),
        "high": min(1.0, center + margin),
    }


def blinding_hash(claims: list[dict[str, Any]]) -> str:
    payload = [{"claim_id": c["claim_id"], "text": c["text"], "asserted": c["asserted"]} for c in claims]
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return sha256_text(blob)


def load_confirmation_record_schema() -> dict[str, Any]:
    """Load the local closed record schema (never the catalog generic_report shim)."""
    return json.loads(LOCAL_RECORD_SCHEMA.read_text(encoding="utf-8"))


def validate_record_shape(record: dict[str, Any], schema: dict[str, Any] | None = None) -> list[str]:
    try:
        import jsonschema
    except ImportError:
        return ["jsonschema-missing"]
    if schema is None:
        schema = load_confirmation_record_schema()
    return [e.message for e in jsonschema.Draft7Validator(schema).iter_errors(record)]


def unsourced_confirmed_rejected(schema: dict[str, Any] | None = None) -> bool:
    """CNF-0129 hole: CONFIRMED with empty source_probe must be invalid."""
    try:
        import jsonschema
    except ImportError:
        return False
    if schema is None:
        schema = load_confirmation_record_schema()
    bad = {
        "claim_id": "CLM-0133-deadbeef012",
        "confirmer": {"id": "x", "vendor": "local"},
        "blinding_attestation_hash": "a" * 16,
        "verdict": "CONFIRMED",
        "source_probe": {},
        "verifier_probe": {"id": "v", "fingerprint": "b" * 16},
        "discrepancies": [],
        "residual_caveat": "none",
    }
    return bool(list(jsonschema.Draft7Validator(schema).iter_errors(bad)))
