"""Planted clean and dual-version fixtures for AUD-0022.

Clean: single resolution, depth 2, zero duplicates.
Dual: widget 1.0.0 and widget 2.0.0 in the same closure (npm nested + two
dist-info directories). The duplicate detector must fire here and stay
silent on clean.
"""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
FIX = HERE / "fixtures"

INT = "sha512-AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=="

CLEAN_NPM = {
    "name": "aud0022-clean",
    "version": "1.0.0",
    "lockfileVersion": 3,
    "requires": True,
    "packages": {
        "": {
            "name": "aud0022-clean",
            "version": "1.0.0",
            "dependencies": {"mid-pkg": "1.0.0"},
        },
        "node_modules/mid-pkg": {
            "version": "1.0.0",
            "resolved": "https://registry.npmjs.org/mid-pkg/-/mid-pkg-1.0.0.tgz",
            "integrity": INT,
            "dependencies": {"leaf-pkg": "1.0.0"},
        },
        "node_modules/leaf-pkg": {
            "version": "1.0.0",
            "resolved": "https://registry.npmjs.org/leaf-pkg/-/leaf-pkg-1.0.0.tgz",
            "integrity": INT,
        },
    },
}

DUAL_NPM = {
    "name": "aud0022-dual",
    "version": "1.0.0",
    "lockfileVersion": 3,
    "requires": True,
    "packages": {
        "": {
            "name": "aud0022-dual",
            "version": "1.0.0",
            "dependencies": {"widget": "1.0.0", "other": "1.0.0"},
        },
        "node_modules/widget": {
            "version": "1.0.0",
            "resolved": "https://registry.npmjs.org/widget/-/widget-1.0.0.tgz",
            "integrity": INT,
        },
        "node_modules/other": {
            "version": "1.0.0",
            "resolved": "https://registry.npmjs.org/other/-/other-1.0.0.tgz",
            "integrity": INT,
            "dependencies": {"widget": "2.0.0"},
        },
        "node_modules/other/node_modules/widget": {
            "version": "2.0.0",
            "resolved": "https://registry.npmjs.org/widget/-/widget-2.0.0.tgz",
            "integrity": INT,
        },
    },
}

CLEAN_UV = """\
version = 1
revision = 1
requires-python = ">=3.11"

[[package]]
name = "aud0022-clean-root"
version = "0.0.0"
source = { virtual = "." }
dependencies = [
    { name = "midpkg" },
]

[[package]]
name = "midpkg"
version = "1.0.0"
source = { registry = "https://pypi.org/simple" }
dependencies = [
    { name = "leafpkg" },
]

[[package]]
name = "leafpkg"
version = "1.0.0"
source = { registry = "https://pypi.org/simple" }
"""

DUAL_UV = """\
version = 1
revision = 1
requires-python = ">=3.11"

[[package]]
name = "aud0022-dual-root"
version = "0.0.0"
source = { virtual = "." }
dependencies = [
    { name = "midpkg" },
]

[[package]]
name = "midpkg"
version = "1.0.0"
source = { registry = "https://pypi.org/simple" }
dependencies = [
    { name = "widget" },
]

[[package]]
name = "widget"
version = "1.0.0"
source = { registry = "https://pypi.org/simple" }
"""


def _meta(name: str, version: str, requires: list[str] | None = None) -> str:
    lines = [
        "Metadata-Version: 2.1",
        f"Name: {name}",
        f"Version: {version}",
    ]
    for req in requires or []:
        lines.append(f"Requires-Dist: {req}")
    return "\n".join(lines) + "\n"


def _pkg_json(name: str, version: str, deps: dict[str, str] | None = None) -> str:
    rec: dict = {"name": name, "version": version}
    if deps:
        rec["dependencies"] = deps
    return json.dumps(rec, indent=2) + "\n"


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def ensure_fixtures(root: Path | None = None) -> Path:
    base = root or FIX
    _write(base / "clean" / "package-lock.json", json.dumps(CLEAN_NPM, indent=2) + "\n")
    _write(base / "clean" / "uv.lock", CLEAN_UV)
    _write(
        base / "clean" / "site-packages" / "midpkg-1.0.0.dist-info" / "METADATA",
        _meta("midpkg", "1.0.0", ["leafpkg (==1.0.0)"]),
    )
    _write(
        base / "clean" / "site-packages" / "leafpkg-1.0.0.dist-info" / "METADATA",
        _meta("leafpkg", "1.0.0"),
    )
    _write(
        base / "clean" / "node_modules" / "mid-pkg" / "package.json",
        _pkg_json("mid-pkg", "1.0.0", {"leaf-pkg": "1.0.0"}),
    )
    _write(
        base / "clean" / "node_modules" / "leaf-pkg" / "package.json",
        _pkg_json("leaf-pkg", "1.0.0"),
    )

    _write(base / "dual" / "package-lock.json", json.dumps(DUAL_NPM, indent=2) + "\n")
    _write(base / "dual" / "uv.lock", DUAL_UV)
    _write(
        base / "dual" / "site-packages" / "midpkg-1.0.0.dist-info" / "METADATA",
        _meta("midpkg", "1.0.0", ["widget"]),
    )
    _write(
        base / "dual" / "site-packages" / "widget-1.0.0.dist-info" / "METADATA",
        _meta("widget", "1.0.0"),
    )
    _write(
        base / "dual" / "site-packages" / "widget-2.0.0.dist-info" / "METADATA",
        _meta("widget", "2.0.0"),
    )
    _write(
        base / "dual" / "node_modules" / "widget" / "package.json",
        _pkg_json("widget", "1.0.0"),
    )
    _write(
        base / "dual" / "node_modules" / "other" / "package.json",
        _pkg_json("other", "1.0.0", {"widget": "2.0.0"}),
    )
    _write(
        base / "dual" / "node_modules" / "other" / "node_modules" / "widget" / "package.json",
        _pkg_json("widget", "2.0.0"),
    )
    return base


def fixture_lock_graph(kind: str):
    from graph import merge_graphs, parse_npm_lock_path, parse_uv_lock_path

    base = ensure_fixtures() / kind
    return merge_graphs(
        parse_npm_lock_path(base / "package-lock.json"),
        parse_uv_lock_path(base / "uv.lock"),
    )


def fixture_installed_graph(kind: str):
    from graph import merge_graphs, parse_dist_info_tree, parse_node_modules_tree

    base = ensure_fixtures() / kind
    return merge_graphs(
        parse_dist_info_tree(
            base / "site-packages", source_label=f"fixture:{kind}:site-packages"
        ),
        parse_node_modules_tree(
            base / "node_modules", source_label=f"fixture:{kind}:node_modules"
        ),
    )


if __name__ == "__main__":
    ensure_fixtures()
    print("wrote", FIX)
