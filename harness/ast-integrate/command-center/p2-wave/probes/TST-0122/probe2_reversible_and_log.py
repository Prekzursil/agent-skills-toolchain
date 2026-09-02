#!/usr/bin/env python3
"""Named probe 2: reversibility, clock-jump log integrity, safety rails.

Independent of probe 1: re-runs inject/revert and the append-only log campaign
on a fresh scratch session. Also checks seed determinism and that network
primitives are delegated, not shipped.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))

from chaos.network import NETWORK_IDS, inject_network  # noqa: E402
from chaos.safety import DelegatedFaultError  # noqa: E402
from chaos.seed import derive_params  # noqa: E402
from chaos.session import (  # noqa: E402
    FaultSession,
    clock_jump_back_does_not_corrupt_log,
    refuse_foreign_pid,
    refuse_live_path,
    run_reversibility,
)

UNIT = "TST-0122"
ART = REPO / "command-center" / "receipts" / "TST-0122.json"
SCHEMA = REPO / "command-center" / "schema" / "fault-injection-receipt.schema.json"
SEED = 122


def fail(msg: str) -> int:
    print(f"FAILED:TST-0122-probe2 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("receipt missing")
    receipt = json.loads(ART.read_text(encoding="utf-8"))
    if "SUCCESS:TST-0122" not in json.dumps(receipt):
        return fail("sentinel absent")
    if str(receipt.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        return fail(f"self-declared {receipt.get('state')}")

    try:
        import jsonschema
    except ImportError:
        return fail("jsonschema not installed")
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    errors = sorted(jsonschema.Draft7Validator(schema).iter_errors(receipt), key=lambda e: list(e.path))
    if errors:
        return fail(f"schema {errors[0].message}")
    garbage_ok = list(jsonschema.Draft7Validator(schema).iter_errors({}))
    if not garbage_ok:
        return fail("schema accepts empty object")

    rev = run_reversibility(SEED)
    if not rev["all_restored"]:
        return fail(f"not reversible {rev['results']}")

    with FaultSession(SEED) as session:
        log = clock_jump_back_does_not_corrupt_log(session)
        live_refused = refuse_live_path(session, Path("/etc/passwd"))
        session.procs.spawn()
        pid_refused = refuse_foreign_pid(session, os.getpid())
    if not log["pass"]:
        return fail(f"append-only log corrupted or naive control silent {log}")
    if not live_refused:
        return fail("live path was not refused")
    if not pid_refused:
        return fail("foreign pid was not refused")

    if derive_params(SEED) != derive_params(SEED):
        return fail("same seed produced different params")
    if derive_params(SEED)["jump_forward_s"] == derive_params(SEED + 1)["jump_forward_s"]:
        return fail("seed is unused (jump_forward_s identical across seeds)")

    for nid in NETWORK_IDS:
        try:
            inject_network(nid)
        except DelegatedFaultError:
            continue
        return fail(f"{nid} was not delegated")

    owner_md = REPO / "command-center" / "OWNER-DECISIONS.md"
    if owner_md.is_file() and "TST-0122" in owner_md.read_text(encoding="utf-8"):
        owner_note = "OWNER-DECISIONS.md mentions TST-0122"
    else:
        owner_note = (
            "OWNER-DECISIONS.md has no TST-0122 sign-off; not forged. "
            "G-1 delivers a scratch-only library; catalog close still wants owner sign-off."
        )

    payload = {
        "all_restored": True,
        "garbage_rejected": True,
        "log_pass": True,
        "naive_control_fired": True,
        "network_delegated": True,
        "owner_note": owner_note,
        "pass": True,
        "probe": "probe2-reversible-and-log",
        "schema_ok": True,
        "seed_used": True,
        "unit_id": UNIT,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        "SUCCESS:TST-0122-probe2 reversible; clock jump back left the append-only "
        "log parseable with seq/hash intact"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
