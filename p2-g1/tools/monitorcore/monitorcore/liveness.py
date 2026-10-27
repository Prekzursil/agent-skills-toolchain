"""Agent liveness: orchestrator + heartbeat + process. mtime is observational only."""
from __future__ import annotations

from typing import Any

ACTIVE = "active"
FINISHED = "finished"
STALLED = "stalled"
UNDECIDABLE = "undecidable"


def classify_agent(agent: dict[str, Any]) -> dict[str, Any]:
    observational_mtime_age_s = agent.get("artifact_mtime_age_s")
    orch = agent.get("orchestrator_state")
    hb = agent.get("heartbeat") or {}
    proc = agent.get("process") or {}
    sources_used: list[str] = []
    independent_signals: list[str] = []

    if orch is None and not hb and not proc:
        state = UNDECIDABLE
        source = "insufficient-signals"
    elif orch == "finished":
        state = FINISHED
        source = "orchestrator_state"
        sources_used = ["orchestrator_state"]
    elif orch == "running" and hb.get("advancing") and proc.get("alive") and not proc.get("stopped"):
        state = ACTIVE
        source = "heartbeat"
        sources_used = ["orchestrator_state", "heartbeat", "process_signal"]
        independent_signals = ["heartbeat", "process_signal"]
    elif orch == "running" and (not hb.get("advancing") or proc.get("stopped")):
        state = STALLED
        source = "orchestrator_state+process_signal"
        sources_used = ["orchestrator_state", "heartbeat", "process_signal"]
        independent_signals = ["heartbeat", "process_signal"]
    else:
        state = UNDECIDABLE
        source = "insufficient-signals"

    return {
        "id": agent.get("id"),
        "state": state,
        "source": source,
        "sources_used": sources_used,
        "independent_signals": independent_signals,
        "mtime_used_as_predicate": False,
        "stall_from_mtime_only": False,
        "observational_mtime_age_s": observational_mtime_age_s,
    }
