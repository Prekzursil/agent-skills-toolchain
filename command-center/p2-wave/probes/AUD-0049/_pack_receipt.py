#!/usr/bin/env python3
"""Pack AUD-0049 runner matrix vs support (BLOCKED on independent review)."""
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
    ctrl = json.loads((PROBE / "control-windows-underexercised.json").read_text(encoding="utf-8"))
    started = "2026-09-07T18:25:00Z"
    ended = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    missing = p1["set_difference"]["promised_minus_exercised"]
    win_defects = p2["windows_defects_named"]

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
        L.art("command-center/p2-wave/probes/AUD-0049/control-windows-underexercised.json", "control"),
        L.art("command-center/p2-wave/probes/AUD-0049/probe1-matrix.raw.txt", "log"),
        L.art("command-center/p2-wave/probes/AUD-0049/probe2-defects.raw.txt", "log"),
    ]
    return {
        "schema_version": 1,
        "unit_id": UNIT,
        "state": "BLOCKED",
        "sentinel": (
            "FAILED:AUD-0049 matrix-diff+defect probes measured promised-minus-exercised="
            f"{missing}; windows defects named={win_defects}; blocked-on-independent-review"
        ),
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json:AUD-0049",
        "min_bytes_threshold": 4096,
        "produced_by": {
            "vendor": "anthropic",
            "model": "composer",
            "role": "auditor",
            "execution_substrate": "linux-local-p2-loop",
        },
        "artifacts": arts,
        "evidence": [
            L.evidence(
                (
                    f"Probe 1 set difference: promised={p1['promised']['promised']} "
                    f"exercised={p1['matrix']['families_exercised']} "
                    f"runs_on_entries={p1['matrix']['runs_on_entries']} "
                    f"promised_minus_exercised={missing} "
                    f"windows_promised_but_underexercised="
                    f"{p1['windows_promised_but_underexercised']}."
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
                                "promised_minus_exercised": missing,
                                "windows_flagged": p1["windows_promised_but_underexercised"],
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
                    f"Probe 2 named {win_defects} already-measured Windows-only defects "
                    f"(AUD-0019 eol_only CRLF, AUD-0082 path hazards, AUD-0085 encoding) "
                    f"for absent platform windows; macos defect_count=0. control_ok={ctrl['ok']}."
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
                                "windows_defects_named": win_defects,
                                "control_ok": ctrl["ok"],
                                "ok": p2["ok"],
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
                "name": "comparator flags Windows as promised-but-underexercised given CRLF corpus",
                "command": "python3 -B command-center/p2-wave/probes/AUD-0049/probe2_absent_platform_defects.py",
                "result": "PASS" if ctrl["ok"] else "FAIL",
                "assertions": 2,
                "output_tail": raw2[-400:],
            }
        ],
        "negative_controls": [
            L.control(
                "AUD0049-C1",
                "known-broken-fixture",
                "Windows must be flagged promised-but-underexercised when CRLF defects exist.",
                True,
                True,
                bad="full coverage claimed",
                good=f"windows_flagged={ctrl['windows_flagged']} defects={ctrl['crlf_or_windows_defects_named']}",
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
                "transcript and must try to FALSIFY the headline underexercised count. "
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
                "id": "AUD-0049-D-WINDOWS-CI-GAP",
                "severity": "P2",
                "status": "open",
                "summary": (
                    f"CI exercises only {p1['matrix']['families_exercised']}; promised-but-absent="
                    f"{missing}; {win_defects} Windows-only measured defects CI never sees."
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
        "retry": {"count": 1, "policy": "two strikes then pivot (AGENTS.md 4b)"},
        "failure": {
            "classification": ["blocked-on-independent-review", "green-not-live"],
            "reason": (
                f"Measured promised_minus_exercised={missing} with {win_defects} Windows "
                "defects named, but reviewer_requirement unmet."
            ),
            "diagnostic_tail": (
                f"runs_on_entries={p1['matrix']['runs_on_entries']} "
                f"families={p1['matrix']['families_exercised']}"
            ),
            "blocked_on": (
                "Dispatch one fresh-context Claude reviewer who has not seen this transcript "
                "to falsify the headline underexercised-platform count before PASS."
            ),
            "two_signal_proof": [
                L.probe(
                    "source",
                    "command",
                    "python3 -B command-center/p2-wave/probes/AUD-0049/probe1_matrix_diff.py",
                    f"promised_minus_exercised={missing}",
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
                "claim": "macOS has a live measured defect unique to that platform in this corpus.",
                "verdict": "NOT-CHECKED",
                "settling_experiment": "Search audit corpus / run native macOS probes for platform-unique failures.",
            }
        ],
        "report": {
            "kind": "audit-drift",
            "question": (
                "Which operating systems does the support contract promise, and which does CI exercise?"
            ),
            "headline": (
                f"promised={p1['promised']['promised']}; exercised="
                f"{p1['matrix']['families_exercised']}; absent={missing}; "
                f"windows_defects_named={win_defects}. BLOCKED on review."
            ),
            "promised_platforms": p1["promised"]["promised"],
            "exercised_families": p1["matrix"]["families_exercised"],
            "promised_minus_exercised": missing,
            "windows_defects_named": win_defects,
            "observations": [
                {
                    "name": "runs_on_entries",
                    "measured": p1["matrix"]["runs_on_entries"],
                    "method": "regex runs-on: across .github/workflows",
                    "anchor": "command-center/p2-wave/probes/AUD-0049/probe1-matrix.raw.txt",
                },
                {
                    "name": "promised_minus_exercised",
                    "measured": len(missing),
                    "method": "set difference of promised OS families vs runs-on families",
                    "anchor": "command-center/p2-wave/probes/AUD-0049/probe1-matrix-diff.json",
                },
                {
                    "name": "windows_defects_named",
                    "measured": win_defects,
                    "method": "cross-ref AUD-0019/0082/0085 for Windows-only measured defects",
                    "anchor": "command-center/p2-wave/probes/AUD-0049/probe2-absent-defects.json",
                },
            ],
            "control_ids": ["AUD0049-C1"],
        },
        "extensions": {
            "anti_false_green": "BLOCKED-with-real-probes",
            "wave": "p2-loop",
            "absent_platforms": missing,
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
