"""Publisher that refuses unportable filenames (TST-0199)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from filename_gate import REJECTED_UNPORTABLE, classify

HERE = Path(__file__).resolve().parent


def invoke(name: str, payload: Mapping[str, Any] | None = None, config_path: str | None = None) -> dict[str, Any]:
    from pr_only_guard import gate

    return gate(name, dict(payload or {}), config_path)


def list_local(pkg: str, config_path: str | None = None) -> dict[str, Any]:
    return {
        "status": "PROCEEDED",
        "code": "PROCEEDED",
        "local": True,
        "pkg": pkg,
        "items": [pkg],
        "config_path": config_path,
    }


def pack(payload: Mapping[str, Any] | str, *, config_path: str | None = None) -> dict[str, Any]:
    if isinstance(payload, str):
        return {
            "status": "PROCEEDED",
            "code": "PROCEEDED",
            "local": True,
            "pkg": payload,
            "config_path": config_path,
        }
    files = list(payload.get("files") or [])
    rejections = []
    for name in files:
        rule = classify(str(name))
        if rule:
            rejections.append({"name": name, "rule": rule})
    if rejections:
        return {
            "status": REJECTED_UNPORTABLE,
            "published": False,
            "rejections": rejections,
            "config_path": config_path,
        }
    return {
        "status": "PROCEEDED",
        "published": True,
        "rejections": [],
        "config_path": config_path,
    }


def publish(payload: Mapping[str, Any] | str, *, config_path: str | None = None) -> dict[str, Any]:
    if isinstance(payload, str):
        from pr_only_guard import gate

        return gate("publish", {"pkg": payload}, config_path)
    return pack(payload, config_path=config_path)
