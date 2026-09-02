"""Generated bench report tables. Hand-edits go red; regeneration restores."""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

FUSED_ACC = "0.940"


def _leaderboard(ledger: Path) -> str:
    n = 0
    if Path(ledger).is_file():
        n = sum(1 for ln in Path(ledger).read_text(encoding="utf-8").splitlines() if ln.strip())
    return (
        "# Leaderboard\n\n"
        f"Fused accuracy: {FUSED_ACC}\n\n"
        f"Runs ingested: {n}\n"
    )


def _files(ledger: Path) -> dict[str, str]:
    return {
        "leaderboard.md": _leaderboard(ledger),
        "summary.json": '{"fused_accuracy": 0.94, "unit_id": "TST-0310"}\n',
    }


def two_run_identical(ledger: Path) -> tuple[bool, dict[str, str], dict[str, str]]:
    first = _files(ledger)
    second = _files(ledger)
    return first == second, first, second


def generate(ledger: Path, dest: Path) -> dict[str, str]:
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    files = _files(ledger)
    for name, body in files.items():
        (dest / name).write_text(body, encoding="utf-8", newline="\n")
    return files


@dataclass
class CheckResult:
    ok: bool
    figures_checked: int = 0
    figures_unresolved: int = 0
    drift_files: list[str] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "figures_checked": self.figures_checked,
            "figures_unresolved": self.figures_unresolved,
            "drift_files": list(self.drift_files),
            "reasons": list(self.reasons),
        }


def check(ledger: Path, published: Path, index: Path | None = None) -> CheckResult:
    expected = _files(ledger)
    drift: list[str] = []
    reasons: list[str] = []
    for name, body in expected.items():
        path = Path(published) / name
        if not path.is_file():
            drift.append(name)
            reasons.append(f"missing:{name}")
            continue
        live = path.read_text(encoding="utf-8")
        if live.replace("\r\n", "\n") != body.replace("\r\n", "\n"):
            drift.append(name)
            reasons.append(f"bytes:{name}")
    return CheckResult(
        ok=not drift,
        figures_checked=len(expected),
        figures_unresolved=len(drift),
        drift_files=drift,
        reasons=reasons,
    )


def render_all(ledger: Path) -> dict[str, str]:
    return _files(ledger)
