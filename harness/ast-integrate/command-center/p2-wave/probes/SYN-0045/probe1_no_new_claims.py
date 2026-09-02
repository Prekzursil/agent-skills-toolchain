#!/usr/bin/env python3
"""Probe 1: no claim in the live brief is absent from the bound report.

Recomputes the set difference from the artifact and the bound report on
disk. Does not trust the printed empty-difference line.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import claims as C  # noqa: E402
import jsonschema  # noqa: E402

UNIT = "SYN-0045"
ART = REPO / "command-center" / "synthesis" / "SYN-0045.owner-brief.md"
SCHEMA = REPO / "command-center" / "schema" / "owner-brief.schema.json"


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe1 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as exc:
        return fail(f"unparseable:{exc}")
    if "SUCCESS:SYN-0045" not in text:
        return fail("sentinel-absent")
    if doc.get("unit_id") != UNIT:
        return fail(f"unit_id={doc.get('unit_id')}")

    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    errors = sorted(jsonschema.Draft7Validator(schema).iter_errors(doc), key=lambda e: list(e.path))
    if errors:
        return fail(f"schema {list(errors[0].path)} {errors[0].message}")
    for garbage in ({}, {"totally": "unrelated"}, {"x": "x" * 2000}):
        if not list(jsonschema.Draft7Validator(schema).iter_errors(garbage)):
            return fail(f"schema accepted garbage {list(garbage)[:1]}")

    source = doc.get("claim_source") or {}
    rel = str(source.get("path") or "")
    report_path = REPO / rel
    if not report_path.is_file():
        return fail(f"bound report missing {rel}")
    report = C.load_json(report_path)
    diff = C.invariant(doc, report)
    print(diff["printed"])
    print(
        f"word_count={doc.get('word_count')} "
        f"claim_count={diff['brief_claim_count']}/{diff['report_claim_count']} "
        f"retention_rate={diff['retention_rate']:.6f}"
    )
    if not diff["empty"]:
        return fail(diff["printed"])
    if diff["brief_minus_report"]:
        return fail(f"extra={diff['brief_minus_report']}")
    if int(doc.get("claim_count") or -1) != diff["brief_claim_count"]:
        return fail("printed claim_count does not match recomputed")
    if int(doc.get("report_claim_count") or -1) != diff["report_claim_count"]:
        return fail("printed report_claim_count does not match recomputed")
    recomputed_words = C.word_count(str(doc.get("markdown") or ""))
    if int(doc.get("word_count") or -1) != recomputed_words:
        return fail(
            f"printed word_count {doc.get('word_count')} != {recomputed_words}"
        )
    page = C.within_one_page(str(doc.get("markdown") or ""))
    if not page["ok"]:
        return fail(f"not-one-page {page}")
    md_texts = C.markdown_claim_texts(str(doc.get("markdown") or ""))
    report_texts = [r["text"] for r in C.extract_report_claims(report)]
    extra_md = C.set_difference(md_texts, report_texts)
    if extra_md:
        return fail(f"markdown extras {extra_md}")
    if not md_texts:
        return fail("markdown produced no claim bullets")

    print(
        json.dumps(
            {
                "probe": "probe1-no-new-claims",
                "unit_id": UNIT,
                "empty_difference": True,
                "brief_claim_count": diff["brief_claim_count"],
                "report_claim_count": diff["report_claim_count"],
                "word_count": recomputed_words,
                "retention_rate": diff["retention_rate"],
                "markdown_claim_count": len(md_texts),
                "pass": True,
            },
            sort_keys=True,
        )
    )
    print("SUCCESS:SYN-0045-probe1 no-new-claims invariant holds")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
