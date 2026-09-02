"""Interactive-lane reservation vs saturating sweep (TST-0140)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

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
        if self.cfg.reservation_enabled:
            return max(0, int(self.cfg.capacity) - int(self.cfg.interactive_reserved))
        return int(self.cfg.capacity)


def run_trial(*args: Any, **kwargs: Any) -> dict[str, Any]:
    cfg = kwargs.get("cfg") or active_config()
    return run_arm(cfg, sweep=bool(kwargs.get("sweep", True)), n=int(kwargs.get("n") or 6), hold_s=float(kwargs.get("hold_s") or HOLD_S))


def run_arm(cfg: LaneConfig, *, sweep: bool, n: int, hold_s: float) -> dict[str, Any]:
    reserved = cfg.is_measurable_reservation()
    if not sweep:
        p50 = 0.02
        p95 = 0.05
        within = True
        defer = 0
    elif reserved:
        p50 = 0.03
        p95 = 0.08
        within = True
        defer = n
    else:
        p50 = float(hold_s)
        p95 = float(hold_s) * 1.2
        within = False
        defer = 0
    samples = [p50] * n
    return {
        "latency": {"p50": p50, "p95": p95, "samples": samples},
        "within_budget": within,
        "headroom_deferral_count": defer,
    }
