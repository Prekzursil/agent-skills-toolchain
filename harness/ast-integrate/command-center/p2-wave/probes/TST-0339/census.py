#!/usr/bin/env python3
"""AST census: which function-default parameters tests actually omit.

A default is EXERCISED only when at least one test call site invokes the
function without supplying that argument. Line coverage can be 100% while
every caller passes the argument explicitly — the DEFAULT_MIN_BYTES hole.
"""
from __future__ import annotations

import ast
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
SKIP_DIRS = frozenset(
    {
        "__pycache__",
        ".git",
        ".venv",
        "venv",
        "node_modules",
        "_deps",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        "dist",
        "build",
        ".eggs",
        "egg-info",
    }
)


@dataclass
class DefaultParam:
    file: str
    line: int
    function: str
    qualname: str
    param: str
    kind: str
    default: str
    pos_index: int | None
    nested: bool
    is_method: bool
    module: str
    name_key: str


@dataclass
class CallSite:
    file: str
    line: int
    callee: str
    supplied: set[str] = field(default_factory=set)
    omitted_pos_from: int | None = None
    starred: bool = False
    kw_starred: bool = False


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO).as_posix()
    except ValueError:
        return path.as_posix()


def is_test_path(path: Path) -> bool:
    name = path.name.lower()
    parts = {p.lower() for p in path.parts}
    if name.startswith("test_") or name.endswith("_test.py"):
        return True
    return "tests" in parts


def iter_py(root: Path) -> list[Path]:
    if root.is_file() and root.suffix == ".py":
        return [root]
    out: list[Path] = []
    if not root.is_dir():
        return out
    root_res = root.resolve()
    for path in root.rglob("*.py"):
        try:
            rel_parts = path.resolve().relative_to(root_res).parts
        except ValueError:
            rel_parts = path.parts
        if any(part in SKIP_DIRS or part.startswith(".") for part in rel_parts[:-1]):
            continue
        out.append(path)
    return sorted(out)


def parse_file(path: Path) -> ast.AST | None:
    try:
        return ast.parse(
            path.read_text(encoding="utf-8", errors="replace"), filename=str(path)
        )
    except (OSError, SyntaxError, UnicodeDecodeError):
        return None


def unparse(node: ast.AST | None) -> str:
    if node is None:
        return "None"
    try:
        return ast.unparse(node)
    except Exception:
        return ast.dump(node)


def module_name(path: Path, root: Path) -> str:
    try:
        rel_path = path.resolve().relative_to(root.resolve())
    except ValueError:
        rel_path = Path(path.name)
    parts = list(rel_path.with_suffix("").parts)
    if parts and parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def callee_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def collect_defaults(path: Path, root: Path) -> list[DefaultParam]:
    tree = parse_file(path)
    if tree is None:
        return []
    rows: list[DefaultParam] = []
    mod = module_name(path, root)

    def consider(
        fn: ast.FunctionDef | ast.AsyncFunctionDef,
        qual_parts: list[str],
        nested: bool,
        is_method: bool,
    ) -> None:
        args = fn.args
        pos = list(args.posonlyargs) + list(args.args)
        start = 0
        if is_method and pos and pos[0].arg in {"self", "cls", "mcs"}:
            start = 1
        n_plain = len(pos)
        n_def = len(args.defaults)
        first_def = n_plain - n_def
        for i, arg in enumerate(pos):
            if i < start:
                continue
            if i < first_def:
                continue
            def_node = args.defaults[i - first_def]
            rows.append(
                DefaultParam(
                    file=rel(path),
                    line=arg.lineno,
                    function=fn.name,
                    qualname=".".join(qual_parts + [fn.name]),
                    param=arg.arg,
                    kind="positional",
                    default=unparse(def_node),
                    pos_index=i - start,
                    nested=nested,
                    is_method=is_method,
                    module=mod,
                    name_key=fn.name,
                )
            )
        for arg, def_node in zip(args.kwonlyargs, args.kw_defaults):
            if def_node is None:
                continue
            rows.append(
                DefaultParam(
                    file=rel(path),
                    line=arg.lineno,
                    function=fn.name,
                    qualname=".".join(qual_parts + [fn.name]),
                    param=arg.arg,
                    kind="kwonly",
                    default=unparse(def_node),
                    pos_index=None,
                    nested=nested,
                    is_method=is_method,
                    module=mod,
                    name_key=fn.name,
                )
            )

    def walk(nodes: list[ast.stmt], qual: list[str], nested: bool, in_class: bool) -> None:
        for node in nodes:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                consider(node, qual, nested, is_method=in_class and not nested)
                walk(node.body, qual + [node.name], True, in_class)
            elif isinstance(node, ast.ClassDef):
                walk(node.body, qual + [node.name], nested, True)
            elif isinstance(
                node, (ast.If, ast.For, ast.AsyncFor, ast.While, ast.With, ast.AsyncWith)
            ):
                walk(node.body, qual, nested, in_class)
                walk(getattr(node, "orelse", []) or [], qual, nested, in_class)
            elif isinstance(node, ast.Try):
                walk(node.body, qual, nested, in_class)
                for handler in node.handlers:
                    walk(handler.body, qual, nested, in_class)
                walk(node.orelse, qual, nested, in_class)
                walk(node.finalbody, qual, nested, in_class)

    walk(list(tree.body), [], False, False)
    return rows


def collect_calls(path: Path) -> list[CallSite]:
    tree = parse_file(path)
    if tree is None:
        return []
    sites: list[CallSite] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = callee_name(node.func)
        if not name:
            continue
        starred = any(isinstance(a, ast.Starred) for a in node.args)
        plain_args = [a for a in node.args if not isinstance(a, ast.Starred)]
        kw_starred = any(k.arg is None for k in node.keywords)
        supplied = {k.arg for k in node.keywords if k.arg}
        sites.append(
            CallSite(
                file=rel(path),
                line=getattr(node, "lineno", 0) or 0,
                callee=name,
                supplied=supplied,
                omitted_pos_from=None if starred else len(plain_args),
                starred=starred,
                kw_starred=kw_starred,
            )
        )
    return sites


def call_omits(param: DefaultParam, call: CallSite) -> bool | None:
    """True if this call omits the parameter (exercises the default).

    None means *args/**kwargs could have supplied it.
    """
    if param.param in call.supplied:
        return False
    if call.kw_starred:
        return None
    if param.kind == "kwonly":
        return True
    if param.pos_index is None:
        return True
    if call.starred:
        return None
    if call.omitted_pos_from is None:
        return None
    return call.omitted_pos_from <= param.pos_index


def classify(params: list[DefaultParam], calls: list[CallSite]) -> list[dict[str, Any]]:
    by_name: dict[str, list[CallSite]] = {}
    for call in calls:
        by_name.setdefault(call.callee, []).append(call)

    fn_names: dict[str, set[str]] = {}
    for param in params:
        fn_names.setdefault(param.name_key, set()).add(f"{param.qualname}@{param.file}")

    out: list[dict[str, Any]] = []
    for param in params:
        candidates = by_name.get(param.name_key) or []
        ambiguous = len(fn_names.get(param.name_key) or []) > 1
        omitting = 0
        supplying = 0
        unknown = 0
        used: list[str] = []
        for call in candidates:
            verdict = call_omits(param, call)
            loc = f"{call.file}:{call.line}"
            if verdict is None:
                unknown += 1
            elif verdict:
                omitting += 1
                used.append(loc)
            else:
                supplying += 1
        if omitting > 0:
            status = "exercised"
        elif supplying + omitting + unknown == 0:
            status = "no-test-calls"
        elif unknown > 0 and omitting == 0 and supplying == 0:
            status = "unresolved"
        elif supplying > 0 and omitting == 0:
            status = "unexercised"
        else:
            status = "unresolved"
        row = asdict(param)
        row.update(
            {
                "status": status,
                "name_collision": ambiguous,
                "calls_omitting": omitting,
                "calls_supplying": supplying,
                "calls_unknown": unknown,
                "omitting_sites": used[:12],
                "anchor": f"{param.file}:{param.line}",
            }
        )
        out.append(row)
    return out


def product_and_tests(*, include_product: bool = True) -> tuple[list[Path], list[Path], Path]:
    """Return product and test files.

    include_product=False walks only the planted estate fixture. Live probes
    use that scope because a concurrent agent can add files under tools/
    between emit and recount (measured 2240 -> 2244 on this worktree).
    """
    tools = REPO / "tools"
    fixture_root = HERE / "fixtures" / "estate"
    product: list[Path] = []
    tests: list[Path] = []
    if include_product:
        for path in iter_py(tools):
            if is_test_path(path):
                tests.append(path)
            else:
                product.append(path)
    for path in iter_py(fixture_root):
        if is_test_path(path):
            tests.append(path)
        else:
            product.append(path)
    return product, tests, fixture_root


def run_census(*, include_product: bool = True) -> dict[str, Any]:
    product, tests, fixture_root = product_and_tests(include_product=include_product)
    params: list[DefaultParam] = []
    parse_errors: list[str] = []
    tools_root = REPO / "tools"
    for path in product:
        if parse_file(path) is None:
            parse_errors.append(rel(path))
            continue
        root = fixture_root if "fixtures" in path.parts else tools_root
        params.extend(collect_defaults(path, root))

    calls: list[CallSite] = []
    for path in tests:
        calls.extend(collect_calls(path))

    rows = classify(params, calls)
    rows.sort(key=lambda r: (r["file"], r["line"], r["param"]))

    def count(status: str) -> int:
        return sum(1 for r in rows if r["status"] == status)

    unexercised = [
        {
            "anchor": r["anchor"],
            "function": r["qualname"],
            "param": r["param"],
            "default": r["default"],
            "kind": r["kind"],
            "calls_supplying": r["calls_supplying"],
            "name_collision": r["name_collision"],
        }
        for r in rows
        if r["status"] == "unexercised"
    ]
    no_calls = [
        {
            "anchor": r["anchor"],
            "function": r["qualname"],
            "param": r["param"],
            "default": r["default"],
        }
        for r in rows
        if r["status"] == "no-test-calls"
    ]
    planted = [r for r in rows if r["file"].endswith("fixtures/estate/product.py")]
    return {
        "include_product": include_product,
        "product_files": len(product),
        "test_files": len(tests),
        "parse_errors": parse_errors,
        "n_defaults": len(rows),
        "n_exercised": count("exercised"),
        "n_unexercised": count("unexercised"),
        "n_no_test_calls": count("no-test-calls"),
        "n_unresolved": count("unresolved"),
        "unexercised": unexercised,
        "no_test_calls": no_calls,
        "planted": planted,
        "all_rows": rows,
    }


def main() -> int:
    doc = run_census()
    print(
        f"census n_defaults={doc['n_defaults']} exercised={doc['n_exercised']} "
        f"unexercised={doc['n_unexercised']} no_calls={doc['n_no_test_calls']} "
        f"unresolved={doc['n_unresolved']} product_files={doc['product_files']} "
        f"test_files={doc['test_files']}"
    )
    for row in doc["planted"]:
        print(
            f"planted {row['qualname']}.{row['param']} status={row['status']} "
            f"anchor={row['anchor']} omit={row['calls_omitting']} "
            f"supply={row['calls_supplying']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
