"""IMP-0062 tests: SBOM matches an independent lockfile parse + CDX schema."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[2]
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from plugin.sbom import build_bom, identities_from_bom  # noqa: E402
from plugin.validate_cdx import validate_bom  # noqa: E402


def _fixture(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "requirements.lock").write_text(
        "requests==2.31.0\n"
        "certifi==2024.2.2\n"
        "# comment line\n"
        "six==1.16.0 ; python_version < '3.10'\n",
        encoding="utf-8",
    )
    (root / "package-lock.json").write_text(
        json.dumps({
            "packages": {
                "": {"name": "root", "version": "1.0.0"},
                "node_modules/left-pad": {"name": "left-pad", "version": "1.3.0"},
                "node_modules/unpinned-widget": {"name": "unpinned-widget", "version": "2.0.1"},
            }
        }),
        encoding="utf-8",
    )
    vendor = root / "vendor" / "vendored-helper"
    vendor.mkdir(parents=True, exist_ok=True)
    (vendor / "METADATA").write_text("Version: 0.9.1\n", encoding="utf-8")
    vendor2 = root / "vendor" / "vendored-raw"
    vendor2.mkdir(parents=True, exist_ok=True)


def _independent_parse(root: Path) -> set:
    """A DIFFERENT parser: regex over the raw lockfiles (not sbom.py)."""
    out = set()
    req = (root / "requirements.lock").read_text(encoding="utf-8")
    for name, ver in re.findall(r"^([A-Za-z0-9_.-]+)==([^;\s]+)", req, re.M):
        out.add((name, ver))
    lock = json.loads((root / "package-lock.json").read_text(encoding="utf-8"))
    for rel, meta in lock["packages"].items():
        if rel and meta.get("version"):
            out.add((meta["name"], meta["version"]))
    vend = root / "vendor"
    if vend.is_dir():
        for child in sorted(vend.iterdir()):
            if child.is_dir():
                ver = "unpinned"
                meta = child / "METADATA"
                if meta.is_file():
                    m = re.search(r"(?im)^version:\s*(.+)$", meta.read_text(encoding="utf-8"))
                    if m:
                        ver = m.group(1).strip()
                out.add((child.name, ver))
    return out


def test_sbom_matches_lockfile_closure(tmp_path: Path) -> None:
    _fixture(tmp_path)
    bom = build_bom(tmp_path)
    assert bom["specVersion"] == "1.5"
    errs = validate_bom(bom)
    assert errs == [], errs[:3]
    got = identities_from_bom(bom)
    want = _independent_parse(tmp_path)
    assert got == want, (sorted(got - want), sorted(want - got))


def test_negative_control_new_dependency_appears_and_test_detects_absence(tmp_path: Path) -> None:
    _fixture(tmp_path)
    bom = build_bom(tmp_path)
    got = identities_from_bom(bom)
    assert ("left-pad", "1.3.0") in got
    # removing it from the closure must make a closure-equality check FAIL
    shrunk = {p for p in got if p[0] != "left-pad"}
    want = _independent_parse(tmp_path)
    assert shrunk != want


def test_vendored_trees_present_as_components(tmp_path: Path) -> None:
    _fixture(tmp_path)
    bom = build_bom(tmp_path)
    vendored = [c for c in bom["components"] if c["properties"][0]["value"] == "vendored"]
    names = {c["name"] for c in vendored}
    assert {"vendored-helper", "vendored-raw"} <= names
