"""Refuse secret-shaped bytes in an offline bundle."""
from __future__ import annotations

import re
from typing import Any

_SECRET = re.compile(rb"(ghp_|sk-|BEGIN [A-Z ]*PRIVATE KEY|AKIA)")


class SecretInBundle(RuntimeError):
    pass


def scan_bytes(data: bytes) -> list[str]:
    return ["secret"] if _SECRET.search(data) else []


def report_contains_secret_body(report: dict[str, Any]) -> bool:
    blob = json_bytes(report)
    return bool(scan_bytes(blob))


def json_bytes(obj: Any) -> bytes:
    import json

    return json.dumps(obj).encode("utf-8")


def assert_clean(data: bytes) -> None:
    hits = scan_bytes(data)
    if hits:
        raise SecretInBundle("secret-shaped bytes in bundle")
