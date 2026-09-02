#!/usr/bin/env python3
"""Run rebuilt fixture and content scanners over TST-0341 corpora."""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from tools.scanners.content_scanner import applies as content_applies
from tools.scanners.content_scanner import scan_content_records
from tools.scanners.fixture_scanner import applies as fixture_applies
from tools.scanners.fixture_scanner import scan_fixture_records
from tools.scanners.runtime import FORBIDDEN_PATTERNS, scan_json_file

from corpus import extra_mentions, historical_false_positives, true_positives

ART = REPO / "command-center" / "receipts" / "TST-0341.json"


def _summary(role: dict[str, Any], expect_fire: bool) -> dict[str, Any]:
    ids = [r["id"] for r in role.get("rows") or []]
    fires = list(role.get("fires_ids") or [])
    silent = list(role.get("silent_ids") or [])
    naive = list(role.get("naive_fires_ids") or [])
    if expect_fire:
        ok = len(silent) == 0 and len(fires) == len(ids) and len(ids) > 0
    else:
        ok = (
            len(fires) == 0
            and len(silent) == len(ids)
            and len(naive) == len(ids)
            and len(ids) > 0
        )
    return {
        "n": len(ids),
        "role_fires": len(fires),
        "role_silent": len(silent),
        "naive_fires": len(naive),
        "role_fires_ids": fires,
        "role_silent_ids": silent,
        "naive_fires_ids": naive,
        "ok": ok,
    }


def evaluate_scanners() -> dict[str, Any]:
    hist = historical_false_positives() + extra_mentions()
    uses = true_positives()
    fixture_fp = scan_fixture_records(hist, mode="role")
    fixture_tp = scan_fixture_records(uses, mode="role")
    content_fp = scan_content_records(hist, mode="role")
    content_tp = scan_content_records(uses, mode="role")
    fx_fp = _summary(fixture_fp, expect_fire=False)
    fx_tp = _summary(fixture_tp, expect_fire=True)
    ct_fp = _summary(content_fp, expect_fire=False)
    ct_tp = _summary(content_tp, expect_fire=True)
    # Wrong repair: silence FPs by never firing. Both numbers are mandatory.
    both_ok = bool(fx_fp["ok"] and fx_tp["ok"] and ct_fp["ok"] and ct_tp["ok"])
    return {
        "fixture": {
            "kinds": sorted(r["kind"] for r in hist + uses if fixture_applies(r)),
            "false_positive": fx_fp,
            "true_positive": fx_tp,
            "ok": bool(fx_fp["ok"] and fx_tp["ok"]),
        },
        "content": {
            "kinds": sorted({r["kind"] for r in hist + uses if content_applies(r)}),
            "false_positive": ct_fp,
            "true_positive": ct_tp,
            "ok": bool(ct_fp["ok"] and ct_tp["ok"]),
        },
        "historical_n": len(historical_false_positives()),
        "true_positive_n": len(uses),
        "both_scanners_both_corpora": both_ok,
        "loosening_would_zero_tp": (
            fx_fp["role_fires"] == 0
            and ct_fp["role_fires"] == 0
            and (fx_tp["role_silent"] > 0 or ct_tp["role_silent"] > 0)
        ),
    }


def self_scan_receipt() -> dict[str, Any]:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return {"ok": False, "reason": "receipt-absent"}
    text = ART.read_text(encoding="utf-8")
    missing = [p for p in FORBIDDEN_PATTERNS if p not in text]
    if missing:
        return {"ok": False, "reason": "examples-absent", "missing": missing}
    role = scan_json_file(ART, FORBIDDEN_PATTERNS, mode="role")
    naive = scan_json_file(ART, FORBIDDEN_PATTERNS, mode="naive")
    ok = (not role.get("fires")) and bool(naive.get("fires")) and not missing
    return {
        "ok": ok,
        "path": str(ART.relative_to(REPO).as_posix()),
        "role_fires": bool(role.get("fires")),
        "role": role.get("role"),
        "locus": role.get("locus"),
        "naive_fires": bool(naive.get("fires")),
        "patterns_present": [p for p in FORBIDDEN_PATTERNS if p in text],
        "missing_examples": missing,
    }
