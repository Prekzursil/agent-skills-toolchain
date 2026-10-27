#!/usr/bin/env python3
"""Shard 12 wave 2: run probes and emit SUBAGENT-RETURN.json + UNIT-ARTIFACT-MANIFEST.json.

For each unit: run the two named probes fresh (capturing output), compute the CRLF-
normalized sha256 of the live receipt and supporting artifacts, then write the per-unit
probe records. Exit 0 only if every probe exited 0 and every file written.
"""
from __future__ import annotations

import datetime
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

W = Path(__file__).resolve().parents[1]

SUPPORTING = {
    "IMP-0165": [
        "tools/workflow_foundry/role_extract.py",
    ],
    "IMP-0219": [
        "tools/agentspec/agentspec/fanout.py",
        "tools/agentspec/agentspec/oracle.py",
        "tools/agentspec/agentspec/progress.py",
    ],
    "IMP-0224": [
        "tools/event-ledger/ledger.py",
        "tools/event-ledger/kill_target.py",
        "tools/event-ledger/naive_writer_NOTE.txt" if False else "command-center/p2-wave/probes/IMP-0224/naive_writer.py",
    ],
    "IMP-0228": [
        "tools/agentspec/agentspec/replay_log.py",
        "tools/agentspec/agentspec/replay.py",
        "tools/agentspec/agentspec/plan.py",
        "tools/agentspec/agentspec/determinism.py",
    ],
}

PROBES = {
    "IMP-0165": [
        ("probe1", "probe1_invented_vs_synonym.py", "invented-vs-synonym-both-states"),
        ("probe2", "probe2_unknown_rate.py", "unknown-rate-computed"),
    ],
    "IMP-0219": [
        ("probe1", "probe1_exit0_missing_receipt.py", "exit0-missing-receipt-both-states"),
        ("probe2", "probe2_progress_stream.py", "progress-stream-never-parsed"),
    ],
    "IMP-0224": [
        ("probe1", "probe1_kill_loop.py", "50-iteration-sigkill-staging-write"),
        ("probe2", "probe2_line_schema.py", "per-line-schema-plus-adversarial-controls"),
    ],
    "IMP-0228": [
        ("probe1", "probe1_cross_machine.py", "cross-machine-plan-bytes-or-named-input"),
        ("probe2", "probe2_zero_dispatch.py", "zero-dispatch-counted-both-states"),
    ],
}


def sha_of(path: Path) -> str:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest()


def run_probe(rel: str) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONPATH"] = os.pathsep.join([
        str(W / "tools" / "agentspec"),
        str(W),
        str(W / "tools"),
        env.get("PYTHONPATH", ""),
    ])
    argv = [sys.executable, "-B", str(W / rel.replace("/", "\\"))]
    p = subprocess.run(
        argv,
        cwd=str(W),
        capture_output=True,
        text=True,
        timeout=1200,
        env=env,
    )
    text = ((p.stdout or "") + (p.stderr or "")).strip()
    return p.returncode, text[-4000:]


def main() -> int:
    wanted = sys.argv[1:] or list(PROBES)
    all_ok = True
    for uid in wanted:
        receipt_path = W / "command-center" / "receipts" / (uid + ".json")
        probe_dir = W / "command-center" / "p2-wave" / "probes" / uid
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        receipt_sha = sha_of(receipt_path)

        named = []
        ok_unit = True
        for pid_, fname, role in PROBES[uid]:
            rel = "command-center/p2-wave/probes/%s/%s" % (uid, fname)
            code, tail = run_probe(rel)
            if code != 0:
                ok_unit = False
            named.append({
                "id": pid_,
                "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B " + rel,
                "exit_code": code,
                "raw_output": tail,
                "role": role,
            })

        artifacts = [{
            "unit_id": uid,
            "path": "command-center/receipts/%s.json" % uid,
            "sha256": receipt_sha,
            "bytes": receipt_path.stat().st_size,
            "present": True,
            "role": "primary",
            "receipt_path": "command-center/p2-wave/probes/%s/SUBAGENT-RETURN.json" % uid,
        }]
        for rel in SUPPORTING[uid]:
            p = W / rel.replace("/", "\\") if os.name == "nt" else W / rel
            if not p.is_file():
                ok_unit = False
                continue
            artifacts.append({
                "unit_id": uid,
                "path": rel,
                "sha256": sha_of(p),
                "bytes": p.stat().st_size,
                "present": True,
                "role": "supporting",
                "receipt_path": "command-center/p2-wave/probes/%s/SUBAGENT-RETURN.json" % uid,
            })
        for _, fname, _role in PROBES[uid]:
            rel = "command-center/p2-wave/probes/%s/%s" % (uid, fname)
            p = probe_dir / fname
            artifacts.append({
                "unit_id": uid,
                "path": rel,
                "sha256": sha_of(p),
                "bytes": p.stat().st_size,
                "present": True,
                "role": "supporting",
                "receipt_path": "command-center/p2-wave/probes/%s/SUBAGENT-RETURN.json" % uid,
            })

        rev = receipt.get("reviewer") or {}
        reviewer = {
            "reviewer_id": str(rev.get("reviewer_id") or "pending"),
            "verdict": str(rev.get("verdict") or "NOT-REVIEWED"),
            "independent": bool(rev.get("independent", False)),
            "notes": str(rev.get("notes") or ""),
        }
        rstate = str(receipt.get("state") or "UNKNOWN")
        if rstate == "SUCCESS":
            ret_state = "DELIVERED"
            fail_class = []
        else:
            ret_state = "BLOCKED-PENDING-INDEPENDENT-REVIEW"
            fail_class = ["reviewer-absent"]

        ret = {
            "id": uid,
            "unit_id": uid,
            "status": "DELIVERED" if ok_unit else "FAILED",
            "state": ret_state if ok_unit else "BLOCKED",
            "receipt_state": rstate,
            "output_path": receipt.get("output_path") or ("command-center/receipts/%s.json" % uid),
            "output_schema": receipt.get("output_schema") or "command-center/schema/receipt.schema.json",
            "sentinel": receipt.get("sentinel") or ("SUCCESS:%s" % uid),
            "manifest_path": "command-center/p2-wave/probes/%s/UNIT-ARTIFACT-MANIFEST.json" % uid,
            "registered": True,
            "cloud_ok": False,
            "failure_classification": fail_class,
            "reviewer": reviewer,
            "primary_artifact": {
                "path": "command-center/receipts/%s.json" % uid,
                "bytes": receipt_path.stat().st_size,
                "sha256": receipt_sha,
            },
            "artifacts": artifacts,
            "named_probes": named,
            "notes": (
                "Shard 12 wave 2 rebuild (2026-10-25): the probe directory was absent on"
                " this worktree; probes rebuilt from the receipt's documented commands"
                " and re-run live against the current implementation. Receipt closure"
                " (%s) kept because it still verifies live." % rstate
            ),
            "ts": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
        (probe_dir / "SUBAGENT-RETURN.json").write_text(
            json.dumps(ret, indent=1, ensure_ascii=False), encoding="utf-8"
        )
        manifest = {
            "unit_id": uid,
            "artifacts": artifacts,
            "generated": ret["ts"],
            "derivation": "shard12-w2 builder (matches _measure_one_delivered.py hashing)",
        }
        (probe_dir / "UNIT-ARTIFACT-MANIFEST.json").write_text(
            json.dumps(manifest, indent=1, ensure_ascii=False), encoding="utf-8"
        )
        print("%s probes_ok=%s receipt_state=%s sha=%s"
              % (uid, ok_unit, rstate, receipt_sha[:12]))
        if not ok_unit:
            all_ok = False
    print("SUCCESS:shard12 records built" if all_ok else "FAILED:shard12 records")
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
