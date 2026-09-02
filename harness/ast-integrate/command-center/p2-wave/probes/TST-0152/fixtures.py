"""TST-0152 fixtures: live, 11h-finished, mtime-only, and genuinely hung."""
from __future__ import annotations

ELEVEN_H_S = 11 * 3600

ACTIVE_AGENT: dict = {
    "id": "agent-live",
    "orchestrator_state": "running",
    "artifact_mtime_age_s": ELEVEN_H_S,
    "heartbeat": {"seq": 12, "age_s": 2, "advancing": True},
    "process": {"alive": True, "stopped": False},
}

FINISHED_11H: dict = {
    "id": "agent-11h-finished",
    "orchestrator_state": "finished",
    "finished_at_age_s": ELEVEN_H_S,
    "artifact_mtime_age_s": ELEVEN_H_S,
    "heartbeat": {"seq": 900, "age_s": ELEVEN_H_S, "advancing": False},
    "process": {"alive": False, "stopped": False},
}

MTIME_ONLY: dict = {
    "id": "mtime-only",
    "artifact_mtime_age_s": ELEVEN_H_S,
}

HUNG_AGENT: dict = {
    "id": "agent-hung",
    "orchestrator_state": "running",
    "artifact_mtime_age_s": 30,
    "heartbeat": {"seq": 3, "age_s": 600, "advancing": False},
    "process": {"alive": True, "stopped": True},
}
