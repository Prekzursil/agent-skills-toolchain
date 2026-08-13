"""VERIFY R2 -- re-execute EVERY committed probe in this lane's scope from the
committed state, and record its exit code.

The lane's headline defect (D2) was a committed receipt that asserted PASS while
re-running the same committed script produced FAIL, rc 1. Both the builder and the
auditor claim the suite now reproduces. That claim is only worth what an execution
says, so this runs them all and reports rc per probe.

CONTROL (both states): a probe that is KNOWN to fail must show up as rc 1 here, and a
probe known to pass must show rc 0. `_b1_control.py --sentinel legacy` is the
known-failing case (it is the lane's permanent negative control) and
`_b1_control.py` (default) the known-passing one. If BOTH come back rc 0, this
runner is not observing exit codes and no rc below may be cited.

Side effects are recorded, not hidden: the tracked receipts each probe rewrites are
listed per probe (git status diffed before/after), so "the published command dirties
a tracked file" is measured rather than assumed.
"""

import json
import pathlib
import subprocess
import sys
import time

REPO = pathlib.Path("C:/Users/Prekzursil/source/ast-integrate")
HERE = "command-center/slop-report"
OUT = pathlib.Path(__file__).with_suffix(".out.json")

PROBES = [
    ["_r2_d2_reproduce.py"],
    ["_r2_fix_verify.py"],
    ["_r2_bucket_c.py"],
    ["_r2_blast_reconcile.py"],
    ["_r2_postcommit.py"],
    ["_r2_frozen.py"],
    ["_r2_predcheck.py"],
    ["_aud1_census.py"],
    ["_aud2_commits.py"],
    ["_aud2_files.py"],
    ["_aud2_citation.py"],
    ["_aud2_dod34.py"],
    ["_aud2_rot.py"],
    ["_aud2_eol.py"],
    ["_aud4_files_and_buckets.py"],
    ["_aud5_head_state.py"],
    ["_aud6_residuals.py"],
    ["_aud7_blastradius.py"],
    ["_aud8_blastradius2.py"],
    ["_ver3_dod.py"],
]


def tracked_dirty():
    r = subprocess.run(
        ["git", "-C", str(REPO), "status", "--porcelain", "--", HERE],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return sorted(
        ln[3:] for ln in r.stdout.splitlines() if ln.strip() and not ln.startswith("??")
    )


def run_one(rel_args, timeout=1500):
    before = tracked_dirty()
    t0 = time.time()
    try:
        p = subprocess.run(
            [sys.executable, f"{HERE}/{rel_args[0]}", *rel_args[1:]],
            cwd=str(REPO),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
        rc, so, se = p.returncode, p.stdout, p.stderr
    except subprocess.TimeoutExpired:
        rc, so, se = "TIMEOUT", "", ""
    after = tracked_dirty()
    return {
        "cmd": " ".join(rel_args),
        "rc": rc,
        "secs": round(time.time() - t0, 1),
        "newly_dirty_tracked": sorted(set(after) - set(before)),
        "stderr_tail": (se or "").strip()[-400:],
        "stdout_tail": (so or "").strip()[-300:],
    }


def main():
    res = {
        "head": subprocess.run(
            ["git", "-C", str(REPO), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
        ).stdout.strip(),
        "dirty_at_start": tracked_dirty(),
    }

    # ---- runner control, BOTH states ---------------------------------------
    ctl_pass = run_one(["_b1_control.py"])
    ctl_fail = run_one(["_b1_control.py", "--sentinel", "legacy"])
    res["runner_control"] = {
        "known_pass_rc": ctl_pass["rc"],
        "known_fail_rc": ctl_fail["rc"],
        "states_distinguishable": ctl_pass["rc"] == 0 and ctl_fail["rc"] == 1,
    }

    rows = []
    for pr in PROBES:
        path = REPO / HERE / pr[0]
        if not path.is_file():
            rows.append({"cmd": " ".join(pr), "rc": "MISSING-ON-DISK"})
            continue
        rows.append(run_one(pr))
    res["probes"] = rows

    nonzero = [r for r in rows if r.get("rc") != 0]
    res["n_probes"] = len(rows)
    res["n_nonzero"] = len(nonzero)
    res["nonzero"] = [{"cmd": r["cmd"], "rc": r["rc"]} for r in nonzero]
    res["probes_that_dirty_tracked_files"] = {
        r["cmd"]: r.get("newly_dirty_tracked", [])
        for r in rows
        if r.get("newly_dirty_tracked")
    }
    res["dirty_at_end"] = tracked_dirty()
    res["verdict"] = (
        "SUITE-REPRODUCES"
        if (res["runner_control"]["states_distinguishable"] and not nonzero)
        else (
            "RUNNER-INERT"
            if not res["runner_control"]["states_distinguishable"]
            else "SUITE-DOES-NOT-REPRODUCE"
        )
    )
    OUT.write_text(json.dumps(res, indent=1), encoding="utf-8", newline="\n")
    print(json.dumps(res, indent=1)[:9000])
    return 0 if res["verdict"] == "SUITE-REPRODUCES" else 1


if __name__ == "__main__":
    sys.exit(main())
