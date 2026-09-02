#!/usr/bin/env python3
"""Probe 1: preview file+permission declarations match post-update census.

TWO independent signals (catalog evidence_requirement):
  (1) preview.file_changes + preview.permission_diff, computed before any write
  (2) dest tree census + plugin.json permissions read back from disk
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
TOOLS = REPO / "tools"
sys.path.insert(0, str(TOOLS))

from marketplace.package import make_package  # noqa: E402
from marketplace.update import (  # noqa: E402
    apply_update,
    assert_preview_matches_actual,
    census_tree,
    effective_permissions_from_disk,
    preview_update,
    write_package_tree,
)
from plugin.permission_diff import Consent, MemoryConsentStore, independent_set_containment  # noqa: E402

PKG = "hello-skill"


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0087-probe1 {msg}")
    return 1


def main() -> int:
    installed = make_package(
        PKG,
        "1.0.0",
        extra_files={
            "skills/SKILL.md": b"# hello 1.0.0\n",
            "hooks/pre.json": b'{"id":"pre"}\n',
        },
        permissions=["fs:read:/pkg", "Read"],
        releases=["1.0.0", "1.1.0", "1.2.0"],
        changelog={"1.0.0": ["initial"]},
    )
    candidate = make_package(
        PKG,
        "1.2.0",
        extra_files={
            "skills/SKILL.md": b"# hello 1.2.0\nchanged\n",
            "docs/CHANGE.md": b"notes\n",
        },
        permissions=["fs:read:/pkg", "Read", "net:connect:api.example"],
        releases=["1.0.0", "1.1.0", "1.2.0"],
        changelog={
            "1.1.0": ["intermediate fix"],
            "1.2.0": ["add docs", "skill rewrite"],
        },
    )
    preview = preview_update(installed, candidate)
    if preview.version_delta != {"from": "1.0.0", "to": "1.2.0"}:
        return fail(f"version_delta={preview.version_delta}")
    if preview.changelog["gaps"]:
        return fail(f"unexpected gaps {preview.changelog['gaps']}")
    if preview.permission_diff["verdict"] != "widen":
        return fail(f"verdict={preview.permission_diff['verdict']}")
    containment = independent_set_containment(
        installed.permissions, candidate.permissions
    )
    if containment != "widen" or containment != preview.independent_containment_verdict:
        return fail(f"containment disagreement lattice={preview.permission_diff['verdict']} set={containment}")

    store = MemoryConsentStore()
    store.persist(
        Consent(
            package_id=PKG,
            from_version="1.0.0",
            to_version="1.2.0",
            widened=("net:connect:api.example",),
        )
    )
    with tempfile.TemporaryDirectory() as td:
        dest = Path(td) / "pkg"
        write_package_tree(dest, installed)
        pre_write_census = census_tree(dest)
        # Signal 1 captured before apply
        signal1 = {
            "file_changes": preview.file_changes,
            "permission_diff": preview.permission_diff,
            "expected_files": preview.expected_files,
            "expected_permissions": preview.expected_permissions,
            "dest_unmutated_before_apply": pre_write_census == census_tree(dest),
        }
        result = apply_update(
            dest, installed, candidate, consent_store=store, preview=preview
        )
        # Signal 2: independent walk + manifest parse
        signal2 = {
            "actual_files": census_tree(dest),
            "actual_permissions": effective_permissions_from_disk(dest),
        }
        fidelity = assert_preview_matches_actual(preview, dest)
        exact = (
            signal2["actual_files"] == signal1["expected_files"]
            and signal2["actual_permissions"] == signal1["expected_permissions"]
        )
        if not exact:
            return fail("preview under/over-reported vs disk census")
        report = {
            "probe": "probe1-preview-fidelity",
            "unit_id": "IMP-0087",
            "pass": True,
            "computed_not_asserted": True,
            "signal1_preview": {
                "added": [r["path"] for r in preview.file_changes["added"]],
                "removed": [r["path"] for r in preview.file_changes["removed"]],
                "modified": [r["path"] for r in preview.file_changes["modified"]],
                "permission_verdict": preview.permission_diff["verdict"],
                "permission_added": preview.permission_diff["added"],
            },
            "signal2_disk": {
                "file_count": len(signal2["actual_files"]),
                "permissions": signal2["actual_permissions"],
            },
            "exact_match": exact,
            "fidelity": fidelity,
            "applied": result["applied"],
            "independent_containment": containment,
        }
        print(json.dumps(report, sort_keys=True))
    print("SUCCESS:IMP-0087-probe1 preview matches post-update census")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
