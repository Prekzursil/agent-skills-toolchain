#!/usr/bin/env python3
"""Probe 2: docs.claude.com → code.claude.com redirect + fresh-process store re-hash."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from urllib.parse import urlsplit

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "command-center" / "lib"))

from evidence_snapshot import SnapshotStore, default_store_root, fetch_url, verify_store_fresh_process  # noqa: E402
from evidence_snapshot.targets import (  # noqa: E402
    ARTIFACT_REL,
    COMPLETION_SENTINEL,
    EVIDENCE_TARGETS,
    STORE_REL,
)

ART = REPO / ARTIFACT_REL
NOT_DELIVERING = {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}
REDIRECT_URL = EVIDENCE_TARGETS[0]["url"]


def _fail(msg: str) -> int:
    print(f"FAILED:RES-0004-probe2 {msg}")
    return 1


def main() -> int:
    store = SnapshotStore(default_store_root(REPO))
    entries = store.entries()
    shapes = {e.get("shape") for e in entries}
    payload = {
        "probe": "probe2-redirect-rehash",
        "unit_id": "RES-0004",
        "store": STORE_REL,
        "n_entries": len(entries),
        "shapes": sorted(shapes),
    }

    fetched = fetch_url(REDIRECT_URL, timeout=30.0)
    final_host = urlsplit(fetched.final_url).netloc.lower()
    hop_statuses = [int(h.get("status") or 0) for h in fetched.redirect_chain]
    redirect_ok = (
        fetched.ok
        and "docs.claude.com" in urlsplit(fetched.url).netloc.lower()
        and "code.claude.com" in final_host
        and 301 in hop_statuses
    )
    payload["live_redirect"] = {
        "url": fetched.url,
        "final_url": fetched.final_url,
        "http_status": fetched.http_status,
        "redirect_chain": fetched.redirect_chain,
        "ok": redirect_ok,
        "error": fetched.error,
    }

    stored_redirect = next((e for e in entries if e.get("shape") == "redirect-chain"), None)
    stored_ok = False
    if stored_redirect:
        stored_final = str(stored_redirect.get("final_url") or "").lower()
        stored_hops = stored_redirect.get("redirect_chain") or []
        stored_ok = "code.claude.com" in stored_final and any(
            int(h.get("status") or 0) == 301 for h in stored_hops if isinstance(h, dict)
        )
    payload["stored_redirect_ok"] = stored_ok

    required = {"redirect-chain", "js-rendered", "raw-file"}
    payload["required_shapes_present"] = required.issubset(shapes)

    js_entry = next((e for e in entries if e.get("shape") == "js-rendered"), None)
    raw_entry = next((e for e in entries if e.get("shape") == "raw-file"), None)
    payload["js_markers"] = (js_entry or {}).get("js_markers")
    payload["raw_content_type"] = (raw_entry or {}).get("content_type")

    fresh = verify_store_fresh_process(REPO)
    payload["fresh_process_rehash"] = {
        "ok": bool(fresh.get("ok")),
        "n": fresh.get("n"),
        "fresh_process": fresh.get("fresh_process"),
        "fresh_process_exit": fresh.get("fresh_process_exit"),
        "entries": fresh.get("entries"),
    }
    print(json.dumps(payload, sort_keys=True, default=str))

    if not redirect_ok:
        return _fail(
            f"docs.claude.com did not land on code.claude.com via 301 "
            f"(final={fetched.final_url!r} hops={fetched.redirect_chain!r} err={fetched.error})"
        )
    if not stored_ok:
        return _fail("stored redirect-chain entry missing code.claude.com final URL / 301 hop")
    if not required.issubset(shapes):
        return _fail(f"store missing required shapes {required - shapes}")
    if not js_entry or not (js_entry.get("js_markers") or []):
        return _fail("js-rendered entry lacks JS markers")
    raw_ct = str((raw_entry or {}).get("content_type") or "").lower()
    if not raw_entry or "text/plain" not in raw_ct:
        return _fail(f"raw-file entry not text/plain ({raw_ct!r})")
    if not fresh.get("ok") or not fresh.get("fresh_process"):
        return _fail(f"fresh-process re-hash failed {fresh}")
    if int(fresh.get("n") or 0) < 3:
        return _fail("store has fewer than 3 entries")

    if not ART.is_file() or ART.stat().st_size < 200:
        return _fail("receipt missing")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in NOT_DELIVERING:
        return _fail(f"self-declared {doc.get('state')}")
    if "SUCCESS:RES-0004" not in text or COMPLETION_SENTINEL not in text:
        return _fail("sentinel absent")
    tests = {t.get("id"): t for t in (doc.get("tests") or []) if isinstance(t, dict)}
    if (tests.get("redirect-docs.claude.com-to-code.claude.com") or {}).get("result") != "PASS":
        return _fail("receipt redirect test not PASS")
    if (tests.get("fresh-process-rehash-all-entries") or {}).get("result") != "PASS":
        return _fail("receipt fresh-process rehash test not PASS")
    print("SUCCESS:RES-0004-probe2 redirect capture and fresh-process re-hash")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
