import json, subprocess, sys
from pathlib import Path
ROOT = Path.cwd()
def sh(cmd, **kw):
    p = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return p.returncode, p.stdout + p.stderr
import runpy
# capture the main() behavior exactly as the file does
import importlib.util
spec = importlib.util.spec_from_file_location("g", "command-center/p2-loop/p2_goal.py")
sys.argv = ["x"]
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
rc = m.main()
print("RC", rc)
sys.exit(0)
