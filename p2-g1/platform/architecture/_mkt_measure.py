"""Measure the on-disk substrate this architecture must reuse or replace.

Scope stated explicitly: walks the FULL repo tree at C:/Users/Prekzursil/source/ast-integrate
(no depth limit), excluding .git and __pycache__. Prints counts per area.
Run: python platform/architecture/_mkt_measure.py
"""

import json
import os
import subprocess
import sys

REPO = "C:/Users/Prekzursil/source/ast-integrate"
EXCL_DIRS = {".git", "__pycache__", ".pytest_cache", "node_modules"}


def walk(root):
    out = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in EXCL_DIRS]
        for fn in filenames:
            out.append(os.path.join(dirpath, fn).replace("\\", "/"))
    return out


def rel(p):
    return os.path.relpath(p, REPO).replace("\\", "/")


def main():
    allf = walk(REPO)
    print("SCOPE: full recursive walk of", REPO)
    print("EXCLUDED DIRS:", sorted(EXCL_DIRS))
    print("TOTAL FILES (excl. above):", len(allf))
    print()

    buckets = {
        "platform/schema": [],
        "platform/lib": [],
        "platform/council": [],
        "platform/registry": [],
        "platform/corpus": [],
        "platform/architecture": [],
        "command-center/schema": [],
        "command-center (other)": [],
        "other": [],
    }
    for p in allf:
        r = rel(p)
        placed = False
        for k in (
            "platform/schema",
            "platform/lib",
            "platform/council",
            "platform/registry",
            "platform/corpus",
            "platform/architecture",
            "command-center/schema",
        ):
            if r.startswith(k + "/") or r == k:
                buckets[k].append(r)
                placed = True
                break
        if placed:
            continue
        if r.startswith("command-center/"):
            buckets["command-center (other)"].append(r)
        else:
            buckets["other"].append(r)

    for k, v in buckets.items():
        print(f"{k:28s} {len(v):6d} files")
    print()

    # --- schema counts
    sch = [f for f in buckets["platform/schema"] if f.endswith(".schema.json")]
    print("platform/schema *.schema.json:", len(sch))
    for s in sorted(sch):
        print("   ", s)
    print()

    # --- council protocol vs preset split
    cc = buckets["platform/council"]
    specs = [f for f in cc if f.endswith(".councilspec.json")]
    prot = [f for f in specs if "/protocols/" in f]
    pres = [f for f in specs if "/presets/" in f]
    print("platform/council .councilspec.json total:", len(specs))
    print("   under /protocols/:", len(prot))
    print("   under /presets/  :", len(pres))
    print("   elsewhere        :", len(specs) - len(prot) - len(pres))
    print("   council dir listing:", sorted({os.path.dirname(f) for f in cc})[:12])
    print()

    # --- lib packages
    libdirs = sorted(
        {f.split("/")[2] for f in buckets["platform/lib"] if f.count("/") >= 3}
    )
    libtop = sorted([f for f in buckets["platform/lib"] if f.count("/") == 2])
    print("platform/lib subpackages:", libdirs)
    print("platform/lib top-level files:", len(libtop))
    pytest_files = [
        f for f in buckets["platform/lib"] if os.path.basename(f).startswith("test_")
    ]
    probe_files = [
        f
        for f in buckets["platform/lib"]
        if os.path.basename(f).startswith("_") and f.endswith(".py")
    ]
    print("  test_*.py:", len(pytest_files), " _probe/_gen scripts:", len(probe_files))
    print()

    # --- command-center/schema shim tree
    ccs = buckets["command-center/schema"]
    print("command-center/schema files:", len(ccs))
    print("  .json:", len([f for f in ccs if f.endswith(".json")]))
    print()

    # --- catalog
    cat = os.path.join(REPO, "command-center/WORK-UNIT-CATALOG.json")
    with open(cat, encoding="utf-8") as f:
        d = json.load(f)
    print("WORK-UNIT-CATALOG.json top-level keys:", sorted(d.keys()))
    wu = d.get("work_units", [])
    items = d.get("items", [])
    print("  work_units:", len(wu), " items:", len(items))
    if wu:
        keys = {}
        for u in wu:
            for k in u:
                keys[k] = keys.get(k, 0) + 1
        print("  work_unit field coverage (field: count):")
        for k in sorted(keys, key=lambda x: -keys[x]):
            print(f"     {k:38s} {keys[k]}")
        # distinct output_schema paths
        paths = set()
        for u in wu:
            v = u.get("output_schema")
            if isinstance(v, str):
                paths.add(v)
            elif isinstance(v, list):
                paths.update(v)
        print("  distinct output_schema string values:", len(paths))
        phases = {}
        for u in wu:
            phases[str(u.get("phase"))] = phases.get(str(u.get("phase")), 0) + 1
        print("  units by phase:", json.dumps(phases, sort_keys=True))
    print()

    # --- registry candidates
    reg = buckets["platform/registry"]
    print("platform/registry files:", len(reg))
    for r in sorted(reg):
        print("   ", r)
    print()

    # --- git-tracked vs untracked for platform/ + command-center/
    for area in ("platform", "command-center"):
        try:
            tracked = subprocess.run(
                ["git", "-C", REPO, "ls-files", area],
                capture_output=True,
                text=True,
                check=True,
            ).stdout.split()
            print(f"git-tracked under {area}/: {len(tracked)}")
        except Exception as e:  # pragma: no cover
            print(f"git ls-files {area} FAILED: {e}")
    print()
    print("SUCCESS:mkt-measure")


if __name__ == "__main__":
    sys.exit(main())
