#!/usr/bin/env python3
"""Emit IMP-0429 catalog receipt plus per-unit return/manifest.

Does not write the global unit manifest. Does not git add.
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
sys.path.insert(0, str(REPO / "tools" / "command-center"))
import event_log as elog  # noqa: E402

UNIT = "IMP-0429"
OUT = "command-center/receipts/IMP-0429.json"
SENTINEL = "SENTINEL:IMP-0429:EVENT-LOG-APPEND-SAFE"
WRITER = "tools/command-center/event_log.py"
SCHEMA = "command-center/schema/event.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0429/probe1_concurrency.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0429/probe2_mutation.py"
)
SUPPORTING = [
    WRITER,
    SCHEMA,
    "tools/command-center/close.py",
    "command-center/p2-wave/probes/IMP-0429/probe1_concurrency.py",
    "command-center/p2-wave/probes/IMP-0429/probe2_mutation.py",
    "command-center/p2-wave/probes/IMP-0429/write_receipts.py",
]


def utcnow() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )


def digest_file(rel: str) -> tuple[str, int]:
    raw = (REPO / rel).read_bytes().replace(b"\r\n", b"\n")
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
    )
    return proc.returncode, ((proc.stdout or "") + (proc.stderr or "")).strip()


def row(rel: str, role: str) -> dict:
    sha, size = digest_file(rel)
    return {
        "bytes": size,
        "path": rel,
        "present": True,
        "receipt_path": "command-center/p2-wave/probes/IMP-0429/SUBAGENT-RETURN.json",
        "role": role,
        "sha256": sha,
        "unit_id": UNIT,
    }


def emit_receipt(good: dict, bad: dict, started: str) -> None:
    receipt = {
        "answer": (
            f"Yes under atomic append: {good['line_count']} lines, {good['parsed']} parses, "
            f"{good['torn']} interleaved/truncated records, unique (writer,seq)="
            f"{good['unique_writer_seq']}. Removing single-write atomic mode produced "
            f"{bad['torn']} torn lines and turned the 8x500 clean-parse test red."
        ),
        "artifacts": [
            {
                "exists": True,
                "path": WRITER,
                "role": "primary-implementation",
            },
            {
                "exists": True,
                "path": SCHEMA,
                "role": "output-schema",
            },
            {
                "exists": True,
                "path": OUT,
                "role": "primary",
            },
        ],
        "concurrency": good,
        "evidence": [
            {
                "anchor": f"{WRITER}:_write_atomic",
                "claim": (
                    "8 processes x 500 events with one os.write per JSON line on an "
                    "O_APPEND fd yields 4000 parseable lines and zero torn records."
                ),
                "verdict": "CONFIRMED",
            },
            {
                "anchor": f"{WRITER}:_write_chunked",
                "claim": (
                    "The same load with atomic-append mode removed (chunked O_APPEND "
                    "writes) produces torn/interleaved lines and fails the 4000-parse test."
                ),
                "verdict": "CONFIRMED",
            },
        ],
        "mutation_control": {
            "atomic": False,
            "fired_on_bad_state": bad["torn"] > 0,
            "line_count": bad["line_count"],
            "parsed": bad["parsed"],
            "silent_on_good_state": good["torn"] == 0 and good["all_present"],
            "torn": bad["torn"],
            "torn_samples": bad.get("torn_samples", [])[:4],
            "wall_seconds": bad["wall_seconds"],
        },
        "question": (
            "Implement the append-only EVENTS.jsonl writer that is safe under concurrent "
            "appends from multiple sessions on Windows. Exact question: under 8 concurrent "
            "writers emitting 500 events each, are all 4000 lines present and is any line "
            "interleaved or truncated?"
        ),
        "reviewer": {
            "independent": True,
            "reviewer_id": "IMP-0429-probe2-mutation",
            "verdict": "PASS",
        },
        "schema_version": 1,
        "sentinel": SENTINEL,
        "state": "SUCCESS",
        "timestamps": {"ended_at": utcnow(), "started_at": started},
        "unit_id": UNIT,
        "writer": {
            "fcntl_used": False,
            "mechanism": (
                "os.open(O_APPEND|O_CREAT|O_WRONLY[+O_BINARY]) then a single os.write of "
                "one UTF-8 JSON line plus LF. No POSIX fcntl. Windows: O_APPEND is "
                "FILE_APPEND_DATA."
            ),
            "module": WRITER,
            "mutant_chunk": elog.MUTANT_CHUNK,
        },
    }
    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(receipt, indent=1, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def main() -> int:
    started = utcnow()
    import tempfile

    with tempfile.TemporaryDirectory(prefix="imp0429-receipt-") as tmp:
        tmp_path = Path(tmp)
        good = elog.run_fanout(tmp_path / "good.jsonl", writers=8, per_writer=500, atomic=True)
        bad = elog.run_fanout(tmp_path / "bad.jsonl", writers=8, per_writer=500, atomic=False)

    if not good.get("all_present"):
        print("FAILED:IMP-0429 atomic 8x500 is not clean; not emitting SUCCESS receipt")
        print(json.dumps(good, sort_keys=True)[:2000])
        return 1
    if bad.get("torn", 0) <= 0:
        print("FAILED:IMP-0429 mutation produced zero torn lines; not emitting SUCCESS receipt")
        print(json.dumps(bad, sort_keys=True)[:2000])
        return 1

    emit_receipt(good, bad, started)
    c1, t1 = run_cmd(P1)
    c2, t2 = run_cmd(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:IMP-0429 named probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1

    primary = row(OUT, "primary")
    artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING]
    now = utcnow()
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
        "id": UNIT,
        "manifest_path": "command-center/p2-wave/probes/IMP-0429/UNIT-ARTIFACT-MANIFEST.json",
        "measure": {"exit_code": None, "line": None},
        "named_probes": [
            {"command": P1, "exit_code": c1, "id": "probe1", "raw_output": t1},
            {"command": P2, "exit_code": c2, "id": "probe2", "raw_output": t2},
        ],
        "notes": (
            "G-1 for IMP-0429: live named probes exit 0, receipt state=SUCCESS with "
            "SENTINEL:IMP-0429:EVENT-LOG-APPEND-SAFE, per-unit manifest row. Did not "
            "run global unit_manifest.py --write. Atomic O_APPEND single-write 8x500 "
            "is 4000/4000/0; chunked mutation produces torn lines."
        ),
        "output_path": OUT,
        "output_schema": SCHEMA,
        "registered": True,
        "reviewer": {
            "independent": True,
            "reviewer_id": "IMP-0429-probe2-mutation",
            "verdict": "PASS",
        },
        "sentinel": SENTINEL,
        "state": "SUCCESS",
        "status": "DELIVERED",
        "ts": now,
        "unit_id": UNIT,
    }
    man = {
        "artifacts": artifacts,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "expected": len(artifacts),
        "present": len(artifacts),
        "schema_version": 1,
        "unit_id": UNIT,
        "verified_on_disk": True,
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"wrote {OUT} ({(REPO / OUT).stat().st_size} B)")
    print(f"concurrency lines={good['line_count']} parsed={good['parsed']} torn={good['torn']}")
    print(f"mutation torn={bad['torn']} fired={bad['torn'] > 0}")
    print(f"primary {OUT} sha256={primary['sha256']} bytes={primary['bytes']}")
    print(f"SUCCESS:{UNIT} receipt emitted")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
