#!/usr/bin/env python3
"""Probe 1: enumerate install entry points and record the resolved hash vs lockfile pin."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from harness import (  # noqa: E402
    PACKAGE_ID,
    UNIT,
    capture_call,
    dest_empty,
    install_direct,
    install_from_handoff,
    marketplace_install,
    request_for,
    seed_install,
    signed_pair,
    static_inventory,
)

from plugin.payloadutil import PAYLOAD_FILES  # noqa: E402


def _row(
    *,
    target_id: str,
    entry: str,
    pin: str,
    resolved: str | None,
    installed: bool,
    empty: bool,
    warns: bool,
    raised: str | None,
    bypass: bool,
    notes: str,
) -> dict:
    matches = resolved == pin if resolved else False
    return {
        "target_id": target_id,
        "entry": entry,
        "lockfile_present": True,
        "pin": pin,
        "resolved": resolved,
        "matches_pin": matches,
        "installed": installed,
        "dest_empty": empty,
        "warns": warns,
        "raised": raised,
        "bypass": bypass,
        "notes": notes,
    }


def main() -> int:
    inventory = static_inventory()
    rows: list[dict] = []
    with tempfile.TemporaryDirectory(prefix="adv0061-p1-") as raw:
        tmp = Path(raw)
        pair = signed_pair(tmp)
        pin = pair["pin"]
        other = pair["other"]
        projection = {rel: rel for rel in PAYLOAD_FILES}

        dest_mkt = tmp / "home-mkt"
        cap = capture_call(
            marketplace_install,
            request_for(
                dest_mkt,
                tmp / "cache-mkt",
                pair["pinned"],
                pin,
                pair["signature"],
                pair["public_hex"],
                transaction_id="txn-p1-mkt",
            ),
        )
        result = cap["result"] or {}
        resolved = result.get("digest") if isinstance(result, dict) else None
        rows.append(
            _row(
                target_id="T-MKT-FILE-PATH",
                entry="tools/marketplace/install.py:marketplace_install",
                pin=pin,
                resolved=resolved,
                installed=bool(result) and result.get("ok") is True,
                empty=dest_empty(dest_mkt),
                warns=cap["warns"],
                raised=cap["raised"],
                bypass=False,
                notes="control: normal path must install exactly the pinned hash",
            )
        )

        dest_url = tmp / "home-fileurl"
        file_url = pair["pinned"].resolve().as_uri()
        cap = capture_call(
            marketplace_install,
            request_for(
                dest_url,
                tmp / "cache-fileurl",
                pair["pinned"],
                pin,
                pair["signature"],
                pair["public_hex"],
                source=file_url,
                transaction_id="txn-p1-fileurl",
            ),
        )
        result = cap["result"] or {}
        resolved = result.get("digest") if isinstance(result, dict) else None
        rows.append(
            _row(
                target_id="T-MKT-FILE-URL",
                entry="tools/marketplace/install.py:marketplace_install+file-URL",
                pin=pin,
                resolved=resolved,
                installed=bool(result) and result.get("ok") is True,
                empty=dest_empty(dest_url),
                warns=cap["warns"],
                raised=cap["raised"],
                bypass=False,
                notes="file: URL is the other documented fetch source",
            )
        )

        dest_direct = tmp / "home-direct"
        cap = capture_call(
            install_direct,
            pair["unpinned"],
            dest_direct,
            package_id=PACKAGE_ID,
            projection_map=projection,
            transaction_id="txn-p1-direct",
            digest=other,
            declared_permissions=["fs:plugin-root"],
        )
        result = cap["result"] or {}
        rows.append(
            _row(
                target_id="T-INSTALL-DIRECT-NO-LOCK",
                entry="tools/plugin/installer.py:install_direct",
                pin=pin,
                resolved=other if result else None,
                installed=bool(result),
                empty=dest_empty(dest_direct),
                warns=cap["warns"],
                raised=cap["raised"],
                bypass=bool(result) and other != pin and not cap["warns"],
                notes="placement API never reads the lockfile; unpinned blob is accepted",
            )
        )

        dest_handoff = tmp / "home-handoff"
        handoff = {
            "schema_version": 1,
            "payload_path": str(pair["unpinned"]),
            "digest": other,
            "declared_permissions": ["fs:plugin-root"],
            "projection_map": dict(projection),
            "transaction_id": "txn-p1-handoff",
            "package_id": PACKAGE_ID,
        }
        cap = capture_call(install_from_handoff, handoff, dest_handoff)
        result = cap["result"] or {}
        rows.append(
            _row(
                target_id="T-HANDOFF-NO-LOCK",
                entry="tools/plugin/installer.py:install_from_handoff",
                pin=pin,
                resolved=other if result else None,
                installed=bool(result),
                empty=dest_empty(dest_handoff),
                warns=cap["warns"],
                raised=cap["raised"],
                bypass=bool(result) and other != pin and not cap["warns"],
                notes="handoff trusts caller digest; no lockfile consult",
            )
        )

        dest_seed = tmp / "home-seed"
        cap = capture_call(seed_install, dest_seed, tmp / "blob-seed")
        result = cap["result"] or {}
        seed_digest = result.get("digest") if isinstance(result, dict) else None
        rows.append(
            _row(
                target_id="T-REPAIR-SEED-NO-LOCK",
                entry="tools/plugin/repair.py:seed_install",
                pin=pin,
                resolved=seed_digest,
                installed=bool(result),
                empty=dest_empty(dest_seed),
                warns=cap["warns"],
                raised=cap["raised"],
                bypass=bool(result) and seed_digest != pin and not cap["warns"],
                notes="repair seeder calls install_direct; lockfile is not an argument",
            )
        )

        dest_wrong = tmp / "home-wrong-source"
        cap = capture_call(
            marketplace_install,
            request_for(
                dest_wrong,
                tmp / "cache-wrong",
                pair["unpinned"],
                pin,
                pair["signature"],
                pair["public_hex"],
                lockfile={"resolver_version": "1", "packages": {"demo@1.0.0": {"digest": pin, "source": str(pair["pinned"])}}},
                transaction_id="txn-p1-wrongsrc",
            ),
        )
        result = cap["result"]
        rows.append(
            _row(
                target_id="T-MKT-WRONG-BLOB-STILL-PINNED",
                entry="tools/marketplace/install.py:marketplace_install",
                pin=pin,
                resolved=None if cap["raised"] else (result or {}).get("digest"),
                installed=bool(result),
                empty=dest_empty(dest_wrong),
                warns=cap["warns"],
                raised=cap["raised"],
                bypass=bool(result),
                notes="offering the unpinned blob against the pin must abort, not swap versions",
            )
        )

    control = next(r for r in rows if r["target_id"] == "T-MKT-FILE-PATH")
    wrong = next(r for r in rows if r["target_id"] == "T-MKT-WRONG-BLOB-STILL-PINNED")
    bypass_rows = [r for r in rows if r["bypass"]]
    names = set(inventory["install_like_names"])
    required_names = {
        "marketplace_install",
        "install_direct",
        "install_from_handoff",
        "seed_install",
        "check_lockfile_digest",
        "run_verification",
    }
    missing_names = sorted(required_names - names)
    control_ok = (
        control["installed"]
        and control["matches_pin"]
        and not control["dest_empty"]
        and not control["raised"]
    )
    pin_holds_on_wrong_blob = (
        not wrong["installed"] and wrong["dest_empty"] and wrong["raised"] is not None
    )
    payload = {
        "probe": "probe1-entrypoints",
        "unit_id": UNIT,
        "static": {
            "install_like_names": inventory["install_like_names"],
            "cli_flags": inventory["cli_flags"],
            "repair_cli_lockfile_flag": inventory["repair_cli_lockfile_flag"],
            "verify_has_fallback_word": inventory["verify_has_fallback_word"],
            "missing_required_names": missing_names,
            "lockfile_mentions": inventory["lockfile_mentions"],
        },
        "runs": rows,
        "control_pin_holds": control_ok,
        "wrong_blob_aborts": pin_holds_on_wrong_blob,
        "bypass_count": len(bypass_rows),
        "bypass_ids": [r["target_id"] for r in bypass_rows],
        "pass": bool(
            control_ok
            and pin_holds_on_wrong_blob
            and not missing_names
            and len(rows) >= 6
            and len(bypass_rows) >= 1
        ),
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    if not payload["pass"]:
        print("FAILED:ADV-0061-probe1 entrypoint matrix did not measure a live pin or a live bypass")
        return 1
    print("SUCCESS:ADV-0061-probe1 entry points executed with lockfile present")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
