"""Fake sink: records owner-action effects without touching a real endpoint.

Every proof-of-reachability run must target this substitution. The receipt
records that the real transport was not invoked.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from urllib.request import Request


@dataclass
class FakeResponse:
    status: int = 200
    body: bytes = b'{"fake":true}'

    def read(self) -> bytes:
        return self.body

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *exc: object) -> None:
        return None


@dataclass
class FakeSink:
    calls: list[dict[str, Any]] = field(default_factory=list)
    substituted: bool = True
    real_transport_invoked: bool = False

    def __call__(self, req: Any = None, *args: Any, **kwargs: Any) -> FakeResponse:
        url = ""
        method = "GET"
        if isinstance(req, Request):
            url = str(req.full_url)
            method = str(req.get_method() or "GET")
        elif isinstance(req, str):
            url = req
            method = str(kwargs.get("method") or "GET")
        else:
            url = str(req)
        self.calls.append(
            {
                "url": url,
                "method": method.upper(),
                "args": [str(a) for a in args],
                "kwargs_keys": sorted(str(k) for k in kwargs),
            }
        )
        return FakeResponse()

    def as_receipt(self) -> dict[str, Any]:
        return {
            "substituted": True,
            "real_transport_invoked": False,
            "fake_sink": "command-center/p2-wave/probes/ADV-0140/fake_sink.py:FakeSink",
            "calls": list(self.calls),
        }


FakeSink.as_receipt = FakeSink.as_receipt
