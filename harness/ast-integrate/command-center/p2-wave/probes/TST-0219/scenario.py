#!/usr/bin/env python3
"""Live both-states + negative-control scenarios for TST-0219."""
from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

import resolver as R


def _run_in(tmp: Path, label: str, fn) -> dict[str, Any]:
    dest = tmp / label
    dest.mkdir(parents=True, exist_ok=True)
    result = fn(dest)
    live_census = R.census(dest)
    live_tree = R.tree_hash(dest)
    row = result.as_dict()
    row["live_census"] = live_census
    row["live_tree_hash"] = live_tree
    row["public_bytes_present"] = R.sha256_hex(R.PUBLIC_PAYLOAD) in live_census.values()
    row["private_bytes_present"] = R.sha256_hex(R.PRIVATE_PAYLOAD) in live_census.values()
    return row


def evaluate() -> dict[str, Any]:
    world = R.make_world()
    pkg = world["package"]
    regs = world["registries"]
    pinned = world["pinned_lock"]
    unpinned = world["unpinned_lock"]
    origin_only = world["origin_only_lock"]

    with tempfile.TemporaryDirectory(prefix="tst0219-") as td:
        tmp = Path(td)
        private_ok = _run_in(
            tmp,
            "private-pin",
            lambda dest: R.resolve_install(pinned, pkg, regs, dest),
        )
        public_offer = _run_in(
            tmp,
            "public-offer",
            lambda dest: R.resolve_install(
                pinned, pkg, regs, dest, offered_origin=R.PUBLIC_ORIGIN
            ),
        )
        unpinned_fail = _run_in(
            tmp,
            "unpinned",
            lambda dest: R.resolve_install(unpinned, pkg, regs, dest),
        )
        integrity_missing = _run_in(
            tmp,
            "origin-only",
            lambda dest: R.resolve_install(origin_only, pkg, regs, dest),
        )
        mutant = _run_in(
            tmp,
            "confused-mutant",
            lambda dest: R.confused_install(unpinned, pkg, regs, dest),
        )

    fails: list[str] = []
    if not private_ok["ok"] or private_ok["code"] != R.CODE_OK:
        fails.append(f"private-pin did not resolve: {private_ok['code']}")
    if private_ok["origin_used"] != R.PRIVATE_ORIGIN:
        fails.append(f"private origin_used={private_ok['origin_used']}")
    if not private_ok["private_bytes_present"]:
        fails.append("private install missing private payload bytes")
    if private_ok["public_bytes_present"]:
        fails.append("private install contained public payload bytes")

    if public_offer["ok"]:
        fails.append("public offer was accepted")
    if public_offer["code"] != R.CODE_DEPENDENCY_CONFUSION:
        fails.append(f"public offer code={public_offer['code']}")
    msg = public_offer["message"]
    for needle in (
        R.CODE_DEPENDENCY_CONFUSION,
        pkg,
        R.PUBLIC_ORIGIN,
        R.PRIVATE_ORIGIN,
    ):
        if needle not in msg:
            fails.append(f"refusal message missing {needle!r}")
    if public_offer["wrote_any"] or public_offer["public_bytes_present"]:
        fails.append("public offer wrote public bytes")
    if public_offer["live_tree_hash"] != world["empty_tree_hash"]:
        fails.append("public-offer dest tree is not empty")

    if unpinned_fail["ok"]:
        fails.append("unpinned lockfile resolved (negative control failed)")
    if unpinned_fail["code"] != R.CODE_ORIGIN_PIN_MISSING:
        fails.append(f"unpinned code={unpinned_fail['code']}")
    if R.CODE_ORIGIN_PIN_MISSING not in unpinned_fail["message"]:
        fails.append("unpinned message does not name ORIGIN_PIN_MISSING")
    if unpinned_fail["public_bytes_present"] or unpinned_fail["wrote_any"]:
        fails.append("unpinned lockfile wrote bytes")

    if integrity_missing["ok"] or integrity_missing["code"] != R.CODE_INTEGRITY_PIN_MISSING:
        fails.append(f"origin-only lock code={integrity_missing['code']}")

    if not mutant["ok"]:
        fails.append("confused mutant did not install (detector vacuous)")
    if mutant["origin_used"] != R.PUBLIC_ORIGIN:
        fails.append(f"mutant origin_used={mutant['origin_used']}")
    if not mutant["public_bytes_present"]:
        fails.append("mutant did not place public payload (detector vacuous)")
    if mutant["live_tree_hash"] == private_ok["live_tree_hash"]:
        fails.append("mutant tree hash equals private tree (payloads not distinct)")
    if world["public_sha256"] == world["private_sha256"]:
        fails.append("public and private payloads share a hash")

    both_states = private_ok["ok"] and (not public_offer["ok"])
    negative = (not unpinned_fail["ok"]) and unpinned_fail["code"] == R.CODE_ORIGIN_PIN_MISSING

    return {
        "unit_id": "TST-0219",
        "package": pkg,
        "private_origin": R.PRIVATE_ORIGIN,
        "public_origin": R.PUBLIC_ORIGIN,
        "private_sha256": world["private_sha256"],
        "public_sha256": world["public_sha256"],
        "private_integrity": world["private_integrity"],
        "public_integrity": world["public_integrity"],
        "empty_tree_hash": world["empty_tree_hash"],
        "pinned_lock": pinned,
        "unpinned_lock": unpinned,
        "private_ok": private_ok,
        "public_offer": public_offer,
        "unpinned_fail": unpinned_fail,
        "integrity_missing": integrity_missing,
        "confused_mutant": mutant,
        "both_states": both_states,
        "negative_control": negative,
        "detector_mutant_installs_public": bool(mutant["public_bytes_present"]),
        "fails": fails,
        "pass": not fails,
    }
