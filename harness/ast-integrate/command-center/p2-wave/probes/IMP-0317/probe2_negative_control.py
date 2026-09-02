#!/usr/bin/env python3
"""Probe 2: negative control — disable the redactor; all 4 forms must be found.

Proves the scanner is not silently passing: the same exact-body detector and
the independent gitleaks-style scanner both fire on the unredacted persist.
Also proves declared retention actually deletes an expired artifact and keeps
one still inside the window.
"""
from __future__ import annotations

import json
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(HERE))

from tools.council.artifacts.retention import (  # noqa: E402
    PersistenceRefused,
    RetentionPolicy,
    apply_retention,
    persist_transcript,
)
import corpus as C  # noqa: E402
import gitleaks_style as G  # noqa: E402

ART = REPO / "command-center/receipts/IMP-0317.json"


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0317-probe2 {msg}")
    return 1


def main() -> int:
    # Hard rule: production persist without the test flag must refuse.
    refused = False
    try:
        with tempfile.TemporaryDirectory(prefix="imp0317-p2-refuse-") as td:
            persist_transcript(
                C.transcript(),
                Path(td) / "x.json",
                RetentionPolicy(redact=False, allow_unredacted_for_test=False),
            )
    except PersistenceRefused:
        refused = True
    if not refused:
        return fail("unredacted persist without test flag was allowed")

    policy = RetentionPolicy(
        redact=False,
        refuse_if_survivors=False,
        allow_unredacted_for_test=True,
        persistence="negative-control-unredacted",
    )
    with tempfile.TemporaryDirectory(prefix="imp0317-p2-") as td:
        dest = Path(td) / "council" / "transcript.json"
        persist_transcript(C.transcript(), dest, policy)
        data = dest.read_bytes()
        survivors = C.survivor_kinds(data)
        gl = G.scan_dir(dest.parent)
        present = C.encodings_present(data)
        gl_rules = sorted({h["rule_id"] for h in gl})

        print(
            json.dumps(
                {
                    "probe": "probe2-negative-control",
                    "unit_id": "IMP-0317",
                    "production_unredacted_refused": True,
                    "survivor_kinds": survivors,
                    "survivor_count": len(survivors),
                    "gitleaks_hits": len(gl),
                    "gitleaks_rule_ids": gl_rules,
                    "encodings_present": present,
                },
                sort_keys=True,
            )
        )
        missing = [k for k in C.ENCODINGS if k not in survivors]
        if missing:
            return fail(
                f"scanner silent on disabled-redactor persist; missed {missing}"
            )
        if len(gl) < 1:
            return fail("independent gitleaks-style scan found 0 hits on dirty artifact")
        # Each encoding should be visible to at least the exact-body detector;
        # gitleaks should fire on env, json, camelCase, and base64 forms.
        needed_rules = {
            "env-assignment",
            "json-password",
            "camelcase-apikey",
            "base64-assignment",
        }
        if not needed_rules.issubset(set(gl_rules)):
            return fail(
                f"gitleaks rules incomplete got={gl_rules} need={sorted(needed_rules)}"
            )

        # Retention actually deletes.
        store = Path(td) / "retain"
        store.mkdir()
        now = datetime(2026, 8, 24, 18, 0, 0, tzinfo=timezone.utc)
        old_policy = RetentionPolicy(
            redact=True,
            retention_seconds=60,
            refuse_if_survivors=True,
        )
        # Write two artifacts: one already expired, one fresh.
        persist_transcript(
            {"schema": "council-transcript/v1", "turns": [{"text": "no secrets here"}]},
            store / "expired.json",
            old_policy,
            now=now - timedelta(seconds=120),
        )
        persist_transcript(
            {"schema": "council-transcript/v1", "turns": [{"text": "no secrets here"}]},
            store / "fresh.json",
            old_policy,
            now=now,
        )
        result = apply_retention(store, old_policy, now=now)
        expired_gone = not (store / "expired.json").exists()
        fresh_kept = (store / "fresh.json").exists()
        print(
            json.dumps(
                {
                    "retention_deleted": result["deleted"],
                    "retention_kept_count": len(result["kept"]),
                    "expired_gone": expired_gone,
                    "fresh_kept": fresh_kept,
                },
                sort_keys=True,
            )
        )
        if not expired_gone:
            return fail("declared retention did not delete the expired artifact")
        if not fresh_kept:
            return fail("declared retention deleted an in-window artifact")

    if not ART.is_file():
        return fail("receipt missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {st}")
    if "SUCCESS:IMP-0317" not in ART.read_text(encoding="utf-8"):
        return fail("sentinel-absent")
    ncs = doc.get("negative_control_ids") or []
    if "disable-redactor-all-four-found" not in ncs:
        return fail("negative_control_ids missing disable-redactor-all-four-found")
    owner = doc.get("owner_signoff") or {}
    if not isinstance(owner, dict) or owner.get("reviewer_granted_owner_half") is not False:
        return fail("owner_signoff block missing or reviewer granted owner half")
    print("SUCCESS:IMP-0317-probe2 negative control fired on all 4 encodings")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
