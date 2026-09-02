"""Physical + guarded isolation of a rehearser from the repository tree."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

SITECUSTOMIZE = r'''
"""Refuse opens under CNF0183_FORBID. Loaded via PYTHONPATH as sitecustomize."""
import builtins
import os
from pathlib import Path

_FORBIDDEN = []
for _p in os.environ.get("CNF0183_FORBID", "").split(os.pathsep):
    if _p:
        try:
            _FORBIDDEN.append(os.path.realpath(_p))
        except Exception:
            _FORBIDDEN.append(_p)

_orig_open = builtins.open
_orig_os_open = os.open


def _as_str(file):
    if isinstance(file, bytes):
        try:
            return os.fsdecode(file)
        except Exception:
            return None
    if isinstance(file, (str, os.PathLike)):
        return file
    return None


def _forbidden(path) -> bool:
    if not _FORBIDDEN or path is None:
        return False
    try:
        resolved = os.path.realpath(path)
    except Exception:
        return False
    for root in _FORBIDDEN:
        try:
            r = os.path.realpath(root)
        except Exception:
            r = str(root)
        if resolved == r or resolved.startswith(r + os.sep):
            return True
    return False


def _open_guard(file, *args, **kwargs):
    path = _as_str(file)
    if path is not None and _forbidden(path):
        raise PermissionError(f"CNF-0183 isolation: refused {path}")
    return _orig_open(file, *args, **kwargs)


def _os_open_guard(path, *args, **kwargs):
    if _forbidden(path):
        raise PermissionError(f"CNF-0183 isolation: refused {path}")
    return _orig_os_open(path, *args, **kwargs)


builtins.open = _open_guard
os.open = _os_open_guard
'''

CATALOG_REL = "command-center/WORK-UNIT-CATALOG.json"
PROBE_PY = r"""
import json, os, sys
if os.environ.get("CNF0183_FORBID"):
    pp = os.environ.get("PYTHONPATH", "")
    if pp:
        sys.path.insert(0, pp.split(os.pathsep)[0])
    import cnf0183_guard  # noqa: F401
p = sys.argv[1]
try:
    with open(p, "rb") as f:
        f.read(32)
    print(json.dumps({"ok": True, "error": None}))
except Exception as e:
    print(json.dumps({"ok": False, "error": type(e).__name__ + ":" + str(e)[:180]}))
"""


def write_sitecustomize(isolate_dir: Path) -> Path:
    isolate_dir.mkdir(parents=True, exist_ok=True)
    body = SITECUSTOMIZE.lstrip("\n")
    for name in ("sitecustomize.py", "cnf0183_guard.py"):
        (isolate_dir / name).write_text(body, encoding="utf-8", newline="\n")
    return isolate_dir / "sitecustomize.py"


def isolation_env(repo: Path, isolate_dir: Path) -> dict:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONPATH"] = str(isolate_dir.resolve())
    env["CNF0183_FORBID"] = str(repo.resolve())
    return env


def try_open(path: Path | str, env: dict, cwd: Path) -> dict:
    p = subprocess.run(
        [sys.executable, "-B", "-c", PROBE_PY, str(path)],
        cwd=str(cwd),
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    raw = (p.stdout or "").strip().splitlines()
    last = raw[-1] if raw else ""
    try:
        return json.loads(last)
    except json.JSONDecodeError:
        return {
            "ok": False,
            "error": f"unparseable rc={p.returncode} {(p.stderr or last)[:180]}",
        }


def outside_repo_tmpdir(repo: Path) -> Path:
    tmp = Path(tempfile.mkdtemp(prefix="cnf0183-iso-"))
    resolved = tmp.resolve()
    repo_r = repo.resolve()
    if repo_r == resolved or repo_r in resolved.parents:
        shutil.rmtree(tmp, ignore_errors=True)
        raise RuntimeError(f"temp dir {resolved} is inside repo {repo_r}")
    return tmp


def both_states(repo: Path) -> dict:
    """Guard ON: absolute catalog refused. Guard OFF: same absolute path readable.

    Relative catalog from a temp cwd must miss even unguarded (physical isolation).
    """
    catalog = repo / CATALOG_REL
    tmp = outside_repo_tmpdir(repo)
    try:
        isolate_dir = tmp / "._isolate"
        write_sitecustomize(isolate_dir)
        guarded = isolation_env(repo, isolate_dir)
        unguarded = os.environ.copy()
        unguarded.pop("PYTHONPATH", None)
        unguarded.pop("CNF0183_FORBID", None)
        unguarded["PYTHONDONTWRITEBYTECODE"] = "1"

        g_abs = try_open(catalog, guarded, tmp)
        u_abs = try_open(catalog, unguarded, tmp)
        u_rel = try_open(CATALOG_REL, unguarded, tmp)

        rec = {
            "catalog_path": CATALOG_REL,
            "catalog_exists": catalog.is_file(),
            "temp_cwd": str(tmp),
            "guarded_absolute_reachable": bool(g_abs.get("ok")),
            "unguarded_absolute_reachable": bool(u_abs.get("ok")),
            "relative_reachable_from_temp": bool(u_rel.get("ok")),
            "guarded_error": g_abs.get("error"),
            "unguarded_error": u_abs.get("error"),
            "relative_error": u_rel.get("error"),
        }
        rec["pass"] = (
            rec["catalog_exists"] is True
            and rec["guarded_absolute_reachable"] is False
            and rec["unguarded_absolute_reachable"] is True
            and rec["relative_reachable_from_temp"] is False
        )
        return rec
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
