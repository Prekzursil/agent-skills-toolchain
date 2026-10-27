#!/usr/bin/env python3
"""Independent reviewer static battery - wave 4 shard 10 (12 units).

MY OWN instrument (fresh context, did not build these units). Checks, per unit:
  S1 catalog entry exists with output_path/output_schema/dependencies + a description
     slot (this catalog uses question_or_target; probes may be absent at catalog level -
     named probes live in probes/<id>/ + SUBAGENT-RETURN.json)
  S2 artifact at output_path exists, non-empty, parses as JSON
  S3 artifact self-declared state recorded (NOT_DELIVERING = BLOCKED/FAILED/SEVERED/TIMEOUT
     is a FAIL except a reviewer-absent BLOCKED awaiting my closure, tracked separately)
  S4 UNIT-ARTIFACT-MANIFEST.json: parses; >=1 row for the unit; EVERY row's path exists
     and its sha256 (CRLF->LF normalized) equals live bytes; receipt row present=True
  S5 receipt validates against the catalog output_schema (receipt.schema.json ->
     receipt_core) via platform.lib.receipt_schema_gate.validate_receipt (Layer 1)
  S6 admission receipt_validate.admit_doc (C1 parse / C2 schema / C3 catalog / C4
     sentinel / C5 internal digest) - recorded; C5 surfaced, not silently folded
  S7 completion_sentinel of the unit appears in the receipt text

Exit 0 + SUCCESS marker only when all mandatory checks hold for all units.
Writes _reviewer-w4s10/static_results.json.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

REPO = Path(r"C:/Users/Prekzursil/p2-g1")
OUT = REPO / "_reviewer-w4s10" / "static_results.json"
UNITS = [
    "IMP-0189", "IMP-0194", "IMP-0195", "IMP-0198", "IMP-0202", "IMP-0204",
    "IMP-0207", "IMP-0219", "IMP-0223", "IMP-0224", "IMP-0228", "IMP-0229",
]
NOT_DELIVERING = {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}

sys.path.insert(0, str(REPO / "platform" / "lib"))
sys.path.insert(0, str(REPO / "command-center"))


def lf_sha(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def main() -> int:
    import receipt_validate  # command-center/receipt_validate.py
    from receipt_schema_gate import load_schema, parse_schema_ref, validate_receipt

    catalog = json.loads((REPO / "command-center/WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
    byid = {u.get("id"): u for u in catalog.get("work_units", []) if isinstance(u, dict)}
    schema_cache: dict[str, dict] = {}

    results: dict[str, dict] = {}
    all_ok = True
    for uid in UNITS:
        r: dict = {"unit": uid, "checks": {}, "notes": [], "fails": []}
        c = r["checks"]

        # S1 catalog
        u = byid.get(uid)
        has_desc = bool(u) and bool(str(u.get("description") or u.get("question_or_target") or "").strip())
        c["catalog_entry"] = bool(u) and all(
            u.get(k) not in (None, "") for k in ("output_path", "output_schema", "dependencies")
        ) and has_desc
        r["catalog_probes_key"] = "probes" in (u or {})
        if not c["catalog_entry"]:
            r["fails"] = ["S1 catalog entry missing/incomplete"]
            results[uid] = r
            all_ok = False
            continue

        # S2 artifact exists/non-empty/parses
        out_rel = str(u["output_path"]).replace("\\", "/")
        out = REPO / out_rel
        ok = out.is_file() and out.stat().st_size > 0
        c["artifact_exists_nonempty"] = ok
        doc = None
        if ok:
            try:
                doc = json.loads(out.read_text(encoding="utf-8"))
            except Exception as exc:  # noqa: BLE001
                c["artifact_parses"] = False
                r["fails"] = [f"S2 unparseable: {type(exc).__name__}"]
                results[uid] = r
                all_ok = False
                continue
            c["artifact_parses"] = True
        else:
            r["fails"] = ["S2 artifact absent or empty"]
            results[uid] = r
            all_ok = False
            continue

        # S3 self-declared state
        state = str((doc or {}).get("state") or "").upper()
        r["state"] = state
        fc = [str(x) for x in ((doc or {}).get("failure") or {}).get("classification", [])]
        awaiting_review = state == "BLOCKED" and fc == ["reviewer-absent"]
        r["awaiting_review"] = awaiting_review
        c["not_self_blocked"] = state not in NOT_DELIVERING or awaiting_review

        # S4 manifest rows: every row present + sha matches live bytes
        man_path = REPO / "command-center/p2-wave/probes" / uid / "UNIT-ARTIFACT-MANIFEST.json"
        try:
            man = json.loads(man_path.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001
            c["manifest"] = False
            r["fails"] = [f"S4 manifest unreadable: {type(exc).__name__}"]
            results[uid] = r
            all_ok = False
            continue
        rows = [a for a in (man.get("artifacts") or []) if isinstance(a, dict) and a.get("unit_id") == uid]
        c["manifest_row_count"] = len(rows)
        row_report = []
        receipt_row_ok = False
        manifest_ok = len(rows) > 0
        for a in rows:
            rel = str(a.get("path") or "").replace("\\", "/")
            p = REPO / rel
            if not p.is_file():
                manifest_ok = False
                row_report.append({"path": rel, "present": False, "sha_match": None})
                continue
            sha, nbytes = lf_sha(p)
            match = str(a.get("sha256") or "") == sha
            row_report.append({"path": rel, "present": True, "sha_match": match, "live_bytes": nbytes})
            if not match:
                manifest_ok = False
            if rel == out_rel and match and a.get("present") is True:
                receipt_row_ok = True
        c["manifest_receipt_row_sha_match"] = receipt_row_ok
        c["manifest_all_rows_match"] = manifest_ok
        r["manifest_rows"] = row_report
        c["manifest"] = receipt_row_ok and manifest_ok

        # S5 output_schema validation (Layer 1, platform gate)
        schema_rel, frag = parse_schema_ref(str(u.get("output_schema") or ""))
        try:
            schema = schema_cache.get(schema_rel)
            if schema is None:
                schema = load_schema(REPO / schema_rel)
                schema_cache[schema_rel] = schema
            errs = validate_receipt(doc, schema=schema, fragment=frag)
            c["output_schema_valid"] = not errs
            if errs:
                r.setdefault("fails", []).append(f"S5 schema errors ({len(errs)}): {errs[0][:200]}")
        except Exception as exc:  # noqa: BLE001
            c["output_schema_valid"] = False
            r.setdefault("fails", []).append(f"S5 schema validation raised: {type(exc).__name__}: {exc}")

        # S6 admission (C1..C5)
        try:
            verdict, codes, reasons = receipt_validate.admit_doc(doc, repo=REPO)
            c["admission"] = verdict
            r["admission_codes"] = codes
            if verdict != "ACCEPT":
                r["admission_reasons"] = [str(x)[:180] for x in reasons[:4]]
                if "C5" in codes:
                    r["notes"].append("C5 internal-digest drift: " + str(reasons[:2]))
        except Exception as exc:  # noqa: BLE001
            c["admission"] = f"RAISED {type(exc).__name__}: {exc}"

        # S7 sentinel in text
        sentinel = str(u.get("completion_sentinel") or "")
        c["sentinel_present"] = (not sentinel) or (sentinel in out.read_text(encoding="utf-8"))
        if not c["sentinel_present"]:
            r["fails"].append(f"S7 sentinel {sentinel!r} absent from artifact text")

        mandatory = [
            c["catalog_entry"], c["artifact_exists_nonempty"], c["artifact_parses"],
            c["not_self_blocked"], c["manifest"], c["output_schema_valid"],
            c["sentinel_present"],
        ]
        r["ok"] = all(bool(x) for x in mandatory)
        if not r["ok"] and not r.get("fails"):
            r["fails"] = [f"S check false: {k}" for k, v in c.items() if v is False]
        all_ok &= r["ok"]
        results[uid] = r

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(results, indent=1) + "\n", encoding="utf-8", newline="\n")
    for uid in UNITS:
        r = results[uid]
        flag = "OK " if r.get("ok") else "FAIL"
        print(f"{flag} {uid} state={r.get('state')} awaiting_review={r.get('awaiting_review')} "
              f"manifest_rows={r['checks'].get('manifest_row_count')} "
              f"admission={r['checks'].get('admission')} "
              f"schema={'ok' if r['checks'].get('output_schema_valid') else 'INVALID'} "
              f"sentinel={'ok' if r['checks'].get('sentinel_present') else 'ABSENT'}")
        for f in r.get("fails", [])[:4]:
            print(f"     - {f}")
        for n in r.get("notes", [])[:2]:
            print(f"     note: {n[:200]}")
    n_ok = sum(1 for u in UNITS if results[u].get("ok"))
    print(f"{'SUCCESS' if all_ok else 'FAILED'}:reviewer-w4s10 static battery {n_ok}/{len(UNITS)} units hold all static checks")
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
