"""Mechanism comparison: identifier-normalized shingles, not filenames.

Token / export-name search is the strike-1 detector (recall-failure on
renames). The load-bearing classifier is Jaccard overlap of w-shingles
taken from a keyword-preserving, identifier-elided token stream, plus a
Python AST-dump fingerprint when the source parses as Python.
"""
from __future__ import annotations

import ast
import hashlib
import re
from pathlib import Path
from typing import Iterable

SHINGLE_W = 5
DUPLICATE_THRESHOLD = 0.52
NOVEL_CEILING = 0.34
MAX_SOURCE_BYTES = 512_000
MECH_SUFFIXES = {".py", ".mjs", ".js", ".cjs", ".ts"}

DELETED_SYMBOL = "BLD0033_DELETED_ONLY_SYMBOL_qx9v"

_COMMENT_JS = re.compile(r"/\*.*?\*/|//[^\n]*", re.DOTALL)
_COMMENT_PY = re.compile(r"#.*?$", re.MULTILINE)
_STRING = re.compile(
    r"'''(?:\\.|[^'\\])*'''|"
    r'"""(?:\\.|[^"\\])*"""|'
    r"'(?:\\.|[^'\\])*'|"
    r'"(?:\\.|[^"\\])*"',
    re.DOTALL,
)
_TOKEN = re.compile(r"[A-Za-z_][A-Za-z0-9_]*|[0-9]+|[(){}\[\],.;:+\-*/%<>=!&|?]")

_JS_KW = frozenset(
    {
        "break",
        "case",
        "catch",
        "class",
        "const",
        "continue",
        "default",
        "delete",
        "do",
        "else",
        "export",
        "extends",
        "finally",
        "for",
        "function",
        "if",
        "import",
        "in",
        "instanceof",
        "let",
        "new",
        "return",
        "static",
        "super",
        "switch",
        "throw",
        "try",
        "typeof",
        "var",
        "void",
        "while",
        "with",
        "yield",
        "async",
        "await",
        "from",
        "of",
        "null",
        "true",
        "false",
        "undefined",
        "this",
        "new",
        "Map",
        "Set",
        "Object",
        "JSON",
        "Error",
        "Number",
        "String",
        "Boolean",
        "Array",
        "TextEncoder",
        "Math",
    }
)
_PY_KW = frozenset(
    {
        "and",
        "as",
        "assert",
        "async",
        "await",
        "break",
        "class",
        "continue",
        "def",
        "del",
        "elif",
        "else",
        "except",
        "finally",
        "for",
        "from",
        "global",
        "if",
        "import",
        "in",
        "is",
        "lambda",
        "nonlocal",
        "not",
        "or",
        "pass",
        "raise",
        "return",
        "try",
        "while",
        "with",
        "yield",
        "None",
        "True",
        "False",
    }
)
_EXPORT_JS = re.compile(
    r"export\s+(?:async\s+)?function\s+([A-Za-z_][A-Za-z0-9_]*)"
    r"|export\s+(?:const|let|var)\s+([A-Za-z_][A-Za-z0-9_]*)"
)
_EXPORT_PY = re.compile(r"^(?:async\s+)?def\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(", re.MULTILINE)


def _strip_comments(src: str, lang: str) -> str:
    if lang == "py":
        src = _COMMENT_PY.sub(" ", src)
    else:
        src = _COMMENT_JS.sub(" ", src)
    src = _STRING.sub(" STR ", src)
    return src


def detect_lang(path: Path | str, src: str) -> str:
    suffix = Path(path).suffix.lower()
    if suffix in {".py"}:
        return "py"
    if suffix in {".mjs", ".js", ".cjs", ".ts"}:
        return "js"
    if "export function" in src or "export const" in src:
        return "js"
    if "def " in src and "import " in src:
        return "py"
    return "js"


def tokenize(src: str, lang: str) -> list[str]:
    body = _strip_comments(src, lang)
    raw = _TOKEN.findall(body)
    kws = _PY_KW if lang == "py" else _JS_KW
    out: list[str] = []
    for tok in raw:
        if tok.isdigit():
            out.append("NUM")
        elif tok in kws or not tok[0].isalpha() and tok[0] != "_":
            out.append(tok)
        else:
            out.append("ID")
    return out


def shingles(tokens: list[str], w: int = SHINGLE_W) -> set[tuple[str, ...]]:
    if not tokens:
        return set()
    if len(tokens) < w:
        return {tuple(tokens)}
    return {tuple(tokens[i : i + w]) for i in range(len(tokens) - w + 1)}


def jaccard(a: set, b: set) -> float:
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def py_ast_types(src: str) -> list[str]:
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return []
    return [type(n).__name__ for n in ast.walk(tree)]


def exports_of(src: str, lang: str) -> list[str]:
    names: list[str] = []
    if lang == "py":
        names.extend(_EXPORT_PY.findall(src))
    else:
        for a, b in _EXPORT_JS.findall(src):
            names.append(a or b)
    return [n for n in names if n]


def fingerprint(path: Path | str, src: str | None = None) -> dict:
    p = Path(path)
    try:
        p = p.resolve()
    except OSError:
        pass
    if src is None:
        src = p.read_text(encoding="utf-8")
    if len(src.encode("utf-8", errors="replace")) > MAX_SOURCE_BYTES:
        src = src[:MAX_SOURCE_BYTES]
    lang = detect_lang(p, src)
    tokens = tokenize(src, lang)
    sh = shingles(tokens)
    ast_types = py_ast_types(src) if lang == "py" else []
    return {
        "path": str(p).replace("\\", "/"),
        "lang": lang,
        "exports": exports_of(src, lang),
        "token_count": len(tokens),
        "shingles": sh,
        "ast_types": ast_types,
        "sha256": hashlib.sha256(src.replace("\r\n", "\n").encode()).hexdigest(),
        "bytes": len(src.replace("\r\n", "\n").encode()),
    }


def compare(subject: dict, candidate: dict) -> dict:
    sh_j = jaccard(subject["shingles"], candidate["shingles"])
    ast_j = None
    if subject["ast_types"] and candidate["ast_types"]:
        ast_j = jaccard(set(subject["ast_types"]), set(candidate["ast_types"]))
    export_overlap = sorted(set(subject["exports"]) & set(candidate["exports"]))
    filename_same = Path(subject["path"]).name == Path(candidate["path"]).name
    # Load-bearing score is identifier-normalized shingles.
    # Python AST *node-type* Jaccard is diagnostic only: CLI scripts share
    # Module/FunctionDef/If/Name bags (measured 0.84-0.95 on unrelated
    # tools/command-center vs tools/measure-guard files) and must not boost
    # a 0.19-0.30 shingle match over DUPLICATE_THRESHOLD.
    score = sh_j
    return {
        "candidate_path": candidate["path"],
        "shingle_jaccard": round(sh_j, 4),
        "ast_jaccard": None if ast_j is None else round(ast_j, 4),
        "score": round(score, 4),
        "export_overlap": export_overlap,
        "filename_same": filename_same,
        "export_name_hit": bool(export_overlap),
    }


def token_search_hit(subject_src: str, haystack: str) -> bool:
    """Strike-1 detector: raw identifier / export tokens from the subject."""
    names = exports_of(subject_src, detect_lang("x.mjs", subject_src))
    if not names:
        names = [t for t in re.findall(r"[A-Za-z_][A-Za-z0-9_]{8,}", subject_src)]
    return any(n in haystack for n in names)


def classify_score(score: float, surfaces_complete: bool) -> str:
    if score >= DUPLICATE_THRESHOLD:
        return "DUPLICATE-OF"
    if not surfaces_complete:
        return "NOT-CHECKED"
    return "GENUINELY-NEW"


def best_match(subject: dict, candidates: Iterable[dict]) -> dict | None:
    ranked = []
    for cand in candidates:
        if cand["path"] == subject["path"]:
            continue
        ranked.append(compare(subject, cand))
    if not ranked:
        return None
    ranked.sort(key=lambda r: r["score"], reverse=True)
    return ranked[0]


def load_fp(path: Path) -> dict | None:
    try:
        if path.stat().st_size > MAX_SOURCE_BYTES:
            return None
        src = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None
    return fingerprint(path, src)
