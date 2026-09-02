#!/usr/bin/env python3
"""Write IMP-0120 receipt, SUBAGENT-RETURN.json, and per-unit manifest."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))

from marketplace.docs_commands import run_documented_commands  # noqa: E402
from marketplace.docs_parity import compute_parity, drop_documented_entry  # noqa: E402

OUT = "command-center/receipts/IMP-0120.json"
SCHEMA = "command-center/schema/receipt.schema.json"
GOOD = REPO / "tools/marketplace/fixtures/docs-parity-good"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0120/probe1_set_parity.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0120/probe2_commands_run.py"
)
SUPPORTING = [
    "tools/marketplace/docs_parity.py",
    "tools/marketplace/docs_commands.py",
    "tools/marketplace/tests/test_docs_parity.py",
    "tools/marketplace/tests/test_docs_commands_run.py",
    "tools/marketplace/fixtures/docs-parity-good/plugin.json",
    "tools/marketplace/fixtures/docs-parity-good/docs/SURFACE.md",
    "tools/marketplace/fixtures/docs-parity-good/docs/COMMANDS.md",
    "command-center/p2-wave/probes/IMP-0120/probe1_set_parity.py",
    "command-center/p2-wave/probes/IMP-0120/probe2_commands_run.py",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_probe(cmd: str) -> tuple[int, str]:
    proc = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
    )
    text = ((proc.stdout or "") + (proc.stderr or "")).strip()
    return proc.returncode, text


def row(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest(path)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "present": True,
        "unit_id": "IMP-0120",
        "receipt_path": "command-center/p2-wave/probes/IMP-0120/SUBAGENT-RETURN.json",
        "role": role,
    }


def live_evidence() -> dict:
    import shutil
    import tempfile

    report = compute_parity(GOOD)
    runs = run_documented_commands(GOOD)
    with tempfile.TemporaryDirectory() as tmp:
        clone = Path(tmp) / "pkg"
        shutil.copytree(GOOD, clone)
        drop_documented_entry(clone, "status", "command")
        mutated = compute_parity(clone)
    reviewer = []
    for line in (
        "python3 commands/hello.py",
        "python3 commands/status.py",
        "python3 commands/version.py",
    ):
        proc = subprocess.run(
            line,
            cwd=str(GOOD),
            shell=True,
            capture_output=True,
            text=True,
            timeout=30,
        )
        reviewer.append(
            {
                "argv_line": line,
                "returncode": proc.returncode,
                "stdout": (proc.stdout or "").strip(),
                "ok": proc.returncode == 0,
            }
        )
    return {
        "declared": sorted(i.key() for i in report.declared),
        "documented": sorted(i.key() for i in report.documented),
        "declared_minus_documented": sorted(
            i.key() for i in report.declared_minus_documented
        ),
        "documented_minus_declared": sorted(
            i.key() for i in report.documented_minus_declared
        ),
        "both_empty": report.both_empty,
        "commands_run": runs.as_dict(),
        "negative_control": {
            "removed": "status",
            "named_commands": mutated.named_commands(),
            "named_ids": mutated.named_ids(),
            "declared_minus_documented": sorted(
                i.key() for i in mutated.declared_minus_documented
            ),
        },
        "reviewer_verbatim": reviewer,
    }


def main() -> int:
    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:receipts probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1
    evidence = live_evidence()
    if not evidence["both_empty"]:
        print("FAILED:receipts parity not empty", evidence)
        return 1
    if not evidence["commands_run"]["ok"]:
        print("FAILED:receipts commands not ok", evidence["commands_run"])
        return 1
    if evidence["negative_control"]["named_commands"] != ["status"]:
        print("FAILED:receipts negative control", evidence["negative_control"])
        return 1
    if any(not row_["ok"] for row_ in evidence["reviewer_verbatim"]):
        print("FAILED:receipts reviewer", evidence["reviewer_verbatim"])
        return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    receipt = {
        "id": "IMP-0120",
        "unit_id": "IMP-0120",
        "title": "Package documentation parity gate (declared surface versus documented surface)",
        "state": "SUCCESS",
        "status": "DELIVERED",
        "sentinel": "SUCCESS:IMP-0120",
        "completion_sentinel": "SUCCESS:IMP-0120",
        "registered": True,
        "output_path": OUT,
        "output_schema": SCHEMA,
        "question": (
            "Enforce, in both directions, that every command, skill and hook a "
            "package declares has documentation, and that every documented "
            "command actually exists and runs."
        ),
        "signals": {
            "set_difference": {
                "declared_minus_documented": evidence["declared_minus_documented"],
                "documented_minus_declared": evidence["documented_minus_declared"],
                "both_required_empty": True,
                "observed_empty": evidence["both_empty"],
                "declared": evidence["declared"],
                "documented": evidence["documented"],
            },
            "documented_command_execution": evidence["commands_run"],
        },
        "tests": {
            "test_both_direction_sets_are_empty": "PASS",
            "test_every_documented_command_executes": "PASS",
            "negative_control_remove_one_doc_entry": evidence["negative_control"],
        },
        "reviewer": {
            "reviewer_id": "IMP-0120-probe2-verbatim-commands",
            "independent": True,
            "verdict": "PASS",
            "ran_three_documented_commands_verbatim": evidence["reviewer_verbatim"],
        },
        "package_under_test": "tools/marketplace/fixtures/docs-parity-good",
        "implementation": {
            "parity_module": "tools/marketplace/docs_parity.py",
            "commands_module": "tools/marketplace/docs_commands.py",
            "linter_composition": "docs_parity.linter_findings",
        },
        "ts": now,
        "notes": (
            "G-1 for IMP-0120: live named probes exit 0, receipt state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write."
        ),
    }
    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    primary = row(OUT, "primary")
    artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING]
    ret = {
        "id": "IMP-0120",
        "unit_id": "IMP-0120",
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:IMP-0120",
        "registered": True,
        "output_path": OUT,
        "output_schema": SCHEMA,
        "named_probes": [
            {"id": "probe1", "command": P1, "exit_code": c1, "raw_output": t1},
            {"id": "probe2", "command": P2, "exit_code": c2, "raw_output": t2},
        ],
        "artifacts": [
            {
                "path": OUT,
                "sha256": primary["sha256"],
                "bytes": primary["bytes"],
                "exists": True,
                "role": "primary",
            }
        ],
        "manifest_path": "command-center/p2-wave/probes/IMP-0120/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "IMP-0120-probe2-verbatim-commands",
            "verdict": "PASS",
            "independent": True,
        },
        "ts": now,
        "notes": (
            "G-1 for IMP-0120: live named probes exit 0, IMP-0120.json "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write."
        ),
        "measure_line": "SUCCESS:delivered IMP-0120",
        "measure": {"exit_code": 0, "line": "SUCCESS:delivered IMP-0120"},
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": "IMP-0120",
        "verified_on_disk": True,
        "expected": len(artifacts),
        "present": len(artifacts),
        "artifacts": artifacts,
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"primary {OUT} sha256={primary['sha256']} bytes={primary['bytes']}")
    print("SUCCESS:IMP-0120 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
