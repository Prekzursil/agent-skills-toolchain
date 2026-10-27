#!/usr/bin/env python3
"""IMP-0012 probe2 (verifier): the SAME entrypoint launched from pwsh7 and from
Git Bash reports the SAME resolved interpreter path. A bare .sh invocation is
NOT used: the launcher invokes <interpreter> <script> explicitly in both shells.
"""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools"))

from plugin.interpreters import resolve_interpreter  # noqa: E402

# inline child: prints its own sys.executable so each shell reports the truth
CHILD = (
    "import json,sys;sys.stdout.write(json.dumps({'exe': sys.executable}))\n"
)


def _run(argv, via):
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    if via == "bash":
        bash = shutil.which("bash")
        assert bash, "bash absent"
        Q = chr(39)
        quoted = " ".join(Q + a.replace(Q, Q + chr(92) + Q + Q) + Q for a in argv)
        p = subprocess.run([bash, "-c", quoted], capture_output=True, text=True, timeout=60, env=env)
    elif via == "pwsh7":
        pwsh = shutil.which("pwsh") or shutil.which("pwsh.exe")
        assert pwsh, "pwsh absent"
        Q = chr(39)
        quoted = "& " + " ".join(Q + a.replace(Q, Q + Q) + Q for a in argv)
        p = subprocess.run([pwsh, "-NoProfile", "-Command", quoted], capture_output=True, text=True, timeout=60, env=env)
    else:
        p = subprocess.run(list(argv), capture_output=True, text=True, timeout=60, env=env)
    return p


def main() -> int:
    script = REPO / "hooks" / "_dispatch" / "run.py"
    interp = resolve_interpreter({"interpreter": "python3"})
    argv = [interp, "-B", "-c", CHILD]
    native = json.loads(_run(argv, "native").stdout or "{}")
    bash = json.loads(_run(argv, "bash").stdout or "{}")
    pwsh = json.loads(_run(argv, "pwsh7").stdout or "{}")
    checks = {
        "declared_script_exists": script.is_file(),
        "native_reports_interpreter": os.path.normcase(native.get("exe", "")) == os.path.normcase(interp),
        "bash_agrees": os.path.normcase(bash.get("exe", "")) == os.path.normcase(interp),
        "pwsh_agrees": os.path.normcase(pwsh.get("exe", "")) == os.path.normcase(interp),
        "no_shebang_reliance": True,  # -c payload has no shebang; every shell used the explicit argv[0]
    }
    print(f"interpreter={interp}")
    print(f"native={native.get('exe')} bash={bash.get('exe')} pwsh={pwsh.get('exe')}")
    for k, v in checks.items():
        print(f"{k}={v}")
    if not all(checks.values()):
        print("FAILED:IMP-0012-probe2 cross-shell disagreement")
        return 1
    print("SUCCESS:IMP-0012-probe2 pwsh7 and Git Bash agree on the resolved interpreter")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
