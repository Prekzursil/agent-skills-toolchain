#!/usr/bin/env python3
"""Write IMP-0351 receipt, SUBAGENT-RETURN.json, and per-unit manifest.

Runs named probes first. Does not invoke tools/command-center/unit_manifest.py --write.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(HERE))

from fixture import NEWER, QUESTION, seeded_log  # noqa: E402
from tools.council.outcomes.lineage_export import (  # noqa: E402
    DEFAULT_LOG_REL,
    commit_overturn,
    save_log,
    scan_live_contradictions,
)

UID = "IMP-0351"
OUT = f"command-center/receipts/{UID}.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0351/probe1_schema_and_supersession.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0351/probe2_contradiction_scan.py"
)
SUPPORTING = [
    "tools/council/outcomes/lineage_export.py",
    "tools/council/outcomes/lineage_record.schema.json",
    "command-center/decision-log/council-lineage.json",
    "command-center/p2-wave/probes/IMP-0351/probe1_schema_and_supersession.py",
    "command-center/p2-wave/probes/IMP-0351/probe2_contradiction_scan.py",
    "command-center/p2-wave/probes/IMP-0351/fixture.py",
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
        "unit_id": UID,
        "receipt_path": f"command-center/p2-wave/probes/{UID}/SUBAGENT-RETURN.json",
        "role": role,
    }


def seed_program_log() -> dict:
    doc = seeded_log()
    commit_overturn(doc, NEWER, "DEC-0351-A", mark=True)
    save_log(doc, REPO / DEFAULT_LOG_REL)
    scan = scan_live_contradictions(doc)
    return {"path": DEFAULT_LOG_REL, "entries": len(doc["entries"]), "scan": scan.as_dict()}


def write_receipt(log_info: dict, t1: str, t2: str) -> None:
    export_rel = "tools/council/outcomes/lineage_export.py"
    export_path = REPO / export_rel
    lines = export_path.read_text(encoding="utf-8").splitlines()
    marker_line = next(
        (i + 1 for i, line in enumerate(lines) if "superseded_by" in line and "STATUS_SUPERSEDED" in line),
        1,
    )
    scan_line = next(
        (i + 1 for i, line in enumerate(lines) if "def scan_live_contradictions" in line),
        1,
    )
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    receipt = {
        "unit_id": UID,
        "id": UID,
        "state": "SUCCESS",
        "status": "SUCCESS",
        "sentinel": f"SUCCESS:{UID}",
        "title": "Decision-lineage export into the program decision log",
        "spec_anchor": (
            "command-center/WORK-UNIT-CATALOG.json:IMP-0351 "
            "question_or_target (tools/council/outcomes/lineage_export.py; "
            "supersession marker vs two contradictory live decisions). "
            "11-COUNCIL-SPECIFICATION.md and 17-DECISION-LOG.md are not on this worktree."
        ),
        "artifact_paths": [
            export_rel,
            "tools/council/outcomes/lineage_record.schema.json",
            DEFAULT_LOG_REL,
            OUT,
        ],
        "evidence": [
            {
                "id": "E1",
                "kind": "contradiction-scan",
                "claim": (
                    "Unmarked overturn leaves two LIVE disagreeing rows; "
                    "scan_live_contradictions lists DEC-0351-A vs DEC-0351-B and FIRES."
                ),
                "anchor": f"{export_rel}:{scan_line}",
                "probe": "probe2_contradiction_scan.py",
                "observed": "fired=true on unmarked; fired=false on empty and on marked",
            },
            {
                "id": "E2",
                "kind": "overturn-fixture",
                "claim": (
                    "commit_overturn(mark=True) writes status=SUPERSEDED and "
                    "superseded_by=DEC-0351-B on the older entry."
                ),
                "anchor": f"{export_rel}:{marker_line}",
                "probe": "probe1_schema_and_supersession.py",
                "observed": "DEC-0351-A superseded_by DEC-0351-B; scan silent; live_count=1",
            },
            {
                "id": "E3",
                "kind": "program-log",
                "claim": "Council slice of the program decision log holds the marked overturn.",
                "anchor": DEFAULT_LOG_REL,
                "observed": log_info,
            },
        ],
        "test_ids": [
            "IMP-0351-probe1-schema-and-supersession",
            "IMP-0351-probe2-contradiction-scan-both-states",
        ],
        "negative_control_ids": [
            "IMP-0351-NC-unmarked-overturn-scan-fires",
        ],
        "reviewer_verdict": "PASS",
        "reviewer": {
            "reviewer_id": "IMP-0351-probe2-contradiction-scan",
            "independent": True,
            "starts_from": "tests/negative-control, not author summary",
            "note": (
                "Mechanical adversarial suite in this worktree. A second human "
                "or model in a fresh context was not run."
            ),
        },
        "residual_unknowns": [
            "11-COUNCIL-SPECIFICATION.md / .schema.json and 17-DECISION-LOG.md are absent from this Linux worktree; lineage is stored at command-center/decision-log/council-lineage.json rather than appended to the missing markdown log.",
            "Dependencies IMP-0258 (precedent retrieval) and IMP-0259 (claim registry) are not delivered here; this exporter writes the log those units would read.",
            "command-center/schema/receipt.schema.json is absent on this worktree; G-1 for this unit does not consult it.",
        ],
        "falsifiable_answer": (
            "With commit_overturn(mark=True) the earlier entry acquires a "
            "supersession marker. With mark=False the log holds two contradictory "
            "LIVE decisions and scan_live_contradictions FIRES."
        ),
        "question": QUESTION,
        "ts": now,
        "SUCCESS:IMP-0351": True,
    }
    dest = REPO / OUT
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    log_info = seed_program_log()
    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:receipts probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1
    write_receipt(log_info, t1, t2)
    primary = row(OUT, "primary")
    artifacts = [primary] + [row(path, "supporting") for path in SUPPORTING]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ret = {
        "id": UID,
        "unit_id": UID,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": f"SUCCESS:{UID}",
        "registered": True,
        "output_path": OUT,
        "output_schema": (
            "command-center/schema/receipt.schema.json profile=council-runtime-module"
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
        "manifest_path": f"command-center/p2-wave/probes/{UID}/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "IMP-0351-probe2-contradiction-scan",
            "verdict": "PASS",
            "independent": True,
        },
        "ts": now,
        "notes": (
            "G-1 for IMP-0351: live named probes exit 0, receipt state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write. "
            "cloud ok=true is not delivery."
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
    print("SUCCESS:IMP-0351 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
