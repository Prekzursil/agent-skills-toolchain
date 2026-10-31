#!/usr/bin/env python3
"""TST-0174 probe2 -- mutation control + leftover-temps inspection (fail-closed).

Two ISOLATED phases (each with its own entry file, go/done dirs and writer
pair, serially joined per trial like probe1):

* Phase A, mutation control: the atomic publish is removed (in-place overwrite
  with a torn-write window). The reader MUST observe partial entries - a
  detector silent on the broken state would measure nothing. Additional
  in-place rounds run (bounded) until the detector fires.
* Phase B, atomic control: the production-shaped tmp+os.replace publish. The
  reader MUST observe zero partials, and the cache parent must hold no
  leftover .tmp-TST0174-* files after the writers join.

Exit 0 on pass, 1 on any failure.
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


def run_phase(base: Path, mode: str, n_trials: int, pa: bytes, pb: bytes, reader_sleep: float):
    """One isolated phase: returns (partial_reads, trials_run, leftover_tmps)."""
    go = base / "go"
    done = base / "done"
    go.mkdir(parents=True)
    done.mkdir()
    entry = base / "cache" / "e.bin"
    entry.parent.mkdir(parents=True)
    entry.write_bytes(AC.encode(b"OLD" * 4))
    stop = base / "stop.flag"
    procs = []
    for tag in ("A", "B"):
        cmd = [
            sys.executable, "-c",
            "import sys; sys.path.insert(0, r'%s'); import atomic_cache as AC; "
            "AC.writer_loop(r'%s', r'%s', '%s', r'%s')"
            % (HERE, go, entry, tag, stop),
        ]
        procs.append(subprocess.Popen(cmd, cwd=str(HERE)))

    partial = 0
    trials = 0
    try:
        n = 0
        while n < n_trials:
            gtmp = go / (".tmp-go-%d.json" % n)
            gtmp.write_text(
                json.dumps({"a": pa.decode(), "b": pb.decode(), "mode": mode}),
                encoding="utf-8",
            )
            gtmp.replace(go / ("go-%d.json" % n))
            deadline = time.time() + 30
            while time.time() < deadline:
                if AC.classify(AC.read_observation(entry)) == "PARTIAL":
                    partial += 1
                if (done / ("%d.A" % n)).exists() and (done / ("%d.B" % n)).exists():
                    break
                time.sleep(reader_sleep)
            trials += 1
            n += 1
            if mode == "inplace" and partial > 0:
                break  # detector has fired; no more rounds needed
    finally:
        stop.touch()
        for p in procs:
            try:
                p.wait(timeout=30)
            except subprocess.TimeoutExpired:
                p.kill()
        for g in go.glob("go-*.json"):
            g.unlink(missing_ok=True)
    leftovers = sorted(p.name for p in entry.parent.glob(".tmp-TST0174-*"))
    return partial, trials, leftovers


def main() -> int:
    base = HERE / ".run-mut"
    if base.exists():
        shutil.rmtree(base)
    pa = (b"A" * 8 + UNIT.encode() + b"-A-" + b"x" * 32)
    pb = (b"B" * 8 + UNIT.encode() + b"-B-" + b"x" * 32)

    # Phase A: mutation (atomic publish removed)
    a_base = base / "mutation"
    mut_partials, mut_trials, mut_left = run_phase(
        a_base, "inplace", n_trials=12, pa=pa, pb=pb, reader_sleep=0.001
    )
    detector_red = mut_partials > 0

    # Phase B: atomic control on a separate entry/writer pair
    b_base = base / "atomic"
    atom_partials, atom_trials, atom_left = run_phase(
        b_base, "atomic", n_trials=30, pa=pa, pb=pb, reader_sleep=0.001
    )
    atomic_clean = atom_partials == 0

    left_ok = not mut_left and not atom_left

    payload = {
        "probe": "probe2-mutation-temps",
        "unit_id": UNIT,
        "pass": detector_red and atomic_clean and left_ok,
        "mutation": {
            "known_broken": "inplace_publish (atomic replace removed)",
            "partial_reads": mut_partials,
            "trials_run": mut_trials,
            "detector_red": detector_red,
        },
        "atomic_control": {
            "partial_reads": atom_partials,
            "trials_run": atom_trials,
            "clean": atomic_clean,
        },
        "leftover_inspection": {
            "signal": "directory scans of both phase cache parents after writers join",
            "mutation_leftovers": mut_left,
            "atomic_leftovers": atom_left,
            "pass": left_ok,
        },
        "both_states": {
            "inplace_partial_reads_appear": detector_red,
            "atomic_publish_no_partials_no_leftovers": atomic_clean and left_ok,
        },
        "design_note": "isolated phases (separate entry files + writer pairs) prevent cross-mode contamination; serial join per trial prevents writer run-ahead",
    }
    print(json.dumps(payload, sort_keys=True))
    if payload["pass"]:
        print("SUCCESS:%s-probe2 mut_partials=%d atom_partials=%d leftovers=[]"
              % (UNIT, mut_partials, atom_partials))
        return 0
    print("FAILED:%s-probe2 mut=%d atom=%d left_mut=%s left_atom=%s"
          % (UNIT, mut_partials, atom_partials, mut_left, atom_left))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
