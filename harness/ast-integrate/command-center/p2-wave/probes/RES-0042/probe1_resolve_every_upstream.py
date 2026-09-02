#!/usr/bin/env python3
"""Probe 1: every catalog server has a resolved (or explicitly unmapped) row.

Mechanically different from probe 2: this probe re-resolves every declared
HTTP upstream and checks the live artifact recorded redirect chains plus
final URL / HTTP status / last-release date / snapshot timestamp. It does
not consult the planted invalid URL.
"""
from __future__ import annotations

import json
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from census import catalog_mcp_servers, validate_against_schema  # noqa: E402
from mappings import OUT_REL, SENTINEL, UNIT  # noqa: E402
from resolve import is_http_url, resolve_url  # noqa: E402
from schema_local import domain  # noqa: E402

ART = REPO / OUT_REL
REQUIRED = ("final_url", "http_status", "last_release_date", "snapshot_timestamp")


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe1 {msg}")
    return 1


def main() -> int:
    catalog = catalog_mcp_servers()
    print(f"catalog_servers={len(catalog)} {catalog}")
    if len(catalog) < 10:
        return fail(f"catalog fleet too small {catalog}")

    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")
    if SENTINEL not in text:
        return fail("sentinel absent")
    errs = validate_against_schema(doc)
    if errs:
        return fail(f"schema {errs[0]}")

    body = domain(doc)
    rows = [r for r in (body.get("servers") or []) if isinstance(r, dict)]
    by_id = {r.get("server_id"): r for r in rows}
    missing = [s for s in catalog if s not in by_id]
    if missing:
        return fail(f"catalog servers omitted from registry {missing}")

    for sid, row in by_id.items():
        for key in REQUIRED:
            if row.get(key) in (None, ""):
                return fail(f"{sid} missing {key}")
        chain = row.get("redirect_chain")
        if not isinstance(chain, list):
            return fail(f"{sid} redirect_chain not a list")

    http_rows = [
        r for r in rows if is_http_url(str(r.get("declared_url") or ""))
    ]
    if not http_rows:
        return fail("no HTTP upstreams to re-resolve")

    live: dict[str, dict] = {}
    with ThreadPoolExecutor(max_workers=6) as pool:
        futs = {
            pool.submit(resolve_url, str(r["declared_url"])): str(r["server_id"])
            for r in http_rows
        }
        for fut in as_completed(futs):
            live[futs[fut]] = fut.result()

    mismatched = []
    for r in http_rows:
        sid = str(r["server_id"])
        got = live[sid]
        recorded_status = int(r.get("http_status") or 0)
        live_status = int(got.get("http_status") or 0)
        # Live re-resolve must itself record a chain (possibly empty) and a status.
        if not isinstance(got.get("redirect_chain"), list):
            mismatched.append(f"{sid}:live-chain-missing")
            continue
        if got.get("skipped") is True:
            mismatched.append(f"{sid}:live-skipped")
            continue
        if live_status == 0 and recorded_status and recorded_status < 400:
            # Transient live miss against a previously resolved URL: still require
            # the artifact row, but fail so a silent skip cannot pass.
            mismatched.append(f"{sid}:live-unresolvable recorded={recorded_status}")
            continue
        print(
            f"resolve {sid} declared={r.get('declared_url')} "
            f"recorded_status={recorded_status} live_status={live_status} "
            f"redirected={bool(got.get('redirected') or r.get('redirected'))} "
            f"hops={len(got.get('redirect_chain') or [])}"
        )

    if mismatched:
        return fail("live re-resolve " + "; ".join(mismatched[:8]))

    redirected = [r["server_id"] for r in rows if r.get("redirected")]
    print(f"redirect_recorded={redirected or 'none-this-snapshot'}")
    print(
        f"SUCCESS:{UNIT}-probe1 resolved={len(http_rows)} rows={len(rows)} "
        f"every-catalog-server-present"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
