#!/usr/bin/env python3
"""Probe 2: every FORBIDDEN cell uses the closed reason vocabulary.

Mechanically different from probe 1 (pair counting). This probe inspects
reason tokens, requires at least one FORBIDDEN cell, and runs two mutants:
an invented reason, and an all-ALLOWED map (the unread-copyleft control).
It also calls compose_pair on a proprietary+GPL pair so refusal happens at
the fusion entry point, not only by inspecting the precomputed matrix.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools"))

from foundry.compat_map import (  # noqa: E402
    FORBIDDEN_REASONS,
    all_allowed_mutant,
    build_map,
    compose_pair,
    forbidden_vocab_report,
    inject_illegal_reason,
    load_components,
    load_licence_matrix,
)

RECEIPT = REPO / "command-center" / "receipts" / "IMP-0175.json"
SIDECAR = REPO / "command-center" / "foundry" / "merge-compatibility-map.json"


def _published_map() -> dict | None:
    if SIDECAR.is_file() and SIDECAR.stat().st_size > 0:
        doc = json.loads(SIDECAR.read_text(encoding="utf-8"))
        if doc.get("cells"):
            return doc
    if RECEIPT.is_file():
        doc = json.loads(RECEIPT.read_text(encoding="utf-8"))
        report = doc.get("report") or doc.get("merge_compatibility_map")
        if isinstance(report, dict) and report.get("cells"):
            return report
    return None


def main() -> int:
    live = build_map(repo=REPO)
    vocab_live = forbidden_vocab_report(live)
    invented = forbidden_vocab_report(inject_illegal_reason(live, "BECAUSE_VIBES"))
    wiped = forbidden_vocab_report(all_allowed_mutant(live))

    comps, _ = load_components(REPO)
    matrix, _ = load_licence_matrix(REPO)
    by_id = {c["id"]: c for c in comps}
    fusion_cell = compose_pair(
        by_id["stage.proprietary-packager"], by_id["stage.airgap-auditor"], matrix
    )

    published = _published_map()
    vocab_pub = forbidden_vocab_report(published) if published else None
    receipt_ok = None
    if RECEIPT.is_file():
        text = RECEIPT.read_text(encoding="utf-8")
        receipt_ok = (
            "SUCCESS:IMP-0175" in text
            and vocab_pub is not None
            and vocab_pub["vocab_ok"] is True
        )

    both_states = (
        vocab_live["vocab_ok"] is True
        and invented["vocab_ok"] is False
        and wiped["vocab_ok"] is False
        and fusion_cell["reason"] == "LICENCE_FUSION_FORBIDDEN"
    )
    payload = {
        "probe": "probe2-forbidden-vocab",
        "unit_id": "IMP-0175",
        "closed_set": sorted(FORBIDDEN_REASONS),
        "forbidden_count": vocab_live["forbidden_count"],
        "illegal_reasons": vocab_live["illegal_reasons"],
        "vocab_ok": vocab_live["vocab_ok"],
        "invented_reason_rejected": invented["vocab_ok"] is False
        and any(i.get("reason") == "BECAUSE_VIBES" for i in invented["illegal_reasons"]),
        "all_allowed_rejected": wiped["vocab_ok"] is False,
        "fusion_entry_pair": {
            "from": fusion_cell["from"],
            "to": fusion_cell["to"],
            "verdict": fusion_cell["verdict"],
            "reason": fusion_cell["reason"],
        },
        "receipt_ok": receipt_ok,
        "pass": both_states and (receipt_ok is not False),
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    if not vocab_live["vocab_ok"]:
        print("FAILED:IMP-0175-probe2 FORBIDDEN reasons not a closed vocabulary")
        return 1
    if invented["vocab_ok"]:
        print("FAILED:IMP-0175-probe2 invented reason was accepted")
        return 1
    if wiped["vocab_ok"]:
        print("FAILED:IMP-0175-probe2 all-ALLOWED map accepted (copyleft unread)")
        return 1
    if fusion_cell["reason"] != "LICENCE_FUSION_FORBIDDEN":
        print("FAILED:IMP-0175-probe2 fusion entry point did not refuse proprietary+GPL")
        return 1
    if receipt_ok is False:
        print("FAILED:IMP-0175-probe2 published map vocabulary mismatch")
        return 1
    print(
        f"forbidden={vocab_live['forbidden_count']} "
        f"invented_rejected={invented['vocab_ok'] is False} "
        f"all_allowed_rejected={wiped['vocab_ok'] is False}"
    )
    print("SUCCESS:IMP-0175-probe2 FORBIDDEN reasons are a closed vocabulary")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
