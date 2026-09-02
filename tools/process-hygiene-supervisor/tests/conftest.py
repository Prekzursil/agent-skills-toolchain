import pathlib
import sys

TOOL_ROOT = pathlib.Path(__file__).resolve().parents[1]
for extra in (TOOL_ROOT, TOOL_ROOT / "evals"):
    if str(extra) not in sys.path:
        sys.path.insert(0, str(extra))
