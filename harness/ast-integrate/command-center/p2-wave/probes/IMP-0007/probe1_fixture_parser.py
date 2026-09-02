#!/usr/bin/env python3
"""Probe 1: fixture strict parser — accept x-, reject bare unknown.

Catalog signal (1): a strict-mode parser fixture rejects a manifest carrying a
bare unknown key and accepts the same key under ``x-``.

Negative control runs FIRST: known-bad must fail before any accept is trusted.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
PLUGIN = REPO / "tools" / "plugin"
TEST = PLUGIN / "tests" / "test_strict_parser_policy.py"
LIVE = REPO / ".claude-plugin" / "plugin.json"
sys.path.insert(0, str(PLUGIN))
import compat_linter as cl  # noqa: E402
import strict_parser as sp  # noqa: E402

BARE = "experimentalFlag"
XKEY = "x-experimentalFlag"


def _fail(msg: str) -> int:
    print(f"FAILED:IMP-0007-probe1 {msg}")
    return 1


def main() -> int:
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
    proc = subprocess.run(
        [sys.executable, "-B", str(TEST)],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
    )
    tail = ((proc.stdout or "") + (proc.stderr or "")).strip()
    print(tail)
    if proc.returncode != 0:
        return _fail("fixture tests")
    if "SUCCESS:IMP-0007-tests" not in tail:
        return _fail("tests sentinel absent")

    live = json.loads(LIVE.read_text(encoding="utf-8"))

    # NEGATIVE CONTROL first: known-bad must reject and name the field.
    bad = dict(live)
    bad[BARE] = True
    bad_result = sp.parse_manifest(bad)
    print(
        f"negative-control bare={BARE!r} ok={bad_result['ok']} "
        f"errors={bad_result['errors']}"
    )
    if bad_result["ok"]:
        return _fail("known-bad accepted; cannot trust later accept")
    if BARE not in " ".join(bad_result["errors"]):
        return _fail("known-bad did not name the field")
    lint_bad = cl.lint_manifest(bad)
    if lint_bad["ok"] or BARE not in lint_bad["additive_rejected"]:
        return _fail("linter silent on known-bad")

    # Same key under x- must accept.
    good = dict(live)
    good[XKEY] = {"forward": True}
    good_result = sp.parse_manifest(good)
    print(
        f"x-accept key={XKEY!r} ok={good_result['ok']} "
        f"kind={good_result['classified'].get(XKEY)}"
    )
    if not good_result["ok"]:
        return _fail(f"x- key rejected: {good_result['errors']}")
    lint_good = cl.lint_manifest(good)
    if not lint_good["ok"]:
        return _fail(f"linter rejected x- key: {lint_good['errors']}")

    live_result = sp.parse_path(LIVE)
    print(f"live-manifest ok={live_result['ok']} keys={live_result['keys']}")
    if not live_result["ok"]:
        return _fail(f"live plugin.json rejected: {live_result['errors']}")

    print(
        "negative_fired=True x_accepted=True live_ok=True "
        f"frozen={len(live_result['frozen'])}"
    )
    print("SUCCESS:IMP-0007-probe1 fixture parser accept x- / reject bare unknown")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
