#!/usr/bin/env python3
"""IMP-0062 probe1 (source): the generated SBOM validates against the CycloneDX
1.5 schema on disk and its component set equals an independent lockfile parse."""
import json
import platform as _stdlib_platform  # prime stdlib before tools/ shadows it
import re
import shutil
import sys
import tempfile
from pathlib import Path

assert hasattr(_stdlib_platform, "python_implementation"), "stdlib platform shadowed"

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools"))

from plugin.sbom import build_bom, identities_from_bom  # noqa: E402
from plugin.validate_cdx import validate_bom  # noqa: E402


def fixture(root: Path) -> None:
    (root / "requirements.lock").write_text("requests==2.31.0\ncertifi==2024.2.2\n", encoding="utf-8")
    (root / "package-lock.json").write_text(json.dumps({
        "packages": {
            "": {"name": "root", "version": "1.0.0"},
            "node_modules/left-pad": {"name": "left-pad", "version": "1.3.0"},
        }}), encoding="utf-8")
    v = root / "vendor" / "vendored-widget"
    v.mkdir(parents=True, exist_ok=True)
    (v / "METADATA").write_text("Version: 3.1.4\n", encoding="utf-8")


def independent(root: Path) -> set:
    out = set()
    for name, ver in re.findall(r"^([A-Za-z0-9_.-]+)==([^;\s]+)", (root / "requirements.lock").read_text(encoding="utf-8"), re.M):
        out.add((name, ver))
    lock = json.loads((root / "package-lock.json").read_text(encoding="utf-8"))
    for rel, meta in lock["packages"].items():
        if rel and meta.get("version"):
            out.add((meta["name"], meta["version"]))
    for child in sorted((root / "vendor").iterdir()):
        if child.is_dir():
            m = re.search(r"(?im)^version:\s*(.+)$", (child / "METADATA").read_text(encoding="utf-8"))
            out.add((child.name, m.group(1).strip() if m else "unpinned"))
    return out


def main() -> int:
    work = Path(tempfile.mkdtemp(prefix="imp0062-p1-"))
    try:
        fixture(work)
        bom = build_bom(work)
        errs = validate_bom(bom)
        got = identities_from_bom(bom)
        want = independent(work)
        checks = {
            "cdx_schema_valid": errs == [],
            "component_set_equals_lockfile_closure": got == want,
            "vendored_source_tagged": any(c["properties"][0]["value"] == "vendored" for c in bom["components"]),
        }
        print(json.dumps({"schema_errors": errs[:3], "components": sorted(n for n, _ in got), "checks": checks}))
        if not all(checks.values()):
            print("FAILED:IMP-0062-probe1 sbom mismatch")
            return 1
        print("SUCCESS:IMP-0062-probe1 schema-valid SBOM equals the independent lockfile closure")
        return 0
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
