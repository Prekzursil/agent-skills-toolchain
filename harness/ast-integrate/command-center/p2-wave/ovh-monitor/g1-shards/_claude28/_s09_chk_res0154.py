import json
import sys
from pathlib import Path

HERE = Path(r"C:\Users\Prekzursil\source\ast-integrate\command-center\p2-wave\probes\RES-0154")
REPO = Path(r"C:\Users\Prekzursil\source\ast-integrate")
sys.path.insert(0, str(HERE))
import experiment as E  # noqa: E402
from util import OUT_REL  # noqa: E402

doc = json.loads((REPO / OUT_REL).read_text(encoding="utf-8"))
ext = doc.get("extensions") or {}
print("extensions keys:", sorted(ext.keys()))
print("extensions.negative_control:", json.dumps(ext.get("negative_control"), indent=1, default=str)[:1200])

live = E.run_experiment()
print("live keys:", sorted(live.keys()))
print("live negative_control:")
print(json.dumps(live["negative_control"], indent=1, sort_keys=True, default=str))
