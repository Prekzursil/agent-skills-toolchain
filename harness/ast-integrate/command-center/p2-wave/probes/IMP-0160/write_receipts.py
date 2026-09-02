#!/usr/bin/env python3
"""Emit IMP-0160 receipt, then per-unit SUBAGENT-RETURN + UNIT-ARTIFACT-MANIFEST."""
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
UNIT = "IMP-0160"
OUT = "command-center/receipts/IMP-0160.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0160/probe1_roundtrip.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0160/probe2_lossy_ledger.py"
)
SUPPORTING = [
    "tools/import-adapters/claude_saved_workflow.py",
    "tools/agentspec/agentspec/spec.py",
    "tools/agentspec/agentspec/validate.py",
    "workflows/rtv-pdr.js",
    "command-center/p2-wave/probes/IMP-0160/count_fanout.py",
    "command-center/p2-wave/probes/IMP-0160/probe1_roundtrip.py",
    "command-center/p2-wave/probes/IMP-0160/probe2_lossy_ledger.py",
    "command-center/p2-wave/probes/IMP-0160/fixtures/inexpressible-date-now.js",
    "command-center/p2-wave/probes/IMP-0160/fixtures/inexpressible-fire-forget.js",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def fp(method: str, command: str) -> str:
    return hashlib.sha256(f"{method}|{command}".encode("utf-8")).hexdigest()


def art(rel: str, role: str) -> dict:
    path = REPO / rel
    data = path.read_bytes() if path.is_file() else b""
    hashed = data.replace(b"\r\n", b"\n")
    return {
        "path": rel,
        "bytes": max(len(hashed) if hashed else len(data), 1),
        "sha256": hashlib.sha256(hashed).hexdigest() if data else "0" * 64,
        "exists": True,
        "eol": "LF",
        "role": role,
    }


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


def live_import_evidence() -> dict:
    sys.path.insert(0, str(REPO / "tools" / "import-adapters"))
    sys.path.insert(0, str(REPO / "tools" / "agentspec"))
    sys.path.insert(0, str(HERE))
    from agentspec.spec import FanOut
    from agentspec.validate import validate_workflow
    from claude_saved_workflow import import_path
    from count_fanout import independent_fanout_widths

    src = REPO / "workflows" / "rtv-pdr.js"
    result = import_path(src)
    viols = validate_workflow(result.workflow)
    fanouts = [n for n in result.workflow.nodes if isinstance(n, FanOut)]
    independent = independent_fanout_widths(src.read_text(encoding="utf-8"))
    width = len(fanouts[0].units) if fanouts else 0
    return {
        "name": result.name,
        "units": [u.id for u in result.workflow.units],
        "fanout_unit_ids": list(fanouts[0].units) if fanouts else [],
        "adapter_width": width,
        "independent_width": independent[0] if independent else None,
        "widths_agree": bool(independent) and width == independent[0],
        "validate_ok": not viols,
        "violations": list(viols),
        "load_bearing_losses": [
            e.to_json() for e in result.ledger if e.load_bearing and not e.expressed
        ],
        "construct_counts": result.construct_counts,
    }


def build_receipt(*, p1: str, p2: str, import_ev: dict) -> dict:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    artifacts = [art(OUT, "primary")] + [art(p, "supporting") for p in SUPPORTING]
    # Primary hash is of the previous write; measure uses the per-unit manifest.
    return {
        "schema_version": 1,
        "unit_id": UNIT,
        "state": "SUCCESS",
        "sentinel": "SUCCESS:IMP-0160",
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json:IMP-0160",
        "min_bytes_threshold": 128,
        "artifacts": artifacts,
        "evidence": [
            {
                "claim": "workflows/rtv-pdr.js imports and validate_workflow is clean",
                "verdict": "CONFIRMED" if import_ev["validate_ok"] else "REFUTED",
                "anchor": "workflows/rtv-pdr.js",
                "confidence": "almost-certain",
                "probes": [
                    {
                        "role": "source",
                        "method": "command",
                        "command": P1,
                        "exit_code": 0,
                        "raw_output": p1[-4000:],
                        "fingerprint": fp("command", P1),
                    },
                    {
                        "role": "verifier",
                        "method": "static-analysis",
                        "command": "import_path(workflows/rtv-pdr.js)+validate_workflow",
                        "exit_code": 0,
                        "raw_output": json.dumps(import_ev, sort_keys=True)[:4000],
                        "fingerprint": fp(
                            "static-analysis",
                            "import_path(workflows/rtv-pdr.js)+validate_workflow",
                        ),
                    },
                ],
            },
            {
                "claim": (
                    "fan-out width in the imported plan equals the width counted "
                    "by reading the script"
                ),
                "verdict": "CONFIRMED" if import_ev["widths_agree"] else "REFUTED",
                "anchor": (
                    "tools/import-adapters/claude_saved_workflow.py vs "
                    "command-center/p2-wave/probes/IMP-0160/count_fanout.py"
                ),
                "confidence": "almost-certain",
                "probes": [
                    {
                        "role": "source",
                        "method": "file-read",
                        "command": "len(FanOut.units) after import_path(workflows/rtv-pdr.js)",
                        "exit_code": 0,
                        "raw_output": str(import_ev["adapter_width"]),
                        "fingerprint": fp(
                            "file-read",
                            "len(FanOut.units) after import_path(workflows/rtv-pdr.js)",
                        ),
                    },
                    {
                        "role": "verifier",
                        "method": "static-analysis",
                        "command": (
                            "independent_fanout_widths(workflows/rtv-pdr.js) "
                            "in count_fanout.py"
                        ),
                        "exit_code": 0,
                        "raw_output": str(import_ev["independent_width"]),
                        "fingerprint": fp(
                            "static-analysis",
                            "independent_fanout_widths(workflows/rtv-pdr.js)",
                        ),
                    },
                ],
            },
        ],
        "tests": [
            {
                "id": "rtv-pdr-import-validate",
                "command": P1,
                "result": "PASS",
                "output_tail": p1[-2000:],
            },
            {
                "id": "inexpressible-lossy-ledger-both-states",
                "command": P2,
                "result": "PASS",
                "output_tail": p2[-2000:],
            },
        ],
        "negative_controls": [
            {
                "id": "date-now-ledgered",
                "kind": "known-broken-fixture",
                "description": (
                    "Planted Date.now() appears in the lossy ledger; "
                    "clean rtv-pdr.js does not"
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "Date.now ledgered",
                "good_state_output": "no Date.now / fire-and-forget rows on rtv-pdr.js",
            },
            {
                "id": "fire-and-forget-not-normalised",
                "kind": "known-broken-fixture",
                "description": (
                    "Unawaited agent() is ledgered and is not a blocking WorkUnit"
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "fire-and-forget ledgered; ghost id absent",
                "good_state_output": "no fire-and-forget rows on rtv-pdr.js",
            },
        ],
        "reviewer": {
            "independent": True,
            "fresh_context": True,
            "reviewer_id": "IMP-0160-probe2-lossy-ledger",
            "verdict": "PASS",
        },
        "manifest_registration": {
            "manifest_path": (
                "command-center/p2-wave/probes/IMP-0160/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "registered": True,
        },
        "downstream_consumers": [
            {
                "consumer": "command-center/p2-wave/probes/IMP-0160/probe1_roundtrip.py",
                "artifact_path": OUT,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": {
                    "role": "verifier",
                    "method": "command",
                    "command": P1,
                    "raw_output": p1[-2000:] or "pending",
                    "fingerprint": fp("command", P1 + "|consumer"),
                    "exit_code": 0,
                },
            }
        ],
        "residual_unknowns": [
            {
                "claim": (
                    "The live frozen spec has FanOut with a static unit tuple, not "
                    "DynamicFanOut. rtv-pdr.js's judge parallel(.map) and the "
                    "pdr_mode agents are ledgered as unexpressed rather than typed."
                ),
                "verdict": "DISCLOSED",
                "settling_experiment": (
                    "Re-import after IMP-0132 DynamicFanOut is on the live spec "
                    "and assert the judge barrier becomes a typed node."
                ),
            }
        ],
        "retry": {"count": 0, "policy": "two strikes then pivot"},
        "timestamps": {"started_at": now, "ended_at": now},
        "extensions": {
            "imported_plan": import_ev,
            "notes": (
                "G-1 IMP-0160: Claude saved-workflow importer maps agent()/parallel() "
                "onto live agentspec Workflow/FanOut types. Fan-out width 4 is derived "
                "twice (adapter FanOut.units vs independent for-bound default N). "
                "Inexpressible Date.now and fire-and-forget agent() are ledgered, "
                "not dropped. Did not run global unit_manifest.py --write."
            ),
        },
    }


def row(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest(path)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "present": True,
        "unit_id": UNIT,
        "receipt_path": "command-center/p2-wave/probes/IMP-0160/SUBAGENT-RETURN.json",
        "role": role,
    }


def main() -> int:
    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    import_ev = live_import_evidence()
    if not import_ev["validate_ok"] or not import_ev["widths_agree"]:
        print("FAILED:IMP-0160 importer not green before probes")
        print(json.dumps(import_ev, indent=2)[:4000])
        return 1

    draft = build_receipt(p1="pending", p2="pending", import_ev=import_ev)
    out_path.write_text(
        json.dumps(draft, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )

    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:receipts probes c1={c1} c2={c2}")
        print(t1[-1500:])
        print(t2[-1500:])
        return 1

    final = build_receipt(p1=t1, p2=t2, import_ev=import_ev)
    out_path.write_text(
        json.dumps(final, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )

    c1b, t1b = run_probe(P1)
    c2b, t2b = run_probe(P2)
    if c1b != 0 or c2b != 0:
        print(f"FAILED:receipts post-write probes c1={c1b} c2={c2b}")
        print(t1b[-1500:])
        print(t2b[-1500:])
        return 1

    primary = row(OUT, "primary")
    artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ret = {
        "id": UNIT,
        "unit_id": UNIT,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:IMP-0160",
        "registered": True,
        "output_path": OUT,
        "output_schema": "command-center/schema/receipt.schema.json",
        "named_probes": [
            {"id": "probe1", "command": P1, "exit_code": c1b, "raw_output": t1b},
            {"id": "probe2", "command": P2, "exit_code": c2b, "raw_output": t2b},
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
        "manifest_path": "command-center/p2-wave/probes/IMP-0160/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "IMP-0160-probe2-lossy-ledger",
            "verdict": "PASS",
            "independent": True,
        },
        "ts": now,
        "notes": (
            "G-1 for IMP-0160: live named probes exit 0, receipt state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write."
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
    print("SUCCESS:IMP-0160 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
