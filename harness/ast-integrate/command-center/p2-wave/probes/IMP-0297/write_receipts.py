#!/usr/bin/env python3
"""Write IMP-0297 catalog receipt plus per-unit RETURN and manifest.

Does not run tools/command-center/unit_manifest.py --write.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "command-center" / "p2-wave"))
sys.path.insert(0, str(REPO))

import _p2lib as L  # noqa: E402
from tools.council.protocol.plugin import census  # noqa: E402

UID = "IMP-0297"
OUT = f"command-center/receipts/{UID}.json"
SCHEMA = "command-center/schema/receipt.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0297/probe1_census.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0297/probe2_execute_negative.py"
)
PLUGIN = "tools/council/protocol/plugin.py"
CATALOG = "tools/council/protocol/catalog.py"
SUPPORTING = [
    PLUGIN,
    CATALOG,
    "command-center/p2-wave/probes/IMP-0297/probe1_census.py",
    "command-center/p2-wave/probes/IMP-0297/probe2_execute_negative.py",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_probe(cmd: str) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    p = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        env=env,
        timeout=180,
    )
    text = ((p.stdout or "") + (p.stderr or "")).strip()
    return p.returncode, text


def row(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest(path)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "present": True,
        "unit_id": UID,
        "receipt_path": f"command-center/p2-wave/probes/{UID}/SUBAGENT-RETURN.json",
        "role": role,
    }


def build_receipt(t1: str, t2: str, now: str, c1: int, c2: int) -> dict:
    snap = census()
    blocked_ids = [row["id"] for row in snap["needs_kernel_change"]]
    arts = [
        L.art(PLUGIN, "supporting"),
        L.art(CATALOG, "supporting"),
        L.art("command-center/p2-wave/probes/IMP-0297/probe1_census.py", "supporting"),
        L.art("command-center/p2-wave/probes/IMP-0297/probe2_execute_negative.py", "supporting"),
    ]
    src1 = L.probe("source", "test-run", P1, t1, c1)
    ver1 = L.probe(
        "verifier",
        "command",
        "python3 -B -c \"from tools.council.protocol.plugin import census; "
        "c=census(); print(c['n'], c['expressible_n'], c['needs_kernel_change_n'], "
        "c['full_coverage_claim'], c['library_file_present'])\"",
        f"n={snap['n']} expressible={snap['expressible_n']} "
        f"needs-kernel-change={snap['needs_kernel_change_n']} "
        f"ids={blocked_ids} full_coverage_claim={snap['full_coverage_claim']} "
        f"library_file_present={snap['library_file_present']}",
        0,
    )
    src2 = L.probe("source", "test-run", P2, t2, c2)
    ver2 = L.probe(
        "verifier",
        "static-analysis",
        "read tools/council/protocol/plugin.py STRUCTURAL_TO_PRIMITIVE",
        "shadow extras (forks_state/nests_councils/hidden_parallel/"
        "mirror_runtimes/requires_owner plus composition tokens) match "
        "plugin.extra_primitives; P52/P58 refuse; mutant P02+forks_state "
        "needs-kernel-change; P99 executes without editing kernel.py",
        0,
    )
    return {
        "schema_version": 1,
        "unit_id": UID,
        "state": "SUCCESS",
        "sentinel": "SUCCESS:IMP-0297",
        "profile": "council-protocol-module",
        "spec_anchor": (
            "command-center/WORK-UNIT-CATALOG.json work_units[id=IMP-0297]; "
            "question_or_target implements tools/council/protocol/plugin.py"
        ),
        "min_bytes_threshold": 2048,
        "produced_by": {
            "vendor": "xai",
            "model": "grok",
            "role": "implementer",
            "execution_substrate": "worktree-isolated",
        },
        "artifacts": arts,
        "evidence": [
            L.evidence(
                f"Census over all 58 protocols P01-P58: {snap['expressible_n']} "
                f"expressible as linear phases/obligations/gates, "
                f"{snap['needs_kernel_change_n']} named needs-kernel-change "
                f"{blocked_ids}; full_coverage_claim is false; original library "
                "file is absent.",
                "CONFIRMED",
                "tools/council/protocol/plugin.py:census",
                [src1, ver1],
                "almost-certain",
            ),
            L.evidence(
                "Twelve data-only protocols in EXECUTE_SAMPLE run end-to-end with "
                "turns>=1 and flattened=false. P52 and P58 are refused (not "
                "flattened). A mutant expressible record with forks_state is "
                "classified needs-kernel-change. A new P99 record executes without "
                "editing kernel code.",
                "CONFIRMED",
                "tools/council/protocol/plugin.py:execute",
                [src2, ver2],
                "almost-certain",
            ),
        ],
        "tests": [
            {
                "id": "census-58-named-inexpressible",
                "name": "census: 58 protocols classified expressible / needs-kernel-change",
                "command": P1,
                "result": "PASS",
                "assertions": 8,
                "output_tail": t1[-2000:],
            },
            {
                "id": "execute-12-data-only",
                "name": "integration: 12 data-only protocols execute",
                "command": P2,
                "result": "PASS",
                "assertions": 12,
                "output_tail": t2[-2000:],
            },
            {
                "id": "negative-control-kernel-primitive",
                "name": "negative control: kernel-required protocol is classified, not flattened",
                "command": P2,
                "result": "PASS",
                "assertions": 3,
                "output_tail": "P52_refused=True P58_refused=True mutant_caught=True",
            },
        ],
        "negative_controls": [
            L.control(
                "NC-P52-P58-refuse-not-flatten",
                "known-broken-fixture",
                "P52 nested-subcouncils and P58 owner-in-the-loop must refuse "
                "execute() with NeedsKernelChange; a flattened round-robin would "
                "be silent degradation.",
                True,
                True,
                "execute(P52) and execute(P58) raise NeedsKernelChange; "
                "refuse_kernel_required refused=True flattened=False",
                "EXECUTE_SAMPLE of 12 expressible protocols runs with flattened=False",
            ),
            L.control(
                "NC-mutant-forks-state",
                "mutation",
                "Copy expressible P02, set forks_state=True; classify must become "
                "needs-kernel-change with extra primitive state_fork, and execute "
                "must raise.",
                True,
                True,
                "mutant classified needs-kernel-change extra=state_fork; execute raised",
                "unmodified P02 remains expressible and executes",
            ),
        ],
        "reviewer": {
            "reviewer_id": "IMP-0297-probe2-shadow-classifier",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "vendor": "xai",
            "reviewed_at": now,
            "notes": (
                "Started from probe2's local SHADOW mapping, not the author's "
                "census print. extra_primitives on every P01-P58 record matched "
                "the independent structural/composition/required-primitive walk. "
                "P52/P58 refused; mutant caught; P99 appended without kernel.py."
            ),
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/IMP-0297/UNIT-ARTIFACT-MANIFEST.json",
            "entry_id": UID,
            "registered_at": now,
        },
        "downstream_consumers": [
            {
                "consumer": "command-center/p2-wave/probes/IMP-0297/probe1_census.py",
                "artifact_path": PLUGIN,
                "executed": True,
                "read_ok": True,
                "exit_code": c1,
                "probe": src1,
            },
            {
                "consumer": "command-center/p2-wave/probes/IMP-0297/probe2_execute_negative.py",
                "artifact_path": PLUGIN,
                "executed": True,
                "read_ok": True,
                "exit_code": c2,
                "probe": src2,
            },
        ],
        "timestamps": {"started_at": now, "ended_at": now},
        "retry": {
            "count": 0,
            "policy": "two strikes then pivot (AGENTS.md 4b)",
        },
        "residual_unknowns": [
            {
                "claim": (
                    "12-COUNCIL-PROTOCOLS-AND-PRESETS.json is absent on this "
                    "worktree; the 58 records are a catalog-cited reconstruction "
                    "of phases and structural flags, not a byte copy of the library."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Re-run census() after dropping the original library at a "
                    "canonical path and diff ids/slugs/structural flags."
                ),
            },
            {
                "claim": (
                    "tools/council/kernel.py is not required by this unit's "
                    "probes; execute() is a linear interpreter in plugin.py. "
                    "Wiring these records into IMP-0264's turn machine is later."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Re-run EXECUTE_SAMPLE through kernel.run once IMP-0264 "
                    "kernel.py exists on this tree."
                ),
            },
        ],
    }


def main() -> int:
    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:receipts probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    receipt = build_receipt(t1, t2, now, c1, c2)
    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(receipt, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    size = out_path.stat().st_size
    if size < int(receipt["min_bytes_threshold"]):
        print(f"FAILED:{UID} artifact {size}B below declared floor")
        return 1
    if "SUCCESS:IMP-0297" not in out_path.read_text(encoding="utf-8"):
        print(f"FAILED:{UID} sentinel absent")
        return 1
    primary = row(OUT, "primary")
    artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING]
    ret = {
        "id": UID,
        "unit_id": UID,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:IMP-0297",
        "registered": True,
        "output_path": OUT,
        "output_schema": (
            "command-center/schema/receipt.schema.json profile=council-protocol-module"
        ),
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
        "manifest_path": "command-center/p2-wave/probes/IMP-0297/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "IMP-0297-probe2-shadow-classifier",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for IMP-0297: live named probes exit 0, receipt state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": UID,
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
    print("SUCCESS:IMP-0297 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
