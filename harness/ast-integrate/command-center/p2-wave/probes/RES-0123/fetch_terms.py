"""HTTP capture of vendor terms. Does not print secrets."""
from __future__ import annotations

import json
import ssl
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from html.parser import HTMLParser

from common import CAPTURES, REPO, collapse_ws, sha256_bytes
from extracts import GROQ_SERVICES, OPENAI_CONSUMER, OPENAI_SERVICES, XAI_CONSUMER

UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
)
SOURCES = [
    {
        "id": "cursor-tos",
        "vendor": "cursor",
        "instrument": "consumer-tos",
        "url": "https://cursor.com/terms-of-service",
        "effective_marker": "Last updated August 13, 2026",
    },
    {
        "id": "cursor-aup",
        "vendor": "cursor",
        "instrument": "acceptable-use-policy",
        "url": "https://cursor.com/acceptable-use-policy",
        "effective_marker": "Last updated August 11, 2026",
    },
    {
        "id": "cursor-msa",
        "vendor": "cursor",
        "instrument": "master-services-agreement",
        "url": "https://cursor.com/terms/msa",
        "effective_marker": "Last updated August 13, 2026",
    },
    {
        "id": "cursor-cli-headless",
        "vendor": "cursor",
        "instrument": "cli-headless-docs",
        "url": "https://cursor.com/docs/cli/headless",
        "effective_marker": "retrieved-live-no-page-date",
    },
    {
        "id": "cursor-service-accounts",
        "vendor": "cursor",
        "instrument": "service-account-docs",
        "url": "https://cursor.com/docs/account/enterprise/service-accounts",
        "effective_marker": "retrieved-live-no-page-date",
    },
    {
        "id": "anthropic-commercial",
        "vendor": "anthropic",
        "instrument": "commercial-terms",
        "url": "https://www.anthropic.com/legal/commercial-terms",
        "effective_marker": "Effective June 17, 2025",
    },
    {
        "id": "anthropic-aup",
        "vendor": "anthropic",
        "instrument": "usage-policy",
        "url": "https://www.anthropic.com/legal/aup",
        "effective_marker": "Effective September 15, 2025",
    },
    {
        "id": "anthropic-consumer",
        "vendor": "anthropic",
        "instrument": "consumer-terms",
        "url": "https://www.anthropic.com/legal/consumer-terms",
        "effective_marker": "Effective October 8, 2025",
    },
    {
        "id": "google-gemini-api",
        "vendor": "google",
        "instrument": "gemini-api-additional-terms",
        "url": "https://ai.google.dev/gemini-api/terms",
        "effective_marker": "Effective March 23, 2026",
    },
    {
        "id": "groq-website-tos",
        "vendor": "groq",
        "instrument": "website-terms-of-use",
        "url": "https://groq.com/terms-of-use/",
        "effective_marker": "effective on October 15, 2025",
    },
    {
        "id": "groq-services",
        "vendor": "groq",
        "instrument": "services-agreement",
        "url": "https://console.groq.com/docs/legal/services-agreement",
        "effective_marker": "Effective Date (online acceptance)",
        "fallback_text": GROQ_SERVICES,
    },
    {
        "id": "openai-services",
        "vendor": "openai",
        "instrument": "services-agreement",
        "url": "https://openai.com/policies/services-agreement/",
        "effective_marker": "Effective: January 1, 2026",
        "fallback_text": OPENAI_SERVICES,
    },
    {
        "id": "openai-consumer",
        "vendor": "openai",
        "instrument": "consumer-terms-of-use",
        "url": "https://openai.com/policies/row-terms-of-use/",
        "effective_marker": "Effective: January 1, 2026",
        "fallback_text": OPENAI_CONSUMER,
    },
    {
        "id": "xai-consumer",
        "vendor": "xai",
        "instrument": "consumer-terms",
        "url": "https://x.ai/legal/terms-of-service",
        "effective_marker": "Effective: June 26, 2026",
        "fallback_text": XAI_CONSUMER,
    },
]


class _Text(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self.skip = 0

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in {"script", "style", "noscript"}:
            self.skip += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript"} and self.skip:
            self.skip -= 1

    def handle_data(self, data: str) -> None:
        if not self.skip:
            self.parts.append(data)


def html_to_text(raw: bytes) -> str:
    parser = _Text()
    parser.feed(raw.decode("utf-8", "replace"))
    lines = [ln.strip() for ln in "".join(parser.parts).splitlines() if ln.strip()]
    return collapse_ws("\n".join(lines))


def _get(url: str) -> tuple[int, str, bytes, str | None]:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": UA, "Accept": "text/html,application/xhtml+xml"},
    )
    ctx = ssl.create_default_context()
    try:
        with urllib.request.urlopen(req, timeout=30, context=ctx) as resp:
            return int(resp.status), resp.geturl(), resp.read(), resp.headers.get("Last-Modified")
    except urllib.error.HTTPError as exc:
        body = exc.read() if exc.fp else b""
        return int(exc.code), url, body, None


def load_existing(src: dict) -> dict | None:
    """Resume from an existing capture; do not overwrite live bytes."""
    meta_path = CAPTURES / f"{src['id']}.meta.json"
    text_path = CAPTURES / f"{src['id']}.txt"
    if not meta_path.is_file() or not text_path.is_file() or text_path.stat().st_size <= 0:
        return None
    rec = json.loads(meta_path.read_text(encoding="utf-8"))
    if not isinstance(rec, dict) or rec.get("id") != src["id"]:
        return None
    rec["text"] = text_path.read_text(encoding="utf-8")
    rec["repo_root"] = str(REPO)
    rec.setdefault("url", src["url"])
    rec.setdefault("vendor", src["vendor"])
    rec.setdefault("instrument", src["instrument"])
    rec.setdefault("effective_marker", src["effective_marker"])
    rec.setdefault("http_status", 0)
    rec.setdefault("used_extract_sidecar", bool(src.get("fallback_text")))
    rec.setdefault(
        "version_pin",
        {
            "kind": "retrieval-sha256",
            "sha256": rec.get("text_sha256") or sha256_bytes(text_path.read_bytes()),
            "http_status": rec.get("http_status"),
            "fetched_at": rec.get("fetched_at"),
            "note": "reused on-disk capture",
        },
    )
    rec.setdefault("body_sha256", rec.get("version_pin", {}).get("sha256"))
    rec.setdefault("text_sha256", sha256_bytes(text_path.read_bytes()))
    rec.setdefault("text_path", f"command-center/p2-wave/probes/RES-0123/captures/{src['id']}.txt")
    rec.setdefault("body_path", f"command-center/p2-wave/probes/RES-0123/captures/{src['id']}.body")
    rec.setdefault("fetched_at", "unknown")
    return rec


def fetch_one(src: dict) -> dict:
    CAPTURES.mkdir(parents=True, exist_ok=True)
    fetched_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    status, final, raw, last_mod = _get(src["url"])
    body_path = CAPTURES / f"{src['id']}.body"
    text_path = CAPTURES / f"{src['id']}.txt"
    meta_path = CAPTURES / f"{src['id']}.meta.json"
    body_path.write_bytes(raw)
    live_text = html_to_text(raw) if raw else ""
    fallback = (src.get("fallback_text") or "").strip()
    used_fallback = False
    if fallback and (status != 200 or len(live_text) < 800):
        text_path.write_text(fallback + "\n", encoding="utf-8")
        used_fallback = True
        stored_text = fallback
    else:
        text_path.write_text(live_text + "\n", encoding="utf-8")
        stored_text = live_text
    pin_raw = raw if status == 200 and raw else text_path.read_bytes()
    rec = {
        "id": src["id"],
        "vendor": src["vendor"],
        "instrument": src["instrument"],
        "url": src["url"],
        "final_url": final,
        "http_status": status,
        "fetched_at": fetched_at,
        "last_modified_header": last_mod,
        "effective_marker": src["effective_marker"],
        "body_bytes": len(raw),
        "body_sha256": sha256_bytes(raw),
        "text_sha256": sha256_bytes(text_path.read_bytes()),
        "body_path": f"command-center/p2-wave/probes/RES-0123/captures/{src['id']}.body",
        "text_path": f"command-center/p2-wave/probes/RES-0123/captures/{src['id']}.txt",
        "used_extract_sidecar": used_fallback,
        "version_pin": {
            "kind": "retrieval-sha256",
            "sha256": sha256_bytes(pin_raw),
            "http_status": status,
            "fetched_at": fetched_at,
            "note": (
                "HTML retrieval sha256 of live bytes when HTTP 200; "
                "otherwise sha256 of the extract sidecar after a blocked or empty fetch"
            ),
        },
    }
    meta_path.write_text(json.dumps(rec, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    rec["text"] = stored_text
    rec["repo_root"] = str(REPO)
    return rec


def fetch_all(reuse_existing: bool = True) -> list[dict]:
    rows: list[dict] = []
    for src in SOURCES:
        if reuse_existing:
            cached = load_existing(src)
            if cached is not None:
                rows.append(cached)
                continue
        rows.append(fetch_one(src))
    return rows


if __name__ == "__main__":
    refresh = "--refresh" in sys.argv
    for row in fetch_all(reuse_existing=not refresh):
        print(
            f"{row['id']:24s} status={row['http_status']} "
            f"sidecar={row['used_extract_sidecar']} bytes={row.get('body_bytes')}"
        )
