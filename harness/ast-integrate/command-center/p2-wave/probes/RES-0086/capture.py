#!/usr/bin/env python3
"""Fetch two-rail sources for RES-0086 and freeze bytes + HTTP metadata."""
from __future__ import annotations

import hashlib
import json
import ssl
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
CAP = HERE / "captures"
UA = (
    "RES-0086-dissent-preservation-research/1.0 "
    "(+https://www.w3.org/policies/process/; academic capture)"
)
TIMEOUT = 70

SOURCES = [
    {
        "id": "w3c-process-html",
        "rail": "R1",
        "kind": "structured-official-html",
        "permalink": "https://www.w3.org/policies/process/",
    },
    {
        "id": "w3c-council-guide",
        "rail": "R2",
        "kind": "prose-guide",
        "permalink": "https://www.w3.org/guide/council/council.html",
    },
    {
        "id": "ieee-opman-sect5",
        "rail": "R1",
        "kind": "structured-official-html",
        "permalink": (
            "https://web.archive.org/web/20240101000000/"
            "https://standards.ieee.org/about/policies/opman/sect5/"
        ),
        "canonical_permalink": "https://standards.ieee.org/about/policies/opman/sect5/",
        "note": "Live IEEE OM returned HTTP 403; Wayback 2024-01-01 snapshot of the same URL.",
    },
    {
        "id": "ieee-recirc-faq",
        "rail": "R2",
        "kind": "prose-faq",
        "permalink": (
            "https://web.archive.org/web/20240101000000/"
            "https://standards.ieee.org/faqs/recirc/"
        ),
        "canonical_permalink": "https://standards.ieee.org/faqs/recirc/",
        "note": "Live IEEE FAQ returned HTTP 403; Wayback 2024-01-01 snapshot of the same URL.",
    },
    {
        "id": "fomc-minutes-20260729",
        "rail": "R1",
        "kind": "structured-official-html",
        "permalink": (
            "https://www.federalreserve.gov/monetarypolicy/fomcminutes20260729.htm"
        ),
    },
    {
        "id": "stlouisfed-fomc-dissents",
        "rail": "R2",
        "kind": "prose-explainer",
        "permalink": (
            "https://www.stlouisfed.org/on-the-economy/2018/january/"
            "fomc-dissents-members-break-consensus"
        ),
    },
    {
        "id": "rfc7282-txt",
        "rail": "R1",
        "kind": "structured-rfc-text",
        "permalink": "https://www.rfc-editor.org/rfc/rfc7282.txt",
    },
    {
        "id": "rfc7282-datatracker-html",
        "rail": "R2",
        "kind": "prose-html",
        "permalink": "https://datatracker.ietf.org/doc/html/rfc7282",
    },
    {
        "id": "govinfo-21-14-60-xml",
        "rail": "R1",
        "kind": "structured-official-xml",
        "permalink": (
            "https://www.govinfo.gov/content/pkg/CFR-2025-title21-vol1/xml/"
            "CFR-2025-title21-vol1-sec14-60.xml"
        ),
        "note": (
            "Live eCFR HTML returned a WAF 'Request Access' interstitial (HTTP 200). "
            "GovInfo CFR XML is the structured official granule for 21 CFR 14.60."
        ),
    },
    {
        "id": "cornell-21-14-60",
        "rail": "R2",
        "kind": "prose-lii",
        "permalink": "https://www.law.cornell.edu/cfr/text/21/14.60",
    },
    {
        "id": "frcp-31-cornell",
        "rail": "R1",
        "kind": "structured-official-html",
        "permalink": "https://www.law.cornell.edu/rules/frcrmp/rule_31",
    },
    {
        "id": "fomc-statement-20260729",
        "rail": "R2",
        "kind": "prose-press",
        "permalink": (
            "https://www.federalreserve.gov/newsevents/pressreleases/"
            "monetary20260729a.htm"
        ),
        "note": "Independent FOMC publication of the same vote-against names.",
    },
    {
        "id": "icj-statute",
        "rail": "R1",
        "kind": "structured-official-html",
        "permalink": "https://www.icj-cij.org/statute",
    },
    {
        "id": "icj-spender-art57",
        "rail": "R2",
        "kind": "prose-application",
        "permalink": "https://www.icj-cij.org/node/140789",
    },
    {
        "id": "ca3-frcp-31-chapter9",
        "rail": "R2",
        "kind": "prose-application",
        "permalink": (
            "https://www.ca3.uscourts.gov/sites/ca3/files/"
            "2020%20Chapter%209%20revisions%20final.pdf"
        ),
        "note": "Third Circuit model instructions quoting FRCP 31 poll-and-mistrial path.",
    },
]


def digest_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def fetch(url: str) -> dict:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": UA,
            "Accept": "text/html,application/xhtml+xml,text/plain,*/*;q=0.8",
        },
        method="GET",
    )
    ctx = ssl.create_default_context()
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT, context=ctx) as resp:
            body = resp.read()
            status = int(getattr(resp, "status", 200) or 200)
            final = resp.geturl()
    except urllib.error.HTTPError as exc:
        body = exc.read() if exc.fp else b""
        status = int(exc.code)
        final = url
    except Exception as exc:  # noqa: BLE001 - capture transport failures honestly
        return {
            "ok": False,
            "http_status": 0,
            "error": f"{type(exc).__name__}:{exc}",
            "fetched_at": ts,
            "final_url": url,
            "body": b"",
        }
    return {
        "ok": 200 <= status < 400 and len(body) > 0,
        "http_status": status,
        "error": None,
        "fetched_at": ts,
        "final_url": final,
        "body": body,
    }


def main() -> int:
    CAP.mkdir(parents=True, exist_ok=True)
    index = []
    fail = 0
    for src in SOURCES:
        got = fetch(src["permalink"])
        body_name = f"{src['id']}.body"
        body_path = CAP / body_name
        body_path.write_bytes(got["body"])
        sha = digest_bytes(got["body"])
        row = {
            "id": src["id"],
            "rail": src["rail"],
            "kind": src["kind"],
            "permalink": src["permalink"],
            "final_url": got["final_url"],
            "fetched_at": got["fetched_at"],
            "http_status": got["http_status"],
            "ok": got["ok"],
            "error": got["error"],
            "bytes": len(got["body"]),
            "sha256": sha,
            "capture_path": f"command-center/p2-wave/probes/RES-0086/captures/{body_name}",
        }
        if src.get("note"):
            row["note"] = src["note"]
        if src.get("canonical_permalink"):
            row["canonical_permalink"] = src["canonical_permalink"]
        index.append(row)
        flag = "OK" if got["ok"] else "FAIL"
        if not got["ok"]:
            fail += 1
        print(
            f"{flag} {src['id']} status={got['http_status']} "
            f"bytes={len(got['body'])} sha256={sha[:12]} "
            f"err={got['error']}"
        )
    (CAP / "INDEX.json").write_text(
        json.dumps(index, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"wrote {len(index)} captures fail={fail}")
    # Local rails for the synthesizer-instruction anti-pattern.
    catalog = HERE.parents[3] / "command-center" / "WORK-UNIT-CATALOG.json"
    fixture = (
        HERE.parent
        / "CC-0024"
        / "fixtures"
        / "prompt-two-slice.md"
    )
    local = []
    for path, lid, kind in (
        (catalog, "catalog-res-0086-row", "structured-catalog-json"),
        (fixture, "prompt-two-slice-dissent-lines", "prose-named-failure-class"),
    ):
        raw = path.read_bytes() if path.is_file() else b""
        local.append(
            {
                "id": lid,
                "kind": kind,
                "path": path.relative_to(HERE.parents[3]).as_posix()
                if path.is_file()
                else str(path),
                "present": path.is_file(),
                "bytes": len(raw),
                "sha256": digest_bytes(raw) if raw else "",
                "http_status": 200 if path.is_file() else 0,
                "fetched_at": datetime.now(timezone.utc).strftime(
                    "%Y-%m-%dT%H:%M:%SZ"
                ),
                "permalink": path.relative_to(HERE.parents[3]).as_posix()
                if path.is_file()
                else "",
            }
        )
    (CAP / "LOCAL.json").write_text(
        json.dumps(local, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    if fail:
        print("FAILED:RES-0086 capture one or more remote rails")
        return 1
    print("SUCCESS:RES-0086 capture")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
