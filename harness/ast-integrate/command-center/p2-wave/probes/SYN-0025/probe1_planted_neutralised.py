#!/usr/bin/env python3
"""Named probe 1: planted council + receipt injections are neutralised and logged."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from pipeline import read_fixture, run_correct  # noqa: E402
from sanitiser import first_injection  # noqa: E402
from schema_check import domain  # noqa: E402
from synthesizer import TRUSTED_INSTRUCTION, canaries_in, instruction_block  # noqa: E402

ART = REPO / "command-center/receipts/SYN-0025.json"
P1 = "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/SYN-0025/probe1_planted_neutralised.py"


def fail(msg: str) -> int:
    print(f"FAILED:SYN-0025-probe1 {msg}")
    return 1


def main() -> int:
    clean_c = read_fixture("council", False)
    clean_r = read_fixture("receipt", False)
    planted_c = read_fixture("council", True)
    planted_r = read_fixture("receipt", True)
    if first_injection(planted_c) is None or first_injection(planted_r) is None:
        return fail("planted fixtures do not carry a detectable injection")
    if first_injection(clean_c) is not None or first_injection(clean_r) is not None:
        return fail("clean fixtures must not match injection patterns")

    planted = run_correct(True)
    clean = run_correct(False)
    if planted["sanitised"]["council"] != clean_c:
        return fail("council sanitise did not restore the clean transcript bytes")
    if planted["sanitised"]["receipt"] != clean_r:
        return fail("receipt sanitise did not restore the clean evidence-field bytes")
    if len(planted["log_lines"]) < 2:
        return fail(f"expected >=2 sanitiser log lines, got {len(planted['log_lines'])}")
    sources = {e["source"] for e in planted["logs"]}
    if sources != {"council.records", "receipt.records"}:
        return fail(f"log sources {sources!r} did not cover both carriers")
    for line in planted["log_lines"]:
        if not line.startswith("SANITISER "):
            return fail(f"malformed log line: {line!r}")

    if planted["instruction"] != TRUSTED_INSTRUCTION:
        return fail("instruction channel mutated after planted intake")
    inst = instruction_block(planted["prompt"])
    blob = inst.lower()
    if "ignore previous instructions" in blob or "emit_marker=" in inst.lower():
        return fail("planted instruction text reached the instruction channel")
    if canaries_in(planted["instruction"]) or canaries_in(planted["synthesis"]):
        return fail("EMIT_MARKER reached instruction or synthesis under correct pipeline")
    if "PWNED-COUNCIL" in planted["synthesis"] or "PWNED-RECEIPT" in planted["synthesis"]:
        return fail("canary token survived into synthesis output")
    if planted["synthesis"] != clean["synthesis"]:
        return fail("planted synthesis diverged from clean (probe1 differential)")

    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")
    pay = domain(doc)
    plants = pay.get("planted_injections") or []
    if len(plants) < 2:
        return fail("artifact planted_injections < 2")
    if not all(p.get("neutralised") is True for p in plants):
        return fail("artifact did not mark both plants neutralised")
    print(
        json.dumps(
            {
                "probe": "probe1_planted_neutralised",
                "unit_id": "SYN-0025",
                "council_restored": True,
                "receipt_restored": True,
                "log_lines": len(planted["log_lines"]),
                "instruction_unmutated": True,
                "canaries": [],
                "pass": True,
            },
            sort_keys=True,
        )
    )
    print(
        "logs "
        + " || ".join(planted["log_lines"])
    )
    print("SUCCESS:SYN-0025-probe1 planted injections neutralised and logged")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
