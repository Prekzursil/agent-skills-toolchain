import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
TOOLS = REPO / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

print("pre-modules lib:", sys.modules.get("lib"))
import importlib.util
spec = importlib.util.find_spec("lib")
print("find_spec:", spec.submodule_search_locations if spec else None)
try:
    from lib.codex_invocation import argv_bytes_match  # noqa: F401
    print("ok")
except Exception as e:
    print("fail", type(e).__name__, e)
    import lib
    print("lib is:", lib.__file__)
