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
    ctrl = p2["control"]
    dominant = p1.get("dominant_item") or {}
    started = "2026-09-07T18:25:00Z"
    ended = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
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
        L.art("command-center/p2-wave/probes/AUD-0062/probe1-tokenize.raw.txt", "log"),
        L.art("command-center/p2-wave/probes/AUD-0062/probe2-occupancy.raw.txt", "log"),
        L.art("command-center/p2-wave/probes/AUD-0062/control-tolerance.json", "supporting"),
    ]
    return {
        "schema_version": 1,
        "unit_id": UNIT,
        "state": "BLOCKED",
        "sentinel": (
            "FAILED:AUD-0062 probes measured always-on token budget "
            f"full_model={p2['probe1_full_file_tokens_model']} "
            f"occupancy_c4={p2['occupancy']['occupancy_tokens_char4']} "
            f"dominant={dominant.get('path')}; blocked-on-independent-review"
        ),
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json:AUD-0062",
        "min_bytes_threshold": 2048,
        "produced_by": {
            "vendor": "anthropic",
            "model": "composer",
            "role": "tool-author",
            "execution_substrate": "linux-local-p2-wave1",
        },
        "artifacts": arts,
        "evidence": [
            L.evidence(
                (
                    f"Probe 1 tokenizer={p1.get('tokenizer')} summed "
                    f"{p1.get('full_file_tokens_model', p1.get('total_tokens_model'))} "
                    f"model tokens across {p1['item_count']} injection items; "
                    f"dominant={dominant.get('path')} "
                    f"tok={dominant.get('tokens_model')}."
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
                                "tokenizer": p1.get("tokenizer"),
                                "full_file_tokens_model": p1.get("full_file_tokens_model"),
                                "dominant": dominant.get("path"),
                            }
                        ),
                        0,
                    ),
                ],
                "almost-certain",
            ),
            L.evidence(
                (
                    f"Probe 2 occupancy instrument={p2['occupancy']['method']} "
                    f"tokens={p2['occupancy']['occupancy_tokens_char4']}; "
                    f"gap_c4_vs_occ={ctrl.get('relative_gap_c4_vs_occ')}; "
                    f"control_ok={ctrl['ok']} (omit-dominant gap="
                    f"{(ctrl.get('bad_state') or {}).get('gap')})."
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
                        "python3 -c read probe2-occupancy-compare.json",
                        json.dumps(
                            {
                                "within_tolerance": ctrl.get("within_tolerance"),
                                "fired_on_bad_state": ctrl.get("fired_on_bad_state"),
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
                "name": "Two instruments within tolerance; omit-dominant exceeds",
                "command": "python3 -B command-center/p2-wave/probes/AUD-0062/probe2_occupancy_compare.py",
                "result": "PASS" if ctrl["ok"] else "FAIL",
                "assertions": 2,
                "output_tail": raw2[-500:],
            }
        ],
        "negative_controls": [
            L.control(
                "AUD0062-C1",
                "known-broken-fixture",
                ctrl["description"],
                bool(ctrl["fired_on_bad_state"]),
                bool(ctrl["silent_on_good_state"]),
                bad=json.dumps(ctrl.get("bad_state"), sort_keys=True),
                good=json.dumps(ctrl.get("good_state"), sort_keys=True),
            )
        ],
        "reviewer": {
            "reviewer_id": "required-fresh-context-claude-reviewer-unassigned",
            "verdict": "NOT-REVIEWED",
            "independent": False,
            "fresh_context": False,
            "vendor": "anthropic",
            "notes": (
                "Catalog requires a fresh-context Claude reviewer who has not seen "
                "this transcript and must try to FALSIFY the headline token count. "
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
                "id": "AUD-0062-D-DOMINANT",
                "severity": "P2",
                "status": "open",
                "summary": (
                    f"Dominant always-on injectee {dominant.get('path')} costs "
                    f"{dominant.get('tokens_model')} model tokens "
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
        "retry": {
            "count": 1,
            "policy": "two strikes then pivot (AGENTS.md 4b)",
        },
        "failure": {
            "classification": ["blocked-on-independent-review", "partial-artifact"],
            "reason": (
                f"Measured full_model={p2['probe1_full_file_tokens_model']} vs "
                f"occupancy={p2['occupancy']['occupancy_tokens_char4']}, but "
                "reviewer_requirement unmet."
            ),
            "diagnostic_tail": (
                f"tokenizer={p1.get('tokenizer')} gap_c4="
                f"{ctrl.get('relative_gap_c4_vs_occ')} control_ok={ctrl['ok']}"
            ),
            "blocked_on": (
                "Dispatch one fresh-context Claude reviewer who has not seen this "
                "transcript to falsify the headline token budget before PASS."
            ),
            "two_signal_proof": [
                L.probe(
                    "source",
                    "command",
                    "python3 -B command-center/p2-wave/probes/AUD-0062/probe1_tokenize_injection.py",
                    f"full_model={p2['probe1_full_file_tokens_model']}",
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
                "claim": "Live session-reported context occupancy at turn 0 (runtime meter).",
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Capture a turn-0 session transcript with vendor-reported "
                    "context_tokens and re-compare within the same tolerance."
                ),
            }
        ],
        "report": {
            "kind": "audit-metric-baseline",
            "question": (
                "What is the exact token cost of everything injected into turn 0, "
                "and which single item dominates it?"
            ),
            "headline": (
                f"full_model_tokens={p2['probe1_full_file_tokens_model']}; "
                f"occupancy_char4={p2['occupancy']['occupancy_tokens_char4']}; "
                f"dominant={dominant.get('path')} "
                f"({dominant.get('tokens_model')} tok). BLOCKED on review."
            ),
            "observations": [
                {
                    "name": "full_file_tokens_model",
                    "measured": p2["probe1_full_file_tokens_model"],
                    "method": f"tokenizer={p1.get('tokenizer')} per-file sum",
                    "anchor": "command-center/p2-wave/probes/AUD-0062/probe1-tokenize-sum.json",
                },
                {
                    "name": "occupancy_tokens_char4",
                    "measured": p2["occupancy"]["occupancy_tokens_char4"],
                    "method": "sum(stat.st_size)/4 turn-0 full-file set",
                    "anchor": "command-center/p2-wave/probes/AUD-0062/probe2-occupancy-compare.json",
                },
                {
                    "name": "relative_gap_c4_vs_occ",
                    "measured": float(ctrl.get("relative_gap_c4_vs_occ") or 0),
                    "method": "abs(a-b)/max(a,b)",
                    "anchor": "command-center/p2-wave/probes/AUD-0062/control-tolerance.json",
                },
                {
                    "name": "dominant_tokens_model",
                    "measured": int(dominant.get("tokens_model") or 0),
                    "method": "argmax tokens_model among full-file injectees",
                    "anchor": "command-center/p2-wave/probes/AUD-0062/probe1-tokenize.raw.txt",
                },
                {
                    "name": "injection_item_count",
                    "measured": p1["item_count"],
                    "method": "count existing injection candidates + skill meta",
                    "anchor": "command-center/p2-wave/probes/AUD-0062/probe1-tokenize-sum.json",
                },
            ],
            "control_ids": ["AUD0062-C1"],
        },
        "extensions": {
            "anti_false_green": "BLOCKED-with-real-probes",
            "wave": "p2-wave1",
            "dominant_path": dominant.get("path"),
            "tokenizer": p1.get("tokenizer"),
        },
    }


def main() -> int:
    for script in ("probe1_tokenize_injection.py", "probe2_occupancy_compare.py"):
        rc, out = L.run(["python3", "-B", str(PROBE / script)])
        if rc != 0:
            print(out)
            print(f"FAILED:{UNIT} {script} exit={rc}")
            return rc
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
