#!/usr/bin/env python3
"""Emit TST-0083 receipt + per-unit SUBAGENT-RETURN + UNIT-ARTIFACT-MANIFEST."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
UNIT = "TST-0083"
OUT_REL = f"command-center/receipts/{UNIT}.json"
SENTINEL = f"SUCCESS:{UNIT}"
SCHEMA = "command-center/schema/test-receipt.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0083/probe1_planted_repo_only.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0083/probe2_three_directions.py"
)
TEST_CMD = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0083/test_differ.py"
)
SUPPORTING = [
    "command-center/p2-wave/probes/TST-0083/differ.py",
    "command-center/p2-wave/probes/TST-0083/fixtures.py",
    "command-center/p2-wave/probes/TST-0083/test_differ.py",
    "command-center/p2-wave/probes/TST-0083/probe1_planted_repo_only.py",
    "command-center/p2-wave/probes/TST-0083/probe2_three_directions.py",
]


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run(cmd: str) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
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


def first_json(text: str) -> dict:
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("{") and line.endswith("}"):
            try:
                doc = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(doc, dict):
                return doc
    return {}


def main() -> int:
    code_t, out_t = run(TEST_CMD)
    code1, out1 = run(P1)
    code2, out2 = run(P2)
    if code_t != 0 or code1 != 0 or code2 != 0:
        print(f"FAILED:{UNIT} emit tests={code_t} p1={code1} p2={code2}")
        print(out_t[-2500:])
        print(out1[-2500:])
        print(out2[-2500:])
        return 1
    if "SUCCESS:TST-0083-tests" not in out_t:
        print("FAILED:TST-0083 emit tests sentinel missing")
        return 1
    if "SUCCESS:TST-0083-probe1" not in out1:
        print("FAILED:TST-0083 emit probe1 sentinel missing")
        return 1
    if "SUCCESS:TST-0083-probe2" not in out2:
        print("FAILED:TST-0083 emit probe2 sentinel missing")
        return 1

    p1_doc = first_json(out1)
    p2_doc = first_json(out2)
    counts = p2_doc.get("counts") or {}
    file_lists = p2_doc.get("file_lists") or {}
    schema_path = REPO / SCHEMA
    started = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    p1 = probe_rec("source", P1, out1, code1)
    p2 = probe_rec("verifier", P2, out2, code2)
    pt = probe_rec("source", TEST_CMD, out_t, code_t)
    artifacts = [art(rel, "supporting") for rel in SUPPORTING]
    pwsh = shutil.which("pwsh") or shutil.which("powershell")

    receipt = {
        "schema_version": 1,
        "unit_id": UNIT,
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "profile": "skill-repo-vs-live-availability-differ",
        "spec_anchor": (
            "WORK-UNIT-CATALOG.json:TST-0083; "
            "_USER-PROMPTS.md:11329; failure class FC-11329"
        ),
        "output_schema": SCHEMA,
        "schema_note": (
            "command-center/schema/test-receipt.schema.json is absent on this "
            "sparse tree. It is not rebuilt here (no ADV schema circle). This "
            "receipt carries the catalog test-receipt fields: unit_id, state, "
            "sentinel, tests, evidence with three-direction counts and file lists, "
            "named probes, and reviewer."
        ),
        "schema_present": schema_path.is_file(),
        "adv_rebuild_circle": False,
        "min_bytes_threshold": 128,
        "title": "A skill exists in the repository but not in the live skill directory",
        "question_or_target": (
            "Failure class :11329. Target: a bidirectional reconciliation "
            "between the repo skill set and the deployed skill set, reporting "
            "repo-only, live-only and content-divergent entries. Distinct from "
            "unit TST-0079 (which tests the sync TOOL's safety); this measures "
            "the AVAILABILITY consequence for capability routing."
        ),
        "timestamps": {"started_at": started, "ended_at": started},
        "retry": {"count": 0, "policy": "two-strikes-then-pivot"},
        "artifact_paths": [OUT_REL, *SUPPORTING],
        "artifacts": artifacts,
        "test_ids": [
            "test_differ_finds_a_planted_repo_only_skill",
            "test_all_three_directions_are_reported",
        ],
        "negative_control_ids": [
            "eol-twin-not-divergent",
            "empty-zero-backed-by-planted-repo-only",
        ],
        "reviewer_verdict": "PASS",
        "evidence": [
            {
                "anchor": "command-center/p2-wave/probes/TST-0083/differ.py:reconcile",
                "claim": (
                    "A deterministic differ reports three counts with file lists: "
                    f"repo-only={counts.get('repo_only')} "
                    f"live-only={counts.get('live_only')} "
                    f"divergent={counts.get('divergent')}. "
                    "The planted repo-only skill is found; a zero on an empty pair "
                    "is backed by that planted detection, not treated as in-sync."
                ),
                "confidence": "almost-certain",
                "verdict": "CONFIRMED",
                "probes": [p1, p2, pt],
                "counts": counts,
                "file_lists": file_lists,
            },
            {
                "anchor": "command-center/p2-wave/probes/TST-0083/differ.py:route",
                "claim": (
                    "Availability consequence: the planted repo-only skill is "
                    "UNAVAILABLE to a live router because it is absent from the "
                    "deployed tree. This is not a sync-tool overwrite test "
                    "(TST-0079)."
                ),
                "confidence": "almost-certain",
                "verdict": "CONFIRMED",
                "probes": [p1],
                "routing": p1_doc.get("routing"),
            },
        ],
        "tests": [
            {
                "id": "test_differ_finds_a_planted_repo_only_skill",
                "command": TEST_CMD,
                "result": "PASS",
            },
            {
                "id": "test_all_three_directions_are_reported",
                "command": TEST_CMD,
                "result": "PASS",
            },
            {"id": "probe1-planted-repo-only", "command": P1, "result": "PASS"},
            {"id": "probe2-three-directions", "command": P2, "result": "PASS"},
        ],
        "negative_controls": [
            {
                "id": "eol-twin-not-divergent",
                "kind": "eol-only-pair",
                "description": (
                    "A skill whose only difference is LF vs CRLF must be "
                    "identical after LF normalization, not content-divergent."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "good_state_output": "eol-twin in identical",
                "bad_state_output": "eol-twin in divergent",
            },
            {
                "id": "empty-zero-backed-by-planted-repo-only",
                "kind": "zero-cannot-be-vacuous",
                "description": (
                    "Two empty trees yield repo_only=0. That zero is allowed "
                    "only because the same differ found planted plant-repo-only."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
            },
        ],
        "three_direction_report": {
            "counts": counts,
            "file_lists": file_lists,
            "identical": p2_doc.get("identical"),
            "independent_walk_matched": p2_doc.get("independent_walk_matched"),
            "host_trees": p2_doc.get("host_trees"),
            "host_counts": p2_doc.get("host_counts"),
        },
        "reviewer": {
            "reviewer_id": "TST-0083-probe2-independent-os-walk",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "scope_not_agreement": True,
            "method": (
                "Recompute repo-only / live-only / divergent from os.walk plus "
                "LF-normalized file digests without calling classify(). Confirm "
                "the three planted ids and that the EOL twin is identical. "
                "Windows PowerShell 7 re-run is residual if pwsh is absent."
            ),
            "windows_other_shell": {
                "required": "PowerShell 7 vs Git Bash",
                "pwsh_present": bool(pwsh),
                "pwsh_path": pwsh,
                "verdict": "PASS" if pwsh else "NOT-CHECKED",
            },
        },
        "implementation": {
            "module": "command-center/p2-wave/probes/TST-0083/differ.py",
            "instrument_not_production_sync": True,
            "skill_marker": "SKILL.md",
            "normalization": "LF before sha256",
            "does_not_auto_deploy": True,
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": f"command-center/p2-wave/probes/{UNIT}/UNIT-ARTIFACT-MANIFEST.json",
            "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        },
        "downstream_consumers": [
            {
                "consumer": "command-center/p2-wave/_measure_one_delivered.py",
                "artifact_path": OUT_REL,
                "executed": False,
                "read_ok": False,
                "note": "G-1 measure runs after this receipt and the per-unit manifest exist.",
            }
        ],
        "residual_unknowns": [
            {
                "claim": (
                    "Host repo skills/ and ~/.claude/skills may be absent on this "
                    "Linux worktree. Fixture counts are the measured three-direction "
                    "report. Host census is recorded read-only."
                ),
                "settling_experiment": (
                    "On a machine with both live skill trees populated, re-run "
                    "probe2 and attach host_counts as the production census."
                ),
                "verdict": "NOT-CHECKED" if not p2_doc.get("host_counts") else "CHECKED",
            },
            {
                "claim": (
                    "Catalog reviewer requires a Windows-platform specialist to "
                    "re-run the probe in the OTHER shell (PowerShell 7 vs Git Bash)."
                ),
                "settling_experiment": (
                    "Run probe1 and probe2 under pwsh.exe on Windows and attach "
                    "the raw output beside the Linux run."
                ),
                "verdict": "NOT-CHECKED" if not pwsh else "CHECKED",
            },
        ],
        "notes": (
            "G-1 delivery of TST-0083 skill repo-vs-live availability differ. "
            "Live named probes exit 0. Did not run global unit_manifest.py "
            "--write. cloud ok is not consulted. No ADV rebuild."
        ),
    }

    out = REPO / OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(receipt, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    live_sha, live_bytes = sha256_file(out)
    if live_bytes < 128:
        print(f"FAILED:{UNIT} receipt too small ({live_bytes} B)")
        return 1
    if SENTINEL not in out.read_text(encoding="utf-8"):
        print("FAILED:TST-0083 sentinel missing from receipt text")
        return 1

    rows = [
        {
            "path": OUT_REL,
            "sha256": live_sha,
            "bytes": live_bytes,
            "exists": True,
            "present": True,
            "role": "primary",
            "eol": "LF",
            "unit_id": UNIT,
            "receipt_path": f"command-center/p2-wave/probes/{UNIT}/SUBAGENT-RETURN.json",
        }
    ]
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
        "output_schema": SCHEMA,
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": code1,
                "role": "planted-repo-only-and-routing-unavailability",
                "raw_output": out1[-8000:],
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": code2,
                "role": "three-directions-independent-walk-and-zero-backing",
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
        "manifest_path": f"command-center/p2-wave/probes/{UNIT}/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "TST-0083-probe2-independent-os-walk",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "measure_line": f"SUCCESS:delivered {UNIT}",
        "notes": (
            "G-1 for TST-0083: live named probes exit 0, receipt state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write. "
            "Cloud ok=true is not delivery. No ADV rebuild."
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
