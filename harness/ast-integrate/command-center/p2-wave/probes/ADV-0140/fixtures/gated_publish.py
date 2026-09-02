"""Known gated publish sink. Used as the rename-control original.

Effect is HTTP POST to the PyPI upload host. The function name is incidental.
The checkpoint call is the gate node.
"""
from __future__ import annotations

import urllib.request

TRANSPORT = urllib.request.urlopen
PUBLISH_URL = "https://upload.pypi.org/legacy/"


def human_checkpoint(question: str) -> str:
    return "approved"


def upload_distribution(payload: bytes = b"wheel-bytes") -> object:
    human_checkpoint("approve public publish to the package index?")
    req = urllib.request.Request(PUBLISH_URL, data=payload, method="POST")
    return TRANSPORT(req)
