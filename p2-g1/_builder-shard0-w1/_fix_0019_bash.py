"""Pin probe2's bash spawns to shutil.which('bash') - bare-name spawns resolve to
System32 WSL bash via CreateProcess search order and hang (wedged WSL)."""
from pathlib import Path

p = Path(
    __file__).resolve().parents[1] / "command-center/p2-wave/probes/ADV-0019/probe2_second_resolver.py"
src = p.read_text(encoding="utf-8")

old = '''    try:
        proc = subprocess.run(
            ["bash", "-c", script],
            capture_output=True,
            text=True,
            timeout=60,
        )'''
new = '''    try:
        # CreateProcess("bash") searches System32 BEFORE PATH and hits the WSL
        # bash, which hangs on this box (wedged WSL). shutil.which() searches
        # PATH only and finds the MSYS Git bash; pin to that binary.
        bash_exe = shutil.which("bash") or "bash"
        proc = subprocess.run(
            [bash_exe, "-c", script],
            capture_output=True,
            text=True,
            timeout=60,
        )'''
assert old in src, "bash spawn anchor missing"
src = src.replace(old, new, 1)
p.write_text(src, encoding="utf-8")
import ast
ast.parse(src)
print("pinned + syntax OK")
