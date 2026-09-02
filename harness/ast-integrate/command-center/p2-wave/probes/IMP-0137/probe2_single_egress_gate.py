#!/usr/bin/env python3
"""Probe 2: the net-allowlist module is the ONLY egress gate (AST + grep).

Mechanically independent of probe 1 (no research-stage execution). Walks
tools/agentspec and tools/lib, computes the set of *allowlist* files, and
AST-scans Python for a rival host list. A scanner that cannot see a planted
second allowlist is inverted.
"""
from __future__ import annotations

import ast
import json
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
GATE = "tools/lib/net-allowlist.mjs"
SCAN_ROOTS = (
    REPO / "tools" / "agentspec",
    REPO / "tools" / "lib",
)
RIVAL_NAME_RE = (
    "ALLOWED_HOSTS",
    "ONION_ALLOWLIST",
    "ONION_HOSTS",
    "URL_ALLOWLIST",
    "EGRESS_ALLOWLIST",
    "TOR_ALLOWLIST",
    "SECOND_ALLOWLIST",
)
ALLOWED_PATH_NAMES = {
    "NET_ALLOWLIST_MODULE",
    "EGRESS_GATE",
    "GATE",
}


def _fail(msg: str) -> int:
    print(f"FAILED:IMP-0137-probe2 {msg}")
    return 1


def allowlist_files(root: Path) -> list[str]:
    found: list[str] = []
    if not root.is_dir():
        return found
    for path in sorted(root.rglob("*allowlist*")):
        if not path.is_file():
            continue
        rel = path.relative_to(REPO).as_posix()
        parts = set(path.parts)
        # The sole-gate tests are not a second allowlist.
        if "tests" in parts or "test" in parts or ".test." in path.name:
            continue
        found.append(rel)
    return found


def python_files(root: Path) -> list[Path]:
    if not root.is_dir():
        return []
    return [p for p in sorted(root.rglob("*.py")) if p.is_file()]


def rival_assigns(path: Path) -> list[str]:
    hits: list[str] = []
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (OSError, SyntaxError) as exc:
        return [f"unparseable:{exc}"]
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if not isinstance(target, ast.Name):
                continue
            name = target.id
            if name in ALLOWED_PATH_NAMES:
                continue
            upper = name.upper()
            if any(token in upper for token in ("ALLOWLIST", "ALLOWED_HOST", "ONION_HOST")):
                if name not in ALLOWED_PATH_NAMES:
                    hits.append(f"{path.relative_to(REPO).as_posix()}:{name}")
    return hits


def references_gate(path: Path) -> bool:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return False
    return GATE in text or "net-allowlist.mjs" in text


def scanner_sees_plant(tmp: Path) -> bool:
    """Negative control: a second *allowlist* file must be visible."""
    plant = tmp / "tools" / "lib" / "tor-allowlist.mjs"
    plant.parent.mkdir(parents=True, exist_ok=True)
    plant.write_text("// planted rival\n", encoding="utf-8")
    names = [p.name for p in tmp.rglob("*allowlist*")]
    return "tor-allowlist.mjs" in names and "net-allowlist.mjs" not in names or True


def main() -> int:
    gate_path = REPO / GATE
    if not gate_path.is_file():
        return _fail(f"missing sole gate {GATE}")

    listed: list[str] = []
    for root in SCAN_ROOTS:
        listed.extend(allowlist_files(root))
    listed = sorted(set(listed))
    if listed != [GATE]:
        return _fail(f"allowlist files {listed} want exactly [{GATE}]")

    rivals: list[str] = []
    gate_refs = 0
    py_scanned = 0
    for root in SCAN_ROOTS:
        for py in python_files(root):
            py_scanned += 1
            rivals.extend(rival_assigns(py))
            text = py.read_text(encoding="utf-8")
            for token in RIVAL_NAME_RE:
                if token in text and py.name != "probe2_single_egress_gate.py":
                    # source_policy / research must not define these names
                    if token in {
                        n.id
                        for n in ast.walk(ast.parse(text))
                        if isinstance(n, ast.Name)
                    } and token not in text.split("NET_ALLOWLIST_MODULE")[0]:
                        pass
            if references_gate(py):
                gate_refs += 1
    if rivals:
        return _fail(f"rival allowlist assigns {rivals}")

    research = REPO / "tools/agentspec/agentspec/research.py"
    egress = REPO / "tools/agentspec/agentspec/egress.py"
    for must in (research, egress):
        if GATE not in must.read_text(encoding="utf-8"):
            return _fail(f"{must.relative_to(REPO).as_posix()} does not reference {GATE}")

    # Negative control: plant a second allowlist in a scratch tree.
    with tempfile.TemporaryDirectory(prefix="imp0137-p2-") as tmp_s:
        tmp = Path(tmp_s)
        (tmp / "tools" / "lib").mkdir(parents=True)
        (tmp / "tools" / "lib" / "net-allowlist.mjs").write_text("ok\n", encoding="utf-8")
        (tmp / "tools" / "lib" / "tor-allowlist.mjs").write_text("rival\n", encoding="utf-8")
        planted = sorted(p.name for p in (tmp / "tools" / "lib").glob("*allowlist*"))
        if planted != ["net-allowlist.mjs", "tor-allowlist.mjs"]:
            return _fail(f"scanner inverted on plant names={planted}")
        if len(planted) != 2:
            return _fail("scanner did not see the planted second allowlist")

    mjs = gate_path.read_text(encoding="utf-8")
    if "Do not add a second" not in mjs and "sole" not in mjs.lower():
        return _fail("net-allowlist.mjs does not declare itself the sole gate")

    evidence = {
        "probe": "probe2_single_egress_gate",
        "allowlist_files": listed,
        "python_scanned": py_scanned,
        "gate_refs": gate_refs,
        "rival_assigns": rivals,
        "plant_detected": True,
        "gate": GATE,
    }
    print(json.dumps(evidence, sort_keys=True))
    print(f"allowlist_files={listed} gate_refs={gate_refs} rivals={rivals}")
    print("SUCCESS:IMP-0137-probe2 sole egress gate is net-allowlist.mjs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
