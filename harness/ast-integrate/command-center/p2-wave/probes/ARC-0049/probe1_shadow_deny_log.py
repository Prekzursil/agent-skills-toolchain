#!/usr/bin/env python3
"""Named probe 1: shadow deny-log event counts (different field than probe 2).

Probe 2 reads grant-document sha256 restore. This probe reads would-have-blocked
counts on live transcripts plus an injected-PowerShell detector control.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import derive as D  # noqa: E402
import observe as O  # noqa: E402
import payload as P  # noqa: E402
import shadow as S  # noqa: E402

ART = REPO / "command-center/phase3/A7/MIGRATION.json"


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        print("FAILED:ARC-0049-probe1 migration artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("unit_id") != "ARC-0049":
        print("FAILED:ARC-0049-probe1 unit_id", doc.get("unit_id"))
        return 1
    if "SUCCESS:ARC-0049" not in json.dumps(doc):
        print("FAILED:ARC-0049-probe1 sentinel absent")
        return 1
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED"}:
        print("FAILED:ARC-0049-probe1 self-declared", doc.get("state"))
        return 1

    sample = P.sample_rows(doc)
    if len(sample) != 10:
        print(f"FAILED:ARC-0049-probe1 sample_size={len(sample)} want=10")
        return 1

    scan = O.scan_transcripts()
    live_rows = D.derive_sample(scan)
    live_by = {r["capability_id"]: r for r in live_rows}
    target = live_by[D.ROLLBACK_CAPABILITY]
    target["replay_calls"] = D.mapped_observed(target)
    current = list(target["declared"])
    proposed = S.drop_perm(current, D.DROP_CANDIDATE)
    live_gate = S.may_tighten(
        target["capability_id"], current, proposed, target["replay_calls"]
    )
    early = S.may_tighten(
        target["capability_id"],
        current,
        S.drop_perm(current, D.EARLY_TIGHTEN_PERM),
        target["replay_calls"],
    )
    detector = S.detector_control(target, D.DROP_CANDIDATE)

    if live_gate["would_have_blocked"] != 0 or not live_gate["allowed"]:
        print("FAILED:ARC-0049-probe1 live candidate drop is not shadow-clean")
        print(json.dumps(live_gate, indent=2)[:2000])
        return 1
    if early["allowed"] or early["would_have_blocked"] < 1:
        print("FAILED:ARC-0049-probe1 early tighten was not refused")
        print(json.dumps(early, indent=2)[:2000])
        return 1
    if not detector["fired_on_injected"]:
        print("FAILED:ARC-0049-probe1 detector silent on injected PowerShell")
        print(json.dumps(detector, indent=2)[:2000])
        return 1

    recorded = P.named_test(doc, "shadow_mode_gate")
    if recorded.get("would_have_blocked_on_live_candidate") != 0:
        print("FAILED:ARC-0049-probe1 artifact shadow count drift")
        return 1
    if not recorded.get("refused_early_tighten"):
        print("FAILED:ARC-0049-probe1 artifact missing refused_early_tighten")
        return 1
    if not recorded.get("detector_fired_on_injected"):
        print("FAILED:ARC-0049-probe1 artifact missing detector fire")
        return 1
    if recorded.get("capability_id") != D.ROLLBACK_CAPABILITY:
        print("FAILED:ARC-0049-probe1 artifact capability drift")
        return 1

    art_ids = [r.get("capability_id") for r in sample]
    if art_ids != list(D.SAMPLE_IDS):
        print("FAILED:ARC-0049-probe1 sample id drift", art_ids)
        return 1

    out = {
        "probe": "probe1-shadow-deny-log",
        "unit_id": "ARC-0049",
        "would_have_blocked_on_live_candidate": live_gate["would_have_blocked"],
        "early_tighten_would_have_blocked": early["would_have_blocked"],
        "refused_early_tighten": True,
        "detector_fired_on_injected": True,
        "transcript_files": scan["files"],
        "tool_events": scan["tool_events"],
        "pass": True,
    }
    print(json.dumps(out, sort_keys=True))
    print(
        f"shadow_blocked={live_gate['would_have_blocked']} "
        f"early_blocked={early['would_have_blocked']} "
        f"detector={detector['fired_on_injected']}"
    )
    print("SUCCESS:ARC-0049-probe1 shadow deny-log and injected detector")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
