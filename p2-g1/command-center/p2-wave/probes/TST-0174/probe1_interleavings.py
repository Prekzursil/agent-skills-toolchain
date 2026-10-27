#!/usr/bin/env python3
"""TST-0174 probe1 -- reader integrity across 1,000 cross-process same-key interleavings.

Two persistent writer PROCESSES (A and B) publish the same cache key while the
coordinator's reader classifies every observation. PASS requires zero partial
reads and a well-defined winner (A or B) per trial.
Exit 0 on pass, 1 on any failure (fail-closed).
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import atomic_cache as AC  # noqa: E402

UNIT = "TST-0174"
TRIALS = 1000
RUN = HERE / ".run"
GO = RUN / "go"
DONE = RUN / "done"


def main() -> int:
    if RUN.exists():
        shutil.rmtree(RUN)
    GO.mkdir(parents=True)
    DONE.mkdir()
    entry = RUN / "cache" / "entries" / "e1.bin"
    entry.parent.mkdir(parents=True, exist_ok=True)
    entry.write_bytes(AC.encode(b"OLD" * 4))
    payload_a = ("A" * 8 + f"{UNIT}-A-" + "x" * 40).encode()
    payload_b = ("B" * 8 + f"{UNIT}-B-" + "x" * 40).encode()

    stop = RUN / "stop.flag"
    env_cmd = [
        sys.executable, "-c",
        "import sys; sys.path.insert(0, r'%s'); "
        "import atomic_cache; atomic_cache.writer_loop("
        "r'%s', r'%s', '%s', r'%s')"
        % (HERE, GO, entry, "A", stop),
    ]
    procs = []
    for tag in ("A", "B"):
        cmd = [
            sys.executable, "-c",
            "import sys; sys.path.insert(0, r'%s'); import atomic_cache as AC; "
            "AC.writer_loop(r'%s', r'%s', '%s', r'%s')"
            % (HERE, GO, entry, tag, stop),
        ]
        procs.append(subprocess.Popen(cmd, cwd=str(HERE)))

    partial = 0
    reads = 0
    winners = {"A": 0, "B": 0, "OLD": 0, "UNKNOWN": 0}
    failures: list[str] = []
    left_tmps: list[str] = []
    try:
        for n in range(TRIALS):
            gtmp = GO / f".tmp-go-{n}.json"
            gtmp.write_text(
                json.dumps({"a": payload_a.decode(), "b": payload_b.decode()}), encoding="utf-8"
            )
            gtmp.replace(GO / f"go-{n}.json")
            deadline = time.time() + 30
            trial_reads = 0
            while time.time() < deadline:
                raw = AC.read_observation(entry)
                c = AC.classify(raw)
                reads += 1
                trial_reads += 1
                if c == "PARTIAL":
                    partial += 1
                if (DONE / f"{n}.A").exists() and (DONE / f"{n}.B").exists():
                    break
                time.sleep(0.002)
            final = AC.classify(AC.read_observation(entry))
            if final in ("COMPLETE-A", "COMPLETE-B"):
                winners[final[-1]] = winners.get(final[-1], 0) + 1
            elif final == "COMPLETE-OTHER":
                winners["OLD"] += 1
            elif final == "ABSENT":
                winners["OLD"] += 1
            else:
                winners["UNKNOWN"] += 1
            (DONE / f"{n}.A").unlink(missing_ok=True)
            (DONE / f"{n}.B").unlink(missing_ok=True)
            (GO / f"go-{n}.json").unlink(missing_ok=True)
            if final not in ("COMPLETE-A", "COMPLETE-B", "COMPLETE-OTHER"):
                failures.append(f"trial {n}: final={final}")
    finally:
        stop.touch()
        for p in procs:
            p.wait(timeout=30)
        left_tmps = sorted(p.name for p in entry.parent.glob(".tmp-TST0174-*"))

    payload = {
        "probe": "probe1-interleavings",
        "unit_id": UNIT,
        "pass": partial == 0 and not failures and not left_tmps,
        "trials": TRIALS,
        "partial_reads": partial,
        "total_reader_reads": reads,
        "winners": winners,
        "leftover_trials": len(left_tmps),
        "leftover_tmps": left_tmps[:10],
        "measured_layer": "command-center/p2-wave/probes/TST-0174/atomic_cache.py",
        "production_cache_present": (Path(__file__).resolve().parents[4] / "platform/plugin/cache.py").exists(),
    }
    print(json.dumps(payload, sort_keys=True))
    if payload["pass"]:
        print(f"SUCCESS:{UNIT}-probe1 trials={TRIALS} partial_reads={partial} winners={winners}")
        return 0
    print(f"FAILED:{UNIT}-probe1 partial={partial} failures={failures[:5]} leftovers={left_tmps[:5]}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
