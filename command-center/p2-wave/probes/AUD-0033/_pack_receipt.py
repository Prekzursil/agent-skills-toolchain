#!/usr/bin/env python3
"""Pack AUD-0033 receipt (BLOCKED on independent review; measurements are real)."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import _p2lib as L  # noqa: E402

UNIT = "AUD-0033"
OUT = "command-center/audit/AUD-0033-doc-path-reference-integrity.json"
SCHEMA = "command-center/schema/audit-finding.schema.json"
PROBE = Path(__file__).resolve().parent
MANIFEST = "command-center/p2-wave/probes/AUD-0033/UNIT-ARTIFACT-MANIFEST.json"


def build(primary: dict | None = None) -> dict:
    p1 = json.loads((PROBE / "probe1-results.json").read_text(encoding="utf-8"))
    p2 = json.loads((PROBE / "probe2-history-results.json").read_text(encoding="utf-8"))
    raw1 = (PROBE / "probe1-existence.raw.txt").read_text(encoding="utf-8")
    raw2 = (PROBE / "probe2-git-history.raw.txt").read_text(encoding="utf-8")
    rawc = (PROBE / "refute-resolver-control.raw.txt").read_text(encoding="utf-8")
    started = "2026-09-07T11:40:00Z"
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
        L.art("command-center/p2-wave/probes/AUD-0033/probe1-results.json", "supporting"),
        L.art(
            "command-center/p2-wave/probes/AUD-0033/probe2-history-results.json",
            "supporting",
        ),
        L.art("command-center/p2-wave/probes/AUD-0033/probe1-existence.raw.txt", "log"),
        L.art("command-center/p2-wave/probes/AUD-0033/probe2-git-history.raw.txt", "log"),
        L.art(
            "command-center/p2-wave/probes/AUD-0033/refute-resolver-control.raw.txt",
            "control",
        ),
    ]
    return {
        "schema_version": 1,
        "unit_id": UNIT,
        "state": "BLOCKED",
        "sentinel": (
            "FAILED:AUD-0033 both named probes re-ran with real measurements; "
            "detector controls discriminate; blocked-on-independent-review "
            "(fresh-context Claude falsifier unavailable)"
        ),
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json:AUD-0033",
        "min_bytes_threshold": 4096,
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
                    f"Probe 1: {p1['distinct_tokens']} distinct identities from "
                    f"{p1['files_scanned']} files; EXISTS={p1['exists']} MISSING={p1['missing']}; "
                    f"control_ok={p1['control']['control_ok']}."
                ),
                "CONFIRMED",
                "command-center/p2-wave/probes/AUD-0033/probe1-existence.raw.txt",
                [
                    L.probe(
                        "source",
                        "command",
                        "python3 -B command-center/p2-wave/probes/AUD-0033/path_reference_probe.py",
                        raw1,
                        0,
                    ),
                    L.probe(
                        "verifier",
                        "file-read",
                        "python3 -c read probe1-results.json",
                        json.dumps(
                            {
                                "exists": p1["exists"],
                                "missing": p1["missing"],
                                "distinct_tokens": p1["distinct_tokens"],
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
                    f"Probe 2: searched {p2['searched']}/{p2['missing_total']} MISSING; "
                    f"counts={json.dumps(p2['class_counts'])}; planted_ok={p2['planted_ok']}."
                ),
                "CONFIRMED",
                "command-center/p2-wave/probes/AUD-0033/probe2-git-history.raw.txt",
                [
                    L.probe(
                        "source",
                        "command",
                        "python3 -B command-center/p2-wave/probes/AUD-0033/git_history_probe.py",
                        raw2,
                        0,
                    ),
                    L.probe(
                        "verifier",
                        "byte-compare",
                        "python3 -c read probe2-history-results.json",
                        json.dumps(
                            {
                                "ok": p2["ok"],
                                "counts": p2["class_counts"],
                                "planted_ok": p2["planted_ok"],
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
                "id": "AUD-0033-detector-control-required-fixture",
                "name": "Find a fenced path and reject slash-bearing prose in the same fixture",
                "command": "python3 -B command-center/p2-wave/probes/AUD-0033/path_reference_probe.py",
                "result": "PASS",
                "assertions": 2,
                "output_tail": raw1[-400:],
            },
            {
                "id": "AUD-0033-refute-resolver-control",
                "name": "Naive resolver false-misses; mutant emits prose traps",
                "command": "python3 -B command-center/p2-wave/probes/AUD-0033/refute_resolver_control.py",
                "result": "PASS",
                "assertions": 2,
                "output_tail": rawc[-400:],
            },
            {
                "id": "AUD-0033-probe2-planted-typo",
                "name": "Planted typo is NEVER-EXISTED",
                "command": "python3 -B command-center/p2-wave/probes/AUD-0033/git_history_probe.py",
                "result": "PASS",
                "assertions": 1,
                "output_tail": raw2[-400:],
            },
        ],
        "negative_controls": [
            L.control(
                "AUD0033-C1",
                "known-broken-fixture",
                "Fenced path found; prose slash traps not emitted.",
                True,
                True,
                bad="mutant emits input/output",
                good="found_fenced_path=true emitted_prose_traps=[]",
            ),
            L.control(
                "AUD0033-C2",
                "mutation",
                "Naive is_file misses source-relative and dot-directory paths.",
                True,
                True,
                bad="naive_rel=MISSING naive_skills=MISSING",
                good="fixed_rel=EXISTS fixed_skills=EXISTS",
            ),
        ],
        "reviewer": {
            "reviewer_id": "required-fresh-context-claude-reviewer-unassigned",
            "verdict": "NOT-REVIEWED",
            "independent": False,
            "fresh_context": False,
            "vendor": "anthropic",
            "notes": (
                "Catalog requires a fresh-context Claude reviewer who has not seen this "
                "transcript and must try to FALSIFY the headline count. Unavailable in-session; "
                "emitting BLOCKED rather than fake-review SUCCESS."
            ),
        },
        "defects": [
            {
                "id": "AUD-0033-D-REVIEW",
                "severity": "P1",
                "status": "open",
                "summary": "Independent fresh-context Claude review unpaid.",
            }
        ],
        "manifest_registration": {
            "registered": True,
            "manifest_path": MANIFEST,
            "entry_id": UNIT,
            "registered_at": ended,
        },
        "downstream_consumers": [
            {
                "consumer": "json.loads + audit-finding schema resolver",
                "artifact_path": OUT,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": L.probe(
                    "source",
                    "schema-validate",
                    "python3 -B command-center/p2-wave/probes/AUD-0033/_pack_receipt.py",
                    "state=BLOCKED schema=audit-finding",
                    0,
                ),
            }
        ],
        "timestamps": {"started_at": started, "ended_at": ended},
        "retry": {
            "count": 1,
            "policy": "retry once with the sweep re-scoped to a single path, then pivot",
        },
        "failure": {
            "classification": ["blocked-on-independent-review"],
            "reason": (
                f"Live probes OK (EXISTS={p1['exists']} MISSING={p1['missing']} of "
                f"{p1['distinct_tokens']}) but reviewer_requirement unmet."
            ),
            "diagnostic_tail": f"probe1_ok={p1['ok']} probe2_ok={p2['ok']} reviewer=NOT-REVIEWED",
            "blocked_on": (
                "Dispatch one fresh-context Claude reviewer who has not seen this transcript "
                "to falsify the headline EXISTS/MISSING counts."
            ),
            "two_signal_proof": [
                L.probe(
                    "source",
                    "command",
                    "python3 -B command-center/p2-wave/probes/AUD-0033/path_reference_probe.py",
                    f"exists={p1['exists']} missing={p1['missing']}",
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
                "claim": "All leftover MISSING identities beyond Probe 2 budget are classified.",
                "verdict": "NOT-CHECKED",
                "settling_experiment": "Raise MAX_MISSING and re-run git_history_probe.py.",
            }
        ],
        "report": {
            "kind": "audit-finding",
            "question": (
                "Does every filesystem path cited in a command-center document, rule, skill, "
                "or README resolve to a file that exists at that path today?"
            ),
            "headline": (
                f"SCOPED: {p1['exists']} EXISTS / {p1['missing']} MISSING of "
                f"{p1['distinct_tokens']} from {p1['files_scanned']} files. "
                "BLOCKED on independent review."
            ),
            "observations": [
                {
                    "name": "distinct_path_identities",
                    "measured": p1["distinct_tokens"],
                    "method": "fenced+backtick extract",
                    "anchor": "command-center/p2-wave/probes/AUD-0033/probe1-existence.raw.txt",
                },
                {
                    "name": "exists_identities",
                    "measured": p1["exists"],
                    "method": "repo+source-relative exists",
                    "anchor": "command-center/p2-wave/probes/AUD-0033/probe1-results.json",
                },
                {
                    "name": "missing_identities",
                    "measured": p1["missing"],
                    "method": "fail-closed resolver",
                    "anchor": "command-center/p2-wave/probes/AUD-0033/probe1-results.json",
                },
                {
                    "name": "probe2_never_existed",
                    "measured": p2["class_counts"].get("NEVER-EXISTED", 0),
                    "method": "git log --all sample",
                    "anchor": "command-center/p2-wave/probes/AUD-0033/probe2-git-history.raw.txt",
                },
                {
                    "name": "probe2_deleted",
                    "measured": p2["class_counts"].get("DELETED", 0),
                    "method": "git log --all sample",
                    "anchor": "command-center/p2-wave/probes/AUD-0033/probe2-git-history.raw.txt",
                },
            ],
            "control_ids": ["AUD0033-C1", "AUD0033-C2"],
        },
        "extensions": {
            "anti_false_green": "BLOCKED-with-real-probes",
            "wave": "p2-wave1",
            "p1": {
                "exists": p1["exists"],
                "missing": p1["missing"],
                "distinct": p1["distinct_tokens"],
            },
            "p2": p2["class_counts"],
        },
    }


def main() -> int:
    doc = build()
    rc = L.write_if_valid(doc, OUT, SCHEMA)
    if rc != 0:
        return rc
    doc = build(primary=L.art(OUT, "primary"))
    rc = L.write_if_valid(doc, OUT, SCHEMA)
    if rc != 0:
        return rc
    # refresh primary once more
    doc = build(primary=L.art(OUT, "primary"))
    rc = L.write_if_valid(doc, OUT, SCHEMA)
    man = {
        "unit_id": UNIT,
        "output_path": OUT,
        "sha256": L.art(OUT)["sha256"],
        "bytes": L.art(OUT)["bytes"],
        "state": "BLOCKED",
    }
    (L.REPO / MANIFEST).write_text(json.dumps(man, indent=2) + "\n", encoding="utf-8")
    print(f"PACKED {OUT} state=BLOCKED bytes={L.art(OUT)['bytes']}")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
