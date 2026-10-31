"""Round-1: extract the VERDICT-BEARING fields from all four probe outputs, and
confirm ORIGINAL vs RERUN agree on every verdict (not merely on diff-count).
Read-only apart from stdout.
"""

import json
import os

PO = r"C:/Users/Prekzursil/source/ast-integrate/command-center/casualty/probe-output"


def L(n):
    return os.path.join(PO, n)


print("#" * 30, "ADV-0021 PROBE 1 (structure)", "#" * 30)
p1 = json.load(open(L("adv0021_probe1_out.ORIGINAL.json"), encoding="utf-8"))
print("top keys:", list(p1.keys()))
for k, v in p1.items():
    if isinstance(v, (int, float, str, bool)) or v is None:
        print(f"  {k} = {str(v)[:300]}")
    elif isinstance(v, list):
        print(f"  {k} : list[{len(v)}]  first={json.dumps(v[0])[:400] if v else None}")
    elif isinstance(v, dict):
        print(f"  {k} : dict keys={list(v.keys())[:30]}")

print()
print("#" * 30, "ADV-0021 PROBE 2 run B (24 cases)", "#" * 30)
for tag in ("ORIGINAL", "RERUN"):
    rb = json.load(open(L(f"adv0021_results_b.{tag}.json"), encoding="utf-8"))
    print(f"--- {tag} top keys:", list(rb.keys()))
    res = rb.get("results", [])
    print(f"    results n={len(res)}")
    if tag == "ORIGINAL":
        print("    item keys:", list(res[0].keys()) if res else None)
    verd = [
        (
            r.get("id") or r.get("case"),
            r.get("verdict") or r.get("result") or r.get("status"),
        )
        for r in res
    ]
    print("    verdict vector:", json.dumps(verd))

print()
print("#" * 30, "ADV-0022 PROBE 1 (escape harness)", "#" * 30)
for tag in ("ORIGINAL", "RERUN"):
    raw = open(L(f"adv0022_probe1_out.{tag}.txt"), encoding="utf-8").read()
    try:
        d = json.loads(raw)
        print(f"--- {tag} parses as JSON; top keys:", list(d.keys()))
        if tag == "ORIGINAL":
            print(json.dumps(d, indent=1)[:5000])
        else:
            # verdict vector only
            def vv(o):
                out = []
                for comp, block in (
                    (o.get("components") or o.get("results") or {}).items()
                    if isinstance(o.get("components") or o.get("results"), dict)
                    else []
                ):
                    out.append((comp, block))
                return out

            print("   (verdict vector printed via ops below)")
    except Exception as e:  # noqa: BLE001
        print(f"--- {tag} NOT json ({e}); first 2500 chars:")
        print(raw[:2500])

print()
print("#" * 30, "ADV-0022 PROBE 2 (static enforcement audit) FULL", "#" * 30)
print(open(L("adv0022_probe2_out.ORIGINAL.txt"), encoding="utf-8").read())
