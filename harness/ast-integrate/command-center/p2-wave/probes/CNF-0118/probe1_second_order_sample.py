#!/usr/bin/env python3
"""Named probe 1: seeded second-order sample, rate vs pre-fixed threshold.

Mechanically different from probe 2: this probe replays the seed against the
frozen population_paths and recomputes the disagreement rate from the frozen
item rows. It does not re-stat the live estate (parallel G-1 writers make
that a flake, not a confirmer). Probe 2 drives planted both-states controls.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import lib as L  # noqa: E402

ART = L.REPO / L.OUT_REL


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:CNF-0118-probe1 artifact missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    errors = L.validate_report(doc)
    if errors:
        print("FAILED:CNF-0118-probe1 schema", errors[:4])
        return 1
    catalog = L.catalog_unit()
    sentinel = str(catalog.get("completion_sentinel") or "")
    if sentinel and sentinel not in text:
        print("FAILED:CNF-0118-probe1 catalog completion_sentinel absent")
        return 1
    if str(doc.get("state") or "").upper() in L.NOT_DELIVERING:
        print("FAILED:CNF-0118-probe1 self-declared", doc.get("state"))
        return 1

    payload = L.domain(doc)
    frame = payload["sampling_frame"]
    measured = payload["measured"]
    items = list(payload.get("items") or [])
    pop_paths = list(frame.get("population_paths") or [])
    if not pop_paths:
        pop_paths = [str(it.get("path") or "") for it in items if it.get("path")]
    k = int(frame.get("draw_size") or L.draw_k(len(pop_paths)))
    if k != L.draw_k(len(pop_paths)):
        print("FAILED:CNF-0118-probe1 draw_size does not match draw_k(population)")
        return 1

    redraw = L.draw(pop_paths, L.SEED, k)
    other = L.draw(pop_paths, L.SEED + 1, k)
    if redraw != list(frame.get("sampled_paths") or []):
        print("FAILED:CNF-0118-probe1 sample-path drift")
        return 1
    if redraw != L.draw(pop_paths, L.SEED, k):
        print("FAILED:CNF-0118-probe1 same-seed redraw drifted")
        return 1
    seed_consumed = True
    if len(pop_paths) > 1 and k < len(pop_paths):
        seed_consumed = other != redraw
    if not seed_consumed:
        print("FAILED:CNF-0118-probe1 seed not consumed")
        return 1
    if frame.get("seed_consumed") is not True:
        print("FAILED:CNF-0118-probe1 artifact seed_consumed is not true")
        return 1
    if frame.get("seed") != L.SEED:
        print("FAILED:CNF-0118-probe1 seed missing")
        return 1

    stats = L.rate_of(items)
    if stats["numerator"] != measured.get("numerator"):
        print("FAILED:CNF-0118-probe1 numerator does not match items")
        return 1
    if stats["denominator"] != measured.get("denominator"):
        print("FAILED:CNF-0118-probe1 denominator does not match items")
        return 1
    if stats["rate"] != measured.get("rate"):
        print("FAILED:CNF-0118-probe1 rate does not match items", stats["rate"], measured.get("rate"))
        return 1

    pinned = L.load_threshold()["threshold"]
    if measured.get("threshold") != pinned:
        print("FAILED:CNF-0118-probe1 artifact threshold is not the pre-fixed value")
        return 1
    exceeded = L.exceeds_threshold(stats["rate"], pinned)
    if measured.get("threshold_exceeded") != exceeded:
        print("FAILED:CNF-0118-probe1 threshold comparison drift")
        return 1
    if pinned in list(frame.get("sampled_ids") or []):
        print("FAILED:CNF-0118-probe1 threshold file appears to contain sample ids")
        return 1

    for it in items:
        if not it.get("fingerprints_differ") and it.get("usable"):
            print("FAILED:CNF-0118-probe1 usable item used the same probe", it.get("id"))
            return 1
        if it.get("third_original_probe_runs") not in (0, None):
            print("FAILED:CNF-0118-probe1 third original probe run recorded", it.get("id"))
            return 1
        src = it.get("source_fingerprint") or {}
        ver = it.get("verifier_fingerprint") or {}
        if L.same_probe(src, ver) and it.get("usable"):
            print("FAILED:CNF-0118-probe1 same-probe item marked usable", it.get("id"))
            return 1

    out = {
        "probe": "probe1-second-order-sample",
        "unit_id": L.UNIT,
        "numerator": stats["numerator"],
        "denominator": stats["denominator"],
        "rate": stats["rate"],
        "threshold": pinned,
        "threshold_exceeded": exceeded,
        "sampled_ids": list(frame.get("sampled_ids") or []),
        "seed_reproduces": True,
        "pass": True,
    }
    print(json.dumps(out, sort_keys=True))
    print(
        f"rate={stats['rate']} {stats['numerator']}/{stats['denominator']} "
        f"threshold={pinned} exceeded={exceeded}"
    )
    print("SUCCESS:CNF-0118-probe1 second-order sample vs pre-fixed threshold")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
