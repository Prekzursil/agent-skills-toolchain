#!/usr/bin/env python3
"""Probe 2: induce lockfile recovery branches; planted fallback must go red."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from harness import (  # noqa: E402
    PACKAGE_ID,
    PACKAGE_REF,
    UNIT,
    capture_call,
    dest_empty,
    fetch_to_cache,
    marketplace_install,
    planted_unpinned_fallback,
    request_for,
    run_verification,
    seed_install,
    signed_pair,
)

from marketplace.verify import blob_digest  # noqa: E402
from plugin.repair import repair_install  # noqa: E402


def _branch(
    *,
    target_id: str,
    kind: str,
    pin: str,
    installed: bool,
    empty: bool,
    raised: str | None,
    gate: str | None,
    fell_back: bool,
    notes: str,
) -> dict:
    return {
        "target_id": target_id,
        "kind": kind,
        "pin": pin,
        "installed": installed,
        "dest_empty": empty,
        "raised": raised,
        "gate": gate,
        "fell_back_unpinned": fell_back,
        "notes": notes,
    }


def main() -> int:
    branches: list[dict] = []
    with tempfile.TemporaryDirectory(prefix="adv0061-p2-") as raw:
        tmp = Path(raw)
        pair = signed_pair(tmp)
        pin = pair["pin"]
        other = pair["other"]

        dest_mismatch = tmp / "home-mismatch"
        cap = capture_call(
            marketplace_install,
            request_for(
                dest_mismatch,
                tmp / "cache-mismatch",
                pair["pinned"],
                pin,
                pair["signature"],
                pair["public_hex"],
                lockfile={
                    "resolver_version": "1",
                    "packages": {
                        PACKAGE_REF: {
                            "digest": other,
                            "source": str(pair["pinned"]),
                        }
                    },
                },
                transaction_id="txn-p2-mismatch",
            ),
        )
        branches.append(
            _branch(
                target_id="T-INTEGRITY-MISMATCH-NO-FALLBACK",
                kind="integrity-mismatch",
                pin=pin,
                installed=bool(cap["result"]),
                empty=dest_empty(dest_mismatch),
                raised=cap["raised"],
                gate=cap["gate"],
                fell_back=bool(cap["result"]),
                notes="resolver must fail closed, not recover to an unpinned blob",
            )
        )

        dest_cache = tmp / "home-corrupt-cache"
        cached = fetch_to_cache(pair["pinned"], tmp / "cache-corrupt")
        cached.write_bytes(cached.read_bytes() + b"\x00CORRUPT")
        req = request_for(
            dest_cache,
            tmp / "cache-corrupt",
            pair["pinned"],
            pin,
            pair["signature"],
            pair["public_hex"],
            transaction_id="txn-p2-corrupt",
        )
        cap = capture_call(
            run_verification,
            cached,
            package_ref=PACKAGE_REF,
            lockfile=req.lockfile,
            signature=req.signature,
            trust_store=req.trust_store,
            revocation=req.revocation,
            compatibility=req.compatibility,
            platform="linux",
            client_version="1.0.0",
        )
        branches.append(
            _branch(
                target_id="T-CORRUPT-CACHE-NO-FALLBACK",
                kind="corrupt-cache",
                pin=pin,
                installed=bool(cap["result"]),
                empty=dest_empty(dest_cache),
                raised=cap["raised"],
                gate=cap["gate"],
                fell_back=bool(cap["result"]),
                notes="mutating the digest-named cache blob must not yield an unpinned install",
            )
        )

        dest_missing = tmp / "home-missing-src"
        cap = capture_call(
            marketplace_install,
            request_for(
                dest_missing,
                tmp / "cache-missing",
                tmp / "does-not-exist.tar.gz",
                pin,
                pair["signature"],
                pair["public_hex"],
                transaction_id="txn-p2-missing",
            ),
        )
        branches.append(
            _branch(
                target_id="T-UNREACHABLE-SOURCE-NO-FALLBACK",
                kind="unreachable-source",
                pin=pin,
                installed=bool(cap["result"]),
                empty=dest_empty(dest_missing),
                raised=cap["raised"],
                gate=cap["gate"],
                fell_back=bool(cap["result"]),
                notes="missing file source is the live unreachable-registry stand-in (fetch has no HTTP client)",
            )
        )

        dest_http = tmp / "home-http"
        cap = capture_call(
            marketplace_install,
            request_for(
                dest_http,
                tmp / "cache-http",
                pair["pinned"],
                pin,
                pair["signature"],
                pair["public_hex"],
                source="http://127.0.0.1:1/adv0061/demo.tar.gz",
                transaction_id="txn-p2-http",
            ),
        )
        branches.append(
            _branch(
                target_id="T-HTTP-REGISTRY-NO-FALLBACK",
                kind="http-source",
                pin=pin,
                installed=bool(cap["result"]),
                empty=dest_empty(dest_http),
                raised=cap["raised"],
                gate=cap["gate"],
                fell_back=bool(cap["result"]),
                notes="HTTP source is unsupported; must not fall back to an unpinned local blob",
            )
        )

        dest_nolock = tmp / "home-nolock"
        cap = capture_call(
            marketplace_install,
            request_for(
                dest_nolock,
                tmp / "cache-nolock",
                pair["pinned"],
                pin,
                pair["signature"],
                pair["public_hex"],
                lockfile={"resolver_version": "1"},
                transaction_id="txn-p2-nolock",
            ),
        )
        branches.append(
            _branch(
                target_id="T-MISSING-LOCKFILE-PACKAGES-NO-FALLBACK",
                kind="missing-lockfile",
                pin=pin,
                installed=bool(cap["result"]),
                empty=dest_empty(dest_nolock),
                raised=cap["raised"],
                gate=cap["gate"],
                fell_back=bool(cap["result"]),
                notes="absent packages object is fail-closed, not treated as unpinned allow",
            )
        )

        dest_force = tmp / "home-no-force-flag"
        req = request_for(
            dest_force,
            tmp / "cache-force",
            pair["unpinned"],
            pin,
            pair["signature"],
            pair["public_hex"],
            transaction_id="txn-p2-noforce",
        )
        cap = capture_call(marketplace_install, req)
        branches.append(
            _branch(
                target_id="T-NO-SKIP-LOCK-FLAG",
                kind="no-skip-lock-flag",
                pin=pin,
                installed=bool(cap["result"]),
                empty=dest_empty(dest_force),
                raised=cap["raised"],
                gate=cap["gate"],
                fell_back=bool(cap["result"]),
                notes="InstallRequest has no skip-lock / --force field; unpinned source still aborts",
            )
        )

        dest_plant = tmp / "home-planted"
        mismatch_req = request_for(
            dest_plant,
            tmp / "cache-planted",
            pair["pinned"],
            pin,
            pair["signature"],
            pair["public_hex"],
            lockfile={
                "resolver_version": "1",
                "packages": {
                    PACKAGE_REF: {"digest": other, "source": str(pair["pinned"])}
                },
            },
            transaction_id="txn-p2-planted-req",
        )
        planted = planted_unpinned_fallback(
            mismatch_req, pair["unpinned"], dest_plant, other
        )
        planted_installed = planted.get("mode") == "unpinned-fallback" and not dest_empty(
            dest_plant
        )
        planted_row = {
            "target_id": "T-PLANTED-FALLBACK-GOES-RED",
            "kind": "negative-control",
            "pin": pin,
            "other": other,
            "mode": planted.get("mode"),
            "installed_unpinned": planted_installed,
            "dest_empty": dest_empty(dest_plant),
            "fired_on_bad_state": planted_installed,
            "notes": "planted recovery must install the unpinned blob so the detector is not vacuous",
        }

        dest_repair = tmp / "home-repair"
        seed = capture_call(seed_install, dest_repair, tmp / "blob-repair")
        seed_ok = bool(seed["result"])
        if seed_ok:
            live = dest_repair / "plugins" / PACKAGE_ID
            skill = live / "skills" / "hello" / "SKILL.md"
            skill.write_bytes(b"mutated-after-pin\n")
        repaired = capture_call(repair_install, dest_repair, PACKAGE_ID)
        repair_ok = bool(repaired["result"]) and repaired["result"].get("ok") is True
        branches.append(
            _branch(
                target_id="T-REPAIR-SKIPS-LOCKFILE",
                kind="repair-path",
                pin=pin,
                installed=repair_ok,
                empty=dest_empty(dest_repair),
                raised=repaired["raised"],
                gate=repaired["gate"],
                fell_back=repair_ok and seed["result"].get("digest") != pin,
                notes="repair_install restores from sidecar digest, not from the lockfile pin",
            )
        )

        control_dest = tmp / "home-control"
        control = capture_call(
            marketplace_install,
            request_for(
                control_dest,
                tmp / "cache-control",
                pair["pinned"],
                pin,
                pair["signature"],
                pair["public_hex"],
                transaction_id="txn-p2-control",
            ),
        )
        control_digest = (control["result"] or {}).get("digest")
        control_ok = (
            control_digest == pin
            and not dest_empty(control_dest)
            and control["raised"] is None
        )

        actual_after_corrupt = blob_digest(cached)

    closed_ids = [
        b["target_id"]
        for b in branches
        if not b["fell_back_unpinned"] and b["dest_empty"] and b["raised"]
    ]
    expected_closed = {
        "T-INTEGRITY-MISMATCH-NO-FALLBACK",
        "T-CORRUPT-CACHE-NO-FALLBACK",
        "T-UNREACHABLE-SOURCE-NO-FALLBACK",
        "T-HTTP-REGISTRY-NO-FALLBACK",
        "T-MISSING-LOCKFILE-PACKAGES-NO-FALLBACK",
        "T-NO-SKIP-LOCK-FLAG",
    }
    missing_closed = sorted(expected_closed - set(closed_ids))
    payload = {
        "probe": "probe2-failure-branches",
        "unit_id": UNIT,
        "branches": branches,
        "planted": planted_row,
        "control_pin_holds": control_ok,
        "control_digest": control_digest,
        "corrupt_blob_digest": actual_after_corrupt,
        "closed_ids": closed_ids,
        "missing_closed": missing_closed,
        "repair_restored_without_lockfile": bool(
            next(b for b in branches if b["target_id"] == "T-REPAIR-SKIPS-LOCKFILE")[
                "installed"
            ]
        ),
        "negative_control_fired": bool(planted_row["fired_on_bad_state"]),
        "pass": bool(
            control_ok
            and not missing_closed
            and planted_row["fired_on_bad_state"]
            and actual_after_corrupt != pin
        ),
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    if not payload["pass"]:
        print("FAILED:ADV-0061-probe2 failure branches did not fail closed or planted control was silent")
        return 1
    print("SUCCESS:ADV-0061-probe2 failure branches fail closed; planted fallback goes red")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
