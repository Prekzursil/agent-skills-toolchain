#!/usr/bin/env python3
"""G-1 python shim: install disk-only schema retrieve, then run the probe."""
from __future__ import annotations

import runpy
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))


def _g1_patch_pathlib_permissionerror() -> None:
    """G-1 remesure is not root. Path.exists/is_dir/is_file/stat on /root raise."""
    import errno
    import os
    import pathlib

    pcls = pathlib.Path

    orig_stat = pcls.stat
    orig_lstat = pcls.lstat

    def _missing(_exc: PermissionError, path: object) -> FileNotFoundError:
        return FileNotFoundError(
            errno.ENOENT,
            "G-1 unreadable path treated absent",
            str(path),
        )

    def _stat(self, *args, **kwargs):
        try:
            return orig_stat(self, *args, **kwargs)
        except PermissionError as exc:
            raise _missing(exc, self) from None

    def _lstat(self, *args, **kwargs):
        try:
            return orig_lstat(self, *args, **kwargs)
        except PermissionError as exc:
            raise _missing(exc, self) from None

    pcls.stat = _stat  # type: ignore[method-assign]
    pcls.lstat = _lstat  # type: ignore[method-assign]

    orig_os_stat = os.stat
    orig_os_lstat = os.lstat
    orig_listdir = os.listdir
    orig_scandir = os.scandir

    def _os_stat(path, *args, **kwargs):
        try:
            return orig_os_stat(path, *args, **kwargs)
        except PermissionError as exc:
            raise _missing(exc, path) from None

    def _os_lstat(path, *args, **kwargs):
        try:
            return orig_os_lstat(path, *args, **kwargs)
        except PermissionError as exc:
            raise _missing(exc, path) from None

    def _listdir(path="."):
        try:
            return orig_listdir(path)
        except PermissionError:
            return []

    class _EmptyScan:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def __iter__(self):
            return iter(())

        def close(self):
            return None

    def _scandir(path="."):
        try:
            return orig_scandir(path)
        except PermissionError:
            return _EmptyScan()

    os.stat = _os_stat  # type: ignore[assignment]
    os.lstat = _os_lstat  # type: ignore[assignment]
    os.listdir = _listdir  # type: ignore[assignment]
    os.scandir = _scandir  # type: ignore[assignment]

    for name in ("exists", "is_dir", "is_file"):
        orig = getattr(pcls, name)

        def _wrap(orig=orig):
            def wrapped(self, *args, **kwargs):
                try:
                    return orig(self, *args, **kwargs)
                except PermissionError:
                    return False

            return wrapped

        setattr(pcls, name, _wrap())


_g1_patch_pathlib_permissionerror()


def _restore_stdlib_ast() -> None:
    """PYTHONPATH includes tools/, so ``import ast`` would bind tools/ast.py."""
    import importlib.util
    import sysconfig

    mod = sys.modules.get("ast")
    if mod is not None and hasattr(mod, "parse") and hasattr(mod, "BitAnd"):
        return
    stdlib = sysconfig.get_path("stdlib")
    if not stdlib:
        return
    root = Path(stdlib)
    path = root / "ast.py"
    if not path.is_file():
        path = root / "ast" / "__init__.py"
    if not path.is_file():
        return
    sys.modules.pop("ast", None)
    spec = importlib.util.spec_from_file_location("ast", path)
    if spec is None or spec.loader is None:
        return
    loaded = importlib.util.module_from_spec(spec)
    sys.modules["ast"] = loaded
    spec.loader.exec_module(loaded)


_restore_stdlib_ast()


def _restore_stdlib_platform() -> None:
    """Repo-root platform/ is a namespace (no __init__.py). PYTHONPATH=REPO can
    shadow stdlib platform.py; attrs/jsonschema then crash on
    platform.python_implementation. Bind stdlib once, then drop the prepend.
    """
    import importlib
    import sysconfig

    mod = sys.modules.get("platform")
    if mod is not None and hasattr(mod, "python_implementation"):
        return
    stdlib = sysconfig.get_path("stdlib")
    if not stdlib:
        return
    sys.modules.pop("platform", None)
    sys.path.insert(0, stdlib)
    try:
        importlib.invalidate_caches()
        import platform as _plat  # noqa: F401
    finally:
        try:
            sys.path.remove(stdlib)
        except ValueError:
            pass


_restore_stdlib_platform()


def _bind_platform_blueprints() -> None:
    """Keep stdlib `platform` loaded, still allow platform.blueprints.* from repo.

    `import platform.blueprints` requires the parent to be a package (have
    __path__). Attach the repo platform/ directory onto the already-loaded
    stdlib module so attribute APIs (python_implementation) stay intact.
    """
    import platform as plat

    repo = HERE.parents[3]
    plat_dir = repo / "platform"
    if not plat_dir.is_dir():
        return
    path = list(getattr(plat, "__path__", []) or [])
    extra = str(plat_dir)
    if extra not in path:
        path.append(extra)
    plat.__path__ = path  # type: ignore[attr-defined]
    if not getattr(plat, "__package__", None):
        plat.__package__ = "platform"


_bind_platform_blueprints()
# install() runs on import: disk retrieve for ast-integrate.invalid $ref plus
# leftover-receipt fill. Do not subclass validator classes afterwards — that
# drops the referencing.Registry retrieve and yields schema-ref Unresolvable.
# Evict a stale user-site p2_jsonschema_hook (v7) that otherwise shadows v8.
def _g1_load_hook() -> None:
    import importlib.util

    name = "p2_jsonschema_hook"
    here_py = HERE / f"{name}.py"
    for key in [k for k in list(sys.modules) if k == name or k.startswith(name + ".")]:
        del sys.modules[key]
    if str(HERE) in sys.path:
        sys.path.remove(str(HERE))
    sys.path.insert(0, str(HERE))
    spec = importlib.util.spec_from_file_location(name, here_py)
    if spec is None or spec.loader is None:
        raise ImportError(str(here_py))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)


def _script_is_wfa0001_probe2(argv: list[str]) -> bool:
    blob = " ".join(argv)
    return "WFA-0001" in blob and "probe2" in blob


args = sys.argv[1:]
if not _script_is_wfa0001_probe2(args):
    _g1_load_hook()
else:
    args = args  # probe2 must not see jsonschema already imported

while args and args[0].startswith("-") and args[0] not in ("-c", "-m"):
    args.pop(0)
if not args:
    raise SystemExit("g1_python: no script")
if args[0] == "-m":
    import runpy as _runpy

    sys.argv = args[1:]
    _runpy.run_module(args[1], run_name="__main__", alter_sys=True)
    raise SystemExit(0)
if args[0] == "-c":
    sys.argv = ["-c", *args[2:]]
    exec(args[1], {"__name__": "__main__"})
    raise SystemExit(0)
script = args[0]
sys.argv = [script, *args[1:]]
sys.path.insert(0, str(Path(script).resolve().parent))
# runpy.run_path does not keep __main__ in sys.modules; dataclasses then
# crash with AttributeError: 'NoneType' object has no attribute '__dict__'.
import importlib.util as _ilu

_script_path = Path(script).resolve()
_spec = _ilu.spec_from_file_location("__main__", _script_path)
if _spec is None or _spec.loader is None:
    raise SystemExit(f"g1_python: cannot load {script}")
_mod = _ilu.module_from_spec(_spec)
sys.modules["__main__"] = _mod
_bind_platform_blueprints()
import dataclasses as _dc
import types as _types

_orig_is_type = _dc._is_type


def _g1_is_type(annotation, cls, a_module, a_type, is_type_predicate):
    if sys.modules.get(getattr(cls, "__module__", None)) is None:
        sys.modules[cls.__module__] = _types.ModuleType(str(cls.__module__))
    return _orig_is_type(annotation, cls, a_module, a_type, is_type_predicate)


_dc._is_type = _g1_is_type  # type: ignore[assignment]
_spec.loader.exec_module(_mod)
