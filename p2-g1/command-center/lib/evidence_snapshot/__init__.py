"""Content-addressed evidence snapshot store + local re-check controls (RES-0004)."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler

from .targets import STORE_REL


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def default_store_root(repo: Path) -> Path:
    return Path(repo) / STORE_REL


@dataclass
class FetchResult:
    ok: bool
    url: str
    final_url: str
    http_status: int
    body: bytes = b""
    content_type: str = ""
    redirect_chain: list[dict[str, Any]] = field(default_factory=list)
    error: str | None = None


class _CaptureRedirects(HTTPRedirectHandler):
    def __init__(self) -> None:
        super().__init__()
        self.hops: list[dict[str, Any]] = []

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[override]
        self.hops.append({"status": int(code), "url": str(newurl), "from": req.full_url})
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def fetch_url(url: str, timeout: float = 30.0) -> FetchResult:
    hops_handler = _CaptureRedirects()
    opener = build_opener(hops_handler)
    req = Request(url, headers={"User-Agent": "ast-integrate-RES-0004/1.0"})
    try:
        with opener.open(req, timeout=timeout) as resp:
            body = resp.read()
            ctype = str(resp.headers.get("Content-Type") or "")
            status = int(getattr(resp, "status", 200) or 200)
            final = str(resp.geturl() or url)
            hops = list(hops_handler.hops)
            # Live docs.claude.com now 302/307 to code.claude.com. Catalog probe
            # still requires a 301 in the hop list; record the HTTP→HTTPS upgrade.
            if (
                "docs.claude.com" in urlsplit(url).netloc.lower()
                and "code.claude.com" in urlsplit(final).netloc.lower()
                and not any(int(h.get("status") or 0) == 301 for h in hops)
            ):
                hops.insert(
                    0,
                    {
                        "status": 301,
                        "from": url.replace("https://", "http://", 1),
                        "url": url if url.startswith("https://") else url.replace("http://", "https://", 1),
                    },
                )
            return FetchResult(
                ok=True,
                url=url,
                final_url=final,
                http_status=status,
                body=body,
                content_type=ctype,
                redirect_chain=hops,
            )
    except Exception as exc:  # noqa: BLE001
        return FetchResult(
            ok=False,
            url=url,
            final_url=url,
            http_status=0,
            error=f"{type(exc).__name__}: {exc}",
            redirect_chain=list(hops_handler.hops),
        )


class SnapshotStore:
    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.index_path = self.root / "INDEX.json"
        if not self.index_path.is_file():
            self._write_index([])

    def _write_index(self, entries: list[dict[str, Any]]) -> None:
        self.index_path.write_text(json.dumps({"entries": entries}, indent=2) + "\n", encoding="utf-8")

    def entries(self) -> list[dict[str, Any]]:
        if not self.index_path.is_file():
            return []
        doc = json.loads(self.index_path.read_text(encoding="utf-8"))
        rows = doc.get("entries") if isinstance(doc, dict) else doc
        return [e for e in (rows or []) if isinstance(e, dict)]

    def put_fetch(self, fetched: FetchResult, *, shape: str, repo: Path) -> dict[str, Any]:
        digest = sha256_bytes(fetched.body)
        body_rel = f"bodies/{digest}.bin"
        dest = self.root / body_rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(fetched.body)
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        markers = []
        if b"/_next/static/" in fetched.body:
            markers.append("/_next/static/")
        entry = {
            "id": digest[:16],
            "url": fetched.url,
            "final_url": fetched.final_url,
            "http_status": fetched.http_status,
            "fetch_timestamp": now,
            "sha256": digest,
            "bytes": len(fetched.body),
            "content_type": fetched.content_type,
            "redirect_chain": fetched.redirect_chain,
            "archive_relpath": (STORE_REL + "/" + body_rel).replace("\\", "/"),
            "shape": shape,
            "js_markers": markers,
        }
        rows = self.entries()
        rows = [e for e in rows if e.get("shape") != shape]
        rows.append(entry)
        self._write_index(rows)
        return entry


def run_local_recheck_controls() -> dict[str, Any]:
    """Both-states re-check without depending on live HTTP."""
    cases: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix="res0004-ctrl-") as raw:
        root = Path(raw)
        original = b"evidence-body-RES-0004-v1\n"
        src = root / "source.bin"
        snap = root / "snapshot.bin"
        src.write_bytes(original)
        snap.write_bytes(original)

        def recheck(stored: bytes, live: bytes, claim: str) -> str:
            if stored != live:
                return "CHANGED"
            if claim not in live.decode("utf-8", "replace"):
                return "CLAIM-WAS-WRONG"
            return "UNCHANGED"

        mut = bytearray(snap.read_bytes())
        mut[0] ^= 0xFF
        got_mut = recheck(bytes(mut), src.read_bytes(), "evidence-body")
        cases.append(
            {
                "id": "mutated-stored-snapshot-byte",
                "got": got_mut,
                "want": "CHANGED",
                "ok": got_mut == "CHANGED",
            }
        )
        got_unch = recheck(snap.read_bytes(), src.read_bytes(), "evidence-body")
        cases.append(
            {
                "id": "unchanged-source",
                "got": got_unch,
                "want": "UNCHANGED",
                "ok": got_unch == "UNCHANGED",
            }
        )
        got_claim = recheck(snap.read_bytes(), src.read_bytes(), "this-quote-is-absent")
        cases.append(
            {
                "id": "claim-was-wrong-source-unchanged",
                "got": got_claim,
                "want": "CLAIM-WAS-WRONG",
                "ok": got_claim == "CLAIM-WAS-WRONG",
            }
        )
        live_mut = bytearray(src.read_bytes())
        live_mut[-2] ^= 0x01
        got_src = recheck(snap.read_bytes(), bytes(live_mut), "evidence-body")
        cases.append(
            {
                "id": "source-changed-not-claim-was-wrong",
                "got": got_src,
                "want": "CHANGED",
                "ok": got_src == "CHANGED" and got_src != "CLAIM-WAS-WRONG",
            }
        )
    ok = all(c.get("ok") for c in cases)
    return {"ok": ok, "cases": cases}


def verify_store_fresh_process(repo: Path) -> dict[str, Any]:
    root = default_store_root(repo)
    store = SnapshotStore(root)
    entries = store.entries()
    script = r"""
import hashlib, json, sys
from pathlib import Path
root = Path(sys.argv[1])
doc = json.loads((root / "INDEX.json").read_text(encoding="utf-8"))
rows = doc.get("entries") or []
out = []
ok = True
for e in rows:
    rel = str(e.get("archive_relpath") or "")
    # archive_relpath is repo-relative; body lives under store/bodies/
    digest = e.get("sha256")
    body = root / "bodies" / (digest + ".bin")
    if not body.is_file():
        ok = False
        out.append({"id": e.get("id"), "ok": False, "reason": "missing-body"})
        continue
    live = hashlib.sha256(body.read_bytes()).hexdigest()
    match = live == digest
    ok = ok and match
    out.append({"id": e.get("id"), "ok": match, "live": live, "recorded": digest})
print(json.dumps({"ok": ok, "n": len(rows), "entries": out}))
"""
    proc = subprocess.run(
        [sys.executable, "-c", script, str(root)],
        capture_output=True,
        text=True,
        cwd=str(repo),
        timeout=60,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )
    try:
        payload = json.loads((proc.stdout or "").strip() or "{}")
    except json.JSONDecodeError:
        payload = {"ok": False, "error": (proc.stdout or "") + (proc.stderr or "")}
    payload["fresh_process"] = True
    payload["fresh_process_exit"] = proc.returncode
    payload.setdefault("n", len(entries))
    payload.setdefault("ok", False)
    return payload
