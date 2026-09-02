"""Scratch execution of credential consumers: UNSET vs syntactically-valid WRONG."""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import constants as C

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
KEEP_ENV = frozenset(
    {
        "PATH",
        "HOME",
        "USER",
        "LOGNAME",
        "LANG",
        "LC_ALL",
        "LC_CTYPE",
        "TZ",
        "TERM",
        "TMPDIR",
        "TMP",
        "TEMP",
        "SYSTEMROOT",
        "WINDIR",
        "COMSPEC",
        "PATHEXT",
        "SYSTEMDRIVE",
        "NUMBER_OF_PROCESSORS",
    }
)
CRED_ENV_NAMES = (
    "CURSOR_API_KEY",
    "CURSOR_API_TOKEN",
    "ANTHROPIC_API_KEY",
    "OPENAI_API_KEY",
    "GITHUB_TOKEN",
    "GITHUB_PAT",
    C.LOUD_TOKEN_NAME,
    C.FILE_ENV_NAME,
)
GATE_INJECT = (
    "\n    print('AUD0079-GATE-PASSED')\n"
    "    return 0\n"
)


def _scrub(text: str) -> str:
    out = text or ""
    needles = [C.WRONG_TOKEN, C.EXPECTED_FIXTURE_TOKEN, C.WRONG_TOKEN[:4]]
    for name in CRED_ENV_NAMES:
        val = os.environ.get(name)
        if val and len(val) >= 8:
            needles.append(val)
            needles.append(val[:4])
    for needle in needles:
        if needle and needle in out:
            out = out.replace(needle, "[REDACTED]")
    return out


def _base_env(home: Path) -> dict[str, str]:
    env: dict[str, str] = {}
    for key, val in os.environ.items():
        if key in KEEP_ENV or key.startswith("PYTHON"):
            env[key] = val
    for name in CRED_ENV_NAMES:
        env.pop(name, None)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["HOME"] = str(home)
    env["TMPDIR"] = str(home / "tmp")
    return env


def _run(cmd: list[str], env: dict[str, str], cwd: Path, timeout: float = 8.0) -> dict:
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(cwd),
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        stdout = _scrub((proc.stdout or "")[-1500:])
        stderr = _scrub((proc.stderr or "")[-800:])
        return {
            "rc": int(proc.returncode),
            "stdout": stdout,
            "stderr": stderr,
            "timeout": False,
        }
    except subprocess.TimeoutExpired as exc:
        stdout = _scrub(((exc.stdout or b"") if isinstance(exc.stdout, (bytes, bytearray)) else (exc.stdout or ""))[-800:] if exc.stdout else "")
        if isinstance(exc.stdout, (bytes, bytearray)):
            stdout = _scrub(exc.stdout.decode("utf-8", "replace")[-800:])
        return {
            "rc": 124,
            "stdout": stdout,
            "stderr": "TIMEOUT",
            "timeout": True,
        }


def _py() -> str:
    return sys.executable


def run_fixture_pair(script: Path, env_name: str, extra_unset: dict | None = None, extra_wrong: dict | None = None) -> dict:
    with tempfile.TemporaryDirectory(prefix="aud0079-") as td:
        home = Path(td)
        (home / "tmp").mkdir()
        cmd = [_py(), "-B", str(script)]
        unset_env = _base_env(home)
        if extra_unset:
            unset_env.update(extra_unset)
        unset_env.pop(env_name, None)
        wrong_env = _base_env(home)
        if extra_wrong:
            wrong_env.update(extra_wrong)
        else:
            wrong_env[env_name] = C.WRONG_TOKEN
        u = _run(cmd, unset_env, home)
        w = _run(cmd, wrong_env, home)
    distinct = (u["rc"] != w["rc"]) or (u["stdout"] != w["stdout"])
    silent = u["rc"] == 0 and w["rc"] == 0
    loud_unset = u["rc"] not in (0, 124)
    return {
        "id": script.stem,
        "kind": "fixture",
        "env_name": env_name,
        "unset": {"rc": u["rc"], "stdout": u["stdout"], "stderr": u["stderr"], "timeout": u["timeout"]},
        "wrong": {"rc": w["rc"], "stdout": w["stdout"], "stderr": w["stderr"], "timeout": w["timeout"]},
        "distinct": distinct,
        "silent_degrade": silent,
        "loud_on_unset": loud_unset,
        "value_reported": False,
    }


def _inject_gate(src: str, needle: str) -> str:
    idx = src.find(needle)
    if idx < 0:
        return src
    # End of the if-block that starts at needle: next line that is less indented
    # and not inside the if. We insert immediately after the if-block.
    after = src.find("\n", idx)
    if after < 0:
        return src
    # Walk from the line after needle until indentation returns to the `if` indent.
    if_line = src.rfind("\n", 0, idx)
    if_indent = 0
    line = src[if_line + 1 : idx] if if_line >= 0 else src[:idx]
    if_indent = len(line) - len(line.lstrip(" "))
    pos = after + 1
    while pos < len(src):
        nl = src.find("\n", pos)
        chunk = src[pos:] if nl < 0 else src[pos:nl]
        if chunk.strip() == "":
            pos = (nl + 1) if nl >= 0 else len(src)
            continue
        indent = len(chunk) - len(chunk.lstrip(" "))
        if indent <= if_indent:
            return src[:pos] + GATE_INJECT + src[pos:]
        pos = (nl + 1) if nl >= 0 else len(src)
    return src + GATE_INJECT


def run_live_cli(spec: dict) -> dict:
    rel = spec["rel"]
    src_path = REPO / rel
    present = src_path.is_file()
    if not present:
        return {
            "id": spec["id"],
            "kind": "live-cli",
            "rel": rel,
            "present": False,
            "distinct": False,
            "silent_degrade": False,
            "loud_on_unset": False,
            "note": "entry-point-absent-on-tree",
            "value_reported": False,
        }
    src = src_path.read_text(encoding="utf-8")
    needle = spec["needle"]
    if needle not in src:
        return {
            "id": spec["id"],
            "kind": "live-cli",
            "rel": rel,
            "present": True,
            "distinct": False,
            "silent_degrade": False,
            "loud_on_unset": False,
            "note": "credential-gate-needle-absent",
            "value_reported": False,
        }
    with tempfile.TemporaryDirectory(prefix="aud0079-cli-") as td:
        home = Path(td)
        (home / "tmp").mkdir()
        scratch_root = (home / "p2").as_posix()
        rewritten = src.replace("/opt/p2/", scratch_root + "/")
        rewritten = _inject_gate(rewritten, needle)
        copy = home / src_path.name
        copy.write_text(rewritten, encoding="utf-8", newline="\n")
        cmd = [_py(), "-B", str(copy)]
        unset_env = _base_env(home)
        for name in spec["vars"]:
            unset_env.pop(name, None)
        wrong_env = _base_env(home)
        for name in spec["vars"]:
            wrong_env.pop(name, None)
        wrong_env[spec["vars"][0]] = C.WRONG_TOKEN
        u = _run(cmd, unset_env, home, timeout=6.0)
        w = _run(cmd, wrong_env, home, timeout=6.0)
    distinct = (u["rc"] != w["rc"]) or ("GATE-PASSED" in w["stdout"] and "GATE-PASSED" not in u["stdout"])
    silent = u["rc"] == 0 and w["rc"] == 0 and "GATE-PASSED" in u["stdout"]
    return {
        "id": spec["id"],
        "kind": "live-cli",
        "rel": rel,
        "present": True,
        "needle_found": True,
        "gate_injected": "AUD0079-GATE-PASSED" in rewritten,
        "unset": {"rc": u["rc"], "stdout": u["stdout"][-600:], "stderr": u["stderr"][-400:], "timeout": u["timeout"]},
        "wrong": {"rc": w["rc"], "stdout": w["stdout"][-600:], "stderr": w["stderr"][-400:], "timeout": w["timeout"]},
        "distinct": distinct,
        "silent_degrade": silent,
        "loud_on_unset": u["rc"] not in (0, 124),
        "value_reported": False,
        "note": "credential-gate executed from a scratch copy; post-gate body replaced with an early return so fleet/cloud side effects cannot run",
    }


def run_file_fixture() -> dict:
    with tempfile.TemporaryDirectory(prefix="aud0079-file-") as td:
        home = Path(td)
        (home / "tmp").mkdir()
        script = HERE / "fixtures" / "file_consumer.py"
        cmd = [_py(), "-B", str(script)]
        unset_env = _base_env(home)
        unset_env.pop(C.FILE_ENV_NAME, None)
        wrong_path = home / "cred-wrong.json"
        wrong_path.write_text('{"token": "syntactically-valid-but-wrong"}\n', encoding="utf-8")
        wrong_env = _base_env(home)
        wrong_env[C.FILE_ENV_NAME] = str(wrong_path)
        u = _run(cmd, unset_env, home)
        w = _run(cmd, wrong_env, home)
    distinct = u["rc"] != w["rc"] or u["stdout"] != w["stdout"]
    return {
        "id": "file_consumer",
        "kind": "fixture-file",
        "env_name": C.FILE_ENV_NAME,
        "unset": {"rc": u["rc"], "stdout": u["stdout"], "stderr": u["stderr"], "timeout": u["timeout"]},
        "wrong": {"rc": w["rc"], "stdout": w["stdout"], "stderr": w["stderr"], "timeout": w["timeout"]},
        "distinct": distinct,
        "silent_degrade": u["rc"] == 0 and w["rc"] == 0,
        "loud_on_unset": u["rc"] not in (0, 124),
        "value_reported": False,
    }


def run_all() -> dict:
    loud = run_fixture_pair(HERE / "fixtures" / "loud_consumer.py", C.LOUD_TOKEN_NAME)
    silent = run_fixture_pair(HERE / "fixtures" / "silent_consumer.py", C.LOUD_TOKEN_NAME)
    file_row = run_file_fixture()
    live = [run_live_cli(spec) for spec in C.LIVE_ENTRYPOINTS]
    rows = [loud, silent, file_row, *live]
    both_states_ok = loud["distinct"] and loud["loud_on_unset"] and (not loud["silent_degrade"])
    silent_detected = silent["silent_degrade"] and (not silent["distinct"] or silent["unset"]["rc"] == 0)
    file_ok = file_row["distinct"] and file_row["loud_on_unset"]
    live_ok = all((r.get("present") is False) or r.get("distinct") for r in live)
    return {
        "rows": rows,
        "both_states_control": {
            "loud_distinct": both_states_ok,
            "silent_detected": silent_detected,
            "file_distinct": file_ok,
            "live_gates_distinct": live_ok,
            "ok": both_states_ok and silent_detected and file_ok and live_ok,
        },
        "executed": len(rows),
        "value_reported": False,
    }


run_all = run_all
