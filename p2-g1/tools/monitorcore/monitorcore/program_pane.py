"""Read-only program pane: renders live events/receipts, refuses mutation (IMP-0450)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .readonly import ReadOnlyFS, ReadOnlyPaneError

PROGRAM_PANE_ID = "program"


class ProgramPane:
    def __init__(self, root: Path | str) -> None:
        self.root = Path(root)
        self.fs = ReadOnlyFS()
        self.events_path = self.root / "command-center" / "events" / "EVENTS.jsonl"
        self.receipts_dir = self.root / "command-center" / "receipts"

    def render(self) -> str:
        events: list[dict[str, Any]] = []
        if self.events_path.is_file():
            for line in self.events_path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    try:
                        events.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        receipts: list[dict[str, Any]] = []
        if self.receipts_dir.is_dir():
            for path in sorted(self.receipts_dir.glob("*.json")):
                try:
                    receipts.append(json.loads(path.read_text(encoding="utf-8")))
                except (OSError, json.JSONDecodeError):
                    continue
        lines = [
            f"program-pane events count={len(events)} receipts count={len(receipts)}",
        ]
        for ev in events:
            lines.append(json.dumps(ev, sort_keys=True))
        for rec in receipts:
            lines.append(json.dumps(rec, sort_keys=True))
        return "\n".join(lines) + "\n"

    def mutate_append_event(self, payload: dict[str, Any] | None = None) -> None:
        raise ReadOnlyPaneError("mutate_append_event refused")

    def mutate_write_receipt(self, unit_id: str = "", body: dict[str, Any] | None = None) -> None:
        raise ReadOnlyPaneError("mutate_write_receipt refused")

    def dispatch_unit(self, unit_id: str = "") -> None:
        raise ReadOnlyPaneError("dispatch_unit refused")


__all__ = ["PROGRAM_PANE_ID", "ProgramPane", "ReadOnlyPaneError"]
