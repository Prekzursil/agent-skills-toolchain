"""Executable family-3 (command-output) and family-6 (environment) reproductions."""
from __future__ import annotations

import json
import os
import random
import socket
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

ReproFn = Callable[[dict], str]


def _fam3_deterministic(_env: dict) -> str:
    return (
        "cmd=python3 -c payload\n"
        "payload=fixed-family3-command-output\n"
        "status=0\n"
    )


def _fam3_iso_timestamp(_env: dict) -> str:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    return (
        "cmd=stamp-iso\n"
        f"now={now}\n"
        "payload=family3-timestamp-control\n"
        "status=0\n"
    )


def _fam3_json_ordering(_env: dict) -> str:
    keys = ["zeta", "alpha", "mu", "beta", "lambda"]
    rng = random.Random(os.urandom(8))
    rng.shuffle(keys)
    # Values are fixed; only key emission order varies.
    obj = {k: f"v-{k}" for k in keys}
    return json.dumps(obj, sort_keys=False) + "\n"


def _fam3_clock_seconds(_env: dict) -> str:
    return (
        "cmd=clock-seconds\n"
        f"now_s={int(datetime.now(timezone.utc).timestamp())}\n"
        "payload=family3-borderline-second-bucket\n"
        "status=0\n"
    )


def _fam6_temp_path(_env: dict) -> str:
    d = tempfile.mkdtemp(prefix="tmp")
    marker = Path(d) / "marker.txt"
    try:
        marker.write_text("family6-temp\n", encoding="utf-8")
        return (
            "cmd=mkdtemp\n"
            f"tmpdir={d}\n"
            "payload=family6-temp-path-control\n"
            "status=0\n"
        )
    finally:
        if marker.is_file():
            marker.unlink()
        try:
            os.rmdir(d)
        except OSError:
            pass


def _fam6_host(_env: dict) -> str:
    host = str(_env.get("HOST") or socket.gethostname())
    return (
        "cmd=uname-n\n"
        f"host={host}\n"
        "payload=family6-host-identifier\n"
        "status=0\n"
    )


def _fam6_seed(_env: dict) -> str:
    draw = os.urandom(8).hex()
    return (
        "cmd=urandom\n"
        f"seed_draw={draw}\n"
        "payload=family6-seed-control\n"
        "status=0\n"
    )


REPRODUCTIONS: dict[str, dict] = {
    "fam3.deterministic-payload": {
        "family": 3,
        "fn": _fam3_deterministic,
        "expect_class": None,
        "expect_deterministic": True,
        "title": "Family 3 command-output with a fixed payload",
    },
    "fam3.iso-timestamp": {
        "family": 3,
        "fn": _fam3_iso_timestamp,
        "expect_class": "timestamps",
        "expect_deterministic": False,
        "title": "Family 3 command-output with an embedded ISO timestamp",
    },
    "fam3.json-key-order": {
        "family": 3,
        "fn": _fam3_json_ordering,
        "expect_class": "ordering",
        "expect_deterministic": False,
        "title": "Family 3 JSON object emitted without sort_keys",
    },
    "fam3.clock-seconds": {
        "family": 3,
        "fn": _fam3_clock_seconds,
        "expect_class": "timestamps",
        "expect_deterministic": False,
        "borderline": True,
        "title": "Family 3 second-resolution clock (borderline; needs triple-run)",
    },
    "fam6.temp-path": {
        "family": 6,
        "fn": _fam6_temp_path,
        "expect_class": "temp_paths",
        "expect_deterministic": False,
        "title": "Family 6 environment: mkdtemp path",
    },
    "fam6.host-id": {
        "family": 6,
        "fn": _fam6_host,
        "expect_class": "host_identifiers",
        "expect_deterministic": True,
        "same_env_stable": True,
        "title": "Family 6 environment: hostname (stable on one box)",
    },
    "fam6.rng-seed": {
        "family": 6,
        "fn": _fam6_seed,
        "expect_class": "seeds",
        "expect_deterministic": False,
        "title": "Family 6 environment: process entropy draw",
    },
}


def run_repro(repro_id: str, env: dict | None = None) -> str:
    spec = REPRODUCTIONS[repro_id]
    fn: ReproFn = spec["fn"]
    return fn(env or {})


def host_variance_pair() -> tuple[str, str]:
    a = run_repro("fam6.host-id", {"HOST": "alpha-host"})
    b = run_repro("fam6.host-id", {"HOST": "bravo-host"})
    return a, b


host_variance_pair = host_variance_pair
