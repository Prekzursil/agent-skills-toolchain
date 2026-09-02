#!/usr/bin/env python3
"""Probe 2: malformed CallToolResult injection per adapter + classification.

Mechanically independent of probe 1: this drives tools/call with injected
payloads and grades the adapter terminal through classify(), which probe 1
never calls. An empty SUCCESS on a malformed payload is P1.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from classify import classify  # noqa: E402
from servers import MALFORMED_INJECTIONS  # noqa: E402
from suite import malformed_matrix, rule_malformed_loud_degrade  # noqa: E402


def _fail(msg: str) -> int:
    print(f"FAILED:TST-0044-probe2 {msg}")
    return 1


def main() -> int:
    matrix = malformed_matrix()
    if matrix["conforming_has_empty_success"]:
        return _fail("conforming adapter produced EMPTY_SUCCESS (P1)")
    if not matrix["mutant_all_empty_success"]:
        return _fail(
            "empty_success mutant did not classify every injection as "
            f"EMPTY_SUCCESS got={matrix['empty_success_injections_on_mutant']}"
        )
    if len(matrix["per_adapter"]) < 2:
        return _fail("need malformed injection on >=2 adapters")

    by_name = {e["adapter"]: e for e in matrix["per_adapter"]}
    conforming = by_name.get("conforming")
    mutant = by_name.get("empty_success")
    if conforming is None or mutant is None:
        return _fail("missing conforming or empty_success adapter rows")
    if conforming["n"] != len(MALFORMED_INJECTIONS):
        return _fail(f"conforming n={conforming['n']}")
    for row in conforming["classifications"]:
        if row["class"] != "SCHEMA_INVALID":
            return _fail(f"conforming {row['injection']} class={row['class']}")
        if row["status"] != "FAILED":
            return _fail(f"conforming {row['injection']} status={row['status']}")
        if row["empty_success"]:
            return _fail(f"conforming {row['injection']} empty_success")
        # Independent re-grade: rebuild a FAILED schema-invalid terminal.
        again = classify(
            {
                "status": "FAILED",
                "id": "regrade",
                "failure_class": "schema-invalid",
                "reason": row["reason"] or "malformed",
                "content": [{"type": "text", "text": "x"}],
            }
        )
        if again["class"] != "SCHEMA_INVALID":
            return _fail(f"regrade {row['injection']} -> {again}")

    for row in mutant["classifications"]:
        if row["class"] != "EMPTY_SUCCESS" or row["severity"] != "P1":
            return _fail(f"mutant {row['injection']} {row}")
        again = classify({"status": "SUCCESS", "id": None, "content": []})
        if again["class"] != "EMPTY_SUCCESS" or again["severity"] != "P1":
            return _fail(f"empty-success classifier silent {again}")

    rule = rule_malformed_loud_degrade()
    if not rule["positive"]["pass"] or not rule["negative"]["fired_on_bad"]:
        return _fail(f"malformed-loud-degrade both-states {rule['positive']} {rule['negative']}")

    summary = {
        "probe": "probe2-malformed-injection",
        "n_injections": len(MALFORMED_INJECTIONS),
        "n_adapters": len(matrix["per_adapter"]),
        "adapters": [e["adapter"] for e in matrix["per_adapter"]],
        "conforming_all_schema_invalid": True,
        "mutant_all_empty_success_p1": True,
        "empty_success_is_p1": True,
    }
    print(json.dumps(summary, sort_keys=True))
    print(
        f"injections={len(MALFORMED_INJECTIONS)} adapters={summary['adapters']} "
        "conforming=SCHEMA_INVALID mutant=EMPTY_SUCCESS/P1"
    )
    print("SUCCESS:TST-0044-probe2 malformed-result injection both-states")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
