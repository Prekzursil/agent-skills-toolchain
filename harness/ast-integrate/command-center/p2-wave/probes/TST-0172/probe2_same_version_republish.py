#!/usr/bin/env python3
"""Probe 2: same-version republish is fetched; name@version still masks.

Independent signals:
  (a) resolved cache key strings differ (content hash, not name+version)
  (b) install after republish writes the new bytes on disk
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from scenario import VERSION, measure_same_version_republish  # noqa: E402

ART = REPO / "command-center/receipts/TST-0172.json"
SENTINEL = "SUCCESS:TST-0172"


def fail(msg: str) -> int:
    print(f"FAILED:TST-0172-probe2 {msg}")
    return 1


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="tst0172-p2-") as tmp:
        live = measure_same_version_republish(Path(tmp))

    print(json.dumps(live, indent=2, sort_keys=True))

    if not live.get("versions_equal"):
        return fail("republish did not keep the same version")
    if live.get("version") != VERSION:
        return fail(f"version={live.get('version')} want={VERSION}")
    if not live.get("keys_differ"):
        return fail(
            f"cache keys collided buggy={live.get('cache_key_buggy')} "
            f"fixed={live.get('cache_key_fixed')}"
        )
    if not live.get("cache_key_is_content_hash"):
        return fail("resolved cache key is not sha256(payload)")
    if not live.get("cas_fetched_fix"):
        return fail("same-version republish was served from stale cache")
    if not live.get("naive_still_served_stale"):
        return fail("name@version control did not mask (detector dead)")
    if not live.get("old_blob_still_present"):
        return fail("old content-addressed blob vanished (cannot prove key change)")
    install = live.get("install_after") or {}
    if install.get("sha256") != live.get("cache_key_fixed"):
        return fail("install-after digest does not match resolved cache key")
    if not install.get("equals_payload"):
        return fail("install-after bytes are not the fixed payload")

    if ART.is_file() and ART.stat().st_size > 0:
        text = ART.read_text(encoding="utf-8")
        if SENTINEL not in text:
            return fail("receipt-sentinel-absent")
        doc = json.loads(text)
        st = str(doc.get("state") or "").upper()
        if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
            return fail(f"receipt-self-declared {st}")
        if not doc.get("same_version_republish_fetched"):
            return fail("receipt-flag-republish-absent")
        keys = (doc.get("cache_key") or {}).get("fixed")
        if keys and keys != live.get("cache_key_fixed"):
            return fail("receipt cache_key.fixed does not match live")

    print(
        f"version={live['version']} key_buggy={live['cache_key_buggy'][:12]} "
        f"key_fixed={live['cache_key_fixed'][:12]} keys_differ=true "
        f"naive_masked=true install={install.get('sha256', '')[:12]}"
    )
    print("SUCCESS:TST-0172-probe2 same-version republish fetched; name@version masked")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
