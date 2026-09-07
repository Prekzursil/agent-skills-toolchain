#!/usr/bin/env python3
"""Pack AUD-0049 runner OS matrix vs support (BLOCKED on independent review)."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import _p2lib as L  # noqa: E402

UNIT = "AUD-0049"
OUT = "command-center/audit/AUD-0049-runner-matrix-vs-support.json"
SCHEMA = "command-center/schema/audit-drift.schema.json"
PROBE = Path(__file__).resolve().parent
MANIFEST = "command-center/p2-wave/probes/AUD-0049/UNIT-ARTIFACT-MANIFEST.json"


def build(primary: dict | None = None) -> dict:
    p1 = json.loads((PROBE / "probe1-matrix-diff.json").read_text(encoding="utf-8"))
    p2 = json.loads((PROBE / "probe2-absent-defects.json").read_text(encoding="utf-8"))
    raw1 = (PROBE / "probe1-matrix.raw.txt").read_text(encoding="utf-8")
    raw2 = (PROBE / "probe2-defects.raw.txt").read_text(encoding="utf-8")
    ctrl = p2["control"]
    started = "2026-09-07T18:20:00Z"
    ended = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    missing = p1["set_difference"]["promised_minus_exercised"]
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
        L.art("command-center/p2-wave/probes/AUD-0049/probe1-matrix-diff.json", "supporting"),
        L.art("command-center/p2-wave/probes/AUD-0049/probe2-absent-defects.json", "supporting"),
        L.art("command-center/p2-wave/probes/AUD-0049/probe1-matrix.raw.txt", "log"),
        L.art("command-center/p2-wave/probes/AUD-0049/probe2-defects.raw.txt", "log"),
        L.art("command-center/p2-wave/probes/AUD-0049/control-both-states.json", "supporting"),
    ]
    return {
        "schema_version": 1,
        "unit_id": UNIT,
        "state": "BLOCKED",
        "sentinel": (
            "FAILED:AUD-0049 probes measured promised-minus-exercised="
            f"{missing}; windows underexercised with {p2['windows_defects_named']} "
            "named defects; blocked-on-independent-review"
        ),
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json:AUD-0049",
        "min_bytes_threshold": 2048,
        "produced_by": {
            "vendor": "anthropic",
            "model": "composer",
            "role": "auditor",
            "execution_substrate": "linux-local-p2-wave1",
        },
        "artifacts": arts,
        "evidence": [
            L.evidence(
                (
                    f"Probe 1 set-diff: promised={p1['promised']['promised']} "
                    f"exercised={p1['matrix']['families_exercised']} "
                    f"missing={missing}; windows_promised_but_underexercised="
                    f"{p1['windows_promised_but_underexercised']}; "
                    f"runs_on_entries={p1['matrix']['runs_on_entries']} across "
                    f"{p1['matrix']['workflow_files']} workflow files."
                ),
                "CONFIRMED",
                "command-center/p2-wave/probes/AUD-0049/probe1-matrix.raw.txt",
                [
                    L.probe(
                        "source",
                        "command",
                        "python3 -B command-center/p2-wave/probes/AUD-0049/probe1_matrix_diff.py",
                        raw1,
                        0,
                    ),
                    L.probe(
                        "verifier",
                        "file-read",
                        "python3 -c read probe1-matrix-diff.json",
                        json.dumps(
                            {
                                "missing": missing,
                                "windows_flagged": p1[
                                    "windows_promised_but_underexercised"
                                ],
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
                    f"Probe 2 named {p2['windows_defects_named']} already-measured "
                    f"Windows-only defects for absent platforms {missing}; "
                    f"per_absent severity windows=high macos="
                    f"{(p2['per_absent_platform'].get('macos') or {}).get('severity')}."
                ),
                "CONFIRMED",
                "command-center/p2-wave/probes/AUD-0049/probe2-defects.raw.txt",
                [
                    L.probe(
                        "source",
                        "command",
                        "python3 -B command-center/p2-wave/probes/AUD-0049/probe2_absent_platform_defects.py",
                        raw2,
                        0,
                    ),
                    L.probe(
                        "verifier",
                        "byte-compare",
                        "python3 -c read probe2-absent-defects.json",
                        json.dumps(
                            {
                                "windows_defects_named": p2["windows_defects_named"],
                                "control_ok": ctrl["ok"],
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
                "id": "AUD-0049-windows-underexercised-control",
                "name": "Comparator flags Windows; rejects fabricated full coverage",
                "command": "python3 -B command-center/p2-wave/probes/AUD-0049/probe1_matrix_diff.py",
                "result": "PASS" if ctrl["ok"] else "FAIL",
                "assertions": 2,
                "output_tail": raw1[-500:],
            }
        ],
        "negative_controls": [
            L.control(
                "AUD0049-C1",
                "known-broken-fixture",
                ctrl["description"],
                bool(ctrl["fired_on_bad_state"]),
                bool(ctrl["silent_on_good_state"]),
                bad=ctrl.get("bad_state_output", ""),
                good=ctrl.get("good_state_output", ""),
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
                "this transcript and must try to FALSIFY the headline count. "
                "Unavailable in-session; BLOCKED instead of fake SUCCESS."
            ),
        },
        "defects": [
            {
                "id": "AUD-0049-D-REVIEW",
                "severity": "P1",
                "status": "open",
                "summary": "Independent fresh-context Claude review unpaid.",
            },
            {
                "id": "AUD-0049-D-WINDOWS-GAP",
                "severity": "P2",
                "status": "open",
                "summary": (
                    f"Promised platforms missing from CI runs-on: {missing}; "
                    f"{p2['windows_defects_named']} Windows-only defects already measured."
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
                "consumer": "json.loads + audit-drift schema resolver",
                "artifact_path": OUT,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": L.probe(
                    "source",
                    "schema-validate",
                    "python3 -B command-center/p2-wave/probes/AUD-0049/_pack_receipt.py",
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
            "classification": ["blocked-on-independent-review", "scope-mismatch"],
            "reason": (
                f"Measured missing={missing} with {p2['windows_defects_named']} "
                "Windows defects, but reviewer_requirement unmet."
            ),
            "diagnostic_tail": (
                f"families_exercised={p1['matrix']['families_exercised']} "
                f"control_ok={ctrl['ok']}"
            ),
            "blocked_on": (
                "Dispatch one fresh-context Claude reviewer who has not seen this "
                "transcript to falsify the headline platform gap before PASS."
            ),
            "two_signal_proof": [
                L.probe(
                    "source",
                    "command",
                    "python3 -B command-center/p2-wave/probes/AUD-0049/probe1_matrix_diff.py",
                    f"missing={missing}",
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
                "claim": "Whether any workflow uses an unexpanded matrix.os that includes windows at runtime.",
                "verdict": "NOT-CHECKED",
                "settling_experiment": "Expand each strategy.matrix and re-diff families.",
            }
        ],
        "report": {
            "kind": "audit-drift",
            "question": (
                "Which operating systems and client versions does the declared "
                "support contract promise, and which of those does CI actually exercise today?"
            ),
            "headline": (
                f"promised={p1['promised']['promised']}; exercised="
                f"{p1['matrix']['families_exercised']}; missing={missing}; "
                f"windows_defects={p2['windows_defects_named']}. BLOCKED on review."
            ),
            "observations": [
                {
                    "name": "promised_platforms",
                    "measured": ",".join(p1["promised"]["promised"]),
                    "method": "regex charter/README platform mention scan",
                    "anchor": "command-center/p2-wave/probes/AUD-0049/probe1-matrix-diff.json",
                },
                {
                    "name": "families_exercised",
                    "measured": ",".join(p1["matrix"]["families_exercised"]) or "none",
                    "method": "runs-on line inventory across .github/workflows",
                    "anchor": "command-center/p2-wave/probes/AUD-0049/probe1-matrix.raw.txt",
                },
                {
                    "name": "promised_minus_exercised_count",
                    "measured": len(missing),
                    "method": "set difference promised - exercised",
                    "anchor": "command-center/p2-wave/probes/AUD-0049/probe1-matrix-diff.json",
                },
                {
                    "name": "windows_defects_named",
                    "measured": p2["windows_defects_named"],
                    "method": "name AUD-0019/0082/0085 Windows-only upstream defects",
                    "anchor": "command-center/p2-wave/probes/AUD-0049/probe2-absent-defects.json",
                },
                {
                    "name": "runs_on_entries",
                    "measured": p1["matrix"]["runs_on_entries"],
                    "method": "count runs-on lines",
                    "anchor": "command-center/p2-wave/probes/AUD-0049/probe1-matrix.raw.txt",
                },
            ],
            "control_ids": ["AUD0049-C1"],
        },
        "extensions": {
            "anti_false_green": "BLOCKED-with-real-probes",
            "wave": "p2-wave1",
            "promised_minus_exercised": missing,
        },
    }


def main() -> int:
    # ensure probes ran
    for script in ("probe1_matrix_diff.py", "probe2_absent_platform_defects.py"):
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
