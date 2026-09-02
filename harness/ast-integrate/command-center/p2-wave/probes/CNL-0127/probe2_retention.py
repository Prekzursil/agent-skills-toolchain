#!/usr/bin/env python3
"""Probe 2: declared retention actually deletes; undeclared retention refuses persist.

Negative control: unexpired payload is not deleted. Replay after expiry is loud.
"""
from __future__ import annotations

import json
import sys
import tempfile
from datetime import timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from contract import (  # noqa: E402
    ReplayUnavailable,
    persist,
    replay,
    sweep,
    utcnow,
)
from fixtures import clean_transcript  # noqa: E402

ART = REPO / (
    "command-center/design/council/"
    "CNL-0127-audit-replay-privacy-and-persistence-contract-for-council-.md"
)
SENTINEL = "SUCCESS:CNL-0127"


def fail(msg: str, extra: dict | None = None) -> int:
    print(f"FAILED:CNL-0127-probe2 {msg}")
    if extra:
        print(json.dumps(extra, sort_keys=True, default=str)[:2000])
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

    clean = clean_transcript()
    undeclared = persist(clean, Path(tempfile.mkdtemp()), council_id="noret")
    if undeclared.get("ok") or undeclared.get("reason") != "retention-undeclared":
        return fail("undeclared retention did not refuse", undeclared)

    now = utcnow()
    with tempfile.TemporaryDirectory(prefix="cnl0127-p2-") as tmp:
        store = Path(tmp)
        expired = persist(
            clean,
            store,
            council_id="expired",
            retain_until=now - timedelta(seconds=1),
            now=now,
        )
        live_body = dict(clean)
        live_body["council_id"] = "unexpired"
        live = persist(
            live_body,
            store,
            council_id="unexpired",
            retain_until=now + timedelta(hours=1),
            now=now,
        )
        if not expired.get("ok") or not live.get("ok"):
            return fail("setup persist failed", {"expired": expired, "live": live})

        before = replay(store, "expired")
        if before.get("council_id") != clean["council_id"]:
            return fail("pre-sweep replay mismatch")

        result = sweep(store, now=now)
        if "expired" not in result.get("deleted", []):
            return fail("expired id not deleted", result)
        if "unexpired" not in result.get("kept", []):
            return fail("unexpired id was not kept", result)

        payload_exp = store / "expired.payload.json"
        tomb = store / "expired.tombstone.json"
        payload_live = store / "unexpired.payload.json"
        if payload_exp.exists():
            return fail("expired payload still on disk")
        if not tomb.is_file():
            return fail("tombstone missing after delete")
        if not payload_live.is_file():
            return fail("unexpired payload was deleted")

        try:
            replay(store, "expired")
            return fail("replay after expiry was silent")
        except ReplayUnavailable as exc:
            if exc.code != "REPLAY_EXPIRED":
                return fail(f"replay code {exc.code}")
            replay_code = exc.code
            replay_loud = True

        still = replay(store, "unexpired")
        if still.get("council_id") != "unexpired":
            return fail("unexpired replay drifted")

        stone = json.loads(tomb.read_text(encoding="utf-8"))
        if stone.get("reason") != "retention-expired":
            return fail("tombstone reason", stone)
        if "payload" in stone:
            return fail("tombstone carried payload")

    recorded = doc.get("tests") or []
    ids = {t.get("id") for t in recorded if isinstance(t, dict)}
    if "retention-deletes" not in ids:
        return fail("artifact missing retention-deletes test row")

    out = {
        "probe": "probe2-retention",
        "unit_id": "CNL-0127",
        "undeclared_retention_refused": True,
        "expired_deleted": True,
        "unexpired_kept": True,
        "tombstone_without_payload": True,
        "replay_after_expiry_code": replay_code,
        "replay_after_expiry_loud": replay_loud,
        "negative_control": (
            "sweep at now must delete retain_until<=now and must keep retain_until>now"
        ),
        "pass": True,
    }
    print(json.dumps(out, sort_keys=True))
    print("negative_control: unexpired payload kept; expired payload gone; replay loud")
    print("SUCCESS:CNL-0127-probe2 retention actually deletes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
