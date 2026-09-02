"""Discover Python/Node interpreters; optional docker floor pivot."""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]

VER_RE = re.compile(r"(\d+)\.(\d+)\.(\d+)")


def _run(
    cmd: list[str],
    *,
    timeout: int = 45,
    env: dict[str, str] | None = None,
    cwd: Path | None = None,
) -> dict[str, Any]:
    merged = os.environ.copy()
    if env:
        merged.update(env)
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(cwd or REPO),
            capture_output=True,
            text=True,
            timeout=timeout,
            env=merged,
        )
        text = (proc.stdout or "") + (proc.stderr or "")
        return {
            "cmd": cmd,
            "exit_code": proc.returncode,
            "output": text[-20000:],
            "timeout": False,
        }
    except subprocess.TimeoutExpired:
        return {
            "cmd": cmd,
            "exit_code": 124,
            "output": f"TIMEOUT after {timeout}s: {' '.join(cmd)}",
            "timeout": True,
        }
    except FileNotFoundError as exc:
        return {
            "cmd": cmd,
            "exit_code": 127,
            "output": f"FileNotFoundError: {exc}",
            "timeout": False,
        }
    except OSError as exc:
        return {
            "cmd": cmd,
            "exit_code": 127,
            "output": f"{type(exc).__name__}: {exc}",
            "timeout": False,
        }


def _parse_version(text: str) -> tuple[int, int, int] | None:
    match = VER_RE.search(text)
    if not match:
        return None
    return int(match.group(1)), int(match.group(2)), int(match.group(3))


def _python_probe(exe: str) -> dict[str, Any] | None:
    which = shutil.which(exe) if not os.path.isabs(exe) else exe
    if not which and not os.path.isfile(exe):
        return None
    target = which or exe
    result = _run(
        [target, "-c", "import sys; print(sys.version); print(sys.executable)"],
        timeout=20,
    )
    if result["exit_code"] != 0:
        return {
            "kind": "python",
            "exe": target,
            "ok": False,
            "output": result["output"][:500],
        }
    version = _parse_version(result["output"])
    if not version:
        return None
    lines = [ln.strip() for ln in result["output"].splitlines() if ln.strip()]
    return {
        "kind": "python",
        "exe": target,
        "ok": True,
        "version": f"{version[0]}.{version[1]}.{version[2]}",
        "tuple": list(version),
        "major_minor": f"{version[0]}.{version[1]}",
        "sys_version": lines[0] if lines else result["output"][:200],
    }


def _node_probe(exe: str) -> dict[str, Any] | None:
    which = shutil.which(exe)
    if not which:
        return None
    result = _run([which, "-v"], timeout=15)
    if result["exit_code"] != 0:
        return None
    version = _parse_version(result["output"])
    if not version:
        return None
    return {
        "kind": "node",
        "exe": which,
        "ok": True,
        "version": f"{version[0]}.{version[1]}.{version[2]}",
        "tuple": list(version),
        "major_minor": str(version[0]),
        "sys_version": result["output"].strip(),
    }


def docker_python(tag: str = "python:3.10-slim") -> dict[str, Any] | None:
    if not shutil.which("docker") and not shutil.which("podman"):
        return {
            "kind": "python-container",
            "ok": False,
            "tag": tag,
            "reason": "docker/podman not on PATH",
        }
    engine = shutil.which("docker") or shutil.which("podman")
    assert engine is not None
    inspect = _run([engine, "image", "inspect", tag], timeout=20)
    if inspect["exit_code"] != 0:
        return {
            "kind": "python-container",
            "ok": False,
            "engine": engine,
            "tag": tag,
            "reason": f"image {tag} not present locally (will not pull)",
        }
    result = _run(
        [engine, "run", "--rm", tag, "python3", "-c", "import sys; print(sys.version)"],
        timeout=90,
    )
    version = _parse_version(result["output"] or "")
    ok = result["exit_code"] == 0 and version is not None
    row: dict[str, Any] = {
        "kind": "python-container",
        "engine": engine,
        "tag": tag,
        "ok": ok,
        "exit_code": result["exit_code"],
        "output": (result["output"] or "")[:800],
    }
    if ok and version:
        row["version"] = f"{version[0]}.{version[1]}.{version[2]}"
        row["tuple"] = list(version)
        row["major_minor"] = f"{version[0]}.{version[1]}"
        row["exe"] = engine
    return row


def discover() -> dict[str, Any]:
    py_names = [
        "python3.10",
        "python3.11",
        "python3.12",
        "python3.13",
        "python3.14",
        "python3",
        "python",
    ]
    seen_exe: set[str] = set()
    pythons: list[dict[str, Any]] = []
    missing: list[str] = []
    for name in py_names:
        row = _python_probe(name)
        if row is None:
            missing.append(name)
            continue
        exe = str(row.get("exe"))
        if exe in seen_exe:
            continue
        seen_exe.add(exe)
        pythons.append(row)

    nodes: list[dict[str, Any]] = []
    for name in ("node", "nodejs"):
        row = _node_probe(name)
        if row:
            nodes.append(row)
            break

    usable_py = [p for p in pythons if p.get("ok")]
    usable_py.sort(key=lambda p: tuple(p.get("tuple") or [0, 0, 0]))
    newest = usable_py[-1] if usable_py else None
    oldest = usable_py[0] if usable_py else None
    return {
        "python": pythons,
        "python_missing_lookups": missing,
        "node": nodes,
        "oldest_python": oldest,
        "newest_python": newest,
    }


def run_python_file(
    exe: str,
    rel: str,
    *,
    extra_env: dict[str, str] | None = None,
    timeout: int = 45,
) -> dict[str, Any]:
    env = {
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONWARNINGS": "default",
    }
    if extra_env:
        env.update(extra_env)
    result = _run([exe, "-B", str(REPO / rel)], timeout=timeout, env=env)
    result["rel"] = rel
    result["exe"] = exe
    return result


def run_python_container_file(
    engine: str,
    tag: str,
    rel: str,
    *,
    timeout: int = 90,
) -> dict[str, Any]:
    cmd = [
        engine,
        "run",
        "--rm",
        "-v",
        f"{REPO}:/src:ro",
        "-w",
        "/src",
        "-e",
        "PYTHONDONTWRITEBYTECODE=1",
        "-e",
        "PYTHONWARNINGS=default",
        tag,
        "python3",
        "-B",
        rel,
    ]
    result = _run(cmd, timeout=timeout)
    result["rel"] = rel
    result["exe"] = f"{engine}:{tag}"
    result["container"] = True
    return result


def dump_json(path: Path, doc: Any) -> None:
    path.write_text(
        json.dumps(doc, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
