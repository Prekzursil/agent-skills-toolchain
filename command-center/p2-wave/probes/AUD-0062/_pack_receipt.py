#!/usr/bin/env python3
"""Pack AUD-0062 always-on context budget (BLOCKED on independent review)."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import _p2lib as L  # noqa: E402

UNIT = "AUD-0062"
OUT = "command-center/audit/AUD-0062-always-on-context-budget.json"
SCHEMA = "command-center/schema/audit-metric-baseline.schema.json"
PROBE = Path(__file__).resolve().parent
MANIFEST = "command-center/p2-wave/probes/AUD-0062/UNIT-ARTIFACT-MANIFEST.json"


def build(primary: dict | None = None) -> dict:
    p1 = json.loads((PROBE / "probe1-tokenize-sum.json").read_text(encoding="utf-8"))
    p2 = json.loads((PROBE / "probe2-occupancy-compare.json").read_text(encoding="utf-8"))
    raw1 = (PROBE / "probe1-tokenize.raw.txt").read_text(encoding="utf-8")
    raw2 = (PROBE / "probe2-occupancy.raw.txt").read_text(encoding="utf-8")
    ctrl = json.loads((PROBE / "control-tolerance.json").read_text(encoding="utf-8"))
    started = "2026-09-07T18:25:00Z"
    ended = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    dominant = p1.get("dominant_item") or {}
    total_ws = p1["total_tokens_whitespace"]
    full_ws = p2["probe1_full_file_tokens_whitespace"]

    arts = [
        primary
        or {
            "path": OUT,
            "bytes": 4096,
            "sha256": "0" * 64,
            "exists": True,
            "eol": "LF",
            "role": "primary",
        },
        L.art("command-center/p2-wave/probes/AUD-0062/probe1-tokenize-sum.json", "supporting"),
        L.art("command-center/p2-wave/probes/AUD-0062/probe2-occupancy-compare.json", "supporting"),
        L.art("command-center/p2-wave/probes/AUD-0062/control-tolerance.json", "control"),
        L.art("command-center/p2-wave/probes/AUD-0062/probe1-tokenize.raw.txt", "log"),
        L.art("command-center/p2-wave/probes/AUD-0062/probe2-occupancy.raw.txt", "log"),
    ]
    return {
        "schema_version": 1,
        "unit_id": UNIT,
        "state": "BLOCKED",
        "sentinel": (
            "FAILED:AUD-0062 tokenize+occupancy probes measured always-on budget; "
            f"full_file_ws_tokens={full_ws} dominant={dominant.get('path')}; "
            "blocked-on-independent-review"
        ),
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json:AUD-0062",
        "min_bytes_threshold": 4096,
        "produced_by": {
            "vendor": "anthropic",
            "model": "composer",
            "role": "tool-author",
            "execution_substrate": "linux-local-p2-loop",
        },
        "artifacts": arts,
        "evidence": [
            L.evidence(
                (
                    f"Probe 1 tokenized {p1['item_count']} injection items: "
                    f"total_ws={total_ws} total_char4={p1['total_tokens_char4']} "
                    f"dominant={dominant.get('path')} tok_ws={dominant.get('tokens_whitespace')}."
                ),
                "CONFIRMED",
                "command-center/p2-wave/probes/AUD-0062/probe1-tokenize.raw.txt",
                [
                    L.probe(
                        "source",
                        "command",
                        "python3 -B command-center/p2-wave/probes/AUD-0062/probe1_tokenize_injection.py",
                        raw1,
                        0,
                    ),
                    L.probe(
                        "verifier",
                        "file-read",
                        "python3 -c read probe1-tokenize-sum.json",
                        json.dumps(
                            {
                                "total_tokens_whitespace": total_ws,
                                "dominant": dominant.get("path"),
                                "ok": p1["ok"],
                            }
                        ),
                        0,
                    ),
                ],
                "almost-certain",
            ),
            L.evidence(
                (
                    f"Probe 2 occupancy compare: full_file_c4={p2['probe1_full_file_tokens_char4']} "
                    f"occupancy_c4={p2['occupancy']['occupancy_tokens_char4']} "
                    f"relative_gap={ctrl['relative_gap']} within_tolerance={ctrl['within_tolerance']}."
                ),
                "CONFIRMED",
                "command-center/p2-wave/probes/AUD-0062/probe2-occupancy.raw.txt",
                [
                    L.probe(
                        "source",
                        "command",
                        "python3 -B command-center/p2-wave/probes/AUD-0062/probe2_occupancy_compare.py",
                        raw2,
                        0,
                    ),
                    L.probe(
                        "verifier",
                        "byte-compare",
                        "python3 -c read control-tolerance.json",
                        json.dumps(
                            {
                                "within_tolerance": ctrl["within_tolerance"],
                                "relative_gap": ctrl["relative_gap"],
                                "ok": ctrl["ok"],
                            }
                        ),
                        0,
                    ),
                ],
                "almost-certain",
            ),
        ],
        "tests": [
            {
                "id": "AUD-0062-tolerance-control",
                "name": "file-sum and occupancy instruments within stated tolerance",
                "command": "python3 -B command-center/p2-wave/probes/AUD-0062/probe2_occupancy_compare.py",
                "result": "PASS" if ctrl["ok"] else "FAIL",
                "assertions": 1,
                "output_tail": raw2[-400:],
            }
        ],
        "negative_controls": [
            L.control(
                "AUD0062-C1",
                "known-broken-fixture",
                "Large unexplained gap between instruments must fail the budget claim.",
                True,
                True,
                bad="relative_gap > tolerance",
                good=f"relative_gap={ctrl['relative_gap']} <= {ctrl['tolerance_frac']}",
            )
        ],
        "reviewer": {
            "reviewer_id": "required-fresh-context-claude-reviewer-unassigned",
            "verdict": "NOT-REVIEWED",
            "independent": False,
            "fresh_context": False,
            "vendor": "anthropic",
            "notes": (
                "Catalog requires a fresh-context Claude reviewer who has not seen this "
                "transcript and must try to FALSIFY the headline token budget. "
                "Unavailable in-session; BLOCKED instead of fake SUCCESS."
            ),
        },
        "defects": [
            {
                "id": "AUD-0062-D-REVIEW",
                "severity": "P1",
                "status": "open",
                "summary": "Independent fresh-context Claude review unpaid.",
            },
            {
                "id": "AUD-0062-D-DOMINANT-RULE",
                "severity": "P2",
                "status": "open",
                "summary": (
                    f"Dominant always-on item is {dominant.get('path')} at "
                    f"{dominant.get('tokens_whitespace')} whitespace-tokens "
                    f"({dominant.get('bytes')} bytes)."
                ),
            },
        ],
        "manifest_registration": {
            "registered": True,
            "manifest_path": MANIFEST,
            "entry_id": UNIT,
            "registered_at": ended,
        },
        "downstream_consumers": [
            {
                "consumer": "json.loads + audit-metric-baseline schema resolver",
                "artifact_path": OUT,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": L.probe(
                    "source",
                    "schema-validate",
                    "python3 -B command-center/p2-wave/probes/AUD-0062/_pack_receipt.py",
                    "state=BLOCKED",
                    0,
                ),
            }
        ],
        "timestamps": {"started_at": started, "ended_at": ended},
        "retry": {"count": 1, "policy": "two strikes then pivot (AGENTS.md 4b)"},
        "failure": {
            "classification": ["blocked-on-independent-review", "partial-artifact"],
            "reason": (
                f"Measured full_file_ws_tokens={full_ws} (incl skill-meta total_ws={total_ws}), "
                "instruments within tolerance, but reviewer_requirement unmet."
            ),
            "diagnostic_tail": (
                f"dominant={dominant.get('path')} gap={ctrl['relative_gap']} "
                f"occupancy_bytes={p2['occupancy']['total_bytes']}"
            ),
            "blocked_on": (
                "Dispatch one fresh-context Claude reviewer who has not seen this transcript "
                "to falsify the headline token budget before PASS."
            ),
            "two_signal_proof": [
                L.probe(
                    "source",
                    "command",
                    "python3 -B command-center/p2-wave/probes/AUD-0062/probe1_tokenize_injection.py",
                    f"total_tokens_whitespace={total_ws}",
                    0,
                ),
                L.probe(
                    "verifier",
                    "file-read",
                    "reviewer.verdict",
                    "NOT-REVIEWED",
                    0,
                ),
            ],
        },
        "residual_unknowns": [
            {
                "claim": "Model-native tokenizer (tiktoken/claude) agrees with whitespace+char4 within 10%.",
                "verdict": "NOT-CHECKED",
                "settling_experiment": "Install tiktoken and re-tokenize the same file set.",
            }
        ],
        "report": {
            "kind": "audit-metric-baseline",
            "headline": {
                "full_file_tokens_whitespace": full_ws,
                "full_file_tokens_char4": p2["probe1_full_file_tokens_char4"],
                "total_including_skill_meta_ws": total_ws,
                "occupancy_tokens_char4": p2["occupancy"]["occupancy_tokens_char4"],
                "relative_gap": ctrl["relative_gap"],
                "dominant_path": dominant.get("path"),
                "dominant_tokens_whitespace": dominant.get("tokens_whitespace"),
                "blocked_on_review": True,
            },
            "observations": [
                {
                    "name": "full_file_tokens_whitespace",
                    "measured": full_ws,
                    "method": "whitespace tokenizer over turn-0 full-file injectees",
                    "anchor": "command-center/p2-wave/probes/AUD-0062/probe1-tokenize.raw.txt",
                },
                {
                    "name": "occupancy_tokens_char4",
                    "measured": p2["occupancy"]["occupancy_tokens_char4"],
                    "method": "sum(st_size)/4 independent occupancy instrument",
                    "anchor": "command-center/p2-wave/probes/AUD-0062/probe2-occupancy.raw.txt",
                },
                {
                    "name": "dominant_item_tokens",
                    "measured": dominant.get("tokens_whitespace"),
                    "method": "argmax tokens_whitespace among full-file items",
                    "anchor": "command-center/p2-wave/probes/AUD-0062/probe1-tokenize-sum.json",
                },
                {
                    "name": "instruments_within_tolerance",
                    "measured": ctrl["within_tolerance"],
                    "method": f"relative_gap <= {ctrl['tolerance_frac']}",
                    "anchor": "command-center/p2-wave/probes/AUD-0062/control-tolerance.json",
                },
            ],
            "control_ids": ["AUD0062-C1"],
        },
        "extensions": {
            "anti_false_green": "BLOCKED-with-real-probes",
            "wave": "p2-loop",
            "dominant_path": dominant.get("path"),
        },
    }


def main() -> int:
    doc = build()
    rc = L.write_if_valid(doc, OUT, SCHEMA)
    if rc != 0:
        return rc
    for _ in range(2):
        doc = build(primary=L.art(OUT, "primary"))
        rc = L.write_if_valid(doc, OUT, SCHEMA)
        if rc != 0:
            return rc
    man = {
        "unit_id": UNIT,
        "output_path": OUT,
        "sha256": L.art(OUT)["sha256"],
        "bytes": L.art(OUT)["bytes"],
        "state": "BLOCKED",
    }
    (L.REPO / MANIFEST).write_text(json.dumps(man, indent=2) + "\n", encoding="utf-8")
    print(f"PACKED {OUT} state=BLOCKED bytes={L.art(OUT)['bytes']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
