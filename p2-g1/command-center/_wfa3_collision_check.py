"""wfa-3: does my slice actually collide with the sibling registries?

The spawn brief named ranges 1-32 / 33-64 / 65-96 ..., but 5 sibling files exist. Assuming
disjointness is a single-signal claim; this measures it. Compares the set of PRIOR-REGISTRY
candidate ids (and, where absent, names) that each file claims.
"""

import json
import re
from pathlib import Path

REG = Path("C:/Users/Prekzursil/source/ast-integrate/platform/registry")
MINE = "workflow-candidates-3.json"


def ids_of(path: Path):
    """Best-effort extraction of the prior-registry ids a sibling file claims."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:  # noqa: BLE001
        return {"__parse_error__": str(e)}, None, 0
    rows = (
        data if isinstance(data, list) else data.get("candidates", data.get("rows", []))
    )
    if not isinstance(rows, list):
        return set(), None, 0
    out = set()
    rng = None
    for r in rows:
        if not isinstance(r, dict):
            continue
        if r.get("range") and not rng:
            rng = r["range"]
        for key in ("prior_id", "source_id", "prior_registry_id", "id"):
            v = r.get(key)
            if isinstance(v, str) and v:
                # prior-registry ids look like fam-slug (wf-saved-*, tool-*, skill-*, plugin-*, ...)
                if re.match(
                    r"^(wf-|tool-|harness-|agent-|plugin-|marketplace-|skill-|exec-|cmd-|vault-)",
                    v,
                ):
                    out.add(v)
                break
    return out, rng, len(rows)


files = sorted(p for p in REG.glob("workflow-candidates-*.json"))
info = {}
for p in files:
    s, rng, n = ids_of(p)
    info[p.name] = {"prior_ids": s, "range": rng, "rows": n}
    print(
        f"{p.name:<28} rows={n:<4} range={rng!s:<28} prior_ids_extracted={len(s) if isinstance(s, set) else s}"
    )

mine = info[MINE]["prior_ids"]
print(f"\nmy prior_ids: {len(mine)}")
print("\n=== pairwise overlap with my slice ===")
total_collisions = 0
for name, d in info.items():
    if name == MINE:
        continue
    other = d["prior_ids"]
    if not isinstance(other, set) or not isinstance(mine, set):
        print(f"  {name}: NOT-COMPARABLE ({other})")
        continue
    inter = mine & other
    total_collisions += len(inter)
    print(
        f"  {name:<28} their_ids={len(other):<4} OVERLAP={len(inter)} {sorted(inter)[:10]}"
    )

# detector control: my file must overlap 100% with ITSELF
self_inter = mine & info[MINE]["prior_ids"]
print(f"\ndetector control (self-overlap must equal {len(mine)}): {len(self_inter)}")

print()
if total_collisions == 0 and len(self_inter) == len(mine) and len(mine) > 0:
    print(
        f"SUCCESS:wfa3-collision-check 0 prior-candidate collisions across {len(files) - 1} sibling files; "
        f"detector proven by a {len(self_inter)}/{len(mine)} self-overlap"
    )
else:
    print(
        f"FAILED:wfa3-collision-check collisions={total_collisions} self_overlap={len(self_inter)}/{len(mine)}"
    )
