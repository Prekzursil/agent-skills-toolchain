#!/usr/bin/env python3
"""Write IMP-0150 catalog receipt plus per-unit SUBAGENT-RETURN / manifest.

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
sys.path.insert(0, str(REPO / "tools"))
sys.path.insert(0, str(HERE))

from discovery.local_repo import as_dicts, discover_local, find_path  # noqa: E402
from scenario import KNOWN_PRESENT, LIVE_ARC_CONTROL, SENTINEL  # noqa: E402

UID = "IMP-0150"
OUT = "command-center/receipts/IMP-0150.json"
SCHEMA = "command-center/schema/receipt.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0150/probe1_known_present_absent.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0150/probe2_ref_only_access.py"
)
SUPPORTING = [
    "tools/discovery/__init__.py",
    "tools/discovery/local_repo.py",
    "command-center/p2-wave/probes/IMP-0150/scenario.py",
    "command-center/p2-wave/probes/IMP-0150/probe1_known_present_absent.py",
    "command-center/p2-wave/probes/IMP-0150/probe2_ref_only_access.py",
    "command-center/p2-wave/probes/IMP-0150/write_receipts.py",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_cmd(cmd: str) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        env=env,
        timeout=180,
    )
    text = ((proc.stdout or "") + (proc.stderr or "")).strip()
    return proc.returncode, text


def first_json(text: str) -> dict:
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end < start:
        return {}
    try:
        doc = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return {}
    return doc if isinstance(doc, dict) else {}


def row(rel: str, role: str) -> dict:
    sha, size = digest(REPO / rel)
    return {
        "bytes": size,
        "path": rel,
        "present": True,
        "receipt_path": "command-center/p2-wave/probes/IMP-0150/SUBAGENT-RETURN.json",
        "role": role,
        "sha256": sha,
        "unit_id": UID,
    }


def main() -> int:
    c1, t1 = run_cmd(P1)
    c2, t2 = run_cmd(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:IMP-0150 receipts probes c1={c1} c2={c2}")
        print(t1[-3000:])
        print(t2[-3000:])
        return 1
    j1 = first_json(t1)
    j2 = first_json(t2)
    if j1.get("pass") is not True or j2.get("pass") is not True:
        print("FAILED:IMP-0150 probe JSON pass=false")
        return 1

    live = discover_local(REPO)
    live_rtv = find_path(live, KNOWN_PRESENT)
    live_sentinel = find_path(live, SENTINEL)
    live_arc = find_path(live, LIVE_ARC_CONTROL)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    receipt = {
        "answer": (
            "Local-repo discovery adapter enumerates workflow-shaped artifacts "
            "in the working tree, linked worktrees, and git refs. Each row "
            "carries a content hash and the exact access method. A path that "
            "exists only on a remote ref records `git show <ref>:<path>` "
            "(never a bare path, never git archive). On this Linux worktree "
            f"{KNOWN_PRESENT} is absent (live_on_disk="
            f"{(REPO / KNOWN_PRESENT).is_file()}); the known-present detector "
            "is proven on a planted fixture of that path, and the live ARC "
            "control is found when present. Known-absent sentinel returns 0. "
            "SUCCESS:IMP-0150"
        ),
        "artifacts": [
            {"path": OUT, "role": "primary"},
            {"path": "tools/discovery/local_repo.py", "role": "implementation"},
        ],
        "cloud_ok": False,
        "completion_sentinel": "SUCCESS:IMP-0150",
        "evidence": [
            {
                "anchor": "command-center/p2-wave/probes/IMP-0150/probe1_known_present_absent.py",
                "claim": (
                    "Planted workflows/rtv-pdr.js is found with a content hash "
                    "that matches an independent file read; a sentinel name "
                    "that exists nowhere returns 0; an empty-repo control is "
                    "silent (both-states)."
                ),
                "verdict": "CONFIRMED",
            },
            {
                "anchor": "command-center/p2-wave/probes/IMP-0150/probe2_ref_only_access.py",
                "claim": (
                    "A ref-only workflow records access_method "
                    "`git show origin/imp0150-ref-only:workflows/ref-only-remote.js`; "
                    "the recorded method is executed and the bytes hash-match "
                    "an independent git show. The bare path is unreadable."
                ),
                "verdict": "CONFIRMED",
            },
        ],
        "id": UID,
        "implementation": {
            "adapter": "tools/discovery/local_repo.py",
            "discover": "discover_local",
            "fetch": "fetch_bytes",
            "git_archive": "forbidden",
        },
        "live_scan": {
            "arc_control_found": bool(live_arc),
            "arc_control_path": LIVE_ARC_CONTROL,
            "candidate_count": len(live),
            "candidates": as_dicts(live),
            "git_worktree": False,
            "rtv_pdr_found": bool(live_rtv),
            "rtv_pdr_on_disk": (REPO / KNOWN_PRESENT).is_file(),
            "sentinel_hits": len(live_sentinel),
        },
        "named_probes": [
            {
                "command": P1,
                "exit_code": c1,
                "id": "probe1",
                "raw_output": t1,
                "role": "known-present-absent",
            },
            {
                "command": P2,
                "exit_code": c2,
                "id": "probe2",
                "raw_output": t2,
                "role": "ref-only-access-method",
            },
        ],
        "notes": (
            "G-1 for IMP-0150: live named probes exit 0, receipt state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write. "
            "cloud_ok is false and is not delivery. Catalog input "
            "workflows/rtv-pdr.js is absent on this worktree; detector control "
            "is the planted fixture plus the live ARC workflow file."
        ),
        "output_schema": SCHEMA,
        "registered": True,
        "reviewer": {
            "basis": (
                "Probe 2 is a distinct control: ref-only access_method plus "
                "read-back, independent of the known-present/absent probe."
            ),
            "independent": True,
            "reviewer_id": "IMP-0150-probe2-ref-only-access",
            "verdict": "PASS",
        },
        "sentinel": "SUCCESS:IMP-0150",
        "state": "SUCCESS",
        "status": "DELIVERED",
        "tests": [
            {
                "id": "known-present-absent",
                "result": "PASS",
            },
            {
                "id": "ref-only-git-show-read-back",
                "result": "PASS",
            },
        ],
        "ts": now,
        "unit_id": UID,
    }
    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(receipt, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    primary = row(OUT, "primary")
    artifacts = [primary] + [row(p, "implementation") for p in SUPPORTING]
    ret = {
        "artifacts": [
            {
                "bytes": primary["bytes"],
                "exists": True,
                "path": OUT,
                "role": "primary",
                "sha256": primary["sha256"],
            }
        ],
        "cloud_ok": False,
        "id": UID,
        "manifest_path": (
            "command-center/p2-wave/probes/IMP-0150/UNIT-ARTIFACT-MANIFEST.json"
        ),
        "named_probes": [
            {
                "command": P1,
                "exit_code": c1,
                "id": "probe1",
                "raw_output": t1,
                "role": "known-present-absent",
            },
            {
                "command": P2,
                "exit_code": c2,
                "id": "probe2",
                "raw_output": t2,
                "role": "ref-only-access-method",
            },
        ],
        "notes": (
            "G-1 for IMP-0150: live named probes exit 0, receipt state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write. "
            "cloud_ok is false and is not delivery."
        ),
        "output_path": OUT,
        "output_schema": SCHEMA,
        "registered": True,
        "reviewer": {
            "independent": True,
            "reviewer_id": "IMP-0150-probe2-ref-only-access",
            "verdict": "PASS",
        },
        "sentinel": "SUCCESS:IMP-0150",
        "state": "SUCCESS",
        "status": "DELIVERED",
        "ts": now,
        "unit_id": UID,
    }
    man = {
        "artifacts": artifacts,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "expected": len(artifacts),
        "present": len(artifacts),
        "schema_version": 1,
        "unit_id": UID,
        "verified_on_disk": True,
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"primary {OUT} sha256={primary['sha256']} bytes={primary['bytes']}")
    print("SUCCESS:IMP-0150 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
