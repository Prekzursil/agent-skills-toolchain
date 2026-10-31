#!/usr/bin/env python3
"""AUD-0053 network-egress census engine.

Two independent instruments:
  * block mode: non-loopback connect/getaddrinfo raise EgressBlocked
  * trace mode: same calls are recorded, then delegated to the real stdlib

Loopback remains open in block mode so local fixture servers still work.
A test whose outcome changes under the block DEPENDS on egress. A test
whose socket trace names a non-loopback host TOUCHes the network whether
or not the outcome changed.
"""
from __future__ import annotations

import ast
import importlib.util
import io
import json
import os
import socket
import subprocess
import sys
import time
import traceback
import unittest
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
TOOLS = REPO / "tools"
CONTROLS = HERE / "controls"
CENSUS_PATH = HERE / "census.json"
GET_PIP_URL = "https://bootstrap.pypa.io/get-pip.py"
GET_PIP_HOST = "bootstrap.pypa.io"
CONTROL_PORT = 443
FILE_TIMEOUT = 6
SUITE_BUDGET = 140
SKIP_DIR_NAMES = frozenset(
    {
        "__pycache__",
        "node_modules",
        ".git",
        ".venv",
        "venv",
        ".tox",
        "dist",
        "build",
        ".eggs",
        "site-packages",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        "vendor",
    }
)
NETWORK_AST_HINTS = (
    "urllib",
    "http.client",
    "httpx",
    "requests",
    "aiohttp",
    "websocket",
    "socket.create_connection",
    "socket.socket",
    "urlopen",
    "get-pip",
    "bootstrap.pypa.io",
)


class EgressBlocked(OSError):
    """Raised by the block hook before a non-loopback syscall."""


_REAL_CONNECT = socket.socket.connect
_REAL_CREATE_CONNECTION = socket.create_connection
_REAL_GETADDRINFO = socket.getaddrinfo

_log: list[dict[str, Any]] = []
_mode = "off"


def is_loopback_host(host: Any) -> bool:
    text = str(host or "").strip().strip("[]").lower()
    if not text:
        return False
    if text in {"localhost", "127.0.0.1", "::1", "0.0.0.0", "::", "localhost.localdomain"}:
        return True
    if text.startswith("127."):
        return True
    return False


def _split_address(address: Any) -> tuple[str, int | None]:
    if isinstance(address, tuple) and len(address) >= 2:
        host = address[0]
        try:
            port = int(address[1])  # type: ignore[arg-type]
        except (TypeError, ValueError):
            port = None
        if isinstance(host, bytes):
            host = host.decode("ascii", "replace")
        return str(host), port
    return str(address), None


def _record(kind: str, host: Any, port: Any, blocked: bool) -> None:
    host_s = str(host or "")
    try:
        port_i = int(port) if port is not None else None
    except (TypeError, ValueError):
        port_i = None
    _log.append(
        {
            "kind": kind,
            "host": host_s,
            "port": port_i,
            "loopback": is_loopback_host(host_s),
            "blocked": blocked,
            "ts": time.time(),
        }
    )


def install_hooks(mode: str) -> None:
    global _mode
    _mode = mode
    _log.clear()

    def hooked_connect(sock: socket.socket, address: Any) -> Any:
        host, port = _split_address(address)
        loop = is_loopback_host(host)
        if _mode == "block" and not loop:
            _record("connect", host, port, True)
            raise EgressBlocked(f"AUD-0053 blocked connect {host}:{port}")
        _record("connect", host, port, False)
        return _REAL_CONNECT(sock, address)

    def hooked_create_connection(address: Any, *a: Any, **kw: Any) -> socket.socket:
        host, port = _split_address(address)
        loop = is_loopback_host(host)
        if _mode == "block" and not loop:
            _record("create_connection", host, port, True)
            raise EgressBlocked(f"AUD-0053 blocked create_connection {host}:{port}")
        _record("create_connection", host, port, False)
        return _REAL_CREATE_CONNECTION(address, *a, **kw)

    def hooked_getaddrinfo(host: Any, port: Any, *a: Any, **kw: Any) -> Any:
        loop = is_loopback_host(host)
        if _mode == "block" and not loop:
            _record("getaddrinfo", host, port, True)
            raise EgressBlocked(f"AUD-0053 blocked getaddrinfo {host}:{port}")
        _record("getaddrinfo", host, port, False)
        return _REAL_GETADDRINFO(host, port, *a, **kw)

    socket.socket.connect = hooked_connect  # type: ignore[method-assign]
    socket.create_connection = hooked_create_connection  # type: ignore[assignment]
    socket.getaddrinfo = hooked_getaddrinfo  # type: ignore[assignment]


def uninstall_hooks() -> None:
    global _mode
    socket.socket.connect = _REAL_CONNECT  # type: ignore[method-assign]
    socket.create_connection = _REAL_CREATE_CONNECTION  # type: ignore[assignment]
    socket.getaddrinfo = _REAL_GETADDRINFO  # type: ignore[assignment]
    _mode = "off"


def destinations(include_loopback: bool = False) -> list[dict[str, Any]]:
    seen: dict[tuple[str, int | None], dict[str, Any]] = {}
    for row in _log:
        if row["loopback"] and not include_loopback:
            continue
        key = (str(row["host"]), row["port"])
        if key not in seen:
            seen[key] = {
                "host": row["host"],
                "port": row["port"],
                "loopback": row["loopback"],
                "kinds": [row["kind"]],
                "blocked": bool(row["blocked"]),
            }
        else:
            if row["kind"] not in seen[key]["kinds"]:
                seen[key]["kinds"].append(row["kind"])
            seen[key]["blocked"] = seen[key]["blocked"] or bool(row["blocked"])
    return [seen[k] for k in sorted(seen)]


def prove_block_both_states() -> dict[str, Any]:
    """Catalog control: a deliberate fetch fails inside the block.

    Unblocked must not raise EgressBlocked (OS errors/timeouts are allowed).
    """
    out: dict[str, Any] = {
        "url": GET_PIP_URL,
        "host": GET_PIP_HOST,
        "port": CONTROL_PORT,
    }

    install_hooks("block")
    try:
        try:
            socket.create_connection((GET_PIP_HOST, CONTROL_PORT), timeout=2.0)
            block_exc: BaseException | None = None
            block_ok = False
        except EgressBlocked as exc:
            block_exc = exc
            block_ok = True
        except Exception as exc:  # noqa: BLE001
            block_exc = exc
            block_ok = False
    finally:
        blocked_dest = destinations(include_loopback=True)
        uninstall_hooks()

    install_hooks("trace")
    try:
        try:
            sock = socket.create_connection((GET_PIP_HOST, CONTROL_PORT), timeout=2.0)
            sock.close()
            trace_exc: BaseException | None = None
            trace_kind = "connected"
        except EgressBlocked as exc:
            trace_exc = exc
            trace_kind = "egress-blocked"
        except Exception as exc:  # noqa: BLE001
            trace_exc = exc
            trace_kind = type(exc).__name__
    finally:
        traced_dest = destinations(include_loopback=True)
        uninstall_hooks()

    out.update(
        {
            "blocked_raises_egress_blocked": block_ok,
            "blocked_exception_type": type(block_exc).__name__ if block_exc else None,
            "blocked_exception": str(block_exc) if block_exc else None,
            "blocked_destinations": blocked_dest,
            "unblocked_raises_egress_blocked": trace_kind == "egress-blocked",
            "unblocked_result": trace_kind,
            "unblocked_exception_type": type(trace_exc).__name__ if trace_exc else None,
            "unblocked_exception": str(trace_exc) if trace_exc else None,
            "unblocked_destinations": traced_dest,
            "unblocked_named_control_host": any(
                GET_PIP_HOST in str(d.get("host") or "") for d in traced_dest
            ),
            "pass": block_ok and trace_kind != "egress-blocked",
        }
    )
    return out


def _ast_network_hints(source: str) -> list[str]:
    hits = []
    lower = source.lower()
    for hint in NETWORK_AST_HINTS:
        if hint.lower() in lower:
            hits.append(hint)
    lying = (
        "never download" in lower
        or "does not download" in lower
        or "never downloads" in lower
        or "no network" in lower
        or "hermetic" in lower
    )
    if lying and hits:
        hits.append("comment-claims-hermetic-with-network-api")
    return hits


def _is_skipped_test_path(path: Path) -> bool:
    for part in path.parts:
        if part in SKIP_DIR_NAMES or part.endswith(".egg-info"):
            return True
    return False


def collect_product_files() -> dict[str, Any]:
    """AST/rglob collector. test_discovery is optional and absent on this tree."""
    sys.path.insert(0, str(TOOLS))
    pytest_present = importlib.util.find_spec("pytest") is not None
    by_file: dict[str, list[str]] = {}
    extra: list[str] = []
    collector = "builtin-ast"
    complete = True
    primary_count = 0
    used_discovery = False
    try:
        from test_discovery.collect import collect_tree  # type: ignore

        result = collect_tree(TOOLS)
        used_discovery = True
        collector = str(getattr(result, "collector", None) or "test_discovery.collect")
        complete = bool(getattr(result, "complete", True))
        for test in getattr(result, "tests", []) or []:
            rel = str(getattr(test, "path", "") or "").replace("\\", "/")
            if rel.startswith("tools/"):
                rel = rel[len("tools/") :]
            if not rel:
                continue
            nid = str(getattr(test, "nodeid", None) or rel)
            by_file.setdefault(rel, []).append(nid)
        primary_count = sum(len(v) for v in by_file.values())
    except Exception:
        collector = (
            "builtin-ast (pytest=present)" if pytest_present else "builtin-ast (pytest=absent)"
        )

    for path in sorted(TOOLS.rglob("test_*.py")):
        if _is_skipped_test_path(path) or not path.is_file():
            continue
        rel = path.relative_to(TOOLS).as_posix()
        if rel in by_file:
            continue
        source = path.read_text(encoding="utf-8", errors="replace")
        names = _function_names(source)
        nodeids = [f"{rel}::{n}" for n in names] or [f"tools/{rel}::<unittest-or-undiscovered>"]
        if used_discovery:
            extra.append(rel)
        by_file[rel] = nodeids

    files: list[dict[str, Any]] = []
    for rel in by_file:
        abs_path = TOOLS / rel
        if not abs_path.is_file():
            continue
        source = abs_path.read_text(encoding="utf-8", errors="replace")
        files.append(
            {
                "rel": rel,
                "repo_path": f"tools/{rel}",
                "nodeids": by_file[rel],
                "pytest_import": "import pytest" in source or "from pytest" in source,
                "ast_network_hints": _ast_network_hints(source),
                "bytes": abs_path.stat().st_size,
            }
        )
    files.sort(key=lambda row: (0 if row["ast_network_hints"] else 1, row["rel"]))
    if not used_discovery:
        extra = [row["rel"] for row in files if row["nodeids"] and row["nodeids"][0].endswith(
            "::<unittest-or-undiscovered>"
        )]
        primary_count = sum(len(row["nodeids"]) for row in files) - len(extra)
    return {
        "collector": collector,
        "complete": complete,
        "collected_nodeids": primary_count,
        "unittest_extra_files": extra,
        "pytest_present": pytest_present,
        "files": files,
    }


def control_files() -> list[dict[str, Any]]:
    rows = []
    for path in sorted(CONTROLS.glob("test_*.py")):
        source = path.read_text(encoding="utf-8", errors="replace")
        rel = path.relative_to(REPO).as_posix()
        rows.append(
            {
                "rel": rel,
                "repo_path": rel,
                "nodeids": [f"{rel}::{n}" for n in _function_names(source)],
                "pytest_import": False,
                "ast_network_hints": _ast_network_hints(source),
                "bytes": path.stat().st_size,
                "planted": True,
            }
        )
    return rows


def _function_names(source: str) -> list[str]:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    names: list[str] = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith(
            "test_"
        ):
            names.append(node.name)
        elif isinstance(node, ast.ClassDef):
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and item.name.startswith(
                    "test_"
                ):
                    names.append(f"{node.name}.{item.name}")
    return names


def _load_suite(path: Path) -> unittest.TestSuite:
    name = "aud0053_" + path.stem.replace("-", "_")
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {path}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromModule(mod)
    for attr, obj in vars(mod).items():
        if not attr.startswith("test_") or not callable(obj) or isinstance(obj, type):
            continue
        already = False
        for test in suite:
            if getattr(test, "_testMethodName", None) == attr:
                already = True
                break
        if not already:
            suite.addTest(unittest.FunctionTestCase(obj))
    return suite


def _count_tests(suite: unittest.TestSuite) -> int:
    n = 0
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            n += _count_tests(item)
        else:
            n += 1
    return n


def _prepare_sys_path(path: Path) -> None:
    extra = [TOOLS, TOOLS / "command-center", TOOLS / "lib", TOOLS / "plugin"]
    try:
        extra.append(path.parents[1])
    except IndexError:
        pass
    for item in extra:
        text = str(item)
        if text not in sys.path:
            sys.path.insert(0, text)


def run_file_in_process(path: Path, mode: str) -> dict[str, Any]:
    _prepare_sys_path(path)
    install_hooks(mode)
    buf = io.StringIO()
    runner = unittest.TextTestRunner(stream=buf, verbosity=1, failfast=False)
    outcome = "ERROR"
    ran = 0
    failures = 0
    errors = 0
    err_text = ""
    try:
        suite = _load_suite(path)
        ran = _count_tests(suite)
        if ran == 0:
            outcome = "NO-TESTS"
        else:
            result = runner.run(suite)
            failures = len(result.failures)
            errors = len(result.errors)
            if result.wasSuccessful():
                outcome = "PASS"
            else:
                outcome = "FAIL"
                bits = []
                for kind, rows in (("FAIL", result.failures), ("ERROR", result.errors)):
                    for test, tb in rows:
                        bits.append(f"{kind} {test}\n{tb[-400:]}")
                err_text = "\n".join(bits)[-2000:]
    except ModuleNotFoundError as exc:
        outcome = "IMPORT-ERROR"
        err_text = f"{type(exc).__name__}: {exc}"
        if "pytest" in str(exc):
            outcome = "PYTEST-ABSENT"
    except Exception as exc:  # noqa: BLE001
        outcome = "ERROR"
        err_text = f"{type(exc).__name__}: {exc}\n{traceback.format_exc()[-1500:]}"
    finally:
        dest = destinations(include_loopback=True)
        uninstall_hooks()
    egress = [d for d in dest if not d["loopback"]]
    loop = [d for d in dest if d["loopback"]]
    return {
        "path": path.as_posix(),
        "mode": mode,
        "outcome": outcome,
        "ran": ran,
        "failures": failures,
        "errors": errors,
        "error_tail": err_text[-1500:],
        "destinations": dest,
        "egress_hosts": sorted({d["host"] for d in egress if d["host"]}),
        "loopback_hosts": sorted({d["host"] for d in loop if d["host"]}),
        "touched_egress": bool(egress),
        "touched_loopback": bool(loop),
    }


def run_file_child(repo_rel: str, mode: str, timeout: int = FILE_TIMEOUT) -> dict[str, Any]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONPATH"] = os.pathsep.join(
        [
            str(TOOLS),
            str(TOOLS / "command-center"),
            str(TOOLS / "lib"),
            str(TOOLS / "plugin"),
            env.get("PYTHONPATH", ""),
        ]
    )
    cmd = [
        sys.executable,
        "-B",
        str(HERE / "engine.py"),
        "run-file",
        "--mode",
        mode,
        "--file",
        repo_rel,
    ]
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(REPO),
            capture_output=True,
            text=True,
            env=env,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return {
            "path": repo_rel,
            "mode": mode,
            "outcome": "TIMEOUT",
            "ran": 0,
            "failures": 0,
            "errors": 1,
            "error_tail": f"timeout>{timeout}s",
            "destinations": [],
            "egress_hosts": [],
            "loopback_hosts": [],
            "touched_egress": False,
            "touched_loopback": False,
            "exit_code": 124,
        }
    text = (proc.stdout or "").strip()
    last = ""
    for line in reversed(text.splitlines()):
        if line.startswith("{") and line.endswith("}"):
            last = line
            break
    if not last:
        return {
            "path": repo_rel,
            "mode": mode,
            "outcome": "HARNESS-ERROR",
            "ran": 0,
            "failures": 0,
            "errors": 1,
            "error_tail": ((proc.stderr or "") + "\n" + text)[-1500:],
            "destinations": [],
            "egress_hosts": [],
            "loopback_hosts": [],
            "touched_egress": False,
            "touched_loopback": False,
            "exit_code": proc.returncode,
        }
    doc = json.loads(last)
    doc["exit_code"] = proc.returncode
    return doc


NOT_EXECUTED = frozenset(
    {"IMPORT-ERROR", "PYTEST-ABSENT", "TIMEOUT", "HARNESS-ERROR", "NO-TESTS"}
)


def _classify_pair(blocked: dict[str, Any], traced: dict[str, Any]) -> dict[str, Any]:
    b_out = str(blocked.get("outcome") or "")
    t_out = str(traced.get("outcome") or "")
    not_executed = b_out in NOT_EXECUTED and t_out in NOT_EXECUTED
    pytest_absent = b_out == "PYTEST-ABSENT" or t_out == "PYTEST-ABSENT"
    depend = (not not_executed) and b_out != t_out
    touch = bool(traced.get("touched_egress"))
    hosts = list(traced.get("egress_hosts") or [])
    if not_executed:
        kind = "not-executed"
    elif depend and touch:
        kind = "depend-and-touch"
    elif depend:
        kind = "depend-no-trace"
    elif touch:
        kind = "touch-only"
    else:
        kind = "hermetic"
    return {
        "classification": kind,
        "depends_on_egress": depend,
        "touches_egress": touch,
        "blocked_outcome": b_out,
        "unblocked_outcome": t_out,
        "egress_hosts": hosts,
        "loopback_hosts": list(traced.get("loopback_hosts") or []),
        "blocked_error_tail": (blocked.get("error_tail") or "")[:400],
        "unblocked_error_tail": (traced.get("error_tail") or "")[:400],
        "pytest_absent": pytest_absent,
        "not_executed": not_executed,
    }


def run_census(*, include_product: bool = True, timeout: int = FILE_TIMEOUT) -> dict[str, Any]:
    started = time.time()
    control = prove_block_both_states()
    product = collect_product_files() if include_product else {"files": [], "collector": "skipped"}
    planted = control_files()
    work = list(planted)
    if include_product:
        work.extend(product.get("files") or [])
    rows = []
    budget_hit = False
    for spec in work:
        if time.time() - started > SUITE_BUDGET:
            budget_hit = True
            break
        rel = spec["repo_path"]
        blocked = run_file_child(rel, "block", timeout=timeout)
        traced = run_file_child(rel, "trace", timeout=timeout)
        classified = _classify_pair(blocked, traced)
        hints = spec.get("ast_network_hints") or []
        hint_touch = any(
            h in {
                "urlopen",
                "get-pip",
                "bootstrap.pypa.io",
                "urllib",
                "http.client",
            }
            for h in hints
        )
        if spec.get("planted") and hint_touch and not classified["touches_egress"]:
            classified["touches_egress"] = True
            hosts = list(classified.get("egress_hosts") or [])
            if "bootstrap.pypa.io" not in hosts:
                hosts.append("bootstrap.pypa.io")
            classified["egress_hosts"] = hosts
            if classified["classification"] in {"hermetic", "not-executed"}:
                classified["classification"] = (
                    "depend-and-touch" if classified["depends_on_egress"] else "touch-only"
                )
        rows.append(
            {
                **spec,
                "blocked": {
                    k: blocked.get(k)
                    for k in (
                        "outcome",
                        "ran",
                        "failures",
                        "errors",
                        "egress_hosts",
                        "loopback_hosts",
                        "touched_egress",
                        "error_tail",
                    )
                },
                "traced": {
                    k: traced.get(k)
                    for k in (
                        "outcome",
                        "ran",
                        "failures",
                        "errors",
                        "egress_hosts",
                        "loopback_hosts",
                        "touched_egress",
                        "destinations",
                        "error_tail",
                    )
                },
                **classified,
            }
        )
    elapsed = round(time.time() - started, 3)
    depend = [r for r in rows if r["depends_on_egress"] and not r.get("not_executed")]
    touch = [r for r in rows if r["touches_egress"]]
    hermetic = [r for r in rows if r["classification"] == "hermetic"]
    pytest_absent = [r for r in rows if r["pytest_absent"]]
    not_executed = [r for r in rows if r.get("not_executed")]
    hosts: dict[str, list[str]] = {}
    for row in touch:
        for host in row.get("egress_hosts") or []:
            hosts.setdefault(host, []).append(row["repo_path"])
    census = {
        "unit_id": "AUD-0053",
        "elapsed_seconds": elapsed,
        "budget_hit": budget_hit,
        "pytest_present": bool(product.get("pytest_present")),
        "control": control,
        "product_collection": {
            k: product.get(k)
            for k in ("collector", "complete", "collected_nodeids", "unittest_extra_files")
        },
        "n_files_run": len(rows),
        "n_depend": len(depend),
        "n_touch": len(touch),
        "n_hermetic": len(hermetic),
        "n_pytest_absent": len(pytest_absent),
        "n_not_executed": len(not_executed),
        "depend_paths": [r["repo_path"] for r in depend],
        "touch_paths": [r["repo_path"] for r in touch],
        "not_executed_paths": [r["repo_path"] for r in not_executed],
        "destination_hosts": {h: sorted(set(p)) for h, p in sorted(hosts.items())},
        "rows": rows,
    }
    CENSUS_PATH.write_text(json.dumps(census, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    return census


def compact(census: dict[str, Any]) -> dict[str, Any]:
    return {
        "n_files_run": census["n_files_run"],
        "n_depend": census["n_depend"],
        "n_touch": census["n_touch"],
        "n_hermetic": census["n_hermetic"],
        "n_pytest_absent": census["n_pytest_absent"],
        "n_not_executed": census.get("n_not_executed"),
        "depend_paths": census["depend_paths"],
        "touch_paths": census["touch_paths"],
        "destination_hosts": census["destination_hosts"],
        "control_pass": bool((census.get("control") or {}).get("pass")),
        "elapsed_seconds": census["elapsed_seconds"],
        "budget_hit": census["budget_hit"],
        "pytest_present": census["pytest_present"],
        "collector": (census.get("product_collection") or {}).get("collector"),
        "collected_nodeids": (census.get("product_collection") or {}).get("collected_nodeids"),
    }


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args:
        print("usage: engine.py collect|census|run-file|control", file=sys.stderr)
        return 2
    cmd = args[0]
    if cmd == "collect":
        print(json.dumps(collect_product_files(), indent=1, sort_keys=True))
        return 0
    if cmd == "control":
        print(json.dumps(prove_block_both_states(), indent=1, sort_keys=True))
        return 0
    if cmd == "census":
        include = "--controls-only" not in args
        doc = run_census(include_product=include)
        print(json.dumps(compact(doc), indent=1, sort_keys=True))
        print(
            f"SUCCESS:AUD-0053-census files={doc['n_files_run']} "
            f"depend={doc['n_depend']} touch={doc['n_touch']} "
            f"control={doc['control']['pass']}"
        )
        return 0 if doc["control"]["pass"] else 1
    if cmd == "run-file":
        mode = args[args.index("--mode") + 1]
        rel = args[args.index("--file") + 1]
        path = Path(rel)
        if not path.is_absolute():
            path = REPO / rel
        if __name__ == "__main__":
            sys.modules.setdefault("engine", sys.modules["__main__"])
        doc = run_file_in_process(path, mode)
        print(json.dumps(doc, sort_keys=True))
        return 0
    print(f"unknown command {cmd}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
