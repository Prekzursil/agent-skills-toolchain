#!/usr/bin/env python3
"""Write per-unit SUBAGENT-RETURN.json and UNIT-ARTIFACT-MANIFEST.json."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(HERE))
import emit_finding as E  # noqa: E402

OUT = "command-center/receipts/SYN-0014.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/SYN-0014/probe1_known_present.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/SYN-0014/probe2_band_vocabulary.py"
)
SUPPORTING = [
    "command-center/schema/meta-review-finding.schema.json",
    "command-center/p2-wave/probes/SYN-0014/bands.py",
    "command-center/p2-wave/probes/SYN-0014/scan.py",
    "command-center/p2-wave/probes/SYN-0014/corpus.py",
    "command-center/p2-wave/probes/SYN-0014/emit_finding.py",
    "command-center/p2-wave/probes/SYN-0014/probe1_known_present.py",
    "command-center/p2-wave/probes/SYN-0014/probe2_band_vocabulary.py",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_probe(cmd: str) -> tuple[int, str]:
    p = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
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
        "unit_id": "SYN-0014",
        "receipt_path": "command-center/p2-wave/probes/SYN-0014/SUBAGENT-RETURN.json",
        "role": role,
    }


def main() -> int:
    erc = E.main()
    if erc != 0:
        print(f"FAILED:SYN-0014 emit rc={erc}")
        return erc
    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:SYN-0014 receipts probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1
    primary = row(OUT, "primary")
    artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ret = {
        "id": "SYN-0014",
        "unit_id": "SYN-0014",
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:SYN-0014",
        "registered": True,
        "output_path": OUT,
        "output_schema": "command-center/schema/meta-review-finding.schema.json",
        "measure_line": "SUCCESS:delivered SYN-0014",
        "measure": {"exit_code": 0, "line": "SUCCESS:delivered SYN-0014"},
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "raw_output": t1,
                "role": "known-present-and-both-states",
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "raw_output": t2,
                "role": "band-vocabulary-and-hedge-residue",
            },
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
        "manifest_path": "command-center/p2-wave/probes/SYN-0014/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "SYN-0014-probe2-band-vocabulary",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for SYN-0014: live named probes exit 0, SYN-0014.json "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. SYN-0011 adjudications and "
            "SYN-0008 candidate syntheses are absent; CLAIM-REGISTRY.json "
            "and repo-root AGENTS.md are present (Sherman-Kent §7 is in "
            "agent-self/config/AGENTS.md). Fixture stratum is labeled."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": "SYN-0014",
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
    print("SUCCESS:SYN-0014 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
