"""Windows recursion wrapper: patch subprocess.run (POSIX env-prefix + python3
substitution), then runpy the requested script. Used by _rebuild_unit.py so
every descendant interpreter handles the unit scripts' POSIX-style command
strings the same way command-center/p2-wave/_measure_one_delivered.py does at
its own level. Recursion is safe: each child that spawns another python goes
through this wrapper again.
"""
import os
import re
import runpy
import subprocess
import sys

_orig_run = subprocess.run


def _patched_run(cmd, **kw):
    if isinstance(cmd, str):
        env = dict(os.environ)
        passed = kw.get("env")
        if isinstance(passed, dict):
            env.update(passed)
        while True:
            m = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)=(\S+)\s+", cmd)
            if m is None:
                break
            env[m.group(1)] = m.group(2).strip('"').strip("'")
            cmd = cmd[m.end():]
        if "python3" in cmd:
            exe = sys.executable.replace("\\", "/")
            w = os.path.abspath(__file__).replace("\\", "/")
            cmd = cmd.replace("python3", f"{exe} {w}", 1)
        kw["env"] = env
        kw["shell"] = True
    return _orig_run(cmd, **kw)


subprocess.run = _patched_run
os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")

# The worktree has a top-level platform/ directory; once a unit script puts
# REPO on sys.path it shadows the stdlib platform module. Pre-import the
# stdlib module so the cache holds the real one before any script import runs.
import platform  # noqa: E402,F401 - stdlib preload on purpose

args = sys.argv[1:]
while args and args[0] in ("-B", "-E", "-s"):
    args = args[1:]
script = args[0]
sys.argv = [script] + args[1:]
runpy.run_path(script, run_name="__main__")
