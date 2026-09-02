#!/usr/bin/env python3
"""Probe 1: planted rename / paraphrase / parameter-fork all detected.

Re-runs the detectors. Does not trust the artifact's caught booleans.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import contract as C  # noqa: E402
import engine as E  # noqa: E402
import findings as F  # noqa: E402
import schema_local as SL  # noqa: E402

ART = REPO / C.OUTPUT_REL


def fail(msg: str) -> int:
    print(f"FAILED:SYN-0017-probe1 {msg}")
    return 1


def main() -> int:
    run = E.run()
    if not run["ok"]:
        print("errors=" + " | ".join(run["errors"]))
        return fail("live detector invariants failed")

    mutants = {m["class"]: m for m in run["planted_mutants"]}
    for cls in ("rename", "paraphrase", "parameter-fork"):
        m = mutants[cls]
        print(
            f"{cls} caught={m['caught']} lex={m['lexical_score']} "
            f"emb={m['embedding_score']} agreement={m['agreement']} "
            f"lex_hit={m['lexical_caught']} emb_hit={m['embedding_caught']}"
        )
        if not m["caught"]:
            return fail(f"{cls} mutant was not collapsed onto the incumbent")
        if not (m["lexical_caught"] or m["embedding_caught"]):
            return fail(f"{cls} mutant: neither detector fired")

    if mutants["rename"]["lexical_score"] < 0.9:
        return fail("rename lexical score too low to be an exact rename control")

    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    if C.SENTINEL not in text:
        return fail("catalog completion_sentinel absent from artifact")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")
    schema_errs = SL.errors(doc)
    if schema_errs:
        return fail("schema " + "; ".join(schema_errs[:8]))

    art_mut = {m["class"]: m for m in (SL.pick(doc, "planted_mutants") or [])}
    for cls, live in mutants.items():
        am = art_mut.get(cls) or {}
        if am.get("caught") is not True:
            return fail(f"artifact {cls} caught is not true")
        if am.get("mutant_id") != live["mutant_id"]:
            return fail(f"artifact {cls} mutant_id drifted")
        if abs(float(am.get("lexical_score")) - live["lexical_score"]) > 1e-9:
            return fail(f"artifact {cls} lexical_score drifted")
        if abs(float(am.get("embedding_score")) - live["embedding_score"]) > 1e-9:
            return fail(f"artifact {cls} embedding_score drifted")

    if F.BASE_ID not in {f["id"] for f in run["findings"]}:
        return fail("incumbent missing from live corpus")

    print("SUCCESS:SYN-0017-probe1 planted rename/paraphrase/parameter-fork all caught")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
