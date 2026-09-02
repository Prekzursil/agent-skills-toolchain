"""Fetch public sources for claim lineage. Does not print secrets."""
from __future__ import annotations

import json
import ssl
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
import sys

if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
CAPTURES = HERE / "captures"
UA = (
    "RES-0150-research-probe/1.0 (local worktree; unfavorable-evidence quota "
    "design unit; +https://en.wikipedia.org/wiki/Goodhart%27s_law)"
)
SOURCES = [
    {
        "id": "goodhart-wikipedia",
        "url": "https://en.wikipedia.org/wiki/Goodhart%27s_law",
        "claim_ids": ["C-QUOTA-GOODHART"],
        "must_contain": "when a measure becomes a target",
    },
    {
        "id": "campbell-wikipedia",
        "url": "https://en.wikipedia.org/wiki/Campbell%27s_law",
        "claim_ids": ["C-QUALITY-FLOOR"],
        "must_contain": "quantitative social indicator",
    },
    {
        "id": "kent-wep-wikipedia",
        "url": "https://en.wikipedia.org/wiki/Words_of_estimative_probability",
        "claim_ids": ["C-KENT-BAND"],
        "must_contain": "Sherman Kent",
    },
    {
        "id": "ioannidis-plos",
        "url": "https://journals.plos.org/plosmedicine/article?id=10.1371/journal.pmed.0020124",
        "claim_ids": ["C-PUBLICATION-BIAS"],
        "must_contain": "Why Most Published Research Findings Are False",
    },
]


def _get(url: str) -> tuple[int, str, bytes]:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/html"})
    ctx = ssl.create_default_context()
    try:
        with urllib.request.urlopen(req, timeout=45, context=ctx) as resp:
            return int(resp.status), str(resp.geturl()), resp.read()
    except urllib.error.HTTPError as exc:
        body = exc.read() if exc.fp else b""
        return int(exc.code), url, body


def fetch_one(src: dict[str, Any]) -> dict[str, Any]:
    import engine as E

    CAPTURES.mkdir(parents=True, exist_ok=True)
    fetched_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    status, final, raw = _get(src["url"])
    body_path = CAPTURES / f"{src['id']}.body"
    meta_path = CAPTURES / f"{src['id']}.meta.json"
    body_path.write_bytes(raw)
    needle = (src.get("must_contain") or "").lower()
    text = raw.decode("utf-8", errors="replace")
    rec = {
        "id": src["id"],
        "resolved_url": final,
        "requested_url": src["url"],
        "http_status": status,
        "fetched_at": fetched_at,
        "sha256": E.sha256_bytes(raw),
        "bytes": len(raw),
        "body_path": f"command-center/p2-wave/probes/RES-0150/captures/{src['id']}.body",
        "claim_ids": list(src.get("claim_ids") or []),
        "must_contain": src.get("must_contain"),
        "needle_present": bool(needle) and needle in text.lower(),
        "ok": status == 200 and len(raw) > 400 and (not needle or needle in text.lower()),
    }
    meta_path.write_text(json.dumps(rec, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return rec


def fetch_all() -> list[dict[str, Any]]:
    return [fetch_one(s) for s in SOURCES]


def load_or_fetch() -> list[dict[str, Any]]:
    import engine as E

    rows: list[dict[str, Any]] = []
    missing = False
    for src in SOURCES:
        meta = CAPTURES / f"{src['id']}.meta.json"
        body = CAPTURES / f"{src['id']}.body"
        if meta.is_file() and body.is_file() and body.stat().st_size > 0:
            rec = json.loads(meta.read_text(encoding="utf-8"))
            live = E.sha256_bytes(body.read_bytes())
            rec["sha256"] = live
            rec["bytes"] = body.stat().st_size
            rows.append(rec)
        else:
            missing = True
            break
    if missing or len(rows) != len(SOURCES):
        return fetch_all()
    return rows


if __name__ == "__main__":
    for row in fetch_all():
        print(
            f"{row['id']:22s} status={row['http_status']} ok={row['ok']} "
            f"bytes={row['bytes']} needle={row['needle_present']}"
        )
