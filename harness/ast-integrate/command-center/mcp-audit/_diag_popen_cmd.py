"""Scratch: does Popen(list) resolve a bare .cmd name on this Python/Windows?"""

import os
import pathlib
import subprocess
import sys
import tempfile

d = pathlib.Path(tempfile.mkdtemp(prefix="diagshim-"))
(d / "diagshim.cmd").write_text(
    "@echo off\r\necho HELLO_FROM_SHIM\r\n", encoding="ascii"
)
os.environ["PATH"] = f"{d}{os.pathsep}{os.environ.get('PATH', '')}"

print("python", sys.version)
for label, argv in (("bare-name", ["diagshim"]), ("with-ext", ["diagshim.cmd"])):
    try:
        out = subprocess.run(argv, capture_output=True, text=True, timeout=20)
        print(f"{label:10} rc={out.returncode} out={out.stdout.strip()!r}")
    except Exception as exc:  # noqa: BLE001
        print(f"{label:10} EXC {type(exc).__name__}: {exc}")

# And the real case that failed in the sweep.
for argv in (["npx", "--version"], ["codex", "--version"]):
    try:
        out = subprocess.run(argv, capture_output=True, text=True, timeout=60)
        print(f"{argv[0]:10} rc={out.returncode} out={out.stdout.strip()[:40]!r}")
    except Exception as exc:  # noqa: BLE001
        print(f"{argv[0]:10} EXC {type(exc).__name__}: {exc}")
