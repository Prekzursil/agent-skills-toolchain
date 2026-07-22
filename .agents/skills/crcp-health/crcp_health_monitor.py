"""Shim entry for mon launcher (monitorcore may exec python on .py)."""

import os
import runpy
import sys
from pathlib import Path

crp = Path.home() / "source" / "agent-skills-toolchain" / "tools" / "crcp"
sys.path.insert(0, str(crp))
os.environ["PYTHONPATH"] = str(crp) + os.pathsep + os.environ.get("PYTHONPATH", "")
runpy.run_path(str(crp / "monitor" / "crcp_health_monitor.py"), run_name="__main__")
