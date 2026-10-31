#!/usr/bin/env python3
"""Wave-3 shard-3 INDEPENDENT REVIEWER - static (non-probe) checks, fresh derivation.

Per unit: C01 catalog entry / C02 artifact exists+nonempty / C03 parses /
C04 not self-blocked / C05 sentinel embedded / C06 SUBAGENT-RETURN sane /
C07 manifest sha256 row matches live artifact (CRLF->LF) / C08 schema valid
(schema_resolver.validate_artifact path) / receipt-row freshness (drives closure edit).
Writes static_results.json; always exits 0 (verdicts are data, not the transport).
"""
from __future__ import annotations
import hashlib
import json
import sys
from pathlib import Path

REPO = Path(r"C:\Users\Prekzursil\p2-g1")
sys.path.insert(0, str(REPO / "platform" / "lib"))
from schema_resolver import UnknownSchemaError  # noqa: E402

UNITS = ["ARC-0055", "ARC-0056", "ARC-0076", "AUD-0003", "AUD-0005", "AUD-0008",
         "AUD-0010", "AUD-0026", "AUD-0032", "AUD-0033", "AUD-0042", "AUD-0043"]
NOT_DELIVERING = {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}


def load(p: Path):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:  # noqa: BLE001 - verdict data, not transport
        return e


def lf_sha(p: Path) -> tuple[str, int]:
    raw = p.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


cat = load(REPO / "command-center" / "WORK-UNIT-CATALOG.json")
CAT = {u["id"]: u for u in cat["work_units"]} if isinstance(cat, dict) else {}
results = {}
for uid in UNITS:
    r: dict = {"unit_id": uid, "checks": {}, "detail": {}}
    c = r["checks"]
    # C01 catalog entry
    unit = CAT.get(uid)
    c["C01_catalog_entry"] = (isinstance(unit, dict)
                              and bool(unit.get("output_path"))
                              and bool(unit.get("output_schema")))
    if not c["C01_catalog_entry"]:
        r["detail"]["C01"] = "catalog entry missing output_path/output_schema"
        results[uid] = r
        continue
    out_rel = str(unit["output_path"]).replace("\\", "/")
    sch_rel = str(unit["output_schema"]).replace("\\", "/")
    r["detail"]["output_path"] = out_rel
    r["detail"]["output_schema"] = sch_rel
    r["detail"]["catalog_sentinel"] = unit.get("completion_sentinel")
    out = REPO / out_rel
    # C02 exists non-empty
    c["C02_artifact_nonempty"] = out.is_file() and out.stat().st_size > 0
    if not c["C02_artifact_nonempty"]:
        r["detail"]["C02"] = "absent-or-empty: %s" % out
        results[uid] = r
        continue
    raw = out.read_bytes()
    # C03 parses
    try:
        doc = json.loads(raw.decode("utf-8"))
        c["C03_parses"] = True
    except Exception as e:  # noqa: BLE001
        c["C03_parses"] = False
        r["detail"]["C03"] = "%s: %s" % (type(e).__name__, e)
        results[uid] = r
        continue
    # C04 not self-blocked
    st = str(doc.get("state") or doc.get("status") or "").upper()
    r["detail"]["artifact_state"] = st or None
    c["C04_not_self_blocked"] = st not in NOT_DELIVERING
    # C05 sentinel embedded
    sentinel = str(unit.get("completion_sentinel") or "")
    if sentinel:
        c["C05_sentinel_embeds"] = sentinel in raw.decode("utf-8", errors="replace")
        r["detail"]["sentinel"] = sentinel
    else:
        c["C05_sentinel_embeds"] = True  # catalog declares none; measure treats as N/A
    # C06 SUBAGENT-RETURN sane
    ret = load(REPO / "command-center" / "p2-wave" / "probes" / uid / "SUBAGENT-RETURN.json")
    if isinstance(ret, Exception):
        c["C06_return_sane"] = False
        r["detail"]["C06"] = repr(ret)[:200]
    else:
        rst = str(ret.get("status") or ret.get("state") or "").upper()
        c["C06_return_sane"] = isinstance(ret, dict) and rst not in NOT_DELIVERING
        r["detail"]["return_status"] = rst or None
        nps = ret.get("named_probes")
        r["detail"]["named_probe_cmds"] = [
            i.get("command") for i in (nps or [])
            if isinstance(i, dict) and i.get("command")]
    # C07 manifest sha row
    man = load(REPO / "command-center" / "p2-wave" / "probes" / uid / "UNIT-ARTIFACT-MANIFEST.json")
    live_sha, live_bytes = lf_sha(out)
    r["detail"]["live_sha256_lf"] = live_sha
    r["detail"]["live_bytes_lf"] = live_bytes
    if isinstance(man, Exception) or not isinstance(man, dict):
        c["C07_manifest_sha_match"] = False
        r["detail"]["C07"] = ("manifest unparseable: %r" % (man,))[:200]
    else:
        rows = [a for a in (man.get("artifacts") or [])
                if isinstance(a, dict) and a.get("unit_id") == uid]
        r["detail"]["manifest_rows"] = [
            {"path": a.get("path"), "sha256": a.get("sha256"), "present": a.get("present")}
            for a in rows]
        c["C07_manifest_sha_match"] = any(
            str(a.get("path") or "").replace("\\", "/") == out_rel
            and str(a.get("sha256") or "") == live_sha
            and a.get("present") is True
            for a in rows)
    # C08 schema validation (blessed resolver path: validate_artifact)
    from schema_resolver import validate_artifact, SchemaResolutionError
    try:
        errs = validate_artifact(doc, sch_rel)
        c["C08_schema_valid"] = not errs
        r["detail"]["schema_errors_first"] = errs[:8]
        r["detail"]["n_schema_errors"] = len(errs)
    except (UnknownSchemaError, SchemaResolutionError) as e:
        c["C08_schema_valid"] = False
        r["detail"]["C08"] = ("resolution failed: %s" % e)[:300]
    except Exception as e:  # noqa: BLE001
        c["C08_schema_valid"] = False
        r["detail"]["C08"] = ("%s: %s" % (type(e).__name__, e))[:300]
    # receipt freshness (drives the closure edit, informational here)
    rec = load(REPO / "command-center" / "receipts" / (uid + ".json"))
    if isinstance(rec, Exception) or not isinstance(rec, dict):
        r["detail"]["receipt"] = "unparseable"
    else:
        rows = [a for a in (rec.get("artifacts") or [])
                if isinstance(a, dict)
                and str(a.get("path") or "").replace("\\", "/") == out_rel]
        if rows:
            a = rows[0]
            r["detail"]["receipt_row"] = {"sha256": a.get("sha256"), "bytes": a.get("bytes")}
            r["detail"]["receipt_row_stale"] = (a.get("sha256") != live_sha)
        r["detail"]["receipt_state"] = rec.get("state")
        r["detail"]["receipt_status"] = rec.get("status")
        f = rec.get("failure")
        r["detail"]["failure_classification"] = (
            (f or {}).get("classification") if isinstance(f, dict) else None)
        r["detail"]["reviewer_block"] = rec.get("reviewer")
    results[uid] = r

out = REPO / "_review-w3s3-r2" / "static_results.json"
out.write_text(json.dumps(results, indent=1, ensure_ascii=False),
               encoding="utf-8", newline="\n")
all_ok = all(all(results[u]["checks"].values()) for u in UNITS)
for uid in UNITS:
    r = results[uid]
    bad = [k for k, v in r["checks"].items() if v is False]
    print(uid, "OK" if not bad else "STATIC-FAIL %s" % bad)
print(("SUCCESS:static checks complete 12 units" if all_ok
       else "FAILED:some static checks red (see static_results.json)"))
