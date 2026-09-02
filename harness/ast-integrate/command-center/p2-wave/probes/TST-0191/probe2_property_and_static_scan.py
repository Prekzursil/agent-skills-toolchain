#!/usr/bin/env python3
"""Probe 2: independent 500-value property, static spawn scan, second-shell check."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
TOOLS = REPO / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from adversarial import REQUIRED_CLASSES, SAFE_MUTATION, generate_adversarial  # noqa: E402
from concat_mutant import concat_echo  # noqa: E402
from lib.argv_spawn_scan import scan_production  # noqa: E402
from lib.codex_invocation import (  # noqa: E402
    ECHO_SCRIPT,
    argv_bytes_match,
    echo_child_argv,
    expected_hex,
)

UNIT = "TST-0191"
N_PROP = 500


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe2 {msg}")
    return 1


def bash_argv_array(arg: str) -> list[dict]:
    proc = subprocess.run(
        [
            "bash",
            "-c",
            'exec "$0" "$@"',
            sys.executable,
            "-B",
            str(ECHO_SCRIPT),
            arg,
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        timeout=30,
    )
    if proc.returncode != 0:
        return []
    try:
        return json.loads(proc.stdout.decode("ascii"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return []


def bash_concat(arg: str) -> list[dict]:
    cmd = f"{sys.executable} -B {ECHO_SCRIPT} {arg}"
    proc = subprocess.run(
        ["bash", "-c", cmd],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        timeout=30,
    )
    if proc.returncode != 0:
        return []
    try:
        return json.loads(proc.stdout.decode("ascii"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return []


def js_live_check() -> dict:
    node = shutil.which("node")
    mjs = TOOLS / "lib" / "codex-invocation.mjs"
    runner = HERE / "run_mjs_echo.mjs"
    if not node or not mjs.is_file():
        return {"ran": False, "reason": "node-or-module-absent"}
    sample = ["has space", "%VAR%", "café-中文-🙂"]
    argv = [sys.executable, "-B", str(ECHO_SCRIPT), *sample]
    proc = subprocess.run(
        [node, str(runner), str(mjs), json.dumps(argv)],
        cwd=str(REPO),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=30,
        check=False,
    )
    try:
        recs = json.loads(proc.stdout.decode("ascii"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        recs = []
    ok = proc.returncode == 0 and argv_bytes_match(sample, recs)
    return {
        "ran": True,
        "ok": ok,
        "exit_code": proc.returncode,
        "stderr_tail": (proc.stderr or b"")[-200:].decode("utf-8", "replace"),
    }


def main() -> int:
    values = generate_adversarial(N_PROP, seed=191)
    if len(values) != N_PROP:
        return fail(f"corpus size {len(values)} want {N_PROP}")
    recs = echo_child_argv(values, timeout=60.0)
    want = expected_hex(values)
    if recs != want:
        mismatches = [i for i, (a, b) in enumerate(zip(want, recs)) if a != b]
        extra = abs(len(want) - len(recs))
        return fail(f"property mismatch indexes={mismatches[:12]} len_delta={extra}")
    print(f"property_n={N_PROP} argv_match=True")

    scan = scan_production()
    print(f"static_scan ok={scan['ok']} hits={scan['hit_count']}")
    if not scan["ok"]:
        return fail(f"production spawn scan hits={scan['hits'][:8]}")

    mutant_fail = 0
    for payload in SAFE_MUTATION:
        got = concat_echo([payload])
        if not argv_bytes_match([payload], got):
            mutant_fail += 1
    print(f"concat_mutation_failures={mutant_fail}")
    if mutant_fail == 0:
        return fail("concat mutation did not fail the property")

    space = "has space"
    bash_arr_ok = argv_bytes_match([space], bash_argv_array(space))
    bash_cat_div = not argv_bytes_match([space], bash_concat(space))
    print(f"bash_argv_array_ok={bash_arr_ok} bash_concat_diverges={bash_cat_div}")
    if not bash_arr_ok:
        return fail("bash argv-array $@ did not preserve 'has space'")
    if not bash_cat_div:
        return fail("bash concat of 'has space' did not diverge")

    js = js_live_check()
    print(f"js_live ran={js.get('ran')} ok={js.get('ok')} reason={js.get('reason', '')}")
    if js.get("ran") and not js.get("ok"):
        return fail(f"node invokeArgv failed {js}")

    required_vals = [v for _n, v in REQUIRED_CLASSES]
    if not argv_bytes_match(required_vals, echo_child_argv(required_vals)):
        return fail("required-class rerun diverged")

    payload = {
        "probe": "probe2-property-and-static-scan",
        "unit_id": UNIT,
        "reviewer_id": "TST-0191-probe2-property-and-static-scan",
        "verdict": "PASS",
        "property_n": N_PROP,
        "property_ok": True,
        "static_scan_ok": True,
        "concat_mutation_failures": mutant_fail,
        "bash_argv_array_ok": bash_arr_ok,
        "bash_concat_diverges": bash_cat_div,
        "js_live": js,
        "windows_shells": {
            "pwsh": shutil.which("pwsh"),
            "powershell": shutil.which("powershell") or shutil.which("powershell.exe"),
            "git_bash": next(
                (
                    p
                    for p in (
                        shutil.which("git-bash"),
                        "/mnt/c/Program Files/Git/bin/bash.exe",
                    )
                    if p and os.path.isfile(p)
                ),
                None,
            ),
            "note": (
                "POSIX worktree. pwsh7 and Git Bash were looked up; absent "
                "shells are NOT-CHECKED, not invented."
            ),
        },
        "pass": True,
    }
    print(json.dumps(payload, ensure_ascii=True, sort_keys=True))
    print(f"SUCCESS:{UNIT}-probe2 500-value property; static scan; concat mutation")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
