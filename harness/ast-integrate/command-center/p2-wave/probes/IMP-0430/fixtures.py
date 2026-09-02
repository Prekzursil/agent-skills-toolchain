"""Repo vs live estate fixtures for the IMP-0430 audit control."""
from __future__ import annotations

from pathlib import Path

HERE = Path(__file__).resolve().parent
ESTATE = HERE / "fixtures" / "estate"

SESSION_HOOK = """STORE_NAME = "{store}"
KEY_SHAPE = "session"
KEY_TEMPLATE = "{{store}}|{{project_id}}|{{session_id}}"


def note() -> str:
    return "{store} session-keyed"
"""

PROJECT_HOOK = """STORE_NAME = "{store}"
KEY_SHAPE = "project"
KEY_TEMPLATE = "{{store}}|{{project_id}}"


def note() -> str:
    return "{store} project-keyed MUTANT live copy"
"""

SESSION_SETTINGS = """{
  "state_keying": {
    "policy": "session",
    "stores": {
      "goal_inject": {"key_shape": "session", "template": "{store}|{project_id}|{session_id}"},
      "ledger_replay": {"key_shape": "session", "template": "{store}|{project_id}|{session_id}"},
      "claims": {"key_shape": "session", "template": "{store}|{project_id}|{session_id}"},
      "caches": {"key_shape": "session", "template": "{store}|{project_id}|{session_id}"}
    }
  }
}
"""

LIVE_SETTINGS = """{
  "state_keying": {
    "policy": "mixed-undeployed",
    "stores": {
      "goal_inject": {"key_shape": "session", "template": "{store}|{project_id}|{session_id}"},
      "ledger_replay": {"key_shape": "session", "template": "{store}|{project_id}|{session_id}"},
      "caches": {"key_shape": "project", "template": "{store}|{project_id}"}
    }
  }
}
"""


def _write(path: Path, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8", newline="\n")


def build_estate() -> tuple[Path, Path]:
    repo = ESTATE / "repo"
    live = ESTATE / "live"
    for name in ("goal_inject", "ledger_replay", "claims", "caches"):
        _write(repo / "hooks" / f"{name}.py", SESSION_HOOK.format(store=name))
    _write(repo / "agent-self" / "config" / "settings.json", SESSION_SETTINGS)
    for name in ("goal_inject", "ledger_replay"):
        _write(live / "hooks" / f"{name}.py", SESSION_HOOK.format(store=name))
    _write(live / "hooks" / "caches.py", PROJECT_HOOK.format(store="caches"))
    _write(live / "agent-self" / "config" / "settings.json", LIVE_SETTINGS)
    claims_live = live / "hooks" / "claims.py"
    if claims_live.is_file():
        claims_live.unlink()
    return repo, live
