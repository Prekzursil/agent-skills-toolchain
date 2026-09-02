#!/usr/bin/env python3
"""Probe 1: every schema field declares SHA-ANCHORED or SAMPLED-AT-TIME.

Also: a live capture's sampled objects carry sampled_at, and SHA-ANCHORED
objects do not.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))
sys.path.insert(0, str(HERE))

from baseline.anchoring import (  # noqa: E402
    ANCHORED_FIELD_NAMES,
    SAMPLED_FIELD_NAMES,
    instance_sampled_timestamp_gaps,
    schema_anchoring_gaps,
)
from baseline.capture import CLASS_INDEX, capture  # noqa: E402
import fixtures as F  # noqa: E402

OUT = HERE / "probe1-anchoring.raw.json"
SCHEMA_REL = "command-center/schema/baseline-snapshot.schema.json"
REQUIRED_CLASSES = (
    "repo",
    "branches",
    "worktrees",
    "live_deployments",
    "caches",
    "plugin_settings",
    "marketplaces",
    "hooks",
    "skills",
    "mcps",
)


def main() -> int:
    schema_path = REPO / SCHEMA_REL
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    gaps = schema_anchoring_gaps(schema)
    props = schema.get("properties") or {}
    missing_props = [n for n in list(ANCHORED_FIELD_NAMES) + list(SAMPLED_FIELD_NAMES) if n not in props]
    index_classes = [row["class"] for row in CLASS_INDEX]
    class_gaps = [c for c in REQUIRED_CLASSES if c not in index_classes]

    with tempfile.TemporaryDirectory(prefix="tst0023-p1-") as td:
        root = Path(td) / "repo"
        sha = F.build_clean_fixture(root)
        snap = capture(root, sha)
        inst_gaps = instance_sampled_timestamp_gaps(snap, schema)

    payload = {
        "probe": "probe1-every-field-declares-anchoring",
        "unit_id": "TST-0023",
        "schema": SCHEMA_REL,
        "schema_anchoring_gaps": gaps,
        "missing_declared_properties": missing_props,
        "class_index_missing": class_gaps,
        "instance_timestamp_gaps": inst_gaps,
        "pinned_sha": snap.get("pinned_sha"),
        "kind": snap.get("kind"),
        "anchored_field_count": len(ANCHORED_FIELD_NAMES),
        "sampled_field_count": len(SAMPLED_FIELD_NAMES),
        "sampled_objects_with_timestamp": [
            name
            for name in SAMPLED_FIELD_NAMES
            if name not in {"kind", "captured_at"}
            and isinstance(snap.get(name), dict)
            and snap[name].get("sampled_at")
        ],
        "pass": not gaps
        and not missing_props
        and not class_gaps
        and not inst_gaps
        and snap.get("kind") == "BASELINE"
        and snap.get("repo", {}).get("anchoring_kind") == "SHA-ANCHORED"
        and snap.get("hooks_tree", {}).get("count") == 1
        and snap.get("caches", {}).get("anchoring_kind") == "SAMPLED-AT-TIME",
    }
    OUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2))
    if not payload["pass"]:
        print("FAILED:TST-0023-probe1 every field must declare anchoring kind")
        return 1
    print(
        f"schema_gaps=0 classes={len(index_classes)} "
        f"sampled_ts={len(payload['sampled_objects_with_timestamp'])} "
        f"kind={snap.get('kind')}"
    )
    print("SUCCESS:TST-0023-probe1 every field declares its anchoring kind")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
