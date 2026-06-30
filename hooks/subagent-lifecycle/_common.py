"""_common.py — shared utilities for subagent-lifecycle hooks.

Stdlib-only. Fail-open: every exported function silently absorbs exceptions.
Never raises; never blocks; never writes to disk on error.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

# ── opt-out gate ─────────────────────────────────────────────────────────────

THIS: Path = Path(__file__).resolve().parent
DISABLED: Path = THIS / ".disabled"

# ── event-ledger bridge (same pattern as goal-reinject/reinject.py) ───────────

_LEDGER_DIR: str = str(THIS.parent / "event-ledger")

# ── per-session sidecar state root ────────────────────────────────────────────
# Override via SUBAGENT_LIFECYCLE_STATE_DIR env var (used by tests).
STATE_ROOT: Path = Path(
    os.environ.get(
        "SUBAGENT_LIFECYCLE_STATE_DIR",
        str(Path.home() / ".claude" / "subagent-lifecycle"),
    )
)


# ---------------------------------------------------------------------------
# Opt-out
# ---------------------------------------------------------------------------


def is_opted_out() -> bool:
    """Return True iff this hook should be silenced.

    Two mechanisms (mirror of honest-signal + mcp-liveness pattern):
      1. A `.disabled` file next to this module.
      2. SUBAGENT_LIFECYCLE env var set to 'off', '0', or 'false'.
    """
    return DISABLED.exists() or os.environ.get("SUBAGENT_LIFECYCLE", "").lower() in (
        "off",
        "0",
        "false",
    )


# ---------------------------------------------------------------------------
# Goal retrieval from the event ledger
# ---------------------------------------------------------------------------


def get_goal(cwd: str) -> str | None:
    """Return the active goal text for *cwd* from the event-ledger, or None.

    Identical source as goal-reinject/reinject.py (reuse, not reinvent):
    reads ledger.state(cwd)['goal'].  Fail-open: any error → None.
    """
    try:
        if _LEDGER_DIR not in sys.path:
            sys.path.insert(0, _LEDGER_DIR)
        import ledger  # noqa: PLC0415 — local import; ledger is stdlib-only

        st = ledger.state(str(cwd))
        return (st or {}).get("goal")
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Output formatting
# ---------------------------------------------------------------------------


def emit_context(
    event_name: str,
    additional_context: str,
    decision: str | None = None,
    reason: str | None = None,
) -> None:
    """Print a hook output JSON object to stdout.

    For SubagentStop blocks, `decision` and `reason` must be at the TOP LEVEL
    of the emitted JSON (not nested inside hookSpecificOutput) per the
    SubagentStop contract spec.  `additionalContext` stays inside
    hookSpecificOutput for context injection.

    Non-blocking calls (decision=None) emit only hookSpecificOutput, matching
    the shape used by every other hook in this harness.
    """
    payload: dict = {
        "hookSpecificOutput": {
            "hookEventName": event_name,
            "additionalContext": additional_context,
        }
    }
    if decision is not None:
        # Top-level decision + reason per SubagentStop blocking spec (M1 fix).
        payload["decision"] = decision
        payload["reason"] = reason if reason is not None else additional_context
    print(json.dumps(payload))


# ---------------------------------------------------------------------------
# Result-contract sidecar helpers
# ---------------------------------------------------------------------------


def _safe_key(session_id: str, agent_type: str) -> str:
    """Windows-safe filename segment from session_id + agent_type."""
    raw = f"{session_id}-{agent_type}"
    return (
        "".join(c if c.isalnum() or c in "-_." else "-" for c in raw)[:80] or "default"
    )


def load_contract(session_id: str, agent_type: str) -> dict | None:
    """Load the result-contract sidecar for this session+agent, or None.

    Contract files are written externally by the orchestrating agent before
    spawning the subagent.  Path:
        STATE_ROOT/contracts/<safe_key>.json
    """
    try:
        path = STATE_ROOT / "contracts" / f"{_safe_key(session_id, agent_type)}.json"
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        pass
    return None


def load_retries(session_id: str, agent_type: str, spawn_id: str = "") -> dict:
    """Load retry-counter state for this session+agent+spawn, or empty dict.

    spawn_id is a short per-spawn hash so distinct subagents of the same
    agent_type never share a retry budget (M1 fix).
    """
    try:
        key = _safe_key(session_id, agent_type)
        if spawn_id:
            key = (key + "-" + spawn_id[:16])[:80]
        path = STATE_ROOT / "retries" / f"{key}.json"
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}


def save_retries(
    session_id: str, agent_type: str, state: dict, spawn_id: str = ""
) -> None:
    """Persist retry-counter state (best-effort; silently ignored on error).

    spawn_id mirrors load_retries — use the same value for a consistent key.
    """
    try:
        key = _safe_key(session_id, agent_type)
        if spawn_id:
            key = (key + "-" + spawn_id[:16])[:80]
        d = STATE_ROOT / "retries"
        d.mkdir(parents=True, exist_ok=True)
        (d / f"{key}.json").write_text(json.dumps(state), encoding="utf-8")
    except Exception:
        pass
