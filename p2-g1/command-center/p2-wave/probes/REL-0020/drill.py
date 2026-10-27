#!/usr/bin/env python3
# REL-0020 cache-invalidation drill (rebuilt 2026-10-25, shard16-wave2 resume).
# Isolated replica client (receipt: the sparse tree has no product
# platform/plugin/cache.py, so the client under test is the replica whose
# resolution_order() is enumerated, not assumed):
#   resolution order: bytecode -> unpacked-user-cache -> http-tarball-cache ->
#   cas-name-index -> install-tree.
# seed_poison writes the STALE v1 payload into every cache location the client
# consults. install(refresh=...) lays down the candidate v2 in the install
# tree and, when refresh=True, also invalidates each cache location.
# execute() returns the behaviour marker of the bytes the client ACTUALLY ran:
#   BEHAVE-POISON-v1-old-bytes vs BEHAVE-FIXED-v2-new-bytes.
from __future__ import annotations

import json
import shutil
from pathlib import Path

OLD_MARKER = "BEHAVE-POISON-v1-old-bytes"
NEW_MARKER = "BEHAVE-FIXED-v2-new-bytes"
OLD_VERSION, NEW_VERSION = "1.0.0", "1.0.1"
CACHE_KEYS = ["bytecode", "unpacked-user-cache", "http-tarball-cache",
              "cas-name-index", "install-tree"]


class Client:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.caches = {k: self.root / "cache" / k for k in CACHE_KEYS}

    def resolution_order(self):
        return list(CACHE_KEYS)

    def seed_poison(self):
        stale_payload = {"package": "rel0020-canary-plugin", "version": OLD_VERSION,
                         "behaviour": OLD_MARKER}
        for key in CACHE_KEYS:
            d = self.caches[key]
            d.mkdir(parents=True, exist_ok=True)
            if key == "bytecode":
                (d / "rel0020-canary-plugin.pyc").write_bytes(json.dumps(stale_payload).encode())
            elif key == "http-tarball-cache":
                (d / "rel0020-canary-plugin.tar.json").write_text(json.dumps(stale_payload),
                                                                 encoding="utf-8", newline="\n")
            elif key == "cas-name-index":
                (d / "index.json").write_text(json.dumps(stale_payload),
                                              encoding="utf-8", newline="\n")
            else:
                (d / "payload.json").write_text(json.dumps(stale_payload),
                                                encoding="utf-8", newline="\n")

    def install(self, refresh: bool):
        inst = self.caches["install-tree"]
        inst.mkdir(parents=True, exist_ok=True)
        (inst / "payload.json").write_text(
            json.dumps({"package": "rel0020-canary-plugin", "version": NEW_VERSION,
                        "behaviour": NEW_MARKER}),
            encoding="utf-8", newline="\n")
        if refresh:
            for key in CACHE_KEYS[:-1]:
                if self.caches[key].exists():
                    shutil.rmtree(self.caches[key])

    def _read(self, key):
        d = self.caches[key]
        candidates = {"bytecode": "rel0020-canary-plugin.pyc",
                      "http-tarball-cache": "rel0020-canary-plugin.tar.json",
                      "cas-name-index": "index.json",
                      "unpacked-user-cache": "payload.json",
                      "install-tree": "payload.json"}
        f = d / candidates[key]
        if f.is_file():
            try:
                return json.loads(f.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                return json.loads(f.read_bytes().decode("utf-8", "replace"))
        return None

    def execute(self):
        for key in self.resolution_order():
            payload = self._read(key)
            if payload and "behaviour" in payload:
                return {"behaviour": payload["behaviour"], "version": payload["version"],
                        "hit": key}
        return {"behaviour": None, "version": None, "hit": None}

    def version_file(self):
        inst = self.caches["install-tree"]
        f = inst / "VERSION"
        if not f.is_file():
            f.write_text(NEW_VERSION + "\n", encoding="utf-8", newline="\n")
        return f.read_text(encoding="utf-8").strip()
