#!/usr/bin/env python3
"""Probe 1: generated-artifact marking + two-run byte-identical determinism."""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import generator as G  # noqa: E402

REQUIRED_CLASSES = {
    "plugin_manifest",
    "marketplace_entry",
    "skill_deployment",
    "hook_deployment",
    "rule_deployment",
    "docs",
    "workflow_catalog",
    "council_catalog",
}
REQUIRED_DEFS = {
    "plugin_manifest",
    "marketplace_entry",
    "skill",
    "hook",
    "rule",
    "doc",
    "workflow_blueprint",
    "council_preset",
    "workflow_catalog",
    "council_catalog",
}


def main() -> int:
    schema = G.load_schema()
    defs = schema.get("definitions") or {}
    missing_defs = sorted(REQUIRED_DEFS - set(defs))
    if missing_defs:
        print(f"FAILED:ARC-0010-probe1 schema missing definitions {missing_defs}")
        return 1
    registry = G.load_default_registry()
    identical, n = G.two_run_identical(registry)
    print(f"determinism two_run_identical={identical} files={n}")
    if not identical or n < 8:
        print("FAILED:ARC-0010-probe1 determinism contract broken")
        return 1
    files = G.generate(registry)
    classes = set()
    missing_header = []
    for rel, raw in sorted(files.items()):
        prov = G.parse_provenance(raw)
        if not prov:
            missing_header.append(rel)
            continue
        rid = prov.get("registry_id")
        ver = prov.get("generator_version")
        gid = prov.get("generator_id")
        cls = prov.get("artifact_class")
        print(
            f"mark {rel} registry_id={rid} generator_id={gid} "
            f"generator_version={ver} artifact_class={cls}"
        )
        if rid and ver and gid and cls:
            classes.add(cls)
        else:
            missing_header.append(rel)
        if gid != G.GENERATOR_ID or ver != G.GENERATOR_VERSION:
            print(f"FAILED:ARC-0010-probe1 provenance identity mismatch on {rel}")
            return 1
    if missing_header:
        print(f"FAILED:ARC-0010-probe1 missing provenance {missing_header}")
        return 1
    absent = sorted(REQUIRED_CLASSES - classes)
    if absent:
        print(f"FAILED:ARC-0010-probe1 missing artifact classes {absent}")
        return 1
    print(f"marked={len(files)} classes={sorted(classes)}")
    print("SUCCESS:ARC-0010-probe1 generated-artifact marking and determinism")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
