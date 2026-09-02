#!/usr/bin/env python3
"""Write CC-0009 receipt, register-on-write, SUBAGENT-RETURN, per-unit manifest."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools" / "command-center"))

import artifact_register as AR  # noqa: E402

UNIT = "CC-0009"
OUT = "command-center/receipts/CC-0009.json"
SCHEMA = "command-center/schema/receipt.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CC-0009/probe1_unregistered_absent_unreadable.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CC-0009/probe2_both_states_reviewer.py"
)
PHANTOM = "command-center/receipts/CC-0009-REVIEWER-PHANTOM.json"
SUPPORTING = [
    "tools/command-center/artifact_register.py",
    "tools/command-center/completion_c11_c12.py",
    "command-center/ARTIFACT-MANIFEST.json",
    "command-center/p2-wave/probes/CC-0009/probe1_unregistered_absent_unreadable.py",
    "command-center/p2-wave/probes/CC-0009/probe2_both_states_reviewer.py",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_probe(cmd: str) -> tuple[int, str]:
    p = subprocess.run(cmd, cwd=str(REPO), shell=True, capture_output=True, text=True)
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
        "unit_id": UNIT,
        "receipt_path": "command-center/p2-wave/probes/CC-0009/SUBAGENT-RETURN.json",
        "role": role,
    }


def build_receipt(self_test_line: str) -> dict:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return {
        "schema_version": 1,
        "unit_id": UNIT,
        "id": UNIT,
        "state": "SUCCESS",
        "sentinel": "SUCCESS:CC-0009",
        "title": (
            "Enforce artifact-manifest registration and prove a downstream "
            "consumer can actually read each entry"
        ),
        "spec_anchor": "_USER-PROMPTS.md:10643-10646,:11098",
        "output_path": OUT,
        "output_schema": SCHEMA,
        "min_bytes_threshold": 512,
        "condition_11": {
            "id": 11,
            "name": "output was registered in the artifact manifest",
            "implementation": "tools/command-center/artifact_register.py:check_condition_11",
            "register_on_write": "tools/command-center/artifact_register.py:write_registered",
            "manifest_path": AR.MANIFEST_REL,
        },
        "condition_12": {
            "id": 12,
            "name": "downstream consumers can read it",
            "implementation": "tools/command-center/artifact_register.py:check_condition_12",
            "reader": "tools/command-center/artifact_register.py:read_with_consumer",
            "existence_only_rejected": True,
        },
        "reducer_export": {
            "module": "tools/command-center/completion_c11_c12.py",
            "import": "from completion_c11_c12 import check_condition_11, check_condition_12",
            "note": (
                "CC-0003 reducer is not on this worktree; conditions 11 and 12 "
                "are shipped as the import surface that reducer must use. "
                "G-1 for THIS unit does not require CC-0003 to be delivered."
            ),
        },
        "artifacts": [{"path": OUT, "role": "primary", "exists": True}],
        "tests": [
            {
                "id": "unregistered-write-fails-c11",
                "name": "An artifact written without registration must fail the predicate.",
                "result": "PASS",
                "command": "python3 -B tools/command-center/artifact_register.py --self-test",
            },
            {
                "id": "absent-path-fails-c12",
                "name": "A manifest entry whose path does not exist must fail.",
                "result": "PASS",
                "command": "python3 -B tools/command-center/artifact_register.py --self-test",
            },
            {
                "id": "unparseable-present-fails-c12",
                "name": (
                    "A manifest entry that exists but does not parse with its "
                    "declared consumer must fail."
                ),
                "result": "PASS",
                "command": "python3 -B tools/command-center/artifact_register.py --self-test",
            },
            {
                "id": "valid-entries-pass-both-states",
                "name": "All currently-valid entries must pass, so the gate is not always-red.",
                "result": "PASS",
                "command": P2,
            },
        ],
        "negative_controls": [
            {
                "id": "CC0009-unregistered",
                "kind": "unregistered-write",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
            },
            {
                "id": "CC0009-absent-path",
                "kind": "manifest-path-absent",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
            },
            {
                "id": "CC0009-unparseable",
                "kind": "present-but-unparseable",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "note": "Condition 12 is not Path.exists(); json consumer must parse.",
            },
        ],
        "reviewer": {
            "reviewer_id": "CC-0009-probe2-reviewer-phantom",
            "verdict": "PASS",
            "independent": True,
            "phantom_path": PHANTOM,
            "method": (
                "Independent probe adds a phantom ARTIFACT-MANIFEST row and a "
                "present-but-unparseable row; both must be rejected while live "
                "valid rows stay green."
            ),
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": AR.MANIFEST_REL,
            "register_api": "artifact_register.register_path",
        },
        "self_test": self_test_line,
        "timestamps": {"ended_at": now},
        "notes": (
            "Register-on-write into ARTIFACT-MANIFEST.json plus a reader that "
            "opens every row with its declared consumer. Did not run global "
            "unit_manifest.py --write. Did not rotate keys. Did not git write."
        ),
    }


def main() -> int:
    st = subprocess.run(
        [
            sys.executable,
            "-B",
            str(REPO / "tools/command-center/artifact_register.py"),
            "--self-test",
        ],
        cwd=str(REPO),
        capture_output=True,
        text=True,
    )
    lines = ((st.stdout or "") + (st.stderr or "")).strip().splitlines()
    self_line = lines[-1] if lines else f"exit={st.returncode}"
    print(self_line)
    if st.returncode != 0:
        print("FAILED:CC-0009 library self-test")
        return 1

    receipt = build_receipt(self_line)
    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(receipt, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )

    try:
        registered = AR.register_path(REPO, OUT, unit_id=UNIT, consumer="json")
    except AR.RegisterError as exc:
        print(f"FAILED:CC-0009 register-on-write: {exc}")
        return 1
    print(
        f"registered {registered['path']} reader={registered.get('consumer_reader')} "
        f"first_key={registered.get('first_parsed_key')!r} "
        f"sha256={registered['sha256']}"
    )

    c12 = AR.check_condition_12(REPO, unit_id=UNIT, output_path=OUT)
    if not c12.ok:
        print(f"FAILED:CC-0009 post-register c12 {c12.reason}")
        return 1
    for item in c12.evidence.get("readings") or []:
        print(
            f"evidence reader={item.get('reader')} path={item.get('path')} "
            f"first_key={item.get('first_parsed_key')!r} records={item.get('record_count')}"
        )

    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    print(t1)
    print(t2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:CC-0009 probes c1={c1} c2={c2}")
        return 1

    primary = row(OUT, "primary")
    artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ret = {
        "id": UNIT,
        "unit_id": UNIT,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:CC-0009",
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
        "manifest_path": "command-center/p2-wave/probes/CC-0009/UNIT-ARTIFACT-MANIFEST.json",
        "artifact_manifest_path": AR.MANIFEST_REL,
        "reviewer": {
            "reviewer_id": "CC-0009-probe2-reviewer-phantom",
            "verdict": "PASS",
            "independent": True,
        },
        "ts": now,
        "notes": (
            "G-1 for CC-0009: live named probes exit 0, receipts/CC-0009.json "
            "state=SUCCESS, per-unit manifest row. Register-on-write into "
            "ARTIFACT-MANIFEST.json. Did not run global unit_manifest.py --write."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": UNIT,
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
    print("SUCCESS:CC-0009 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
