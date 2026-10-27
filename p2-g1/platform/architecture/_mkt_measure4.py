"""Fourth pass: settle the 234-vs-305 disagreement by NAMING the normalization rule,
and classify the 70 residual strings. Then inventory what a marketplace package would carry.

Run: python platform/architecture/_mkt_measure4.py
"""

import json
import os
import re
from collections import Counter

REPO = "C:/Users/Prekzursil/source/ast-integrate"


def strip_all(s):
    s = str(s)
    out = []
    for chunk in re.split(r"\s+\+\s+|\s*;\s*", s):
        c = chunk.strip()
        if not c:
            continue
        c = re.sub(r"\s*\([^)]*\)", "", c)  # any parenthetical prose
        c = c.split("#")[0]  # JSON-Pointer fragment
        c = re.sub(r"\s+profile=\S+.*$", "", c)  # ' profile=<name>' selector
        c = re.sub(r"\s+bucket=\S+.*$", "", c)
        c = c.strip().rstrip(",")
        if c:
            out.append(c)
    return out


def main():
    with open(
        os.path.join(REPO, "command-center/WORK-UNIT-CATALOG.json"), encoding="utf-8"
    ) as f:
        wu = json.load(f)["work_units"]

    raw = [str(u.get("output_schema")) for u in wu]
    print("=== NORMALIZATION LADDER (each row is a different convention) ===")
    print("  L0 total references (1 per unit)          :", len(raw))
    print("  L1 distinct raw strings                   :", len(set(raw)))
    print(
        "  L2 distinct after '#'-strip only          :",
        len({r.split("#")[0] for r in raw}),
    )
    lvl3 = set()
    for r in raw:
        lvl3.update(strip_all(r))
    print("  L3 distinct after full normalization      :", len(lvl3))
    fs = {p for p in lvl3 if not p.startswith("http")}
    ex = {p for p in fs if os.path.exists(os.path.join(REPO, p))}
    print("     ... filesystem-shaped                  :", len(fs))
    print("     ... EXIST on disk                      :", len(ex))
    print("     ... MISSING                            :", len(fs - ex))
    for m in sorted(fs - ex):
        print("         MISSING:", m)
    print()

    print("=== CLASSIFY the residual (why 234 != 305) ===")
    l2 = {r.split("#")[0] for r in raw}
    resid = sorted(
        p
        for p in l2
        if not os.path.exists(os.path.join(REPO, p)) and not p.startswith("http")
    )
    cls = Counter()
    for p in resid:
        if " profile=" in p:
            cls["carries ' profile=<name>' selector"] += 1
        elif "+" in p:
            cls["composite (' + ' joins 2+ schemas)"] += 1
        elif p.startswith(".claude-plugin/"):
            cls["names .claude-plugin/*.schema.json (does NOT exist)"] += 1
        elif "/" not in p:
            cls["prose, not a path (e.g. external standard)"] += 1
        else:
            cls["other"] += 1
    for k, v in cls.most_common():
        print(f"  {k:52s} {v}")
    print("  residual total:", len(resid))
    print()

    print("=== WHAT A PACKAGE WOULD CARRY (candidate plugin payload, measured) ===")

    def count(d, pred=None):
        full = os.path.join(REPO, d)
        n, b = 0, 0
        if not os.path.isdir(full):
            return 0, 0
        for dp, dn, fn in os.walk(full):
            dn[:] = [x for x in dn if x not in {".git", "__pycache__", ".pytest_cache"}]
            for f in fn:
                p = os.path.join(dp, f)
                if pred and not pred(p.replace("\\", "/")):
                    continue
                n += 1
                try:
                    b += os.path.getsize(p)
                except OSError:
                    pass
        return n, b

    rows = [
        ("platform/schema", lambda p: p.endswith(".schema.json")),
        (
            "platform/lib",
            lambda p: (
                p.endswith(".py") and not os.path.basename(p).startswith(("_", "test_"))
            ),
        ),
        (
            "platform/lib",
            lambda p: os.path.basename(p).startswith("_") and p.endswith(".py"),
        ),
        ("platform/council/protocols", None),
        ("platform/council/presets", None),
        ("platform/registry", None),
        ("command-center/schema", None),
        ("skills", None),
        ("hooks", None),
        ("agents", None),
        ("commands", None),
        ("rules", None),
        (".agents", None),
        ("tools", None),
        ("docs", None),
        ("ci", None),
        ("scripts", None),
    ]
    seen_lib = 0
    for d, pred in rows:
        n, b = count(d, pred)
        label = d
        if d == "platform/lib":
            seen_lib += 1
            label = d + ("  [runtime .py]" if seen_lib == 1 else "  [_probe/_gen .py]")
        print(f"  {label:44s} files={n:6d}  bytes={b:12,d}")
    print()
    print("SUCCESS:mkt-measure4")


if __name__ == "__main__":
    main()
