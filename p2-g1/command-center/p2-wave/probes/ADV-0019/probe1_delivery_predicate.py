#!/usr/bin/env python3
"""ADV-0019 probe1 -- builder-side delivery predicate (live, fail-closed).

Checks the measured DELIVERED bar: artifact parses, not self-declared
BLOCKED/FAILED/SEVERED/TIMEOUT, unit_id, completion sentinel present, one
legal verdict per enumerated target/evidence row, controls recorded, named
probes recorded, min-bytes threshold. The receipt_core SUCCESS battery
(reviewer PASS+independent, downstream-executed, zero open P0/P1) is the
independent reviewer's closure job and is deliberately not fabricated by a
builder: the builder terminal is BLOCKED/reviewer-absent on the receipt
(program contract). This predicate fails closed on any builder-side gap.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
OUT = REPO / "command-center/adversarial/ADV-0019-retired-capability-dead-references.json"
SENTINEL = json.loads(r'''"SUCCESS:ADV-0019 emitted ONLY when the artifact at output_path exists, is non-empty, parses against output_schema, records BOTH named probes verbatim with their raw output, carries exactly one verdict from {CONFIRMED|REFUTED|PARTIAL|NOT-CHECKED|BLOCKED} per enumerated target, and records the result of every listed control/negative test. Any missing control downgrades the unit's verdicts to NOT-CHECKED. Otherwise FAILED:ADV-0019 <reason>."''')
NOT_DELIVERING = {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}
LEGAL = {"CONFIRMED", "REFUTED", "PARTIAL", "NOT-CHECKED", "BLOCKED"}
UNIT = "ADV-0019"
TARGETS_KEY = 'verdicts'
MIN_TARGETS = 1
CONTROLS_KEYS = ['controls']
EVIDENCE_MODE = False
MIN_BYTES = 1024

fails: list[str] = []


def chk(ok: bool, label: str, detail: str = "") -> None:
    if not ok:
        fails.append(label + (": " + detail if detail else ""))


def main() -> int:
    try:
        text = OUT.read_text(encoding="utf-8")
        doc = json.loads(text)
    except Exception as exc:
        print("FAILED:ADV-0019-probe1 artifact-unreadable:" + type(exc).__name__)
        return 1
    chk(OUT.stat().st_size >= MIN_BYTES, "artifact-under-min-bytes",
        str(OUT.stat().st_size))
    st = str(doc.get("state") or "").upper()
    chk(st not in NOT_DELIVERING, "self-declared", st)
    uid_field = str(doc.get("unit_id") or doc.get("id") or "")
    chk(uid_field == UNIT, "unit-id", uid_field)
    chk(SENTINEL in text, "completion-sentinel-absent")

    if TARGETS_KEY is not None:
        targets = doc.get(TARGETS_KEY) or []
        chk(len(targets) >= MIN_TARGETS, "targets-under-minimum", str(len(targets)))
        for i, t in enumerate(targets):
            v = str(t.get("verdict") or "")
            chk(v in LEGAL, "target-verdict-illegal", f"[{i}]={v!r}")
        verdicts = [str(t.get("verdict")) for t in targets]
        if verdicts and len(set(verdicts)) != len(verdicts):
            # duplicates are allowed across targets, but zero-verdict rows are not
            chk(all(verdicts), "empty-verdict-row")

    if EVIDENCE_MODE:
        ev = doc.get("evidence") or []
        chk(len(ev) >= 2, "evidence-under-minimum", str(len(ev)))
        for i, item in enumerate(ev):
            probes = item.get("probes") or []
            roles = {p.get("role") for p in probes if isinstance(p, dict)}
            fps = {p.get("fingerprint") for p in probes if isinstance(p, dict)}
            v = str(item.get("verdict") or "")
            chk(len(probes) >= 1, f"evidence[{i}]-probes-absent")
            if v in ("CONFIRMED", "REFUTED"):
                # two mechanically independent signals for decisive rows;
                # degraded rows (PARTIAL/NOT-CHECKED) honestly carry the
                # single leg that ran - that is what makes them degraded.
                chk("source" in roles, f"evidence[{i}]-source-probe-absent")
                chk("verifier" in roles, f"evidence[{i}]-verifier-probe-absent")
            chk(len(fps) == len(probes) and len(probes) >= 1,
                f"evidence[{i}]-fingerprints-not-distinct")

    controls_present = any(
        isinstance(doc.get(k), (list, dict)) and len(doc.get(k) or {}) > 0
        for k in CONTROLS_KEYS
    )
    chk(controls_present, "controls-absent", ",".join(CONTROLS_KEYS))

    probe_cmds = re.findall(
        r"command-center/p2-wave/probes/ADV-0019/[A-Za-z0-9_./-]+\.py",
        text,
    )
    np_entries = [p for p in (doc.get("named_probes") or [])
                  if isinstance(p, dict) and (p.get("command") or p.get("raw_output"))]
    chk(len(set(probe_cmds)) >= 2 or len(np_entries) >= 2,
        "named-probes-under-recorded-minimum",
        f"cmds={len(set(probe_cmds))} entries={len(np_entries)}")

    if fails:
        for f in fails[:10]:
            print("FAILED:ADV-0019-probe1 " + f)
        return 1
    print("SUCCESS:ADV-0019-probe1 delivery predicate: parses, state=" + st
          + ", sentinel present, verdicts legal, controls recorded")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
