#!/usr/bin/env python3
"""Probe 2: system commit charge and pagefile/swap, not RAM-percent.

Catalog evidence: RAM alone hides the commit-exhaustion freeze. This probe
reads Committed_AS/CommitLimit and SwapTotal (Linux pagefile analogue) via a
different instrument than probe 1's per-process RSS.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "tools"))
import census as C  # noqa: E402

from headroom_guard.commit_charge import (  # noqa: E402
    COMMIT_CHARGE_KEY,
    COMMIT_LIMIT_KEY,
    PAGEFILE_KEY,
    read_live,
)

ART = REPO / "command-center/audit/AUD-0061-mcp-process-multiplication.json"
SENTINEL = (
    "SUCCESS:AUD-0061 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and both named probes are "
    "recorded with their verbatim output"
)


def fail(msg: str) -> int:
    print(f"FAILED:AUD-0061-probe2 {msg}")
    return 1


def main() -> int:
    snap = read_live()
    d = snap.as_dict()
    if COMMIT_CHARGE_KEY not in d["fields_read"] or COMMIT_LIMIT_KEY not in d["fields_read"]:
        return fail(f"did not read commit-charge keys {d['fields_read']}")
    if PAGEFILE_KEY not in d["fields_read"]:
        return fail(f"did not read pagefile/swap key {d['fields_read']}")
    if d["committed_bytes"] <= 0 or d["commit_limit_bytes"] <= 0:
        return fail(f"commit counters not live {d}")
    if d["source"] != "proc-meminfo":
        return fail(f"source={d['source']}")
    # RAM-percent is a different instrument. Equality would be a coincidence;
    # missing RAM fields would mean we cannot prove the control exists.
    if d["ram_total_bytes"] <= 0:
        return fail("ram_total missing; control comparator absent")
    if d["committed_bytes"] == d["ram_used_bytes"] and d["commit_limit_bytes"] == d["ram_total_bytes"]:
        return fail("commit-charge collapsed onto RAM-percent fields")

    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if SENTINEL not in text:
        return fail("sentinel-absent")
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared:{doc.get('state')}")

    report = doc.get("report") or {}
    commit = report.get("commit_charge") or {}
    ram = report.get("ram_control") or {}
    if commit.get("fields_read") is None:
        return fail("artifact missing commit_charge.fields_read")
    fields = [str(x) for x in commit.get("fields_read") or []]
    if COMMIT_CHARGE_KEY not in fields or COMMIT_LIMIT_KEY not in fields:
        return fail("artifact commit_charge did not name Committed_AS/CommitLimit")
    if PAGEFILE_KEY not in fields:
        return fail("artifact did not record SwapTotal/pagefile")
    if ram.get("used_as_headline_cost") is True:
        return fail("artifact treated RAM-percent as the headline cost")
    if "rss" in json.dumps(commit).lower() and COMMIT_CHARGE_KEY not in fields:
        return fail("commit_charge looks like working-set")

    named = C.artifact_named_probes(doc)
    if len(named) < 2:
        return fail("named_probes missing")
    raw2 = " ".join(str(p.get("raw_output") or "") for p in named)
    if COMMIT_CHARGE_KEY not in raw2 or "pagefile" not in raw2.lower() and PAGEFILE_KEY not in raw2:
        if COMMIT_CHARGE_KEY not in raw2:
            return fail("probe2 verbatim output missing Committed_AS")

    headline = report.get("headline") or {}
    if headline.get("commit_counter") not in {"Committed_AS/CommitLimit", COMMIT_CHARGE_KEY + "/" + COMMIT_LIMIT_KEY}:
        return fail(f"headline commit_counter={headline.get('commit_counter')}")

    out = {
        "probe": "probe2-commit-charge-pagefile",
        "unit_id": "AUD-0061",
        "pass": True,
        "committed_bytes": d["committed_bytes"],
        "commit_limit_bytes": d["commit_limit_bytes"],
        "commit_ratio": d["commit_ratio"],
        "pagefile_bytes": d["pagefile_bytes"],
        "ram_percent": d["ram_percent"],
        "ram_used_bytes": d["ram_used_bytes"],
        "fields_read": d["fields_read"],
        "host": d["host"],
        "instruments_differ": d["committed_bytes"] != d["ram_used_bytes"],
    }
    print(json.dumps(out, sort_keys=True))
    print(
        f"Committed_AS={d['committed_bytes']} CommitLimit={d['commit_limit_bytes']} "
        f"SwapTotal/pagefile={d['pagefile_bytes']} ram_percent={d['ram_percent']}"
    )
    print("SUCCESS:AUD-0061-probe2 commit-charge and pagefile, not RAM-percent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
