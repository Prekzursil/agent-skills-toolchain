#!/usr/bin/env python3
"""CC-0012 probe2 - migration round-trip on real pre-freeze data.

Lane 1: manifest sha byte-compare. Lane 2: m0001_catalog_v2_v3 executed
up+down on the REAL pre-freeze catalog slice fixture into scratch out-paths;
byte-identical round-trip asserted and the after/restored hashes cross-checked
against the receipt's migration block AND the proof files left on disk.
Lane 3: mutation control (both-states). Rebuilt 2026-10-26 (wave-3 shard 7).
"""
from __future__ import annotations

import hashlib
import json
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO / "command-center"))
OUT = REPO / "command-center/receipts/CC-0012.json"
MANIFEST = HERE / "UNIT-ARTIFACT-MANIFEST.json"
UNIT = "CC-0012"

from freeze.lib import apply_migration_to_file, load_migrations  # noqa: E402


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
    # ---- Lane 1: manifest byte-compare ----
    if not MANIFEST.is_file():
        fails.append("manifest-absent")
        check(False, "per-unit manifest exists")
    else:
        man = json.loads(MANIFEST.read_text(encoding="utf-8"))
        rows = [a for a in man.get("artifacts", []) if a.get("unit_id") == UNIT]
        live = digest_norm(OUT)
        match = [a for a in rows
                 if str(a.get("path", "")).replace("\\", "/")
                 == "command-center/receipts/CC-0012.json"
                 and str(a.get("sha256", "")) == live
                 and a.get("present") is True]
        check(bool(match), "manifest sha row matches live artifact (LF-normalized)",
              "sha=" + live[:16] + "... rows=" + str(len(rows)))

    # ---- Lane 2: m0001 up/down on the real pre-freeze fixture ----
    mig = doc.get("migration") or {}
    fixture = REPO / "command-center/freeze/fixtures/prefreeze_catalog_slice.json"
    check(fixture.is_file(), "pre-freeze fixture exists on disk", str(fixture))
    fdoc = json.loads(fixture.read_text(encoding="utf-8"))
    check(fdoc.get("schema_version") == 2,
          "fixture is real pre-freeze data (schema_version 2)",
          str(fdoc.get("schema_version")))
    migs = load_migrations(REPO)
    m1 = [m for m in migs if m.id == "m0001_catalog_v2_v3"]
    check(len(m1) == 1, "m0001_catalog_v2_v3 loadable", str([m.id for m in migs]))
    with tempfile.TemporaryDirectory() as td:
        tdp = Path(td)
        after_p = tdp / "after.json"
        restored_p = tdp / "restored.json"
        res = apply_migration_to_file(m1[0], fixture, after_p, restored_p)
        check(res["byte_identical"] is True,
              "down(up(fixture)) byte-identical round-trip on real pre-freeze data")
        check(res["after_schema_version"] == 3,
              "up() moves the fixture to schema_version 3",
              str(res.get("after_schema_version")))
        check(res["after_sha256"] == mig.get("after_sha256"),
              "live after.json sha equals the receipt's recorded after_sha256",
              res["after_sha256"][:16] + " vs " + str(mig.get("after_sha256"))[:16])
        check(res["restored_sha256"] == mig.get("restored_sha256"),
              "live restored.json sha equals the receipt's recorded restored_sha256")
    # ---- proof files on disk cross-checked against the receipt ----
    for key, rel in (("after_path", "command-center/freeze/proof/after.json"),
                     ("restored_path", "command-center/freeze/proof/restored.json")):
        p = REPO / rel
        check(p.is_file(), "proof file exists: " + rel)
        if p.is_file():
            sha = digest_norm(p)
            want = mig.get("after_sha256" if key == "after_path" else "restored_sha256")
            check(sha == want, "proof file sha equals the receipt record: " + rel,
                  sha[:16] + " vs " + str(want)[:16])
    check((REPO / "command-center/freeze/proof/before.json").is_file()
          and (REPO / "command-center/freeze/proof/roundtrip.json").is_file(),
          "before.json and roundtrip.json proof artifacts present")

    # ---- Lane 3: mutation control (both-states) ----
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
        "kind": "mutation",
        "description": "predicate must fire on a unit-id-tampered copy and stay silent on the real artifact",
        "fired_on_bad_state": fired_t,
        "silent_on_good_state": not fired_r,
        "bad_state_why": why_t,
        "good_state_why": why_r,
    }
    (HERE / "nc_live.json").write_text(json.dumps(nc, indent=1) + "\n",
                                       encoding="utf-8", newline="\n")
    check(control_ok, "mutation control: fires on tampered, silent on real",
          why_t + "/" + why_r)

    report = {"probe": "probe2-migration-roundtrip", "unit_id": UNIT,
              "lanes": {"rederivations": checks, "mutation_control": nc},
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
