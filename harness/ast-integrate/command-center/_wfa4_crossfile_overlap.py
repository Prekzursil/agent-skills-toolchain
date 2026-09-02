"""Cross-file overlap check across all five unit registries (mechanical, not judgement)."""

import json
import pathlib
import re

REGDIR = pathlib.Path(r"C:/Users/Prekzursil/source/ast-integrate/platform/registry")
files = sorted(REGDIR.glob("workflow-candidates-[0-9].json"))
data = {}
for p in files:
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:  # noqa: BLE001
        print(f"{p.name}: UNPARSEABLE {e}")
        continue
    rows = d if isinstance(d, list) else d.get("candidates", [])
    data[p.name] = rows

print(f"{'file':34s} {'entries':>7s} {'skeleton?':>10s} {'idx-range':>12s}")
for n, rows in data.items():
    sk = any(
        "not yet measured" in json.dumps(r).lower() or "SKELETON" in json.dumps(r)
        for r in rows
    )
    idxs = [
        r.get("registry_index")
        for r in rows
        if isinstance(r.get("registry_index"), int)
    ]
    rng = f"{min(idxs)}-{max(idxs)}" if idxs else "none"
    print(f"{n:34s} {len(rows):7d} {str(sk):>10s} {rng:>12s}")


def keyset(rows):
    """Identity keys: registry_index, source_registry_id, and the bare skill/workflow name."""
    idx, sid, nm = set(), set(), set()
    for r in rows:
        if isinstance(r, dict):
            if isinstance(r.get("registry_index"), int):
                idx.add(r["registry_index"])
            if isinstance(r.get("source_registry_id"), str):
                sid.add(r["source_registry_id"])
            n = r.get("name")
            if isinstance(n, str) and "not yet measured" not in n.lower():
                nm.add(
                    re.sub(
                        r"^(skills?/|\.agents/skills/|exec-|wf-saved-)", "", n
                    ).strip()
                )
    return idx, sid, nm


print("\npairwise overlap (registry_index / source_registry_id / normalised name):")
names = list(data)
clean = True
for i in range(len(names)):
    for j in range(i + 1, len(names)):
        a, b = names[i], names[j]
        ia, sa, na = keyset(data[a])
        ib, sb, nb = keyset(data[b])
        oi, os_, on = ia & ib, sa & sb, na & nb
        if oi or os_ or on:
            clean = False
            print(
                f"  {a} x {b}: idx={sorted(oi)} sid={sorted(os_)[:6]} name={sorted(on)[:6]}"
            )
        else:
            print(f"  {a} x {b}: NONE")

# CONTROL: the detector must find a deliberately injected collision
ctl_a = [{"registry_index": 999, "name": "collision-probe", "source_registry_id": "x"}]
ctl_b = [{"registry_index": 999, "name": "collision-probe", "source_registry_id": "x"}]
ia, sa, na = keyset(ctl_a)
ib, sb, nb = keyset(ctl_b)
assert (ia & ib) and (sa & sb) and (na & nb), (
    "overlap detector cannot see a known collision"
)
print("\nCONTROL: injected collision detected on all three keys = True")

total_md = sum(
    1
    for rows in data.values()
    for r in rows
    if isinstance(r, dict) and r.get("materially_distinct")
)
print(
    f"\nprogram-wide materially_distinct across the five files = {total_md} (floor is 160)"
)
print(
    "SUCCESS:wfa4-crossfile-overlap"
    if clean
    else "PARTIAL:wfa4-crossfile-overlap collisions found"
)
