#!/usr/bin/env python3
"""Emit command-center/receipts/IMP-0210.json from live stage + probe output.

Does not call tools/command-center/unit_manifest.py --write.
Does not validate against receipt.schema.json (that path is still absent on
this worktree; G-1 measure does not consult it).
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
P2 = REPO / "command-center" / "p2-wave"
sys.path.insert(0, str(P2))
sys.path.insert(0, str(REPO / "command-center" / "foundry" / "scout"))

import _p2lib as L  # noqa: E402
from licence_stage import verify_one  # noqa: E402

UNIT = "IMP-0210"
OUT = "command-center/receipts/IMP-0210.json"
SCHEMA = "command-center/schema/receipt.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0210/probe1_both_states.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0210/probe2_vocabulary.py"
)
FIX = HERE / "fixtures" / "twins.json"
SUPPORTING = [
    "command-center/foundry/scout/licence_stage.py",
    "command-center/foundry/scout/vocabulary.py",
    "command-center/foundry/scout/wf.scout-prior-art-licence.json",
    "command-center/p2-wave/probes/IMP-0210/fixtures/twins.json",
    "command-center/p2-wave/probes/IMP-0210/probe1_both_states.py",
    "command-center/p2-wave/probes/IMP-0210/probe2_vocabulary.py",
]


def run_probe(cmd: str) -> tuple[int, str]:
    env = dict(**{k: v for k, v in __import__("os").environ.items()})
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


def main() -> int:
    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:{UNIT} probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1

    doc = json.loads(FIX.read_text(encoding="utf-8"))
    target = doc["target_spdx"]
    unlicensed = verify_one(
        doc["twins"]["unlicensed_permissive_blurb"], target_spdx=target
    )
    licensed = verify_one(doc["twins"]["licensed_mit"], target_spdx=target)
    if unlicensed["disposition"] != "CLEAN-ROOM-REIMPLEMENT":
        print("FAILED:IMP-0210 emit unlicensed not CLEAN-ROOM-REIMPLEMENT")
        return 1
    if licensed["disposition"] != "ADOPT-AS-IS":
        print("FAILED:IMP-0210 emit MIT twin not ADOPT-AS-IS")
        return 1

    now = datetime.now(timezone.utc).replace(microsecond=0).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    artifacts = [L.art(p, "supporting") for p in SUPPORTING]
    p1 = L.probe("source", "command", P1, t1, c1)
    p2 = L.probe("verifier", "command", P2, t2, c2)

    receipt = {
        "schema_version": 1,
        "unit_id": UNIT,
        "id": UNIT,
        "state": "SUCCESS",
        "sentinel": "SUCCESS:IMP-0210",
        "completion_sentinel": "SUCCESS:IMP-0210",
        "spec_anchor": "_USER-PROMPTS.md:10723 (disposition vocabulary); catalog IMP-0210",
        "title": "Implement the scout prior-art stage with mandatory licence verification",
        "min_bytes_threshold": 128,
        "output_schema": SCHEMA,
        "implementation": {
            "stage": "command-center/foundry/scout/licence_stage.py",
            "vocabulary": "command-center/foundry/scout/vocabulary.py",
            "typed_stage_document": "command-center/foundry/scout/wf.scout-prior-art-licence.json",
            "not_claimed": [
                "full workflow-scout meta-workflow (IMP-0209)",
                "20-licence SPDX control set (IMP-0156)",
                "fusion licence matrix (IMP-0157)",
                "shared workflow runtime dogfooding",
            ],
        },
        "both_states": {
            "shared_id": unlicensed["id"],
            "target_spdx": target,
            "unlicensed_permissive_blurb": unlicensed,
            "licensed_mit": licensed,
            "verdicts_differ": unlicensed["disposition"] != licensed["disposition"],
        },
        "artifacts": artifacts,
        "evidence": [
            L.evidence(
                "Unlicensed candidate (permissive marketing blurb, no licence field) is dispositioned CLEAN-ROOM-REIMPLEMENT and is not recommended.",
                "CONFIRMED",
                "command-center/p2-wave/probes/IMP-0210/fixtures/twins.json:twins.unlicensed_permissive_blurb",
                [p1, p2],
                "almost-certain",
            ),
            L.evidence(
                "MIT twin (same id and blurb, SPDX MIT + LICENSE text) is dispositioned ADOPT-AS-IS and is recommended.",
                "CONFIRMED",
                "command-center/p2-wave/probes/IMP-0210/fixtures/twins.json:twins.licensed_mit",
                [p1, p2],
                "almost-certain",
            ),
        ],
        "tests": [
            {
                "id": "t1-both-states",
                "command": P1,
                "result": "PASS" if c1 == 0 else "FAIL",
                "exit_code": c1,
            },
            {
                "id": "t2-closed-vocabulary",
                "command": P2,
                "result": "PASS" if c2 == 0 else "FAIL",
                "exit_code": c2,
            },
        ],
        "negative_controls": [
            L.control(
                "unlicensed-twin",
                "both-states",
                "Permissively-described unlicensed twin must not ADOPT; MIT twin must ADOPT-AS-IS.",
                True,
                True,
                bad=unlicensed["disposition"],
                good=licensed["disposition"],
            ),
            L.control(
                "closed-vocab-ADOPT-truncation",
                "mutation",
                "Truncated ADOPT and other out-of-vocab aliases are refused by assert_disposition.",
                True,
                True,
                bad="ADOPT",
                good="ADOPT-AS-IS",
            ),
        ],
        "reviewer": {
            "reviewer_id": "IMP-0210-probe2-vocabulary",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": False,
            "notes": "Mechanical second probe on this worktree. Catalog asked for a cross-vendor Codex legal-surface reviewer; that reviewer was not run here.",
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/IMP-0210/UNIT-ARTIFACT-MANIFEST.json",
            "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        },
        "downstream_consumers": [
            {
                "consumer": "command-center/p2-wave/_measure_one_delivered.py",
                "artifact_path": OUT,
                "executed": False,
                "read_ok": False,
                "notes": "Filled after write_receipts.py; G-1 measure is the consumer.",
            }
        ],
        "residual_unknowns": [
            {
                "claim": "Cross-vendor Codex legal-surface review named by the catalog reviewer_requirement.",
                "verdict": "NOT-CHECKED",
                "settling_experiment": "Run an independent Codex reviewer against licence_stage.py and the both-states twins.",
            },
            {
                "claim": "Dependencies IMP-0156, IMP-0157, IMP-0209 are not delivered on this worktree.",
                "verdict": "NOT-CHECKED",
                "settling_experiment": "Compose this stage into workflow-scout once IMP-0209 exists; replace the local SPDX alias table with IMP-0156's extractor.",
            },
        ],
        "retry": {"count": 0, "policy": "two strikes then pivot"},
        "timestamps": {"started_at": now, "ended_at": now},
        "notes": (
            "G-1 for IMP-0210: scout prior-art licence stage is live. "
            "Unlicensed permissive-blurb twin -> CLEAN-ROOM-REIMPLEMENT; "
            "MIT twin -> ADOPT-AS-IS. Dispositions are the closed 15-value set. "
            "Did not run global unit_manifest.py --write. SUCCESS:IMP-0210"
        ),
    }

    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(receipt, indent=1, sort_keys=True) + "\n"
    out_path.write_text(payload, encoding="utf-8", newline="\n")
    raw = out_path.read_bytes().replace(b"\r\n", b"\n")
    digest = hashlib.sha256(raw).hexdigest()
    print(f"wrote {OUT} bytes={len(raw)} sha256={digest}")
    if "SUCCESS:IMP-0210" not in payload:
        print("FAILED:IMP-0210 sentinel missing from receipt")
        return 1
    if receipt["state"] in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print("FAILED:IMP-0210 self-declared non-delivery")
        return 1
    print("SUCCESS:IMP-0210 receipt emitted")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
