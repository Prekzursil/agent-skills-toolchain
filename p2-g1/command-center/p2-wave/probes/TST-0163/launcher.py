#!/usr/bin/env python3
"""Fan-out launcher: spec hash at dispatch, CONTRACT-DRIFT at fan-in.

Catalog TST-0163: if the launcher or unit spec is edited after launch, fan-in
must detect that units ran under different contracts. PASS requires a spec
hash recorded at dispatch and compared at fan-in, with a typed CONTRACT-DRIFT
result naming the two hashes.

Regression seed: a mid-run edit of tool_call_cap that left contradictory
caps live when fan-in used last-write-wins (only the last dispatch hash
compared to the current file).

Modes:
  detect=True  (fixed)  — every unit's recorded dispatch hash is compared to
                          the current spec hash recomputed by a *separate*
                          process. Any mismatch is CONTRACT-DRIFT.
  detect=False (naive)  — last-write-wins: only the most recently dispatched
                          unit is compared, in-process. Early units that ran
                          under the old cap are invisible; contradictory
                          tool_call_cap values stay live.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Literal

HERE = Path(__file__).resolve().parent
HASHER = HERE / "hash_spec.py"
CompareMode = Literal["per-unit", "last-write-wins"]


def digest_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def digest_path(path: Path) -> str:
    return digest_bytes(path.read_bytes())


def independent_digest(path: Path) -> tuple[str, int]:
    """Recompute the spec hash in a child process (evidence signal b)."""
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run(
        [sys.executable, "-B", str(HASHER), str(path)],
        capture_output=True,
        text=True,
        env=env,
        check=False,
        timeout=30,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"hash_spec.py rc={proc.returncode} stderr={(proc.stderr or '')[-500:]}"
        )
    digest = (proc.stdout or "").strip().splitlines()[-1].strip()
    if len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
        raise RuntimeError(f"hash_spec.py produced non-sha256: {digest!r}")
    pid = os.getpid()
    for line in (proc.stderr or "").splitlines():
        if line.startswith("pid="):
            try:
                pid = int(line.split("=", 1)[1])
            except ValueError:
                pass
    return digest, pid


class FanOutLauncher:
    def __init__(
        self,
        spec_path: Path,
        *,
        detect: bool = True,
    ) -> None:
        self.spec_path = Path(spec_path)
        self.detect = detect
        self.compare_mode: CompareMode = "per-unit" if detect else "last-write-wins"
        self.records: list[dict[str, Any]] = []
        self.launcher_pid = os.getpid()

    def _read_raw(self) -> bytes:
        return self.spec_path.read_bytes().replace(b"\r\n", b"\n")

    def dispatch(self, unit_id: str) -> dict[str, Any]:
        raw = self._read_raw()
        text = raw.decode("utf-8")
        spec = json.loads(text)
        rec = {
            "unit_id": unit_id,
            "dispatch_hash": digest_bytes(raw),
            "dispatch_spec_text": text,
            "tool_call_cap": spec["tool_call_cap"],
            "spec_path": str(self.spec_path),
            "dispatch_pid": os.getpid(),
        }
        self.records.append(rec)
        return dict(rec)

    def fan_in(self) -> dict[str, Any]:
        if not self.records:
            raise RuntimeError("fan-in with empty dispatch log")
        current_raw = self._read_raw()
        current_spec = json.loads(current_raw.decode("utf-8"))
        current_cap = current_spec["tool_call_cap"]
        hasher_pid: int | None
        if self.detect:
            fanin_hash, hasher_pid = independent_digest(self.spec_path)
            if hasher_pid == self.launcher_pid:
                raise RuntimeError(
                    "fan-in hasher pid equals launcher pid; hash was not independent"
                )
        else:
            fanin_hash = digest_bytes(current_raw)
            hasher_pid = self.launcher_pid

        if self.compare_mode == "last-write-wins":
            compared = [self.records[-1]]
        else:
            compared = list(self.records)

        drifted: list[dict[str, Any]] = []
        for rec in compared:
            if rec["dispatch_hash"] != fanin_hash:
                drifted.append(
                    {
                        "kind": "CONTRACT-DRIFT",
                        "unit_id": rec["unit_id"],
                        "dispatch_hash": rec["dispatch_hash"],
                        "fanin_hash": fanin_hash,
                        "dispatch_tool_call_cap": rec["tool_call_cap"],
                        "fanin_tool_call_cap": current_cap,
                    }
                )

        caps_observed = sorted({int(r["tool_call_cap"]) for r in self.records})
        contradictory = len(caps_observed) > 1
        dispatch_named = (
            drifted[0]["dispatch_hash"] if drifted else self.records[0]["dispatch_hash"]
        )
        result = "CONTRACT-DRIFT" if drifted else "OK"
        return {
            "result": result,
            "detect": self.detect,
            "compare_mode": self.compare_mode,
            "fanin_hash": fanin_hash,
            "fanin_process": (
                "independent-subprocess" if self.detect else "in-process-last-write-wins"
            ),
            "launcher_pid": self.launcher_pid,
            "fanin_hasher_pid": hasher_pid,
            "pids_distinct": hasher_pid != self.launcher_pid,
            "drifted_units": drifted,
            "named_hashes": {
                "dispatch": dispatch_named,
                "fanin": fanin_hash,
            },
            "hashes_named_and_unequal": bool(
                drifted
                and drifted[0]["dispatch_hash"] != drifted[0]["fanin_hash"]
            ),
            "contradictory_caps_live": contradictory,
            "caps_observed": caps_observed,
            "current_cap": current_cap,
            "n_dispatched": len(self.records),
            "n_compared": len(compared),
            "n_drifted": len(drifted),
            "records": [
                {
                    "unit_id": r["unit_id"],
                    "dispatch_hash": r["dispatch_hash"],
                    "tool_call_cap": r["tool_call_cap"],
                    "dispatch_spec_text": r["dispatch_spec_text"],
                }
                for r in self.records
            ],
        }
