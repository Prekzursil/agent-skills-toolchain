"""Deterministic diamond registry fixture for offline export tests."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from marketplace.digest import sha256_hex


@dataclass
class Diamond:
    index: dict[str, Any]
    blobs: dict[str, bytes]
    private_keys: dict[str, bytes]
    package_key_id: str


def diamond_registry() -> Diamond:
    blobs = {
        "app/1.0.0": b"app-payload-v1\n",
        "lib/1.0.0": b"lib-payload-v1\n",
        "util/1.0.0": b"util-payload-v1\n",
        "leaf/1.0.0": b"leaf-payload-v1\n",
    }
    index = {
        "packages": {
            "app": {
                "1.0.0": {
                    "blob": "app/1.0.0",
                    "digest": sha256_hex(blobs["app/1.0.0"]),
                    "deps": ["lib@1.0.0"],
                }
            },
            "lib": {
                "1.0.0": {
                    "blob": "lib/1.0.0",
                    "digest": sha256_hex(blobs["lib/1.0.0"]),
                    "deps": ["util@1.0.0"],
                }
            },
            "util": {
                "1.0.0": {
                    "blob": "util/1.0.0",
                    "digest": sha256_hex(blobs["util/1.0.0"]),
                    "deps": ["leaf@1.0.0"],
                }
            },
            "leaf": {
                "1.0.0": {
                    "blob": "leaf/1.0.0",
                    "digest": sha256_hex(blobs["leaf/1.0.0"]),
                    "deps": [],
                }
            },
        }
    }
    return Diamond(
        index=index,
        blobs=blobs,
        private_keys={"k1": b"not-a-real-key"},
        package_key_id="k1",
    )
