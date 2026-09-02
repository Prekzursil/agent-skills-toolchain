#!/usr/bin/env python3
"""Probe 2: planted extra keys (and native unmapped keys) land in the lossy register.

Mechanically different from probe 1 (lossless value preservation). Both-states:
the same descriptor with planted keys removed must NOT list those keys.
Locators must cite a real file:line that contains the source key.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import scenario as S  # noqa: E402
from tools.router import normalize as N  # noqa: E402

ART = S.REPO / S.ART_REL


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0386-probe2 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact-missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if S.SENTINEL not in json.dumps(doc):
        return fail("sentinel-absent")
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared:{st}")

    live = S.live_results()
    art_rows = {
        row.get("source_format"): row
        for row in (doc.get("lossy_field_register") or [])
        if isinstance(row, dict)
    }
    if len(art_rows) < 4:
        return fail(f"artifact register rows {len(art_rows)} want>=4")

    for result in live:
        fmt = result.parsed.source_format
        planted = N.PLANTED_KEYS[fmt]
        errors = N.planted_errors(result.parsed, result, planted)
        if errors:
            return fail("; ".join(errors))

        live_dropped = {row["source_key"]: row for row in result.dropped}
        if planted not in live_dropped:
            return fail(f"{fmt} planted key missing live")
        ok, detail = S.locator_points_at_key(live_dropped[planted]["locator"], planted)
        if not ok:
            return fail(f"{fmt} planted locator {detail}")

        for native in N.NATIVE_DROPS[fmt]:
            if native not in result.parsed.mapping:
                return fail(f"{fmt} fixture missing native drop {native}")
            if native not in live_dropped:
                return fail(f"{fmt} native drop {native} not in register")
            n_ok, n_detail = S.locator_points_at_key(
                live_dropped[native]["locator"], native
            )
            if not n_ok:
                return fail(f"{fmt} native {native} locator {n_detail}")

        clean = copy.deepcopy(result.parsed)
        del clean.mapping[planted]
        clean.locators.pop(planted, None)
        clean_result = N.normalize_parsed(clean)
        clean_keys = {row["source_key"] for row in clean_result.dropped}
        if planted in clean_keys:
            return fail(f"{fmt} planted key survived after removal")
        if N.planted_errors(result.parsed, result, planted):
            return fail(f"{fmt} planted detector silent on dirty state")

        art_row = art_rows.get(fmt)
        if not art_row:
            return fail(f"artifact missing register row {fmt}")
        art_keys = {
            d.get("source_key")
            for d in (art_row.get("dropped_keys") or [])
            if isinstance(d, dict)
        }
        if planted not in art_keys:
            return fail(f"artifact omitted planted {planted}")
        for native in N.NATIVE_DROPS[fmt]:
            if native not in art_keys:
                return fail(f"artifact omitted native {native}")

        print(
            f"lossy format={fmt} planted={planted} "
            f"native={list(N.NATIVE_DROPS[fmt])} "
            f"clean_absent=True locator={live_dropped[planted]['locator']}"
        )

    finding = doc.get("finding") or {}
    if finding.get("headline_format") != N.FORMAT_MCP_TOOL:
        return fail("finding headline_format is not mcp_tool")
    if finding.get("headline_field") != "inputSchema":
        return fail("finding headline_field is not inputSchema")
    lost = finding.get("formats_that_lose_information") or []
    if set(lost) != set(S.FIXTURE_RELS):
        return fail(f"finding formats {lost}")

    payload = {
        "formats": 4,
        "pass": True,
        "planted_both_states": True,
        "probe": "probe2-lossy-register",
        "unit_id": "IMP-0386",
    }
    print(json.dumps(payload, sort_keys=True))
    print("SUCCESS:IMP-0386-probe2 planted extras and native drops in lossy register")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
