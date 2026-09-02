#!/usr/bin/env python3
"""Fetch literature rails for RES-0182. Network is for capture only; probes re-hash bytes."""
from __future__ import annotations

import hashlib
import json
import ssl
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
SNAP = HERE / "snapshots"
UA = "ast-integrate-RES-0182-research/1.0 (Linux worktree evidence capture)"
CTX = ssl.create_default_context()

SOURCES = [
    {
        "id": "plos-hemming-2018-idea-html",
        "url": "https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0198468",
        "filename": "plos-hemming-2018-idea.html",
        "rail": "prose-source",
        "role": "idea-protocol",
    },
    {
        "id": "plos-hemming-2018-idea-pdf",
        "url": (
            "https://journals.plos.org/plosone/article/file"
            "?id=10.1371/journal.pone.0198468&type=printable"
        ),
        "filename": "plos-hemming-2018-idea.pdf",
        "rail": "prose-source",
        "role": "idea-protocol",
    },
    {
        "id": "wiley-hemming-2018-guide-html",
        "url": "https://besjournals.onlinelibrary.wiley.com/doi/full/10.1111/2041-210X.12857",
        "filename": "wiley-hemming-2018-guide.html",
        "rail": "prose-source",
        "role": "idea-protocol",
    },
    {
        "id": "osf-hemming-2018-preprint",
        "url": "https://osf.io/ex4mf/download",
        "filename": "osf-hemming-2018-preprint.bin",
        "rail": "prose-source",
        "role": "idea-protocol",
    },
    {
        "id": "cooke-goossens-2008-ress",
        "url": (
            "https://filelist.tudelft.nl/EWI/Over%20de%20faculteit/Afdelingen/"
            "Applied%20Mathematics/uitzoeken/Applied%20Probability/Risk/Download/"
            "RESS_Cooke_Goossens.pdf"
        ),
        "filename": "cooke-goossens-2008-ress.pdf",
        "rail": "prose-source",
        "role": "classical-model",
    },
    {
        "id": "cooke-reep-sej",
        "url": "https://rogermcooke.net/rogermcooke_files/REEP%20SEJ.pdf",
        "filename": "cooke-reep-sej.pdf",
        "rail": "prose-source",
        "role": "classical-model",
    },
    {
        "id": "tudelft-ocw-quantiles",
        "url": "https://ocw.tudelft.nl/course-lectures/2-5-1-how-to-construct-experts-distributions/",
        "filename": "tudelft-ocw-quantiles.html",
        "rail": "prose-source",
        "role": "classical-model",
    },
    {
        "id": "shelf-cran-overview",
        "url": "https://cran.r-project.org/web/packages/SHELF/vignettes/SHELF-overview.html",
        "filename": "shelf-cran-overview.html",
        "rail": "prose-source",
        "role": "shelf-protocol",
    },
    {
        "id": "shelf-cran-refman",
        "url": "https://cran.r-project.org/web/packages/SHELF/refman/SHELF.html",
        "filename": "shelf-cran-refman.html",
        "rail": "prose-source",
        "role": "shelf-protocol",
    },
    {
        "id": "ohagan-abstract",
        "url": "http://tonyohagan.co.uk/academic/abs/ElicSubjSci.html",
        "filename": "ohagan-2019-abstract.html",
        "rail": "prose-source",
        "role": "shelf-protocol",
    },
]


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def fetch(url: str) -> tuple[int, bytes, str]:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": UA,
            "Accept": "*/*",
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=90, context=CTX) as resp:
            raw = resp.read()
            final = str(resp.geturl() or url)
            status = int(getattr(resp, "status", 200) or 200)
            return status, raw, final
    except urllib.error.HTTPError as exc:
        raw = exc.read() if exc.fp else b""
        return int(exc.code), raw, url


def main() -> int:
    SNAP.mkdir(parents=True, exist_ok=True)
    rows = []
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    for src in SOURCES:
        status, raw, final = fetch(src["url"])
        ok = status == 200 and len(raw) >= 400
        dest = SNAP / src["filename"]
        if ok:
            dest.write_bytes(raw)
            digest = sha256_bytes(raw)
        else:
            digest = sha256_bytes(raw) if raw else ""
        row = {
            "id": src["id"],
            "ok": ok,
            "http_status": status,
            "requested_url": src["url"],
            "resolved_url": final,
            "fetched_at": now,
            "bytes": len(raw),
            "sha256": digest,
            "path": f"snapshots/{src['filename']}" if ok else None,
            "rail": src["rail"],
            "role": src["role"],
        }
        rows.append(row)
        print(f"{src['id']} status={status} ok={ok} bytes={len(raw)}")
    index = HERE / "sources_index.json"
    index.write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
    n_ok = sum(1 for r in rows if r["ok"])
    print(f"captured {n_ok}/{len(rows)} rails -> {index}")
    return 0 if n_ok >= 4 else 1


if __name__ == "__main__":
    raise SystemExit(main())
