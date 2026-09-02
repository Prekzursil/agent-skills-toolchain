"""Fail-closed tripwire for generated ``_NS`` placeholder modules (02.09, council guard 1+2).

Every module `seed-stage/_emit_g1_modules.py` generated carries the marker line
(``# g1-surface:`` followed by ``generated``; spelled in two parts here so this file
never matches its own test) and a permissive ``_NS`` duck-type, so a probe can "pass"
against it without exercising any real behaviour. This meta-path finder wraps normal
import resolution and, when the resolved file carries the marker:

  * ``G1_PLACEHOLDER_MODE=trace``  -> append ``<unit>\t<module>\t<origin>`` to
    ``$G1_TRACE_FILE`` (default ``/tmp/g1-placeholder-trace.tsv``) and let the import
    proceed. Gives the exact (unit, module) dependency set -- the regression set for a
    module repair is its traced importers, never a sample.
  * ``G1_PLACEHOLDER_MODE=strict`` -> raise ``ImportError`` ("G1-STRICT placeholder").
    The probe exits non-zero; the unit is FAILED:delivered probe-exit. Only a census run
    with STRICT on may be called green.
  * unset/other -> no-op (owner's historical behaviour).

Installed by ``g1_python.py`` (every named probe runs through it). Unit id is taken from
the ``probes/<ID>/`` segment of the running script path when available.
"""
from __future__ import annotations

import importlib.abc
import importlib.machinery
import os
import re
import sys
from pathlib import Path

MARKER = "# g1-surface: " + "generated"
# Second stub family (02.09, writer w8 finding): the "g1-mod / real-surface" import-surface files whose
# `Result` dataclass defaults to ok=True / verdict='PASS' and whose functions return constants. Same
# fail-closed treatment; G1_PLACEHOLDER_MARKERS=generated limits the guard to the first family.
MARKER2 = "# g1-mod: " + "real-surface"
_MARKERS = tuple(m for m, key in ((MARKER, "generated"), (MARKER2, "real-surface"))
                 if key in (os.environ.get("G1_PLACEHOLDER_MARKERS") or "generated,real-surface"))
_UID_RE = re.compile(r"probes[\\/]([A-Z]{2,5}-\d{4})[\\/]")
_checked: dict[str, bool] = {}


def _is_placeholder(origin: str | None) -> bool:
    if not origin or not origin.endswith(".py"):
        return False
    hit = _checked.get(origin)
    if hit is None:
        try:
            with open(origin, "r", encoding="utf-8", errors="replace") as fh:
                head = fh.read(1200)
                hit = any(m in head for m in _MARKERS)
        except OSError:
            hit = False
        _checked[origin] = hit
    return hit


def _unit_id() -> str:
    for cand in [sys.argv[0] if sys.argv else "", os.getcwd(), os.environ.get("G1_UNIT", "")]:
        m = _UID_RE.search(str(cand))
        if m:
            return m.group(1)
    return os.environ.get("G1_UNIT") or "?"


class _PlaceholderGuard(importlib.abc.MetaPathFinder):
    def __init__(self, mode: str, trace_file: str) -> None:
        self.mode = mode
        self.trace_file = trace_file

    def find_spec(self, fullname, path=None, target=None):  # noqa: D401
        for finder in sys.meta_path:
            if finder is self:
                continue
            find = getattr(finder, "find_spec", None)
            if find is None:
                continue
            try:
                spec = find(fullname, path, target)
            except Exception:
                spec = None
            if spec is None:
                continue
            if _is_placeholder(getattr(spec, "origin", None)):
                if self.mode == "strict":
                    raise ImportError(
                        f"G1-STRICT placeholder module {fullname!r} at {spec.origin} "
                        "(generated _NS surface; a real implementation is required)"
                    )
                try:
                    with open(self.trace_file, "a", encoding="utf-8") as fh:
                        fh.write(f"{_unit_id()}\t{fullname}\t{spec.origin}\n")
                except OSError:
                    pass
            return spec
        return None


def install() -> None:
    mode = (os.environ.get("G1_PLACEHOLDER_MODE") or "").strip().lower()
    if mode not in ("trace", "strict"):
        return
    if any(isinstance(f, _PlaceholderGuard) for f in sys.meta_path):
        return
    trace_file = os.environ.get("G1_TRACE_FILE") or "/tmp/g1-placeholder-trace.tsv"
    sys.meta_path.insert(0, _PlaceholderGuard(mode, trace_file))
    # Modules already imported before the guard went in (e.g. by the shim itself).
    if mode == "strict":
        for name, mod in list(sys.modules.items()):
            if _is_placeholder(getattr(mod, "__file__", None)):
                raise ImportError(f"G1-STRICT placeholder module {name!r} already loaded from {mod.__file__}")
    else:
        for name, mod in list(sys.modules.items()):
            if _is_placeholder(getattr(mod, "__file__", None)):
                try:
                    with open(trace_file, "a", encoding="utf-8") as fh:
                        fh.write(f"{_unit_id()}\t{name}\t{mod.__file__}\n")
                except OSError:
                    pass


def scan_tree(root: Path) -> list[Path]:
    """Lint helper (guard 6): every marker file under the given root."""
    out: list[Path] = []
    for p in root.rglob("*.py"):
        if _is_placeholder(str(p)):
            out.append(p)
    return out
