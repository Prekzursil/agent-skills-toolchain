#!/usr/bin/env python3
"""TST-0168 live-target refute sweep (shard17-w4).

Re-runs the receipt's race amplification against the LIVE B07 target
tools/lib/handled-ledger.mjs via live_ledger_refute.mjs:
  * both-states: suspend before the fan-out (cut 0) and after completion
  * race amplification: 20 randomized in-flight cut points (seeded), each a
    real process death (exit 137) followed by a resume process
  * chaos: 5 randomized SIGKILL-time kills mid-walk, then resume
  * mutant control: ignore-handled resume must double-execute (the exactly-once
    detector is load-bearing)
The archived-proxy refutation (receipt-before-ledger window, 3/20 cuts) is
preserved in the receipt as history; this sweep measures the live target,
where the child receipt is the markHandled meta - one atomic write, no window.
"""
from __future__ import annotations
import json
import random
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
DRIVER = HERE / "live_ledger_refute.mjs"
RAW = HERE / "live-ledger-refute.raw.txt"
N = 24
SEED = 0x168CAFE


def run(args, timeout=120):
    p = subprocess.run(["node", str(DRIVER)] + args, capture_output=True, text=True, timeout=timeout)
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def verify(sd):
    rc, out = run(["--mode", "verify", "--state-dir", str(sd)])
    if rc != 0:
        return {"verify_rc": rc, "exactly_once": False, "error": out[-300:]}
    return json.loads(out)


def one_cut(root, name, cut, kill_after=None, mutant_resume=False):
    sd = root / name
    if kill_after is None:
        rc, _ = run(["--mode", "dispatcher", "--state-dir", str(sd), "--cut", str(cut)])
    else:
        rc, _ = run(["--mode", "dispatcher", "--state-dir", str(sd),
                     "--kill-after-ms", str(kill_after)])
    resume_rc, _ = run(["--mode", "dispatcher", "--state-dir", str(sd)] +
                       (["--mutant-ignore-handled"] if mutant_resume else []))
    row = verify(sd)
    row.update({"case": name, "suspend_rc": rc, "resume_rc": resume_rc})
    return row


def main() -> int:
    rng = random.Random(SEED)
    results = {"unit": "TST-0168", "probe": "live-ledger-race-sweep", "seed": SEED,
               "target": "tools/lib/handled-ledger.mjs", "children_per_case": N}

    with tempfile.TemporaryDirectory(prefix="tst0168-live-") as td:
        root = Path(td)

        b0 = one_cut(root, "both-states-before", 0)
        bfull = one_cut(root, "both-states-after", N)
        both_ok = b0["exactly_once"] and bfull["exactly_once"]

        race = []
        for k in range(20):
            cut = rng.randrange(0, 2 * N)
            race.append(one_cut(root, f"race-{k:02d}", cut))
        race_ok = all(r["exactly_once"] for r in race)

        chaos = []
        for k in range(5):
            chaos.append(one_cut(root, f"chaos-{k:02d}", None, kill_after=rng.randrange(2, 40)))
        chaos_ok = all(r["exactly_once"] for r in chaos)

        # Mutant arms need PRIOR progress: an ignore-handled resume over an
        # empty ledger executes each child once and is indistinguishable from
        # honest. Partial (cut 10) and fully-completed (cut N) priors both
        # force the mutant to re-execute handled children (runs increments).
        mut0 = one_cut(root, "mutant-00", 10, mutant_resume=True)
        mut1 = one_cut(root, "mutant-01", N, mutant_resume=True)
        mutant_fails = [m for m in (mut0, mut1) if not m["exactly_once"]]

    results.update({
        "both_states": {"before": b0, "after": bfull, "pass": both_ok},
        "race_amplification": {"points": 20, "events": [r.get("case") and None or None for r in []] or
                               [json.loads(json.dumps(r)) for r in race],
                               "exactly_once_all": race_ok},
        "chaos_kills": {"trials": 5, "rows": chaos, "exactly_once_all": chaos_ok},
        "mutant_control": {"rows": [mut0, mut1], "detector_fired_all": len(mutant_fails) == 2},
        "single_writer_caveat": "markHandled is read-modify-write; the fan-out shape has ONE dispatcher per state-dir, the discipline the live module documents as safe.",
        "pass": bool(both_ok and race_ok and chaos_ok and len(mutant_fails) == 2),
    })
    RAW.write_text(json.dumps(results, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({k: results[k] for k in
                      ("probe", "pass", "single_writer_caveat")}, sort_keys=True))
    print(f"both_states={both_ok} race20={race_ok} chaos5={chaos_ok} mutant_fired={len(mutant_fails)}/2")
    print(f"SUCCESS:TST-0168-live-refute live target exactly-once under 20 cuts + 5 chaos kills; mutant detector fired" if results["pass"]
          else f"FAILED:TST-0168-live-refute")
    return 0 if results["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
