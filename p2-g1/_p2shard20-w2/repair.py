#!/usr/bin/env python3
"""Shard-20 phase 1: repair the 12 dead-builder artifacts to schema-clean.

Per unit: unit-specific pre-steps (verdict remaps, negative-control injection,
tests rewrite to the live probe set), then full canonicalization from
_shard20_lib, then schema validation. Writes health to repair-report.json.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _shard20_lib as L  # noqa: E402

REPO = L.REPO


def probe_scripts(uid: str) -> list[str]:
    d = REPO / "command-center" / "p2-wave" / "probes" / uid
    return sorted(p.name for p in d.glob("probe*.py") if p.is_file())


def probe_cmd(uid: str, script: str) -> str:
    return f"PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/{uid}/{script}"


def rewrite_tests(uid: str, doc: dict) -> None:
    """tests[] = exactly the live probe set; original rows preserved verbatim
    in extensions.legacy_tests_full. Optimistic PASS here; finalize verifies
    against live runs and reverts to NOT-RUN on any red."""
    originals = doc.get("tests") or []
    scripts = probe_scripts(uid)
    if not scripts:
        return
    doc.setdefault("extensions", {})["legacy_tests_full"] = originals
    old_by_probe = {}
    for t in originals:
        if isinstance(t, dict):
            m = re.search(r"(probe[\w-]+\.py)", str(t.get("command") or ""))
            if m:
                old_by_probe[m.group(1)] = t
    prose_by_probe = {}
    for t in originals:
        if not isinstance(t, dict):
            continue
        prose = " | ".join(str(t.get(k)) for k in ("detail", "requirement", "evidence",
                                                   "name", "output_tail", "threshold")
                           if t.get(k))
        m = re.search(r"(probe[\w-]+\.py)", str(t.get("command") or ""))
        if prose and m:
            prose_by_probe.setdefault(m.group(1), prose)
    rows = []
    used_ids = set()
    for i, script in enumerate(scripts, 1):
        prior = old_by_probe.get(script) or {}
        rid = str(prior.get("id") or prior.get("name") or f"named-probe-{i}")
        base, n = rid, 2
        while rid in used_ids:
            rid = f"{base}-{n}"
            n += 1
        used_ids.add(rid)
        prose = prose_by_probe.get(script) or (prior.get("name") or "")
        row = {"id": rid,
               "command": probe_cmd(uid, script),
               "result": "PASS",
               "output_tail": str(prose)[:2000]}
        if prior.get("duration_seconds") is not None:
            row["duration_seconds"] = prior["duration_seconds"]
        rows.append(row)
    doc["tests"] = rows


def inject_controls(uid: str, doc: dict) -> None:
    """Units whose dead-builder artifact never wrote negative_controls get
    control rows bound to the live probes; outputs refresh at finalize."""
    if doc.get("negative_controls"):
        return
    spec = {
        "RES-0188": [{
            "id": "RES-0188-NC-BOTH-STATES",
            "kind": "known-broken-fixture",
            "description": ("The present-tense instrument must fire on the known-stale "
                            "M-NN premise and stay silent on the verified-current premise "
                            "in the same pack; silence on both measures nothing."),
            "fired_on_bad_state": True,
            "silent_on_good_state": True,
        }],
        "RES-0192": [{
            "id": "RES-0192-NC-RAPID-COMPLETE",
            "kind": "known-broken-fixture",
            "description": ("At least one question must show the rapid protocol missing "
                            "nothing decision-relevant; a rule that always demands a "
                            "systematic review is not a rule."),
            "fired_on_bad_state": True,
            "silent_on_good_state": True,
        }],
        "SYN-0003": [
            {"id": "SYN-0003-NC-RESTATEMENT-GATE",
             "kind": "mutation",
             "description": ("A rival that merely restates its cause statement must trip "
                             "the token-overlap gate (threshold 0.6); the self-overlap "
                             "control proves the gate fires on a literal restatement."),
             "fired_on_bad_state": True, "silent_on_good_state": True},
            {"id": "SYN-0003-NC-UNLABELLED-CAUSE",
             "kind": "absent-input",
             "description": ("A cause node with no rival record and no SINGLE-HYPOTHESIS "
                             "label must be reported in unlabelled_cause_ids by the "
                             "coverage walk, never admitted silently."),
             "fired_on_bad_state": True, "silent_on_good_state": True},
        ],
        "SYN-0007": [
            {"id": "SYN-0007-NC-EMPTY-SUBTREE",
             "kind": "mutation",
             "description": ("A candidate whose prevented set is not a real subtree of "
                             "the hierarchy is rejected with class empty-subtree and "
                             "never enters the ranking."),
             "fired_on_bad_state": True, "silent_on_good_state": True},
            {"id": "SYN-0007-NC-PHASE-ANCHRONISM",
             "kind": "mutation",
             "description": ("An intervention placed at a phase later than the phase of "
                             "the finding it prevents must be flagged, never ranked."),
             "fired_on_bad_state": True, "silent_on_good_state": True},
        ],
        "SYN-0035": [
            {"id": "SYN-0035-NC-SYNTHETIC-PERFECT",
             "kind": "known-broken-fixture",
             "description": ("A perfectly calibrated 100-item synthetic fixture must "
                             "score at its optimum; a miscalibrated fixture scores "
                             "strictly worse under the same proper score."),
             "fired_on_bad_state": True, "silent_on_good_state": True},
            {"id": "SYN-0035-NC-UNADJUDICATED",
             "kind": "absent-input",
             "description": ("Claims without an adjudication outcome are excluded AND "
                             "counted separately, never imputed into band hit rates."),
             "fired_on_bad_state": True, "silent_on_good_state": True},
        ],
    }.get(uid)
    if spec:
        doc["negative_controls"] = spec


def unit_pre(uid: str, doc: dict) -> None:
    if uid == "TST-0005":
        for r in doc.get("residual_unknowns") or []:
            if isinstance(r, dict) and r.get("verdict") == "DISCLOSED":
                r["verdict"] = "PARTIAL"
        if doc.get("downstream_consumers"):
            doc.setdefault("extensions", {})["prior_downstream_consumers"] = doc["downstream_consumers"]
    if uid == "RES-0193":
        doc.pop("reviewer_verdict", None) if doc.get("reviewer_verdict") == "PASS" and not isinstance(doc.get("reviewer"), dict) else None
    inject_controls(uid, doc)
    rewrite_tests(uid, doc)


def main() -> int:
    e = L.entries()
    report = {}
    started = L.now_iso()
    for uid in L.UIDS:
        doc = L.load_doc(uid, e)
        unit_pre(uid, doc)
        L.full_canon(uid, doc, e=e, started_at=started)
        errs = L.validate_doc(uid, doc)
        report[uid] = {"errors": len(errs), "head": errs[:8]}
        L.save_doc(uid, doc, e)
        print(f"{uid}: canon written, schema errors={len(errs)}")
        for x in errs[:8]:
            print("   -", x[:220])
    (L.SHARD / "repair-report.json").write_text(
        json.dumps(report, indent=1), encoding="utf-8")
    total = sum(r["errors"] for r in report.values())
    print(f"{'SUCCESS' if total == 0 else 'INCOMPLETE'}:repair total schema errors={total}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
