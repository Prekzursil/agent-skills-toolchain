"""Fifth pass: (1) node_modules bloat in the candidate package payload,
(2) does the repo-owned splitter keep BOTH halves of a ' + ' composite output_schema?

(2) is the fairness control on my own claim. If parse_schema_ref() returns only the FIRST
schema of a composite, then the sibling's "0 unresolved" is scoped to first-halves and my
40 second-half misses are real. If it returns both, my finding is wrong and I say so.

Run: python platform/architecture/_mkt_measure5.py
"""

import json
import os
import sys

REPO = "C:/Users/Prekzursil/source/ast-integrate"
sys.path.insert(0, os.path.join(REPO, "platform", "lib"))


def main():
    print("=== (1) node_modules / cache bloat inside the candidate payload ===")
    for top in ("tools", "skills", ".agents", "hooks", "platform", "command-center"):
        tot = nm = cache = 0
        for dp, dn, fn in os.walk(os.path.join(REPO, top)):
            parts = dp.replace("\\", "/").split("/")
            tot += len(fn)
            if "node_modules" in parts:
                nm += len(fn)
            if any(
                p in ("__pycache__", ".pytest_cache", ".ruff_cache", ".venv")
                for p in parts
            ):
                cache += len(fn)
        print(
            f"  {top:18s} files={tot:6d}  in node_modules={nm:6d}  in caches={cache:5d}"
            f"  shippable={tot - nm - cache:6d}"
        )
    print()

    print(
        "=== (2) FAIRNESS CONTROL: what does parse_schema_ref() do with a composite? ==="
    )
    from receipt_schema_gate import parse_schema_ref  # noqa: E402

    with open(
        os.path.join(REPO, "command-center/WORK-UNIT-CATALOG.json"), encoding="utf-8"
    ) as f:
        wu = json.load(f)["work_units"]
    comp = [u for u in wu if " + " in str(u.get("output_schema", ""))]
    print("  composite units:", len(comp))
    for u in comp[:6]:
        r = parse_schema_ref(u["output_schema"])
        print(f"    {u['id']}  raw={u['output_schema'][:96]!r}")
        print(f"         parsed -> {r!r}")
    print()

    # Does any parsed result mention the SECOND schema of a composite?
    second_kept = 0
    seconds = []
    for u in comp:
        raw = str(u["output_schema"])
        second = raw.split(" + ", 1)[1]
        second_path = second.split("#")[0].split(" (")[0].strip()
        r = parse_schema_ref(raw)
        blob = json.dumps(r, default=str)
        if second_path and second_path in blob:
            second_kept += 1
        seconds.append(second_path)
    print(
        f"  composites whose SECOND schema survives parse_schema_ref(): {second_kept}"
        f" / {len(comp)}"
    )
    uniq = sorted(set(seconds))
    print(f"  distinct second-half schema paths: {len(uniq)}")
    miss = [p for p in uniq if not os.path.exists(os.path.join(REPO, p))]
    print(f"  ... of which have NO artifact on disk: {len(miss)}")
    for m in miss:
        print("      NO-ARTIFACT:", m)
    print()

    print("=== (3) profile= selector: does the resolver honour it? ===")
    prof = [u for u in wu if " profile=" in str(u.get("output_schema", ""))]
    print("  units with ' profile=':", len(prof))
    for u in prof[:4]:
        print(f"    {u['id']} raw={u['output_schema'][:110]!r}")
        print(f"       parsed -> {parse_schema_ref(u['output_schema'])!r}")
    print()
    print("SUCCESS:mkt-measure5")


if __name__ == "__main__":
    main()
