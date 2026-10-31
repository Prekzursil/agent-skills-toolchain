"""Shared config + serialization helpers for the fb-messenger MCP server."""

from __future__ import annotations

import dataclasses
import json
import os
from typing import Any

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

COOKIES_PATH: str = os.environ.get("FB_COOKIES_PATH") or os.path.join(
    _REPO_ROOT, "data", "cookies.json"
)
MAX_CHARS = 8000


def ser(obj: Any) -> Any:
    """Best-effort, dependency-free serialization of arbitrary library models."""
    if obj is None or isinstance(obj, (str, int, float, bool)):
        return obj
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        try:
            return {k: ser(v) for k, v in dataclasses.asdict(obj).items()}
        except Exception:
            pass  # nosec B110 - best-effort; falls through to generic serialization
    if isinstance(obj, (list, tuple, set)):
        return [ser(x) for x in obj]
    if isinstance(obj, dict):
        return {str(k): ser(v) for k, v in obj.items()}
    if hasattr(obj, "__dict__"):
        return {k: ser(v) for k, v in vars(obj).items() if not k.startswith("_")}
    return str(obj)


def dump(obj: Any, limit: int = MAX_CHARS) -> str:
    """Serialize `obj` to a truncated, human-readable JSON string."""
    return json.dumps(ser(obj), default=str, indent=2, ensure_ascii=False)[:limit]


def fb_client():
    """Create an fbchat-muqit Client from the configured cookies.

    Only usable for NON-E2EE threads (groups / rooms / pages). Imported lazily
    so the rest of the server imports cleanly even if fbchat-muqit is absent.
    """
    from fbchat_muqit import Client

    return Client(cookies_file_path=COOKIES_PATH, disable_logs=True)
