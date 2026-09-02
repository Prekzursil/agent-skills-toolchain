import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

print("sys.modules lib:", sys.modules.get("lib"))
print("path head:", sys.path[:8])
import importlib.util
spec = importlib.util.find_spec("lib")
print("find_spec lib:", spec.origin if spec else None, spec.submodule_search_locations if spec else None)
try:
    import lib.completion_reducer as cr
    print("ok", cr.__file__)
except Exception as e:
    print("fail", type(e).__name__, e)
