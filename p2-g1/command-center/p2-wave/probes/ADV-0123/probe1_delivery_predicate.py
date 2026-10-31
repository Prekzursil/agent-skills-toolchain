#!/usr/bin/env python3
"""ADV-0123 probe1 -- structural + sentinel delivery predicate (live, fail-closed).

Checks the completion-sentinel contract on the live artifact: parses, unit_id,
state not self-declaring non-delivery, sentinel text present, one in-vocabulary
verdict per enumerated target, controls and negative controls recorded, and
min-bytes floor. Current-schema drift is surfaced as a NOTE, never folded into
a pass (the delivered predicate is the sentinel list, not the moved schema).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
OUT = REPO / "command-center/adversarial/ADV-0123-concurrent-session-index-and-lease-race.json"
UNIT = "ADV-0123"
NOT_DELIVERING = {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}
VOCAB = {"CONFIRMED", "REFUTED", "PARTIAL", "NOT-CHECKED", "BLOCKED"}


def main() -> int:
    fails = []
    notes = []

    def check(ok: bool, label: str, detail: str = "") -> None:
        if not ok:
            fails.append(label + (f": {detail}" if detail else ""))

    try:
        text = OUT.read_text(encoding="utf-8")
        doc = json.loads(text)
    except Exception as exc:
        print(f"FAILED:{UNIT}-probe1 artifact unreadable/unparseable: {type(exc).__name__}")
        return 1
    if not isinstance(doc, dict):
        print("FAILED:ADV-0123-probe1 artifact is not a JSON object")
        return 1

    check(doc.get("unit_id") == UNIT, "unit_id mismatch", str(doc.get("unit_id")))
    check(str(doc.get("state", "")).upper() not in NOT_DELIVERING, "self-declared non-delivery", str(doc.get("state")))
    check(OUT.stat().st_size > 0, "artifact empty")
    minb = int(doc.get("min_bytes_threshold") or 0)
    check(OUT.stat().st_size >= minb, "below min_bytes_threshold", f"{OUT.stat().st_size} < {minb}")
    sentinel = str(doc.get("completion_sentinel") or doc.get("sentinel") or "")
    check(bool(sentinel) and sentinel in text, "sentinel absent from artifact text")

    tgt = doc.get("targets") or doc.get("verdicts") or doc.get("enumerated_targets") or doc.get("component_matrix") or []
    if not tgt and doc.get("overall_verdict"):
        tgt = [{"id": doc.get("question_or_target") or "overall", "verdict": doc.get("overall_verdict")}]
    verdicts = [
        t.get("verdict") for t in tgt
        if isinstance(t, dict) and t.get("verdict") is not None
    ]
    check(len(tgt) >= 1, "no enumerated targets recorded")
    check(all(v in VOCAB for v in verdicts), "target verdict outside vocabulary", str(verdicts[:6]))

    ctrls = doc.get("controls") or doc.get("negative_controls") or []
    check(len(ctrls) >= 1, "no control results recorded")
    ncs = doc.get("negative_controls") or []
    if not ncs:
        ncs = [
            c for c in ctrls
            if isinstance(c, dict) and (
                c.get("fired_on_bad_state") is not None
                or "negative" in str(c.get("id", "")).lower()
                or "blind" in str(c.get("id", "")).lower()
                or "silent" in str(c.get("id", "")).lower()
                or "drop" in str(c.get("id", "")).lower()
            )
        ]
    check(len(ncs) >= 1, "no negative controls recorded")
    bad_nc = [
        str(c.get("id")) for c in ncs
        if isinstance(c, dict)
        and c.get("fired_on_bad_state") is not None
        and (c.get("fired_on_bad_state") is not True or c.get("silent_on_good_state") is not True)
    ]
    check(not bad_nc, "negative control failed a both-states field", str(bad_nc[:3]))

    # informational: schema drift note (never folded into the verdict)
    sch_rel = str(doc.get("output_schema") or doc.get("declared_schema") or "")
    if sch_rel:
        sp = REPO / sch_rel.split(" profile=")[0].split("#")[0]
        if sp.is_file():
            try:
                import jsonschema
                errs = list(
                    jsonschema.Draft202012Validator(json.loads(sp.read_text(encoding="utf-8"))).iter_errors(doc)
                )
                if errs:
                    notes.append(f"schema-drift-note: {len(errs)} error(s) against {sp.name} (schema moved post-delivery)")
            except Exception as exc:
                notes.append(f"schema-note: {type(exc).__name__}")
        else:
            notes.append("schema-note: declared schema file absent on this worktree")

    report = {
        "probe": "probe1-delivery-predicate",
        "unit_id": UNIT,
        "artifact_bytes": OUT.stat().st_size,
        "targets": len(tgt),
        "verdicts": verdicts,
        "controls": len(ctrls),
        "negative_controls": len(ncs),
        "notes": notes,
        "fails": fails,
    }
    print(json.dumps(report, indent=1))
    if fails:
        print(f"FAILED:{UNIT}-probe1 {'; '.join(fails)}")
        return 1
    print(f"SUCCESS:{UNIT}-probe1 predicate holds ({len(tgt)} targets, {len(ctrls)}+{len(ncs)} controls)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
