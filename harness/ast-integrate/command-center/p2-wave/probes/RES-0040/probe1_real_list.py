#!/usr/bin/env python3
"""Probe 1: encode THIS unit's real tool_permissions list per client.

Both-states:
  known-can  = claude-code overall can (the catalog list is Claude-shaped)
  known-cannot = codex overall cannot (no Write(path)/WebSearch tokens)
Every row must carry an explicit can/cannot verdict, not an adjective.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import encoder as E  # noqa: E402
import schema_lib as S  # noqa: E402

ART = REPO / "command-center/research/RES-0040.json"
SENTINEL = (
    "SUCCESS:RES-0040 in the receipt AND a per-client encoding attempt "
    "for one real tool_permissions list with an explicit can/cannot verdict"
)


def fail(msg: str) -> int:
    print(f"FAILED:RES-0040-probe1 {msg}")
    return 1


def main() -> int:
    real = E.load_real_list()
    print(f"real_list_n={len(real)} entries={real}")
    if "Write(command-center/research/**)" not in real:
        return fail("catalog list missing path-scoped Write")
    if not any(x.startswith("mcp__") for x in real):
        return fail("catalog list has no MCP tools")
    if "WebSearch" not in real:
        return fail("catalog list missing WebSearch")

    live = {row["client_id"]: row for row in E.encode_all(real)}
    for cid, row in live.items():
        print(
            f"live {cid} verdict={row['verdict']} "
            f"can={row['can_count']} cannot={row['cannot_count']}"
        )
        for ent in row["per_entry"]:
            if ent["verdict"] not in {"can", "cannot"}:
                return fail(f"{cid} adjective/invalid verdict {ent['verdict']!r}")
            print(f"  {ent['catalog_entry']} -> {ent['verdict']}")

    claude = live["claude-code"]
    if claude["verdict"] != "can":
        return fail("known-can: claude-code must encode the catalog list")
    write_row = next(
        e for e in claude["per_entry"] if e["catalog_entry"].startswith("Write(")
    )
    if "ENFORCED" not in (write_row.get("caveat") or ""):
        return fail("claude Write(path) missing declared-vs-enforced caveat")

    codex = live["codex"]
    if codex["verdict"] != "cannot":
        return fail("known-cannot: codex must fail lossless encode of the real list")
    write_gap = next(
        e for e in codex["per_entry"] if e["catalog_entry"].startswith("Write(")
    )
    if write_gap["verdict"] != "cannot":
        return fail("codex Write(path) must be cannot")

    cursor = live["cursor"]
    search = next(e for e in cursor["per_entry"] if e["catalog_entry"] == "WebSearch")
    if search["verdict"] != "cannot":
        return fail("cursor WebSearch must be cannot (no token)")
    mcp_ok = [
        e
        for e in cursor["per_entry"]
        if e["catalog_entry"].startswith("mcp__") and e["verdict"] == "can"
    ]
    if len(mcp_ok) < 1:
        return fail("cursor must encode at least one MCP tool as Mcp(server:tool)")

    if not ART.is_file():
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    if SENTINEL not in text:
        return fail("completion sentinel absent")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        return fail(f"self-declared {doc.get('state')}")

    art_rows = {r["client_id"]: r for r in S.domain_get(doc, "encodings_real") or []}
    if set(art_rows) != set(live):
        return fail(f"artifact clients {sorted(art_rows)} != live {sorted(live)}")
    for cid, row in live.items():
        art = art_rows[cid]
        if art.get("verdict") != row["verdict"]:
            return fail(f"artifact {cid} verdict {art.get('verdict')} != live {row['verdict']}")
        art_ents = {e["catalog_entry"]: e["verdict"] for e in art.get("per_entry") or []}
        live_ents = {e["catalog_entry"]: e["verdict"] for e in row["per_entry"]}
        if art_ents != live_ents:
            return fail(f"artifact {cid} per-entry mismatch")
        if any(v not in {"can", "cannot"} for v in art_ents.values()):
            return fail(f"artifact {cid} has non can/cannot verdict")

    listed = (S.domain_get(doc, "real_list") or {}).get("entries")
    if listed != real:
        return fail("artifact real_list does not match catalog")

    print("SUCCESS:RES-0040-probe1 real-list can/cannot both-states")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
