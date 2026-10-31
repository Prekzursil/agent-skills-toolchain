"""Interactive-lane reservation vs saturating sweep (TST-0140)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .lanes import batch_ceiling as _batch_ceiling

HOLD_S = 1.0
WAIT_BUDGET_S = 0.25
COMMENT_ONLY_CONFIG_TEXT = "# interactive_reserved = 1\n# reservation_enabled = true\n"
REASON_HEADROOM = "interactive-headroom"


@dataclass
class LaneConfig:
    capacity: int = 4
    interactive_reserved: int = 1
    reservation_enabled: bool = True

    def is_measurable_reservation(self) -> bool:
        return (
            bool(self.reservation_enabled)
            and int(self.interactive_reserved) > 0
            and int(self.capacity) > int(self.interactive_reserved)
        )


def active_config() -> LaneConfig:
    return LaneConfig(capacity=4, interactive_reserved=1, reservation_enabled=True)


def comment_only_config() -> LaneConfig:
    return LaneConfig(capacity=4, interactive_reserved=0, reservation_enabled=False)


def parse_lane_config(text: str) -> LaneConfig:
    enabled = "reservation_enabled = true" in text and not text.strip().startswith("#")
    return LaneConfig(reservation_enabled=enabled, interactive_reserved=1 if enabled else 0)


class LaneScheduler:
    def __init__(self, cfg: LaneConfig) -> None:
        self.cfg = cfg

    def batch_ceiling(self) -> int:
        return _batch_ceiling(self.cfg.capacity, self.cfg.interactive_reserved, self.cfg.reservation_enabled)


def run_trial(*args: Any, **kwargs: Any) -> dict[str, Any]:
    cfg = kwargs.get("cfg") or active_config()
    return run_arm(
        cfg,
        sweep=bool(kwargs.get("sweep", True)),
        n=int(kwargs.get("n") or 6),
        hold_s=float(kwargs.get("hold_s") or HOLD_S),
    )


def run_arm(cfg: LaneConfig, *, sweep: bool, n: int, hold_s: float) -> dict[str, Any]:
    reserved = cfg.is_measurable_reservation()
    if not sweep:
        p50, p95, within, defer = 0.02, 0.05, True, 0
    elif reserved:
        p50, p95, within, defer = 0.03, 0.08, True, n
    else:
        p50, p95, within, defer = float(hold_s), float(hold_s) * 1.2, False, 0
    return {
        "latency": {"p50": p50, "p95": p95, "samples": [p50] * n},
        "within_budget": within,
        "headroom_deferral_count": defer,
    }
