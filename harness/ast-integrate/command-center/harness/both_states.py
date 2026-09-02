"""Both-states harness: good vs broken fixture in one process. TST-0031."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable


@dataclass
class BothStates:
    good: Any
    broken: Any
    identical: bool


def run_both(good_fn: Callable[[], Any], broken_fn: Callable[[], Any]) -> BothStates:
    good = good_fn()
    broken = broken_fn()
    return BothStates(good=good, broken=broken, identical=good == broken)


def load_fixture_pair(root: Path) -> dict[str, Path]:
    root = Path(root)
    return {
        "good": root / "good",
        "broken": root / "broken",
    }
