#!/usr/bin/env python3
"""Named probe 2: differential identity, clean-zero logs, sanitise-before-split.

Independent mechanical reviewer of the intake order, not an agreement check
on probe1's wording. Author vendor is anthropic; this probe is the other-vendor
adversarial control (openai-shaped scope: order-of-operations leak).
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from pipeline import read_fixture, run_correct, run_naive  # noqa: E402
from synthesizer import TRUSTED_INSTRUCTION, canaries_in, sha256_text  # noqa: E402

ART = REPO / "command-center/receipts/SYN-0025.json"
SCHEMA = REPO / "command-center/schema/injection-defence-report.schema.json"


def fail(msg: str) -> int:
    print(f"FAILED:SYN-0025-probe2 {msg}")
    return 1


def digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8").replace(b"\r\n", b"\n")).hexdigest()


def main() -> int:
    clean = run_correct(False)
    planted = run_correct(True)
    naive = run_naive(True)

    if clean["log_lines"]:
        return fail(f"clean corpus produced sanitiser logs: {clean['log_lines']}")
    if len(planted["log_lines"]) < 2:
        return fail("planted corpus produced fewer than two sanitiser logs")

    if planted["synthesis"] != clean["synthesis"]:
        return fail("differential: synthesis with fixture != synthesis without fixture")
    if digest(planted["synthesis"]) != digest(clean["synthesis"]):
        return fail("differential sha256 mismatch")

    planted_receipt = read_fixture("receipt", True)
    evidence_line = [
        ln for ln in planted_receipt.splitlines() if ln.startswith("SYN-0008|")
    ][0]
    if evidence_line.count("|") < 3:
        return fail("planted receipt evidence line must contain a delimiter inside the field")
    if len(evidence_line.split("|")) <= 3:
        return fail("split-first would not shift columns on the planted receipt line")

    if not naive["leaked_extras"]:
        return fail("naive after-split control did not leak extra columns (order proof missing)")
    if not any("EMIT_MARKER=" in x for x in naive["leaked_extras"]):
        return fail(f"naive extras lacked canary: {naive['leaked_extras']!r}")
    if naive["synthesis"] == clean["synthesis"]:
        return fail("naive after-split synthesis matched clean; control is insensitive")
    if not canaries_in(naive["instruction"]):
        return fail("naive pipeline did not move canary into the instruction channel")
    if canaries_in(planted["instruction"]) or planted["instruction"] != TRUSTED_INSTRUCTION:
        return fail("correct pipeline mutated instruction")

    if sha256_text(planted["instruction"]) != sha256_text(TRUSTED_INSTRUCTION):
        return fail("instruction digest drifted")

    if not ART.is_file():
        return fail("artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    diff = doc.get("differential") or {}
    if diff.get("byte_identical") is not True:
        return fail("artifact differential.byte_identical is not true")
    if diff.get("without_fixture_sha256") != digest(clean["synthesis"]):
        return fail("artifact without_fixture_sha256 != live clean synthesis")
    if diff.get("with_fixture_sha256") != digest(planted["synthesis"]):
        return fail("artifact with_fixture_sha256 != live planted synthesis")
    both = doc.get("both_states") or {}
    if both.get("clean_log_line_count") != 0 or both.get("clean_zero_logs") is not True:
        return fail("artifact both_states clean control failed")
    if int(both.get("planted_log_line_count") or 0) < 2:
        return fail("artifact planted_log_line_count < 2")
    ctrl = doc.get("sanitise_after_split_control") or {}
    if ctrl.get("proves_order_matters") is not True:
        return fail("artifact order-control missing")
    if ctrl.get("naive_synthesis_matches_clean") is not False:
        return fail("artifact naive control did not report divergence")

    try:
        import jsonschema
    except Exception as exc:
        return fail(f"jsonschema import failed: {type(exc).__name__}")
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    jsonschema.Draft7Validator(schema).validate(doc)
    garbage = [{}, {"totally": "unrelated", "passing_tests": 999999}, {"blob": "x" * 200}]
    rejected = 0
    for g in garbage:
        try:
            jsonschema.Draft7Validator(schema).validate(g)
        except jsonschema.ValidationError:
            rejected += 1
    if rejected != 3:
        return fail(f"schema accepted garbage ({rejected}/3 rejected)")

    print(
        json.dumps(
            {
                "probe": "probe2_differential_before_split",
                "unit_id": "SYN-0025",
                "clean_logs": 0,
                "planted_logs": len(planted["log_lines"]),
                "byte_identical": True,
                "sha256": digest(clean["synthesis"]),
                "naive_leaked": naive["leaked_extras"],
                "naive_diverged": True,
                "schema_rejects_garbage": 3,
                "pass": True,
            },
            sort_keys=True,
        )
    )
    print(
        "differential identical=True clean_logs=0 "
        f"planted_logs={len(planted['log_lines'])} "
        f"naive_canary={naive['leaked_extras']!r}"
    )
    print("SUCCESS:SYN-0025-probe2 differential identical; sanitise-before-split proven")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
