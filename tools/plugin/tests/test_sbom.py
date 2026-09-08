"""IMP-0062: SBOM matches lockfile closure; negative control + vendored trees."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import sbom as sbom_mod  # noqa: E402

REPO = Path(__file__).resolve().parents[3]


def _fixture_lock(tmp_path: Path) -> Path:
    lock = {
        "name": "fixture-app",
        "version": "1.0.0",
        "lockfileVersion": 3,
        "packages": {
            "": {"name": "fixture-app", "version": "1.0.0"},
            "node_modules/left-pad": {
                "version": "1.3.0",
                "resolved": "https://registry.npmjs.org/left-pad/-/left-pad-1.3.0.tgz",
                "integrity": "sha512-XxXFAKESECRET=",
                "license": "MIT",
            },
            "node_modules/@scope/pkg": {
                "version": "2.0.1",
                "license": "Apache-2.0",
            },
            "packages/workspace-a": {
                "name": "@fixture/workspace-a",
                "version": "0.1.0",
            },
        },
    }
    path = tmp_path / "package-lock.json"
    path.write_text(json.dumps(lock, indent=2) + "\n", encoding="utf-8")
    return path


def test_sbom_matches_lockfile_closure(tmp_path: Path) -> None:
    """Catalog node: SBOM names == independent lockfile parse (set equality)."""
    lock = _fixture_lock(tmp_path)
    vendor = tmp_path / "vendor" / "unpinned-blob"
    vendor.mkdir(parents=True)
    (vendor / "README.md").write_text("vendored\n", encoding="utf-8")

    doc = sbom_mod.build_sbom(
        name="fixture-app",
        version="1.0.0",
        npm_lockfiles=[lock],
        python_requirement_text="requests==2.32.3\n",
        vendored_markers=["vendor/unpinned-blob"],
        repo=tmp_path,
        timestamp="2026-09-08T00:00:00Z",
    )
    errs = sbom_mod.validate_cyclonedx(doc, sbom_mod.load_schema(REPO))
    assert errs == [], errs

    sbom_names = sbom_mod.component_names(doc)
    independent = sbom_mod.independent_npm_lockfile_names(lock)
    # Python pins are outside the npm independent set — compare npm subset.
    npm_only = {n for n in sbom_names if n != "requests"}
    assert npm_only == independent
    assert "left-pad" in sbom_names
    assert "@scope/pkg" in sbom_names
    assert "@fixture/workspace-a" in sbom_names
    assert "requests" in sbom_names
    assert "vendored:vendor/unpinned-blob" in sbom_mod.vendored_component_names(doc)


def test_negative_control_added_dependency_appears(tmp_path: Path) -> None:
    """NEGATIVE CONTROL: add a dependency; regenerated SBOM must list it."""
    lock = _fixture_lock(tmp_path)
    before = sbom_mod.build_sbom(
        name="fixture-app",
        version="1.0.0",
        npm_lockfiles=[lock],
        repo=tmp_path,
        vendored_markers=[],
        timestamp="2026-09-08T00:00:00Z",
    )
    assert "new-dep" not in sbom_mod.component_names(before)

    # Mutate lockfile: plant new-dep
    data = json.loads(lock.read_text(encoding="utf-8"))
    data["packages"]["node_modules/new-dep"] = {"version": "9.9.9", "license": "MIT"}
    lock.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")

    after = sbom_mod.build_sbom(
        name="fixture-app",
        version="1.0.0",
        npm_lockfiles=[lock],
        repo=tmp_path,
        vendored_markers=[],
        timestamp="2026-09-08T00:00:00Z",
    )
    assert "new-dep" in sbom_mod.component_names(after)
    # And the independent oracle also sees it (test would fail if SBOM ignored it).
    assert "new-dep" in sbom_mod.independent_npm_lockfile_names(lock)
    assert sbom_mod.component_names(after) == sbom_mod.independent_npm_lockfile_names(
        lock
    )


def test_vendored_trees_present_as_components(tmp_path: Path) -> None:
    """Vendored trees without lockfile entries must still appear as components."""
    lock = _fixture_lock(tmp_path)
    # Unpinned vendor path — no package-lock under it.
    orphan = tmp_path / "third_party" / "blob"
    orphan.mkdir(parents=True)
    (orphan / "lib.c").write_text("int x;\n", encoding="utf-8")

    doc = sbom_mod.build_sbom(
        name="fixture-app",
        version="1.0.0",
        npm_lockfiles=[lock],
        vendored_markers=["third_party/blob"],
        repo=tmp_path,
        timestamp="2026-09-08T00:00:00Z",
    )
    vnames = sbom_mod.vendored_component_names(doc)
    assert "vendored:third_party/blob" in vnames
    # Silent omission would mean vendored set empty while tree exists.
    assert vnames, "vendored trees must not be silently omitted"


def test_repo_root_lockfile_set_equality() -> None:
    """Live root package-lock.json: builder names == independent parse."""
    lock = REPO / "package-lock.json"
    assert lock.is_file()
    doc = sbom_mod.build_sbom(
        name="agent-skills-toolchain",
        version="0.1.0",
        npm_lockfiles=[lock],
        vendored_markers=["tools/editor/ralph-orchestrator/vendor"],
        repo=REPO,
        timestamp="2026-09-08T00:00:00Z",
    )
    errs = sbom_mod.validate_cyclonedx(doc, sbom_mod.load_schema(REPO))
    assert errs == [], errs
    assert sbom_mod.component_names(doc) == sbom_mod.independent_npm_lockfile_names(lock)
    assert "vendored:tools/editor/ralph-orchestrator/vendor" in (
        sbom_mod.vendored_component_names(doc)
    )
