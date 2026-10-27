r"""ROUND-2 FINAL VERIFICATION -- one command, one terminal state.

Runs every round-2 check as a real subprocess and records its verbatim output. Nothing here
reads a claim; every line is produced by executing something. A reviewer runs this file.

  1. defect controls      -- 5 both-states controls against the pinned round-1 baseline
  2. receipt gate         -- the 12-condition vector for both receipts (never the binary marker)
  3. elided self-digests  -- with the mutated-state control, and the empty-input fail-closed check
  4. fresh clone          -- clone into a throwaway dir, digest from BOTH object store and checkout
  5. census               -- control pairs first; no tally is printed unless they separate
  6. liveness             -- three-state control on the SAME invocation as the tally
  7. ADV-0002 / ADV-0038  -- widened all-projects sweep with a wildcard detector control
  8. git verifier         -- the ADV-0022 independent probe, self-match guarded

Terminal: SUCCESS:r2-verify-all / FAILED:r2-verify-all <failing step ids>
"""

from __future__ import annotations

import datetime as _dt
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path("C:/Users/Prekzursil/source/ast-integrate")
CAS = "command-center/casualty"
R21 = f"{CAS}/ADV-0021-install-path-stride-threat-model.json"
R22 = f"{CAS}/ADV-0022-declared-permission-escape.json"

# `bash` on PATH from a Python subprocess resolves to C:\WINDOWS\system32\bash.exe = WSL, which
# sees /mnt/c and makes `git` inside the script die with "fatal: not a git repository". The first
# version of this runner used bare `bash` and the step still PASSED, because its needle
# (ADV0022_GITV_END) prints even when every git query inside failed. That is a needle that cannot
# fail -- fixed by using Git Bash explicitly AND by requiring the C1 control to be non-zero.
GIT_BASH = next(
    (
        p
        for p in (
            "C:/Program Files/Git/bin/bash.exe",
            "C:/Program Files (x86)/Git/bin/bash.exe",
        )
        if Path(p).exists()
    ),
    "bash",
)

STEPS = [
    # (id, argv, expected_rc, must_contain)
    (
        "defect-controls",
        [sys.executable, f"{CAS}/_r2_defect_controls.py"],
        0,
        "SUCCESS:r2-defect-controls",
    ),
    (
        "gate-0021",
        ["python", "platform/lib/receipt_schema_gate.py", R21, "--repo-root", "."],
        None,
        "c1=UNSATISFIED",
    ),
    (
        "gate-0022",
        ["python", "platform/lib/receipt_schema_gate.py", R22, "--repo-root", "."],
        None,
        "c1=UNSATISFIED",
    ),
    (
        "elided-digests",
        [sys.executable, f"{CAS}/verify_elided_digest.py", R21, R22],
        0,
        "MATCH=True",
    ),
    (
        "elided-empty-fails-closed",
        [sys.executable, f"{CAS}/verify_elided_digest.py"],
        2,
        "FAILED:elided-digest no inputs",
    ),
    (
        "fresh-clone",
        [sys.executable, f"{CAS}/verify_blob_parity.py", "--fresh-clone"],
        0,
        "SUCCESS:fresh-clone",
    ),
    (
        "blob-eol-scan",
        [sys.executable, f"{CAS}/_r2_blob_eol_scan.py"],
        0,
        "SUCCESS:blob-eol-scan",
    ),
    ("census", [sys.executable, f"{CAS}/census_v2.py"], 0, "SUCCESS:census-v2"),
    ("liveness", [sys.executable, f"{CAS}/liveness_v2.py"], 0, "SUCCESS:liveness-v2"),
    (
        "liveness-control-is-not-inert",
        [sys.executable, f"{CAS}/liveness_v2.py", "--selftest-mutate", "drop-g3"],
        1,
        "FAILED:liveness-v2-selftest",
    ),
    (
        "adv0002-widened",
        [sys.executable, f"{CAS}/_r2_adv0002_recheck.py"],
        0,
        "UPHELD (and WIDENED)",
    ),
    (
        "git-verifier",
        [GIT_BASH, f"{CAS}/probes/adv0022_git_verifier.sh"],
        0,
        "tracked_files_under_hooks=289",
    ),
]

SATISFIED = (2, 4, 6, 7, 8, 12)
UNSATISFIED = (1, 3, 5, 9, 10, 11)


def _vector_ok(out: str) -> bool:
    """Parse the twelve condition lines and require the exact expected vector -- and require
    that all twelve were seen, so a truncated or reformatted report cannot pass vacuously."""
    import re as _re

    seen = {
        int(n): (mark.strip() == "ok")
        for mark, n in _re.findall(r"\[\s*(ok|FAIL)\]\s*(\d+)\.", out)
    }
    if len(seen) != 12:
        return False
    return all(seen.get(n) for n in SATISFIED) and not any(
        seen.get(n) for n in UNSATISFIED
    )


# Extra per-step assertions that a single needle cannot express.
EXTRA = {
    # the hooks/ zero is only meaningful against a POPULATED pathspec, and the whole point of
    # D4 is that the delta must be computed rather than narrated
    "git-verifier": lambda out: (
        "git_grep_exit=1" in out
        and "self_match_inflation=" in out
        and "219 files, of which 12" not in out
        and "not a git repository" not in out
    ),
    # The vector, not the marker: these six must be the SATISFIED ones on both receipts.
    # The gate right-aligns the condition number ("[  ok]  2."), so a literal "[  ok] 2." never
    # matches -- my first version of this assertion failed both gates for that reason alone.
    "gate-0021": lambda out: _vector_ok(out),
    "gate-0022": lambda out: _vector_ok(out),
    # the clone's CHECKOUT (not only its object store) must reproduce the digest
    "fresh-clone": lambda out: (
        out.count("clone CHECKOUT") == 2
        and "clone CHECKOUT" in out
        and out.count("MATCH=True") >= 4
    ),
}


def run(argv: list[str]) -> tuple[int, str]:
    r = subprocess.run(argv, cwd=str(ROOT), capture_output=True, text=True)
    return r.returncode, (r.stdout + r.stderr).replace("\r\n", "\n")


def main() -> int:
    head = run(["git", "rev-parse", "HEAD"])[1].strip()
    print(
        f"ROUND-2 FINAL VERIFICATION  head={head[:8]}  "
        f"{_dt.datetime.now(_dt.timezone.utc).isoformat()}\n"
    )
    results, failed = [], []
    for sid, argv, want_rc, needle in STEPS:
        rc, out = run(argv)
        extra_ok = EXTRA.get(sid, lambda _out: True)(out)
        ok = (want_rc is None or rc == want_rc) and (needle in out) and extra_ok
        tail = [ln for ln in out.strip().splitlines() if ln.strip()][-1:] or [""]
        results.append(
            {
                "id": sid,
                "argv": argv,
                "rc": rc,
                "expected_rc": want_rc,
                "must_contain": needle,
                "contains": needle in out,
                "extra_assertions_pass": extra_ok,
                "PASS": ok,
                "last_line": tail[0][:300],
                "output": out[-6000:],
            }
        )
        if not ok:
            failed.append(sid)
        print(
            f"[{'PASS' if ok else 'FAIL'}] {sid:<30} rc={rc} (want {want_rc})  {tail[0][:110]}"
        )

    out_path = ROOT / CAS / "R2-FINAL-VERIFICATION.json"
    out_path.write_text(
        json.dumps(
            {
                "generated_at_utc": _dt.datetime.now(_dt.timezone.utc).isoformat(),
                "head": head,
                "note": (
                    "gate-0021/gate-0022 intentionally expect a non-zero rc: completed adversarial "
                    "units in this family ship state=BLOCKED with a FAILED: sentinel, so the binary "
                    "marker is saturated and only the 12-condition VECTOR is informative."
                ),
                "steps": results,
                "failed": failed,
                "all_pass": not failed,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"\nwrote {out_path}")
    if failed:
        print(f"FAILED:r2-verify-all {failed}")
        return 1
    print(f"SUCCESS:r2-verify-all {len(results)} steps executed, all pass")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
