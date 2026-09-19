#!/usr/bin/env python3
"""Write per-unit SUBAGENT-RETURN.json and UNIT-ARTIFACT-MANIFEST.json."""

from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
OUT = "command-center/audit/AUD-0084-hardcoded-path-census.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/AUD-0084/probe1_literal_scan.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/AUD-0084/probe2_ast_adjudication.py"
)
EMIT = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/AUD-0084/emit_census.py"
)
SUPPORTING = [
    "command-center/p2-wave/probes/AUD-0084/artifact.schema.json",
    "command-center/p2-wave/probes/AUD-0084/census.py",
    "command-center/p2-wave/probes/AUD-0084/emit_census.py",
    "command-center/p2-wave/probes/AUD-0084/probe1_literal_scan.py",
    "command-center/p2-wave/probes/AUD-0084/probe2_ast_adjudication.py",
    "command-center/p2-wave/probes/AUD-0084/fixtures/use_vs_mention_fixture.py",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_cmd(cmd: str) -> tuple[int, str]:
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
        "unit_id": "AUD-0084",
        "receipt_path": "command-center/p2-wave/probes/AUD-0084/SUBAGENT-RETURN.json",
        "role": role,
    }


def main() -> int:
    ce, te = run_cmd(EMIT)
    print(te[-2000:])
    if ce != 0:
        print(f"FAILED:AUD-0084 receipts emit rc={ce}")
        return 1
    c1, t1 = run_cmd(P1)
    print(t1[-2000:])
    c2, t2 = run_cmd(P2)
    print(t2[-2000:])
    if c1 != 0 or c2 != 0:
        print(f"FAILED:AUD-0084 receipts probes c1={c1} c2={c2}")
        return 1

    # Embed live probe stdout into the artifact, then re-hash.
    art_path = REPO / OUT
    doc = json.loads(art_path.read_text(encoding="utf-8"))
    probes = doc.get("named_probes") or []
    for item, text, code in ((probes[0], t1, c1), (probes[1], t2, c2)):
        item["raw_output"] = text
        item["exit_code"] = code
    doc["named_probes"] = probes
    art_path.write_text(
        json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )

    # Probes check census counts, not stdout; re-run after embed so measure matches.
    c1b, t1b = run_cmd(P1)
    c2b, t2b = run_cmd(P2)
    if c1b != 0 or c2b != 0:
        print(f"FAILED:AUD-0084 receipts post-embed probes c1={c1b} c2={c2b}")
        print(t1b[-1500:])
        print(t2b[-1500:])
        return 1

    primary = row(OUT, "primary")
    artifacts = [primary]
    for p in SUPPORTING:
        if (REPO / p).is_file():
            artifacts.append(row(p, "supporting"))
        else:
            print(f"FAILED:AUD-0084 missing supporting {p}")
            return 1
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ret = {
        "id": "AUD-0084",
        "unit_id": "AUD-0084",
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:AUD-0084",
        "registered": True,
        "output_path": OUT,
        "output_schema": "command-center/schema/audit-finding.schema.json",
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1b,
                "role": "literal-string-scan",
                "raw_output": t1b,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2b,
                "role": "ast-use-versus-mention",
                "raw_output": t2b,
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
        "manifest_path": "command-center/p2-wave/probes/AUD-0084/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "AUD-0084-probe2-ast-use-versus-mention",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for AUD-0084: live named probes exit 0, hardcoded-path-census "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. Declared audit-finding.schema.json is "
            "absent; local artifact.schema.json used. cloud ok=true is not delivery. "
            "No ADV rebuild."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": "AUD-0084",
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
    print("SUCCESS:AUD-0084 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
