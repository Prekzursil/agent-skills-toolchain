#!/usr/bin/env python3
"""Probe 1: extraction coverage + planted-claim recall.

Independently enumerates headings and verdict-tagged sentences, then requires
the artifact coverage_index to map each span. Planting a synthetic claim in a
scratch copy must produce a record; the unmodified corpus must not already
contain that token.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "fixtures"))

from contract import OUT_REL, PLANTED_TOKEN, SENTINEL, UNIT  # noqa: E402
from extract import coverage_key  # noqa: E402
from plant import plant_and_extract  # noqa: E402
from spans import enumerate_file  # noqa: E402


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe1 {msg}")
    return 1


def main() -> int:
    art = REPO / OUT_REL
    if not art.is_file() or art.stat().st_size <= 0:
        return fail("artifact-missing")
    text = art.read_text(encoding="utf-8")
    if SENTINEL not in text:
        return fail("sentinel-absent")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared:{doc.get('state')}")
    if doc.get("unit_id") != UNIT:
        return fail("unit_id")
    index = doc.get("coverage_index") or {}
    if not isinstance(index, dict) or not index:
        return fail("coverage-index-empty")
    if doc.get("planted_in_unmodified_corpus"):
        return fail("planted-token-already-in-corpus")

    files = (doc.get("corpus") or {}).get("files") or []
    if len(files) != 29:
        return fail(f"contract-n={len(files)} want 29")

    missing = []
    extra_ok = 0
    span_n = 0
    heading_n = 0
    verdict_n = 0
    claim_n = 0
    nac_n = 0
    first: Path | None = None
    for item in files:
        rel = item.get("path") or ""
        abs_path = Path(item.get("abs") or (REPO / rel))
        if not abs_path.is_file():
            return fail(f"source-missing {item.get('name')}")
        if first is None:
            first = abs_path
        spans = enumerate_file(abs_path, rel)
        for span in spans:
            span_n += 1
            if span["kind"] == "heading":
                heading_n += 1
            else:
                verdict_n += 1
            key = coverage_key(span)
            hit = index.get(key)
            if not isinstance(hit, dict):
                missing.append(key)
                continue
            extra_ok += 1
            if hit.get("decision") == "CLAIM":
                claim_n += 1
            elif hit.get("decision") == "NOT-A-CLAIM":
                nac_n += 1
            else:
                return fail(f"bad-decision {key} {hit}")

    if missing:
        return fail(f"unmapped-spans n={len(missing)} e.g. {missing[:4]}")
    if span_n < 29:
        return fail(f"too-few-spans n={span_n}")
    if heading_n < 29 or verdict_n < 29:
        return fail(f"population-thin headings={heading_n} verdicts={verdict_n}")
    if claim_n < 1 or nac_n < 1:
        return fail(f"classifier-not-both-states claim={claim_n} not_a_claim={nac_n}")

    claimed_keys = set(index)
    live_keys = set()
    for item in files:
        rel = item.get("path") or ""
        abs_path = Path(item.get("abs") or (REPO / rel))
        for span in enumerate_file(abs_path, rel):
            live_keys.add(coverage_key(span))
    over = sorted(claimed_keys - live_keys)
    if over:
        return fail(f"coverage-overclaim n={len(over)} e.g. {over[:3]}")

    plant = plant_and_extract(first)
    print(
        f"plant ok={plant.get('ok')} heading_hit={plant.get('heading_hit')} "
        f"verdict_hit={plant.get('verdict_hit')} hits={plant.get('hit_ids')}"
    )
    if not plant.get("ok"):
        return fail(f"planted-claim-missed {plant}")
    if PLANTED_TOKEN in text:
        return fail("planted-token-leaked-into-artifact")

    summary = {
        "probe": "probe1-coverage",
        "unit_id": UNIT,
        "span_n": span_n,
        "heading_n": heading_n,
        "verdict_n": verdict_n,
        "mapped_claim_n": claim_n,
        "mapped_not_a_claim_n": nac_n,
        "unmapped_n": 0,
        "overclaim_n": 0,
        "planted_recall": True,
        "pass": True,
    }
    print(json.dumps(summary, sort_keys=True))
    print(f"SUCCESS:{UNIT}-probe1 coverage spans={span_n} planted-recall=True")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
