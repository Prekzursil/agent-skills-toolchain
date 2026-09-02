"""Wilson score interval and Brier score. Pure functions of k/n or (p, y)."""
from __future__ import annotations

import hashlib
import json
import math
from typing import Any, Iterable, Sequence


Z_95 = 1.96
BRIER_FORMULA = "mean((p_defect - y_should_refute)^2) over raw rows; y in {0,1}"


def dumps(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def sha256_obj(obj: Any) -> str:
    return hashlib.sha256(dumps(obj).encode("utf-8")).hexdigest()


def r10(x: float) -> float:
    return float(f"{float(x):.10f}")


def wilson(k: int, n: int, z: float = Z_95) -> dict[str, Any]:
    if n <= 0:
        raise ValueError("wilson n must be > 0")
    if k < 0 or k > n:
        raise ValueError("wilson k out of range")
    p = k / n
    z2 = z * z
    den = 1.0 + z2 / n
    center = (p + z2 / (2.0 * n)) / den
    rad = z * math.sqrt((p * (1.0 - p) + z2 / (4.0 * n)) / n) / den
    return {
        "k": k,
        "n": n,
        "z": z,
        "point": r10(p),
        "center": r10(center),
        "low": r10(max(0.0, center - rad)),
        "high": r10(min(1.0, center + rad)),
    }


def brier(pairs: Sequence[tuple[float, int]]) -> dict[str, Any]:
    if not pairs:
        raise ValueError("brier empty")
    total = 0.0
    for p, y in pairs:
        if y not in (0, 1):
            raise ValueError("brier y must be 0 or 1")
        if p < 0.0 or p > 1.0:
            raise ValueError("brier p out of range")
        total += (p - y) ** 2
    n = len(pairs)
    return {
        "n": n,
        "brier": r10(total / n),
        "formula": BRIER_FORMULA,
    }


def brier_control() -> dict[str, Any]:
    """Scorer self-check: perfect forecasts score 0; sure-wrong score 1."""
    perfect = brier([(0.0, 0), (0.0, 0), (1.0, 1), (1.0, 1)])
    sure_wrong = brier([(1.0, 0), (1.0, 0), (0.0, 1), (0.0, 1)])
    if perfect["brier"] != 0.0:
        raise RuntimeError(f"brier scorer broken: perfect={perfect}")
    if sure_wrong["brier"] != 1.0:
        raise RuntimeError(f"brier scorer broken: sure_wrong={sure_wrong}")
    return {"perfect_brier": perfect["brier"], "sure_wrong_brier": sure_wrong["brier"]}


def close(a: float, b: float, tol: float = 1e-9) -> bool:
    return abs(float(a) - float(b)) <= tol


def grouped(rows: Iterable[dict[str, Any]], key: str) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        out.setdefault(str(row[key]), []).append(row)
    return out
