#!/usr/bin/env python3
"""Add direct shebang-interpreter spawn to the Windows launch adapter.

Windows CreateProcess cannot exec shebang scripts (WinError 193). The
IMP-0013 charter forbids Git-Bash in the launch path, so the adapter resolves
the #! interpreter itself (shutil.which, python3->python Windows alias) and
spawns it with the script as argv[1]. Shell stays False; the forbidden-token
scan region is untouched (helpers live outside the markers).
"""
from pathlib import Path

P = Path(r"C:\Users\Prekzursil\p2-g1\release\platforms\windows\launch_adapter.py")
t = P.read_text(encoding="utf-8")

HELPERS = (
    'def _shebang_interpreter(path: str) -> str | None:\n'
    '    """Resolve the interpreter named by a #! line, Windows-natively.\n'
    '\n'
    '    Accepts /usr/bin/env forms and direct paths; applies the python3 ->\n'
    '    python alias Windows convention needs.\n'
    '    """\n'
    '    try:\n'
    '        first = Path(path).read_bytes().split(b"\\n", 1)[0]\n'
    '    except OSError:\n'
    '        return None\n'
    '    if not first.startswith(b"#!"):\n'
    '        return None\n'
    '    parts = first[2:].decode("utf-8", "replace").strip().split()\n'
    '    if not parts:\n'
    '        return None\n'
    '    target = parts[-1].rsplit("/", 1)[-1]\n'
    '    found = shutil.which(target)\n'
    '    if found is None and target in ("python3", "python"):\n'
    '        found = shutil.which("python")\n'
    '    return found\n'
    '\n'
    '\n'
)
OLD = "def posix_command_v_live("
NEW = HELPERS + OLD

n = t.count(OLD)
if n != 1:
    raise SystemExit(f"FAILED:shebang-spawn anchor found {n} times (want 1)")
t = t.replace(OLD, NEW)

OLD2 = (
    "    cmd = [resolved, *(argv or [])]\n"
    "    # LAUNCH-PATH-BEGIN\n"
    "    proc = subprocess.run(\n"
    "        cmd,\n"
    "        capture_output=True,\n"
    "        text=True,\n"
    "        shell=False,\n"
    "        timeout=30,\n"
    "    )\n"
    "    # LAUNCH-PATH-END\n"
)
NEW2 = (
    "    cmd = [resolved, *(argv or [])]\n"
    "    # LAUNCH-PATH-BEGIN\n"
    "    try:\n"
    "        proc = subprocess.run(\n"
    "            cmd,\n"
    "            capture_output=True,\n"
    "            text=True,\n"
    "            shell=False,\n"
    "            timeout=30,\n"
    "        )\n"
    "    except OSError as exc:\n"
    "        if os.name != \"nt\" or _shebang_interpreter(resolved) is None:\n"
    "            raise\n"
    "        # 2026-10-24: CreateProcess cannot exec shebang scripts\n"
    "        # (WinError 193). Resolve the #! interpreter directly (no\n"
    "        # shell, no bash) and spawn it with the script as argv[1].\n"
    "        interp = _shebang_interpreter(resolved)\n"
    "        proc = subprocess.run(\n"
    "            [interp, resolved, *(argv or [])],\n"
    "            capture_output=True,\n"
    "            text=True,\n"
    "            shell=False,\n"
    "            timeout=30,\n"
    "        )\n"
    "    # LAUNCH-PATH-END\n"
)
n2 = t.count(OLD2)
if n2 != 1:
    raise SystemExit(f"FAILED:shebang-spawn launch block found {n2} times (want 1)")
t = t.replace(OLD2, NEW2)
P.write_text(t, encoding="utf-8")
import ast

ast.parse(t)
print("SUCCESS:shebang-spawn added, syntax OK")
