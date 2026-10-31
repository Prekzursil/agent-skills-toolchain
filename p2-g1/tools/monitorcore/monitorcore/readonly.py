"""Read-only filesystem wrapper for the program pane (IMP-0450)."""
from __future__ import annotations

from pathlib import Path


class ReadOnlyPaneError(RuntimeError):
    pass


class ReadOnlyFS:
    def open(self, path: Path | str, mode: str = "r", *args: object, **kwargs: object):
        if any(flag in mode for flag in "aw+x"):
            raise ReadOnlyPaneError(f"refused open({path!s}, {mode!r})")
        return Path(path).open(mode, *args, **kwargs)


__all__ = ["ReadOnlyFS", "ReadOnlyPaneError"]
