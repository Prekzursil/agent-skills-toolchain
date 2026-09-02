#!/usr/bin/env python3
"""Probe 1: planted synthetic token is caught before persist; clean transcript persists.

Both-states plus scanner-off negative control. Never prints the token value.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from contract import (  # noqa: E402
    SYNTHETIC_TOKEN,
    SYNTHETIC_TOKEN_SHA256,
    disk_contains_synthetic_token,
    persist,
    scan,
)
from fixtures import clean_transcript, planted_encodings  # noqa: E402

ART = REPO / (
    "command-center/design/council/"
    "CNL-0127-audit-replay-privacy-and-persistence-contract-for-council-.md"
)
SENTINEL = "SUCCESS:CNL-0127"


def fail(msg: str, extra: dict | None = None) -> int:
    print(f"FAILED:CNL-0127-probe1 {msg}")
    if extra:
        print(json.dumps(extra, sort_keys=True)[:2000])
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as exc:
        return fail(f"artifact unparseable {exc}")
    if SENTINEL not in text:
        return fail("sentinel absent")
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")
    if doc.get("unit_id") != "CNL-0127":
        return fail("unit_id mismatch")

    clean = clean_transcript()
    if scan(clean):
        return fail("clean transcript was not silent")

    rows = []
    for name, planted in planted_encodings().items():
        findings = scan(planted)
        with tempfile.TemporaryDirectory(prefix=f"cnl0127-p1-{name}-") as tmp:
            store = Path(tmp)
            refused = persist(planted, store, council_id=name, ttl_seconds=3600)
            leaked = disk_contains_synthetic_token(store)
        if not findings:
            return fail(f"{name} scan silent on planted")
        if not refused.get("refused") or refused.get("ok"):
            return fail(f"{name} persist did not refuse", refused)
        if leaked:
            return fail(f"{name} synthetic bytes reached disk after refuse")
        if SYNTHETIC_TOKEN in json.dumps(refused):
            return fail(f"{name} persist result echoed token")
        rows.append(
            {
                "encoding": name,
                "finding_count": len(findings),
                "finding_classes": sorted({f["class"] for f in findings}),
                "refused": True,
                "disk_contains_synthetic": False,
                "token_sha256": SYNTHETIC_TOKEN_SHA256,
            }
        )

    with tempfile.TemporaryDirectory(prefix="cnl0127-p1-clean-") as tmp:
        store = Path(tmp)
        ok = persist(clean, store, council_id="clean", ttl_seconds=3600)
        leaked = disk_contains_synthetic_token(store)
        payload = store / "clean.payload.json"
        if not ok.get("ok") or not payload.is_file():
            return fail("clean persist failed", ok)
        if leaked:
            return fail("clean persist contained synthetic token")
        if scan(json.loads(payload.read_text(encoding="utf-8"))):
            return fail("persisted clean payload is not scan-silent")

    with tempfile.TemporaryDirectory(prefix="cnl0127-p1-neg-") as tmp:
        store = Path(tmp)
        planted = planted_encodings()["plain"]
        off = persist(
            planted,
            store,
            council_id="neg",
            ttl_seconds=3600,
            scan_enabled=False,
        )
        leaked = disk_contains_synthetic_token(store)
        if not off.get("ok"):
            return fail("negative control persist with scan off failed", off)
        if not leaked:
            return fail("negative control: scanner-off persist had no planted bytes")

    recorded = doc.get("tests") or []
    ids = {t.get("id") for t in recorded if isinstance(t, dict)}
    if "planted-secret-scan" not in ids:
        return fail("artifact missing planted-secret-scan test row")

    out = {
        "probe": "probe1-planted-secret",
        "unit_id": "CNL-0127",
        "encodings_caught": [r["encoding"] for r in rows],
        "rows": rows,
        "clean_persisted": True,
        "negative_control_scanner_off_wrote_planted": True,
        "token_sha256": SYNTHETIC_TOKEN_SHA256,
        "value_printed": False,
        "pass": True,
    }
    print(json.dumps(out, sort_keys=True))
    print(
        "negative_control: scanner-off persist writes planted bytes; scanner-on refuses"
    )
    print("SUCCESS:CNL-0127-probe1 planted-secret scan both-states")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
