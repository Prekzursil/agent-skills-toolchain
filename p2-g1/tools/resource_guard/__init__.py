"""Resource guard package."""
from .termination import (  # noqa: F401
    ACTION_REAP,
    ACTION_SPARE,
    REASON_ALLOWLIST,
    REASON_BELOW_CEILING,
    REASON_ORPHAN_NOT_PROVEN,
    REASON_ORPHAN_PROVEN,
    apply_reaps,
    drop_allowlist,
    evaluate,
    health_status,
    load_below_ceiling_world,
    load_ceiling_world,
    naive_rss_kill_set,
    shared_service_survives,
)
