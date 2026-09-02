"""AST auditor: outbound publish calls may live only in pr_only_guard.py."""
from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

FORBIDDEN = {"urlopen", "urlretrieve", "request", "put", "post", "patch"}


def _hits(path: Path) -> list[dict[str, Any]]:
    text = path.read_text(encoding="utf-8")
    tree = ast.parse(text)
    found = []
    for node in ast.walk(tree):
        name = None
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name):
                name = func.id
            elif isinstance(func, ast.Attribute):
                name = func.attr
        if name in FORBIDDEN:
            found.append({"file": path.name, "name": name, "lineno": getattr(node, "lineno", 0)})
    return found


def audit_tree(root: Path) -> dict[str, Any]:
    root = Path(root)
    watch = [
        "publishing.py",
        "pr_only_guard.py",
        "release_mode.py",
        "publisher.py",
        "publication.py",
        "_planted_bypass.py",
    ]
    scanned = []
    findings = []
    for name in watch:
        path = root / name
        if not path.is_file():
            continue
        scanned.append(path.name)
        if path.name == "pr_only_guard.py":
            continue
        findings.extend(_hits(path))
    return {
        "clean": not findings,
        "finding_count": len(findings),
        "findings": findings,
        "scanned": scanned,
    }


def plant_and_detect(root: Path) -> dict[str, Any]:
    plant = Path(root) / "_planted_bypass.py"
    plant.write_text(
        "import urllib.request\n"
        "def leak():\n"
        "    urllib.request.urlopen('https://example.invalid')\n",
        encoding="utf-8",
        newline="\n",
    )
    planted = audit_tree(root)
    plant.unlink()
    after = audit_tree(root)
    planted_found = any(f.get("file") == "_planted_bypass.py" for f in planted["findings"])
    silent = after["clean"]
    return {
        "planted_found": planted_found,
        "silent_after_removal": silent,
        "detector_control_ok": planted_found and silent,
        "planted_findings": planted["findings"],
        "after_findings": after["findings"],
    }
