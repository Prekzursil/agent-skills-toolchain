"""Third pass: (a) re-derive the sibling's 234 with a compositing-aware normalizer,
(b) inventory the plugin/marketplace control planes the catalog already names.

Detector discipline: pass (a) is a KNOWN-ANSWER control. The sibling claims 234 distinct
logical files. My naive #-strip gave 304/234-exist. If compositing explains the gap, the
normalizer must land on 234 exactly. If it lands anywhere else, one of us is wrong and I say so.

Run: python platform/architecture/_mkt_measure3.py
"""

import json
import os
import re
import subprocess
from collections import Counter

REPO = "C:/Users/Prekzursil/source/ast-integrate"


def norm_refs(value):
    """Split a free-text output_schema value into candidate logical schema paths."""
    if value is None:
        return []
    if isinstance(value, list):
        parts = []
        for v in value:
            parts.extend(norm_refs(v))
        return parts
    s = str(value)
    out = []
    # split on ' + ' conjunctions and ' and ' / ',' separators used in the catalog
    for chunk in re.split(r"\s+\+\s+|\s*;\s*", s):
        chunk = chunk.strip()
        if not chunk:
            continue
        # drop trailing parenthetical prose
        chunk = re.sub(r"\s*\([^)]*\)\s*$", "", chunk).strip()
        # drop JSON-Pointer fragment
        chunk = chunk.split("#")[0].strip()
        out.append(chunk)
    return out


def main():
    with open(
        os.path.join(REPO, "command-center/WORK-UNIT-CATALOG.json"), encoding="utf-8"
    ) as f:
        cat = json.load(f)
    wu = cat["work_units"]

    logical, refcount = set(), 0
    for u in wu:
        parts = norm_refs(u.get("output_schema"))
        refcount += 1  # one reference per unit
        for p in parts:
            logical.add(p)
    print("=== (a) COMPOSITING-AWARE NORMALIZER (control for the sibling's 234) ===")
    print("  units with an output_schema reference :", refcount)
    fs = {p for p in logical if not p.startswith("http")}
    url = logical - fs
    print("  distinct logical refs (all)          :", len(logical))
    print("  ... URL-shaped                       :", len(url), sorted(url))
    print("  ... filesystem-shaped                :", len(fs))
    exists = {p for p in fs if os.path.exists(os.path.join(REPO, p))}
    print("  ... that EXIST on disk               :", len(exists))
    missing = sorted(fs - exists)
    print("  ... that DO NOT exist                :", len(missing))
    for m in missing[:25]:
        print("        MISSING:", m)
    print(
        "  SIBLING CLAIM = 234 distinct logical files; my normalizer =",
        len(logical),
        "->",
        "MATCH" if len(logical) == 234 else "MISMATCH",
    )
    print()

    print("=== (a2) how many output_schema values are COMPOSITE / carry prose? ===")
    comp = [u for u in wu if "+" in str(u.get("output_schema", ""))]
    paren = [u for u in wu if re.search(r"\([^)]*\)", str(u.get("output_schema", "")))]
    frag = [u for u in wu if "#" in str(u.get("output_schema", ""))]
    print("  units whose output_schema contains '+'   :", len(comp))
    print("  units whose output_schema contains '(..)':", len(paren))
    print("  units whose output_schema contains '#'   :", len(frag))
    print(
        "  example composite:",
        (comp[0]["id"], comp[0]["output_schema"]) if comp else None,
    )
    print()

    print("=== (b) PLUGIN / MARKETPLACE CONTROL PLANES the catalog NAMES ===")
    named = sorted({p for p in fs})
    interesting_pref = (
        "tools/plugin",
        "tools/marketplace",
        ".claude-plugin",
        "tools/foundry",
        "tools/council",
        "release",
        "platform/",
        "command-center/",
    )
    byp = Counter()
    for p in named:
        for ip in interesting_pref:
            if p.startswith(ip):
                byp[ip] += 1
                break
        else:
            byp["<other>"] += 1
    for k, v in byp.most_common():
        print(f"  {k:26s} {v}")
    print()
    print("  do those dirs EXIST on disk?")
    for d in (
        "tools/plugin",
        "tools/marketplace",
        ".claude-plugin",
        "tools/foundry",
        "release",
        "platform/workflows",
        "command-center/schema",
        "command-center/receipts",
        "command-center/wfa",
    ):
        full = os.path.join(REPO, d)
        n = 0
        if os.path.isdir(full):
            for dp, dn, fn in os.walk(full):
                dn[:] = [x for x in dn if x not in {".git", "__pycache__"}]
                n += len(fn)
        print(f"    {d:30s} exists={os.path.isdir(full)!s:5s} files={n}")
    print()

    print("=== (c) which PHASES name plugin/marketplace artifacts? ===")
    ph = Counter()
    for u in wu:
        s = str(u.get("output_schema", "")) + " " + str(u.get("output_path", ""))
        if "plugin" in s or "marketplace" in s or ".claude-plugin" in s:
            ph[str(u.get("phase"))] += 1
    print("  units naming plugin/marketplace, by phase:", dict(sorted(ph.items())))
    print("  total such units:", sum(ph.values()))
    print()

    print("=== (d) release/ + .claude-plugin/ tracked inventory ===")
    for area in ("release", ".claude-plugin", "tools/plugin", "tools/marketplace"):
        r = subprocess.run(
            ["git", "-C", REPO, "ls-files", area], capture_output=True, text=True
        )
        files = [x for x in r.stdout.split("\n") if x]
        print(f"  git ls-files {area:22s} -> {len(files)} files")
        for f in files[:12]:
            print("      ", f)
    print()
    print("SUCCESS:mkt-measure3")


if __name__ == "__main__":
    main()
