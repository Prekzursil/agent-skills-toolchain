#!/usr/bin/env python3
"""Probe 1: prose vs definition on the frozen 30-sample; zeros stay empty.

Re-runs extraction. Does not trust the artifact's disagreement rate until the
live recompute matches. An empty definition must stay [] — never a default id.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from corpus import all_artifacts, load_corpus, sample_30_ids  # noqa: E402
from extractor import (  # noqa: E402
    compare_sample,
    extract_all,
    extract_from_definition,
    incidence_from_rows,
    zero_fixture,
)

ART = REPO / "command-center" / "wfa" / "WFA-0059-mechanism-extraction.json"
SENTINEL = "SUCCESS:WFA-0059"


def fail(msg: str) -> int:
    print(f"FAILED:WFA-0059-probe1 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        return fail(f"self-declared {doc.get('state')}")
    if SENTINEL not in text:
        return fail("sentinel-absent")

    corpus = load_corpus()
    artifacts = all_artifacts(corpus)
    rows = extract_all(artifacts)
    live_inc = incidence_from_rows(rows)
    sample_ids = sample_30_ids(artifacts)
    live_sample = compare_sample(rows, sample_ids)

    art_inc = doc.get("incidence") or {}
    if art_inc.get("by_artifact") != live_inc["by_artifact"]:
        return fail("incidence by_artifact drifted from live extraction")
    if live_sample["n"] != 30:
        return fail(f"sample n={live_sample['n']}")
    recorded = doc.get("sample_30") or {}
    if recorded.get("n_disagreements") != live_sample["n_disagreements"]:
        return fail("disagreement count drifted")
    if recorded.get("disagreement_rate") != live_sample["disagreement_rate"]:
        return fail("disagreement rate drifted")
    if live_sample["n_disagreements"] < 1:
        return fail("sample has no prose/definition disagreement")

    z = extract_from_definition(zero_fixture())
    if z != []:
        return fail(f"zero fixture defaulted to {z}")
    zeros = live_inc["zero_mechanism_artifact_ids"]
    if not zeros:
        return fail("no zero-extractable artifact in incidence")
    defaulted = [aid for aid, ids in live_inc["by_artifact"].items() if ids is None]
    if defaulted:
        return fail(f"null default {defaulted[:3]}")

    n_c = len(corpus["candidates"])
    n_b = len(corpus["blueprints"])
    print(
        f"sample n=30 disagreements={live_sample['n_disagreements']} "
        f"rate={live_sample['disagreement_rate']:.4f}"
    )
    print(f"zeros={len(zeros)} ids={zeros}")
    print(f"corpus candidates={n_c} blueprints={n_b} mode={corpus['mode']}")
    print(
        "SUCCESS:WFA-0059-probe1 prose-vs-definition sample recomputed; "
        "zeros stay empty"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
