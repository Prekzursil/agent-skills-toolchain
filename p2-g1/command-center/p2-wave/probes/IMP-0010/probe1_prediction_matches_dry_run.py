#!/usr/bin/env python3
"""IMP-0010 probe1: the catalog test suite runs green against the live module."""
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]


def main() -> int:
    proc = subprocess.run(
        [sys.executable, "-B", "-m", "pytest", "-q",
         "tools/plugin/tests/test_projection_map.py"],
        cwd=str(REPO), capture_output=True, text=True, timeout=600,
        env={"PYTHONDONTWRITEBYTECODE": "1", "PATH": "", "SYSTEMROOT": __import__("os").environ.get("SYSTEMROOT", "")},
    )
    tail = (proc.stdout or "") + (proc.stderr or "")
    print(tail.strip()[-600:])
    passed = proc.returncode == 0 and "passed" in tail and " failed" not in tail
    if not passed:
        print("FAILED:IMP-0010-probe1 pytest rc=%d" % proc.returncode)
        return 1
    print("SUCCESS:IMP-0010-probe1 projection-map suite green")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
