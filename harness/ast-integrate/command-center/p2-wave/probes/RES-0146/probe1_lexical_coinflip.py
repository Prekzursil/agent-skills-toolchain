#!/usr/bin/env python3
"""Probe 1: recompute lexical accuracy vs coin-flip on the frozen 50-set."""
from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from common import MARGIN, N_DOCS, N_PER_CLASS, UNIT, WILSON_FLOOR  # noqa: E402
from lexical import HIT_THRESHOLD, predict_label as lex_predict  # noqa: E402
from measure_core import run_measurement  # noqa: E402
from score import score_predictions  # noqa: E402


FORBIDDEN_IN_LEXICAL = (
    "permalink",
    "provenance",
    "guru99",
    "geeksforgeeks",
    "tutorialspoint",
    "huggingface",
    "INDEX.json",
)


def scan_lexical_source() -> None:
    src = (HERE / "lexical.py").read_text(encoding="utf-8")
    low = src.lower()
    for tok in FORBIDDEN_IN_LEXICAL:
        if tok.lower() in low:
            raise AssertionError(f"lexical-source-leak:{tok}")
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] in {"corpus", "dataset", "measure_core"}:
                    raise AssertionError(f"lexical-import:{alias.name}")
        if isinstance(node, ast.ImportFrom) and (node.module or "").split(".")[0] in {
            "corpus",
            "dataset",
            "measure_core",
        }:
            raise AssertionError(f"lexical-from:{node.module}")
    fns = {
        n.name: n
        for n in tree.body
        if isinstance(n, ast.FunctionDef)
    }
    if "predict_label" not in fns or "lexical_score" not in fns:
        raise AssertionError("lexical-missing-functions")
    args = [a.arg for a in fns["lexical_score"].args.args]
    if args != ["text"]:
        raise AssertionError(f"lexical_score-args:{args}")


def always_mill(_text: str) -> str:
    return "mill"


def main() -> int:
    try:
        scan_lexical_source()
        m = run_measurement()
        if m["n"] != N_DOCS:
            raise AssertionError(f"n={m['n']}")
        if m["n_practitioner"] != N_PER_CLASS or m["n_mill"] != N_PER_CLASS:
            raise AssertionError("class-split")
        lex = m["lexical"]
        coin = m["coin_flip"]
        dec = m["decision"]
        if coin["expected_fair_p"] != 0.5:
            raise AssertionError("coin-expected")
        if abs(coin["majority_class_accuracy"] - 0.5) > 1e-9:
            raise AssertionError("majority-not-balanced")
        if abs(lex["accuracy"] - (lex["correct"] / lex["n"])) > 1e-12:
            raise AssertionError("lex-acc-mismatch")
        # Negative control: coin-flip is reported; decision uses expected 0.5+margin.
        if dec["stated_margin"] != MARGIN:
            raise AssertionError("margin-drift")
        if dec["wilson_floor"] != WILSON_FLOOR:
            raise AssertionError("wilson-floor-drift")
        if dec["lexical"]["point_estimate_beats_margin"] != (
            lex["accuracy"] >= 0.5 + MARGIN
        ):
            raise AssertionError("lex-point-rule")
        # Both-states: an always-mill mutant is prevalence, not a win.
        from dataset import load_docs

        docs = load_docs()
        mutant = score_predictions(docs, always_mill)
        if mutant["accuracy"] != 0.5:
            raise AssertionError(f"always-mill-acc={mutant['accuracy']}")
        if mutant["fp"] != N_PER_CLASS:
            raise AssertionError("always-mill-should-false-positive-all-practitioner")
        # Live classifier must not be the always-mill mutant (different predictions).
        live_preds = [r["pred"] for r in lex["per_doc"]]
        if live_preds == ["mill"] * N_DOCS:
            raise AssertionError("live-lexical-is-always-mill")
        outcome = dec["outcome"]
        if outcome not in {"NOT-DECIDABLE", "AUTO-DEMOTE-SUPPORTED-ON-THIS-SET"}:
            raise AssertionError(f"bad-outcome:{outcome}")
        # Catalog: failing to beat margin => NOT-DECIDABLE, which is valid.
        if not dec["both_classifiers_clear"] and outcome != "NOT-DECIDABLE":
            raise AssertionError("missed-not-decidable")
        if HIT_THRESHOLD < 1:
            raise AssertionError("lexical-threshold-collapsed")
    except (AssertionError, KeyError, OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"FAILED:{UNIT}-probe1 {exc}")
        return 1
    print(
        json.dumps(
            {
                "probe": "probe1-lexical-coinflip",
                "unit_id": UNIT,
                "n": m["n"],
                "lexical_accuracy": lex["accuracy"],
                "lexical_correct": lex["correct"],
                "coin_flip_expected": 0.5,
                "coin_flip_realized": coin["accuracy"],
                "majority_class_accuracy": coin["majority_class_accuracy"],
                "stated_margin": MARGIN,
                "beats_margin": dec["lexical"]["beats_for_auto_demote"],
                "always_mill_mutant_accuracy": mutant["accuracy"],
                "outcome": outcome,
                "pass": True,
            },
            sort_keys=True,
        )
    )
    print(
        f"n={m['n']} lex_acc={lex['accuracy']:.4f} coin_expected=0.5 "
        f"coin_realized={coin['accuracy']:.4f} outcome={outcome}"
    )
    print(f"SUCCESS:{UNIT}-probe1 lexical vs coin-flip baseline")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
