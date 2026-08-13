"""BUILD-R2 instrument: per-gate WALL TIME, tagged with the WORLD it was measured in.

WHY THIS EXISTS.  BUILD-R1 shipped a gate table with a `wall` column and no instrument
behind it.  The numbers were real -- they are all in committed receipts -- but the column
silently MERGED TWO ENVIRONMENTS:

    _b3_portability.win-bare-nohome.json   HOME redirected to an empty temp dir (runner world)
        rule_audit --self-test 1.2 | r2_pathrefs --self-test 2.8 | r2_control_count 1.6
        r2_failclosed 3.1 | r4_receipt_argv 0.5 | r4_credential 0.2 | rule_audit bare 1.3
        | lazy_predict 0.7 | r2_pathrefs bare 3.3
    _b2_slowgate_probe.json                real HOME (this box)
        r2_pathrefs bare 110.5 | r3_corpus_parity 89.0

Eight rows of the R1 table came from the first file and two from the second, in one column
with no world label.  An adversarial verifier then measured `r2_pathrefs --self-test` at
235.4 / 124.8 / 116.1 s with a real HOME and REFUTED the 2.8 s cell.  The verifier is right
about the number and the R1 table is wrong about its scope.

So this instrument measures BOTH worlds with ONE clock, writes a receipt, and asserts the
self-consistency the R1 table lacked: the sum of the per-gate parts must be within tolerance
of the timed whole.  A part-sum that cannot account for the whole is a detector failure, not
a finding.

It also pins the MECHANISM rather than arguing about it: `r2_pathrefs.in_claude_home()` walks
seven `~/.claude` subtrees per DISTINCT unresolved basename with no shared index, so the cost
is (number of absent names) x (a full recursive walk of the live tree).  With HOME redirected
those roots do not exist, every walk short-circuits, and the same self-test is seconds.  That
is the whole 2.8-vs-116 delta, and it is measured below, not asserted.

Read-only.  Writes only its own JSON receipt, incrementally, so a kill leaves truth on disk.

Run::

    python docs/rule-audit/_b10_gate_timing.py --tag before
    python docs/rule-audit/_b10_gate_timing.py --tag after     (after any speed change)
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
TIMEOUT_SEC = 900

# Exactly the six invocations ci_gate.CI_PLAN runs, in its order.
PLAN: list[tuple[str, list[str], int]] = [
    ("rule_audit.py", ["--self-test"], 0),
    ("r2_pathrefs.py", ["--self-test"], 0),
    ("r2_control_count_gate.py", [], 0),
    ("r2_failclosed_mutation.py", [], 0),
    ("r4_receipt_argv_gate.py", [], 0),
    ("r4_credential_rule_gate.py", [], 1),
]


def marker_of(stdout: str) -> str:
    # Deliberately a second copy of _b3_portability.marker_of (the dup-guard hook flagged it).
    # Importing _b3 would make a BUILD-R2 instrument depend on a BUILD-R1 one-shot probe that
    # ci_gate.EXCLUDED explicitly says must never run per PR; a five-line marker reader is not
    # worth that coupling. Same convention ci_gate's docstring records for the two lane gates.
    lines = [ln for ln in stdout.splitlines() if ln.strip()]
    for line in reversed(lines):
        if line.startswith(("SUCCESS:", "FAILED:")):
            return line.strip()[:160]
    return lines[-1].strip()[:160] if lines else "<no stdout>"


def spawn(argv: list[str], env: dict[str, str] | None) -> dict[str, object]:
    started = time.monotonic()
    rec: dict[str, object] = {"argv": argv}
    try:
        proc = subprocess.run(
            [sys.executable, *argv],
            cwd=str(REPO),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=TIMEOUT_SEC,
            env=env,
        )
        rec["rc"] = proc.returncode
        rec["marker"] = marker_of(proc.stdout)
    except subprocess.TimeoutExpired:
        rec["rc"] = None
        rec["marker"] = f"<timeout {TIMEOUT_SEC}s>"
    rec["wall_sec"] = round(time.monotonic() - started, 1)
    return rec


def empty_home_env() -> tuple[str, dict[str, str]]:
    """The _b3_portability.py recipe, reused verbatim so the two receipts are comparable."""
    fake = tempfile.mkdtemp(prefix="rule-audit-b10-nohome-")
    env = dict(os.environ)
    env["HOME"] = fake
    env["USERPROFILE"] = fake
    env["PYTHONIOENCODING"] = "utf-8"
    for stale in ("HOMEDRIVE", "HOMEPATH"):
        env.pop(stale, None)
    return fake, env


def mechanism() -> dict[str, object]:
    """In-process, real HOME: where does r2_pathrefs actually spend the time?"""
    sys.path.insert(0, str(HERE))
    import r2_pathrefs as rp  # noqa: PLC0415  (deliberate: after sys.path is set)

    out: dict[str, object] = {"home": str(rp.HOME)}

    t0 = time.monotonic()
    index = rp.basename_index()
    out["basename_index_sec"] = round(time.monotonic() - t0, 2)
    out["basename_index_distinct_names"] = len(index)
    out["basename_index_files"] = sum(index.values())

    # Per-subdir cost of ONE absent-name lookup: this is the loop that has no shared index.
    per_dir: list[dict[str, object]] = []
    total = 0.0
    for sub in rp.HOME_SEARCH_DIRS:
        root = rp.HOME / ".claude" / sub
        t0 = time.monotonic()
        n = 0
        if root.is_dir():
            for _ in root.rglob("__b10_absent_name__.zzz"):
                n += 1
        dt = time.monotonic() - t0
        total += dt
        per_dir.append(
            {"dir": sub, "exists": root.is_dir(), "sec": round(dt, 2), "hits": n}
        )
    out["home_walk_per_dir"] = per_dir
    out["home_walk_one_absent_name_sec"] = round(total, 2)

    t0 = time.monotonic()
    rp.in_claude_home("__b10_definitely_absent__.zzz")
    out["in_claude_home_absent_sec"] = round(time.monotonic() - t0, 2)

    t0 = time.monotonic()
    found = rp.in_claude_home("windows-shell.md")
    out["in_claude_home_present_sec"] = round(time.monotonic() - t0, 2)
    out["in_claude_home_present_result"] = found
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", required=True)
    ap.add_argument("--reps", type=int, default=2)
    args = ap.parse_args()

    receipt: dict[str, object] = {
        "tag": args.tag,
        "platform": platform.system(),
        "python": sys.version.split()[0],
        "note": "SKELETON - nothing measured yet",
    }
    dest = HERE / f"_b10_gate_timing.{args.tag}.json"

    def flush() -> None:
        dest.write_text(
            json.dumps(receipt, indent=1) + "\n", encoding="utf-8", newline="\n"
        )

    flush()

    # -- 1. the refuted cell, both worlds, same clock -------------------------------------
    real_runs = []
    for i in range(args.reps):
        rec = spawn([str(HERE / "r2_pathrefs.py"), "--self-test"], None)
        print(
            f"real-HOME  r2_pathrefs --self-test #{i + 1}: {rec['wall_sec']}s rc={rec['rc']}",
            flush=True,
        )
        real_runs.append(rec)
        receipt["pathrefs_selftest_real_home"] = real_runs
        receipt["note"] = "PARTIAL - real-HOME self-test measured"
        flush()

    fake, env = empty_home_env()
    nohome_runs = []
    for i in range(args.reps):
        rec = spawn([str(HERE / "r2_pathrefs.py"), "--self-test"], env)
        print(
            f"no-HOME    r2_pathrefs --self-test #{i + 1}: {rec['wall_sec']}s rc={rec['rc']}",
            flush=True,
        )
        nohome_runs.append(rec)
        receipt["pathrefs_selftest_no_home"] = nohome_runs
        receipt["no_home_dir"] = fake
        flush()

    # -- 2. mechanism --------------------------------------------------------------------
    receipt["mechanism_real_home"] = mechanism()
    receipt["note"] = "PARTIAL - mechanism measured"
    flush()
    print(f"mechanism: {json.dumps(receipt['mechanism_real_home'])[:300]}", flush=True)

    # -- 3. parts and whole, real HOME ---------------------------------------------------
    parts = []
    for name, argv, expect in PLAN:
        rec = spawn([str(HERE / name), *argv], None)
        rec["label"] = f"{name} {' '.join(argv)}".strip()
        rec["expect"] = expect
        rec["rc_as_expected"] = rec["rc"] == expect
        print(
            f"part  {rec['label']:38} {rec['wall_sec']:>7}s rc={rec['rc']}", flush=True
        )
        parts.append(rec)
        receipt["ci_plan_parts_real_home"] = parts
        flush()

    whole = spawn([str(HERE / "ci_gate.py")], None)
    print(f"whole ci_gate.py: {whole['wall_sec']}s rc={whole['rc']}", flush=True)
    receipt["ci_gate_whole_real_home"] = whole

    part_sum = round(sum(float(p["wall_sec"]) for p in parts), 1)
    whole_sec = float(whole["wall_sec"])
    ratio = round(whole_sec / part_sum, 2) if part_sum else None
    # BAND, chosen from the measurement rather than from taste, and WIDENED after the `before`
    # run: that run produced ratio=0.45 under a first-cut 0.75-1.6 band and flagged incoherent,
    # but the cause was ordinary run-to-run variance -- the dominant gate measured 97.9, 142.9
    # and 210.1 s in one session, a 2.1x spread from OS file-cache warmth and sibling load. A
    # band that fires on 2x variance cannot distinguish "noisy" from "measured in the other
    # world", so it is not a control (single-signal-verification 3c). The defect it must catch
    # is a 60x world mismatch (2.6 s vs 98-210 s on the same gate), which lands at ratio ~0.04
    # or ~60. 0.25-4.0 tolerates 4x noise and still fires an order of magnitude before that.
    receipt["consistency"] = {
        "part_sum_sec": part_sum,
        "whole_sec": whole_sec,
        "whole_over_parts": ratio,
        "coherent": bool(ratio is not None and 0.25 <= ratio <= 4.0),
        "band": [0.25, 4.0],
        "why": (
            "the whole runs exactly these six children, so the two numbers must be within "
            "cache-variance of each other; a ratio outside the band means they were not "
            "produced in the same environment -- the R1 table's defect. NOT a pass/fail gate: "
            "wall time is not a contract, so this is reported, and only exit codes are asserted"
        ),
    }
    receipt["note"] = "COMPLETE"
    flush()

    bad = [p["label"] for p in parts if not p["rc_as_expected"]]
    print("")
    print(f"part_sum={part_sum}s whole={whole_sec}s ratio={ratio}")
    if bad:
        print(f"FAILED:b10-gate-timing exit codes changed: {bad}")
        return 1
    print(f"SUCCESS:b10-gate-timing tag={args.tag} receipt={dest.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
