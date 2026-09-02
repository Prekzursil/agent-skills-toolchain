import json
import sys
from pathlib import Path

HERE = Path(r"C:\Users\Prekzursil\source\ast-integrate\command-center\p2-wave\probes\IMP-0162")
REPO = Path(r"C:\Users\Prekzursil\source\ast-integrate")
sys.path.insert(0, str(REPO / "tools" / "agentspec"))

from agentspec.import_generic_dag import GenericDeclarativeDagAdapter  # noqa: E402

ADAPTER = GenericDeclarativeDagAdapter()
for name in ("duplicate_keys.json", "duplicate_node_id.json", "case_distinct.json", "valid_minimal.json"):
    res = ADAPTER.import_path(HERE / "fixtures" / name)
    d = res.to_dict()
    print(name, "ok=", d.get("ok"), "violations=", d.get("violations"))
