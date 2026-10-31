#!/usr/bin/env python3
"""Opaque compute handles: ``compute://<provider>/<kind>/<ident>``.

A handle is the single string a caller passes back to ``compute_exec`` /
``compute_status`` / ``compute_teardown`` after a ``compute_provision`` returns
one. ``ident`` may itself contain ``/`` -- OVH needs both the Public Cloud
project (``serviceName``) and the instance id, and Lightning may carry a
teamspace before the studio name -- so parsing keeps everything after the second
slash verbatim as the identity:

* ``compute://runpod/pod/<podId>``
* ``compute://ovh/instance/<serviceName>/<instanceId>``
* ``compute://lightning/studio/<name>``  (or ``.../<teamspace>/<name>``)

Pure, stdlib-only, no I/O: a wrong string raises :class:`HandleError`, which the
dispatch layer turns into an ``ok=False`` envelope rather than a crash.
"""

from __future__ import annotations

from dataclasses import dataclass

SCHEME = "compute://"
PROVIDERS = ("runpod", "ovh", "lightning")
# The canonical resource kind minted for each provider by ``compute_provision``.
DEFAULT_KIND = {"runpod": "pod", "ovh": "instance", "lightning": "studio"}


class HandleError(ValueError):
    """A malformed / unsupported compute handle string."""


@dataclass(frozen=True)
class Handle:
    """A parsed compute handle. ``ident`` may contain further ``/`` segments."""

    provider: str
    kind: str
    ident: str

    def format(self) -> str:
        """Render back to the canonical ``compute://`` URL (round-trips parse)."""
        return f"{SCHEME}{self.provider}/{self.kind}/{self.ident}"

    @property
    def parts(self) -> list[str]:
        """Non-empty ``/``-split segments of ``ident`` (OVH: ``[sn, id]``)."""
        return [p for p in self.ident.split("/") if p]


def parse(text: str) -> Handle:
    """Parse a ``compute://<provider>/<kind>/<ident>`` string into a Handle."""
    if not isinstance(text, str) or not text.startswith(SCHEME):
        raise HandleError(f"handle must start with '{SCHEME}': {text!r}")
    bits = text[len(SCHEME) :].split("/", 2)
    if len(bits) < 3 or not bits[0] or not bits[1] or not bits[2].strip("/"):
        raise HandleError(
            f"handle must be '{SCHEME}<provider>/<kind>/<ident>': {text!r}"
        )
    provider, kind, ident = bits[0], bits[1], bits[2].strip("/")
    if provider not in PROVIDERS:
        raise HandleError(
            f"unknown provider {provider!r}; valid: {', '.join(PROVIDERS)}"
        )
    return Handle(provider, kind, ident)


def make(provider: str, ident: str, kind: str = "") -> Handle:
    """Build a Handle for a freshly provisioned resource (kind defaulted)."""
    return Handle(provider, kind or DEFAULT_KIND.get(provider, provider), ident)
