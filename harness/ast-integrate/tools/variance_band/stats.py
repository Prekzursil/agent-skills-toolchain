"""Library MDE from a raw vector."""
from __future__ import annotations

import math
from statistics import NormalDist

_Z = NormalDist()
Z_SUM = _Z.inv_cdf(1.0 - 0.05 / 2.0) + _Z.inv_cdf(0.80)


class EmptyInputError(ValueError):
    pass


def band_from_raw(bid: str, raw: list[float]) -> dict[str, float]:
    if not raw:
        raise EmptyInputError("empty")
    n = len(raw)
    mu = sum(raw) / n
    if n < 2:
        sd = 0.0
        mde = 0.0
    else:
        ss = sum((x - mu) ** 2 for x in raw)
        sd = math.sqrt(ss / (n - 1))
        mde = Z_SUM * sd * math.sqrt(2.0 / n)
    return {"id": bid, "n": n, "mean": mu, "stdev": sd, "mde": mde}
