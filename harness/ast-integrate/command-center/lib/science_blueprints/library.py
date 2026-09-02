"""Science blueprint library (IMP-0251)."""
from __future__ import annotations

BLUEPRINTS = {
    "bp.experiment-design": {"id": "bp.experiment-design"},
    "bp.statistical-review": {"id": "bp.statistical-review"},
    "bp.scientific-replication": {"id": "bp.scientific-replication"},
    "bp.model-evaluation": {"id": "bp.model-evaluation"},
}


def load_library() -> dict:
    return dict(BLUEPRINTS)


def omission_gate() -> list[str]:
    return [
        "no-preregistration",
        "no-power-analysis",
        "no-effect-size",
        "no-held-out",
        "no-multiplicity-correction",
        "no-replication-protocol",
    ]
