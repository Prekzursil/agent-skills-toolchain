"""Blueprint library + omission gate (IMP-0242)."""
from __future__ import annotations

LIBRARY = {
    "bp.benchmark-generation": {"id": "bp.benchmark-generation"},
    "bp.reproducibility": {"id": "bp.reproducibility"},
    "bp.performance": {"id": "bp.performance"},
    "bp.concurrency-load-soak": {"id": "bp.concurrency-load-soak"},
    "bp.abandoned-work-salvage": {"id": "bp.abandoned-work-salvage"},
}


def load_library() -> dict:
    return dict(LIBRARY)


def omission_gate() -> dict[str, str]:
    return {
        "no-benchmark-generation": "omit-benchmark-generation",
        "no-reproducibility": "omit-reproducibility",
        "no-performance": "omit-performance",
        "no-soak": "omit-concurrency-load-soak",
        "no-salvage": "omit-abandoned-work-salvage",
        "no-content-equality-proof": "omit-content-equality-proof",
    }
