#!/usr/bin/env python3
"""Probe 2: independent rank recompute, rule-index citations, credit-loss, schema.

Mechanically different from probe 1: does not call lattice.fuse for the
per-fusion expected class. Uses reviewer.independent_fuse (second SPDX/rank
table). Dropping rules_applied from a fusion row must make the checker fail.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import lattice as L  # noqa: E402
import loader as LD  # noqa: E402
import reviewer as R  # noqa: E402
import schema_merge as SM  # noqa: E402

ART = REPO / (
    "command-center/foundry/"
    "WFA-0139-license-and-credit-propagation-lattice-through-fusio.json"
)
SCHEMA = REPO / "command-center/schema/foundry-artifact.schema.json"
GARBAGE = (
    {"totally": "unrelated", "passing_tests": 999999},
    {"blob": "x" * 2000},
    {},
)


def fail(msg: str) -> int:
    print(f"FAILED:WFA-0139-probe2 {msg}")
    return 1


def schema_def() -> dict:
    return SM.ensure_shared(REPO)


def every_verdict_cites_rule(doc: dict) -> tuple[bool, str]:
    for row in doc.get("fusions") or []:
        rules = row.get("rules_applied")
        if not isinstance(rules, list) or not rules:
            return False, f"{row.get('fusion_id')} missing rules_applied"
        if any(not isinstance(i, int) or i < 1 or i > 7 for i in rules):
            return False, f"{row.get('fusion_id')} rule index out of range"
    return True, "ok"


def main() -> int:
    if not ART.is_file():
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if "SUCCESS:WFA-0139" not in text:
        return fail("sentinel-absent")
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared:{doc.get('state')}")
    spec = schema_def()
    validator = jsonschema.Draft7Validator(spec)
    errs = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    if errs:
        print("FAILED:WFA-0139-probe2 schema errors")
        for err in errs[:12]:
            print(" ", list(err.path), err.message)
        return 1
    for garbage in GARBAGE:
        if not list(validator.iter_errors(garbage)):
            return fail("schema accepted garbage")
    print("schema_valid=True garbage_rejected=True")

    ok, why = every_verdict_cites_rule(doc)
    print(f"rule_index_ok={ok} {why}")
    if not ok:
        return fail(why)

    mutant = copy.deepcopy(doc)
    stripped = False
    for row in mutant["fusions"]:
        if row.get("rules_applied"):
            del row["rules_applied"]
            stripped = True
            break
    if not stripped:
        return fail("no rules_applied to strip")
    mok, mwhy = every_verdict_cites_rule(mutant)
    print(f"mutant_ok={mok} {mwhy}")
    if mok:
        return fail("mutant without rules_applied was accepted")

    review = R.review()
    print(
        f"independent_verdict={review['verdict']} "
        f"mismatches={review['mismatch_count']}"
    )
    if review["verdict"] != "PASS":
        print(review.get("mismatches"))
        return fail("independent recompute disagreed")

    corpus = LD.load_corpus(REPO)
    register = corpus["register_by_id"]
    indie_credit_loss = []
    for unit, row in zip(corpus["merge_units"], doc["fusions"]):
        indie = R.independent_fuse(unit, register)
        if indie["status"] != row.get("status"):
            return fail(f"{unit['id']} status {row.get('status')} != indie {indie['status']}")
        if indie.get("result_class") != row.get("result_class"):
            return fail(
                f"{unit['id']} class {row.get('result_class')} != indie {indie.get('result_class')}"
            )
        if indie.get("attribution_lost"):
            indie_credit_loss.append(unit["id"])
    art_loss = list(doc.get("credit_loss", {}).get("fusion_ids") or [])
    print(f"credit_loss_artifact={art_loss} independent={indie_credit_loss}")
    if sorted(art_loss) != sorted(indie_credit_loss):
        return fail("credit-loss set mismatch")
    if corpus["kind"] == "catalog-reconstructed-fixture":
        if "MU-22" not in art_loss or "MU-29" not in art_loss:
            return fail("fixture credit-drop units not reported")
        if "MU-11" in art_loss:
            return fail("MU-11 should carry Alice credit")

    pairs = doc.get("prohibited_combinations") or []
    if ["PROPRIETARY", "STRONG_COPYLEFT"] not in pairs and [
        "STRONG_COPYLEFT",
        "PROPRIETARY",
    ] not in [sorted(p) for p in pairs]:
        # pairs are sorted alphabetically by lattice.prohibited_class_pairs
        if not any(set(p) == {"PROPRIETARY", "STRONG_COPYLEFT"} for p in pairs):
            return fail("prohibited list missing copyleft+proprietary")
    if not any("RIDER_RESTRICTED" in p for p in pairs):
        return fail("prohibited list missing rider")

    # Confirm live RANK tables have not drifted.
    if R.RANK != L.RANK:
        return fail("reviewer RANK drifted from lattice.RANK")

    # Evidence anchors resolve.
    for i, ev in enumerate(doc.get("evidence") or []):
        anchor = str(ev.get("anchor") or "")
        if ":" not in anchor:
            return fail(f"evidence[{i}] missing line")
        rel, _, line_s = anchor.rpartition(":")
        path = REPO / rel
        if not path.is_file():
            return fail(f"evidence[{i}] missing file {rel}")
        line_no = int(line_s)
        lines = path.read_text(encoding="utf-8").splitlines()
        if line_no < 1 or line_no > len(lines):
            return fail(f"evidence[{i}] line {line_no} out of range")
        print(f"anchor[{i}] ok=True {anchor}")
    if len(doc.get("evidence") or []) < 2:
        return fail("need two evidence signals")
    if len(doc.get("classification_rules") or []) != 7:
        return fail("need 7 classification rules")
    if len(doc.get("license_risk_register") or []) != 45:
        return fail("need 45-row register")
    if len(doc.get("fusions") or []) != 30:
        return fail("need 30 fusion verdicts")
    print("SUCCESS:WFA-0139-probe2 independent recompute rule-index credit-loss")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
