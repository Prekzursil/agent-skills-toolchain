"""Measure workflow `id` collisions across platform/workflows/ (D4 probe).

Scope: recursive rglob('*.json') under WORKFLOWS_ROOT -- NOT a depth-1 walk.
Identity key is `id` per platform/schema/workflow-dsl.schema.json required
['dsl_version','id','name','version','stages'].  Status/report JSON files that
are not workflow documents are counted separately, never folded into a pass.
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

WORKFLOWS_ROOT = Path("C:/Users/Prekzursil/source/ast-integrate/platform/workflows")


def is_workflow_doc(doc: object) -> bool:
    return (
        isinstance(doc, dict)
        and isinstance(doc.get("id"), str)
        and bool(doc.get("id"))
        and "dsl_version" in doc
        and "stages" in doc
    )


def main() -> int:
    by_id: dict[str, list[str]] = defaultdict(list)
    non_workflow: list[str] = []
    unparsable: list[str] = []
    total = 0

    for p in sorted(WORKFLOWS_ROOT.rglob("*.json")):
        total += 1
        rel = str(p.relative_to(WORKFLOWS_ROOT)).replace("\\", "/")
        try:
            doc = json.loads(p.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001
            unparsable.append(f"{rel}: {exc}")
            continue
        if not is_workflow_doc(doc):
            non_workflow.append(rel)
            continue
        by_id[str(doc["id"])].append(rel)

    dupes = {k: v for k, v in by_id.items() if len(v) > 1}

    print(f"SCOPE: recursive rglob('*.json') under {WORKFLOWS_ROOT}")
    print(f"json files walked          : {total}")
    print(f"workflow documents         : {sum(len(v) for v in by_id.values())}")
    print(f"distinct workflow ids      : {len(by_id)}")
    print(f"non-workflow json (status) : {len(non_workflow)}")
    print(f"unparsable files           : {len(unparsable)}")
    print(f"COLLIDING IDS              : {len(dupes)}")
    for wid, paths in sorted(dupes.items()):
        print(f"\n  id={wid}  ({len(paths)} files)")
        for path in paths:
            doc = json.loads((WORKFLOWS_ROOT / path).read_text(encoding="utf-8"))
            stages = doc.get("stages")
            nstages = len(stages) if isinstance(stages, list) else "n/a"
            print(f"    - {path}  stages={nstages}")
    for line in unparsable:
        print(f"  UNPARSABLE {line}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
