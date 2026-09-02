#!/usr/bin/env python3
"""Independent recount from fixtures. Does not read the design-note argument.

Two recounts:
  R1 — the F01 counter module over the on-disk corpus.
  R2 — a second tokenizer (whitespace/alnum, no stoplist) plus raw
       action+object string equality, then the same OR-duplicate rule.

A disagreement in a load-bearing number fails the unit.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import counter as C  # noqa: E402

CORPUS = HERE / "fixtures" / "corpus.json"
ALNUM = re.compile(r"[a-z0-9]+")
REQUIRED_DUP_CLASSES = (
    "exact_rename",
    "paraphrase",
    "one_parameter_fork",
    "full_rewrite",
)


def _ws_tokens(text: str) -> frozenset[str]:
    return frozenset(ALNUM.findall((text or "").lower()))


def _ws_jaccard(a: str, b: str) -> float:
    A, B = _ws_tokens(a), _ws_tokens(b)
    if not A and not B:
        return 1.0
    if not A or not B:
        return 0.0
    return len(A & B) / len(A | B)


def _raw_key(idea: dict) -> str | None:
    mech = idea.get("canonical_mechanism")
    if not isinstance(mech, dict):
        return None
    action = str(mech.get("action") or "").strip().lower()
    obj = str(mech.get("object") or "").strip().lower()
    if not action or not obj:
        return None
    return f"{action}|{obj}"


def load_corpus() -> dict:
    return json.loads(CORPUS.read_text(encoding="utf-8"))


def recount() -> dict:
    corpus = load_corpus()
    parent = corpus["parents"][0]
    class_rows = []
    for mutant in corpus["mutants"]:
        row = C.mutant_row(parent, mutant)
        jac2 = round(_ws_jaccard(C.idea_text(parent), C.idea_text(mutant)), 6)
        k2_hit = _raw_key(parent) is not None and _raw_key(parent) == _raw_key(mutant)
        r2_caught = (jac2 >= C.LEXICAL_THRESHOLD) or k2_hit
        if row["caught_as_duplicate"] != r2_caught:
            raise AssertionError(
                f"reviewer tokenizer disagreement on {mutant['id']}: "
                f"R1={row['caught_as_duplicate']} R2={r2_caught}"
            )
        class_rows.append(row)

    decoy = corpus["decoy"]
    decoy_row = C.mutant_row(parent, decoy)
    jac2 = round(_ws_jaccard(C.idea_text(parent), C.idea_text(decoy)), 6)
    k2_hit = _raw_key(parent) is not None and _raw_key(parent) == _raw_key(decoy)
    r2_caught = (jac2 >= C.LEXICAL_THRESHOLD) or k2_hit
    if decoy_row["caught_as_duplicate"] != r2_caught:
        raise AssertionError("reviewer tokenizer disagreement on decoy")

    good = C.gaming_check(
        corpus["known_good"], corpus["known_good_claimed_unique"]
    )
    bad = C.gaming_check(
        corpus["planted_bad"], corpus["planted_bad_claimed_unique"]
    )
    return {
        "parent_id": parent["id"],
        "class_rows": class_rows,
        "decoy_row": decoy_row,
        "known_good": good,
        "planted_bad": bad,
        "r2_decoy_jaccard": jac2,
    }


def assert_invariants(bundle: dict) -> None:
    seen = {row["class"] for row in bundle["class_rows"]}
    missing = [c for c in REQUIRED_DUP_CLASSES if c not in seen]
    if missing:
        raise AssertionError(f"unplanted required classes: {missing}")
    per_class = {}
    for row in bundle["class_rows"]:
        cls = row["class"]
        per_class.setdefault(cls, {"planted": 0, "caught": 0})
        per_class[cls]["planted"] += 1
        if row["caught_as_duplicate"]:
            per_class[cls]["caught"] += 1
    for cls in REQUIRED_DUP_CLASSES:
        rec = per_class[cls]
        if rec["caught"] != rec["planted"]:
            raise AssertionError(
                f"recall {cls}: {rec['caught']}/{rec['planted']} (want all caught)"
            )
    rewrite = next(r for r in bundle["class_rows"] if r["class"] == "full_rewrite")
    if rewrite["lexical_hit"]:
        raise AssertionError("full_rewrite was lexical-hit; fixture is not a rewrite")
    if rewrite["caught_by_and_gate"]:
        raise AssertionError("pairwise AND would catch rewrite; that is not this fixture")
    if not rewrite["mechanism_hit"]:
        raise AssertionError("full_rewrite missed by mechanism key")
    if bundle["decoy_row"]["caught_as_duplicate"]:
        raise AssertionError("decoy falsely merged")
    if not bundle["planted_bad"]["fired"]:
        raise AssertionError("gaming check silent on planted-bad")
    if not bundle["known_good"]["silent"]:
        raise AssertionError("gaming check fired on known-good")
    if bundle["known_good"]["corroborated_unique"] != 6:
        raise AssertionError(
            f"known-good corroborated_unique="
            f"{bundle['known_good']['corroborated_unique']} want 6"
        )
    if bundle["planted_bad"]["corroborated_unique"] != 1:
        raise AssertionError(
            f"planted-bad corroborated_unique="
            f"{bundle['planted_bad']['corroborated_unique']} want 1"
        )
    keys = [C.mechanism_key(idea) for idea in load_corpus()["planted_bad"]]
    if len(set(keys)) != 1:
        raise AssertionError(f"planted-bad key recount {set(keys)} want 1 key")
    good_keys = [C.mechanism_key(idea) for idea in load_corpus()["known_good"]]
    if len(set(good_keys)) != 6:
        raise AssertionError(f"known-good key recount {set(good_keys)} want 6 keys")
    bundle["per_class"] = per_class
