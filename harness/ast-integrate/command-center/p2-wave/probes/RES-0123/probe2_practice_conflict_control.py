#!/usr/bin/env python3
"""Probe 2: flag plain-reading tensions with currently running practices (both-states)."""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from common import OUT, SENTINEL  # noqa: E402
from model import compute_conflicts, locate_quotes, practices  # noqa: E402


def fail(msg: str) -> int:
    print(f"FAILED:RES-0123-probe2 {msg}")
    return 1


def load_captures() -> dict[str, dict]:
    out: dict[str, dict] = {}
    for meta in (HERE / "captures").glob("*.meta.json"):
        rec = json.loads(meta.read_text(encoding="utf-8"))
        text_path = HERE / "captures" / f"{rec['id']}.txt"
        rec["text"] = text_path.read_text(encoding="utf-8") if text_path.is_file() else ""
        rec["http_status"] = rec.get("http_status")
        out[rec["id"]] = rec
    return out


def main() -> int:
    if not OUT.is_file():
        return fail("artifact missing")
    text = OUT.read_text(encoding="utf-8")
    if SENTINEL not in text:
        return fail("sentinel absent")
    doc = json.loads(text)
    if doc.get("no_legal_conclusion") is not True:
        return fail("legal conclusion leaked")
    for blob in json.dumps(doc.get("conflicts_with_current_practice") or []).lower().split("verdict"):
        pass
    banned = ("is a violation", "violates the terms", "non-compliant", "we conclude this is illegal")
    conf_text = json.dumps(doc.get("conflicts_with_current_practice") or []).lower()
    if any(b in conf_text for b in banned):
        return fail("conflict list rendered a compliance verdict")

    captures = load_captures()
    quotes = locate_quotes(captures)
    live_p = practices()
    live = compute_conflicts(live_p, quotes)
    live_ids = {c["id"] for c in live}
    art_ids = {c["id"] for c in (doc.get("conflicts_with_current_practice") or []) if isinstance(c, dict)}
    if live_ids != art_ids:
        return fail(f"artifact conflicts {sorted(art_ids)} != recomputed {sorted(live_ids)}")
    if "C-CURSOR-AUP-AUTOMATION-VS-UNATTENDED-CLI" not in live_ids:
        return fail("live unattended-CLI tension silent")
    if any(c["practice_id"] == "multi-account-rotation" for c in live):
        return fail("live rotator tension on a non-running practice")

    off = copy.deepcopy(live_p)
    for row in off:
        if row["id"] == "cursor-unattended-cli":
            row["running"] = False
    off_ids = {c["id"] for c in compute_conflicts(off, quotes)}
    if "C-CURSOR-AUP-AUTOMATION-VS-UNATTENDED-CLI" in off_ids:
        return fail("cleared unattended practice still flagged")
    if off_ids == live_ids:
        return fail("both-states silent: clearing unattended CLI did not drop a conflict")

    planted = copy.deepcopy(live_p)
    for row in planted:
        if row["id"] == "multi-account-rotation":
            row["running"] = True
    planted_ids = {c["id"] for c in compute_conflicts(planted, quotes)}
    if "C-ANTHROPIC-AUP-MULTI-ACCOUNT-VS-ROTATION" not in planted_ids:
        return fail("planted rotator did not flag Anthropic multi-account clause")
    if "C-OPENAI-LIMITS-VS-ROTATION" not in planted_ids:
        return fail("planted rotator did not flag OpenAI rate-limit clause")
    if "C-ANTHROPIC-AUP-MULTI-ACCOUNT-VS-ROTATION" in live_ids:
        return fail("live state already had planted rotator flag")

    print(
        f"live_conflicts={sorted(live_ids)} "
        f"unattended_off_dropped={('C-CURSOR-AUP-AUTOMATION-VS-UNATTENDED-CLI' not in off_ids)} "
        f"rotator_planted={('C-ANTHROPIC-AUP-MULTI-ACCOUNT-VS-ROTATION' in planted_ids)}"
    )
    print("SUCCESS:RES-0123-probe2 practice-conflict both-states")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
