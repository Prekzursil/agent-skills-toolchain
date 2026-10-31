"""Round-1 extraction pass 2: correct field names; full verdict vectors; equivalence."""

import json
import os

PO = r"C:/Users/Prekzursil/source/ast-integrate/command-center/casualty/probe-output"


def L(n):
    return os.path.join(PO, n)


def strip_sentinel(txt, begin):
    i = txt.find(begin)
    if i >= 0:
        txt = txt[i + len(begin) :]
    j = txt.rfind("}")
    return txt[: j + 1]


print("=" * 20, "0021 P2b outcome vectors (ORIGINAL vs RERUN)", "=" * 20)
vecs = {}
for tag in ("ORIGINAL", "RERUN"):
    rb = json.load(open(L(f"adv0021_results_b.{tag}.json"), encoding="utf-8"))
    vecs[tag] = [(r["case"], r["outcome"]) for r in rb["results"]]
print("IDENTICAL_OUTCOME_VECTOR =", vecs["ORIGINAL"] == vecs["RERUN"])
for c, o in vecs["ORIGINAL"]:
    print(f"  {c:38s} {o}")

print()
print("=" * 20, "0021 P2b full detail (ORIGINAL)", "=" * 20)
rb = json.load(open(L("adv0021_results_b.ORIGINAL.json"), encoding="utf-8"))
for r in rb["results"]:
    print(f"* {r['case']} -> {r['outcome']}\n    {r['detail'][:420]}")

print()
print("=" * 20, "0022 P1 summary + wide control (both tags)", "=" * 20)
for tag in ("ORIGINAL", "RERUN"):
    raw = open(L(f"adv0022_probe1_out.{tag}.txt"), encoding="utf-8").read()
    d = json.loads(strip_sentinel(raw, "ADV0022_JSON_BEGIN"))
    print(f"--- {tag} keys={list(d.keys())}")
    print(
        "  detector_integrity.discriminates =", d["detector_integrity"]["discriminates"]
    )
    print("  meta =", json.dumps(d["meta"]))
    for sect in (
        "narrow_component",
        "wide_component_control",
        "wide_component",
        "control",
    ):
        if sect in d:
            blk = d[sect]
            print(f"  {sect}.declared = {blk.get('declared')}")
            for op in blk.get("ops", []):
                print(
                    f"    {op['op']:26s} {op['outcome']:10s} escaped={op.get('escaped_declaration')} tool={op.get('required_tool')}"
                )
    print("  summary =", json.dumps(d.get("summary"), indent=1)[:2500])

print()
print("=" * 20, "0022 P2 rest of file", "=" * 20)
raw = open(L("adv0022_probe2_out.ORIGINAL.txt"), encoding="utf-8").read()
d = json.loads(strip_sentinel(raw, "ADV0022_P2_BEGIN"))
print("keys:", list(d.keys()))
for k, v in d.items():
    if k == "checks":
        for ck, cv in v.items():
            n = len(cv) if isinstance(cv, list) else cv
            print(
                f"  checks.{ck}: {'list[%d]' % len(cv) if isinstance(cv, list) else json.dumps(cv)[:400]}"
            )
            if (
                isinstance(cv, list)
                and ck != "_control_scanner_finds_known_present_callers"
            ):
                for it in cv[:12]:
                    print("      -", str(it)[:250])
    else:
        print(f"  {k} = {json.dumps(v)[:1200]}")
