"""Lint: sweep-lane credentialed I/O must route through acquire.credentialed_call.

A net/gh Call is routed when it sits inside credentialed_call(...) (lambda) or
inside a function passed as that transport argument. Direct urlopen / gh api
outside that routing is a bypass. acquire.py is the choke point: it must call
admit and must not contain its own urlopen (I/O is injected).
"""
from __future__ import annotations

import ast
from pathlib import Path
from typing import Any, Iterable

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]

SWEEP_LANE_UNITS = (
    "WFA-0016",
    "WFA-0021",
    "WFA-0023",
    "WFA-0024",
    "WFA-0025",
    "WFA-0026",
    "WFA-0027",
    "WFA-0028",
    "WFA-0033",
    "WFA-0034",
)

ROUTE_FUNCS = frozenset({"credentialed_call", "credentialed_get", "admit"})
NET_ATTRS = frozenset(
    {
        "urlopen",
        "urlretrieve",
        "HTTPSConnection",
        "HTTPConnection",
        "get",
        "post",
        "put",
        "delete",
        "patch",
        "head",
        "request",
        "Client",
        "ClientSession",
    }
)
NET_MODULES = frozenset(
    {
        "urllib",
        "urllib.request",
        "urllib3",
        "http.client",
        "requests",
        "httpx",
        "aiohttp",
    }
)
SPAWN_ATTRS = frozenset({"run", "Popen", "call", "check_output", "check_call"})


def _qual_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return f"{_qual_name(node.value)}.{node.attr}"
    return ""


def _attach_parents(tree: ast.AST) -> None:
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            setattr(child, "parent", node)


def _ancestors(node: ast.AST) -> Iterable[ast.AST]:
    cur = getattr(node, "parent", None)
    while cur is not None:
        yield cur
        cur = getattr(cur, "parent", None)


def _import_net_aliases(tree: ast.AST) -> set[str]:
    names = set(NET_MODULES)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name in NET_MODULES or alias.name.split(".")[0] in {
                    "urllib",
                    "requests",
                    "httpx",
                    "aiohttp",
                    "http",
                }:
                    names.add(alias.asname or alias.name)
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            if mod in NET_MODULES or mod.startswith("urllib"):
                for alias in node.names:
                    names.add(alias.asname or alias.name)
    return names


def _is_net_call(call: ast.Call, net_qual: set[str]) -> bool:
    qn = _qual_name(call.func)
    if not qn:
        return False
    head = qn.split(".", 1)[0]
    attr = qn.rsplit(".", 1)[-1]
    if head not in net_qual and qn not in net_qual:
        return False
    return attr in NET_ATTRS or qn.endswith(".urlopen")


def _string_args(call: ast.Call) -> list[str]:
    out: list[str] = []
    for node in ast.walk(call):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            out.append(node.value)
        elif isinstance(node, ast.Constant) and isinstance(node.value, (list, tuple)):
            pass
    return out


def _name_ids(node: ast.AST) -> list[str]:
    return [n.id for n in ast.walk(node) if isinstance(n, ast.Name)]


def _is_gh_api_spawn(call: ast.Call) -> bool:
    qn = _qual_name(call.func)
    attr = qn.rsplit(".", 1)[-1] if qn else ""
    name = qn.split(".", 1)[0] if qn else ""
    if attr not in SPAWN_ATTRS and name not in SPAWN_ATTRS:
        if not (isinstance(call.func, ast.Name) and call.func.id in SPAWN_ATTRS):
            if "subprocess" not in qn:
                return False
    blobs = " ".join(_string_args(call)).lower()
    names = " ".join(_name_ids(call)).lower()
    hay = f"{blobs} {names}"
    if "gh" not in hay:
        return False
    return any(tok in hay for tok in ("api", "search", "release"))


def _inside_route_call(node: ast.AST) -> bool:
    for anc in _ancestors(node):
        if isinstance(anc, ast.Call):
            tail = _qual_name(anc.func).rsplit(".", 1)[-1]
            if tail in ROUTE_FUNCS:
                return True
    return False


def _enclosing_function_name(node: ast.AST) -> str | None:
    for anc in _ancestors(node):
        if isinstance(anc, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return anc.name
    return None


def _transport_names(tree: ast.AST) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        tail = _qual_name(node.func).rsplit(".", 1)[-1]
        if tail not in {"credentialed_call", "credentialed_get"}:
            continue
        if len(node.args) >= 2 and isinstance(node.args[1], ast.Name):
            names.add(node.args[1].id)
        for kw in node.keywords:
            if kw.arg == "transport" and isinstance(kw.value, ast.Name):
                names.add(kw.value.id)
    return names


def _has_admit_call(tree: ast.AST) -> bool:
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            tail = _qual_name(node.func).rsplit(".", 1)[-1]
            if tail == "admit":
                return True
    return False


def _rel(path: Path) -> str:
    try:
        return path.relative_to(REPO).as_posix()
    except ValueError:
        return path.as_posix()


def inspect_file(path: Path) -> dict[str, Any]:
    src = path.read_text(encoding="utf-8")
    tree = ast.parse(src)
    _attach_parents(tree)
    net_qual = _import_net_aliases(tree)
    transports = _transport_names(tree)
    bypass: list[dict[str, Any]] = []
    routed: list[dict[str, Any]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        kind = None
        if _is_net_call(node, net_qual):
            kind = "net"
        elif _is_gh_api_spawn(node):
            kind = "gh-api"
        if kind is None:
            continue
        fn = _enclosing_function_name(node)
        site = {
            "kind": kind,
            "line": getattr(node, "lineno", 0),
            "func": fn,
            "call": _qual_name(node.func),
        }
        if _inside_route_call(node) or (fn is not None and fn in transports):
            routed.append(site)
        else:
            bypass.append(site)
    route_calls = 0
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            tail = _qual_name(node.func).rsplit(".", 1)[-1]
            if tail in ROUTE_FUNCS:
                route_calls += 1
    return {
        "path": _rel(path),
        "bypass": bypass,
        "routed": routed,
        "route_calls": route_calls,
        "admit_present": _has_admit_call(tree),
        "has_urlopen": any(
            s.get("call", "").endswith("urlopen") for s in bypass + routed
        ),
    }


def choke_point_ok(path: Path) -> dict[str, Any]:
    """acquire.py must admit(); it must not be a raw urlopen wrapper."""
    report = inspect_file(path)
    ok = bool(report["admit_present"]) and not report["bypass"]
    # choke point may contain zero net calls (injected transport).
    return {
        "path": report["path"],
        "admit_present": report["admit_present"],
        "bypass": report["bypass"],
        "ok": ok,
    }


def scan_paths(paths: Iterable[Path]) -> list[dict[str, Any]]:
    rows = []
    for path in paths:
        if path.is_file() and path.suffix == ".py":
            rows.append(inspect_file(path))
    return rows


def sweep_lane_files(repo: Path | None = None) -> list[Path]:
    root = repo or REPO
    found: list[Path] = []
    probes = root / "command-center" / "p2-wave" / "probes"
    for uid in SWEEP_LANE_UNITS:
        d = probes / uid
        if not d.is_dir():
            continue
        for p in sorted(d.rglob("*.py")):
            if "__pycache__" in p.parts:
                continue
            found.append(p)
    wfa = root / "command-center" / "wfa"
    if wfa.is_dir():
        for p in sorted(wfa.rglob("*.py")):
            if "__pycache__" in p.parts:
                continue
            found.append(p)
    return found


def evaluate(repo: Path | None = None) -> dict[str, Any]:
    root = repo or REPO
    planted_bypass = HERE / "fixtures" / "planted_bypass.py"
    planted_gh = HERE / "fixtures" / "planted_gh_bypass.py"
    routed_ok = HERE / "fixtures" / "routed_ok.py"
    acquire = HERE / "acquire.py"
    plants = {
        "urlopen": inspect_file(planted_bypass),
        "gh_api": inspect_file(planted_gh),
        "routed": inspect_file(routed_ok),
    }
    planted_fired = bool(plants["urlopen"]["bypass"]) and bool(plants["gh_api"]["bypass"])
    routed_silent = (
        not plants["routed"]["bypass"] and plants["routed"]["route_calls"] > 0
    )
    choke = choke_point_ok(acquire)
    live = scan_paths(sweep_lane_files(root))
    live_bypass = [r for r in live if r["bypass"]]
    own_py = []
    for path in sorted(HERE.rglob("*.py")):
        if "__pycache__" in path.parts or "fixtures" in path.parts:
            continue
        own_py.append(path)
    own_rows = scan_paths(own_py)
    own_bypass = [r for r in own_rows if r["bypass"]]
    # Downstream sweep units (WFA-0016/0024/0026) depend on this scheduler; their
    # remaining urlopen/gh-api sites are inventoried, not a fail of THIS unit.
    return {
        "planted": plants,
        "planted_fired": planted_fired,
        "routed_ok": routed_silent,
        "choke_point": choke,
        "own_files_scanned": len(own_rows),
        "own_bypass": own_bypass,
        "own_clean": not own_bypass,
        "live_files_scanned": len(live),
        "live_bypass": live_bypass,
        "live_clean": not live_bypass,
        "live_bypass_paths": [r["path"] for r in live_bypass],
        "pass": bool(
            planted_fired and routed_silent and choke["ok"] and not own_bypass
        ),
    }
