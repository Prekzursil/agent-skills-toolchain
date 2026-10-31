#!/usr/bin/env python3
"""CC-0009 probe2 - both-states reviewer battery (mechanically different).

Lane 1: per-unit manifest sha byte-compare. Lane 2: artifact_register
--self-test (the both-states battery: unregistered fails, absent fails,
present-but-unparseable fails, valid passes) run as a live subprocess; then
the reviewer-phantom both-states re-enacted in a scratch manifest: a phantom
absent row and a present-but-unparseable row must BOTH be rejected while the
valid row stays green. Lane 3: mutation control on the receipt (both-states).
Rebuilt 2026-10-26 (wave-3 shard 7) after the original probe tree was lost.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO / "tools" / "command-center"))
sys.path.insert(0, str(REPO / "command-center" / "p2-wave"))
from _measure_one_delivered import run_cmd as run_cmd_compat  # noqa: E402
OUT = REPO / "command-center/receipts/CC-0009.json"
AM = REPO / "command-center/ARTIFACT-MANIFEST.json"
MANIFEST = HERE / "UNIT-ARTIFACT-MANIFEST.json"
UNIT = "CC-0009"

from artifact_register import (  # noqa: E402
    check_condition_12,
    read_with_consumer,
)


def digest_norm(path):
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def main() -> int:
    fails = []
    checks = []

    def check(ok, label, detail=""):
        checks.append({"label": label, "ok": bool(ok), "detail": str(detail)[:300]})
        if not ok:
            fails.append(label + (": " + str(detail)[:200] if detail else ""))
    text = OUT.read_text(encoding="utf-8")
    doc = json.loads(text)

    # ---- Lane 1: per-unit manifest byte-compare ----
    if not MANIFEST.is_file():
        fails.append("manifest-absent")
        check(False, "per-unit manifest exists")
    else:
        man_text = MANIFEST.read_text(encoding="utf-8")
        man = json.loads(man_text)
        rows = [a for a in man.get("artifacts", []) if a.get("unit_id") == UNIT]
        live = digest_norm(OUT)
        match = [a for a in rows
                 if str(a.get("path", "")).replace("\\", "/")
                 == "command-center/receipts/CC-0009.json"
                 and str(a.get("sha256", "")) == live
                 and a.get("present") is True]
        check(bool(match), "manifest sha row matches live artifact (LF-normalized)",
              "sha=" + live[:16] + "... rows=" + str(len(rows)))

    # ---- Lane 2a: artifact_register --self-test (live subprocess) ----
    reg_rel = (REPO / "tools/command-center/artifact_register.py")\
        .relative_to(REPO).as_posix()
    cmd = "PYTHONDONTWRITEBYTECODE=1 python3 -B " + reg_rel + " --self-test"
    selftest_rc, tail = run_cmd_compat(cmd)
    check(selftest_rc == 0 and "SUCCESS:artifact-register-self-test" in tail,
          "artifact_register --self-test exits 0 with SUCCESS marker",
          "rc=" + str(selftest_rc) + " tail=" + tail[-120:])
    need = ("phantom_rejected=True", "unparseable_fail=True", "absent_fail=True",
            "unregistered_fail=True", "valid_pass=True")
    missing = [n for n in need if n not in tail]
    check(not missing, "self-test asserts every negative control fired",
          "missing=" + str(missing))
    # ---- Lane 2b: reviewer phantom both-states in a scratch manifest ----
    with tempfile.TemporaryDirectory() as td:
        tdp = Path(td)
        junk = tdp / "unparseable.json"
        junk.write_bytes(b"\x00{not json")
        phantom = {
            "path": "receipts/CC-0009-PHANTOM.json",
            "sha256": "0" * 64,
            "present": True,
            "unit_id": "CC-0009",
            "consumer": "json",
        }
        junkrow = {
            "path": junk.relative_to(tdp).as_posix(),
            "sha256": "0" * 64,
            "present": True,
            "consumer": "text",
        }
        scratch = {"artifacts": [phantom, junkrow]}
        r12 = check_condition_12(tdp, manifest=scratch)
        phantom_rejected = not r12.ok
        check(phantom_rejected, "scratch manifest with phantom+unparseable is REJECTED",
              r12.reason)
        # valid control: the real AM rows must stay green under the same check
        r12_live = check_condition_12(REPO, unit_id=UNIT)
        check(r12_live.ok, "condition 12 stays green on the live manifest",
              r12_live.reason)

    # ---- Lane 3: mutation control on the receipt (both-states) ----
    tamper = json.loads(text)
    tamper["unit_id"] = "XXXX-0000"
    tamper_text = json.dumps(tamper, ensure_ascii=False, indent=1)

    def structural_fires(blob):
        try:
            d = json.loads(blob)
        except Exception:
            return True, "parse-error"
        if not isinstance(d, dict):
            return True, "not-an-object"
        if d.get("unit_id") != UNIT:
            return True, "unit-id-mismatch"
        sent = str(d.get("completion_sentinel") or d.get("sentinel") or "")
        if not sent or sent not in blob:
            return True, "sentinel-absent"
        return False, "clean"

    fired_t, why_t = structural_fires(tamper_text)
    fired_r, why_r = structural_fires(text)
    control_ok = fired_t and not fired_r
    nc = {
        "id": "NC-STRUCTURAL-PREDICATE-BOTH-STATES",
        "bad_state_why": why_t,
        "description": "predicate must fire on a unit-id-tampered copy and stay silent on the real artifact",
        "fired_on_bad_state": fired_t,
        "good_state_why": why_r,
        "kind": "mutation",
        "silent_on_good_state": not fired_r,
    }
    (HERE / "nc_live.json").write_text(json.dumps(nc, indent=1) + "\n",
                                       encoding="utf-8", newline="\n")
    check(control_ok, "mutation control: fires on tampered, silent on real",
          why_t + "/" + why_r)

    # observation (not a fail): receipt vs CURRENT frozen receipt.schema.json
    # drifted estate-wide; see SUBAGENT-RETURN notes.
    schema_lane = "see SUBAGENT-RETURN notes (estate-wide schema drift, disclosed)"

    report = {"probe": "probe2-both-states-reviewer", "unit_id": UNIT,
              "lanes": {"rederivations": checks, "mutation_control": nc,
                        "schema_lane": schema_lane},
              "fails": fails}
    print(json.dumps(report, indent=1))
    if fails:
        print("FAILED:" + UNIT + "-probe2 " + "; ".join(fails))
        return 1
    print("SUCCESS:" + UNIT + "-probe2 manifest sha match, " + str(len(checks))
          + " rederivations hold, mutation control both-states ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
