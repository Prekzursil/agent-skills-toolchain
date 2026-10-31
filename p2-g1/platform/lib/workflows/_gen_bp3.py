"""Emit the bp-3 blueprint range (doc-order 25-36 of the 96 built-ins) as JSON on disk.

Run from the repo root::

    python platform/lib/workflows/_gen_bp3.py

Writes twelve blueprints to ``platform/workflows/`` plus the shared subworkflows to
``platform/workflows/_shared/``, then prints a terminal-state marker. The JSON files are the
deliverable; this script is their provenance, so a reviewer can see that no blueprint was
produced by copying a sibling and renaming it.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from _bp3_common import SHARED_DIR, WORKFLOW_DIR  # noqa: E402


def _collect() -> tuple[list[dict], list[dict]]:
    blueprints: list[dict] = []
    shared: list[dict] = []
    for mod_name in ("_gen_bp3_a", "_gen_bp3_b", "_gen_bp3_c"):
        try:
            mod = __import__(mod_name)
        except ModuleNotFoundError:
            continue
        blueprints.extend(fn() for fn in getattr(mod, "BLUEPRINTS", []))
        shared.extend(fn() for fn in getattr(mod, "SHARED", []))
    return blueprints, shared


def main() -> int:
    WORKFLOW_DIR.mkdir(parents=True, exist_ok=True)
    SHARED_DIR.mkdir(parents=True, exist_ok=True)
    blueprints, shared = _collect()

    ids = [b["id"] for b in blueprints]
    if len(set(ids)) != len(ids):
        print(f"FAILED:blueprints/bp-3 duplicate blueprint id in {ids}")
        return 1

    written: list[str] = []
    for doc in blueprints:
        path = WORKFLOW_DIR / f"{doc['id']}.workflow.json"
        path.write_text(json.dumps(doc, indent=1) + "\n", encoding="utf-8")
        written.append(str(path.relative_to(WORKFLOW_DIR.parents[1])))
    for doc in shared:
        path = SHARED_DIR / f"{doc['id']}.subworkflow.json"
        path.write_text(json.dumps(doc, indent=1) + "\n", encoding="utf-8")
        written.append(str(path.relative_to(WORKFLOW_DIR.parents[1])))

    flagship = [b["id"] for b in blueprints if b.get("flagship")]
    print(f"blueprints written : {len(blueprints)}")
    print(f"subworkflows       : {len(shared)}")
    print(f"flagship           : {len(flagship)}")
    for w in written:
        print(f"  {w}")
    print(f"SUCCESS:blueprints/bp-3 emitted={len(written)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
