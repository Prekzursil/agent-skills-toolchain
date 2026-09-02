"""Scratch entry point: reaches a publish sink without a human checkpoint.

Planted so the enumerator must find an ungated public_publishing path.
The TRANSPORT binding is the substitution point for the fake sink.
"""
from __future__ import annotations

import urllib.request

TRANSPORT = urllib.request.urlopen
PUBLISH_URL = "https://upload.pypi.org/legacy/"


def scratch_cli_publish(payload: bytes = b"wheel-bytes") -> object:
    req = urllib.request.Request(PUBLISH_URL, data=payload, method="POST")
    return TRANSPORT(req)


scratch_cli_publish = scratch_cli_publish


if __name__ == "__main__":
    raise SystemExit("refusing real publish; inject FakeSink.TRANSPORT instead")
