#!/usr/bin/env python3
"""Probe 1: digest deny-list + known-present control (both states)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
from denylist import DIGEST_CLASS, RAW, classify, matches_digest_denylist  # noqa: E402
from inventory import control_inventory  # noqa: E402
from synthesizer import RAW_ONLY_FACT_ID, RAW_ONLY_SPAN, run  # noqa: E402

ART = REPO / "command-center/synthesis/SYN-0009.raw-source-control.json"
SCHEMA = REPO / "command-center/schema/synthesis-candidate.schema.json"
NOT_DELIVERING = frozenset({"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"})
SENTINEL = (
    "SUCCESS:SYN-0009 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and the admitted-input "
    "inventory shows zero digest-class files and the known-present control "
    "fact is present. Any other terminal state is FAILED:SYN-0009 "
    "<classification> with the diagnostic tail attached."
)


def fail(msg: str) -> int:
    print(f"FAILED:SYN-0009-probe1 {msg}")
    return 1


def main() -> int:
    inv = control_inventory(REPO)
    if inv["admitted_count"] < 1 or inv["excluded_count"] < 1:
        return fail(f"control corpus too thin {inv['admitted_count']}/{inv['excluded_count']}")
    for row in inv["admitted"]:
        if matches_digest_denylist(row["path"]) or row["class"] == DIGEST_CLASS:
            return fail(f"admitted digest-class {row['path']}")
        if classify(row["path"]) != RAW:
            return fail(f"admitted non-raw {row['path']} class={row['class']}")
    if inv["digest_class_admitted"] != 0:
        return fail(f"digest_class_admitted={inv['digest_class_admitted']}")
    if inv["digest_class_excluded"] < 1:
        return fail("no digest-class files excluded (deny-list unexercised)")

    span_files = []
    for row in inv["admitted"] + inv["excluded"]:
        text = (REPO / row["path"]).read_text(encoding="utf-8", errors="replace")
        if RAW_ONLY_SPAN in text:
            span_files.append(row)
    if len(span_files) != 1:
        return fail(f"known-present span file count={len(span_files)} {span_files}")
    if span_files[0]["class"] != RAW:
        return fail("known-present span is not exclusive to a raw artifact")

    live = run(REPO, apply_deny=True)
    kp = live["known_present_control"]
    if not kp["present"] or not kp["exists_only_in_raw"]:
        return fail(f"known-present missed {kp}")
    if live["digest_framing_present"]:
        return fail("digest framing leaked into raw-only findings")
    if live["sibling_leak_present"]:
        return fail("sibling leak token present under deny")
    if live["inventory"]["digest_class_admitted"] != 0:
        return fail("live inventory admitted digest-class")

    contaminated = run(REPO, apply_deny=False)
    if not contaminated["digest_framing_present"]:
        return fail("unguarded read did not pick up digest framing (control silent)")
    digest_only = run(REPO, apply_deny=True, digest_only=True)
    if digest_only["known_present_control"]["present"]:
        return fail("digest-only synthesis recovered the raw-only fact")
    if not digest_only["digest_framing_present"]:
        return fail("digest-only synthesis missed digest framing")

    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    validator = jsonschema.Draft7Validator(schema)
    for garbage in (
        {},
        {"totally": "unrelated", "passing_tests": 999999},
        {"blob": "x" * 2000},
    ):
        if not list(validator.iter_errors(garbage)):
            return fail("schema accepted garbage")

    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in NOT_DELIVERING:
        return fail(f"self-declared {doc.get('state')}")
    if SENTINEL not in text:
        return fail("completion-sentinel-absent")
    errs = list(validator.iter_errors(doc))
    if errs:
        return fail(f"schema-invalid {errs[0].message}")
    inv_doc = doc.get("input_inventory") or {}
    if inv_doc.get("digest_class_admitted") != 0:
        return fail(f"artifact digest_class_admitted={inv_doc.get('digest_class_admitted')}")
    if RAW_ONLY_SPAN not in text or RAW_ONLY_FACT_ID not in text:
        return fail("known-present fact absent from artifact")
    art_ids = {f.get("id") for f in (doc.get("findings") or [])}
    if RAW_ONLY_FACT_ID not in art_ids:
        return fail("artifact findings omit RAW-ONLY-001")
    if "DIGEST-FRAMING" in art_ids or "SIBLING-LEAK" in art_ids:
        return fail("artifact findings contaminated")
    kp_doc = doc.get("known_present_control") or {}
    if kp_doc.get("present") is not True or kp_doc.get("exists_only_in_raw") is not True:
        return fail(f"artifact known_present {kp_doc}")

    summary = {
        "admitted": inv["admitted_count"],
        "excluded": inv["excluded_count"],
        "digest_class_admitted": inv["digest_class_admitted"],
        "known_present": True,
        "unguarded_digest_framing": True,
        "digest_only_misses_raw_fact": True,
        "schema_rejects_garbage": True,
    }
    print(json.dumps(summary, sort_keys=True))
    print(
        f"admitted={inv['admitted_count']} excluded={inv['excluded_count']} "
        f"digest_admitted={inv['digest_class_admitted']} fact={RAW_ONLY_FACT_ID}"
    )
    print("SUCCESS:SYN-0009-probe1 deny-list and known-present control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
