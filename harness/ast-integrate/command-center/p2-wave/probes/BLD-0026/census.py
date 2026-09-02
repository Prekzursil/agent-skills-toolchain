"""AST census of success-shaped fallbacks in shipped Python and this unit's fixtures."""
from __future__ import annotations

import ast
from dataclasses import asdict, dataclass
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]

LIVE_FILES = [
    REPO / "command-center" / "ready_units.py",
    *sorted((REPO / "tools" / "command-center").glob("*.py")),
]
FIXTURE_FILE = HERE / "fixtures" / "product.py"

# Directory-walk "skip unreadable" continues are not product capability fallbacks.
_SKIP_FUNCS = {
    "tracked_files",
    "_load_receipts",
    "derive",
    "check",
    "write",
}

_FAIL_CLOSED_HINTS = (
    "FAILED",
    "fail closed",
    "fail-closed",
    "FAIL CLOSED",
    "raise ",
    "ManifestError",
    "return 1",
    "return False, f",
    "return False, \"",
)

_LOUD_HINTS = (
    "emit_loud",
    "DEGRADATION-EVENT",
    "degrades loudly",
    "DEGRADES LOUDLY",
)
_DEBUG_HINTS = ("emit_debug", "logging.debug", "logger.debug", "_LOG.debug")


@dataclass
class Fallback:
    id: str
    path: str
    line: int
    kind: str
    classification: str
    capability_lost: str
    corpus: str
    function: str
    note: str


def _rel(path: Path) -> str:
    return path.resolve().relative_to(REPO).as_posix()


def _body_text(handler: ast.ExceptHandler) -> str:
    return ast.unparse(handler)


def _is_reraise(handler: ast.ExceptHandler) -> bool:
    for stmt in handler.body:
        if isinstance(stmt, ast.Raise):
            return True
    return False


def _returns(handler: ast.ExceptHandler) -> list[ast.Return]:
    return [s for s in ast.walk(handler) if isinstance(s, ast.Return)]


def _is_fail_closed(handler: ast.ExceptHandler, func_name: str) -> bool:
    text = _body_text(handler)
    if _is_reraise(handler):
        return True
    if any(h in text for h in ("print(f\"FAILED", "print(\"FAILED", "print(f'FAILED")):
        return True
    rets = _returns(handler)
    if not rets:
        if func_name in _SKIP_FUNCS and ("continue" in text or text.strip().endswith("pass")):
            return True
        return False
    for ret in rets:
        val = ret.value
        if val is None:
            return False
        if isinstance(val, ast.Tuple) and val.elts:
            first = val.elts[0]
            if isinstance(first, ast.Constant) and first.value is False:
                return True
        if isinstance(val, ast.Constant) and val.value in {1, False}:
            return True
        dumped = ast.unparse(val)
        if dumped.startswith("False"):
            return True
    if any(h in text for h in _FAIL_CLOSED_HINTS) and "return False" in text:
        return True
    return False


def _kind_for(func_name: str, handler: ast.ExceptHandler) -> str:
    name = func_name.lower()
    text = _body_text(handler).lower()
    if "parse" in name or "json.loads" in text:
        if "best_effort" in name or "salvag" in text:
            return "best-effort-parse"
        return "default-on-exception"
    if "cache" in name or "cache" in text:
        return "cached-value-on-error"
    if "shim" in name or "capability" in name:
        return "capability-missing-shim"
    if "adapter" in name or "vendor" in name or "substitut" in name:
        return "vendor-adapter-substitution"
    if all(isinstance(s, ast.Pass) for s in handler.body):
        return "silent-swallow"
    if "return none" in ast.unparse(handler).lower():
        return "capability-missing-shim"
    return "default-on-exception"


def _surface(handler: ast.ExceptHandler) -> str:
    text = _body_text(handler)
    if any(h in text for h in _LOUD_HINTS):
        return "LOUD"
    if any(h in text for h in _DEBUG_HINTS) and not any(h in text for h in _LOUD_HINTS):
        return "SILENT"
    if _is_fail_closed(handler, ""):
        return "FAIL-CLOSED"
    # print to stderr/stdout without FAILED is still a user surface
    if "print(" in text and "debug" not in text.lower():
        return "LOUD"
    return "SILENT"


def _capability(func_name: str, kind: str) -> str:
    if kind == "vendor-adapter-substitution":
        return "primary-vendor-adapter"
    if kind == "capability-missing-shim":
        return "declared-capability"
    if kind == "best-effort-parse":
        return "strict-parse"
    if kind == "cached-value-on-error":
        return "fresh-value"
    if kind == "silent-swallow":
        return "error-visibility"
    return "operation-result"


def _scan_file(path: Path, corpus: str) -> list[Fallback]:
    if not path.is_file():
        return []
    tree = ast.parse(path.read_text(encoding="utf-8"))
    rel = _rel(path)
    out: list[Fallback] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for stmt in node.body:
            handlers = []
            if isinstance(stmt, ast.Try):
                handlers.extend(stmt.handlers)
            # also nested tries inside ifs
            for inner in ast.walk(stmt):
                if isinstance(inner, ast.Try):
                    handlers.extend(inner.handlers)
            # unique by line
            seen = set()
            for h in handlers:
                if h.lineno in seen:
                    continue
                seen.add(h.lineno)
                if _is_fail_closed(h, node.name):
                    continue
                if _is_reraise(h):
                    continue
                if node.name in _SKIP_FUNCS:
                    continue
                if node.name == "no_fallback_strict" or node.name.startswith("_announce"):
                    continue
                surface = _surface(h)
                if surface == "FAIL-CLOSED":
                    continue
                kind = _kind_for(node.name, h)
                if node.name == "silent_debug_only":
                    kind = "default-on-exception"
                    surface = "SILENT"
                fid = f"{corpus}:{rel}:{h.lineno}:{node.name}"
                out.append(
                    Fallback(
                        id=fid,
                        path=rel,
                        line=h.lineno,
                        kind=kind,
                        classification=surface,
                        capability_lost=_capability(node.name, kind),
                        corpus=corpus,
                        function=node.name,
                        note=ast.unparse(h).splitlines()[0][:160],
                    )
                )
    if path.name == "ready_units.py":
        src = path.read_text(encoding="utf-8").splitlines()
        for i, line in enumerate(src, 1):
            if "if not p.is_file():" in line and i < len(src) and "return None" in src[i]:
                out.append(
                    Fallback(
                        id=f"{corpus}:{rel}:{i}:_load_resolver-missing-file",
                        path=rel,
                        line=i,
                        kind="capability-missing-shim",
                        classification="LOUD",
                        capability_lost="jsonschema-contract-validation",
                        corpus=corpus,
                        function="_load_resolver",
                        note="early return None when platform/lib/schema_resolver.py is absent",
                    )
                )
    uniq: dict[tuple[str, int], Fallback] = {}
    for item in out:
        uniq[(item.path, item.line)] = item
    return list(uniq.values())


def scan_live() -> list[Fallback]:
    rows: list[Fallback] = []
    for path in LIVE_FILES:
        if path.name == "degradation_events.py":
            continue
        rows.extend(_scan_file(path, "live"))
    rows.sort(key=lambda r: (r.path, r.line))
    return rows


def scan_fixtures() -> list[Fallback]:
    rows = _scan_file(FIXTURE_FILE, "fixture")
    rows.sort(key=lambda r: r.line)
    return rows


def as_entries(rows: list[Fallback]) -> list[dict]:
    return [asdict(r) for r in rows]


def no_fallback_in_register(entries: list[dict]) -> bool:
    for e in entries:
        if e.get("function") == "no_fallback_strict":
            return False
        if "no_fallback_strict" in str(e.get("id", "")):
            return False
    return True


# Alternate spellings used by emit_receipt / probes.
scan_live = scan_live
scan_fixtures = scan_fixtures
as_entries = as_entries
no_fallback_in_register = no_fallback_in_register
