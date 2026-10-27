#!/usr/bin/env python3
"""Wave-4 shard-0 independent reviewer -- passive verification battery (12 units).

Re-derives, in THIS fresh context, for each unit:
  C1 catalog    : id in WORK-UNIT-CATALOG.json; output_path + output_schema present
  C2 artifact   : exists at catalog output_path, non-empty, parses, not self-declared
                  BLOCKED/FAILED/SEVERED/TIMEOUT
  C3 manifest   : command-center/p2-wave/probes/<id>/UNIT-ARTIFACT-MANIFEST.json has a
                  row for this unit at output_path with present=true and sha256 equal to
                  the LIVE artifact's CRLF->LF-normalized sha256
  C4 schema     : artifact validates against its catalog output_schema via
                  platform/lib/schema_resolver.validate_artifact (errors must be empty)
  C5 receipt    : receipt parses; state=SUCCESS; reviewer.verdict=PASS;
                  reviewer.independent=true (receipt_core rule); ALSO cross-checks the
                  receipt's primary-artifact sha against the live file (staleness note)
Read-only. Emits one JSON verdict table. Fails closed on every unexpected condition.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

REPO = Path(r"C:\Users\Prekzursil\p2-g1")
CATALOG = REPO / "command-center/WORK-UNIT-CATALOG.json"
PROBES = REPO / "command-center/p2-wave/probes"
RECEIPTS = REPO / "command-center/receipts"
UNITS = ["ADV-0005", "ADV-0010", "ADV-0014", "ADV-0015", "ADV-0018", "ADV-0019",
         "ADV-0022", "ADV-0023", "ADV-0024", "ADV-0028", "ADV-0029", "ADV-0037"]
NOT_DELIVERING = {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}
OUT_PATH = REPO / "_reviewer-w4s0" / "passive-results.json"


def lf_sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def raw_sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def load_resolver():
    p = REPO / "platform" / "lib" / "schema_resolver.py"
    sys.path.insert(0, str(p.parent))
    import importlib.util
    spec = importlib.util.spec_from_file_location("schema_resolver", p)
    if spec is None or spec.loader is None:
        raise SystemExit("FAILED:reviewer-w4s0 cannot load schema_resolver")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["schema_resolver"] = mod
    spec.loader.exec_module(mod)
    return mod


def main() -> int:
    cat = json.loads(CATALOG.read_text(encoding="utf-8"))
    entries = {u["id"]: u for u in cat["work_units"] if isinstance(u.get("id"), str)}
    resolver = load_resolver()

    results = {}
    for uid in UNITS:
        r: dict = {"unit": uid, "checks": {}, "fail": []}

        def fail(check: str, detail: str) -> None:
            r["fail"].append(f"{check}: {detail}")

        # C1 catalog
        ce = entries.get(uid)
        r["checks"]["catalog"] = bool(ce)
        if not ce:
            fail("catalog", "id absent from WORK-UNIT-CATALOG")
            results[uid] = r
            continue
        opath = str(ce.get("output_path") or "")
        oschema = str(ce.get("output_schema") or "")
        r["output_path"] = opath
        r["output_schema"] = oschema
        if not opath or not oschema:
            fail("catalog", f"output_path/output_schema missing ({opath!r}, {oschema!r})")
        r["checks"]["catalog_fields"] = bool(opath) and bool(oschema)

        # C2 artifact
        art = REPO / opath
        r["art_bytes"] = art.stat().st_size if art.is_file() else None
        doc = None
        if not art.is_file():
            fail("artifact", "absent at catalog output_path")
        elif art.stat().st_size == 0:
            fail("artifact", "zero bytes")
        else:
            try:
                doc = json.loads(art.read_text(encoding="utf-8"))
                r["checks"]["artifact_parses"] = True
            except Exception as exc:
                fail("artifact", f"unparseable JSON: {type(exc).__name__}")
            st = ""
            if isinstance(doc, dict):
                st = str(doc.get("state") or "").upper()
                r["art_state"] = st
                uid_field = str(doc.get("unit_id") or doc.get("id") or "")
                r["art_unit_id"] = uid_field
                if st in NOT_DELIVERING:
                    fail("artifact", f"self-declared {st}")
                if uid_field and uid_field != uid:
                    fail("artifact", f"unit_id field is {uid_field!r}")
            else:
                fail("artifact", "top-level value is not an object")
        r["checks"]["artifact"] = art.is_file() and art.stat().st_size > 0 and doc is not None

        # C3 manifest byte-compare (CRLF->LF)
        man_p = PROBES / uid / "UNIT-ARTIFACT-MANIFEST.json"
        r["checks"]["manifest"] = False
        if not man_p.is_file():
            fail("manifest", "UNIT-ARTIFACT-MANIFEST.json absent")
        elif art.is_file():
            try:
                man = json.loads(man_p.read_text(encoding="utf-8"))
            except Exception as exc:
                man = None
                fail("manifest", f"unparseable: {type(exc).__name__}")
            if isinstance(man, dict):
                rows = [a for a in (man.get("artifacts") or [])
                        if isinstance(a, dict) and a.get("unit_id") == uid]
                match = [a for a in rows
                         if str(a.get("path") or "").replace("\\", "/") == opath
                         and a.get("present") is True]
                live = lf_sha(art)
                r["live_lf_sha"] = live
                r["manifest_rows"] = [
                    {"path": a.get("path"), "sha256": a.get("sha256"),
                     "bytes": a.get("bytes"), "present": a.get("present")}
                    for a in rows]
                if not rows:
                    fail("manifest", "no row for this unit")
                elif not match:
                    fail("manifest", "row present but path/present-flag mismatch")
                elif match[0].get("sha256") != live:
                    fail("manifest",
                         f"sha mismatch live={live[:16]} manifest={str(match[0].get('sha256'))[:16]}")
                else:
                    r["checks"]["manifest"] = True

        # C4 schema validation (only meaningful on a parsed doc)
        r["checks"]["schema"] = False
        if doc is not None and isinstance(doc, dict) and oschema:
            try:
                errs = resolver.validate_artifact(doc, oschema)
            except Exception as exc:
                errs = [f"resolver-raised {type(exc).__name__}: {exc}"]
            r["schema_errors"] = errs
            if errs:
                fail("schema", "; ".join(str(e)[:120] for e in errs[:3]))
            else:
                r["checks"]["schema"] = True

        # C5 receipt + receipt_core rule + receipt-primary-sha cross-check
        rec_p = RECEIPTS / f"{uid}.json"
        r["checks"]["receipt"] = False
        if not rec_p.is_file():
            fail("receipt", "receipt absent")
        else:
            try:
                rec = json.loads(rec_p.read_text(encoding="utf-8"))
                r["checks"]["receipt_parses"] = True
            except Exception as exc:
                rec = None
                fail("receipt", f"unparseable: {type(exc).__name__}")
            if isinstance(rec, dict):
                rv = rec.get("reviewer") or {}
                state = str(rec.get("state") or "")
                verdict = str(rv.get("verdict") or "")
                indep = rv.get("independent")
                r["receipt"] = {"state": state, "reviewer_id": rv.get("reviewer_id"),
                                "verdict": verdict, "independent": indep,
                                "reviewed_at": rv.get("reviewed_at")}
                if state == "SUCCESS" and not (verdict == "PASS" and indep is True):
                    fail("receipt-core", f"state=SUCCESS without reviewer PASS+independent "
                                         f"(verdict={verdict!r}, independent={indep!r})")
                if state in NOT_DELIVERING:
                    fail("receipt", f"receipt state={state}")
                # receipt_core-shaped docs
                fcore = rec.get("receipt_core")
                if isinstance(fcore, dict):
                    fc_state = str(fcore.get("state") or "")
                    r["receipt"]["core_state"] = fc_state
                    if fc_state == "SUCCESS" and not (verdict == "PASS" and indep is True):
                        fail("receipt-core", "receipt_core.state=SUCCESS without PASS+independent")
                # cross-check receipt primary artifact sha vs live (staleness note only)
                prim = [a for a in (rec.get("artifacts") or [])
                        if isinstance(a, dict) and a.get("role") == "primary"]
                if art.is_file() and prim:
                    live_raw = raw_sha(art)
                    live_lf = lf_sha(art)
                    rsha = prim[0].get("sha256")
                    r["receipt_primary_sha_matches"] = rsha in (live_raw, live_lf)
                    if rsha not in (live_raw, live_lf):
                        r["receipt_sha_stale"] = {"receipt": str(rsha)[:16],
                                                  "live_raw": live_raw[:16],
                                                  "live_lf": live_lf[:16]}
                if verdict == "PASS" and indep is True and state == "SUCCESS":
                    r["checks"]["receipt"] = True

        r["PASS_PASSIVE"] = not r["fail"]
        results[uid] = r

    OUT_PATH.write_text(json.dumps(results, indent=1), encoding="utf-8")
    n_pass = sum(1 for v in results.values() if v.get("PASS_PASSIVE"))
    print(f"reviewer-w4s0 passive battery: {n_pass}/{len(UNITS)} units all-checks-hold")
    for uid, v in results.items():
        mark = "PASS" if v.get("PASS_PASSIVE") else "FAIL"
        print(f"  {uid} {mark} {v['fail'] if v['fail'] else ''}")
    return 0 if n_pass == len(UNITS) else 1


if __name__ == "__main__":
    raise SystemExit(main())
