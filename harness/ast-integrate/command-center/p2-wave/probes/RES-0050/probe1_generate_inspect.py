#!/usr/bin/env python3
"""Probe 1: generate a draft CycloneDX SBOM and inspect what it captured."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from sbom import inspect_bom, write_bom  # noqa: E402

OUT = HERE / "draft-sbom.cdx.json"


def main() -> int:
    bom = write_bom(OUT)
    insp = inspect_bom(bom)
    skills = insp["skill_paths"]
    hooks = insp["hook_paths"]
    by_type = insp["by_type"]
    errors: list[str] = []
    if bom.get("bomFormat") != "CycloneDX":
        errors.append("bomFormat")
    if bom.get("specVersion") != "1.6":
        errors.append("specVersion")
    if insp["component_count"] < 8:
        errors.append(f"too-few-components:{insp['component_count']}")
    if by_type.get("data", 0) < 1:
        errors.append("no-data-type-for-markdown")
    if by_type.get("file", 0) < 1:
        errors.append("no-file-type")
    if insp["library_count"] != 0:
        errors.append(f"unexpected-library:{insp['library_count']}")
    if insp["missing_hash_count"] != 0:
        errors.append("missing-hash")
    if not any(p.endswith("skills/skill.council/SKILL.md") for p in skills):
        errors.append("skill-not-captured")
    if not hooks:
        errors.append("hook-not-captured")
    if insp["python_tool_count"] < 1:
        errors.append("python-tools-not-captured")
    lf = insp["lockfile_root"]
    if lf.get("parse_error"):
        errors.append(f"lockfile-parse:{lf['parse_error']}")
    if lf.get("lockfile_captures_prompt_or_script_payload"):
        errors.append("lockfile-only-captured-payload")
    if "package-lock.json" in (lf.get("root_manifests") or []):
        n = lf.get("lockfile_only_component_count")
        if not isinstance(n, int) or n < 1:
            errors.append("root-lockfile-empty")
        # Control: even with a live root lockfile, lockfile-only inventory
        # is npm packages, not skills/hooks/Python tools.
    if insp["vulnerabilities_listed"] != 0:
        errors.append("vulns-should-be-empty-on-draft-inventory")
    print(json.dumps(insp, indent=2, sort_keys=True))
    print(
        f"captured types={by_type} skills={len(skills)} "
        f"hooks={len(hooks)} py={insp['python_tool_count']}"
    )
    if errors:
        print("FAILED:RES-0050-probe1 " + ",".join(errors))
        return 1
    print("SUCCESS:RES-0050-probe1 draft SBOM generated and inspected")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
