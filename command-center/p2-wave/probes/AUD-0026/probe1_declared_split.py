#!/usr/bin/env python3
"""AUD-0026 NAMED PROBE 1: declared prod/dev dependency split in manifests."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from split_lib import (
    discover_manifests,
    is_other_probe_scratch,
    is_our_fixture,
    parse_manifest,
    rel,
)

PROBE = Path(__file__).resolve().parent
OUT_JSON = PROBE / "probe1-declared-split.json"
OUT_RAW = PROBE / "probe1-declared-split.raw.txt"

CATALOG_VERBATIM = "Probe 1: the declared prod/dev split in the manifests."


def main() -> int:
    rows = []
    for path in discover_manifests():
        rpath = rel(path)
        if is_other_probe_scratch(rpath):
            continue
        rec = parse_manifest(path)
        if rec is None:
            continue
        rec["planted_fixture"] = is_our_fixture(rpath)
        rec["in_other_unit_probe_scratch"] = False
        # drop bulky packages_cfg from summary rows but keep presence
        if "packages_cfg" in rec:
            rec["has_packages_cfg"] = rec["packages_cfg"] is not None
            del rec["packages_cfg"]
        rows.append(rec)

    live = [r for r in rows if not r.get("planted_fixture")]
    planted = [r for r in rows if r.get("planted_fixture")]

    def tally(rs: list[dict]) -> dict:
        prod_n = sum(len(r.get("prod") or []) for r in rs if not r.get("error"))
        dev_n = sum(len(r.get("dev") or []) for r in rs if not r.get("error"))
        dev_only_n = sum(len(r.get("dev_only") or []) for r in rs if not r.get("error"))
        with_split = sum(
            1
            for r in rs
            if not r.get("error") and (r.get("prod") or r.get("dev"))
        )
        with_dev_only = sum(1 for r in rs if not r.get("error") and r.get("dev_only"))
        return {
            "manifests": len(rs),
            "prod_declaration_count": prod_n,
            "dev_declaration_count": dev_n,
            "dev_only_declaration_count": dev_only_n,
            "manifests_with_any_deps": with_split,
            "manifests_with_dev_only": with_dev_only,
        }

    live_t = tally(live)
    plant_t = tally(planted)

    # Fixture must show the expected declared split for both ecosystems.
    py_plant = next(
        (
            r
            for r in planted
            if r.get("ecosystem") == "pip" and "planted-shipped-imports-dev" in r["manifest"]
        ),
        None,
    )
    node_plant = next(
        (
            r
            for r in planted
            if r.get("ecosystem") == "npm"
            and "planted-node-shipped-imports-dev" in r["manifest"]
        ),
        None,
    )
    planted_split_ok = bool(
        py_plant
        and "pytest" in (py_plant.get("dev_only") or [])
        and "requests" in (py_plant.get("prod_only") or [])
        and node_plant
        and "typescript" in (node_plant.get("dev_only") or [])
        and "zod" in (node_plant.get("prod_only") or [])
    )

    payload = {
        "unit": "AUD-0026",
        "catalog_verbatim": CATALOG_VERBATIM,
        "live": live_t,
        "planted": plant_t,
        "live_manifests": live,
        "planted_manifests": planted,
        "planted_split_ok": planted_split_ok,
        "ok": planted_split_ok,
        # headline aliases
        "packages_scanned": live_t["manifests"],
        "prod_declaration_count": live_t["prod_declaration_count"],
        "dev_declaration_count": live_t["dev_declaration_count"],
        "dev_only_declaration_count": live_t["dev_only_declaration_count"],
    }
    OUT_JSON.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    lines = [
        "AUD-0026 NAMED PROBE 1: declared prod/dev dependency split",
        f"catalog_verbatim={CATALOG_VERBATIM}",
        "unit=AUD-0026",
        f"live_manifests={live_t['manifests']}",
        f"live_prod_declarations={live_t['prod_declaration_count']}",
        f"live_dev_declarations={live_t['dev_declaration_count']}",
        f"live_dev_only_declarations={live_t['dev_only_declaration_count']}",
        f"live_manifests_with_dev_only={live_t['manifests_with_dev_only']}",
        f"planted_manifests={plant_t['manifests']}",
        f"planted_split_ok={planted_split_ok}",
        "PLANTED-SPLIT-BEGIN",
    ]
    for r in planted:
        lines.append(
            f"PLANTED\t{r.get('ecosystem')}\t{r.get('manifest')}\t"
            f"prod={','.join(r.get('prod') or [])}\t"
            f"dev_only={','.join(r.get('dev_only') or [])}"
        )
    lines.append("PLANTED-SPLIT-END")
    lines.append("LIVE-DEV-ONLY-BEGIN")
    for r in live:
        if not r.get("dev_only"):
            continue
        lines.append(
            f"LIVE\t{r.get('ecosystem')}\t{r.get('manifest')}\t"
            f"dev_only_count={len(r['dev_only'])}\t"
            f"dev_only={','.join(r['dev_only'][:12])}"
        )
    lines.append("LIVE-DEV-ONLY-END")
    lines.append(
        "SUCCESS:AUD-0026-probe1" if planted_split_ok else "FAIL:AUD-0026-probe1"
    )
    raw = "\n".join(lines) + "\n"
    OUT_RAW.write_text(raw, encoding="utf-8")
    sys.stdout.write(raw)
    return 0 if planted_split_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
