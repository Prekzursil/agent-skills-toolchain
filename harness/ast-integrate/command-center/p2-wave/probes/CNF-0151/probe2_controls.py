#!/usr/bin/env python3
"""Probe 2: image pin, no-host-mount both-states, stale-CI-summary, second digest.

Mechanically independent of probe 1's table construction: this probe plants the
host cache, runs a clean chroot and a bind-mounted chroot, rejects floating
tags, and re-reads two instance digests of the windows-specific row.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from container import is_floating_ref, pinned_ref  # noqa: E402
from matrix import dump, isolation_both_states, second_digest_review  # noqa: E402

OUT = HERE / "probe2-controls.raw.json"


def main() -> int:
    iso = isolation_both_states(nonce="probe2")
    rev = second_digest_review(nonce="probe2")
    floating = [
        "python:latest",
        "ubuntu:24.04",
        "cnf0151-python3.12-chroot:latest",
        "python",
        "",
    ]
    pinned = [pinned_ref()]
    floating_caught = all(is_floating_ref(r) for r in floating)
    pinned_ok = all(not is_floating_ref(r) for r in pinned)
    doc = {
        "isolation": iso,
        "second_digest": rev,
        "floating_caught": floating_caught,
        "pinned_ok": pinned_ok,
        "floating_examples": floating,
        "pinned_ref": pinned[0],
        "pass": bool(iso["pass"] and rev["pass"] and floating_caught and pinned_ok),
    }
    dump(OUT, doc)
    if not iso["pass"]:
        print("FAILED:CNF-0151-probe2 host-cache isolation both-states")
        print(json.dumps(iso, sort_keys=True))
        return 1
    if not rev["pass"]:
        print("FAILED:CNF-0151-probe2 second container digest review")
        print(json.dumps(rev, sort_keys=True))
        return 1
    if not floating_caught or not pinned_ok:
        print("FAILED:CNF-0151-probe2 image pin detector")
        return 1
    print(
        "clean_sees_cache="
        + str(iso["clean_sees_host_cache"])
        + " mounted_sees_cache="
        + str(iso["mounted_sees_host_cache"])
        + " clean_shim="
        + str(iso["clean_resolves_shim"])
        + " mounted_shim="
        + str(iso["mounted_resolves_shim"])
        + " digest_a="
        + rev["digest_a"][:12]
        + " digest_b="
        + rev["digest_b"][:12]
        + " instances_differ="
        + str(rev["instances_differ"])
        + " floating_caught="
        + str(floating_caught)
    )
    print("SUCCESS:CNF-0151-probe2 pin, no-host-mount both-states, second digest")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
