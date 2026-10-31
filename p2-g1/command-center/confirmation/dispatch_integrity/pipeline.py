"""Fan-in pipeline: evaluate_result, early-return on reject, then read_digest."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from .digest_reader import read_digest
from .gate import evaluate_result


def fan_in(root: Path, result: dict[str, Any]) -> dict[str, Any]:
    gate = evaluate_result(root, result)
    if not gate.get("passed"):
        return {"accepted": False, "digest": None, "gate": gate}
    digest = read_digest(root, result)
    return {"accepted": True, "digest": digest, "gate": gate}
