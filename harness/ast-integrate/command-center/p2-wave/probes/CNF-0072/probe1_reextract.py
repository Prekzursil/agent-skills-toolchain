#!/usr/bin/env python3
"""Probe 1: re-run the independent extractor; every reference classified; no guessing.

This probe does not read probe 2's verdict. It re-derives the audit from disk
and checks the emitted artifact against that live re-run.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import extract as E  # noqa: E402

ART = REPO / E.OUTPUT_REL


def _class_map(refs: list[dict]) -> dict[tuple, str]:
    return {
        (r["corpus"], r["path"], r["line"], r["token"]): r["classification"]
        for r in refs
    }


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:CNF-0072-probe1 artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    ok, why = E.validate_against_schema(doc)
    print(f"schema_ok={ok} {why}")
    if not ok:
        print("FAILED:CNF-0072-probe1 schema")
        return 1
    text = ART.read_text(encoding="utf-8")
    if E.SENTINEL not in text:
        print("FAILED:CNF-0072-probe1 sentinel-absent")
        return 1
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:CNF-0072-probe1 self-declared {doc.get('state')}")
        return 1
    body = E.report_of(doc)
    if not body.get("every_reference_classified") or not body.get("no_guessing"):
        print("FAILED:CNF-0072-probe1 classification/no-guess flags")
        return 1

    live = E.audit(REPO)
    live_body = E.report_of(live)
    refs = body.get("references") or []
    if not refs:
        print("FAILED:CNF-0072-probe1 empty references")
        return 1
    unclassified = [r for r in refs if r.get("classification") not in E.CLASSIFICATIONS]
    guessed = E.no_guess_violation(refs)
    print(
        f"refs={len(refs)} unclassified={len(unclassified)} guessed={len(guessed)} "
        f"live_ns={live_body['live']['declared_namespace_count']} "
        f"control_ns={live_body['control']['declared_namespace_count']}"
    )
    if unclassified:
        print("FAILED:CNF-0072-probe1 unclassified", unclassified[:3])
        return 1
    if guessed:
        print("FAILED:CNF-0072-probe1 guessed", guessed[:3])
        return 1

    art_map = _class_map(refs)
    live_map = _class_map(live_body["references"])
    if set(art_map) != set(live_map):
        only_art = sorted(set(art_map) - set(live_map))[:5]
        only_live = sorted(set(live_map) - set(art_map))[:5]
        print(f"FAILED:CNF-0072-probe1 reference-set drift art_only={only_art} live_only={only_live}")
        return 1
    disagree_cls = [k for k, c in art_map.items() if live_map[k] != c]
    if disagree_cls:
        print("FAILED:CNF-0072-probe1 classification drift", disagree_cls[:5])
        return 1

    live_d = body["extractor_disagreement"]["live"]
    print(
        f"extractorA={live_d['count_a']} extractorB={live_d['count_b']} "
        f"agree={live_d['agree']} b_only={len(live_d.get('b_only') or [])}"
    )
    if "count_a" not in live_d or "count_b" not in live_d:
        print("FAILED:CNF-0072-probe1 missing extractor counts")
        return 1
    # Slash-run extras are expected on the catalog; both counts must be present
    # even when they disagree.
    if live_d["count_a"] == live_d["count_b"] == 0:
        print("FAILED:CNF-0072-probe1 both extractors empty on live tree")
        return 1

    print("SUCCESS:CNF-0072-probe1 reextract classified no-guess")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
