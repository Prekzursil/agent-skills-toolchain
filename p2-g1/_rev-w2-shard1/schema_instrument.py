#!/usr/bin/env python3
"""Reviewer schema instrument v2: distinguish post-delivery schema movement
from genuine content violation.

Instruments:
  A. declared shim (absolute file:// ref) -> source-tree control plane  [v1, done]
  B. worktree platform/schema/artifact-class-profiles.schema.json $defs  [new]
  C. what the estate resolver resolve() actually points at

Verdict rule: unit schema-check passes iff artifact validates under the
WORKTREE control-plane schema for its class. Source-tree-only failures are
reported as cross-tree drift (program-level finding), not unit defects.
"""
import json
import sys
from pathlib import Path

import jsonschema

REPO = Path(r"C:\Users\Prekzursil\p2-g1")
SRC_PROFILES = Path(r"C:\Users\Prekzursil\source\ast-integrate\platform\schema\artifact-class-profiles.schema.json")
WT_PROFILES = REPO / "platform" / "schema" / "artifact-class-profiles.schema.json"
IDS = [
    "ADV-0037", "ADV-0038", "ADV-0040", "ADV-0090", "ADV-0091", "ADV-0096",
    "ADV-0100", "ADV-0109", "ADV-0110", "ADV-0117", "ADV-0119", "ADV-0123",
]


def sha(p):
    import hashlib

    return hashlib.sha256(p.read_bytes().replace(b"\r\n", b"\n")).hexdigest()[:16]


def defs_valid(art, profiles_doc, cls):
    """Validate against profiles $defs/<cls> keeping internal refs local."""
    if cls not in (profiles_doc.get("$defs") or {}):
        return [f"class {cls} absent from profiles $defs"]
    wrapper = {
        "allOf": [{"$ref": f"#/$defs/{cls}"}],
        "$defs": profiles_doc.get("$defs") or {},
    }
    return [
        f"{'/'.join(map(str, e.absolute_path)) or '<root>'}: {e.message}"
        for e in jsonschema.validators.validator_for(wrapper)(wrapper).iter_errors(art)
    ]


def main() -> int:
    cat = json.loads((REPO / "command-center" / "WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
    wu = {x["id"]: x for x in cat["work_units"]}

    same = sha(SRC_PROFILES) == sha(WT_PROFILES)
    print(f"control-plane schema: source={sha(SRC_PROFILES)} worktree={sha(WT_PROFILES)} identical={same}")
    src_doc = json.loads(SRC_PROFILES.read_text(encoding="utf-8"))
    wt_doc = json.loads(WT_PROFILES.read_text(encoding="utf-8"))
    src_defs = set(src_doc.get("$defs") or {})
    wt_defs = set(wt_doc.get("$defs") or {})
    if src_defs - wt_defs:
        print("classes missing in worktree profiles:", sorted(src_defs - wt_defs))
    if wt_defs - src_defs:
        print("classes only in worktree profiles:", sorted(wt_defs - src_defs))

    # C: what the estate resolver points at
    sys.path.insert(0, str(REPO / "platform" / "lib"))
    import schema_resolver as SR

    sample = SR.resolve("command-center/schema/benchmark-integrity.schema.json", SR.load_registry())
    print("resolver sample ->", getattr(sample, "as_dict", lambda: sample)())

    print("\nper-unit: [W]=worktree-profiles result  [S]=source-tree result")
    worst = 0
    for uid in IDS:
        u = wu[uid]
        art = json.loads((REPO / u["output_path"]).read_text(encoding="utf-8"))
        shim = json.loads((REPO / u["output_schema"]).read_text(encoding="utf-8"))
        cls = shim.get("x-artifact-class")
        we = defs_valid(art, wt_doc, cls)
        se = defs_valid(art, src_doc, cls)
        verdict = "WT-PASS" if not we else f"WT-FAIL({len(we)})"
        worst = max(worst, len(we))
        print(f"{uid}: class={cls} [W]{verdict} [S]{'PASS' if not se else 'FAIL(' + str(len(se)) + ')'}")
        if we:
            for e in we[:4]:
                print(f"    W-err: {e[:170]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
