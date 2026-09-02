#!/usr/bin/env python3
"""Windows-box column: PATHEXT / Get-Command semantics on this Linux worktree.

There is no Win32 kernel here. The column applies documented Windows lookup
rules (PATHEXT, .cmd shims, no POSIX which) to the planted host-cache shim.
Provenance is recorded as windows-semantics-oracle, not as a live VM.
Portable claims use the same stdlib evaluators as the Linux container.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from claims import (
    HOST_CACHE,
    WIN_PATHEXT,
    evaluate_bundle,
    plant_host_cache,
)


def run_windows_oracle(*, nonce: str, run_id: str) -> dict[str, Any]:
    cache = plant_host_cache()
    bin_dir = str(cache / "bin")
    # Prepend the planted shim directory. Do not inherit a contaminated PATH
    # of host developer tools into the shim lookup; portable claims ignore PATH.
    path = os.pathsep.join([bin_dir, "/usr/bin", "/bin"])
    env_save = {
        "PATH": os.environ.get("PATH"),
        "PATHEXT": os.environ.get("PATHEXT"),
        "CNF0151_PATH": os.environ.get("CNF0151_PATH"),
        "CNF0151_PATHEXT": os.environ.get("CNF0151_PATHEXT"),
        "CNF0151_HOST_CACHE": os.environ.get("CNF0151_HOST_CACHE"),
        "CNF0151_WORK": os.environ.get("CNF0151_WORK"),
    }
    try:
        os.environ["CNF0151_PATH"] = path
        os.environ["CNF0151_PATHEXT"] = WIN_PATHEXT
        os.environ["PATHEXT"] = WIN_PATHEXT
        os.environ["CNF0151_HOST_CACHE"] = str(cache)
        os.environ["CNF0151_WORK"] = str(Path(__file__).resolve().parent)
        bundle = evaluate_bundle(Path(__file__).resolve().parent)
    finally:
        for key, val in env_save.items():
            if val is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = val
    bundle["windows"] = {
        "instrument": "windows-semantics-oracle",
        "hardware": "not-present-on-this-linux-worktree",
        "rules_applied": [
            "PATHEXT=.COM;.EXE;.BAT;.CMD",
            "Get-Command resolves name+ext without POSIX X_OK",
            ".cmd shim planted in host cache bin",
        ],
        "run_id": run_id,
        "nonce": nonce,
        "host_cache": str(HOST_CACHE),
    }
    return bundle
