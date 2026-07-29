"""R9: the hard wave ceiling for UNATTENDED (cron) fan-out.

CSIE-DESIGN.md:197-202 — the harness `submit_and_gate` deliberately defaults to NO wall-clock
cap, because a hard cap once produced a FALSE `TIMEOUT` on a wave whose artifacts were complete
and gate-valid. That default is correct for an interactive run and unsafe for a cron, so the
ceiling lives here in the engine and leaves the harness default untouched.

`check_wave` runs BEFORE fan-out. Every branch fails CLOSED: an unknown quota, a zero unit
count, or a disabled timeout refuses the wave rather than assuming it is fine. An unattended
run has nobody to ask.

Why this is not theoretical: measured 2026-07-26, a coverage fan-out whose artifacts had all
landed at 3m04s was still billing an r5d.2xlarge ~15 minutes later after its poller died, and
was found only by a manual sweep. Unwatched and repeated nightly, that is the failure this
gate exists to prevent.
"""

from __future__ import annotations

from dataclasses import dataclass

#: Databricks-side concurrency the RAIL is policy-approved for (harness.contract.RAIL).
RAIL_MAX_CONCURRENCY = 48


@dataclass(frozen=True)
class WaveCeiling:
    """All four limits are mandatory; 0 or negative means "disabled" and is rejected."""

    max_units: int
    max_concurrent: int
    wall_clock_s: int
    per_unit_watchdog_s: int


#: Shipped default for the nightly wave. Deliberately conservative: a wave that needs more than
#: this should be split, not granted a bigger ceiling.
DEFAULT = WaveCeiling(
    max_units=48,
    max_concurrent=RAIL_MAX_CONCURRENCY,
    wall_clock_s=4 * 3600,
    per_unit_watchdog_s=1800,
)


def check_wave(
    n_units: int, ceiling: WaveCeiling, quota_ok: bool | None
) -> tuple[bool, str]:
    """Gate an unattended wave. Returns (allowed, reason); reason is "ok" only when allowed.

    `quota_ok` is caller-supplied on purpose. There is no budget API to consult — AgentBridge's
    `get_budget` was retired with the daemon — so inventing a number here would be worse than
    admitting the dependency. `None` (unknown) refuses.
    """
    if n_units <= 0:
        return False, f"n_units={n_units}: nothing to fan out"
    if ceiling.wall_clock_s <= 0:
        return (
            False,
            "wall_clock_s is disabled: an unattended wave needs a wall-clock ceiling",
        )
    if ceiling.per_unit_watchdog_s <= 0:
        return (
            False,
            "per_unit_watchdog_s is disabled: a stuck unit would run to the wave ceiling",
        )
    if ceiling.per_unit_watchdog_s > ceiling.wall_clock_s:
        return False, (
            f"watchdog {ceiling.per_unit_watchdog_s}s exceeds wall_clock_s "
            f"{ceiling.wall_clock_s}s: it could never fire"
        )
    if ceiling.max_units <= 0 or n_units > ceiling.max_units:
        return False, f"n_units={n_units} exceeds max_units={ceiling.max_units}"
    if ceiling.max_concurrent <= 0 or ceiling.max_concurrent > RAIL_MAX_CONCURRENCY:
        return False, (
            f"max_concurrent={ceiling.max_concurrent} outside the policy-approved "
            f"1..{RAIL_MAX_CONCURRENCY}"
        )
    if quota_ok is not True:
        state = "unknown" if quota_ok is None else "exhausted"
        return False, f"quota {state}: refusing to start an unattended wave"
    return True, "ok"
