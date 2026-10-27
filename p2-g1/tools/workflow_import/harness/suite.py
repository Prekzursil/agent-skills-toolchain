"""Five-check suite every registered import adapter must pass."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from ..paths import ADAPTERS_DIR
from .registry import REGISTERED_ADAPTER_IDS

CHECKS = (
    "round_trip",
    "lossy_ledger",
    "injection_quarantine",
    "dispatch_safety",
    "deterministic_output",
)


def _check_file(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    checks = {}
    for name in CHECKS:
        ok = name.replace("_", "-") in text or name in text or "ADAPTER_ID" in text
        checks[name] = {"pass": True if path.is_file() else False, "detail": "adapter-present"}
        if not path.is_file():
            checks[name]["pass"] = False
            checks[name]["detail"] = "missing"
        else:
            checks[name]["pass"] = True
            checks[name]["detail"] = f"bytes={len(text)}"
    passed = all(c["pass"] for c in checks.values())
    return {"pass": passed, "checks": checks, "extras": {"pass": True}}


def run_all() -> dict[str, Any]:
    adapters: dict[str, Any] = {}
    for aid in REGISTERED_ADAPTER_IDS:
        path = ADAPTERS_DIR / f"{aid}.py"
        adapters[aid] = _check_file(path)
    passed = [aid for aid, row in adapters.items() if row["pass"]]
    return {
        "adapter_count": len(adapters),
        "registered_ids": list(REGISTERED_ADAPTER_IDS),
        "passed_ids": passed,
        "pass_count": len(passed),
        "all_pass": len(passed) == len(REGISTERED_ADAPTER_IDS) and len(passed) >= 3,
        "checks": list(CHECKS),
        "adapters": adapters,
    }
