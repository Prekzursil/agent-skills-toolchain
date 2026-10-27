"""Load the CC-0003 completion reducer without owning it.

STATUS.md must name the shared predicate. When the reducer is importable it is
consumed (imported and identified). When it is absent the status board reports
NOT-CHECKED — never a pass, never a locally reimplemented twelve-condition gate.
"""

from __future__ import annotations

import importlib.util
import sys
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Any

REPO = Path(__file__).resolve().parents[2]

# CC-0003 ships the reducer at platform/lib/completion_predicate.py. ADV-0009
# also looks under tools/command-center/. Try both; do not author a third copy.
REDUCER_CANDIDATES: tuple[Path, ...] = (
    REPO / "platform" / "lib" / "completion_predicate.py",
    REPO / "tools" / "command-center" / "completion_predicate.py",
    REPO / "command-center" / "lib" / "completion_reducer.py",
)


@dataclass(frozen=True)
class ReducerLoad:
    source: Path | None
    importable: bool
    reducer: ModuleType | None
    reason: str


def _rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def load_reducer() -> ReducerLoad:
    """Return the live CC-0003 module, or an explicit NOT-CHECKED load."""
    misses: list[str] = []
    for path in REDUCER_CANDIDATES:
        rel = _rel(path)
        if not path.is_file():
            misses.append(f"absent:{rel}")
            continue
        libdir = str(path.parent)
        if libdir not in sys.path:
            sys.path.insert(0, libdir)
        # Dataclass evaluation reads sys.modules[cls.__module__]. A spec_from_file
        # load that never registers the module raises AttributeError on 3.12.
        mod_name = (
            "completion_predicate"
            if path.name == "completion_predicate.py"
            else f"cc0003_{path.stem}"
        )
        existing = sys.modules.get(mod_name)
        if existing is not None and getattr(existing, "evaluate", None) is not None:
            return ReducerLoad(
                source=path,
                importable=True,
                reducer=existing,
                reason=f"importable:{rel}",
            )
        spec = importlib.util.spec_from_file_location(mod_name, path)
        if spec is None or spec.loader is None:
            misses.append(f"unimportable-spec:{rel}")
            continue
        mod = importlib.util.module_from_spec(spec)
        sys.modules[mod_name] = mod
        try:
            spec.loader.exec_module(mod)
        except Exception as exc:  # noqa: BLE001 — load is a measurement, not a crash
            sys.modules.pop(mod_name, None)
            misses.append(f"import-failed:{rel}:{type(exc).__name__}")
            continue
        return ReducerLoad(
            source=path,
            importable=True,
            reducer=mod,
            reason=f"importable:{rel}",
        )
    return ReducerLoad(
        source=None,
        importable=False,
        reducer=None,
        reason="NOT-CHECKED:" + (";".join(misses) if misses else "no-candidate"),
    )


def reducer_id(loaded: ReducerLoad | None = None) -> str:
    loaded = loaded if loaded is not None else load_reducer()
    if loaded.reducer is None:
        return "NOT-CHECKED"
    ident = getattr(loaded.reducer, "REDUCER_ID", None)
    if isinstance(ident, str) and ident.strip():
        return ident.strip()
    if loaded.source is not None:
        return loaded.source.as_posix()
    return "NOT-CHECKED"


def consume_reducer() -> dict[str, Any]:
    """Import-and-identify. Does not evaluate receipts; that is Gate A, not STATUS.md."""
    loaded = load_reducer()
    return {
        "importable": loaded.importable,
        "source": None if loaded.source is None else _rel(loaded.source),
        "reason": loaded.reason,
        "reducer_id": reducer_id(loaded),
        "has_evaluate": bool(loaded.reducer is not None and hasattr(loaded.reducer, "evaluate")),
    }
