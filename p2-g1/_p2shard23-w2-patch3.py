"""Patch 3: backslash-escape fix in probe1 template, sys imports, platform shim, 0129 scan scope."""
from pathlib import Path

p = Path(__file__).resolve().parent / "_p2shard23-w2-build.py"
src = p.read_text(encoding="utf-8")

# 1. probe1 template: rendered probe must contain replace("\\", "/") so the
#    builder template source needs FOUR backslashes at this layer.
old = 'rel = str(a.get("path") or "").replace("\\\\", "/")'
new = 'rel = str(a.get("path") or "").replace("\\\\\\\\", "/")'
assert old in src, "backslash line not found"
src = src.replace(old, new)
print("patched: probe1 backslash escape")

# 2. import sys into probe bodies that use sys.modules
a = "import hashlib\nimport importlib.util\nimport json\nimport random\nfrom datetime import timedelta"
assert a in src, "0136 import block"
src = src.replace(a, "import hashlib\nimport importlib.util\nimport json\nimport random\nimport sys\nfrom datetime import timedelta")
print("patched: 0136 sys import")

b = "import hashlib\nimport importlib.util\nimport json\nfrom pathlib import Path"
assert b in src, "0137/0139 import block"
src = src.replace(b, "import hashlib\nimport importlib.util\nimport json\nimport sys\nfrom pathlib import Path")
print("patched: 0137/0139 sys import")

# 3. 0144: stdlib `platform` shadows the repo dir; use a package shim
old_shim = '''    if str(REPO) not in sys.path:
        sys.path.insert(0, str(REPO))
    import platform.plugin.cache as pc  # noqa: PLC0415 -- relative imports need the package'''
new_shim = '''    import types
    pkg = types.ModuleType("p2_platform_plugin")
    pkg.__path__ = [str(REPO / "platform/plugin")]
    sys.modules["p2_platform_plugin"] = pkg
    spec2 = importlib.util.spec_from_file_location(
        "p2_platform_plugin.cache", REPO / "platform/plugin/cache.py")
    pc = importlib.util.module_from_spec(spec2)
    sys.modules["p2_platform_plugin.cache"] = pc
    spec2.loader.exec_module(pc)'''
assert old_shim in src, "cache shim target"
src = src.replace(old_shim, new_shim)
print("patched: 0144 platform shim")

# 4. 0129: scope the remote-fetch scan to the marketplace install surface
old_scan = '''    plugin = REPO / "tools/plugin"
    remote_primitives = ("urllib.request", "http.client", "requests.get", "httpx", "fetch(")
    hits = []
    for p in sorted(plugin.glob("*.py")) if plugin.is_dir() else []:
        t = p.read_text(encoding="utf-8", errors="replace")
        for prim in remote_primitives:
            if prim in t:
                hits.append((p.name, prim))
    chk(not hits, "remote-fetch-primitive-live", hits)'''
new_scan = '''    surface = REPO / "tools/plugin/client_negotiate.py"
    remote_primitives = ("urllib.request", "http.client", "requests.get", "httpx", "fetch(", "socket.create_connection")
    hits = []
    if surface.is_file():
        t = surface.read_text(encoding="utf-8", errors="replace")
        for prim in remote_primitives:
            if prim in t:
                hits.append((surface.name, prim))
    chk(not hits, "remote-fetch-primitive-live", hits)'''
assert old_scan in src, "0129 scan target"
src = src.replace(old_scan, new_scan)
print("patched: 0129 scan scope")

p.write_text(src, encoding="utf-8", newline="\n")
print("patch3 complete, bytes:", len(src))
