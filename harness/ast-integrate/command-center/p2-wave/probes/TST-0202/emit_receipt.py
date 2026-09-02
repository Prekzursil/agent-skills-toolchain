#!/usr/bin/env python3
"""Emit command-center/receipts/TST-0202.json from a live probe run."""
from __future__ import annotations

import hashlib
import json
import platform
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import scenario as S  # noqa: E402

OUT_REL = "command-center/receipts/TST-0202.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0202/probe1_both_states.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0202/probe2_negative_alias.py"
)
ARTIFACT_RELS = [
    "tools/command-center/artifact_writer.py",
    "command-center/p2-wave/probes/TST-0202/scenario.py",
    "command-center/p2-wave/probes/TST-0202/probe1_both_states.py",
    "command-center/p2-wave/probes/TST-0202/probe2_negative_alias.py",
]
QUESTION = (
    "When the target is reached through a junction/symlink, is the length "
    "budget applied to the resolved path rather than the short alias? PASS "
    "requires the resolved measurement; measuring the alias is the defect "
    "being tested."
)


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def build_receipt() -> dict:
    both = S.run_both_states()
    neg = S.run_negative_alias()
    if not both["pass"] or not neg["pass"]:
        raise SystemExit(
            f"FAILED:TST-0202 live matrix both={both['pass']} neg={neg['pass']}"
        )

    artifacts = []
    for rel in ARTIFACT_RELS:
        path = REPO / rel
        sha, size = digest(path)
        artifacts.append(
            {
                "path": rel,
                "sha256": sha,
                "bytes": size,
                "exists": True,
                "role": "implementation" if rel.startswith("tools/") else "probe",
            }
        )

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    pwsh = shutil.which("pwsh")
    return {
        "unit_id": "TST-0202",
        "id": "TST-0202",
        "title": (
            "Length is measured on the RESOLVED path, through junctions "
            "and symlinks"
        ),
        "state": "SUCCESS",
        "sentinel": "SUCCESS:TST-0202",
        "completion_sentinel": "SUCCESS:TST-0202",
        "report_kind": "portability_report",
        "report": {
            "kind": "portability_report",
            "observations": [
                {
                    "name": "writer_measured_resolved_length",
                    "measured": neg["writer_measured_length"],
                    "method": "pathlib.Path.resolve via write_artifact",
                    "anchor": "tools/command-center/artifact_writer.py",
                },
                {
                    "name": "independent_readlink_f_length",
                    "measured": neg["independent_length"],
                    "method": "GNU coreutils readlink -f",
                    "anchor": "command-center/p2-wave/probes/TST-0202/scenario.py",
                },
            ],
            "control_ids": [
                "TST-0202-BOTH-STATES",
                "TST-0202-NEGATIVE-ALIAS",
            ],
        },
        "registered": True,
        "cloud_ok": False,
        "question": QUESTION,
        "phase": "10",
        "ts": now,
        "host": {
            "os": platform.system(),
            "release": platform.release(),
            "python": platform.python_version(),
            "junction_analog": (
                "POSIX directory symlink (NTFS junction unavailable on Linux)"
            ),
        },
        "budget": {
            "name": "WINDOWS_MAX_PATH",
            "value": 260,
            "comparison": "measured_length <= budget is admitted",
            "applied_to": "resolved path (pathlib.Path.resolve)",
        },
        "evidence_requirement": (
            "two independent signals: (a) the measured length recorded by "
            "the writer, and (b) an independent resolution of the same path "
            "by a different API"
        ),
        "evidence": [
            {
                "id": "E1-writer-measured-length",
                "signal": 1,
                "kind": "live-tree",
                "api": "pathlib.Path.resolve via tools/command-center/artifact_writer.py",
                "claim": (
                    "Production write_artifact records measured_length of the "
                    "resolved path and refuses when that length exceeds 260."
                ),
                "writer_measured_length": neg["writer_measured_length"],
                "alias_length": neg["over"]["alias_length"],
                "resolved_length": neg["over"]["resolved_length"],
                "production_refused": neg["production_refused"],
            },
            {
                "id": "E2-independent-readlink-f",
                "signal": 2,
                "kind": "live-tree",
                "api": "GNU coreutils readlink -f (not pathlib)",
                "claim": (
                    "Independent resolution length equals the writer's "
                    "recorded measured_length."
                ),
                "independent_path": neg["independent_readlink_f"],
                "independent_length": neg["independent_length"],
                "bash_path": neg["bash_resolved"],
                "bash_length": neg["bash_length"],
                "lengths_agree": neg["lengths_agree"],
            },
        ],
        "tests": [
            {
                "id": "TST-0202-BOTH-STATES",
                "name": (
                    "both-states control: a direct (non-junction) path of "
                    "equal resolved length behaves identically"
                ),
                "command": P1,
                "result": "PASS" if both["pass"] else "FAIL",
                "identical_over_budget": both["identical_over_budget"],
                "identical_in_budget": both["identical_in_budget"],
                "over_resolved_length": both["over"]["resolved_length"],
                "over_direct_resolved_length": both["over"]["direct_resolved_length"],
                "junction_over_measured": both["junction_over"]["measured_length"],
                "direct_over_measured": both["direct_over"]["measured_length"],
            },
            {
                "id": "TST-0202-NEGATIVE-ALIAS",
                "name": (
                    "negative control: measuring the alias must be shown "
                    "to admit an over-limit write"
                ),
                "command": P2,
                "result": "PASS" if neg["pass"] else "FAIL",
                "alias_admits_over_limit_write": neg[
                    "alias_admits_over_limit_write"
                ],
                "defect_measured_length": neg["defect"]["measured_length"],
                "defect_measure": neg["defect"]["measure"],
                "production_refused": neg["production_refused"],
            },
        ],
        "negative_controls": [
            {
                "id": "NC-alias-measurement",
                "description": (
                    "write_measuring_alias applies the budget to the short "
                    "symlink alias and therefore writes a file whose resolved "
                    "path exceeds WINDOWS_MAX_PATH"
                ),
                "fired_on_bad_state": neg["alias_admits_over_limit_write"],
                "silent_on_good_state": neg["production_refused"],
                "result": "PASS",
            }
        ],
        "reviewer": {
            "reviewer_id": "TST-0202-probe2-readlink-f-and-bash",
            "verdict": "PASS",
            "independent": True,
            "second_shell": "/bin/bash",
            "pwsh7_present": bool(pwsh),
            "divergence": None,
            "notes": (
                "Catalog asks for pwsh7 and Git Bash. This Linux worktree has "
                "/bin/bash (Git Bash analog) and no pwsh; powershell was not "
                "substituted. bash readlink -f agreed with GNU readlink -f "
                "and with the writer's pathlib.Path.resolve length."
            ),
        },
        "defects": [],
        "artifacts": artifacts,
        "output_path": OUT_REL,
        "output_schema": (
            "command-center/schema/receipt.schema.json#/$defs/portability_report"
        ),
        "notes": (
            "G-1 TST-0202: production artifact writer measures resolved path "
            "length through a directory symlink (POSIX analog of a junction). "
            "The alias-length writer is the named defect and is shown to admit "
            "an over-limit write. cloud_ok is not delivery. SUCCESS:TST-0202"
        ),
    }


def write_receipt(doc: dict | None = None) -> dict:
    doc = doc or build_receipt()
    out = REPO / OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(doc, indent=2, sort_keys=True) + "\n"
    out.write_text(text, encoding="utf-8", newline="\n")
    return doc


def main() -> int:
    doc = write_receipt()
    sha, size = digest(REPO / OUT_REL)
    print(f"wrote {OUT_REL} bytes={size} sha256={sha}")
    print("SUCCESS:TST-0202 receipt")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
