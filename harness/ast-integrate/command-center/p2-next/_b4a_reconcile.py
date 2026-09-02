"""Reconcile reviewer enumeration vs the unit's, by SET not by count, before calling anything a defect."""

import json
import pathlib
import re
import subprocess

ROOT = pathlib.Path(__file__).resolve().parents[2]


def git(*a):
    return subprocess.run(["git", *a], cwd=ROOT, capture_output=True, text=True).stdout


tracked = [ln for ln in git("ls-files").splitlines() if ln.strip()]

print("### AUD-0020: what did the unit enumerate?")
a20 = json.loads(
    (ROOT / "command-center/audit/AUD-0020-python-dep-inventory.json").read_text(
        encoding="utf-8"
    )
)
p0 = a20["report"]["packages"][0]
print("  package row keys:", list(p0.keys()))
print("  row[0]:", json.dumps(p0)[:500])
unit_dirs = [
    p.get("package") or p.get("dir") or p.get("path") for p in a20["report"]["packages"]
]
print(f"  unit package dirs ({len(unit_dirs)}):")
for d in unit_dirs:
    print("    ", d)
print("  raw_output of probe1 (the unit's own manifest list):")
print("   ", a20["evidence"][0]["probes"][0]["raw_output"][:2500])

print()
print("### AUD-0021: which package.json does the unit see that I do not?")
a21 = json.loads(
    (ROOT / "command-center/audit/AUD-0021-node-dep-inventory.json").read_text(
        encoding="utf-8"
    )
)
mans = a21["report"]["manifests"]
print("  manifest row keys:", list(mans[0].keys()))
unit_man = sorted(
    (m.get("path") or m.get("manifest") or "").replace("\\", "/") for m in mans
)
VEND = (
    "node_modules",
    "site-packages",
    ".venv",
    "venv",
    "vendor",
    "third_party",
    ".git",
    "__pycache__",
    "dist",
    "build",
    ".claude/plugins",
    ".local/opt",
)


def is_vend(rel):
    s = rel.replace("\\", "/")
    return any(f"/{v}/" in f"/{s}/" for v in VEND)


mine_disk = sorted(
    str(p.relative_to(ROOT)).replace("\\", "/")
    for p in ROOT.rglob("package.json")
    if not is_vend(str(p.relative_to(ROOT)))
)
mine_all = sorted(
    str(p.relative_to(ROOT)).replace("\\", "/")
    for p in ROOT.rglob("package.json")
    if "node_modules" not in str(p.relative_to(ROOT)).replace("\\", "/")
)
print(f"  unit manifests   : {len(unit_man)}")
print(f"  reviewer (my VEND filter)      : {len(mine_disk)}")
print(f"  reviewer (only node_modules)   : {len(mine_all)}")
print("  in unit but not in my filtered set:")
for x in sorted(set(unit_man) - set(mine_disk)):
    print("    +", x)
print("  in my filtered set but not in unit:")
for x in sorted(set(mine_disk) - set(unit_man)):
    print("    -", x)
print("  in unit but not in node_modules-only set:")
for x in sorted(set(unit_man) - set(mine_all)):
    print("    +", x)
print("  in node_modules-only set but not unit:")
for x in sorted(set(mine_all) - set(unit_man)):
    print("    -", x)
# which package.json has a LIST dependencies (the crash)
for p in ROOT.rglob("package.json"):
    rel = str(p.relative_to(ROOT)).replace("\\", "/")
    if "node_modules" in rel:
        continue
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"  PARSE ERROR {rel}: {e}")
        continue
    for sec in ("dependencies", "devDependencies"):
        if sec in d and not isinstance(d[sec], dict):
            print(
                f"  NON-DICT {sec} in {rel}: {type(d[sec]).__name__} = {str(d[sec])[:120]}"
            )

print()
print("### AUD-0020 manifest set reconciliation")
man = [
    f
    for f in tracked
    if (
        f.endswith("/pyproject.toml")
        or f == "pyproject.toml"
        or re.search(r"(^|/)requirements[^/]*\.txt$", f)
    )
    and not is_vend(f)
]
print(f"  my git-index manifests ({len(man)}):")
for f in sorted(man):
    print("    ", f)
