#!/usr/bin/env python3
"""Probe 1: kappa on the 40-row held-out set; print the confusion matrix."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from gold import gold_rows  # noqa: E402
from grader import KAPPA_FLOOR, grade  # noqa: E402
from kappa import (  # noqa: E402
    cohen_kappa,
    confusion,
    format_matrix,
    observed_agreement,
    permute,
)

ART = REPO / "command-center/research/RES-0003.json"
SENTINEL = (
    "SUCCESS:RES-0003 in the receipt AND a printed confusion matrix and a "
    "kappa >= 0.6 recorded with the 40 labelled rows attached"
)


def main() -> int:
    rows = gold_rows()
    gold = [r["author_grade"] for r in rows]
    pred = [grade(r) for r in rows]
    n = len(rows)
    if n != 40:
        print(f"FAILED:RES-0003-probe1 n={n} want=40")
        return 1
    matrix = confusion(gold, pred)
    kappa = cohen_kappa(gold, pred)
    po = observed_agreement(matrix)
    print(format_matrix(matrix))
    print(f"n={n} observed_agreement={po:.4f} kappa={kappa:.4f} floor={KAPPA_FLOOR}")
    print("labelled_rows " + json.dumps(
        [
            {
                "id": r["id"],
                "author_grade": r["author_grade"],
                "predicted": p,
            }
            for r, p in zip(rows, pred)
        ],
        sort_keys=True,
    ))
    if kappa < KAPPA_FLOOR:
        print(f"FAILED:RES-0003-probe1 kappa {kappa:.4f} < {KAPPA_FLOOR}")
        return 1

    chance = permute(gold, seed=17)
    k_chance = cohen_kappa(gold, chance)
    print(f"chance_control_permuted_kappa={k_chance:.4f}")
    if k_chance >= KAPPA_FLOOR:
        print("FAILED:RES-0003-probe1 permute control still above floor (wiring)")
        return 1

    agree = permute(gold, seed=1)
    # Identity control: gold vs gold must be 1.
    k_id = cohen_kappa(gold, gold)
    print(f"identity_control_kappa={k_id:.4f}")
    if k_id != 1.0:
        print("FAILED:RES-0003-probe1 identity kappa != 1")
        return 1
    del agree

    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:RES-0003-probe1 artifact missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    if SENTINEL not in text:
        print("FAILED:RES-0003-probe1 catalog sentinel absent from artifact")
        return 1
    doc = json.loads(text)
    stored = doc.get("kappa")
    if stored is None:
        print("FAILED:RES-0003-probe1 kappa not stored")
        return 1
    if abs(float(stored) - kappa) > 1e-9:
        print(f"FAILED:RES-0003-probe1 stored kappa {stored} != live {kappa}")
        return 1
    attached = doc.get("labelled_rows") or []
    if len(attached) != 40:
        print(f"FAILED:RES-0003-probe1 labelled_rows {len(attached)} != 40")
        return 1
    cm = doc.get("confusion_matrix")
    if not cm:
        print("FAILED:RES-0003-probe1 confusion_matrix missing")
        return 1
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:RES-0003-probe1 self-declared {doc.get('state')}")
        return 1
    print("SUCCESS:RES-0003-probe1 kappa and confusion matrix")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
