#!/usr/bin/env python3
"""Shared harvest, quote, and protocol helpers for RES-0158."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
CAP = HERE / "captures"
ARTIFACT_REL = (
    "command-center/research/gem-hunt/"
    "RES-0158-transfer-structured-analytic-techniques.json"
)
ARTIFACT = REPO / ARTIFACT_REL
UID = "RES-0158"
SENTINEL = "SUCCESS:RES-0158"
MIN_BYTES = 256
NOT_DELIVERING = frozenset({"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"})
SHERMAN_KENT_BANDS = (
    "almost-certain",
    "likely",
    "roughly-even",
    "unlikely",
    "remote",
)
PLAIN_DEBATE = {"id": "P01", "slug": "free-form-moderated-panel"}

# Frozen fetch metadata for captures that probes actually cite.
CAPTURES: dict[str, dict[str, str]] = {
    "cia-tradecraft-primer": {
        "url": "https://www.cia.gov/resources/csi/static/Tradecraft-Primer-apr09.pdf",
        "fetched_at": "2026-08-24T20:48:12Z",
        "text": "cia-tradecraft-primer.pdftext",
    },
    "heuer-pia-html": {
        "url": (
            "https://web.archive.org/web/20201112024629id_/"
            "https://www.cia.gov/library/center-for-the-study-of-intelligence/"
            "csi-publications/books-and-monographs/"
            "psychology-of-intelligence-analysis/art11.html"
        ),
        "fetched_at": "2026-08-24T20:48:13Z",
        "text": "heuer-pia-html.text",
    },
    "icd-203-pdf": {
        "url": "https://www.dni.gov/files/documents/ICD/ICD-203.pdf",
        "fetched_at": "2026-08-24T20:48:15Z",
        "text": "icd-203-pdf.pdftext",
    },
    "odni-icd203-page": {
        "url": (
            "https://web.archive.org/web/20201109000000id_/"
            "https://www.dni.gov/index.php/how-we-work/objectivity"
        ),
        "fetched_at": "2026-08-24T20:51:20Z",
        "text": "odni-icd203-page.body",
    },
    "mandel-dhami-ach-jdm": {
        "url": (
            "https://pdfs.semanticscholar.org/b4e4/"
            "19bb5900bfba6b9197b66f913c36973e5797.pdf"
        ),
        "fetched_at": "2026-08-24T20:50:40Z",
        "text": "mandel-dhami-ach-jdm.pdftext",
    },
    "klein-premortem-html": {
        "url": (
            "https://www.psychologytoday.com/us/blog/"
            "seeing-what-others-dont/202101/the-pre-mortem-method"
        ),
        "fetched_at": "2026-08-24T20:48:20Z",
        "text": "klein-premortem-html.text",
    },
    "hbr-premortem-wayback": {
        "url": (
            "https://web.archive.org/web/20150905080222id_/"
            "https://hbr.org/2007/09/performing-a-project-premortem"
        ),
        "fetched_at": "2026-08-24T20:51:10Z",
        "text": "hbr-premortem-wayback.body",
    },
}


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes()
    return sha256_bytes(raw), len(raw)


CATALOG_PY_REL = "tools/council/protocol/catalog.py"
CATALOG_PY = REPO / CATALOG_PY_REL
CAPTURES["council-protocol-catalog"] = {
    "url": CATALOG_PY_REL,
    "fetched_at": "2026-08-24T20:42:00Z",
    "text": "",
    "local": "1",
}


def searchable(capture_id: str) -> str:
    spec = CAPTURES[capture_id]
    if spec.get("local"):
        return CATALOG_PY.read_text(encoding="utf-8")
    parts: list[str] = []
    body = CAP / f"{capture_id}.body"
    if body.is_file():
        parts.append(body.read_bytes().decode("utf-8", errors="replace"))
    text_name = spec.get("text")
    if text_name:
        tp = CAP / text_name
        if tp.is_file():
            parts.append(tp.read_text(encoding="utf-8", errors="replace"))
    return "\n".join(parts)


def quote_in_capture(capture_id: str, quote: str) -> bool:
    if not quote or capture_id not in CAPTURES:
        return False
    return quote in searchable(capture_id)


def live_capture_row(capture_id: str) -> dict[str, Any]:
    spec = CAPTURES[capture_id]
    if spec.get("local"):
        if not CATALOG_PY.is_file():
            raise FileNotFoundError("missing council protocol catalog")
        sha, size = sha256_file(CATALOG_PY)
        return {
            "id": capture_id,
            "resolved_url": spec["url"],
            "fetch_timestamp": spec["fetched_at"],
            "sha256_of_fetched_bytes": sha,
            "bytes": size,
            "present": True,
            "capture_path": CATALOG_PY_REL,
        }
    body = CAP / f"{capture_id}.body"
    if not body.is_file() or body.stat().st_size <= 0:
        raise FileNotFoundError(f"missing capture {capture_id}")
    sha, size = sha256_file(body)
    return {
        "id": capture_id,
        "resolved_url": spec["url"],
        "fetch_timestamp": spec["fetched_at"],
        "sha256_of_fetched_bytes": sha,
        "bytes": size,
        "present": True,
        "capture_path": f"command-center/p2-wave/probes/RES-0158/captures/{capture_id}.body",
    }


def lineage(capture_id: str, quote: str, rail: str) -> dict[str, Any]:
    row = live_capture_row(capture_id)
    if not quote_in_capture(capture_id, quote):
        raise ValueError(f"quote-absent:{capture_id}:{quote[:48]}")
    row.update({"quote": quote, "rail": rail})
    return row


def live_protocols() -> dict[str, dict[str, Any]]:
    if str(REPO) not in sys.path:
        sys.path.insert(0, str(REPO))
    from tools.council.protocol.catalog import by_id  # noqa: WPS433
    from tools.council.protocol.plugin import classify  # noqa: WPS433

    out: dict[str, dict[str, Any]] = {}
    for pid, rec in by_id().items():
        cls = classify(rec)
        out[pid] = {
            "id": pid,
            "slug": rec.get("slug"),
            "family": rec.get("family"),
            "phases": rec.get("phases") or [],
            "kernel_status": cls.status,
            "extra_primitives": list(cls.extra_primitives),
            "forks_state": bool(rec.get("forks_state")),
            "hidden_parallel": bool(rec.get("hidden_parallel")),
        }
    return out


def obligation_ids(rec: dict[str, Any]) -> list[str]:
    ids: list[str] = []
    for phase in rec.get("phases") or []:
        for ob in phase.get("obligations") or []:
            oid = str(ob.get("id") or "")
            if oid:
                ids.append(oid)
    return ids


def load_artifact() -> dict[str, Any]:
    return json.loads(ARTIFACT.read_text(encoding="utf-8"))
