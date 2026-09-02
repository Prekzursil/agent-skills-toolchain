"""Static enumeration of credential-shaped env and file reads."""
from __future__ import annotations

import ast
import re
from pathlib import Path

import constants as C

_ENV_JS = re.compile(r"process\.env\.([A-Z][A-Z0-9_]{2,})")
_ENV_PS = re.compile(r"\$env:([A-Z][A-Z0-9_]{2,})", re.I)
_ENV_SH = re.compile(r"\$\{?([A-Z][A-Z0-9_]{8,})\}?")
_FILE_OPEN = re.compile(
    r"""(?:open|Path)\(\s*['"]([^'"]*(?:credential|secret|auth\.json|\.env|id_rsa|id_ed25519|\.pem|\.p12)[^'"]*)['"]""",
    re.I,
)


def is_credential_name(name: str) -> bool:
    if not name or name in C.NOT_CREDENTIAL_NAMES:
        return False
    up = name.upper()
    if up in C.NOT_CREDENTIAL_NAMES:
        return False
    return any(m in up for m in C.CREDENTIAL_NAME_MARKERS)


def _rel(repo: Path, path: Path) -> str:
    return path.relative_to(repo).as_posix()


def _skip_rel(rel: str) -> bool:
    parts = set(rel.split("/"))
    if parts & C.SKIP_DIR_PARTS:
        return True
    if rel.startswith(C.SKIP_PROBE_PREFIX) and not rel.startswith(C.KEEP_PROBE_PREFIX):
        return True
    return False


def iter_source_files(repo: Path) -> list[Path]:
    out: list[Path] = []
    for root_name in C.SCAN_ROOTS:
        root = repo / root_name
        if not root.is_dir():
            continue
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            rel = _rel(repo, path)
            if _skip_rel(rel):
                continue
            if path.suffix.lower() in {".py", ".js", ".ts", ".ps1", ".sh"}:
                out.append(path)
    out.sort()
    return out


def _const_str(node: ast.AST) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _attr_chain(node: ast.AST) -> str:
    parts: list[str] = []
    cur: ast.AST | None = node
    while isinstance(cur, ast.Attribute):
        parts.append(cur.attr)
        cur = cur.value
    if isinstance(cur, ast.Name):
        parts.append(cur.id)
    parts.reverse()
    return ".".join(parts)


def _snippet(src: str, lineno: int, span: int = 12) -> str:
    lines = src.splitlines()
    i = max(0, lineno - 1)
    return "\n".join(lines[i : i + span])


def _classify(snippet: str, form: str, default_present: bool) -> str:
    low = snippet.lower()
    loud_marks = (
        "sys.exit",
        "raise ",
        "return 2",
        "return 1",
        "failed:",
        "missing",
        "auth_fail",
        "erroractionpreference = 'stop'",
        "throw ",
    )
    if form == "subscript":
        return "crash-on-absent"
    if any(m in low for m in loud_marks) and ("if not " in low or "if not\n" in low or "if (" in low):
        return "loud-fail"
    if "if not " in low and ("return" in low or "sys.exit" in low or "raise" in low):
        return "loud-fail"
    if "if not " in snippet and ("FAILED:" in snippet or "missing" in low):
        return "loud-fail"
    if "continue" in low and "if not " in low:
        return "skip-if-absent"
    if default_present or " or " in low or "else " in low:
        return "silent-degrade"
    if form in {"get", "getenv"} and "if not" not in low and "if " not in low[:80]:
        return "silent-degrade"
    return "unknown"


class _PyVisitor(ast.NodeVisitor):
    def __init__(self, rel: str, src: str) -> None:
        self.rel = rel
        self.src = src
        self.hits: list[dict] = []
        self._entry = "module" in src and "__main__" in src

    def visit_Call(self, node: ast.Call) -> None:
        chain = _attr_chain(node.func)
        name: str | None = None
        default_present = False
        form = "get"
        if chain in {"os.environ.get", "os.environ.get"}:
            if node.args:
                name = _const_str(node.args[0])
            default_present = len(node.args) >= 2 or any(
                k.arg == "default" for k in node.keywords if k.arg
            )
            form = "get"
        elif chain in {"os.getenv", "getenv"}:
            if node.args:
                name = _const_str(node.args[0])
            default_present = len(node.args) >= 2
            form = "getenv"
        if name and is_credential_name(name):
            snip = _snippet(self.src, int(getattr(node, "lineno", 1) or 1))
            self.hits.append(
                {
                    "path": self.rel,
                    "line": int(getattr(node, "lineno", 1) or 1),
                    "kind": "env",
                    "name": name,
                    "form": form,
                    "default_present": default_present,
                    "classification": _classify(snip, form, default_present),
                    "snippet": snip[:400],
                    "language": "python",
                    "entry_point": self._entry,
                }
            )
        self.generic_visit(node)

    def visit_Subscript(self, node: ast.Subscript) -> None:
        chain = _attr_chain(node.value)
        name = None
        sl = node.slice
        if isinstance(sl, ast.Constant):
            name = sl.value if isinstance(sl.value, str) else None
        if chain in {"os.environ", "environ"} and isinstance(name, str) and is_credential_name(name):
            snip = _snippet(self.src, int(getattr(node, "lineno", 1) or 1))
            self.hits.append(
                {
                    "path": self.rel,
                    "line": int(getattr(node, "lineno", 1) or 1),
                    "kind": "env",
                    "name": name,
                    "form": "subscript",
                    "default_present": False,
                    "classification": "crash-on-absent",
                    "snippet": snip[:400],
                    "language": "python",
                    "entry_point": self._entry,
                }
            )
        self.generic_visit(node)


def _scan_python(repo: Path, path: Path) -> list[dict]:
    rel = _rel(repo, path)
    try:
        src = path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        return [
            {
                "path": rel,
                "line": 0,
                "kind": "parse-error",
                "name": "",
                "form": "read",
                "default_present": False,
                "classification": "unknown",
                "snippet": type(exc).__name__,
                "language": "python",
                "entry_point": False,
            }
        ]
    try:
        tree = ast.parse(src)
    except SyntaxError as exc:
        return [
            {
                "path": rel,
                "line": int(exc.lineno or 0),
                "kind": "parse-error",
                "name": "",
                "form": "parse",
                "default_present": False,
                "classification": "unknown",
                "snippet": (exc.msg or "")[:120],
                "language": "python",
                "entry_point": False,
            }
        ]
    vis = _PyVisitor(rel, src)
    vis.visit(tree)
    for match in _FILE_OPEN.finditer(src):
        vis.hits.append(
            {
                "path": rel,
                "line": src[: match.start()].count("\n") + 1,
                "kind": "file",
                "name": match.group(1),
                "form": "open",
                "default_present": False,
                "classification": "unknown",
                "snippet": _snippet(src, src[: match.start()].count("\n") + 1)[:400],
                "language": "python",
                "entry_point": vis._entry,
            }
        )
    return vis.hits


def _scan_text(repo: Path, path: Path, language: str, regex: re.Pattern[str]) -> list[dict]:
    rel = _rel(repo, path)
    try:
        src = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    hits: list[dict] = []
    for match in regex.finditer(src):
        name = match.group(1)
        if not is_credential_name(name):
            continue
        line = src[: match.start()].count("\n") + 1
        snip = _snippet(src, line)
        hits.append(
            {
                "path": rel,
                "line": line,
                "kind": "env",
                "name": name,
                "form": "text",
                "default_present": False,
                "classification": _classify(snip, "text", False),
                "snippet": snip[:400],
                "language": language,
                "entry_point": True,
            }
        )
    return hits


def scan_repo(repo: Path) -> list[dict]:
    hits: list[dict] = []
    for path in iter_source_files(repo):
        suf = path.suffix.lower()
        if suf == ".py":
            hits.extend(_scan_python(repo, path))
        elif suf in {".js", ".ts"}:
            hits.extend(_scan_text(repo, path, "javascript", _ENV_JS))
        elif suf == ".ps1":
            hits.extend(_scan_text(repo, path, "powershell", _ENV_PS))
        elif suf == ".sh":
            hits.extend(_scan_text(repo, path, "shell", _ENV_SH))
    hits.sort(key=lambda h: (h.get("path") or "", int(h.get("line") or 0), h.get("name") or ""))
    return hits


iter_source_files = iter_source_files
_ENV_JS = _ENV_JS
_ENV_PS = _ENV_PS
_ENV_SH = _ENV_SH


def summarize(hits: list[dict]) -> dict:
    by_class: dict[str, int] = {}
    names: dict[str, int] = {}
    for h in hits:
        cls = str(h.get("classification") or "unknown")
        by_class[cls] = by_class.get(cls, 0) + 1
        n = str(h.get("name") or "")
        if n:
            names[n] = names.get(n, 0) + 1
    return {
        "read_count": len(hits),
        "by_classification": dict(sorted(by_class.items())),
        "distinct_names": sorted(names),
        "name_counts": dict(sorted(names.items())),
        "loud_fail": by_class.get("loud-fail", 0),
        "silent_degrade": by_class.get("silent-degrade", 0),
        "crash_on_absent": by_class.get("crash-on-absent", 0),
        "skip_if_absent": by_class.get("skip-if-absent", 0),
        "unknown": by_class.get("unknown", 0),
        "read_count": len(hits),
        "crash_on_absent": by_class.get("crash-on-absent", 0),
        "skip_if_absent": by_class.get("skip-if-absent", 0),
        "loud_fail": by_class.get("loud-fail", 0),
        "silent_degrade": by_class.get("silent-degrade", 0),
    }
