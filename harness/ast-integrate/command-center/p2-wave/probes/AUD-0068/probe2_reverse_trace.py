#!/usr/bin/env python3
"""Probe 2: reverse-trace sampled records to source spans.

Known-good records must match the cited line. A mutant snippet that is not
in the file must fail. Exists-only would wrongly accept the mutant if the
file exists; content compare is required.
"""
from __future__ import annotations

import copy
import json
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from contract import OUT_REL, SENTINEL, UNIT  # noqa: E402
from reverse import reverse_trace  # noqa: E402

SAMPLE_N = 20
SEED = 68
MUTANT_SNIPPET = "AUD-0068-SNIPPET-NOT-IN-FILE"


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe2 {msg}")
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
    records = [r for r in (doc.get("records") or []) if isinstance(r, dict)]
    if len(records) < 10:
        return fail(f"too-few-records n={len(records)}")

    rng = random.Random(SEED)
    n = min(SAMPLE_N, len(records))
    sample = rng.sample(records, n)

    matched = 0
    for rec in sample:
        hit = reverse_trace(rec)
        print(
            f"trace id={rec.get('claim_id')} ok={hit['ok']} "
            f"reason={hit['reason']} path={hit['path']}:{hit['line']}"
        )
        if not hit["ok"]:
            return fail(f"good-record-miss {rec.get('claim_id')} {hit['reason']}")
        matched += 1
        # Exists-only control: file exists, but mutant snippet must not match.
        mutant = copy.deepcopy(rec)
        mutant["source_lineage"][0]["snippet"] = MUTANT_SNIPPET
        bad = reverse_trace(mutant)
        exists_only = bool(hit["file_exists"]) and bad["ok"]
        if exists_only:
            return fail(f"exists-only-accepted-mutant {rec.get('claim_id')}")
        if bad["ok"]:
            return fail(f"mutant-snippet-accepted {rec.get('claim_id')}")

    # Both-states on the helper itself using the first sample row.
    good = reverse_trace(sample[0])
    mutant = copy.deepcopy(sample[0])
    mutant["source_lineage"][0]["snippet"] = MUTANT_SNIPPET
    bad = reverse_trace(mutant)
    if not (good["ok"] and not bad["ok"]):
        return fail(
            f"both-states-failed good={good['ok']} bad={bad['ok']} "
            f"bad_reason={bad['reason']}"
        )

    summary = {
        "probe": "probe2-reverse-trace",
        "unit_id": UNIT,
        "sample_n": n,
        "matched": matched,
        "mutant_rejected": True,
        "silent_on_good": True,
        "fires_on_bad": True,
        "pass": True,
    }
    print(json.dumps(summary, sort_keys=True))
    print(
        f"SUCCESS:{UNIT}-probe2 reverse-trace sample={n} "
        "silent_on_good=True fires_on_mutant=True"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
