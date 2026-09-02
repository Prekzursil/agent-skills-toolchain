#!/usr/bin/env python3
"""Live cancel-during-render harness for TST-0156.

Signal (a): reader-side parse of the dest cache after every trial.
Signal (b): directory scan for leftover tmp files after scavenge.
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import cache_publish as CP  # noqa: E402

UNIT = "TST-0156"
CANCEL_N = 200
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0156/probe1_cancel_atomic.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0156/probe2_mutation.py"
)
OUT_REL = "command-center/receipts/TST-0156.json"
WRITER = HERE / "cache_publish.py"
PY = sys.executable


def make_payloads() -> tuple[bytes, bytes, int]:
    old_body = (b"OLD-PANEL-v1:" + os.urandom(32) + b":") * 80
    new_body = (b"NEW-PANEL-v2:" + os.urandom(32) + b":") * 80
    old = CP.encode_cache(1, old_body)
    new = CP.encode_cache(2, new_body)
    hold = min(len(old), len(new)) // 3
    if hold < 64:
        raise RuntimeError("payload too small to split")
    return old, new, hold


def _wait_ready(ready: Path, proc: subprocess.Popen, timeout: float = 60.0) -> None:
    # 60s not 5s: the measurement host runs under heavy memory pressure and a
    # Python subprocess can take >5s just to start. The writer must still
    # signal ready; we only wait longer before declaring it hung.
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if ready.is_file():
            return
        if proc.poll() is not None:
            err = (proc.stderr.read() if proc.stderr else b"") or b""
            raise RuntimeError(
                f"writer exited {proc.returncode} before ready: {err[-400:]!r}"
            )
        time.sleep(0.002)
    raise TimeoutError(f"writer pid={proc.pid} never signalled ready")


def spawn_writer(
    dest: Path,
    payload_file: Path,
    mode: str,
    hold: int,
    ready: Path,
    go: Path,
) -> subprocess.Popen:
    for path in (ready, go):
        if path.exists():
            path.unlink()
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
    return subprocess.Popen(
        [
            PY,
            "-B",
            str(WRITER),
            "--dest",
            str(dest),
            "--payload",
            str(payload_file),
            "--mode",
            mode,
            "--hold-after-bytes",
            str(hold),
            "--ready",
            str(ready),
            "--go",
            str(go),
        ],
        cwd=str(REPO),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
    )


def kill_writer(proc: subprocess.Popen) -> None:
    if proc.poll() is None:
        proc.kill()
        try:
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            os.kill(proc.pid, 9)
            proc.wait(timeout=3)


def seed_old(dest: Path, old: bytes) -> None:
    CP.publish_atomic(dest, old)
    verdict, _, parsed = CP.read_dest(dest)
    if verdict != "COMPLETE" or int(parsed.get("seq") or 0) != 1:
        raise RuntimeError(f"seed failed verdict={verdict}")


def trial_cancel(
    dest: Path,
    cache_dir: Path,
    payload_file: Path,
    mode: str,
    hold: int,
    ctl: Path,
) -> dict:
    ready = ctl / "ready"
    go = ctl / "go"
    proc = spawn_writer(dest, payload_file, mode, hold, ready, go)
    _wait_ready(ready, proc)
    # Mid-write: dest under atomic must still be the seeded complete object.
    mid_verdict, mid_n, _ = CP.read_dest(dest)
    kill_writer(proc)
    after_verdict, after_n, parsed = CP.read_dest(dest)
    orphans_before = CP.scan_orphans(cache_dir, dest)
    removed = CP.scavenge_orphans(cache_dir, dest)
    orphans_after = CP.scan_orphans(cache_dir, dest)
    seq = None if not parsed else parsed.get("seq")
    return {
        "mode": mode,
        "mid_verdict": mid_verdict,
        "mid_bytes": mid_n,
        "after_verdict": after_verdict,
        "after_bytes": after_n,
        "after_seq": seq,
        "orphans_before_scavenge": orphans_before,
        "orphans_removed": removed,
        "orphans_after_scavenge": orphans_after,
        "writer_returncode": proc.returncode,
    }


def trial_uncancelled(
    dest: Path,
    payload_file: Path,
    mode: str,
    hold: int,
    ctl: Path,
) -> dict:
    ready = ctl / "ready"
    go = ctl / "go"
    proc = spawn_writer(dest, payload_file, mode, hold, ready, go)
    _wait_ready(ready, proc)
    go.write_text("go\n", encoding="utf-8")
    rc = proc.wait(timeout=8)
    verdict, n, parsed = CP.read_dest(dest)
    return {
        "mode": mode,
        "rc": rc,
        "verdict": verdict,
        "bytes": n,
        "seq": None if not parsed else parsed.get("seq"),
    }


def run_campaign(cancel_n: int = CANCEL_N, include_direct: bool = True) -> dict:
    old, new, hold = make_payloads()
    with tempfile.TemporaryDirectory(prefix="tst0156-") as tmp:
        root = Path(tmp)
        cache_dir = root / "cache"
        ctl = root / "ctl"
        cache_dir.mkdir()
        ctl.mkdir()
        dest = cache_dir / CP.CACHE_NAME
        payload_file = root / "new.bin"
        payload_file.write_bytes(new)

        seed_old(dest, old)
        uncancelled = trial_uncancelled(dest, payload_file, "atomic", hold, ctl)
        if uncancelled["rc"] != 0 or uncancelled["verdict"] != "COMPLETE":
            raise RuntimeError(f"uncancelled atomic failed: {uncancelled}")
        if uncancelled["seq"] != 2:
            raise RuntimeError(f"uncancelled did not publish seq=2: {uncancelled}")

        seed_old(dest, old)
        atomic_rows = []
        for i in range(cancel_n):
            seed_old(dest, old)
            row = trial_cancel(dest, cache_dir, payload_file, "atomic", hold, ctl)
            row["i"] = i
            atomic_rows.append(row)

        seed_old(dest, old)
        direct_rows = []
        if include_direct:
            for i in range(cancel_n):
                seed_old(dest, old)
                row = trial_cancel(dest, cache_dir, payload_file, "direct", hold, ctl)
                row["i"] = i
                direct_rows.append(row)

        def tally(rows: list[dict]) -> dict:
            after = [r["after_verdict"] for r in rows]
            mid = [r["mid_verdict"] for r in rows]
            return {
                "n": len(rows),
                "after_complete": after.count("COMPLETE"),
                "after_partial": after.count("PARTIAL"),
                "after_absent": after.count("ABSENT"),
                "mid_complete": mid.count("COMPLETE"),
                "mid_partial": mid.count("PARTIAL"),
                "mid_absent": mid.count("ABSENT"),
                "mid_complete_seq1": sum(
                    1
                    for r in rows
                    if r["mid_verdict"] == "COMPLETE" and r["after_seq"] in (1, None)
                    or (r["after_verdict"] == "COMPLETE" and r["after_seq"] == 1)
                ),
                "after_complete_still_old": sum(
                    1 for r in rows if r["after_verdict"] == "COMPLETE" and r["after_seq"] == 1
                ),
                "orphans_seen_before_scavenge": sum(
                    1 for r in rows if r["orphans_before_scavenge"]
                ),
                "orphans_remaining": sum(len(r["orphans_after_scavenge"]) for r in rows),
                "killed": sum(
                    1 for r in rows if r["writer_returncode"] not in (0, None)
                ),
            }

        atomic_t = tally(atomic_rows)
        direct_t = tally(direct_rows)
        # Atomic: every post-cancel dest must be COMPLETE old (seq 1), never PARTIAL.
        atomic_ok = (
            atomic_t["n"] == cancel_n
            and atomic_t["after_partial"] == 0
            and atomic_t["after_complete_still_old"] == cancel_n
            and atomic_t["mid_partial"] == 0
            and atomic_t["orphans_remaining"] == 0
        )
        # Mutation: in-place write must expose PARTIAL after cancel.
        if include_direct:
            mutation_ok = (
                direct_t["n"] == cancel_n
                and direct_t["after_partial"] == cancel_n
            )
        else:
            mutation_ok = None
        uncancelled_ok = (
            uncancelled["verdict"] == "COMPLETE" and uncancelled["seq"] == 2
        )
        passed = bool(atomic_ok and uncancelled_ok and (mutation_ok is not False))
        return {
            "unit_id": UNIT,
            "cancel_n": cancel_n,
            "hold_after_bytes": hold,
            "old_bytes": len(old),
            "new_bytes": len(new),
            "production_publisher": CP.production_publisher(),
            "sut": "command-center/p2-wave/probes/TST-0156/cache_publish.py",
            "publish_symbol": "publish_atomic",
            "mutation_symbol": "publish_direct / writer --mode direct",
            "uncancelled": uncancelled,
            "uncancelled_ok": uncancelled_ok,
            "atomic": atomic_t,
            "direct": direct_t,
            "atomic_ok": atomic_ok,
            "mutation_ok": mutation_ok,
            "include_direct": include_direct,
            "pass": passed,
        }


def assert_pass(report: dict) -> None:
    if not report.get("pass"):
        raise RuntimeError(f"campaign failed: {report}")


if __name__ == "__main__":
    doc = run_campaign()
    print(doc)
    raise SystemExit(0 if doc["pass"] else 1)
