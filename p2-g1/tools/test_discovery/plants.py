"""Plant matching trees, orphans, ghosts, and hostile paths (TST-0326)."""
from __future__ import annotations

from pathlib import Path
from typing import Any


def _write(path: Path, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")


def build_matching_tree(root: Path) -> dict[str, Any]:
    root = Path(root)
    tests = root / "tests"
    _write(tests / "test_registered.py", "def test_ok():\n    assert True\n")
    _write(tests / "test_second.py", "def test_two():\n    assert True\n")
    _write(tests / "test_third.py", "def test_three():\n    assert True\n")
    registry = root / "test-registry.json"
    nodeids = [
        "tests/test_registered.py::test_ok",
        "tests/test_second.py::test_two",
        "tests/test_third.py::test_three",
    ]
    registry.write_text(
        __import__("json").dumps({"tests": nodeids}, indent=2) + "\n", encoding="utf-8"
    )
    return {"root": str(root), "registry": str(registry), "nodeids": nodeids}


def plant_orphan_python(root: Path) -> Path:
    dest = Path(root) / "tests" / "test_planted_orphan.py"
    _write(dest, "def test_planted_orphan():\n    assert True\n")
    return dest


def plant_orphan_vitest(root: Path) -> Path:
    dest = Path(root) / "tests" / "planted.orphan.test.ts"
    _write(dest, "test('planted orphan', () => {})\n")
    return dest


def write_ghost_registry(root: Path, planted: dict[str, Any]) -> Path:
    import json

    registry = Path(planted["registry"])
    doc = json.loads(registry.read_text(encoding="utf-8"))
    tests = list(doc.get("tests") or [])
    tests.append("tests/test_ghost_not_on_disk.py::test_ghost")
    doc["tests"] = tests
    registry.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    return registry


def plant_hostile_tree(root: Path) -> dict[str, Any]:
    root = Path(root)
    _write(root / "NUL", "reserved-device-name fixture\n")
    _write(root / "test_after_nul.py", "def test_after_nul():\n    assert True\n")
    long_dir = root
    # Build a path whose full string exceeds 260 when possible; record leaf length.
    chunk = "longdir_" + ("x" * 20)
    for _ in range(8):
        long_dir = long_dir / chunk
        long_dir.mkdir(parents=True, exist_ok=True)
    leaf = long_dir / "test_long_path.py"
    _write(leaf, "def test_long_path():\n    assert True\n")
    cycle = root / "cycle"
    cycle.mkdir(parents=True, exist_ok=True)
    try:
        (cycle / "self").symlink_to(cycle, target_is_directory=True)
        cycled = True
    except OSError:
        cycled = False
    return {
        "root": str(root),
        "long_leaf_len": len(str(leaf)),
        "cycle": cycled,
        "nul": str(root / "NUL"),
        "after": str(root / "test_after_nul.py"),
        "long": str(leaf),
    }
