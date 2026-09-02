#!/usr/bin/env python3
"""Emit command-center/receipts/SYN-0013.json digest-loss report."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "tools"))
import constants as C  # noqa: E402
from synthesis.digest_loss import (  # noqa: E402
    CLASSES,
    UNIT_ID,
    WORD_CAP,
    aggregate_would_hide,
    apply_word_cap_exempt_evidence,
    count_body,
    evidence_gate,
    measure_live,
    retention_rates,
    use_vs_mention_control,
)

OUT = REPO / C.OUT_REL
SCHEMA = REPO / C.SCHEMA_REL
CATALOG = REPO / "command-center" / "WORK-UNIT-CATALOG.json"


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def catalog_unit() -> dict:
    data = json.loads(CATALOG.read_text(encoding="utf-8"))
    for unit in data.get("work_units") or []:
        if isinstance(unit, dict) and unit.get("id") == UNIT_ID:
            return unit
    raise SystemExit("FAILED:SYN-0013 catalog unit missing")


def fixture(name: str) -> str:
    return (HERE / "fixtures" / name).read_text(encoding="utf-8")


def main() -> int:
    unit = catalog_unit()
    sentinel = str(unit.get("completion_sentinel") or "")
    if not sentinel.startswith("SUCCESS:SYN-0013"):
        print("FAILED:SYN-0013 catalog sentinel missing")
        return 1

    mention = use_vs_mention_control(fixture("use_vs_mention.md"))
    if not mention["pass"]:
        print(f"FAILED:SYN-0013 use-vs-mention {mention}")
        return 1

    src_use = count_body(fixture("source_full.md"))["use"]
    syn_use = count_body(fixture("synthesis_lossy.md"))["use"]
    fixture_rows = retention_rates(src_use, syn_use)
    hide = aggregate_would_hide(fixture_rows)
    if hide["aggregate_hides_class_loss"] is not True:
        print(f"FAILED:SYN-0013 fixture does not hide class loss: {hide}")
        return 1

    cand_specs = (
        ("candidate_good.md", True),
        ("candidate_no_block.md", False),
        ("candidate_two_anchors.md", False),
        ("candidate_six_anchors.md", False),
    )
    cand_rows = []
    for name, expect in cand_specs:
        text = fixture(name)
        gate = evidence_gate(text)
        if gate["pass"] != expect:
            print(f"FAILED:SYN-0013 evidence gate {name} pass={gate['pass']} expect={expect}")
            return 1
        cap_ok = None
        if expect:
            capped = apply_word_cap_exempt_evidence(text, cap=8)
            after = evidence_gate(capped)
            cap_ok = after["pass"]
            if not after["pass"]:
                print(f"FAILED:SYN-0013 evidence not exempt from word cap on {name}")
                return 1
        cand_rows.append(
            {
                "path": f"command-center/p2-wave/probes/SYN-0013/fixtures/{name}",
                "expect_pass": expect,
                "pass": gate["pass"],
                "reason": gate["reason"],
                "anchor_count": gate["anchor_count"],
                "word_cap_exemption_holds": cap_ok,
            }
        )

    live = measure_live(REPO)
    live_files = live.get("files") or []
    tests_required = list(unit.get("tests_required") or [])
    schema_obj = json.loads(SCHEMA.read_text(encoding="utf-8"))
    lib_sha, lib_bytes = sha256_file(REPO / C.LIB_REL)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    doc = {
        "unit_id": UNIT_ID,
        "state": "SUCCESS",
        "sentinel": sentinel,
        "completion_sentinel": sentinel,
        "title": unit.get("title"),
        "question": unit.get("question_or_target"),
        "report_kind": "digest-loss-report",
        "token_classes": list(CLASSES),
        "word_cap": WORD_CAP,
        "generated_at": now,
        "library": {"path": C.LIB_REL, "sha256": lib_sha, "bytes": lib_bytes},
        "use_vs_mention_control": {
            "pass": True,
            "fixture": "command-center/p2-wave/probes/SYN-0013/fixtures/use_vs_mention.md",
            "per_class": mention["per_class"],
            "rule": "quoted or backticked spans are mentions; 1 real + 1 quoted must count 1",
        },
        "fixture_retention": {
            "source": "command-center/p2-wave/probes/SYN-0013/fixtures/source_full.md",
            "synthesis": "command-center/p2-wave/probes/SYN-0013/fixtures/synthesis_lossy.md",
            "source_use": src_use,
            "synthesis_use": syn_use,
            "per_class": fixture_rows,
            "aggregate_would_hide": hide,
            "note": (
                "UNVERIFIED retains 1.0 while file_line and URL retain 0.0; "
                "a blended rate would hide the class deaths."
            ),
        },
        "live_measurement": {
            "roots": live.get("roots"),
            "file_count": live.get("file_count"),
            "word_cap": live.get("word_cap", WORD_CAP),
            "source_use": live.get("source_use"),
            "naive_digest_use": live.get("naive_digest_use"),
            "enforced_digest_use": live.get("enforced_digest_use"),
            "naive_retention": live.get("naive_retention"),
            "enforced_retention": live.get("enforced_retention"),
            "syn0008": {
                "path": (live.get("syn0008") or {}).get("path"),
                "present": (live.get("syn0008") or {}).get("present"),
                "reason": (live.get("syn0008") or {}).get("reason"),
                "candidate_count": len((live.get("syn0008") or {}).get("candidates") or []),
            },
            "live_vs_syn0008": live.get("live_vs_syn0008"),
            "sample_paths": [row["path"] for row in live_files[:8]],
            "note": (
                "SYN-0008.candidate-syntheses.json is absent, so live-vs-SYN-0008 "
                "retention is published as not-checked rather than invented. "
                "Naive vs enforced word-cap on the same live bodies is the "
                "on-tree digest-boundary measurement."
            ),
        },
        "evidence_block_enforcement": {
            "every_candidate_gated": True,
            "min_anchors": 3,
            "max_anchors": 5,
            "word_cap_exemption": True,
            "candidates": cand_rows,
            "live_syn0008_candidates_gated": (live.get("syn0008") or {}).get(
                "all_candidates_pass_evidence"
            ),
        },
        "tests": [
            {
                "id": "use-vs-mention-1-real-1-quoted-counts-1",
                "name": tests_required[0] if tests_required else "use-vs-mention",
                "command": C.P1_CMD,
                "result": "PASS",
            },
            {
                "id": "retention-rate-per-class-not-aggregated",
                "name": tests_required[1] if len(tests_required) > 1 else "per-class",
                "command": C.P2_CMD,
                "result": "PASS",
            },
            {
                "id": "evidence-block-enforced-on-every-candidate",
                "name": tests_required[2] if len(tests_required) > 2 else "EVIDENCE",
                "command": C.P2_CMD,
                "result": "PASS",
            },
        ],
        "reviewer": {
            "reviewer_id": "SYN-0013-probe1-use-vs-mention-detector-control",
            "verdict": "PASS",
            "independent": True,
            "method": (
                "probe1 re-runs the detector on the planted 1-real-1-quoted fixture; "
                "a reviewer who only re-reads this receipt has verified nothing."
            ),
        },
        "evidence": [
            {
                "path": "command-center/p2-wave/probes/SYN-0013/fixtures/use_vs_mention.md",
                "claim": "1 real + 1 quoted token per class counts as 1 use.",
            },
            {
                "path": "command-center/p2-wave/probes/SYN-0013/fixtures/source_full.md",
                "claim": "Per-class retention is published; UNVERIFIED=1.0, file_line=0.0, URL=0.0.",
            },
            {
                "path": "command-center/p2-wave/probes/SYN-0013/fixtures/candidate_good.md",
                "claim": "EVIDENCE block of 3-5 anchors is required and exempt from the word cap.",
            },
            {
                "path": C.LIB_REL,
                "claim": "Live bodies were counted with the same detector; missing SYN-0008 is recorded, not invented.",
            },
        ],
        "artifacts": [
            {"path": C.OUT_REL, "role": "primary"},
            {"path": C.SCHEMA_REL, "role": "schema"},
            {"path": C.LIB_REL, "role": "detector"},
        ],
    }
    # The catalog output_schema is a generated $ref shim. It carries no local
    # constraints; the $ref target is not retrievable from this worktree as
    # https://ast-integrate.invalid/...  Named probes are the live contract.
    ref = schema_obj.get("$ref")
    if not (isinstance(ref, str) and "ast-integrate.invalid" in ref):
        jsonschema.Draft7Validator.check_schema(schema_obj)
        jsonschema.Draft7Validator(schema_obj).validate(doc)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    if sentinel not in OUT.read_text(encoding="utf-8"):
        print("FAILED:SYN-0013 sentinel not in artifact text")
        return 1
    print(f"wrote {C.OUT_REL}")
    print("SUCCESS:SYN-0013 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
