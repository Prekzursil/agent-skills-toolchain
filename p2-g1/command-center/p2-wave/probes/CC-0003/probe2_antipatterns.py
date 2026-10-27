#!/usr/bin/env python3
"""Named probe 2 (CC-0003): the three spec anti-patterns, mechanically
different from the table-driven authoring probe; plus fanin import identity
and live-receipt liveness checks.

Spec line 10646: exit code zero alone is never success; a plausible digest is
not a receipt; a file path in text is not proof the file exists. This probe
attacks the reducer with each anti-pattern and requires INCOMPLETE.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "command-center" / "p2-wave"))
import scenario as S  # noqa: E402
import _p2lib as P  # noqa: E402

REAL = "command-center/receipts/CC-0003.json"
CATALOG_SCHEMA = "command-center/schema/receipt.schema.json"


def ap1_exit_zero_alone() -> tuple[bool, str]:
    fx = S.Fixture()
    try:
        fx.art_path.unlink()  # artifact gone...
        r = S.CP.evaluate(
            fx.receipt,
            fx.opts(),
            process={"exit_code": 0, "stdout": "all green"},
        )
        ok = (
            r.verdict is not S.CP.Verdict.COMPLETE
            and r.process_exit_code == 0
        )
        detail = "verdict=%s process_exit_code=%s (exit zero alone)" % (
            r.verdict.value, r.process_exit_code)
    finally:
        fx.cleanup()
    return ok, detail


def ap2_fabricated_digest() -> tuple[bool, str]:
    fx = S.Fixture()
    try:
        m = copy.deepcopy(fx.receipt)
        # well-formed hex that is NOT the digest of the on-disk bytes
        m["artifacts"][0]["sha256"] = "b" * 64
        r = fx.evaluate(m)
        c2 = r.condition(2)
        ok = (
            r.verdict is S.CP.Verdict.INCOMPLETE
            and c2.outcome is S.CP.Outcome.UNSATISFIED
            and "digest" in c2.basis.lower()
        )
        detail = "verdict=%s c2=%s %s" % (r.verdict.value, c2.outcome.value, c2.basis[:90])
    finally:
        fx.cleanup()
    return ok, detail


def ap3_path_in_text_lie() -> tuple[bool, str]:
    fx = S.Fixture()
    try:
        m = copy.deepcopy(fx.receipt)
        m["artifacts"][0]["path"] = "command-center/p2-wave/probes/CC-0003/_never_written.json"
        m["artifacts"][0]["exists"] = True  # the receipt LIES
        r = fx.evaluate(m)
        c2 = r.condition(2)
        ok = (
            r.verdict is S.CP.Verdict.INCOMPLETE
            and c2.outcome is S.CP.Outcome.UNSATISFIED
            and "exists=true" in c2.basis
        )
        detail = "verdict=%s c2 basis=%s" % (r.verdict.value, c2.basis[:90])
    finally:
        fx.cleanup()
    return ok, detail


def ap4_not_checked_distinct() -> tuple[bool, str]:
    fx = S.Fixture()
    try:
        fx.manifest_path.unlink()  # registration not measurable
        r = fx.evaluate()
        c11 = r.condition(11)
        ok = (
            r.verdict is not S.CP.Verdict.COMPLETE
            and c11.outcome is S.CP.Outcome.NOT_CHECKED
        )
        detail = "verdict=%s c11=%s (NOT-CHECKED blocks, never folds into PASS)" % (
            r.verdict.value, c11.outcome.value)
    finally:
        fx.cleanup()
    return ok, detail


def fanin_identity() -> tuple[bool, str]:
    sys.path.insert(0, str(REPO / "platform" / "lib"))
    import fanin  # noqa: E402
    import completion_predicate as CP  # noqa: E402
    sites_ok, sites = [], []
    import importlib
    for site in fanin.SITES:
        mod = importlib.import_module("fanin." + site)
        same = getattr(mod, "evaluate", None) is CP.evaluate
        sites_ok.append(same)
        sites.append("%s=%s" % (site, same))
    common = importlib.import_module("fanin._site_common")
    common_ok = common.evaluate is CP.evaluate
    ok = common_ok and all(sites_ok)
    detail = "site_common=%s %s" % (common_ok, " ".join(sites))
    return ok, detail


def real_receipt_liveness() -> tuple[bool, str]:
    doc = json.loads((REPO / REAL).read_text(encoding="utf-8"))
    errs = P.validate(doc, CATALOG_SCHEMA)
    if errs:
        return False, "%s schema errors: %s" % (len(errs), errs[0][:160])
    rv = doc.get("reviewer") or {}
    if rv.get("verdict") != "PASS" or rv.get("independent") is not True:
        return False, "reviewer closure missing: %s" % rv
    cat = None
    for u in json.loads(
        (REPO / "command-center/WORK-UNIT-CATALOG.json").read_text(encoding="utf-8")
    )["work_units"]:
        if u.get("id") == "CC-0003":
            cat = u
            break
    if cat is None:
        return False, "catalog entry absent"
    if str(cat.get("output_schema", "")).replace("\\", "/") != CATALOG_SCHEMA:
        return False, "catalog output_schema drift: %s" % cat.get("output_schema")
    # every declared artifact of the receipt exists on disk and supporting rows
    # carry live-correct digests (refreshed by the wave-2 completion pass)
    import hashlib
    for a in doc.get("artifacts", []):
        p = REPO / str(a.get("path"))
        if not p.is_file():
            return False, "declared artifact absent: %s" % a.get("path")
        if a.get("role") == "supporting" and isinstance(a.get("sha256"), str):
            live = hashlib.sha256(p.read_bytes()).hexdigest()
            if live != a["sha256"] and live != hashlib.sha256(
                p.read_bytes().replace(b"\r\n", b"\n")
            ).hexdigest():
                return False, "supporting digest drift: %s" % a.get("path")
    sent = str(doc.get("sentinel") or "")
    if sent not in (REPO / REAL).read_text(encoding="utf-8"):
        return False, "sentinel not in receipt text"
    return True, "schema 0 errors; reviewer PASS/independent; catalog schema match; artifacts live"


def main() -> int:
    checks = [
        ("AP1-exit-zero-alone", ap1_exit_zero_alone),
        ("AP2-fabricated-digest", ap2_fabricated_digest),
        ("AP3-path-in-text-lie", ap3_path_in_text_lie),
        ("AP4-not-checked-distinct", ap4_not_checked_distinct),
        ("fanin-import-identity", fanin_identity),
        ("real-receipt-liveness", real_receipt_liveness),
    ]
    bad = []
    for name, fn in checks:
        try:
            ok, detail = fn()
        except Exception as exc:  # noqa: BLE001 - a crashing check is a failed check
            ok, detail = False, "%s: %s" % (type(exc).__name__, exc)
        print("%-24s %s %s" % (name, "PASS" if ok else "FAIL", detail))
        if not ok:
            bad.append(name)
    if bad:
        print("FAILED:CC-0003-probe2 %s" % ",".join(bad))
        return 1
    print("SUCCESS:CC-0003-probe2 antipatterns blocked; identity + liveness hold")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
