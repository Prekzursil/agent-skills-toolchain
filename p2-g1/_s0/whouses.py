import re, subprocess
from pathlib import Path
REPO = Path.home() / "p2-g1"
print("=== real import lines in tests/ ===")
for name in ["test_index_schema.py", "test_dependency_graph.py", "test_license.py"]:
    p = REPO / "tools/marketplace/tests" / name
    print("---", name)
    for line in p.read_text(encoding="utf-8").splitlines():
        if "import" in line and "marketplace" in line:
            print("   ", line.strip())
print("=== probe dirs importing those test modules ===")
r = subprocess.run(["grep", "-rln", "test_index_schema", str(REPO / "command-center/p2-wave/probes")], capture_output=True, text=True)
print([l for l in r.stdout.splitlines() if "__pycache__" not in l])
r = subprocess.run(["grep", "-rln", "search", str(REPO / "tools/marketplace/tests/test_index_schema.py")], capture_output=True, text=True)
print("test_index_schema mentions search:", bool(r.stdout.strip()))
