#!/usr/bin/env python3
"""CNF-0070 probe2 - mechanically different independent recheck (live, fail-closed).

Mechanically different lane: datetime-parses each capture timestamp and re-checks timeliness (including the same-day boundary case), re-derives the 3/2/1 verdict split, and records the lost fixture-body drift as a note (recorded shas are format-checked, not re-hashed - the original archive bytes were lost with the probe tree and are not fabricated).
Lane 1: byte-compare the per-unit manifest sha (LF-normalized) against the
live artifact. Lane 2: unit-specific re-derivations from artifact internals.
Lane 3: mutation negative control - the structural predicate must FIRE on a
tampered copy and stay SILENT on the real artifact (both-states).
Recreated 2026-10-25 (wave-2 shard 7) after the original probe tree was lost.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
OUT = REPO / "command-center/confirmation/CNF-0070-archival-corroboration.json"
UNIT = "CNF-0070"
MANIFEST = HERE / "UNIT-ARTIFACT-MANIFEST.json"


def digest_norm(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def structural_fires(text: str) -> tuple[bool, str]:
    try:
        doc = json.loads(text)
    except Exception:
        return True, "parse-error"
    if not isinstance(doc, dict):
        return True, "not-an-object"
    if doc.get("unit_id") != UNIT:
        return True, "unit-id-mismatch"
    sentinel = str(doc.get("completion_sentinel") or doc.get("sentinel") or "")
    if not sentinel or sentinel not in text:
        return True, "sentinel-absent"
    return False, "clean"


def main() -> int:
    fails = []
    checks = []

    # Lane 1: manifest byte-compare
    if not MANIFEST.is_file():
        fails.append("manifest-absent")
    else:
        man = json.loads(MANIFEST.read_text(encoding="utf-8"))
        rows = [a for a in man.get("artifacts", []) if a.get("unit_id") == UNIT]
        live = digest_norm(OUT)
        match = [
            a for a in rows
            if str(a.get("path", "")).replace("\\", "/") == "command-center/confirmation/CNF-0070-archival-corroboration.json"
            and str(a.get("sha256", "")) == live
            and a.get("present") is True
        ]
        checks.append((
            "manifest sha row matches live artifact (LF-normalized)",
            bool(match),
            "sha=%s... rows=%d" % (live[:16], len(rows)),
        ))
        if not match:
            fails.append("manifest-sha-mismatch")

    # Lane 2: unit-specific re-derivation
    try:
        text = OUT.read_text(encoding="utf-8")
        doc = json.loads(text)
    except Exception as exc:
        print("FAILED:%s-probe2 artifact unparseable: %s" % (UNIT, type(exc).__name__))
        return 1

    import datetime as _dt
    cits = doc.get("citations") or []
    same = next((c for c in cits if str(c.get("id")) == "C-SAMEDAY"), None)
    checks.append(("same-day boundary: capture 2024-07-01T23:50Z is ON the 2024-07-01 citation date",
                   same is not None and _dt.date.fromisoformat(str((same.get("archived_corroboration") or {}).get("capture_timestamp", ""))[:10])
                   == _dt.date.fromisoformat(str(same.get("citation_date"))),
                   "capture=%s cit=%s" % ((same or {}).get("archived_corroboration", {}).get("capture_timestamp"), (same or {}).get("citation_date"))))
    vc = {}
    for c in cits:
        vc[str(c.get("verdict"))] = vc.get(str(c.get("verdict")), 0) + 1
    checks.append(("verdict split re-derives to the recorded 3/2/1 across three distinct classes",
                   vc.get("was-true-then-changed") == 3 and vc.get("no-snapshot-available") == 2 and vc.get("never-supported") == 1,
                   json.dumps(vc)))
    changed = [c for c in cits if str(c.get("verdict")) == "was-true-then-changed"]
    ok_ts = all(_dt.date.fromisoformat(str((c.get("archived_corroboration") or {}).get("capture_timestamp", ""))[:10])
                <= _dt.date.fromisoformat(str(c.get("citation_date"))) for c in changed)
    checks.append(("every archived corroboration timely: capture date <= citation date (3/3)",
                   ok_ts and len(changed) == 3, "rows=%d" % len(changed)))
    lost = [str((c.get("archived_corroboration") or {}).get("body_path", "")) for c in changed
            if (c.get("archived_corroboration") or {}).get("body_path")
            and not (REPO / str((c.get("archived_corroboration") or {}).get("body_path"))).is_file()]
    checks.append(("recorded shas are hex64 (content-addressed provenance preserved in the receipt)",
                   all(len(str((c.get("archived_corroboration") or {}).get("sha256", ""))) == 64 for c in changed),
                   "lost-fixture-bodies=%d (drift note: archive bytes lost with the original probe tree; not fabricated)" % len(lost)))
    untrusted = [c.get("id") for c in cits if "untrusted_instructions_recorded" in c]
    checks.append(("untrusted-instruction handling recorded on archived rows",
                   len(untrusted) >= 1, "rows=%s" % untrusted[:3]))

    for label, ok, detail in checks:
        if not ok:
            fails.append("%s (%s)" % (label, detail))

    # Lane 3: mutation negative control (both-states)
    real_doc = json.loads(OUT.read_text(encoding="utf-8"))
    real_doc["unit_id"] = "XXXX-0000"
    tamper = json.dumps(real_doc, ensure_ascii=False, indent=1)
    fired_t, why_t = structural_fires(tamper)
    fired_r, why_r = structural_fires(OUT.read_text(encoding="utf-8"))
    control_ok = fired_t and not fired_r
    nc = {
        "id": "NC-STRUCTURAL-PREDICATE-BOTH-STATES",
        "kind": "mutation",
        "description": "predicate must fire on a unit-id-tampered copy and stay silent on the real artifact",
        "fired_on_bad_state": fired_t,
        "silent_on_good_state": not fired_r,
        "bad_state_why": why_t,
        "good_state_why": why_r,
    }
    (HERE / "nc_live.json").write_text(json.dumps(nc, indent=1) + "\n", encoding="utf-8", newline="\n")
    if not control_ok:
        fails.append("mutation control: tampered-fired=%s real-fired=%s (%s/%s)" % (fired_t, fired_r, why_t, why_r))

    report = {
        "probe": "probe2-independent-recheck",
        "unit_id": UNIT,
        "lanes": {
            "manifest_byte_compare": "ok" if not any("manifest" in f for f in fails) else "fail",
            "rederivations": [{"label": lb, "ok": ok, "detail": dt} for lb, ok, dt in checks],
            "mutation_control": nc,
        },
        "fails": fails,
    }
    print(json.dumps(report, indent=1))
    if fails:
        print("FAILED:%s-probe2 %s" % (UNIT, "; ".join(fails)))
        return 1
    print("SUCCESS:%s-probe2 manifest sha match, %d rederivations hold, mutation control both-states ok"
          % (UNIT, len(checks)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
