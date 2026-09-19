#!/usr/bin/env python3
"""AUD-0084 hardcoded-path census: lexical recall + Python AST use-versus-mention."""

from __future__ import annotations

import ast
import json
import os
import re
import tokenize
from io import StringIO
from pathlib import Path
from typing import Any, Iterable

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
FIXTURE = HERE / "fixtures" / "use_vs_mention_fixture.py"

CATALOG_SENTINEL = (
    "SUCCESS:AUD-0084 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and both named probes are "
    "recorded with their verbatim output"
)
# Catalog completion_sentinel (must appear verbatim in the artifact):
# SUCCESS:AUD-0084 emitted only when the artifact at output_path exists, is non-empty, parses against output_schema, and both named probes are recorded with their verbatim output
QUESTION = (
    "Which source files contain a hardcoded absolute path, a drive letter, "
    "a home directory, or a hardcoded path separator that would break on "
    "another platform or another user profile?"
)

SKIP_DIRS = {
    ".git",
    "node_modules",
    "__pycache__",
    ".venv",
    "venv",
    "dist",
    "build",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".tox",
    ".eggs",
    "site-packages",
    ".cursor",
}
SOURCE_EXTS = {
    ".py",
    ".pyi",
    ".js",
    ".jsx",
    ".mjs",
    ".cjs",
    ".ts",
    ".tsx",
    ".ps1",
    ".psm1",
    ".sh",
    ".bash",
    ".zsh",
    ".cmd",
    ".bat",
    ".go",
    ".yml",
    ".yaml",
    ".toml",
}
MAX_BYTES = 2_000_000
VALUE_CAP = 160

DRIVE_RE = re.compile(r"(?<![A-Za-z0-9_])[A-Za-z]:(?:[\\/])")
HOME_RE = re.compile(r"/home/[A-Za-z0-9._-]+")
USERS_RE = re.compile(r"/Users/[A-Za-z0-9._-]+")
ENV_HOME_RE = re.compile(r"(?:\$HOME|%USERPROFILE%|%HOMEPATH%|%HOME%)", re.I)
UNC_RE = re.compile(r"\\\\[A-Za-z0-9._$-]+\\")
BACKSLASH_PATH_RE = re.compile(r"[A-Za-z0-9._~$-]+\\[A-Za-z0-9._~$-]+")
QUOTED_RE = re.compile(r"(?P<q>['\"`])(?P<body>(?:\\.|[^\\])*?)(?P=q)", re.DOTALL)

REGEX_FUNCS = {
    "compile",
    "search",
    "match",
    "fullmatch",
    "findall",
    "finditer",
    "sub",
    "subn",
    "split",
}
PATH_FUNCS = {
    "open",
    "Path",
    "PurePath",
    "PureWindowsPath",
    "PurePosixPath",
    "WindowsPath",
    "PosixPath",
    "joinpath",
    "glob",
    "rglob",
    "chmod",
    "mkdir",
    "makedirs",
    "unlink",
    "remove",
    "rename",
    "chdir",
    "listdir",
    "scandir",
    "exists",
    "isfile",
    "isdir",
    "is_file",
    "is_dir",
    "expanduser",
    "abspath",
    "realpath",
    "normpath",
    "expandvars",
    "Popen",
    "run",
    "call",
    "check_call",
    "check_output",
    "walk",
    "startfile",
}
# "replace" is omitted: str.replace is content; os.replace is handled via os_path/name.
OS_PATH_FUNCS = {"join", "split", "dirname", "basename", "commonpath", "relpath"}
CONTENT_FUNCS = {
    "write_text",
    "write_bytes",
    "write",
    "writelines",
    "print",
    "info",
    "debug",
    "warning",
    "error",
    "critical",
    "exception",
    "log",
    "dumps",
    "dump",
    "format",
}


def relposix(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO).as_posix()
    except ValueError:
        return path.as_posix()


def surface_of(rel: str) -> str:
    parts = rel.split("/")
    name = parts[-1] if parts else ""
    if "vendor" in parts or "third_party" in parts or "node_modules" in parts:
        return "vendored"
    if "p2-wave" in parts and "probes" in parts:
        return "probe-evidence"
    if any(
        p in {"tests", "testdata", "fixtures", "conftest"} or p.startswith("test_")
        for p in parts
    ) or name.startswith("test_"):
        return "test-or-fixture"
    if "generated" in parts:
        return "generated-control-plane"
    return "first-party"


def language_of(path: Path) -> str:
    ext = path.suffix.lower()
    mapping = {
        ".py": "python",
        ".pyi": "python",
        ".js": "javascript",
        ".jsx": "javascript",
        ".mjs": "javascript",
        ".cjs": "javascript",
        ".ts": "javascript",
        ".tsx": "javascript",
        ".ps1": "powershell",
        ".psm1": "powershell",
        ".sh": "shell",
        ".bash": "shell",
        ".zsh": "shell",
        ".cmd": "cmd",
        ".bat": "cmd",
        ".yml": "config",
        ".yaml": "config",
        ".toml": "config",
    }
    return mapping.get(ext, ext.lstrip(".") or "unknown")


def kinds_in(value: str) -> list[str]:
    found: list[str] = []
    if DRIVE_RE.search(value):
        found.append("drive-letter")
    if HOME_RE.search(value):
        found.append("home-posix")
    if USERS_RE.search(value):
        found.append("users-posix")
    if (
        value.startswith("~/")
        or "/~/" in value
        or re.search(r"(?:^|[\s=\"'])~/", value)
    ):
        found.append("tilde-home")
    if ENV_HOME_RE.search(value):
        found.append("env-home")
    if UNC_RE.search(value) or value.startswith("\\\\"):
        found.append("unc")
    if BACKSLASH_PATH_RE.search(value):
        found.append("backslash-separator")
    return found


def clip(value: str) -> str:
    if len(value) <= VALUE_CAP:
        return value
    return value[: VALUE_CAP - 3] + "..."


def discover_sources() -> list[Path]:
    out: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(str(REPO), followlinks=False):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for name in filenames:
            path = Path(dirpath) / name
            if path.suffix.lower() not in SOURCE_EXTS:
                continue
            try:
                if path.stat().st_size > MAX_BYTES:
                    continue
            except OSError:
                continue
            out.append(path)
    out.sort(key=lambda p: relposix(p))
    return out


def decode_py_string(token_src: str) -> str | None:
    raw = token_src.strip()
    if not raw:
        return None
    prefix = ""
    i = 0
    while i < len(raw) and raw[i] in "rRuUfFbB":
        prefix += raw[i].lower()
        i += 1
    if "f" in prefix:
        return None
    try:
        val = ast.literal_eval(raw)
    except (SyntaxError, ValueError):
        return None
    if isinstance(val, bytes):
        return val.decode("utf-8", errors="replace")
    if isinstance(val, str):
        return val
    return None


def py_string_tokens(src: str) -> list[tokenize.TokenInfo]:
    out: list[tokenize.TokenInfo] = []
    try:
        for tok in tokenize.generate_tokens(StringIO(src).readline):
            if tok.type == tokenize.STRING:
                out.append(tok)
    except (tokenize.TokenError, IndentationError, SyntaxError):
        return out
    return out


def quoted_strings_non_python(src: str) -> list[tuple[int, str]]:
    rows: list[tuple[int, str]] = []
    for match in QUOTED_RE.finditer(src):
        body = match.group("body")
        line = src.count("\n", 0, match.start()) + 1
        unescaped = body.replace(r"\\", "\x00")
        unescaped = unescaped.replace(r"\"", '"').replace(r"\'", "'")
        unescaped = unescaped.replace("\x00", "\\")
        rows.append((line, unescaped))
    return rows


def lexical_hits_for_file(path: Path, src: str) -> list[dict[str, Any]]:
    rel = relposix(path)
    lang = language_of(path)
    hits: list[dict[str, Any]] = []
    if lang == "python":
        tokens = py_string_tokens(src)
        iterable = [
            (int(tok.start[0]), int(tok.start[1]), decode_py_string(tok.string))
            for tok in tokens
        ]
    else:
        iterable = [(line, 0, value) for line, value in quoted_strings_non_python(src)]
        iterable = [(ln, col, val) for ln, col, val in iterable]
    for line, col, value in iterable:
        if value is None:
            continue
        kinds = kinds_in(value)
        if not kinds:
            continue
        hits.append(
            {
                "file": rel,
                "line": line,
                "col": col,
                "value": clip(value),
                "kinds": kinds,
                "language": lang,
                "surface": surface_of(rel),
            }
        )
    return hits


def dotted(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        left = dotted(node.value)
        return f"{left}.{node.attr}" if left else node.attr
    if isinstance(node, ast.Call):
        return dotted(node.func)
    return ""


def mark_constants(node: ast.AST, label: str, into: dict[tuple[int, int], str]) -> None:
    if isinstance(node, ast.Constant) and isinstance(node.value, (str, bytes)):
        into[(node.lineno, node.col_offset)] = label
        return
    if isinstance(node, ast.JoinedStr):
        for part in node.values:
            mark_constants(part, label, into)


def classify_python_ast(src: str) -> dict[tuple[int, int], str]:
    labels: dict[tuple[int, int], str] = {}
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return labels

    for node in ast.walk(tree):
        if isinstance(
            node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
        ):
            body = list(getattr(node, "body", []) or [])
            if (
                body
                and isinstance(body[0], ast.Expr)
                and isinstance(body[0].value, ast.Constant)
                and isinstance(body[0].value.value, str)
            ):
                mark_constants(body[0].value, "excluded-docstring", labels)

    class Visitor(ast.NodeVisitor):
        def visit_Call(self, node: ast.Call) -> None:
            name = dotted(node.func)
            suffix = name.split(".")[-1] if name else ""
            os_path = name.startswith("os.path.") or name.endswith("path.join")
            if suffix in REGEX_FUNCS and (
                name.startswith("re.")
                or name.startswith("regex.")
                or suffix == "compile"
            ):
                role = "excluded-regex"
            elif suffix in {"write_text", "write_bytes", "writelines"}:
                role = "excluded-content"
            elif suffix == "write" and not os_path:
                role = "excluded-content"
            elif suffix in {
                "print",
                "info",
                "debug",
                "warning",
                "error",
                "critical",
                "exception",
                "log",
                "dumps",
                "dump",
                "format",
            }:
                role = "excluded-content"
            elif (
                os_path
                or suffix in PATH_FUNCS
                or (suffix in OS_PATH_FUNCS and "path" in name)
                or name in {"os.replace", "os.rename"}
            ):
                role = "path-use"
            elif suffix in CONTENT_FUNCS:
                role = "excluded-content"
            else:
                role = "other-call"
            args: list[ast.AST] = list(node.args)
            if node.keywords:
                args.extend(k.value for k in node.keywords if k.value is not None)
            for arg in args:
                if role == "path-use":
                    mark_constants(arg, "operational-path-use", labels)
                elif role == "excluded-regex":
                    mark_constants(arg, "excluded-regex", labels)
                elif role == "excluded-content":
                    mark_constants(arg, "excluded-content", labels)
                else:
                    mark_constants(arg, "mention-or-unknown", labels)
            self.generic_visit(node)

        def visit_Constant(self, node: ast.Constant) -> None:
            if isinstance(node.value, (str, bytes)):
                labels.setdefault((node.lineno, node.col_offset), "mention-or-unknown")
            self.generic_visit(node)

    Visitor().visit(tree)
    return labels


def is_relative_glob(value: str) -> bool:
    if Path(value).is_absolute() or DRIVE_RE.search(value):
        return False
    return any(ch in value for ch in "*?[]")


def adjudicate_hit(
    hit: dict[str, Any], ast_labels: dict[tuple[int, int], str] | None
) -> dict[str, Any]:
    row = dict(hit)
    value = str(hit.get("value") or "")

    def finish(use_class: str) -> dict[str, Any]:
        row["use_class"] = use_class
        row["use_class"] = use_class
        return row

    if is_relative_glob(value) and "/home/" not in value and "/Users/" not in value:
        return finish("excluded-relative-glob")
    if ast_labels is None:
        return finish("unresolved-non-python")
    key = (int(hit["line"]), int(hit.get("col") or 0))
    label = ast_labels.get(key)
    if label is None:
        for (ln, col), lab in ast_labels.items():
            if ln == int(hit["line"]) and abs(col - int(hit.get("col") or 0)) <= 2:
                label = lab
                break
    if label == "operational-path-use":
        if is_relative_glob(value):
            return finish("excluded-relative-glob")
        return finish("operational-path-use")
    if label in {
        "excluded-regex",
        "excluded-docstring",
        "excluded-content",
        "mention-or-unknown",
    }:
        return finish(label)
    return finish("unresolved-python")


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def scan_tree(paths: Iterable[Path] | None = None) -> dict[str, Any]:
    files = list(paths) if paths is not None else discover_sources()
    lexical: list[dict[str, Any]] = []
    adjudicated: list[dict[str, Any]] = []
    parse_issues = 0
    for path in files:
        src = read_text(path)
        hits = lexical_hits_for_file(path, src)
        lexical.extend(hits)
        ast_labels = None
        if language_of(path) == "python":
            ast_labels = classify_python_ast(src)
            if hits:
                try:
                    ast.parse(src)
                except SyntaxError:
                    parse_issues += 1
                    ast_labels = {}
        for hit in hits:
            adjudicated.append(adjudicate_hit(hit, ast_labels))
    return {
        "source_files_discovered": len(files),
        "lexical_hits": lexical,
        "adjudicated": adjudicated,
        "parse_issues": parse_issues,
    }


def summarize(scan: dict[str, Any]) -> dict[str, Any]:
    lexical = scan["lexical_hits"]
    adj = scan["adjudicated"]
    by_kind: dict[str, int] = {}
    for hit in lexical:
        for k in hit["kinds"]:
            by_kind[k] = by_kind.get(k, 0) + 1
    by_class: dict[str, int] = {}
    for hit in adj:
        cls = str(hit.get("use_class") or "unknown")
        by_class[cls] = by_class.get(cls, 0) + 1
    operational = [h for h in adj if h.get("use_class") == "operational-path-use"]
    files_lexical = sorted({h["file"] for h in lexical})
    files_operational = sorted({h["file"] for h in operational})
    first_party_op = sorted(
        {h["file"] for h in operational if h.get("surface") == "first-party"}
    )
    return {
        "source_files_discovered": scan["source_files_discovered"],
        "lexical_hit_count": len(lexical),
        "lexical_file_count": len(files_lexical),
        "kind_counts": dict(sorted(by_kind.items())),
        "use_class_counts": dict(sorted(by_class.items())),
        "operational_hit_count": len(operational),
        "operational_file_count": len(files_operational),
        "first_party_operational_file_count": len(first_party_op),
        "first_party_operational_files": first_party_op,
        "operational_files": files_operational,
        "parse_issues": scan.get("parse_issues") or 0,
    }


def control_rows(use_filter: bool) -> dict[str, Any]:
    src = read_text(FIXTURE)
    hits = lexical_hits_for_file(FIXTURE, src)
    labels = classify_python_ast(src) if use_filter else {}
    rows = []
    for hit in hits:
        if use_filter:
            rows.append(adjudicate_hit(hit, labels))
        else:
            row = dict(hit)
            row["use_class"] = "operational-path-use"
            rows.append(row)
    return {"fixture": relposix(FIXTURE), "use_filter": use_filter, "rows": rows}


def evaluate_control() -> dict[str, Any]:
    good = control_rows(use_filter=True)
    mutant = control_rows(use_filter=False)
    rows = good["rows"]
    regex_silent = any(
        r.get("use_class") == "excluded-regex" and "Users" in str(r.get("value") or "")
        for r in rows
    )
    docstring_silent = any(r.get("use_class") == "excluded-docstring" for r in rows)
    open_flagged = any(
        r.get("use_class") == "operational-path-use"
        and "portable" in str(r.get("value") or "")
        for r in rows
    )
    glob_excluded = not any(
        "SKILL.md" in str(r.get("value") or "")
        and r.get("use_class") == "operational-path-use"
        for r in rows
    )
    payload_excluded = not any(
        "~/.claude/" in str(r.get("value") or "")
        and r.get("use_class") == "operational-path-use"
        for r in rows
    )
    mutant_red = (
        all(r.get("use_class") == "operational-path-use" for r in mutant["rows"])
        and len(mutant["rows"]) >= 3
    )
    passed = bool(
        regex_silent
        and docstring_silent
        and open_flagged
        and glob_excluded
        and payload_excluded
        and mutant_red
    )
    return {
        "passed": passed,
        "regex_silent": regex_silent,
        "docstring_silent": docstring_silent,
        "open_flagged": open_flagged,
        "relative_glob_excluded": glob_excluded,
        "write_text_payload_excluded": payload_excluded,
        "mutant_context_filter_disabled_goes_red": mutant_red,
        "good_row_count": len(rows),
        "mutant_row_count": len(mutant["rows"]),
        "good_classes": [r.get("use_class") for r in rows],
        "mutant_classes": [r.get("use_class") for r in mutant["rows"]],
        "good_values": [r.get("value") for r in rows],
    }


def dump_json(path: Path, doc: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")


# Aliases used by probes/emit.
scan_tree = scan_tree
summarize = summarize
dump_json = dump_json
dump_json = dump_json
CATALOG_SENTINEL = CATALOG_SENTINEL
QUESTION = QUESTION

if __name__ == "__main__":
    scan = scan_tree()
    print(json.dumps(summarize(scan), indent=2, sort_keys=True))
    print(json.dumps(evaluate_control(), indent=2, sort_keys=True))
