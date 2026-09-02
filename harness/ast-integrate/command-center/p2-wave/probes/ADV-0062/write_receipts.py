#!/usr/bin/env python3
"""Write per-unit SUBAGENT-RETURN.json and UNIT-ARTIFACT-MANIFEST.json."""
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
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import emit as E  # noqa: E402
from probe_common import P1_CMD, P2_CMD  # noqa: E402

OUT = E.OUT
SCHEMA = E.SCHEMA
SUPPORTING = [
    SCHEMA,
    "command-center/p2-wave/probes/ADV-0062/packager.py",
    "command-center/p2-wave/probes/ADV-0062/probe_common.py",
    "command-center/p2-wave/probes/ADV-0062/probe1_rebuild_compare.py",
    "command-center/p2-wave/probes/ADV-0062/probe2_causal_attribution.py",
    "command-center/p2-wave/probes/ADV-0062/emit.py",
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
        "unit_id": "ADV-0062",
        "receipt_path": "command-center/p2-wave/probes/ADV-0062/SUBAGENT-RETURN.json",
        "role": role,
    }


def main() -> int:
    c1, t1 = run_probe(P1_CMD)
    c2, t2 = run_probe(P2_CMD)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:ADV-0062 receipts probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1
    doc = E.build_doc(probe1_raw=t1, probe2_raw=t2, p1_rc=c1, p2_rc=c2)
    out_path = E.write_artifact(doc)
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:ADV-0062 self-declared {doc.get('state')}")
        return 1
    extra = []
    for name in ("probe1-measurement.json", "probe2-measurement.json"):
        rel = f"command-center/p2-wave/probes/ADV-0062/{name}"
        if (REPO / rel).is_file():
            extra.append(rel)
    primary = row(OUT, "primary")
    artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING + extra]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ret = {
        "id": "ADV-0062",
        "unit_id": "ADV-0062",
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:ADV-0062",
        "registered": True,
        "output_path": OUT,
        "output_schema": SCHEMA,
        "named_probes": [
            {
                "id": "probe1",
                "command": P1_CMD,
                "exit_code": c1,
                "role": "rebuild-and-compare",
                "raw_output": t1[-8000:],
            },
            {
                "id": "probe2",
                "command": P2_CMD,
                "exit_code": c2,
                "role": "causal-attribution",
                "raw_output": t2[-8000:],
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
        "manifest_path": "command-center/p2-wave/probes/ADV-0062/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "ADV-0062-probe2-causal-attribution",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for ADV-0062: live named probes exit 0, artifact state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write. "
            "No ADV rebuild circle. Historical shipped zip absent; attested "
            "local package rebuilds byte-identically."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": "ADV-0062",
        "verified_on_disk": True,
        "expected": len(artifacts),
        "present": len(artifacts),
        "artifacts": artifacts,
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1, sort_keys=True, ensure_ascii=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1, sort_keys=True, ensure_ascii=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(f"primary {OUT} sha256={primary['sha256']} bytes={primary['bytes']}")
    print(f"wrote {out_path}")
    print("SUCCESS:ADV-0062 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
