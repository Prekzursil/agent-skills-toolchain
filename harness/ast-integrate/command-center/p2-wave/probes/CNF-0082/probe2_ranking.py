#!/usr/bin/env python3
"""Probe 2: ranking vs rebuild, invalid plant, index injection, schema.

Found-but-ranked-below-rebuild is a recommendation defect. A mutant that
puts rebuild on top must fire. Index-only ghosts must stay silent. The
artifact must parse against detector-control.schema.json.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import control as C  # noqa: E402
import scenario as S  # noqa: E402
import schema_local as SL  # noqa: E402

ART = REPO / S.OUT_REL


def main() -> int:
    live = C.run(REPO)
    mutant = live["recommendation_mutant"]
    print(
        f"live_defect={mutant['live_defect']} "
        f"mutant_defect={mutant['mutant_defect']} "
        f"invalid={live['invalid_plant']['verdict']} "
        f"injection={live['index_injection']['verdict']}"
    )
    if mutant["live_defect"]:
        print("FAILED:CNF-0082-probe2 live ranking is already a defect")
        return 1
    if not mutant["mutant_defect"]:
        print("FAILED:CNF-0082-probe2 mutant rebuild-on-top did not fire")
        return 1
    if live["invalid_plant"]["verdict"] != "silent":
        print("FAILED:CNF-0082-probe2 invalid plant returned")
        return 1
    if live["index_injection"]["verdict"] != "silent":
        print("FAILED:CNF-0082-probe2 index ghosts returned")
        return 1
    if live["recommendation_defects"]:
        print(
            "FAILED:CNF-0082-probe2 live class ranking defects "
            f"{live['recommendation_defects']}"
        )
        return 1

    scout_src = (HERE / "scout.py").read_text(encoding="utf-8")
    if "index.json" not in scout_src:
        print("FAILED:CNF-0082-probe2 scout.py does not mention skipping index.json")
        return 1
    if "json.load" in scout_src and "index.json" in scout_src:
        # allowed: we skip by filename before load
        pass

    if not ART.is_file():
        print("FAILED:CNF-0082-probe2 artifact missing")
        return 1
    raw = ART.read_text(encoding="utf-8")
    doc = json.loads(raw)
    pay = SL.payload(doc)
    errs = SL.iter_errors(doc)
    if errs:
        print("FAILED:CNF-0082-probe2 schema-invalid")
        for err in errs[:12]:
            print(f"  {list(err.path)}: {err.message}")
        return 1

    garbage = {"unit_id": "CNF-0082", "state": "SUCCESS"}
    g_errs = list(SL.validator().iter_errors(garbage))
    if not g_errs:
        print("FAILED:CNF-0082-probe2 schema accepted garbage")
        return 1

    if S.SENTINEL not in raw:
        print("FAILED:CNF-0082-probe2 sentinel absent")
        return 1
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:CNF-0082-probe2 self-declared {doc.get('state')}")
        return 1
    answer = str(pay.get("answer") or "")
    if "probe-local" not in answer.lower() and "probe_local" not in answer.lower():
        if "probe-local" not in answer:
            print("FAILED:CNF-0082-probe2 answer hides detector-under-test")
            return 1
    if "absent" not in answer.lower() and not (
        live["census"].get("production_present")
        or live["census"].get("production_present")
    ):
        print("FAILED:CNF-0082-probe2 answer hides production-scout absence")
        return 1
    if "11331" not in raw and "rebuild" not in answer.lower():
        print("FAILED:CNF-0082-probe2 spec 11331 rebuild case not addressed")
        return 1

    art_mutant = next(
        (
            c
            for c in pay.get("controls") or []
            if c.get("kind") == "recommendation-mutant"
        ),
        None,
    )
    if not art_mutant or not art_mutant.get("mutant_defect"):
        print("FAILED:CNF-0082-probe2 artifact omitted mutant fire")
        return 1
    print(f"schema_ok=True garbage_rejected={len(g_errs)}")
    print("SUCCESS:CNF-0082-probe2 ranking injection schema")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
