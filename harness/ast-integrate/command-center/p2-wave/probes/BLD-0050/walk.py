#!/usr/bin/env python3
"""Code-site enumerator for BLD-0050.

Finds every subprocess-spawn and network-call AST site on this worktree, then
assigns each site to exactly one spawn/network boundary id.

Mentions (strings in comments, docstrings, or data) are not sites. A Call node
whose function resolves to subprocess.{run,Popen,call,check_output,check_call}
or os.{system,popen}, or to socket/urllib/http.client/requests/httpx/aiohttp
client constructors, is a site.
"""
from __future__ import annotations

import ast
from pathlib import Path
from typing import Any, Iterable

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]  # command-center/p2-wave/probes/BLD-0050 -> repo root

SKIP_PARTS = frozenset(
    {
        "__pycache__",
        ".git",
        "node_modules",
        ".venv",
        "venv",
        ".ruff_cache",
        ".pytest_cache",
        "site-packages",
    }
)
_SITES_CACHE: dict[str, list[dict[str, Any]]] = {}
SKIP_SUFFIXES = frozenset({".pyc", ".pyo"})

SPAWN_ATTRS = frozenset(
    {"run", "Popen", "call", "check_output", "check_call", "check_output"}
)
SPAWN_NAMES = frozenset(
    {"Popen", "check_output", "check_call", "check_output"}
)
OS_SPAWN = frozenset({"system", "popen"})
SUBPROCESS_ALIASES = frozenset({"subprocess", "sp", "subp", "sproc"})
OS_ALIASES = frozenset({"os"})

NET_ATTRS = frozenset(
    {
        "socket",
        "create_connection",
        "create_server",
        "urlopen",
        "urlretrieve",
        "Request",
        "HTTPSConnection",
        "HTTPConnection",
        "urlopen",
        "get",
        "post",
        "put",
        "delete",
        "patch",
        "head",
        "request",
        "Client",
        "ClientSession",
        "wrap_socket",
    }
)
NET_MODULES = frozenset(
    {
        "socket",
        "ssl",
        "http.client",
        "http",
        "urllib",
        "urllib.request",
        "urllib3",
        "requests",
        "httpx",
        "aiohttp",
        "websocket",
        "websockets",
    }
)


def _posix(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def iter_py_files(root: Path) -> Iterable[Path]:
    for path in sorted(root.rglob("*.py")):
        if not path.is_file():
            continue
        parts = set(path.relative_to(root).parts)
        if parts & SKIP_PARTS:
            continue
        if path.suffix in SKIP_SUFFIXES:
            continue
        rel = _posix(path, root)
        if "/fixtures/" in f"/{rel}" and "/probes/BLD-0050/" in f"/{rel}":
            continue
        yield path


def _import_aliases(tree: ast.AST) -> tuple[set[str], set[str], set[str], set[str]]:
    """Return (subprocess_mods, spawn_from_import, os_mods, net_qualifiers)."""
    sub_mods: set[str] = set(SUBPROCESS_ALIASES)
    spawn_from: set[str] = set()
    os_mods: set[str] = set(OS_ALIASES)
    net_qual: set[str] = set(NET_MODULES)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                name = alias.name
                asname = alias.asname or name
                if name == "subprocess" or name.startswith("subprocess."):
                    sub_mods.add(asname)
                if name == "os" or name.startswith("os."):
                    os_mods.add(asname)
                if name in NET_MODULES or name.split(".")[0] in NET_MODULES:
                    net_qual.add(asname)
                    net_qual.add(name)
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            for alias in node.names:
                asname = alias.asname or alias.name
                if mod == "subprocess" and alias.name in SPAWN_ATTRS | SPAWN_NAMES:
                    spawn_from.add(asname)
                if mod == "os" and alias.name in OS_SPAWN:
                    spawn_from.add(asname)
                if mod in NET_MODULES or mod.startswith("urllib"):
                    net_qual.add(asname)
    return sub_mods, spawn_from, os_mods, net_qual


def _qual_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return f"{_qual_name(node.value)}.{node.attr}"
    return ""


def _string_hints(call: ast.Call) -> list[str]:
    hints: list[str] = []
    for sub in ast.walk(call):
        if isinstance(sub, ast.Constant) and isinstance(sub.value, str):
            if sub.value.strip():
                hints.append(sub.value)
    return hints


def _is_spawn(
    call: ast.Call, sub_mods: set[str], spawn_from: set[str], os_mods: set[str]
) -> bool:
    func = call.func
    if isinstance(func, ast.Name) and func.id in spawn_from:
        return True
    if isinstance(func, ast.Attribute):
        if func.attr in SPAWN_ATTRS and isinstance(func.value, ast.Name):
            if func.value.id in sub_mods:
                return True
        if func.attr in OS_SPAWN and isinstance(func.value, ast.Name):
            if func.value.id in os_mods:
                return True
        # subprocess.Popen already covered; os.popen too.
    return False


def _is_network(call: ast.Call, net_qual: set[str]) -> bool:
    qn = _qual_name(call.func)
    if not qn:
        return False
    head = qn.split(".", 1)[0]
    if head not in net_qual and qn not in net_qual:
        return False
    # requests.get / httpx.Client / socket.socket / urllib.request.urlopen
    attr = qn.rsplit(".", 1)[-1]
    if attr in NET_ATTRS or qn in {"socket.socket", "ssl.wrap_socket"}:
        return True
    if head in {"requests", "httpx", "aiohttp", "urllib3"} and attr in NET_ATTRS:
        return True
    return False


def spawn_boundary_id(rel: str, hints: list[str], func: str) -> str:
    rel_n = rel.replace("\\", "/")
    blob = "\n".join(hints)
    low = blob.lower()
    tokens: set[str] = set()
    for h in hints:
        tokens.add(h)
        for part in h.replace("=", " ").split():
            tokens.add(part)
    if rel_n.endswith("seed-stage/bringup_cursor_fleet.py"):
        return "TB-SPAWN-SCW"
    if rel_n.endswith("seed-stage/dispatch_cursor.py"):
        if any("pgrep" in (h.lower()) for h in hints) or "pgrep" in tokens:
            return "TB-SPAWN-PGREP"
        if "bash" in tokens or "bash" in low:
            return "TB-SPAWN-BASH"
        # Popen launches cursor-agent. --sandbox/--model are agent argv. `-h` is the
        # agent binary help probe. sys.executable + _measure_one_delivered is python.
        if func.endswith("Popen"):
            return "TB-SPAWN-CURSOR-AGENT"
        agent_argv = ("--sandbox", "--model", "--force", "--trust", "--workspace")
        if any(tok in tokens for tok in agent_argv):
            return "TB-SPAWN-CURSOR-AGENT"
        if "-h" in tokens:
            return "TB-SPAWN-CURSOR-AGENT"
        return "TB-SPAWN-PYTHON"
    if "git" in tokens:
        return "TB-SPAWN-GIT"
    return "TB-SPAWN-PYTHON"


def find_sites(root: Path | None = None) -> list[dict[str, Any]]:
    root = root or REPO
    cache_key = str(root.resolve())
    cached = _SITES_CACHE.get(cache_key)
    if cached is not None:
        return [dict(s) for s in cached]
    sites: list[dict[str, Any]] = []
    for path in iter_py_files(root):
        rel = _posix(path, root)
        try:
            src = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        try:
            tree = ast.parse(src)
        except SyntaxError:
            continue
        sub_mods, spawn_from, os_mods, net_qual = _import_aliases(tree)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            kind = None
            if _is_spawn(node, sub_mods, spawn_from, os_mods):
                kind = "spawn"
            elif _is_network(node, net_qual):
                kind = "network"
            if kind is None:
                continue
            hints = _string_hints(node)
            func = _qual_name(node.func)
            line = int(getattr(node, "lineno", 0) or 0)
            bid = (
                spawn_boundary_id(rel, hints, func)
                if kind == "spawn"
                else "TB-NET-DIRECT"
            )
            sites.append(
                {
                    "path": rel,
                    "line": line,
                    "kind": kind,
                    "func": func,
                    "hints": hints[:12],
                    "boundary_id": bid,
                    "site_id": f"{rel}:{line}:{kind}",
                }
            )
    sites.sort(key=lambda s: (s["path"], s["line"], s["kind"]))
    _SITES_CACHE[cache_key] = sites
    return [dict(s) for s in sites]


def snippet_present(root: Path, rel: str, snippet: str) -> tuple[bool, int]:
    path = Path(rel)
    if not path.is_absolute():
        path = root / rel
    if not path.is_file():
        return False, 0
    text = path.read_text(encoding="utf-8")
    idx = text.find(snippet)
    if idx < 0:
        return False, 0
    return True, text[:idx].count("\n") + 1


def test_present(root: Path, rel: str) -> bool:
    path = Path(rel)
    if not path.is_absolute():
        path = root / rel
    return path.is_file() and path.stat().st_size > 0


def check_status_for(
    *,
    consumed: bool,
    root: Path,
    rule_path: str | None,
    snippet: str | None,
    test_path: str | None,
    rule_override_path: Path | None = None,
) -> str:
    """CHECKED only with a live named rule (path+snippet) AND a live test file.

    A comment asserting safety, or a naming convention, is UNCHECKED.
    CONSUMED short-circuits (ADV-0021 install path — not re-audited).
    """
    if consumed:
        return "CONSUMED"
    if not rule_path or not snippet or not test_path:
        return "UNCHECKED"
    target = rule_override_path if rule_override_path is not None else rule_path
    ok, _line = snippet_present(root, str(target), snippet)
    if not ok:
        return "UNCHECKED"
    if not test_present(root, test_path):
        return "UNCHECKED"
    return "CHECKED"


def site_map(sites: list[dict[str, Any]]) -> dict[str, str]:
    out: dict[str, str] = {}
    for site in sites:
        sid = site["site_id"]
        bid = site["boundary_id"]
        if sid in out and out[sid] != bid:
            raise RuntimeError(f"site {sid} mapped to both {out[sid]} and {bid}")
        out[sid] = bid
    return out


if __name__ == "__main__":
    rows = find_sites()
    by: dict[str, int] = {}
    for s in rows:
        by[s["boundary_id"]] = by.get(s["boundary_id"], 0) + 1
    print(f"sites={len(rows)}")
    for k in sorted(by):
        print(f"  {k} {by[k]}")
    for s in rows:
        print(f"{s['site_id']} -> {s['boundary_id']} func={s['func']}")
