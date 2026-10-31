"""CNF-0133 calibrate: mutant corpus + blind protocol, fully deterministic.

Each planted set: 4 true baseline claims + 4 falsified claims. Killed-class
mutations falsify the fields the suite CHECKS (count/status) and must be
REFUTED; surviving-class mutations falsify only decoy fields the suite does
NOT check (sha/names) and become false passes. The inbox is blind (identical
form regardless of label). Rebuilt 2026-10-26 (wave-3 shard 7).
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
import pipeline  # noqa: E402

FILES = {
    "one.txt": "cnf0133 set fixture line one\n",
    "two.txt": "cnf0133 set fixture line two\n",
    "nested/three.txt": "cnf0133 set fixture line three\n",
    "nested/four.txt": "cnf0133 set fixture line four\n",
}
OPS_SET_A = {
    "killed": ["count_plus_one", "status_forced_empty"],
    "surviving": ["hash_xor", "names_reversed"],
}
OPS_SET_B = {
    "killed": ["count_minus_one", "zero_count"],
    "surviving": ["hash_upper", "names_by_length"],
}
LEAK_TOKENS = ("planted", "oracle_label", "operator", "mutation", "falsified",
               "naive_verdict", "set_id", "role")


def materialize(dest, which):
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    for rel, text in FILES.items():
        p = dest / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8", newline="\n")
    return dest


def build_claims(dest, set_id):
    """Return (inbox, oracle): blind inbox claims + labelled oracle rows."""
    report = pipeline.scan(dest)
    count = report["file_count"]
    salt = hashlib.sha256(set_id.encode("utf-8")).hexdigest()[:16]
    inbox = []
    oracle = []

    def add_claim(expected, decoys, label, op_class, op):
        idx = len(inbox) + 1
        cid = "CLM-0133-" + hashlib.sha256((salt + "-" + str(idx)).encode()).hexdigest()[:16]
        inbox.append({
            "claim_id": cid,
            "subject_id": "SUBJ-" + salt[:4] + "-" + str(idx),
            "subject_dir": Path(dest).name,
            "expected": expected,
            "claimed_sha256": decoys["sha256"],
            "claimed_names": decoys["names"],
        })
        oracle.append({
            "claim_id": cid,
            "set_id": set_id,
            "oracle_label": label,
            "operator": op,
            "operator_class": op_class,
        })

    add_claim({"file_count": count, "status": report["status"]},
              {"sha256": report["sha256"], "names": report["names"]},
              "true", "none", "baseline")
    add_claim({"file_count": count, "status": report["status"]},
              {"sha256": report["sha256"], "names": report["names"]},
              "true", "none", "baseline")
    add_claim({"file_count": count, "status": report["status"]},
              {"sha256": report["sha256"],
               "names": report["names"]},
              "true", "none", "baseline")
    add_claim({"file_count": count, "status": report["status"]},
              {"sha256": report["sha256"], "names": report["names"]},
              "true", "none", "baseline")
    for op in OPS_SET_A["killed"] + OPS_SET_A["surviving"] if set_id == "set_a" \
            else OPS_SET_B["killed"] + OPS_SET_B["surviving"]:
        exp = {"file_count": count, "status": report["status"]}
        decoys = {"sha256": report["sha256"], "names": report["names"]}
        if op == "count_plus_one":
            exp = {"file_count": count + 1, "status": "ok"}
        elif op == "count_minus_one":
            exp = {"file_count": count - 1, "status": "ok"}
        elif op == "zero_count":
            exp = {"file_count": 0, "status": "ok"}
        elif op == "status_forced_empty":
            exp = {"file_count": count, "status": "empty"}
        elif op == "hash_xor":
            decoys["sha256"] = "0" * 64
        elif op == "hash_upper":
            decoys["sha256"] = report["sha256"].upper()
        elif op == "names_reversed":
            decoys["names"] = list(reversed(report["names"]))
        elif op == "names_by_length":
            decoys["names"] = sorted(report["names"], key=len)
        add_claim(exp, decoys, "false", "killed" if op in OPS_SET_A["killed"] + OPS_SET_B["killed"] else "surviving", op)
    return inbox, oracle
