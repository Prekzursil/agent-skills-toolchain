"""Child-side loader: install intercept then run the target script."""
from __future__ import annotations

import runpy
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import intercept as I  # noqa: E402

I.install()

args = sys.argv[1:]
if not args:
    raise SystemExit("boot.py: missing script")
script = args[0]
sys.argv = [script, *args[1:]]
sys.path.insert(0, str(Path(script).resolve().parent))
runpy.run_path(script, run_name="__main__")
