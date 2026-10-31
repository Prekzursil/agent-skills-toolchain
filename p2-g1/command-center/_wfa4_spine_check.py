"""Prove the canonical partition spine is SHARED, and measure overlap with siblings.

Sibling wfa-2 declared its range as 'document order over the 284 ### `<id>` entries of
08-WORKFLOW-ARCHAEOLOGY-AND-SOURCE-CATALOG.md'. This unit used JSON array order of the
companion 08-WORKFLOW-CANDIDATE-REGISTRY.json. If the two orders are identical, the
partition is provably shared and slice 97-128 is unambiguous.
"""

import json
import pathlib
import re

CORPUS = pathlib.Path(r"C:/Users/Prekzursil/.claude/harness-restore-20260806")
MD = CORPUS / "08-WORKFLOW-ARCHAEOLOGY-AND-SOURCE-CATALOG.md"
JS = CORPUS / "08-WORKFLOW-CANDIDATE-REGISTRY.json"
REGDIR = pathlib.Path(r"C:/Users/Prekzursil/source/ast-integrate/platform/registry")

md = MD.read_text(encoding="utf-8", errors="replace")
json_order = [c["id"] for c in json.loads(JS.read_text(encoding="utf-8"))["candidates"]]

# document order: headings shaped '### `<id>` - <name>'
head = re.compile(r"^###\s+`([^`]+)`", re.M)
doc_order = [m.group(1) for m in head.finditer(md)]
print(f"doc-order headings = {len(doc_order)}   json-array entries = {len(json_order)}")

# CONTROL: the extractor must find a heading we have literally read (pos 1)
assert "wf-saved-agentic-repair-reliability" in doc_order, "heading extractor is broken"
# CONTROL: it must NOT invent one
assert "wf-saved-does-not-exist-xyz" not in doc_order

identical = doc_order == json_order
print(f"orders IDENTICAL = {identical}")
if not identical:
    diffs = [
        (i + 1, a, b) for i, (a, b) in enumerate(zip(doc_order, json_order)) if a != b
    ]
    print(f"  first 10 positional differences: {diffs[:10]}")
    print(f"  set difference doc-json: {set(doc_order) - set(json_order)}")
    print(f"  set difference json-doc: {set(json_order) - set(doc_order)}")

LO, HI = 97, 128
mine = json_order[LO - 1 : HI]
print(f"\nmy slice ({LO}-{HI}) n={len(mine)}")
print("  doc-order slice equals json-order slice:", doc_order[LO - 1 : HI] == mine)

print("\n=== overlap with sibling registry files ===")
mine_set = set(mine)
# also index the whole spine so we can map any sibling id -> position
pos_of = {cid: i + 1 for i, cid in enumerate(json_order)}
for p in sorted(REGDIR.glob("workflow-candidates-*.json")):
    if p.name == "workflow-candidates-4.json":
        continue
    try:
        doc = json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:  # noqa: BLE001
        print(f"{p.name}: UNPARSEABLE ({e})")
        continue
    entries = doc if isinstance(doc, list) else doc.get("candidates", [])
    sib_ids = set()
    sib_pos = []
    for e in entries:
        if not isinstance(e, dict):
            continue
        for k in ("id", "prior_id", "source_id", "canonical_id", "name"):
            v = e.get(k)
            if isinstance(v, str):
                sib_ids.add(v)
                if v in pos_of:
                    sib_pos.append(pos_of[v])
        # some siblings may nest the spine id
        for k, v in e.items():
            if isinstance(v, str) and v in pos_of:
                sib_ids.add(v)
                sib_pos.append(pos_of[v])
    inter = sib_ids & mine_set
    rng = f"{min(sib_pos)}-{max(sib_pos)}" if sib_pos else "no-spine-ids"
    print(
        f"  {p.name:28s} entries={len(entries):3d}  spine-ids={len(set(sib_pos)):3d} "
        f"spine-range={rng:12s} OVERLAP_WITH_MINE={sorted(inter) if inter else 'NONE'}"
    )

out = pathlib.Path(
    r"C:/Users/Prekzursil/source/ast-integrate/command-center/_wfa4_spine.json"
)
out.write_text(
    json.dumps(
        {
            "doc_order_count": len(doc_order),
            "json_order_count": len(json_order),
            "orders_identical": identical,
            "slice_lo": LO,
            "slice_hi": HI,
            "slice_ids": mine,
        },
        indent=1,
    ),
    encoding="utf-8",
)
print(f"\nwrote {out}")
print(
    "SUCCESS:wfa4-spine-check"
    if identical
    else "PARTIAL:wfa4-spine-check orders differ"
)
