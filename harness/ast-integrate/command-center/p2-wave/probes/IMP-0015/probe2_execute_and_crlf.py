#!/usr/bin/env python3
"""Probe 2: execute each shipped script; CRLF copy must fail (both-states).

Signal 2 is live execution with a trivial argument (exit 0 + expected stdout),
not another syntax check. The adapter is the launch path; a second invoke uses
explicit `bash script arg` so a green shebang is not the only evidence.
"""
from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
ART = REPO / "command-center/receipts/IMP-0015.json"
LAUNCH = REPO / "release/platforms/linux/launch.sh"
SCRIPTS = REPO / "release/platforms/linux/scripts"
SENTINEL = "SUCCESS:IMP-0015"
EXPECTED = {
    "hello.sh": "IMP-0015-HELLO",
    "echo_arg.sh": "IMP-0015-ECHO:",
    "longrun.sh": "IMP-0015-LONGRUN",
}


def run(args: list[str], cwd: Path | None = None) -> tuple[int, str, str]:
    p = subprocess.run(
        args,
        cwd=str(cwd or REPO),
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )
    return p.returncode, p.stdout or "", p.stderr or ""


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        print("FAILED:IMP-0015-probe2 receipt missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if SENTINEL not in text:
        print("FAILED:IMP-0015-probe2 sentinel absent")
        return 1
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        print("FAILED:IMP-0015-probe2 self-declared", doc.get("state"))
        return 1

    if os.uname().sysname != "Linux":
        print("FAILED:IMP-0015-probe2 not Linux")
        return 1
    cwd = str(REPO)
    if cwd == "/mnt/c" or cwd.startswith("/mnt/c/"):
        print("FAILED:IMP-0015-probe2 cwd is /mnt/c")
        return 1

    scripts = sorted(SCRIPTS.glob("*.sh"))
    if len(scripts) < 3:
        print(f"FAILED:IMP-0015-probe2 script count {len(scripts)}")
        return 1

    runs = []
    for src in scripts:
        rel = src.relative_to(REPO).as_posix()
        prefix = EXPECTED.get(src.name)
        if not prefix:
            print(f"FAILED:IMP-0015-probe2 unexpected {rel}")
            return 1
        rc_a, out_a, err_a = run(["sh", str(LAUNCH), "run", rel, "trivial"])
        rc_b, out_b, err_b = run(["bash", str(src), "trivial"])
        a_ok = rc_a == 0 and out_a.startswith(prefix)
        b_ok = rc_b == 0 and out_b.startswith(prefix)
        runs.append(
            {
                "path": rel,
                "adapter_rc": rc_a,
                "adapter_stdout": out_a.strip(),
                "direct_bash_rc": rc_b,
                "direct_bash_stdout": out_b.strip(),
                "adapter_ok": a_ok,
                "direct_ok": b_ok,
            }
        )
        if not a_ok or not b_ok:
            print(json.dumps({"runs": runs, "err_a": err_a, "err_b": err_b}, indent=2))
            print(f"FAILED:IMP-0015-probe2 execute {src.name}")
            return 1
        if out_a.strip().splitlines()[0] != out_b.strip().splitlines()[0]:
            print(json.dumps(runs, indent=2))
            print(f"FAILED:IMP-0015-probe2 adapter/direct stdout disagree {src.name}")
            return 1

    victim = SCRIPTS / "longrun.sh"
    lf_ok_before = run(["bash", "-n", str(victim)])[0] == 0
    tmp = Path(tempfile.mkdtemp(prefix="imp0015-p2-"))
    crlf = tmp / "longrun.crlf.sh"
    crlf.write_bytes(victim.read_bytes().replace(b"\r\n", b"\n").replace(b"\n", b"\r\n"))
    crlf.chmod(crlf.stat().st_mode | stat.S_IXUSR)
    if b"\r" not in crlf.read_bytes():
        print("FAILED:IMP-0015-probe2 CRLF fixture has no CR")
        return 1

    rc_n, nout, nerr = run(["bash", "-n", str(crlf)])
    rc_chk, chk_out, chk_err = run(["sh", str(LAUNCH), "check", str(crlf)])
    rc_x, xout, xerr = run([str(crlf)])
    rc_run, rout, rerr = run(["sh", str(LAUNCH), "run", str(crlf), "trivial"])
    lf_ok_after = run(["bash", "-n", str(victim)])[0] == 0
    rc_good, gout, gerr = run(["sh", str(LAUNCH), "run", "release/platforms/linux/scripts/longrun.sh", "trivial"])

    crlf_block = {
        "bash_n_rc": rc_n,
        "bash_n_err": (nerr or nout)[-400:],
        "adapter_check_rc": rc_chk,
        "adapter_check_err": (chk_err or chk_out)[-400:],
        "shebang_exec_rc": rc_x,
        "shebang_exec_err": (xerr or xout)[-400:],
        "adapter_run_rc": rc_run,
        "lf_bash_n_before": lf_ok_before,
        "lf_bash_n_after": lf_ok_after,
        "lf_run_rc": rc_good,
        "lf_run_stdout": gout.strip(),
    }
    fired = rc_n != 0 and rc_chk != 0 and "ERROR:CRLF_REJECTED" in (chk_err + chk_out)
    shebang_fired = rc_x != 0
    silent_good = lf_ok_before and lf_ok_after and rc_good == 0 and gout.startswith("IMP-0015-LONGRUN")
    if not fired:
        print(json.dumps(crlf_block, indent=2))
        print("FAILED:IMP-0015-probe2 CRLF negative control did not fire")
        return 1
    if not shebang_fired:
        print(json.dumps(crlf_block, indent=2))
        print("FAILED:IMP-0015-probe2 CRLF shebang exec did not fail")
        return 1
    if not silent_good:
        print(json.dumps(crlf_block, indent=2))
        print("FAILED:IMP-0015-probe2 LF original not still green")
        return 1

    payload = {
        "probe": "probe2-execute-and-crlf",
        "unit_id": "IMP-0015",
        "pass": True,
        "runs": runs,
        "negative_control": {
            "kind": "crlf-converted-copy",
            "fired_on_bad_state": True,
            "silent_on_good_state": True,
            "shebang_exec_failed": True,
            "detail": crlf_block,
        },
        "two_invoke_paths": ["adapter launch.sh run", "explicit bash script arg"],
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    print("SUCCESS:IMP-0015-probe2 execute + CRLF negative control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
