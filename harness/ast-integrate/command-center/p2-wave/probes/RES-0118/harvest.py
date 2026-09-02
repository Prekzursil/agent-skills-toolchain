#!/usr/bin/env python3
"""Live-fetch Google Patents HTML, pin snapshots, extract claim 1 (and selected dependents)."""
from __future__ import annotations

import hashlib
import html as htmlmod
import json
import re
import ssl
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
SNAP = HERE / "snapshots"
UA = "Mozilla/5.0 (compatible; RES-0118-harvest/1.0; research-claim-pinning)"
DISCLAIMER = (
    "The legal status is an assumption and is not a legal conclusion. "
    "Google has not performed a legal analysis and makes no representation "
    "as to the accuracy of the status listed."
)

# Publication identifiers that resolved HTTP 200 on a prior probe of this
# worktree. 404s are attempted again and recorded as unresolved.
TARGETS: list[dict[str, Any]] = [
    {
        "publication_number": "US12307349B2",
        "url": "https://patents.google.com/patent/US12307349B2/en",
        "claims": [1],
    },
    {
        "publication_number": "US20250252293A1",
        "url": "https://patents.google.com/patent/US20250252293A1/en",
        "claims": [1, 3],
    },
    {
        "publication_number": "CN117633174B",
        "url": "https://patents.google.com/patent/CN117633174B/en",
        "claims": [1],
    },
    {
        "publication_number": "US20260127463A1",
        "url": "https://patents.google.com/patent/US20260127463A1/en",
        "claims": [1],
    },
    {
        "publication_number": "US12412138B1",
        "url": "https://patents.google.com/patent/US12412138B1/en",
        "claims": [1],
    },
    {
        "publication_number": "US12536406B2",
        "url": "https://patents.google.com/patent/US12536406B2/en",
        "claims": [1],
    },
    {
        "publication_number": "US12321370B2",
        "url": "https://patents.google.com/patent/US12321370B2/en",
        "claims": [1],
    },
]
UNRESOLVED_CANDIDATES = [
    "https://patents.google.com/patent/US12699885B1/en",
    "https://patents.google.com/patent/US12639295B1/en",
]
SECOND_RAIL = [
    "https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/12307349",
    "https://worldwide.espacenet.com/publicationDetails/biblio?FT=D&CC=US&NR=12307349B2&KC=B2",
]


def utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def fetch(url: str, timeout: int = 45) -> dict[str, Any]:
    ctx = ssl.create_default_context()
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": UA,
            "Accept": "text/html,application/pdf,*/*;q=0.8",
            "Accept-Language": "en",
        },
    )
    stamp = utcnow()
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            body = resp.read()
            return {
                "url": url,
                "final_url": resp.geturl(),
                "http_status": getattr(resp, "status", None) or resp.getcode(),
                "content_type": resp.headers.get("Content-Type"),
                "body": body,
                "fetch_timestamp": stamp,
                "error": None,
            }
    except urllib.error.HTTPError as exc:
        body = exc.read() if exc.fp else b""
        return {
            "url": url,
            "final_url": None,
            "http_status": int(exc.code),
            "content_type": exc.headers.get("Content-Type") if exc.headers else None,
            "body": body,
            "fetch_timestamp": stamp,
            "error": f"HTTPError: {exc.code}",
        }
    except Exception as exc:  # noqa: BLE001 — harvest must record any rail failure
        return {
            "url": url,
            "final_url": None,
            "http_status": None,
            "content_type": None,
            "body": b"",
            "fetch_timestamp": stamp,
            "error": f"{type(exc).__name__}: {exc}",
        }


def strip_tags(chunk: str) -> str:
    text = re.sub(r"(?is)<script[^>]*>.*?</script>", " ", chunk)
    text = re.sub(r"(?is)<style[^>]*>.*?</style>", " ", text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = htmlmod.unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def first_itemprop(html: str, name: str) -> str:
    pat = rf'itemprop="{re.escape(name)}"[^>]*>([^<]+)'
    m = re.search(pat, html)
    if m:
        return htmlmod.unescape(m.group(1)).strip()
    pat2 = rf'itemprop="{re.escape(name)}"[^>]*content="([^"]+)"'
    m = re.search(pat2, html)
    return htmlmod.unescape(m.group(1)).strip() if m else ""


def extract_claim(html: str, claim_num: int) -> str:
    cid = f'id="CLM-{claim_num:05d}"'
    start = html.find(cid)
    if start >= 0:
        lt = html.rfind("<", 0, start)
        if lt >= 0:
            start = lt
        nxt = html.find(f'id="CLM-{claim_num + 1:05d}"', start + 1)
        if nxt > 0:
            nxt_lt = html.rfind("<", start, nxt)
            end = nxt_lt if nxt_lt > start else nxt
        else:
            end = min(len(html), start + 20000)
        text = strip_tags(html[start:end])
    else:
        m = re.search(
            rf'(?:class="claim-text">|<claim-text>)\s*{claim_num}\.\s+',
            html,
        )
        if not m:
            return ""
        start = m.start()
        nxt = re.search(
            rf'(?:class="claim-text">|<claim-text>)\s*{claim_num + 1}\.\s+',
            html[start + 10 :],
        )
        end = start + 10 + nxt.start() if nxt else start + 12000
        text = strip_tags(html[start:end])
    numbered = re.search(rf"{claim_num}\.\s+", text)
    if numbered:
        text = text[numbered.start() :]
    return text.strip()


def kind_from_pub(pub: str) -> str:
    m = re.search(r"([A-Z]\d?)$", pub)
    return m.group(1) if m else ""


def jurisdiction_from_pub(pub: str) -> str:
    m = re.match(r"^([A-Z]{2})", pub)
    return m.group(1) if m else ""


def parse_hit(target: dict[str, Any], fetched: dict[str, Any]) -> list[dict[str, Any]]:
    body: bytes = fetched["body"]
    html = body.decode("utf-8", errors="replace")
    pub = target["publication_number"]
    snap_name = f"{pub}.html"
    SNAP.mkdir(parents=True, exist_ok=True)
    snap_path = SNAP / snap_name
    snap_path.write_bytes(body)
    sha = hashlib.sha256(body.replace(b"\r\n", b"\n")).hexdigest()
    rel = f"command-center/p2-wave/probes/RES-0118/snapshots/{snap_name}"
    status_printed = first_itemprop(html, "status") or ""
    pub_in_html = first_itemprop(html, "publicationNumber") or pub
    title = first_itemprop(html, "title") or ""
    pub_date = first_itemprop(html, "publicationDate") or ""
    app_no = first_itemprop(html, "applicationNumber") or ""
    assignee = first_itemprop(html, "assigneeOriginal") or first_itemprop(
        html, "assigneeCurrent"
    )
    disclaimer_present = DISCLAIMER[:40] in html
    rows = []
    for claim_num in target["claims"]:
        claim_text = extract_claim(html, claim_num)
        rows.append(
            {
                "publication_number": pub,
                "publication_number_as_printed": pub_in_html,
                "jurisdiction": jurisdiction_from_pub(pub),
                "kind_code": kind_from_pub(pub),
                "title_as_printed": title,
                "legal_status": {
                    "as_printed": status_printed,
                    "as_reported_by_source": status_printed,
                    "source": "Google Patents bibliographic itemprop=status",
                    "source_disclaimer": DISCLAIMER,
                    "disclaimer_present_in_snapshot": disclaimer_present,
                    "kind_code": kind_from_pub(pub),
                },
                "publication_date_as_printed": pub_date,
                "application_number_as_printed": app_no,
                "assignee_as_printed": assignee,
                "assignee_source_caveat": (
                    "Google Patents states listed assignees may be inaccurate "
                    "and that it has not performed a legal analysis."
                ),
                "claim_number_read": claim_num,
                "claim_text_read": claim_text,
                "source_url": target["url"],
                "http_status": fetched["http_status"],
                "fetch_timestamp": fetched["fetch_timestamp"],
                "snapshot_path": rel,
                "snapshot_sha256": sha,
                "snapshot_bytes": len(body.replace(b"\r\n", b"\n")),
                "content_type": fetched.get("content_type"),
            }
        )
    return rows


def main() -> int:
    SNAP.mkdir(parents=True, exist_ok=True)
    hits: list[dict[str, Any]] = []
    unresolved: list[dict[str, Any]] = []
    fetch_errors: list[str] = []
    for target in TARGETS:
        fetched = fetch(target["url"])
        if fetched["http_status"] != 200 or not fetched["body"]:
            unresolved.append(
                {
                    "publication_number": target["publication_number"],
                    "url": target["url"],
                    "http_status": fetched["http_status"],
                    "error": fetched["error"],
                    "fetch_timestamp": fetched["fetch_timestamp"],
                }
            )
            fetch_errors.append(
                f"{target['publication_number']} status={fetched['http_status']} {fetched['error']}"
            )
            continue
        rows = parse_hit(target, fetched)
        for row in rows:
            if len(row.get("claim_text_read") or "") < 40:
                fetch_errors.append(
                    f"{row['publication_number']} claim {row['claim_number_read']} extract failed"
                )
            else:
                hits.append(row)
                print(
                    f"OK {row['publication_number']} claim={row['claim_number_read']} "
                    f"status={row['legal_status']['as_printed']!r} "
                    f"bytes={row['snapshot_bytes']} sha256={row['snapshot_sha256'][:12]}"
                )
    for url in UNRESOLVED_CANDIDATES:
        fetched = fetch(url)
        unresolved.append(
            {
                "url": url,
                "http_status": fetched["http_status"],
                "error": fetched["error"],
                "fetch_timestamp": fetched["fetch_timestamp"],
                "note": "candidate identifier did not resolve to a readable claim",
            }
        )
        print(f"UNRESOLVED {url} status={fetched['http_status']} {fetched['error']}")
    second = []
    for url in SECOND_RAIL:
        fetched = fetch(url)
        second.append(
            {
                "url": url,
                "http_status": fetched["http_status"],
                "error": fetched["error"],
                "fetch_timestamp": fetched["fetch_timestamp"],
                "bytes": len(fetched.get("body") or b""),
            }
        )
        print(f"SECOND_RAIL {url} status={fetched['http_status']} {fetched['error']}")
    doc = {
        "unit_id": "RES-0118",
        "harvested_at": utcnow(),
        "user_agent": UA,
        "primary_host": "patents.google.com",
        "hits": hits,
        "unresolved_publication_identifiers": unresolved,
        "second_rail_attempts": second,
        "extract_errors": fetch_errors,
    }
    out = HERE / "harvest.json"
    out.write_text(json.dumps(doc, indent=1, ensure_ascii=True) + "\n", encoding="utf-8")
    print(f"wrote {out.relative_to(REPO).as_posix()} hits={len(hits)} unresolved={len(unresolved)}")
    if len(hits) < 1:
        print("FAILED:RES-0118-harvest no hits")
        return 1
    if fetch_errors:
        print("WARN extract_errors=" + "; ".join(fetch_errors))
    print("SUCCESS:RES-0118-harvest")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
