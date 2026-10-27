"""Common contracts for CRCP rail adapters.

Adapters are intentionally small facades over existing rail implementations.
The control plane can use the read methods for every rail and discover whether
the optional write operation is enabled through ``health()["writable"]``.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class RailAdapter(Protocol):
    """Structural interface implemented by a CRCP rail facade.

    ``send`` is an optional *capability* even though it is part of the Python
    interface. Read-only adapters should implement it by raising
    ``NotImplementedError`` and report ``writable=False`` from ``health``.
    Keeping a single structural interface makes capability checks predictable
    for callers and avoids probing for arbitrary method names.
    """

    @property
    def name(self) -> str:
        """Stable rail identifier used in normalized results."""
        ...

    def list_events(self, *, offset: int = 0, limit: int = 20) -> dict[str, Any]:
        """Return a page containing normalized event summaries."""
        ...

    def fetch(self, event_id: str) -> dict[str, Any]:
        """Fetch one event and return its lossless rail payload."""
        ...

    def send(
        self,
        text: str,
        *,
        conversation_id: str | None = None,
        model: str | None = None,
        new_conversation: bool = False,
    ) -> dict[str, Any]:
        """Optionally submit text to the rail.

        Implementations must not include credentials or challenge tokens in
        the returned metadata.
        """
        ...

    def health(self) -> dict[str, Any]:
        """Return a metadata-only health snapshot without raising."""
        ...
