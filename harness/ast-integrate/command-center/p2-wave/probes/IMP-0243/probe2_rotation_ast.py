#!/usr/bin/env python3
"""IMP-0243 probe2: no rotation/revocation call site (AST over the allowed call set)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO))
import platform as _plat

_plat.__path__ = [str(REPO / "platform")]  # type: ignore[attr-defined]

from platform.blueprints.security import callset, runtime  # noqa: E402


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0243-probe2 {msg}")
    return 1


def main() -> int:
    extra: set[str] = set()
    vectors = []
    for path in runtime.discover_blueprints():
        doc = runtime.load_blueprint(path)
        extra.update(str(x) for x in (doc.get("allowed_call_set") or []))
        vectors.append((doc["id"], doc.get("capability_vector") or {}))

    rotation = callset.assert_no_rotation()
    allowed = callset.assert_allowed(extra_allowed=extra)

    mutant_rotate = "def evil():\n    rotate_secret(token)\n"
    mutant_revoke = "client.delete_secret(Name='k')\n"
    mutant_ok = "def scan():\n    return redact_value(prefix)\n"
    fires_rotate = callset.detector_fires_on_mutant(mutant_rotate)
    fires_revoke = callset.detector_fires_on_mutant(mutant_revoke)
    silent_ok = not callset.detector_fires_on_mutant(mutant_ok)

    rotate_caps = [i for i, v in vectors if v.get("rotate") or v.get("revoke") or v.get("unset")]

    summary = {
        "probe": "probe2-rotation-ast",
        "rotation_ok": rotation.get("ok"),
        "rotation_call_sites": rotation.get("rotation_call_sites"),
        "allowed_ok": allowed.get("ok"),
        "forbidden": allowed.get("forbidden"),
        "unknown": allowed.get("unknown"),
        "call_count": rotation.get("call_count"),
        "files": rotation.get("files"),
        "mutant_rotate_fires": fires_rotate,
        "mutant_revoke_fires": fires_revoke,
        "clean_helper_silent": silent_ok,
        "rotate_capability_ids": rotate_caps,
    }
    print(json.dumps(summary, sort_keys=True))
    if not rotation.get("ok"):
        return fail(f"rotation call sites present: {rotation.get('rotation_call_sites')}")
    if allowed.get("forbidden"):
        return fail(f"forbidden calls: {allowed.get('forbidden')}")
    if allowed.get("unknown"):
        return fail(f"calls outside allowed set: {allowed.get('unknown')}")
    if not fires_rotate or not fires_revoke:
        return fail("mutant rotation/revocation detector did not fire (vacuous)")
    if not silent_ok:
        return fail("detector fired on a non-rotation helper")
    if rotate_caps:
        return fail(f"capability vector allows rotation: {rotate_caps}")
    print("SUCCESS:IMP-0243-probe2 no rotation/revocation call site; allowed call set holds")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
