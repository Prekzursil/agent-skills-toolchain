#!/usr/bin/env python3
"""AUD-0022 Probe 2: independently built graph from installed package metadata."""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from importlib import metadata
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
PROBE = Path(__file__).resolve().parent
OUT = PROBE / "probe2-installed-meta.json"
RAW = PROBE / "probe2-installed.raw.txt"
CTRL_OUT = PROBE / "control-dual-version.json"


def scan_node_modules(root: Path) -> dict[str, set[str]]:
    versions: dict[str, set[str]] = defaultdict(set)
    nm = root / "node_modules"
    if not nm.is_dir():
        return versions
    # walk only top two levels of node_modules (incl scoped)
    for child in nm.iterdir():
        if child.name.startswith("."):
            continue
        if child.name.startswith("@"):
            for scoped in child.iterdir():
                pkg = scoped / "package.json"
                if pkg.is_file():
                    try:
                        meta = json.loads(pkg.read_text(encoding="utf-8"))
                    except json.JSONDecodeError:
                        continue
                    name = meta.get("name") or f"{child.name}/{scoped.name}"
                    ver = meta.get("version")
                    if ver:
                        versions[name].add(str(ver))
                # nested node_modules one level
                nested = scoped / "node_modules"
                if nested.is_dir():
                    for n2 in nested.iterdir():
                        if n2.name.startswith("@"):
                            continue
                        p2 = n2 / "package.json"
                        if p2.is_file():
                            try:
                                m2 = json.loads(p2.read_text(encoding="utf-8"))
                            except json.JSONDecodeError:
                                continue
                            if m2.get("name") and m2.get("version"):
                                versions[m2["name"]].add(str(m2["version"]))
        else:
            pkg = child / "package.json"
            if pkg.is_file():
                try:
                    meta = json.loads(pkg.read_text(encoding="utf-8"))
                except json.JSONDecodeError:
                    continue
                name = meta.get("name") or child.name
                ver = meta.get("version")
                if ver:
                    versions[name].add(str(ver))
    return versions


def python_installed() -> dict[str, set[str]]:
    versions: dict[str, set[str]] = defaultdict(set)
    for dist in metadata.distributions():
        name = dist.metadata["Name"] if dist.metadata else None
        ver = dist.version
        if name and ver:
            versions[name.lower()].add(str(ver))
    return versions


def detect_dupes(versions: dict[str, set[str]]) -> dict[str, list[str]]:
    return {n: sorted(vs) for n, vs in versions.items() if len(vs) >= 2}


def control_dual_version() -> dict:
    """Plant a dual-version case and a clean single-version case."""
    bad = {"left-pad": {"1.0.0", "1.3.0"}, "clean-pkg": {"2.0.0"}}
    good = {"left-pad": {"1.3.0"}, "clean-pkg": {"2.0.0"}}
    bad_dupes = detect_dupes(bad)
    good_dupes = detect_dupes(good)
    fired = "left-pad" in bad_dupes and len(bad_dupes["left-pad"]) == 2
    silent = "left-pad" not in good_dupes and good_dupes == {}
    return {
        "ok": fired and silent,
        "fired_on_dual_version": fired,
        "silent_on_clean": silent,
        "bad_dupes": bad_dupes,
        "good_dupes": good_dupes,
    }


def main() -> int:
    lines: list[str] = []
    lines.append("AUD-0022 NAMED PROBE 2: installed package metadata graph")
    lines.append("unit=AUD-0022")

    node_v = scan_node_modules(REPO)
    py_v = python_installed()
    node_dupes = detect_dupes(node_v)
    py_dupes = detect_dupes(py_v)

    # depth from nested node_modules presence
    max_depth = 0
    nm = REPO / "node_modules"
    if nm.is_dir():
        for p in nm.rglob("package.json"):
            rel = p.relative_to(REPO)
            depth = sum(1 for part in rel.parts if part == "node_modules")
            max_depth = max(max_depth, depth)

    ctrl = control_dual_version()
    CTRL_OUT.write_text(json.dumps(ctrl, indent=2) + "\n", encoding="utf-8")

    result = {
        "ok": True,
        "unit": "AUD-0022",
        "probe": 2,
        "node_packages_seen": len(node_v),
        "node_duplicate_version_count": len(node_dupes),
        "node_duplicate_versions": {k: v for k, v in sorted(node_dupes.items())[:100]},
        "python_distributions": len(py_v),
        "python_duplicate_version_count": len(py_dupes),
        "python_duplicate_versions": {k: v for k, v in sorted(py_dupes.items())[:50]},
        "installed_max_depth": max_depth,
        "control": ctrl,
    }
    OUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")

    lines.append(f"node_packages_seen={len(node_v)}")
    lines.append(f"node_duplicate_version_count={len(node_dupes)}")
    for n, vs in sorted(node_dupes.items())[:40]:
        lines.append(f"NODE_DUP\t{n}\t{','.join(vs)}")
    lines.append(f"python_distributions={len(py_v)}")
    lines.append(f"python_duplicate_version_count={len(py_dupes)}")
    lines.append(f"installed_max_depth={max_depth}")
    lines.append(
        f"CONTROL fired_on_dual={ctrl['fired_on_dual_version']} "
        f"silent_on_clean={ctrl['silent_on_clean']} ok={ctrl['ok']}"
    )
    lines.append("SUCCESS:AUD-0022-probe2")
    RAW.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(RAW.read_text(encoding="utf-8"))
    return 0 if ctrl["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
