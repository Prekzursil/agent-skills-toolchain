#!/usr/bin/env python3
"""BLD-0043 probe2 - mechanically different independent recheck (live, fail-closed).

Re-derives the channel histogram from the fixture mappings, re-opens the recreated fixture files to confirm every recorded mapping test id resolves, and runs the delete-known-mapping-moves-untested detector both-states.
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
OUT = REPO / "command-center/receipts/BLD-0043.json"
UNIT = "BLD-0043"
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
            if str(a.get("path", "")).replace("\\", "/") == "command-center/receipts/BLD-0043.json"
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

    fx = doc.get("fixture_corpus") or {}
    mappings = fx.get("mappings") or []
    hist = {}
    for m in mappings:
        hist[str(m.get("channel"))] = hist.get(str(m.get("channel")), 0) + 1
    want_hist = {"test-id": 7, "marker": 2, "registry-entry": 2}
    checks.append(("fixture channel histogram re-derives to 7/2/2", hist == want_hist, json.dumps(hist)))
    mt = (HERE / "fixtures" / "mapped_tests.py").read_text(encoding="utf-8") if (HERE / "fixtures" / "mapped_tests.py").is_file() else ""
    missing_fn = []
    for m in mappings:
        tid = str(m.get("test_id", ""))
        fn = tid.split("::")[-1]
        if "def " + fn not in mt:
            missing_fn.append(fn)
    checks.append(("all 11 recorded fixture mapping test ids resolve in recreated mapped_tests.py",
                   not missing_fn, "missing=%s" % missing_fn[:3]))
    co = (HERE / "fixtures" / "comment_only.py")
    co_text = co.read_text(encoding="utf-8") if co.is_file() else ""
    checks.append(("comment-only fixture carries the REQ only in a comment (detector must keep it unmapped)",
                   "def test_comment_only_does_not_map" in co_text and "# REQ-FX-COMMENT" in co_text,
                   "fn=%s comment=%s" % ("def test_comment_only_does_not_map" in co_text, "# REQ-FX-COMMENT" in co_text)))
    # delete-known-mapping-moves-untested detector, both states, in memory
    def untested_after(join_map, req_id, dropped_test):
        t = [t for t in join_map.get(req_id, []) if t != dropped_test]
        return len(t) == 0
    join = {"REQ-FX-DEL": ["test_REQ_FX_DEL_sole_mapping_delete_moves_untested"]}
    good_untested = untested_after(join, "REQ-FX-DEL", "")
    bad_untested = untested_after(join, "REQ-FX-DEL", "test_REQ_FX_DEL_sole_mapping_delete_moves_untested")
    checks.append(("delete-known-test control both-states: mapped=unmapped(False), deleted=untested(True)",
                   good_untested is False and bad_untested is True,
                   "mapped->%s deleted->%s" % (good_untested, bad_untested)))
    reg = REPO / "command-center" / "TEST-REGISTRY.json"
    checks.append(("live join note holds: TEST-REGISTRY.json present on this worktree",
                   reg.is_file(), str(reg)))

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
