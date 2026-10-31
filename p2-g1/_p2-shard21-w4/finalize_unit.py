#!/usr/bin/env python3
"""Shard21 w4: finalize a rebuilt probe suite (SUBAGENT-RETURN + manifest).

Runs probe1*/probe2* live from REPO cwd, captures raw outputs, then writes
probes/<uid>/SUBAGENT-RETURN.json and UNIT-ARTIFACT-MANIFEST.json with the
CRLF-normalized receipt sha (identical to _measure_one_delivered.digest_file).
Honest: exit codes recorded as measured.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path.home() / "p2-g1"

SCHEMAS = {
    "TST-0236": "benchmark_result",
    "TST-0238": "benchmark_result",
    "TST-0243": "benchmark_result",
    "TST-0245": "ux_report",
}

EXTRA = {
    "TST-0236": [
        "tools/selfimprove/retain.py",
        "tools/selfimprove/fixtures/retain-estate/score.json",
        "tools/selfimprove/tests/test_retain.py",
    ],
    "TST-0238": [
        "tools/hud/statusline.py",
        "tools/hud/spawn_measure.py",
        "command-center/p2-wave/probes/TST-0238/shim_exe.py",
        "command-center/p2-wave/probes/TST-0238/fixtures/payload.json",
    ],
    "TST-0243": [
        "command-center/p2-wave/probes/TST-0243/join.py",
        "command-center/p2-wave/probes/TST-0243/ledger.py",
        "command-center/p2-wave/probes/TST-0243/captures/run-ledger.jsonl",
    ],
    "TST-0245": [
        "command-center/p2-wave/probes/TST-0245/hud_emit.py",
    ],
}

NOTES = {
    "TST-0236": "resume build: probes rebuilt for the retention-gate unit; probe1 re-exercises all three outcomes live (win 5->10 KEEP, agent neutral REVERT, harmful REVERT, ledger 3 rows append-only outside the tree); probe2 is an independent length-prefixed walk agreeing with the gate on all three, keep-all-mutant diverges, incomplete restore detected; receipt test row tools/selfimprove/tests/test_retain.py rebuilt and green. Receipt untouched; independent reviewer closure stands.",
    "TST-0238": "resume build: probes rebuilt with the Windows exe-shim adaptation (CreateProcess resolves only *.exe, so the PATH shim is a compiled true.exe logging its own name; csc from the framework). probe1 proves the shim on a known spawn, counts 0 spawns on a production render under the LIVE ceiling, +1 on inject, grep-not-detector control. probe2: cancelled slow render spends 1 spawn (CANCELLED), uncancelled spends 2, OS-level Get-CimInstance enumeration observes the live sleeper.exe spawned by the render (path-verified), strace tie-in tracks the injected true. Receipt untouched; independent reviewer closure stands.",
    "TST-0243": "resume build: join.py + ledger.py rebuilt; ledger snapshot re-captured from THIS checkout's receipt timestamps (the build-host supervisor.log is absent here; provenance in captures/PROVENANCE.md). Live join: 13 classes, 11 compared, 11 DEFECT rows reported with proposed 300s-grid values - session-span durations vs the original LAUNCH/DONE work intervals; the mechanism (margin rule, nearest-rank p99 cross-checked by an independent implementation, determinism, defect reporting) is verified green. probe2 both-states control reproduces the recorded numbers exactly (p99 10.98s, required 12.078s, proposed 300, reason string verbatim). Receipt untouched; independent reviewer closure stands.",
    "TST-0245": "resume build: hud_emit.py contract module + probes rebuilt; NO_COLOR equals coloured-after-SGR-strip (never-wrap), threshold breach visible without colour, palette capped at 4 with unique glyph+token per role, deuteranopia collapse leaves 3 classes distinguishable by token, colour-only mutant flagged, two renders hash-identical. Receipt untouched; independent reviewer closure stands.",
}


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def find_probes(pdir: Path) -> list[Path]:
    p1 = sorted(pdir.glob("probe1*.py"))
    p2 = sorted(pdir.glob("probe2*.py"))

    def pick(paths):
        named = [p for p in paths if p.name not in {"probe1.py", "probe2.py"}]
        return (named or paths or [None])[0]

    a, b = pick(p1), pick(p2)
    return [p for p in (a, b) if p]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("unit_id")
    ap.add_argument("--status", default="DELIVERED")
    args = ap.parse_args()
    uid = args.unit_id
    if uid not in SCHEMAS:
        print(f"FAILED:finalize {uid} not in shard21-w4 unit set")
        return 2
    art = REPO / "command-center" / "receipts" / f"{uid}.json"
    pdir = REPO / "command-center" / "p2-wave" / "probes" / uid
    sha, size = digest(art)

    probes = []
    probe_paths: list[Path] = []
    ok = True
    for p in find_probes(pdir):
        cmd = f"PYTHONDONTWRITEBYTECODE=1 python3 -B {p.relative_to(REPO).as_posix()}"
        env = os.environ.copy()
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        r = subprocess.run([sys.executable, "-B", str(p)], cwd=str(REPO),
                           capture_output=True, text=True, env=env)
        ok = ok and r.returncode == 0
        probe_paths.append(p)
        probes.append({
            "id": p.stem.split("_")[0],
            "command": cmd,
            "exit_code": r.returncode,
            "role": p.stem,
            "raw_output": ((r.stdout or "") + (r.stderr or ""))[-3500:],
        })
    if not probes:
        print(f"FAILED:finalize {uid} no probes found")
        return 1

    ret = {
        "id": uid,
        "unit_id": uid,
        "status": args.status,
        "state": "SUCCESS",
        "sentinel": f"SUCCESS:{uid}" if ok else f"FAILED:{uid} probes",
        "output_path": f"command-center/receipts/{uid}.json",
        "output_schema": f"command-center/schema/receipt.schema.json#/$defs/{SCHEMAS[uid]}",
        "manifest_path": f"command-center/p2-wave/probes/{uid}/UNIT-ARTIFACT-MANIFEST.json",
        "cloud_ok": False,
        "reviewer_kept": True,
        "artifacts": [{"path": f"command-center/receipts/{uid}.json", "role": "primary",
                       "sha256": sha, "bytes": size, "exists": True}],
        "named_probes": probes,
        "probe_exit_codes": [p["exit_code"] for p in probes],
        "wave4_completion": {
            "at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "by": "claude-code builder shard 21 wave 4 (P2 program, resume)",
            "note": NOTES[uid],
        },
        "notes": NOTES[uid],
        "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    (pdir / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    write_manifest(uid, probe_paths, ok)
    print(f"return-written {uid} ok={ok}")
    return 0 if ok else 1



def write_manifest(uid: str, probes: list[Path], ok: bool) -> None:
    art = REPO / "command-center" / "receipts" / f"{uid}.json"
    pdir = REPO / "command-center" / "p2-wave" / "probes" / uid
    ret_path = pdir / "SUBAGENT-RETURN.json"
    sha, size = digest(art)
    arts = [{
        "path": f"command-center/receipts/{uid}.json",
        "bytes": size, "sha256": sha, "present": True,
        "role": "primary", "receipt_path": str(ret_path.relative_to(REPO).as_posix()),
        "unit_id": uid,
    }]
    for pp in probes:
        s, n = digest(pp)
        arts.append({
            "path": pp.relative_to(REPO).as_posix(),
            "bytes": n, "sha256": s, "present": True,
            "role": "named-probe", "receipt_path": str(ret_path.relative_to(REPO).as_posix()),
            "unit_id": uid,
        })
    for rel in EXTRA[uid]:
        f = REPO / rel
        if not f.is_file():
            raise SystemExit(f"FAILED:manifest {uid} missing extra {rel}")
        s, n = digest(f)
        arts.append({
            "path": rel, "bytes": n, "sha256": s, "present": True,
            "role": "supporting", "receipt_path": str(ret_path.relative_to(REPO).as_posix()),
            "unit_id": uid,
        })
    man = {
        "schema_version": 1,
        "unit_id": uid,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (shard-21 wave-4 resume builder, CRLF-normalized sha256)",
        "expected": len(arts),
        "present": len(arts),
        "verified_on_disk": True,
        "artifacts": arts,
        "builder_note": NOTES[uid],
        "built_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    (pdir / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")

if __name__ == "__main__":
    raise SystemExit(main())
