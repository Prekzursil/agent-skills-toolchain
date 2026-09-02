#!/usr/bin/env python3
"""Probe 2: 20-example blind discrimination, merge-before-freeze, reviewer."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import discriminate as D  # noqa: E402
import namespaces as N  # noqa: E402
import reviewer as R  # noqa: E402
from vocab import DISCRIMINATION_FLOOR  # noqa: E402

ART = REPO / "command-center/wfa/WFA-0058-mechanism-vocabulary.json"
SCHEMA = HERE / "mechanism-record.schema.json"


def fail(msg: str) -> int:
    print(f"FAILED:WFA-0058-probe2 {msg}")
    return 1


def main() -> int:
    blind = D.run_blind()
    print(
        f"discrimination n={blind['n']} correct={blind['correct']} "
        f"score={blind['score']} floor={blind['floor']} passed={blind['passed']}"
    )
    for row in blind["rows"]:
        if not row["ok"]:
            print(f"  miss gold={row['gold']} got={row['got']} text={row['text'][:80]}")
    if blind["n"] != 20:
        return fail(f"held-out n={blind['n']} want 20")
    if not blind["passed"] or blind["score"] < DISCRIMINATION_FLOOR:
        return fail("discrimination floor not met")

    merge = D.indistinguishable_pair()
    print(
        f"indistinguishable separability={merge['separability']} "
        f"must_merge={merge['must_merge']} "
        f"clone_admitted={merge['clone_admitted_to_frozen_vocab']} "
        f"merged_before_freeze={merge['merged_before_freeze']}"
    )
    if not merge["must_merge"]:
        return fail("clone pair was separable; merge control did not fire")
    if merge["clone_admitted_to_frozen_vocab"]:
        return fail("indistinguishable clone was frozen as a second id")
    if not merge["merged_before_freeze"]:
        return fail("vocabulary frozen without merging indistinguishable pair")

    ns = N.audit()
    print(
        f"namespace clean={ns['clean']} pattern_ok={ns['pattern_ok']} "
        f"collisions={ns['collisions']} "
        f"M-16_rejected={ns['planted_M-16_rejected_as_vocab_id']}"
    )
    if not ns["clean"]:
        return fail(f"namespace collision {ns}")
    if not ns["planted_M-16_rejected_as_vocab_id"]:
        return fail("option id M-16 was admitted as a mechanism id")

    rev = R.review()
    print(
        f"reviewer verdict={rev['verdict']} both_states_rerun={rev['both_states_rerun']} "
        f"disc={rev['discrimination_score']} merge={rev['indistinguishable_merged_before_freeze']}"
    )
    if rev["verdict"] != "PASS" or not rev["both_states_rerun"]:
        return fail(f"reviewer {rev}")

    if not ART.is_file():
        return fail("artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    jsonschema.validate(doc, json.loads(SCHEMA.read_text(encoding="utf-8")))
    print("schema_valid=True")
    ev_b = doc.get("discrimination") or {}
    if int(ev_b.get("n") or 0) != 20 or not ev_b.get("passed"):
        return fail("artifact discrimination block mismatch")
    print("SUCCESS:WFA-0058-probe2 discrimination merge-before-freeze reviewer")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
