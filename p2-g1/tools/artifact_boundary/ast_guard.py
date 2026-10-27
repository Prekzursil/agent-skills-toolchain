"""AST auditor: payload must not reach apply_policy."""
from __future__ import annotations

import ast
from pathlib import Path


def _payload_reaches_apply(tree: ast.AST) -> bool:
    payload_names = {"payload", "body"}
    assigned_from_body: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            val = node.value
            body_access = False
            if isinstance(val, ast.Attribute) and val.attr == "body":
                body_access = True
            if isinstance(val, ast.Name) and val.id in payload_names:
                body_access = True
            if body_access:
                for tgt in node.targets:
                    if isinstance(tgt, ast.Name):
                        assigned_from_body.add(tgt.id)
                        payload_names.add(tgt.id)
        if isinstance(node, ast.Call):
            func = node.func
            name = ""
            if isinstance(func, ast.Name):
                name = func.id
            elif isinstance(func, ast.Attribute):
                name = func.attr
            if name == "apply_policy" and node.args:
                arg0 = node.args[0]
                if isinstance(arg0, ast.Name) and arg0.id in payload_names | assigned_from_body:
                    return True
                if isinstance(arg0, ast.Attribute) and arg0.attr == "body":
                    return True
    return False


def audit_source(src: str, label: str = "source") -> list[dict]:
    tree = ast.parse(src)
    findings = []
    if _payload_reaches_apply(tree):
        findings.append(
            {
                "id": "payload-reaches-apply_policy",
                "label": label,
                "severity": "high",
            }
        )
    return findings


def audit_consume_module(path: Path) -> dict:
    src = Path(path).read_text(encoding="utf-8")
    tree = ast.parse(src)
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            names.add(node.name)
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name):
                names.add(func.id)
            elif isinstance(func, ast.Attribute):
                names.add(func.attr)
    findings = audit_source(src, label=str(path))
    return {
        "clean": findings == [],
        "wraps": "wrap_artifact" in names or "wraps" in src,
        "extracts": "extract_facts" in names,
        "applies_policy": "apply_policy" in names,
        "findings": findings,
        "path": str(path),
    }
