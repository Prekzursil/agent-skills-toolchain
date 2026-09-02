"""Run the four-benchmark variance-band pack (TST-0109)."""
from __future__ import annotations

import hashlib
import random
from pathlib import Path
from typing import Any

from variance_band.benchmarks import BENCHMARKS, DEFAULT_REQUESTS, REQUIRED, raw_for
from variance_band.stats import EmptyInputError, band_from_raw

DEFAULT_N = 8
DEFAULT_SEED = 109
DEFAULT_WARMUP = 1

_PINNED = ("stats.py", "benchmarks.py", "harness.py")


def sha_pin(repo: Path | None = None) -> dict[str, str]:
    """Pin the pack to the bytes of the code that produced it.

    Prefers the checkout's HEAD when a plain .git/HEAD is readable, otherwise
    fingerprints the variance_band sources themselves.
    """
    if repo is not None:
        head = Path(repo) / ".git" / "HEAD"
        try:
            ref = head.read_text(encoding="utf-8").strip()
            if ref.startswith("ref: "):
                ref = (Path(repo) / ".git" / ref[5:]).read_text(encoding="utf-8").strip()
            if len(ref) >= 40:
                return {"kind": "git-head", "sha": ref}
        except OSError:
            pass
    h = hashlib.sha256()
    here = Path(__file__).resolve().parent
    for name in _PINNED:
        h.update(name.encode("utf-8"))
        h.update((here / name).read_bytes())
    return {"kind": "variance-band-source-sha256", "sha": h.hexdigest()}


def run_pack(
    repo: Path | None = None, n: int = DEFAULT_N, seed: int = DEFAULT_SEED, warmup: int = DEFAULT_WARMUP
) -> dict[str, Any]:
    pin = sha_pin(repo)
    rows = []
    for bid in REQUIRED:
        raw = raw_for(bid, n=n, seed=seed, warmup=warmup)
        band = band_from_raw(
            bid,
            raw,
            metric=BENCHMARKS[bid][1],
            input_cardinality=DEFAULT_REQUESTS,
            sha=pin["sha"],
            seed=seed,
        )
        rows.append({**band, "raw": raw})

    rng = random.Random(seed)
    gauss_raw = [rng.gauss(100.0, 5.0) for _ in range(n)]
    gauss = band_from_raw("gaussian-seeded", gauss_raw, metric="synthetic", input_cardinality=n, sha=pin["sha"], seed=seed)

    # Empty-input control: the library must refuse, never emit a number.
    empty: dict[str, Any] = {"id": "empty-input", "fired_on_empty": False, "emitted_number": True}
    try:
        band_from_raw("empty-input", [])
    except EmptyInputError as exc:
        empty = {
            "id": "empty-input",
            "fired_on_empty": True,
            "emitted_number": False,
            "refused": True,
            "error": type(exc).__name__,
            "message": str(exc),
        }

    return {
        "benchmarks": rows,
        "n": n,
        "warmup": warmup,
        "seed": seed,
        "sha_pin": pin,
        "repo": str(repo or ""),
        "controls": {
            "gaussian-seeded": {**gauss, "raw": gauss_raw},
            "empty-input": empty,
        },
    }
