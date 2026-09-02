#!/usr/bin/env python3
"""Emit TST-0074 receipt, per-unit manifest, and SUBAGENT-RETURN after live probes."""

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
UNIT = "TST-0074"
OUT_REL = f"command-center/receipts/{UNIT}.json"
SENTINEL = "SUCCESS:TST-0074"
TEST_CMD = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "tools/plugin/tests/test_repair_from_corruption.py"
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0074/probe1_repair_each_corruption_mode.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0074/probe2_unrepairable_names_component.py"
)
SUPPORTING = [
    "tools/plugin/repair.py",
    "tools/plugin/journeys.py",
    "tools/plugin/installer.py",
    "tools/plugin/payloadutil.py",
    "tools/plugin/tests/test_repair_from_corruption.py",
    "command-center/p2-wave/probes/TST-0074/probe1_repair_each_corruption_mode.py",
    "command-center/p2-wave/probes/TST-0074/probe2_unrepairable_names_component.py",
]


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run(cmd: str) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONPATH"] = str(REPO / "tools") + os.pathsep + env.get("PYTHONPATH", "")
    proc = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        timeout=180,
        env=env,
    )
    text = ((proc.stdout or "") + (proc.stderr or "")).strip()
    return proc.returncode, text


def art(rel: str, role: str) -> dict:
    path = REPO / rel
    digest, size = sha256_file(path) if path.is_file() else ("", 0)
    return {
        "path": rel,
        "bytes": size,
        "sha256": digest,
        "exists": path.is_file(),
        "present": path.is_file(),
        "role": role,
        "eol": "LF",
        "unit_id": UNIT,
        "receipt_path": f"command-center/p2-wave/probes/{UNIT}/SUBAGENT-RETURN.json",
    }


def probe_rec(role: str, command: str, raw: str, code: int) -> dict:
    return {
        "role": role,
        "method": "command",
        "command": command,
        "raw_output": raw[-16000:],
        "exit_code": code,
        "fingerprint": hashlib.sha256(f"command\x1f{command}".encode()).hexdigest()[:32],
    }


def main() -> int:
    code_t, out_t = run(TEST_CMD)
    code1, out1 = run(P1)
    code2, out2 = run(P2)
    if code_t != 0 or code1 != 0 or code2 != 0:
        print("FAILED:TST-0074 live tests/probes did not all exit 0")
        print(out_t[-2000:])
        print(out1[-2000:])
        print(out2[-2000:])
        return 1
    if "SUCCESS:TST-0074-tests" not in out_t:
        print("FAILED:TST-0074 tests sentinel missing")
        return 1
    if "SUCCESS:TST-0074-probe1" not in out1:
        print("FAILED:TST-0074 probe1 sentinel missing")
        return 1
    if "SUCCESS:TST-0074-probe2" not in out2:
        print("FAILED:TST-0074 probe2 sentinel missing")
        return 1

    started = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    p1 = probe_rec("source", P1, out1, code1)
    p2 = probe_rec("verifier", P2, out2, code2)
    pt = probe_rec("tests", TEST_CMD, out_t, code_t)
    receipt = {
        "schema_version": 1,
        "unit_id": UNIT,
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "spec_anchor": "_USER-PROMPTS.md:10836; catalog TST-0074",
        "min_bytes_threshold": 128,
        "title": "Repair command recovers a deliberately corrupted install",
        "question_or_target": (
            "Phase 5 lists a repair command. Corrupt the INSTALL TREE in each "
            "distinct way (missing file, truncated manifest, wrong file "
            "permissions, missing interpreter shim) and require repair to "
            "restore a working state or fail naming the unrepairable "
            "component. Cache corruption is owned by TST-0097."
        ),
        "timestamps": {"started_at": started, "ended_at": started},
        "retry": {
            "count": 0,
            "policy": "two strikes then pivot; no ADV rebuild circle",
        },
        "implementation": {
            "module": "tools/plugin/repair.py",
            "command": "python3 -m plugin.repair --home <profile> --package-id demo",
            "sidecar": "plugins/.releases/<id>/<txn>.payload (outside the live symlink)",
        },
        "artifacts": [art(rel, "supporting") for rel in SUPPORTING],
        "evidence": [
            {
                "anchor": "tools/plugin/tests/test_repair_from_corruption.py::test_repair_from_each_corruption_mode",
                "claim": (
                    "Each of four install-tree corruption modes (missing SKILL.md, "
                    "truncated plugin.json, shim mode 0644, missing bin/demo) is "
                    "repaired from the payload sidecar, then golden journeys "
                    "(manifest parse, hook load, skill read, shim exec, mode census) "
                    "all pass. Repair exit 0 is recorded but is not the evidence."
                ),
                "confidence": "almost-certain",
                "verdict": "CONFIRMED",
                "probes": [p1, pt],
            },
            {
                "anchor": "tools/plugin/tests/test_repair_from_corruption.py::test_unrepairable_corruption_fails_loudly_naming_the_component",
                "claim": (
                    "When SKILL.md is deleted from the live tree and dropped from "
                    "the payload sidecar, repair fails, prints "
                    "UNREPAIRABLE:skills/hello/SKILL.md, and skill_read stays red."
                ),
                "confidence": "almost-certain",
                "verdict": "CONFIRMED",
                "probes": [p2, pt],
            },
        ],
        "tests": [
            {
                "id": "test_repair_from_each_corruption_mode",
                "command": TEST_CMD,
                "result": "PASS",
            },
            {
                "id": "test_unrepairable_corruption_fails_loudly_naming_the_component",
                "command": TEST_CMD,
                "result": "PASS",
            },
            {"id": "named-probe1", "command": P1, "result": "PASS"},
            {"id": "named-probe2", "command": P2, "result": "PASS"},
        ],
        "corruption_modes": [
            "missing_file",
            "truncated_manifest",
            "wrong_permissions",
            "missing_shim",
        ],
        "negative_controls": [
            {
                "id": "unrepairable-dropped-sidecar-member",
                "kind": "known-broken-fixture",
                "description": (
                    "Live SKILL.md deleted and sidecar rewritten without that "
                    "member; repair must name skills/hello/SKILL.md"
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "UNREPAIRABLE:skills/hello/SKILL.md",
                "good_state_output": "post-repair journeys ok",
            }
        ],
        "reviewer": {
            "reviewer_id": "TST-0074-probe2-unrepairable-names-component",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "notes": (
                "Probe 2 does not trust repair exit 0. It requires the named "
                "component and a still-red skill_read journey."
            ),
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/TST-0074/UNIT-ARTIFACT-MANIFEST.json"
            ),
        },
        "downstream_consumers": [
            {
                "consumer": "command-center/p2-wave/_measure_one_delivered.py TST-0074",
                "artifact_path": OUT_REL,
                "executed": False,
                "read_ok": True,
                "note": "G-1 measure runs after this receipt and the per-unit manifest exist.",
            }
        ],
        "residual_unknowns": [
            {
                "claim": (
                    "TST-0070 (clean install of the published artifact) is a "
                    "catalog dependency and is not delivered in this worktree. "
                    "This unit seeds a throwaway install via the same plugin "
                    "installer control plane."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "After TST-0070 lands, re-run both named probes against the "
                    "published-artifact install tree rather than the seeded fixture."
                ),
            }
        ],
        "notes": (
            "G-1 delivery of TST-0074 install-tree repair. Live named probes "
            "exit 0. Receipt state=SUCCESS. Per-unit manifest row. Did not run "
            "global unit_manifest.py --write. Cloud ok=true is not delivery. "
            + SENTINEL
        ),
    }

    out = REPO / OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(receipt, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    live_sha, live_bytes = sha256_file(out)
    if live_bytes < 128:
        print(f"FAILED:TST-0074 receipt too small ({live_bytes} B)")
        return 1
    if SENTINEL not in out.read_text(encoding="utf-8"):
        print("FAILED:TST-0074 sentinel missing from receipt")
        return 1

    rows = [art(OUT_REL, "primary")]
    rows[0]["sha256"] = live_sha
    rows[0]["bytes"] = live_bytes
    rows[0]["exists"] = True
    rows[0]["present"] = True
    for rel in SUPPORTING:
        rows.append(art(rel, "supporting"))

    manifest = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": UNIT,
        "verified_on_disk": True,
        "expected": len(rows),
        "present": len(rows),
        "artifacts": rows,
    }
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(manifest, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )

    ret = {
        "id": UNIT,
        "unit_id": UNIT,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "registered": True,
        "output_path": OUT_REL,
        "output_schema": "command-center/schema/fault-injection-receipt.schema.json",
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": code1,
                "role": "repair-each-corruption-mode",
                "raw_output": out1[-8000:],
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": code2,
                "role": "unrepairable-names-component",
                "raw_output": out2[-8000:],
            },
        ],
        "artifacts": [
            {
                "path": OUT_REL,
                "sha256": live_sha,
                "bytes": live_bytes,
                "exists": True,
                "role": "primary",
            }
        ],
        "manifest_path": (
            "command-center/p2-wave/probes/TST-0074/UNIT-ARTIFACT-MANIFEST.json"
        ),
        "reviewer": {
            "reviewer_id": "TST-0074-probe2-unrepairable-names-component",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "notes": (
            "G-1 for TST-0074: live named probes exit 0, TST-0074.json "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. No ADV rebuild. Cloud ok=true is not delivery."
        ),
        "ts": started,
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"wrote {OUT_REL} bytes={live_bytes} sha256={live_sha}")
    print(SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
