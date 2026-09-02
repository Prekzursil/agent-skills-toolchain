#!/usr/bin/env python3
"""Probe 1: enumerate crypto-bearing components in the resolved tree.

Distinguishes bundled implementations from platform-library calls.
Control: a package that ships a signer and pulls cryptography transitively
must list that bundled component; a direct-only walk misses it.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import classify as C  # noqa: E402


def fail(msg: str) -> int:
    print(f"FAILED:ADV-0055-probe1 {msg}")
    return 1


def main() -> int:
    signer = C.load_tree("acme-signer")
    plat = C.load_tree("hashlib-packager")
    control = C.evaluate_signer_control(signer)
    plat_trans = C.walk_lockfile_transitive(plat)
    plat_bundled = C.bundled_in_closure(plat_trans)
    live = C.scan_live_tooling(REPO)

    report = {
        "probe": "probe1-enumerate-crypto",
        "unit_id": "ADV-0055",
        "mechanism": "transitive-lockfile-walk-plus-import-classification",
        "control": control,
        "platform_tree": {
            "tree_id": plat.get("id"),
            "transitive_names": plat_trans,
            "bundled": plat_bundled,
            "imports_declared": plat.get("imports"),
        },
        "live_tooling": live,
        "direct_only_is_insufficient": control.get("direct_only_misses_transitive"),
    }
    print(json.dumps(report, sort_keys=True, default=str))

    if not signer.get("ships_signer"):
        return fail("acme-signer fixture must ships_signer=true")
    if not control.get("bundled_transitive"):
        return fail(
            "empty bundled enumeration on a package that ships a signer; "
            "traversal missed transitive cryptography"
        )
    names = {C._norm_name(x["name"]) for x in control["bundled_transitive"]}
    if "cryptography" not in names:
        return fail(f"known bundled crypto cryptography missing: {sorted(names)}")
    if not control.get("direct_only_misses_transitive"):
        return fail("direct-only walk also found bundled crypto; transitivity not shown")
    if plat_bundled:
        return fail(f"hashlib-packager classified as bundled: {plat_bundled}")
    if live.get("bundled_import_count", 0) != 0:
        return fail(
            "live signing/packaging tooling imported bundled crypto unexpectedly: "
            f"{live.get('bundled_modules')}"
        )
    if "hashlib" not in (live.get("platform_modules") or []):
        return fail("live tooling hashlib import not observed; scan too narrow")
    if control.get("empty_on_signer_means_missed_transitives"):
        return fail("control marked empty-on-signer")

    print(
        "control cryptography via packaging-core "
        f"bundled={names} direct_only_miss={control['direct_only_misses_transitive']}"
    )
    print(
        "live bundled_imports="
        f"{live['bundled_import_count']} platform_modules={live['platform_modules']}"
    )
    print("SUCCESS:ADV-0055-probe1 enumerate-crypto bundled-vs-platform")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
