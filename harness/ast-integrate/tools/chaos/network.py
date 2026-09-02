"""Delegated network primitives — not shipped."""
from __future__ import annotations

from chaos.safety import DelegatedFaultError

NETWORK_IDS = ("net.partition", "net.loss", "net.latency")


def inject_network(name: str, *args, **kwargs):
    raise DelegatedFaultError(f"network primitive {name} is delegated, not shipped")
