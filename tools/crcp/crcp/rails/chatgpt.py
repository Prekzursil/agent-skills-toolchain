"""ChatGPT rail facade backed by CRCP's existing bridge and write path."""

from __future__ import annotations

import time
from typing import Any, Callable, Protocol

from ..bridge import ChatGPTBridge


class _BridgeClient(Protocol):
    """Narrow bridge surface used by the adapter and its fixture tests."""

    def list_conversations(
        self, offset: int = 0, limit: int = 20
    ) -> dict[str, Any]: ...

    def get_conversation(self, conversation_id: str) -> dict[str, Any]: ...

    def me(self) -> dict[str, Any]: ...


Sender = Callable[..., dict[str, Any]]


class ChatGPTRail:
    """Normalize ChatGPT bridge operations behind the rail contract.

    Construction is lazy when no bridge is injected. This lets ``health``
    describe missing or expired local authentication instead of failing while
    the adapter registry is being assembled.

    The write capability remains opt-in per call and delegates to the existing
    owner-authorized ``write_path.send_message`` implementation. It is not
    invoked by polling or health checks.
    """

    _NAME = "chatgpt"

    def __init__(
        self,
        bridge: _BridgeClient | None = None,
        *,
        sender: Sender | None = None,
    ) -> None:
        self._bridge = bridge
        self._sender = sender

    @property
    def name(self) -> str:
        return self._NAME

    def _client(self) -> _BridgeClient:
        if self._bridge is None:
            self._bridge = ChatGPTBridge()
        return self._bridge

    def _send_impl(self) -> Sender:
        if self._sender is None:
            # Lazy import keeps read-only deployments independent of the
            # experimental write path until an owner explicitly sends.
            from ..write_path import send_message

            self._sender = send_message
        return self._sender

    def list_events(self, *, offset: int = 0, limit: int = 20) -> dict[str, Any]:
        """List conversations as normalized ChatGPT event summaries."""
        if isinstance(offset, bool) or not isinstance(offset, int) or offset < 0:
            raise ValueError("offset must be a non-negative integer")
        if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
            raise ValueError("limit must be a positive integer")

        listing = self._client().list_conversations(offset=offset, limit=limit)
        raw_items = listing.get("items") or []
        if not isinstance(raw_items, list):
            raise RuntimeError("ChatGPT conversation listing has invalid items")

        events: list[dict[str, Any]] = []
        for item in raw_items:
            if not isinstance(item, dict):
                continue
            event_id = item.get("id") or item.get("conversation_id")
            if not event_id:
                continue
            events.append(
                {
                    "id": str(event_id),
                    "kind": "conversation",
                    "title": item.get("title"),
                    "created_at": item.get("create_time"),
                    "updated_at": item.get("update_time"),
                }
            )

        return {
            "rail": self.name,
            "events": events,
            "offset": listing.get("offset", offset),
            "limit": listing.get("limit", limit),
            "total": listing.get("total"),
            "returned": len(events),
        }

    def fetch(self, event_id: str) -> dict[str, Any]:
        """Fetch a conversation while preserving its complete source payload."""
        if not isinstance(event_id, str) or not event_id.strip():
            raise ValueError("event_id must be a non-empty string")
        event_id = event_id.strip()
        payload = self._client().get_conversation(event_id)
        if not isinstance(payload, dict):
            raise RuntimeError("ChatGPT conversation response is not an object")
        return {
            "rail": self.name,
            "id": str(payload.get("id") or payload.get("conversation_id") or event_id),
            "kind": "conversation",
            "payload": payload,
        }

    def send(
        self,
        text: str,
        *,
        conversation_id: str | None = None,
        model: str | None = None,
        new_conversation: bool = False,
    ) -> dict[str, Any]:
        """Delegate an explicit owner-authorized send to ``write_path``."""
        if not isinstance(text, str) or not text.strip():
            raise ValueError("text must be a non-empty string")
        if conversation_id is not None and (
            not isinstance(conversation_id, str) or not conversation_id.strip()
        ):
            raise ValueError("conversation_id must be a non-empty string when supplied")
        if model is not None and (not isinstance(model, str) or not model.strip()):
            raise ValueError("model must be a non-empty string when supplied")
        if not isinstance(new_conversation, bool):
            raise ValueError("new_conversation must be a boolean")

        result = self._send_impl()(
            text,
            conversation_id=conversation_id.strip() if conversation_id else None,
            model=model.strip() if model else None,
            new_conversation=new_conversation,
        )
        if not isinstance(result, dict):
            raise RuntimeError("ChatGPT write path returned a non-object result")
        return result

    def health(self) -> dict[str, Any]:
        """Probe the bridge and return bounded, secret-free diagnostics."""
        started = time.monotonic()
        try:
            response = self._client().me()
            if not isinstance(response, dict):
                raise RuntimeError("ChatGPT identity response is not an object")
            return {
                "rail": self.name,
                "status": "READY",
                "ok": True,
                "readable": True,
                "writable": True,
                "latency_ms": round((time.monotonic() - started) * 1000, 1),
            }
        except Exception as exc:
            # Do not echo exception messages: HTTP bodies and local paths may
            # contain data unsuitable for health endpoints or shared logs.
            return {
                "rail": self.name,
                "status": "UNAVAILABLE",
                "ok": False,
                "readable": False,
                "writable": False,
                "latency_ms": round((time.monotonic() - started) * 1000, 1),
                "error_type": type(exc).__name__,
            }
