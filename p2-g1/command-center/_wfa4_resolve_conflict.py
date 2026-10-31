"""Resolve the self-contradicting catalogue detector + read sibling registries."""

import json
import pathlib
import re

CORPUS = pathlib.Path(r"C:/Users/Prekzursil/.claude/harness-restore-20260806")
REGDIR = pathlib.Path(r"C:/Users/Prekzursil/source/ast-integrate/platform/registry")

reg = json.loads(
    (CORPUS / "08-WORKFLOW-CANDIDATE-REGISTRY.json").read_text(encoding="utf-8")
)
cands = reg["candidates"]
DARK = [
    "codex-audit",
    "codex-brainstorm",
    "codex-coordinate",
    "codex-curate",
    "codex-discuss",
    "codex-fix",
    "codex-governance",
    "codex-review",
    "codex-triage",
]
print("=== which id/name fields actually contain each dark-suite token? ===")
for d in DARK:
    pat = re.compile(rf"\b{re.escape(d)}\b")
    hits = [
        (c["id"], c["name"], c["family"])
        for c in cands
        if pat.search(c["id"]) or pat.search(c["name"])
    ]
    print(f"  {d:20s} -> {hits}")

print(
    "\n=== so where did the earlier substring detector fire? (re-run its exact regex) ==="
)
blob = json.dumps(cands)
for d in DARK:
    m = re.search(rf'"(?:id|name)"\s*:\s*"[^"]*\b{re.escape(d)}\b[^"]*"', blob)
    print(f"  {d:20s} -> {m.group(0) if m else None}")

print("\n=== SIBLING REGISTRIES ===")
for p in sorted(REGDIR.glob("workflow-candidates-*.json")):
    try:
        doc = json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:  # noqa: BLE001
        print(f"{p.name}: UNPARSEABLE {e}")
        continue
    if isinstance(doc, list):
        n = len(doc)
        sample = doc[:3]
        keys = sorted({k for e in doc if isinstance(e, dict) for k in e})
        ids = [e.get("id") for e in doc if isinstance(e, dict)]
    else:
        n = "dict"
        sample = doc
        keys = sorted(doc.keys())
        ids = []
    print(f"\n--- {p.name}  bytes={p.stat().st_size}  entries={n}")
    print(f"    keys={keys[:24]}")
    print(f"    ids={ids[:40]}")
    if n in ("dict",) or (isinstance(n, int) and n <= 3):
        print("    RAW:", json.dumps(sample, indent=1)[:1200])
