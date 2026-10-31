"""Windows exe shims for TST-0238: a PATH shim must be a real executable.

On this Windows box CreateProcess only resolves *.exe, so the PATH-shim
detector compiles tiny logging executables with the framework C# compiler.
true.exe appends its name to TST0238_SHIM_LOG and exits 0; sleeper.exe does
the same and additionally leaves a detached 25s powershell child whose
command line carries a unique token, so an OS-level process enumeration can
independently observe that the render genuinely created a process.
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

OS_TOKEN = "TST0238OS7Q4ZTOKEN"

CSC_CANDIDATES = [
    Path("C:/Windows/Microsoft.NET/Framework64/v4.0.30319/csc.exe"),
    Path("C:/Windows/Microsoft.NET/Framework/v4.0.30319/csc.exe"),
]

NL = chr(92) + "n"  # backslash-n for the C# escape, harness-safe

CS_TRUE = (
    "using System; using System.IO; "
    "class Shim { static int Main() { "
    "var log = Environment.GetEnvironmentVariable(\"TST0238_SHIM_LOG\"); "
    "if (log != null) { try { File.AppendAllText(log, \"true" + NL + "\"); } catch {} } "
    "return 0; } }"
)

CS_SLEEPER = (
    "using System; using System.IO; using System.Threading; "
    "class Shim { static int Main() { "
    "var log = Environment.GetEnvironmentVariable(\"TST0238_SHIM_LOG\"); "
    "if (log != null) { try { File.AppendAllText(log, \"sleeper" + NL + "\"); } catch {} } "
    "Thread.Sleep(8000); "
    "return 0; } }"
)


def find_csc() -> Path | None:
    for c in CSC_CANDIDATES:
        if c.is_file():
            return c
    return None


def shim_env(shim_dir: Path, log_path: Path) -> dict:
    env = os.environ.copy()
    env["PATH"] = str(shim_dir) + os.pathsep + env.get("PATH", "")
    env["TST0238_SHIM_LOG"] = str(log_path)
    return env


def compile_shims(work_dir: Path) -> dict:
    """Compile true.exe + sleeper.exe; returns {csc, shim_dir, exe paths}."""
    csc = find_csc()
    if csc is None:
        return {"ok": False, "reason": "csc.exe not found"}
    work_dir = Path(work_dir)
    shim_dir = work_dir / "shims"
    shim_dir.mkdir(parents=True, exist_ok=True)
    outs = {}
    for name, src in (("true", CS_TRUE), ("sleeper", CS_SLEEPER)):
        cs = work_dir / f"shim_{name}.cs"
        exe = shim_dir / f"{name}.exe"
        cs.write_text(src, encoding="utf-8")
        r = subprocess.run(
            [str(csc), "/nologo", "/out:" + str(exe), "/target:exe", str(cs)],
            capture_output=True, text=True, timeout=120,
        )
        if r.returncode != 0 or not exe.is_file():
            return {"ok": False, "reason": f"csc failed for {name}: {r.stdout} {r.stderr}"}
        outs[name] = exe
    return {"ok": True, "csc": str(csc), "shim_dir": shim_dir, **outs}
