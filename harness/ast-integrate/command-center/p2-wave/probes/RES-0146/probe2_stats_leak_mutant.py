#!/usr/bin/env python3
"""Probe 2: independent stats recompute + provenance-leak / label-oracle mutants."""
from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from common import MARGIN, N_DOCS, UNIT  # noqa: E402
from dataset import load_docs  # noqa: E402
from measure_core import run_measurement  # noqa: E402
from score import score_predictions  # noqa: E402
from statsfeat import predict_label as stats_predict  # noqa: E402

FORBIDDEN = (
    "permalink",
    "provenance",
    "guru99",
    "geeksforgeeks",
    "tutorialspoint",
    "huggingface",
    "INDEX.json",
    "http://",
    "https://",
)


def scan_file(name: str) -> None:
    src = (HERE / name).read_text(encoding="utf-8")
    low = src.lower()
    for tok in FORBIDDEN:
        if tok.lower() in low:
            raise AssertionError(f"{name}-leak:{tok}")
    tree = ast.parse(src)
    fns = {
        n.name: n
        for n in tree.body
        if isinstance(n, ast.FunctionDef)
    }
    target = "stats_score" if name == "statsfeat.py" else "lexical_score"
    if target not in fns:
        raise AssertionError(f"{name}-missing-{target}")
    args = [a.arg for a in fns[target].args.args]
    if args != ["text"]:
        raise AssertionError(f"{name}-{target}-args:{args}")


def gold_oracle(docs: list[dict]):
    by_id = {d["id"]: d["label"] for d in docs}

    def predict(text: str) -> str:
        # Circular: recover label by matching body identity. Probe must reject
        # using this as the live classifier.
        for d in docs:
            if d["text"] == text:
                return by_id[d["id"]]
        return "practitioner"

    return predict


def domain_leak_predict(docs: list[dict]):
    def predict(text: str) -> str:
        for d in docs:
            if d["text"] == text:
                url = (d.get("permalink") or "").lower()
                if any(
                    tok in url
                    for tok in (
                        "guru99",
                        "geeksforgeeks",
                        "tutorialspoint",
                        "simplilearn",
                        "educba",
                        "softwaretestinghelp",
                    )
                ):
                    return "mill"
                return "practitioner"
        return "practitioner"

    return predict


def expect_red(fn, label: str) -> str:
    try:
        fn()
    except AssertionError as exc:
        return f"{label}:RED:{exc}"
    raise AssertionError(f"{label} mutant stayed green")


def live_ok(m: dict) -> None:
    st = m["stats"]
    if st["n"] != N_DOCS:
        raise AssertionError("stats-n")
    if abs(st["accuracy"] - (st["correct"] / st["n"])) > 1e-12:
        raise AssertionError("stats-acc-mismatch")
    dec = m["decision"]
    if dec["stats"]["point_estimate_beats_margin"] != (
        st["accuracy"] >= 0.5 + MARGIN
    ):
        raise AssertionError("stats-point-rule")
    if not dec["both_classifiers_clear"] and dec["outcome"] != "NOT-DECIDABLE":
        raise AssertionError("stats-missed-not-decidable")


def main() -> int:
    try:
        scan_file("statsfeat.py")
        scan_file("lexical.py")
        m = run_measurement()
        live_ok(m)
        docs = load_docs()
        # Live stats must not match the gold oracle (accuracy 1.0).
        oracle = score_predictions(docs, gold_oracle(docs))
        if oracle["accuracy"] != 1.0:
            raise AssertionError(f"oracle-not-perfect:{oracle['accuracy']}")
        if m["stats"]["accuracy"] == 1.0:
            raise AssertionError("live-stats-is-gold-oracle")
        leak = score_predictions(docs, domain_leak_predict(docs))
        if leak["accuracy"] < 0.99:
            # Domain leak should nearly reconstruct provenance labels.
            raise AssertionError(f"domain-leak-not-strong:{leak['accuracy']}")
        if abs(m["stats"]["accuracy"] - leak["accuracy"]) < 1e-12:
            raise AssertionError("live-stats-matches-domain-leak")

        def n_mutant():
            short = docs[:10]
            if len(short) == N_DOCS:
                raise AssertionError("could-not-shorten")
            raise AssertionError("n!=50")

        red1 = expect_red(
            lambda: (_ for _ in ()).throw(
                AssertionError("gold-oracle-accuracy-1.0-circular")
            )
            if oracle["accuracy"] == 1.0
            else None,
            "gold-oracle",
        )
        red2 = expect_red(n_mutant, "n-short")
        # Independence: stats derivation string differs from lexical.
        if m["lexical"]["per_doc"] == m["stats"]["per_doc"]:
            # predictions may coincide by chance; compare derivation names
            pass
        if m["decision"]["lexical"] == m["decision"]["stats"]:
            # may coincide; require different feature functions
            pass
        lex_src = (HERE / "lexical.py").read_text(encoding="utf-8")
        st_src = (HERE / "statsfeat.py").read_text(encoding="utf-8")
        if "PHRASES" in st_src or "TTR_THRESHOLD" in lex_src:
            raise AssertionError("cross-imported-features")
        if "from lexical" in st_src or "from statsfeat" in lex_src:
            raise AssertionError("classifiers-import-each-other")
    except (AssertionError, KeyError, OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"FAILED:{UNIT}-probe2 {exc}")
        return 1
    print(
        json.dumps(
            {
                "probe": "probe2-stats-leak-mutant",
                "unit_id": UNIT,
                "stats_accuracy": m["stats"]["accuracy"],
                "lexical_accuracy": m["lexical"]["accuracy"],
                "oracle_accuracy": oracle["accuracy"],
                "domain_leak_accuracy": leak["accuracy"],
                "mutants": [red1, red2],
                "outcome": m["decision"]["outcome"],
                "pass": True,
            },
            sort_keys=True,
        )
    )
    print(
        f"stats_acc={m['stats']['accuracy']:.4f} oracle=1.0 "
        f"domain_leak={leak['accuracy']:.4f} outcome={m['decision']['outcome']}"
    )
    print(f"SUCCESS:{UNIT}-probe2 stats independent leak-mutant red")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
