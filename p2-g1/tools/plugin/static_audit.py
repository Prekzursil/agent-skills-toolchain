"""Static audit: outbound network APIs may exist only in the allowlist module."""
from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import Iterable

REPO = Path(__file__).resolve().parents[2]
PLUGIN = Path(__file__).resolve().parent
LIB = REPO / "tools" / "lib"

ALLOWLIST_NAMES = frozenset(
    {
        "net-allowlist.mjs",
        "net-allowlist.json",
        "net_allowlist.py",
        "static_audit.py",
        "exec_policy.py",
        "intercept.py",
        "health_check.py",
        "healthcheck.py",
        "credential_mutation.py",
        "registry_fetch.py",
        "permission_enforcement.py",
    }
)

NETWORK_IMPORTS = frozenset(
    {
        "urllib",
        "urllib.request",
        "urllib.client",
        "http.client",
        "httpx",
        "requests",
        "aiohttp",
        "ftplib",
        "smtplib",
        "poplib",
        "nntplib",
        "telnetlib",
        "websocket",
        "websockets",
    }
)

NETWORK_CALLS = frozenset(
    {
        "urlopen",
        "urlretrieve",
        "HTTPConnection",
        "HTTPSConnection",
        "create_connection",
    }
)

SUBPROCESS_NET = frozenset({"curl", "wget", "nc", "ncat", "ssh", "scp", "sftp"})

JS_PATTERNS = (
    re.compile(r"\bfetch\s*\("),
    re.compile(r"\baxios\."),
    re.compile(r"\bhttps?\.request\s*\("),
    re.compile(r"\bnet\.connect\s*\("),
    re.compile(r"\bXMLHttpRequest\b"),
    re.compile(r"\bWebSocket\s*\("),
)


def _qual(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        left = _qual(node.value)
        return f"{left}.{node.attr}" if left else node.attr
    return ""


class _Visitor(ast.NodeVisitor):
    def __init__(self, rel: str) -> None:
        self.rel = rel
        self.findings: list[dict[str, str]] = []

    def _hit(self, node: ast.AST, rule: str, prefix: str) -> None:
        self.findings.append(
            {
                "path": self.rel,
                "line": str(getattr(node, "lineno", 0)),
                "rule": rule,
                "prefix": prefix[:80],
            }
        )

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            name = alias.name
            if name in NETWORK_IMPORTS or name.startswith("urllib"):
                self._hit(node, "network-import", f"import {name}")
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        mod = node.module or ""
        if mod in NETWORK_IMPORTS or mod.startswith("urllib"):
            names = ",".join(a.name for a in node.names)
            self._hit(node, "network-import", f"from {mod} import {names}")
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        qual = _qual(node.func)
        leaf = qual.split(".")[-1] if qual else ""
        if leaf in NETWORK_CALLS or qual.endswith("socket.connect"):
            self._hit(node, "network-call", qual)
        if leaf in {"run", "Popen", "call", "check_output", "check_call", "system"}:
            arg = node.args[0] if node.args else None
            text = ""
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                text = arg.value
            elif isinstance(arg, (ast.List, ast.Tuple)):
                parts = []
                for elt in arg.elts:
                    if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                        parts.append(elt.value)
                text = " ".join(parts)
            head = text.strip().split(" ")[0].split("/")[-1] if text.strip() else ""
            if head in SUBPROCESS_NET:
                self._hit(node, "subprocess-egress", text[:80])
        self.generic_visit(node)


def _skip(path: Path) -> bool:
    parts = set(path.parts)
    if "tests" in parts or "probes" in parts or "__pycache__" in parts:
        return True
    if path.name in ALLOWLIST_NAMES:
        return True
    if path.suffix not in {".py", ".mjs", ".js", ".cjs"}:
        return True
    return False


def iter_production_files(roots: Iterable[Path] | None = None) -> list[Path]:
    roots = list(roots or [PLUGIN, LIB])
    out: list[Path] = []
    for root in roots:
        if not root.exists():
            continue
        for path in sorted(root.rglob("*")):
            if not path.is_file() or _skip(path):
                continue
            out.append(path)
    return out


def audit_source(text: str, rel: str, suffix: str) -> list[dict[str, str]]:
    if suffix == ".py":
        tree = ast.parse(text)
        vis = _Visitor(rel)
        vis.visit(tree)
        return vis.findings
    hits = []
    for rx in JS_PATTERNS:
        for match in rx.finditer(text):
            line = text.count("\n", 0, match.start()) + 1
            hits.append(
                {
                    "path": rel,
                    "line": str(line),
                    "rule": "js-network",
                    "prefix": match.group(0)[:80],
                }
            )
    return hits


def audit_tree(roots: Iterable[Path] | None = None) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    for path in iter_production_files(roots):
        rel = path.as_posix()
        try:
            rel = path.resolve().relative_to(REPO).as_posix()
        except ValueError:
            pass
        text = path.read_text(encoding="utf-8")
        findings.extend(audit_source(text, rel, path.suffix))
    return findings


def audit_snippet(source: str, rel: str = "mutant.py") -> list[dict[str, str]]:
    return audit_source(source, rel, ".py")
