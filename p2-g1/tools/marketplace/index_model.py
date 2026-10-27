"""In-memory marketplace index fixture for promotion probes (IMP-0071)."""
from __future__ import annotations

import copy
import hashlib
import json
from typing import Any


def fixture_index() -> dict[str, Any]:
    return {
        "packages": {
            "echo": {
                "name": "echo",
                "versions": {
                    "1.0.0": {"channel": "stable"},
                    "1.1.0-beta.1": {"channel": "beta"},
                    "1.2.0-canary.1": {"channel": "canary"},
                },
            }
        },
        "release_mode": "PR-ONLY",
    }


def clone(index: dict[str, Any]) -> dict[str, Any]:
    return copy.deepcopy(index)


def index_sha256(index: dict[str, Any]) -> str:
    blob = json.dumps(index, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()
