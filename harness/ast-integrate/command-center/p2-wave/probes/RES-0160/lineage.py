#!/usr/bin/env python3
"""Source lineage: resolved URL + fetch timestamp + sha256 of fetched bytes."""
from __future__ import annotations

import hashlib
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
SOURCES = HERE / "sources"

# Wall-clock of the HTTP GET that populated sources/. Re-hashing the cache
# does not change this timestamp.
FETCH_TS = "2026-08-24T18:47:00Z"

REMOTE = (
    {
        "id": "wep-wikipedia",
        "url": "https://en.wikipedia.org/wiki/Words_of_estimative_probability",
        "rel": "command-center/p2-wave/probes/RES-0160/sources/wep-wikipedia.html",
        "quoted_span": '<td id="mwLg">Almost certain</td>\n<td id="mwLw">93%</td>',
        "role": "sherman-kent-bands",
    },
    {
        "id": "sre-error-budget",
        "url": "https://sre.google/sre-book/embracing-risk/",
        "rel": "command-center/p2-wave/probes/RES-0160/sources/sre-embracing-risk.html",
        "quoted_span": (
            "If SLO violations occur frequently enough to expend the error "
            "budget, releases are temporarily halted"
        ),
        "role": "revert-when-budget-spent",
    },
    {
        "id": "kent-wep-pdf",
        "url": "https://www.cia.gov/resources/csi/static/Words-of-Estimative-Probability.pdf",
        "rel": "command-center/p2-wave/probes/RES-0160/sources/kent-wep.pdf",
        "quoted_span": "%PDF-1.3",
        "role": "sherman-kent-original-bytes",
        "notes": (
            "1964 Kent article, CIA Historical Review Program PDF. Body text "
            "is CID-positioned; table numbers are corroborated by the Wikipedia "
            "page that cites this article, not extracted from these bytes."
        ),
    },
)

LOCAL = (
    {
        "id": "ready-units",
        "rel": "command-center/ready_units.py",
        "quoted_span": "BYPASS_PROVEN = True",
        "role": "live-gate-source",
    },
    {
        "id": "p2-build-round2",
        "rel": "command-center/p2-wave/P2-BUILD-ROUND2.md",
        "quoted_span": "BYPASS_PROVEN = True",
        "role": "sweep-r2-report",
    },
    {
        "id": "p2-build-round3",
        "rel": "command-center/p2-wave/P2-BUILD-ROUND3.md",
        "quoted_span": "the document, used AS a contract, must reject all three garbage probes",
        "role": "sweep-r3-report",
    },
    {
        "id": "catalog-res0160",
        "rel": "command-center/WORK-UNIT-CATALOG.json",
        "quoted_span": "_USER-PROMPTS.md:11146 (revert when neutral or harmful)",
        "role": "catalog-spec-anchor",
        "notes": (
            "_USER-PROMPTS.md, command-center/sources/REGISTER.md and "
            "command-center/CLAIM-REGISTRY.json are absent on this worktree. "
            "The catalog row is the reachable quote of spec:11146."
        ),
    },
)


def digest_bytes(raw: bytes) -> tuple[str, int]:
    norm = raw.replace(b"\r\n", b"\n")
    return hashlib.sha256(norm).hexdigest(), len(norm)


def _file_url(rel: str) -> str:
    return "file://" + (REPO / rel).resolve().as_posix()


def load_lineage() -> list[dict]:
    rows: list[dict] = []
    for spec in REMOTE:
        path = REPO / spec["rel"]
        raw = path.read_bytes()
        sha, size = digest_bytes(raw)
        quote = spec["quoted_span"]
        text = raw.decode("utf-8", errors="replace")
        present = quote in text or quote.encode("ascii", "replace") in raw
        row = {
            "id": spec["id"],
            "url": spec["url"],
            "fetch_timestamp": FETCH_TS,
            "sha256": sha,
            "bytes": size,
            "quoted_span": quote,
            "quote_present": present,
            "role": spec["role"],
            "cache_path": spec["rel"],
        }
        if spec.get("notes"):
            row["notes"] = spec["notes"]
        rows.append(row)
    for spec in LOCAL:
        path = REPO / spec["rel"]
        raw = path.read_bytes()
        sha, size = digest_bytes(raw)
        quote = spec["quoted_span"]
        text = raw.decode("utf-8", errors="replace")
        rows.append(
            {
                "id": spec["id"],
                "url": _file_url(spec["rel"]),
                "fetch_timestamp": FETCH_TS,
                "sha256": sha,
                "bytes": size,
                "quoted_span": quote,
                "quote_present": quote in text,
                "role": spec["role"],
                "cache_path": spec["rel"],
                **({"notes": spec["notes"]} if spec.get("notes") else {}),
            }
        )
    return rows


def by_id() -> dict[str, dict]:
    return {r["id"]: r for r in load_lineage()}


def assert_quotes_present() -> None:
    missing = [
        r["id"]
        for r in load_lineage()
        if r["id"] != "kent-wep-pdf" and not r["quote_present"]
    ]
    if missing:
        raise SystemExit(f"FAILED:RES-0160 lineage quotes absent: {missing}")
